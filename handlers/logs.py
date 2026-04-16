"""Log handlers: view, filter, real-time streaming."""

import asyncio

from aiogram import Router, F
from aiogram.types import CallbackQuery

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from core.log_streamer import stream_logs_to_chat
from ui import keyboards as kb
from ui import formatters as fmt

router = Router()


@router.callback_query(F.data == "menu:logs")
async def menu_logs(cb: CallbackQuery):
    await send_or_edit(cb, "📋 *Log Viewer*", kb.logs_menu())


@router.callback_query(F.data.startswith("log:last"))
async def log_last(cb: CallbackQuery):
    suffix = cb.data.replace("log:last", "")
    limit = int(suffix) if suffix.isdigit() else 20
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    logs = await r.get_logs(limit=limit)
    await send_or_edit(cb, fmt.fmt_logs(logs), kb.logs_menu())


@router.callback_query(F.data.startswith("log:filter:"))
async def log_filter(cb: CallbackQuery):
    topics = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    logs = await r.get_logs(limit=30, topics=topics)
    await send_or_edit(cb, fmt.fmt_logs(logs), kb.logs_menu())


@router.callback_query(F.data.startswith("log:stream"))
async def log_stream(cb: CallbackQuery):
    uid = cb.from_user.id
    if not ctx.rbac.can(uid, "log.stream"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    parts = cb.data.split(":")
    topics = parts[2] if len(parts) > 2 else ""
    await ctx.sessions.stop_log_stream(uid)
    stop_event = asyncio.Event()

    async def _stream():
        await stream_logs_to_chat(r, ctx.bot, uid, topics=topics, stop_event=stop_event)

    task = asyncio.create_task(_stream())
    ctx.sessions.set_log_task(uid, task)
    await cb.answer("📡 Log stream started!")
    await cb.message.answer(
        "📡 *Log stream active.* Use /stop\\_logs to stop.",
        parse_mode="Markdown",
        reply_markup=kb.log_stream_stop(),
    )


@router.callback_query(F.data == "log:stop")
async def log_stop(cb: CallbackQuery):
    await ctx.sessions.stop_log_stream(cb.from_user.id)
    await cb.answer("🔴 Stopped")
    await send_or_edit(cb, "📋 *Log Viewer*", kb.logs_menu())
