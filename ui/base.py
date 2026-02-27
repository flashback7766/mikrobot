"""
Base handler utilities – shared auth checks, router getter, answer helpers.
"""

import logging
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from core.rbac import RBACManager, Role
from core.session import SessionManager
from core.router_manager import RouterManager

log = logging.getLogger("Handlers")


async def send_or_edit(
    source: Message | CallbackQuery,
    text: str,
    keyboard=None,
    parse_mode: str = "Markdown",
):
    """Send or edit a message – smart dispatch."""
    kwargs = {"parse_mode": parse_mode}
    if keyboard:
        kwargs["reply_markup"] = keyboard
    if len(text) > 4096:
        text = text[:4090] + "\n…"

    if isinstance(source, CallbackQuery):
        try:
            await source.message.edit_text(text, **kwargs)
        except TelegramBadRequest:
            await source.message.answer(text, **kwargs)
        await source.answer()
    else:
        await source.answer(text, **kwargs)


async def check_auth(
    source: Message | CallbackQuery,
    rbac: RBACManager,
    permission: str | None = None,
) -> bool:
    """
    Check if user is authorized.
    Returns True if ok, False if denied (and sends an error message).
    """
    uid = source.from_user.id

    if not rbac.is_bootstrapped():
        # Bootstrap mode – first user becomes owner
        await rbac.bootstrap_owner(uid)
        msg = "👑 You are now the owner of this bot!"
        if isinstance(source, CallbackQuery):
            await source.answer(msg, show_alert=True)
        else:
            await source.answer(msg)
        return True

    if not rbac.is_known(uid):
        msg = "🚫 You are not authorized. Contact the bot owner to get access."
        if isinstance(source, CallbackQuery):
            await source.answer(msg, show_alert=True)
        else:
            await source.answer(msg)
        return False

    if permission:
        try:
            rbac.require(uid, permission)
        except PermissionError as e:
            if isinstance(source, CallbackQuery):
                await source.answer(str(e), show_alert=True)
            else:
                await source.answer(str(e), parse_mode="Markdown")
            return False

    return True


def get_router(user_id: int, rm: RouterManager):
    """Get active router, returns None if not connected."""
    return rm.get_active(user_id)


async def require_router(
    source: Message | CallbackQuery,
    rm: RouterManager,
):
    """Get active router or send a helpful error."""
    uid = source.from_user.id
    router = rm.get_active(uid)
    if router is None:
        msg = (
            "❌ No router connected.\n"
            "Use /add\\_router to connect your first MikroTik device."
        )
        await send_or_edit(source, msg)
        return None
    return router
