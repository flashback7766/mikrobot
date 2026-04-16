"""
HTTP Healthcheck server for MikroBot.

Exposes a lightweight HTTP endpoint for Docker/Kubernetes health probes:

  GET /health  → 200 {"status":"ok", "uptime":..., "routers":..., "sessions":...}
  GET /metrics → 200 Prometheus-compatible plain text metrics
  GET /ping    → 200 "pong"

Usage in bot.py:
    from core.healthcheck import HealthServer
    health = HealthServer(rm, sessions, port=8080)
    await health.start()
    ...
    await health.stop()

Docker healthcheck:
    HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://localhost:8080/ping || exit 1
"""

import asyncio
import json
import logging
import time
from aiohttp import web

log = logging.getLogger("HealthServer")

_start_time = time.time()


class HealthServer:
    """
    Minimal async HTTP server for health probes and metrics.

    Args:
        rm: RouterManager instance (to count routers / connected status).
        sessions: SessionManager instance (to count active sessions).
        port: TCP port to bind (default 8080). Set to 0 to disable.
    """

    def __init__(self, rm, sessions, port: int = 8080):
        self._rm = rm
        self._sessions = sessions
        self._port = port
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

        self._app = web.Application()
        self._app.router.add_get("/ping",    self._handle_ping)
        self._app.router.add_get("/health",  self._handle_health)
        self._app.router.add_get("/metrics", self._handle_metrics)

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _handle_ping(self, request: web.Request) -> web.Response:
        """Simple liveness probe."""
        return web.Response(text="pong", content_type="text/plain")

    async def _handle_health(self, request: web.Request) -> web.Response:
        """
        Readiness probe with JSON payload.

        Response fields:
            status      "ok" | "degraded"
            uptime_s    Bot process uptime in seconds
            routers     Total number of configured routers (all users)
            connected   Number of routers currently connected
            sessions    Number of active user sessions
            timestamp   ISO-8601 UTC timestamp
        """
        total_routers = 0
        connected_routers = 0
        for uid, alias, entry in self._rm.iter_all_entries():
            total_routers += 1
            if entry.router and entry.router.connected:
                connected_routers += 1

        active_sessions = self._sessions.active_count() if hasattr(self._sessions, "active_count") else 0

        uptime = int(time.time() - _start_time)
        status = "ok" if connected_routers >= 0 else "degraded"

        payload = {
            "status": status,
            "uptime_s": uptime,
            "routers": total_routers,
            "connected": connected_routers,
            "sessions": active_sessions,
            "timestamp": _iso_now(),
        }
        return web.Response(
            text=json.dumps(payload, indent=2),
            content_type="application/json",
            status=200 if status == "ok" else 503,
        )

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """
        Prometheus-compatible plain text metrics.

        Metrics exposed:
            mikrobot_uptime_seconds     Bot process uptime
            mikrobot_routers_total      Configured routers count
            mikrobot_routers_connected  Connected routers count
            mikrobot_sessions_active    Active user sessions count
        """
        total = 0
        connected = 0
        for uid, alias, entry in self._rm.iter_all_entries():
            total += 1
            if entry.router and entry.router.connected:
                connected += 1

        active_sessions = self._sessions.active_count() if hasattr(self._sessions, "active_count") else 0
        uptime = int(time.time() - _start_time)

        lines = [
            "# HELP mikrobot_uptime_seconds Bot process uptime in seconds",
            "# TYPE mikrobot_uptime_seconds gauge",
            f"mikrobot_uptime_seconds {uptime}",
            "",
            "# HELP mikrobot_routers_total Total configured routers",
            "# TYPE mikrobot_routers_total gauge",
            f"mikrobot_routers_total {total}",
            "",
            "# HELP mikrobot_routers_connected Currently connected routers",
            "# TYPE mikrobot_routers_connected gauge",
            f"mikrobot_routers_connected {connected}",
            "",
            "# HELP mikrobot_sessions_active Active user sessions",
            "# TYPE mikrobot_sessions_active gauge",
            f"mikrobot_sessions_active {active_sessions}",
        ]
        return web.Response(text="\n".join(lines), content_type="text/plain")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the HTTP server in the background."""
        if self._port == 0:
            log.info("HealthServer disabled (port=0)")
            return
        self._runner = web.AppRunner(self._app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await self._site.start()
        log.info(f"HealthServer listening on :{self._port} → /ping /health /metrics")

    async def stop(self) -> None:
        """Gracefully shut down the HTTP server."""
        if self._runner:
            await self._runner.cleanup()
            log.info("HealthServer stopped")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
