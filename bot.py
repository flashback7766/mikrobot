"""
MikroBot – WinBox-level MikroTik management in Telegram.

Supports:
  RouterOS 6 (NSA only)
  RouterOS 7 (NSA + SA/standalone Docker)

Entry point. Run with: python bot.py
"""

import asyncio
import logging
import signal
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, LOG_LEVEL, OWNER_ID
from core import crypto
from core.router_manager import RouterManager
from core.rbac import RBACManager
from core.session import SessionManager
from core.monitor import Monitor
from core.watchdog import Watchdog
from core.healthcheck import HealthServer
from core.dhcp_guard import GuardSettingsStore, DhcpAttackDetector
import handlers

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("MikroBot")

# ─── Ensure data directory ────────────────────────────────────────────────────

Path("data").mkdir(exist_ok=True)

# ─── Crypto (must init before RouterManager loads passwords) ──────────────────

crypto.init(BOT_TOKEN)

# ─── Core Components ─────────────────────────────────────────────────────────

rm = RouterManager()
rbac = RBACManager()
sessions = SessionManager()
# DHCP Guard — detector (in-memory) + settings store (JSON persisted)
guard_store = GuardSettingsStore()
guard_detector = DhcpAttackDetector()


# ─── Startup / Shutdown Notifications ─────────────────────────────────────────

async def _notify_owner(bot: Bot, text: str):
    """Send a notification to the bot owner (if configured)."""
    if not OWNER_ID:
        return
    try:
        await bot.send_message(OWNER_ID, text, parse_mode="Markdown")
    except Exception as e:
        log.warning(f"Could not notify owner: {e}")


async def main():
    log.info("Starting MikroBot…")

    # Bootstrap owner from config if set and not yet registered
    if OWNER_ID and not rbac.is_bootstrapped():
        await rbac.bootstrap_owner(OWNER_ID)
        log.info(f"Owner bootstrapped: {OWNER_ID}")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    # Inject dependencies and wire all handler sub-routers
    handlers.setup(rm, rbac, sessions, bot, guard_store, guard_detector)

    dp = Dispatcher()
    dp.include_router(handlers.parent_router)

    # Start background services
    monitor = Monitor(rm, bot, OWNER_ID or 0, guard_store, guard_detector)
    rm._monitor = monitor  # Wire cleanup hook
    watchdog = Watchdog(rm)
    await monitor.start()
    await watchdog.start()

    # Start HTTP healthcheck server (port 8080)
    health = HealthServer(rm, sessions, port=8080)
    await health.start()

    # Start session auto-cleanup (expires stale FSM states)
    await sessions.start_cleanup_loop()

    # Notify owner that bot is online
    now = datetime.now().strftime("%H:%M:%S %d.%m.%Y")
    await _notify_owner(bot, f"🟢 *MikroBot Online*\n`{now}`")

    log.info("Bot is running. Press Ctrl+C to stop.")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        log.info("Shutting down…")
        await _notify_owner(bot, "🔴 *MikroBot shutting down…*")
        await sessions.stop_cleanup_loop()
        await monitor.stop()
        await watchdog.stop()
        await health.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
