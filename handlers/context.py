"""
Shared handler context — injected at startup, imported by all handler modules.

Includes:
  - Dependency injection (rm, rbac, sessions, bot)
  - Auth middleware (auto-bootstrap + reject unknown users)
  - Global error handler (friendly errors instead of crashes)
  - Throttle middleware (anti-flood, 0.5s cooldown per user)
"""

import time
import logging
import traceback
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

from core.router_manager import RouterManager
from core.rbac import RBACManager
from core.session import SessionManager
from core.dhcp_guard import GuardSettingsStore, DhcpAttackDetector

log = logging.getLogger("Handlers")

# ─── Shared State (set once via init()) ───────────────────────────────────────

rm: RouterManager = None
rbac: RBACManager = None
sessions: SessionManager = None
bot = None
# DHCP Guard (optional — None until init() is called with them)
guard_store: GuardSettingsStore = None
guard_detector: DhcpAttackDetector = None
_start_time: float = 0.0


def init(
    router_manager: RouterManager,
    rbac_manager: RBACManager,
    session_manager: SessionManager,
    bot_instance,
    guard_store_: GuardSettingsStore = None,
    guard_detector_: DhcpAttackDetector = None,
):
    """Called once from bot.py at startup to inject dependencies."""
    global rm, rbac, sessions, bot, guard_store, guard_detector, _start_time
    rm = router_manager
    rbac = rbac_manager
    sessions = session_manager
    bot = bot_instance
    guard_store = guard_store_
    guard_detector = guard_detector_
    _start_time = time.time()


def get_uptime() -> str:
    """Return human-readable uptime string."""
    secs = int(time.time() - _start_time)
    days, secs = divmod(secs, 86400)
    hours, secs = divmod(secs, 3600)
    mins, secs = divmod(secs, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


# ─── Permission Check Shortcut ────────────────────────────────────────────────

async def perm(cb: CallbackQuery, permission: str) -> bool:
    """Check if user has permission. Sends alert and returns False if denied."""
    if not rbac.can(cb.from_user.id, permission):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return False
    return True


# ─── Throttle Middleware (anti-flood) ─────────────────────────────────────────

class ThrottleMiddleware(BaseMiddleware):
    """
    Prevents spam-clicking buttons. Users get a 0.5s cooldown between callbacks.
    Silently drops events during cooldown (no error shown).
    """

    def __init__(self, cooldown: float = 0.5):
        self._cooldown = cooldown
        self._last_action: dict[int, float] = {}

    async def __call__(self, handler, event, data: dict):
        uid = event.from_user.id
        now = time.time()
        last = self._last_action.get(uid, 0)
        if now - last < self._cooldown:
            if isinstance(event, CallbackQuery):
                await event.answer()  # Acknowledge silently
            return  # Drop the event
        self._last_action[uid] = now
        return await handler(event, data)


# ─── Global Error Handler ─────────────────────────────────────────────────────

class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Wraps ALL handlers in try/except. Instead of crashing silently,
    shows a user-friendly error message and logs the full traceback.
    """

    _ERROR_MESSAGES = {
        "ConnectionResetError": "🔌 Router connection lost. Try again or reconnect.",
        "TimeoutError": "⏱ Router is not responding. Check if it's online.",
        "asyncio.TimeoutError": "⏱ Operation timed out. Router may be overloaded.",
        "OSError": "🔌 Cannot reach the router. Check network connectivity.",
        "ConnectionRefusedError": "🔌 Router API refused connection. Is API enabled?",
    }

    async def __call__(self, handler, event, data: dict):
        try:
            return await handler(event, data)
        except TelegramBadRequest:
            # Message not modified, etc — not a real error
            pass
        except Exception as e:
            error_type = type(e).__name__
            friendly = self._ERROR_MESSAGES.get(
                error_type,
                f"❌ Unexpected error: `{error_type}`\n`{str(e)[:200]}`"
            )
            log.error(f"Handler error [{error_type}]: {e}\n{traceback.format_exc()}")
            try:
                if isinstance(event, CallbackQuery):
                    await event.answer(f"⚠️ {friendly[:180]}", show_alert=True)
                elif isinstance(event, Message):
                    await event.answer(f"⚠️ {friendly}", parse_mode="Markdown")
            except Exception:
                pass  # Can't even send the error — give up gracefully


# ─── Auth Middleware ──────────────────────────────────────────────────────────

class CallbackAuthMiddleware(BaseMiddleware):
    """
    Runs before every callback handler.
    Handles: bootstrap (first user → owner), unknown user rejection.
    Individual permission checks remain in handlers.
    """

    async def __call__(self, handler, event: CallbackQuery, data: dict):
        uid = event.from_user.id

        if not rbac.is_bootstrapped():
            await rbac.bootstrap_owner(uid)
            await event.answer("👑 You are now the owner of this bot!", show_alert=True)
            return await handler(event, data)

        if not rbac.is_known(uid):
            await event.answer(
                "🚫 You are not authorized. Contact the bot owner.",
                show_alert=True,
            )
            return

        return await handler(event, data)


class MessageAuthMiddleware(BaseMiddleware):
    """Same as above but for message handlers (commands, FSM text)."""

    async def __call__(self, handler, event: Message, data: dict):
        uid = event.from_user.id

        if not rbac.is_bootstrapped():
            await rbac.bootstrap_owner(uid)
            await event.answer("👑 You are now the owner of this bot!")
            return await handler(event, data)

        if not rbac.is_known(uid):
            await event.answer("🚫 You are not authorized. Contact the bot owner.")
            return

        return await handler(event, data)
