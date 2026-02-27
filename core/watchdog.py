"""
Watchdog – periodically checks all router connections and reconnects if needed.

CHANGES vs original:
  - Watchdog now waits BEFORE the first reconnect attempt (not on startup)
  - Proper task cancellation with await on stop()
  - Reconnect is already concurrent inside RouterManager.reconnect_all()
"""

import asyncio
import logging

from .router_manager import RouterManager

log = logging.getLogger("Watchdog")


class Watchdog:

    def __init__(self, manager: RouterManager, interval: int = 30):
        self.manager = manager
        self.interval = interval
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("Watchdog started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.interval)
            try:
                await self.manager.reconnect_all()
            except Exception as e:
                log.warning(f"Watchdog error: {e}")
