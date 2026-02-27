"""
Background monitor – polls all connected routers every N seconds,
detects threshold breaches, and pushes Telegram alerts.

CHANGES vs original:
  - _poll_all() now uses asyncio.gather() — all routers polled concurrently
  - _poll_router() gathers its 3 independent API calls concurrently
  - AlertState is now keyed by (user_id, alias) not just user_id — fixes
    bug where 2 routers shared one alert state per user
  - Monitor no longer accesses rm._entries directly — uses rm.iter_all_entries()
  - last_status cleaned up via on_router_removed() hook
  - asyncio.get_event_loop() replaced with asyncio.get_running_loop()
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot

from .router_manager import RouterManager

log = logging.getLogger("Monitor")

# Alert thresholds
CPU_THRESHOLD = 90
MEMORY_THRESHOLD = 90
INTERFACE_DOWN_ALERT = True
POLL_INTERVAL = 30  # seconds


class AlertState:
    """Per-router alert state — prevents duplicate alerts."""
    def __init__(self):
        self.cpu_alerted: bool = False
        self.mem_alerted: bool = False
        self.interface_down: set[str] = set()
        self.last_seen_macs: set[str] = set()


class Monitor:

    def __init__(self, router_manager: RouterManager, bot: Bot, owner_id: int):
        self.rm = router_manager
        self.bot = bot
        self.owner_id = owner_id
        # Key: (user_id, alias) — one AlertState per router, not per user
        self._alert_states: dict[tuple[int, str], AlertState] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        # Cached status: user_id -> {alias -> stats dict}
        self.last_status: dict[int, dict] = {}

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("Monitor started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def on_router_removed(self, user_id: int, alias: str) -> None:
        """Call this when a router is removed to clean up stale cache."""
        self._alert_states.pop((user_id, alias), None)
        if user_id in self.last_status:
            self.last_status[user_id].pop(alias, None)
            if not self.last_status[user_id]:
                del self.last_status[user_id]

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._poll_all()
            except Exception as e:
                log.warning(f"Monitor poll error: {e}")
            await asyncio.sleep(POLL_INTERVAL)

    async def _poll_all(self) -> None:
        """Poll all connected routers concurrently."""
        tasks = [
            self._poll_router(uid, alias, entry.router, entry.host)
            for uid, alias, entry in self.rm.iter_all_entries()
            if entry.router and entry.router.connected
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _poll_router(self, user_id: int, alias: str, router, host: str) -> None:
        # Keyed by (user_id, alias) — one state per router, not per user
        state = self._alert_states.setdefault((user_id, alias), AlertState())

        try:
            # Gather the 3 independent API calls concurrently
            res, ifaces, leases = await asyncio.gather(
                router.get_system_resource(),
                router.get_interfaces() if INTERFACE_DOWN_ALERT else _empty(),
                router.get_dhcp_leases(),
                return_exceptions=True,
            )
        except Exception as e:
            log.debug(f"Poll gather error for {alias}: {e}")
            return

        # ── Resource metrics ────────────────────────────────────────────────
        if isinstance(res, Exception) or not res:
            return

        cpu = int(res.get("cpu-load", 0))
        total_mem = int(res.get("total-memory", 1))
        free_mem = int(res.get("free-memory", 0))
        mem_pct = int((1 - free_mem / total_mem) * 100) if total_mem else 0

        self.last_status.setdefault(user_id, {})[alias] = {
            "cpu": cpu,
            "mem_pct": mem_pct,
            "uptime": res.get("uptime", "?"),
            "polled_at": datetime.now().isoformat(),
        }

        # CPU alert (with 10% hysteresis to prevent flapping)
        if cpu >= CPU_THRESHOLD and not state.cpu_alerted:
            state.cpu_alerted = True
            await self._send_alert(user_id, f"🔥 *{alias}* ({host})\n⚠️ HIGH CPU: {cpu}%")
        elif cpu < CPU_THRESHOLD - 10:
            state.cpu_alerted = False

        # Memory alert
        if mem_pct >= MEMORY_THRESHOLD and not state.mem_alerted:
            state.mem_alerted = True
            await self._send_alert(user_id, f"💾 *{alias}* ({host})\n⚠️ HIGH MEMORY: {mem_pct}%")
        elif mem_pct < MEMORY_THRESHOLD - 10:
            state.mem_alerted = False

        # ── Interface down alerts ───────────────────────────────────────────
        if INTERFACE_DOWN_ALERT and isinstance(ifaces, list):
            for iface in ifaces:
                name = iface.get("name", "")
                running = iface.get("running", "true") == "true"
                disabled = iface.get("disabled", "false") == "true"
                key = f"{alias}:{name}"
                if not running and not disabled:
                    if key not in state.interface_down:
                        state.interface_down.add(key)
                        await self._send_alert(
                            user_id,
                            f"📵 *{alias}* ({host})\n🔴 Interface `{name}` is DOWN"
                        )
                else:
                    if key in state.interface_down:
                        state.interface_down.discard(key)
                        await self._send_alert(
                            user_id,
                            f"✅ *{alias}* ({host})\n🟢 Interface `{name}` is UP"
                        )

        # ── New DHCP client detection ───────────────────────────────────────
        if isinstance(leases, list):
            try:
                macs = {l.get("mac-address", "") for l in leases}
                new_macs = macs - state.last_seen_macs
                for mac in new_macs:
                    lease = next((l for l in leases if l.get("mac-address") == mac), {})
                    ip = lease.get("address", "?")
                    host_name = lease.get("host-name", "unknown")
                    await self._send_alert(
                        user_id,
                        f"🔍 *{alias}*\nNew device on network:\n"
                        f"🖥 `{host_name}` — `{ip}` — `{mac}`"
                    )
                state.last_seen_macs = macs
            except Exception:
                pass

    async def _send_alert(self, user_id: int, text: str) -> None:
        try:
            await self.bot.send_message(user_id, text, parse_mode="Markdown")
        except Exception as e:
            log.warning(f"Failed to send alert to {user_id}: {e}")


async def _empty() -> list:
    """Placeholder coroutine for disabled gather slots."""
    return []
