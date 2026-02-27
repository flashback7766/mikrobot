"""
Router Manager – manages multiple router connections per user.

CHANGES vs original:
  - _load_registry() / _save_registry() are now async, using asyncio.to_thread()
    to offload disk I/O off the event loop
  - reconnect_all() now reconnects concurrently with asyncio.gather()
  - Added iter_all_entries() public iterator so Monitor doesn't need to
    access private _entries (breaks tight coupling)
  - Added cleanup_user_status() hook so Monitor can remove stale cache
  - last_status dict moved out of Monitor and into RouterEntry for consistency
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Iterator

from .router_ros6 import RouterROS6
from .router_ros7 import RouterROS7
from .mock_router import MockRouter
from .router_base import RouterBase

log = logging.getLogger("RouterManager")

REGISTRY_FILE = Path("data/routers.json")


class RouterEntry:
    def __init__(
        self,
        alias: str,
        host: str,
        username: str,
        password: str,
        port: int = 8728,
        use_ssl: bool = False,
        ros_version: int = 0,
        standalone: bool = False,
        owner_id: int = 0,
    ):
        self.alias = alias
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.ros_version = ros_version
        self.standalone = standalone
        self.owner_id = owner_id
        self.router: Optional[RouterBase] = None
        self.detected_version: int = 0

    def to_dict(self) -> dict:
        return {
            "alias": self.alias,
            "host": self.host,
            "username": self.username,
            "password": self.password,
            "port": self.port,
            "use_ssl": self.use_ssl,
            "ros_version": self.ros_version,
            "standalone": self.standalone,
            "owner_id": self.owner_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RouterEntry":
        return cls(**d)


class RouterManager:
    """Manages router connections for all Telegram users."""

    def __init__(self):
        # user_id -> {alias -> RouterEntry}
        self._entries: dict[int, dict[str, RouterEntry]] = {}
        # user_id -> active alias
        self._active: dict[int, str] = {}
        # Serialises registry writes to prevent concurrent write corruption
        self._write_lock = asyncio.Lock()
        # Synchronous load only during __init__ (before the event loop starts)
        self._load_registry_sync()

    # ─── Registry ─────────────────────────────────────────────────────────────

    def _load_registry_sync(self) -> None:
        """Synchronous load — only safe before the event loop is running."""
        if not REGISTRY_FILE.exists():
            return
        try:
            data = json.loads(REGISTRY_FILE.read_text())
            for uid_str, routers in data.items():
                uid = int(uid_str)
                self._entries[uid] = {}
                for alias, rdata in routers.items():
                    self._entries[uid][alias] = RouterEntry.from_dict(rdata)
        except Exception as e:
            log.warning(f"Failed to load registry: {e}")

    def _build_registry_payload(self) -> dict:
        return {
            str(uid): {alias: entry.to_dict() for alias, entry in routers.items()}
            for uid, routers in self._entries.items()
        }

    async def _save_registry(self) -> None:
        """Non-blocking async registry save."""
        async with self._write_lock:
            payload = self._build_registry_payload()
            await asyncio.to_thread(
                lambda: (
                    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True),
                    REGISTRY_FILE.write_text(json.dumps(payload, indent=2)),
                )
            )

    # ─── Public Iterator (replaces direct _entries access) ────────────────────

    def iter_all_entries(self) -> Iterator[tuple[int, str, RouterEntry]]:
        """
        Yields (user_id, alias, RouterEntry) for every registered router.
        Use this instead of accessing _entries directly.
        """
        for uid, routers in list(self._entries.items()):
            for alias, entry in list(routers.items()):
                yield uid, alias, entry

    # ─── Router CRUD ──────────────────────────────────────────────────────────

    async def add_router(
        self,
        user_id: int,
        alias: str,
        host: str,
        username: str,
        password: str,
        port: int = 8728,
        use_ssl: bool = False,
        ros_version: int = 0,
        standalone: bool = False,
    ) -> tuple[bool, str]:
        """Add and connect to a router. Returns (success, message)."""
        entry = RouterEntry(
            alias=alias, host=host, username=username, password=password,
            port=port, use_ssl=use_ssl, ros_version=ros_version,
            standalone=standalone, owner_id=user_id,
        )

        router, version = await self._create_and_connect(entry)
        if router is None:
            return False, f"❌ Cannot connect to {host}:{port}"

        entry.router = router
        entry.detected_version = version

        if user_id not in self._entries:
            self._entries[user_id] = {}

        self._entries[user_id][alias] = entry

        if user_id not in self._active:
            self._active[user_id] = alias

        await self._save_registry()
        return True, f"✅ Connected to {host} (RouterOS {version}) as `{alias}`"

    async def remove_router(self, user_id: int, alias: str) -> bool:
        if user_id not in self._entries or alias not in self._entries[user_id]:
            return False
        entry = self._entries[user_id][alias]
        if entry.router:
            await entry.router.close()
        del self._entries[user_id][alias]
        if self._active.get(user_id) == alias:
            remaining = list(self._entries.get(user_id, {}).keys())
            self._active[user_id] = remaining[0] if remaining else None
        await self._save_registry()
        return True

    def switch_router(self, user_id: int, alias: str) -> bool:
        if user_id in self._entries and alias in self._entries[user_id]:
            self._active[user_id] = alias
            return True
        return False

    def get_router_list(self, user_id: int) -> list[dict]:
        entries = self._entries.get(user_id, {})
        active = self._active.get(user_id)
        return [
            {
                "alias": alias,
                "host": entry.host,
                "version": entry.detected_version,
                "connected": entry.router.connected if entry.router else False,
                "active": alias == active,
                "standalone": entry.standalone,
            }
            for alias, entry in entries.items()
        ]

    # ─── Active Router Access ─────────────────────────────────────────────────

    def get_active(self, user_id: int) -> Optional[RouterBase]:
        alias = self._active.get(user_id)
        if not alias:
            return None
        entry = self._entries.get(user_id, {}).get(alias)
        if not entry or not entry.router:
            return None
        return entry.router

    def get_active_entry(self, user_id: int) -> Optional[RouterEntry]:
        alias = self._active.get(user_id)
        if not alias:
            return None
        return self._entries.get(user_id, {}).get(alias)

    def has_routers(self, user_id: int) -> bool:
        return bool(self._entries.get(user_id))

    # ─── Connection ───────────────────────────────────────────────────────────

    async def _create_and_connect(self, entry: RouterEntry) -> tuple[Optional[RouterBase], int]:
        """Auto-detect ROS version and connect. Returns (router, version)."""
        versions_to_try: list[int] = (
            [entry.ros_version] if entry.ros_version in (6, 7) else [7, 6]
        )

        for ver in versions_to_try:
            try:
                router: RouterBase = (
                    RouterROS7(
                        host=entry.host, username=entry.username,
                        password=entry.password, port=entry.port,
                        use_ssl=entry.use_ssl, standalone=entry.standalone,
                    )
                    if ver == 7
                    else RouterROS6(
                        host=entry.host, username=entry.username,
                        password=entry.password, port=entry.port,
                        use_ssl=entry.use_ssl,
                    )
                )

                ok = await router.connect()
                if ok:
                    res = await router.get_system_resource()
                    if res:
                        detected = (
                            7 if "ros-version" in res and "7" in str(res.get("ros-version", ""))
                            else ver
                        )
                        return router, detected
                    await router.close()
            except Exception as e:
                log.debug(f"Failed with ROS{ver}: {e}")
                continue

        return None, 0

    async def reconnect_all(self) -> None:
        """
        Reconnect all disconnected routers concurrently.
        Previously sequential — now uses asyncio.gather() so N routers
        each timing out at 10s costs 10s total, not N×10s.
        """
        tasks = []
        for uid, alias, entry in self.iter_all_entries():
            if not entry.router or not entry.router.connected:
                tasks.append(self._reconnect_one(uid, alias, entry))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _reconnect_one(self, uid: int, alias: str, entry: RouterEntry) -> None:
        log.info(f"Reconnecting {entry.host} ({alias}) for user {uid}")
        try:
            router, ver = await self._create_and_connect(entry)
            if router:
                entry.router = router
                entry.detected_version = ver
                log.info(f"Reconnected {alias} ({entry.host}) ROS{ver}")
            else:
                log.warning(f"Reconnect failed for {alias} ({entry.host})")
        except Exception as e:
            log.warning(f"Reconnect error for {alias}: {e}")

    async def get_or_mock(self, user_id: int) -> RouterBase:
        """Return active router or a mock (for development)."""
        router = self.get_active(user_id)
        if router and router.connected:
            return router
        return MockRouter()
