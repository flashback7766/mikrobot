"""
Low-level async RouterOS API client.

Features:
  - Full sentence encode/decode with binary length framing
  - MD5 challenge-response login (ROS6 compatible, also ROS7)
  - Plain-text login fallback for ROS7
  - Request tag multiplexing (multiple concurrent commands)
  - Streaming command support (e.g., /log/print follow=yes)
  - Automatic reconnect with exponential backoff
  - SSL support for port 8729
"""

import asyncio
import logging
import struct
from typing import AsyncIterator, Optional

from .api_protocol import (
    build_sentence,
    decode_length,
    decode_sentence,
    md5_challenge_response,
    parse_response,
)

log = logging.getLogger("RouterClient")

_RECV_BUF = 65536
_RECONNECT_DELAYS = [1, 2, 5, 10, 30]


class APIError(Exception):
    """Raised when RouterOS returns !trap or !fatal."""
    def __init__(self, message: str, category: str = ""):
        super().__init__(message)
        self.category = category


class RouterAPIClient:
    """
    Thread-safe async RouterOS API client.

    Usage:
        client = RouterAPIClient("192.168.88.1", "admin", "", port=8728)
        await client.connect()
        results = await client.command("/ip/address/print")
        async for row in client.stream("/log/print", {"follow": ""}):
            print(row)
        await client.close()
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 8728,
        timeout: float = 10.0,
        use_ssl: bool = False,
        ros_version: int = 6,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.use_ssl = use_ssl
        self.ros_version = ros_version

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._lock = asyncio.Lock()
        self._tag_counter = 0
        # tag -> asyncio.Queue for multiplexed responses
        self._pending: dict[int, asyncio.Queue] = {}
        self._recv_task: Optional[asyncio.Task] = None
        self._buf = b""
        # Incremented on each connect() so stale receiver loops don't
        # overwrite _connected after a fresh connection is established.
        self._conn_gen = 0

    # ─── Connection ───────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        try:
            ssl_ctx = None
            if self.use_ssl:
                import ssl
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE

            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port, ssl=ssl_ctx),
                timeout=self.timeout,
            )
            self._connected = True
            self._buf = b""
            self._conn_gen += 1
            my_gen = self._conn_gen

            # Start background receiver
            self._recv_task = asyncio.create_task(self._receiver_loop(my_gen))

            # Authenticate
            await self._login()

            # Verify the receiver loop didn't crash during login
            if not self._connected or self._conn_gen != my_gen:
                log.warning(f"Connection lost during login to {self.host}:{self.port}")
                return False

            log.info(f"Connected to {self.host}:{self.port} (ROS{self.ros_version})")
            return True

        except Exception as e:
            log.warning(f"Cannot connect to {self.host}:{self.port}: {e}")
            self._connected = False
            return False

    async def close(self):
        self._connected = False
        if self._recv_task:
            self._recv_task.cancel()
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

    @property
    def connected(self) -> bool:
        return self._connected

    # ─── Authentication ───────────────────────────────────────────────────────

    async def _login(self):
        if self.ros_version >= 7:
            await self._login_ros7()
        else:
            await self._login_ros6()

    async def _login_ros6(self):
        """ROS6: two-step MD5 challenge login."""
        tag = self._next_tag()
        await self._send_raw(build_sentence(["/login", f".tag={tag}"]))
        resp = await self._read_one(tag)
        if resp["type"] == "!trap":
            raise APIError(f"Login rejected: {resp['attrs']}")

        challenge = resp["attrs"].get("ret", "")
        digest = md5_challenge_response(self.password, challenge)

        tag2 = self._next_tag()
        await self._send_raw(build_sentence([
            "/login",
            f"=name={self.username}",
            f"=response=00{digest}",
            f".tag={tag2}",
        ]))
        resp2 = await self._read_one(tag2)
        if resp2["type"] == "!trap":
            raise APIError(f"Authentication failed: {resp2['attrs']}")

    async def _login_ros7(self):
        """ROS7: single-step plain+MD5 login (tries plain first)."""
        tag = self._next_tag()
        await self._send_raw(build_sentence([
            "/login",
            f"=name={self.username}",
            f"=password={self.password}",
            f".tag={tag}",
        ]))
        resp = await self._read_one(tag)
        if resp["type"] == "!trap":
            # Fallback to MD5 (some ROS7 configs require it)
            challenge = resp["attrs"].get("ret", "")
            if challenge:
                digest = md5_challenge_response(self.password, challenge)
                tag2 = self._next_tag()
                await self._send_raw(build_sentence([
                    "/login",
                    f"=name={self.username}",
                    f"=response=00{digest}",
                    f".tag={tag2}",
                ]))
                resp2 = await self._read_one(tag2)
                if resp2["type"] == "!trap":
                    raise APIError(f"Authentication failed: {resp2['attrs']}")
            else:
                raise APIError(f"Authentication failed: {resp['attrs']}")

    # ─── Command Execution ────────────────────────────────────────────────────

    async def command(
        self,
        path: str,
        params: dict | None = None,
        queries: list[str] | None = None,
    ) -> list[dict]:
        """Execute a command and return all !re responses."""
        tag = self._next_tag()
        words = self._build_words(path, params, queries, tag)

        q: asyncio.Queue = asyncio.Queue()
        self._pending[tag] = q

        try:
            async with self._lock:
                await self._send_raw(build_sentence(words))

            results = []
            while True:
                resp = await asyncio.wait_for(q.get(), timeout=self.timeout)
                if resp["type"] == "!re":
                    results.append(resp["attrs"])
                elif resp["type"] == "!done":
                    break
                elif resp["type"] in ("!trap", "!fatal"):
                    msg = resp["attrs"].get("message", str(resp["attrs"]))
                    cat = resp["attrs"].get("category", "")
                    raise APIError(msg, cat)
            return results

        finally:
            self._pending.pop(tag, None)

    async def stream(
        self,
        path: str,
        params: dict | None = None,
        queries: list[str] | None = None,
    ) -> AsyncIterator[dict]:
        """
        Stream !re responses (for follow=yes commands).
        Yields attr dicts until cancelled or connection drops.
        """
        tag = self._next_tag()
        words = self._build_words(path, params, queries, tag)

        q: asyncio.Queue = asyncio.Queue()
        self._pending[tag] = q

        try:
            async with self._lock:
                await self._send_raw(build_sentence(words))

            while True:
                resp = await asyncio.wait_for(q.get(), timeout=60.0)
                if resp["type"] == "!re":
                    yield resp["attrs"]
                elif resp["type"] == "!done":
                    break
                elif resp["type"] in ("!trap", "!fatal"):
                    msg = resp["attrs"].get("message", str(resp["attrs"]))
                    raise APIError(msg)
        finally:
            # Send /cancel to stop the streaming command
            try:
                cancel_tag = self._next_tag()
                await self._send_raw(build_sentence([
                    "/cancel",
                    f"=tag={tag}",
                    f".tag={cancel_tag}",
                ]))
            except Exception:
                pass
            self._pending.pop(tag, None)

    async def command_one(self, path: str, params: dict | None = None) -> dict | None:
        """Execute and return first result or None."""
        results = await self.command(path, params)
        return results[0] if results else None

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _next_tag(self) -> int:
        self._tag_counter = (self._tag_counter + 1) % 65535
        return self._tag_counter

    @staticmethod
    def _build_words(
        path: str,
        params: dict | None,
        queries: list[str] | None,
        tag: int,
    ) -> list[str]:
        words = [path]
        if params:
            for k, v in params.items():
                if v == "" or v is None:
                    words.append(f"={k}=")
                else:
                    words.append(f"={k}={v}")
        if queries:
            words.extend(queries)
        words.append(f".tag={tag}")
        return words

    async def _send_raw(self, data: bytes):
        if not self._connected or self._writer is None:
            raise ConnectionError("Not connected")
        self._writer.write(data)
        await self._writer.drain()

    async def _read_one(self, tag: int) -> dict:
        """Wait for the next response for a specific tag (used during login)."""
        q: asyncio.Queue = asyncio.Queue()
        self._pending[tag] = q
        try:
            resp = await asyncio.wait_for(q.get(), timeout=self.timeout)
            return resp
        finally:
            self._pending.pop(tag, None)

    async def _receiver_loop(self, gen: int):
        """Background task: reads bytes, decodes sentences, dispatches to queues."""
        # WinError codes that are transient on Windows TCP sockets and can be retried
        _TRANSIENT_WINERRORS = {64, 121, 995}
        _MAX_TRANSIENT_RETRIES = 5
        transient_retries = 0

        try:
            while self._connected and self._reader and self._conn_gen == gen:
                try:
                    chunk = await self._reader.read(_RECV_BUF)
                except OSError as e:
                    winerror = getattr(e, "winerror", None)
                    if winerror in _TRANSIENT_WINERRORS and transient_retries < _MAX_TRANSIENT_RETRIES:
                        transient_retries += 1
                        log.debug(f"Transient socket error (retry {transient_retries}/{_MAX_TRANSIENT_RETRIES}): {e}")
                        await asyncio.sleep(0.1)
                        continue
                    log.warning(f"Receiver loop error: {e}")
                    break

                if not chunk:
                    break

                transient_retries = 0  # reset on successful read
                self._buf += chunk
                self._dispatch_buf()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning(f"Receiver loop error: {e}")
        finally:
            # Only mark disconnected if this loop still owns the current connection
            if self._conn_gen == gen:
                self._connected = False
                # Unblock all waiters with fatal
                for q in self._pending.values():
                    await q.put({"type": "!fatal", "tag": None, "attrs": {"message": "disconnected"}})

    def _dispatch_buf(self):
        """Extract complete sentences from buffer and dispatch."""
        offset = 0
        while offset < len(self._buf):
            try:
                words, new_offset = decode_sentence(self._buf, offset)
            except BufferError:
                break  # need more data

            if not words:
                offset += 1  # skip zero byte
                continue

            offset = new_offset
            resp = parse_response(words)
            tag = resp.get("tag")

            if tag is not None and tag in self._pending:
                self._pending[tag].put_nowait(resp)
            else:
                # Untagged or unknown – log it
                log.debug(f"Untagged response: {resp}")

        self._buf = self._buf[offset:]
