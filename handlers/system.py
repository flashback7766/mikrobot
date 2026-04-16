"""System handlers: system info, health, routerboard, reboot, scheduler, users, NTP, certs."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from core.router_ros7 import RouterROS7
from ui import keyboards as kb
from ui import formatters as fmt

router = Router()


@router.callback_query(F.data.in_({"menu:system", "sys:refresh"}))
async def menu_system(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    res = await r.get_system_resource()
    identity = await r.get_system_identity()
    health = await r.get_system_health()
    await send_or_edit(cb, fmt.fmt_system(res, identity, health), kb.system_menu())


@router.callback_query(F.data == "sys:health")
async def sys_health(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    health = await r.get_system_health()
    if not health:
        await cb.answer("No health data available on this device.", show_alert=True)
        return
    lines = ["🌡 *System Health*\n"]
    for k, v in health.items():
        lines.append(f"• {k}: `{v}`")
    await send_or_edit(cb, "\n".join(lines), kb.system_menu())


@router.callback_query(F.data == "sys:routerboard")
async def sys_routerboard(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    rb = await r.get_system_routerboard()
    await send_or_edit(cb, fmt.fmt_routerboard(rb), kb.system_menu())


@router.callback_query(F.data == "sys:reboot")
async def sys_reboot(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "system.reboot"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    await send_or_edit(cb, "⚠️ *Confirm Reboot?*\nThis will disconnect all clients!", kb.reboot_confirm())


@router.callback_query(F.data == "sys:reboot_confirm")
async def sys_reboot_confirm(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "system.reboot"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await cb.answer("🔁 Rebooting…")
    await r.reboot()
    await cb.message.edit_text(
        "🔁 *Reboot command sent.*\nRouter will be back in ~30 seconds.",
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "sys:users")
async def sys_users(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "user.view"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    users = await r.get_users()
    await send_or_edit(cb, fmt.fmt_router_users(users), kb.system_menu())


@router.callback_query(F.data == "sys:scheduler")
async def sys_scheduler(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    entries = await r.get_scheduler_entries()
    if not entries:
        await cb.answer("No scheduled tasks.", show_alert=True)
        return
    lines = ["📅 *Scheduler*\n"]
    for e in entries:
        name = e.get("name", "?")
        interval = e.get("interval", e.get("on-event", "?"))
        disabled = e.get("disabled", "false") == "true"
        icon = "⏸" if disabled else "▶️"
        lines.append(f"{icon} `{name}` — {interval}")
    await send_or_edit(cb, "\n".join(lines), kb.system_menu())


@router.callback_query(F.data == "sys:add_user")
async def sys_add_user(cb: CallbackQuery):
    if not await ctx.perm(cb, "user.add"):
        return
    ctx.sessions.set_state(cb.from_user.id, "sys:add_user:name")
    await send_or_edit(cb, "👤 *Add Router User*\n\nEnter username:", kb.cancel_keyboard("sys:users_detail"))


@router.callback_query(F.data.startswith("sys:remove_user:"))
async def sys_remove_user(cb: CallbackQuery):
    parts = cb.data.split(":")
    id_ = parts[2]
    if not await ctx.perm(cb, "user.remove"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_user(id_)
    await cb.answer("🗑 User removed")
    users = await r.get_users()
    await send_or_edit(cb, fmt.fmt_router_users(users), kb.system_menu())


# ── NTP ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.in_({"sys:ntp", "ntp:view"}))
async def sys_ntp(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    ntp = await r.get_ntp_client()
    await send_or_edit(cb, fmt.fmt_ntp(ntp), kb.ntp_menu())


@router.callback_query(F.data == "ntp:set_prompt")
async def ntp_set_prompt(cb: CallbackQuery):
    if not await ctx.perm(cb, "system.export"):
        return
    ctx.sessions.set_state(cb.from_user.id, "ntp:set_servers")
    await send_or_edit(
        cb,
        "🕐 *Set NTP Servers*\n\nEnter servers (space/comma separated):\nExample: `pool.ntp.org 1.1.1.1`",
        kb.cancel_keyboard("sys:ntp"),
    )


# ── Certificates ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "sys:certs")
async def sys_certs(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    certs = await r.get_certificates()
    await send_or_edit(cb, fmt.fmt_certificates(certs), kb.certs_menu(certs))


@router.callback_query(F.data.startswith("cert:detail:"))
async def cert_detail(cb: CallbackQuery):
    parts = cb.data.split(":")
    name = ":".join(parts[2:])
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    certs = await r.get_certificates()
    c = next((x for x in certs if x.get("name") == name), {})
    if not c:
        await cb.answer("Certificate not found.", show_alert=True)
        return
    lines = [f"🔐 *Certificate: {name}*"]
    for k, v in c.items():
        if not k.startswith("."):
            lines.append(f"`{k}`: {v}")
    await send_or_edit(cb, "\n".join(lines), kb.certs_menu([]))
