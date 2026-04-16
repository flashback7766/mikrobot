"""Tools handlers: ping, traceroute, bandwidth test, scripts view."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from ui import keyboards as kb

router = Router()


@router.callback_query(F.data == "menu:tools")
async def menu_tools(cb: CallbackQuery):
    await send_or_edit(cb, "🔧 *Network Tools*", kb.tools_menu())


@router.callback_query(F.data == "tool:ping")
async def tool_ping(cb: CallbackQuery):
    ctx.sessions.set_state(cb.from_user.id, "tool:ping")
    await send_or_edit(cb, "🏓 Enter hostname or IP to ping:", kb.cancel_keyboard("menu:tools"))


@router.callback_query(F.data == "tool:traceroute")
async def tool_traceroute(cb: CallbackQuery):
    ctx.sessions.set_state(cb.from_user.id, "tool:traceroute")
    await send_or_edit(cb, "🗺 Enter hostname or IP for traceroute:", kb.cancel_keyboard("menu:tools"))


@router.callback_query(F.data == "tool:bwtest")
async def tool_bwtest(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "tool.bandwidth_test"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    ctx.sessions.set_state(cb.from_user.id, "tool:bwtest")
    await send_or_edit(
        cb,
        "📊 Enter target IP for bandwidth test\n(requires Bandwidth Test tool on target):",
        kb.cancel_keyboard("menu:tools"),
    )


@router.callback_query(F.data == "tool:scripts")
async def tool_scripts(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    scripts = await r.get_scripts()
    if not scripts:
        await cb.answer("No scripts found.", show_alert=True)
        return
    lines = [f"📜 *Scripts* ({len(scripts)})\n"]
    for s in scripts:
        name = s.get("name", "?")
        last_run = s.get("last-started", "")
        lines.append(f"• `{name}`" + (f" — last: {last_run}" if last_run else ""))
    await send_or_edit(cb, "\n".join(lines), kb.tools_menu())
