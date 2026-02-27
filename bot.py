"""
MikroBot – WinBox-level MikroTik management in Telegram.

Supports:
  RouterOS 6 (NSA only)
  RouterOS 7 (NSA + SA/standalone Docker)

Entry point. Run with: python bot.py
"""

import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, LOG_LEVEL, OWNER_ID
from core.router_manager import RouterManager
from core.rbac import RBACManager, Role
from core.session import SessionManager
from core.monitor import Monitor
from core.watchdog import Watchdog
import handlers.callbacks as cb_handlers
from handlers.callbacks import router as main_router

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("MikroBot")

# ─── Ensure data directory ────────────────────────────────────────────────────

Path("data").mkdir(exist_ok=True)

# ─── Core Components ─────────────────────────────────────────────────────────

rm = RouterManager()
rbac = RBACManager()
sessions = SessionManager()


async def main():
    log.info("Starting MikroBot…")

    # Bootstrap owner from config if set and not yet registered
    if OWNER_ID and not rbac.is_bootstrapped():
        rbac.bootstrap_owner(OWNER_ID)
        log.info(f"Owner bootstrapped: {OWNER_ID}")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    # Inject dependencies into handler module
    cb_handlers.setup(rm, rbac, sessions, bot)

    dp = Dispatcher()
    dp.include_router(main_router)

    # Start background services
    monitor = Monitor(rm, bot, OWNER_ID or 0)
    watchdog = Watchdog(rm)
    await monitor.start()
    await watchdog.start()

    log.info("Bot is running. Press Ctrl+C to stop.")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await monitor.stop()
        await watchdog.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
