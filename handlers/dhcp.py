"""DHCP handlers: leases, servers, static lease management."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from ui import keyboards as kb
from ui import formatters as fmt

router = Router()


@router.callback_query(F.data == "menu:dhcp")
async def menu_dhcp(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "dhcp.view"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    await send_or_edit(cb, "📡 *DHCP Manager*", kb.dhcp_menu())


@router.callback_query(F.data == "dhcp:leases")
async def dhcp_leases(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    leases = await r.get_dhcp_leases()
    page = ctx.sessions.get_page(cb.from_user.id)
    await send_or_edit(cb, fmt.fmt_dhcp_leases(leases, page), kb.dhcp_lease_list(leases, page))


@router.callback_query(F.data.startswith("dhcp:page:"))
async def dhcp_page(cb: CallbackQuery):
    page = int(cb.data.split(":")[2])
    ctx.sessions.set_page(cb.from_user.id, page)
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    leases = await r.get_dhcp_leases()
    await send_or_edit(cb, fmt.fmt_dhcp_leases(leases, page), kb.dhcp_lease_list(leases, page))


@router.callback_query(F.data.startswith("dhcp:lease:"))
async def dhcp_lease_detail(cb: CallbackQuery):
    lease_id = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    leases = await r.get_dhcp_leases()
    lease = next((l for l in leases if l.get(".id") == lease_id), None)
    if not lease:
        await cb.answer("Lease not found.", show_alert=True)
        return
    is_dynamic = lease.get("type", "dynamic") == "dynamic"
    await send_or_edit(cb, fmt.fmt_dhcp_lease_detail(lease), kb.dhcp_lease_detail(lease_id, is_dynamic))


@router.callback_query(F.data.startswith("dhcp:make_static:"))
async def dhcp_make_static(cb: CallbackQuery):
    lease_id = cb.data.split(":")[2]
    if not ctx.rbac.can(cb.from_user.id, "dhcp.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.make_dhcp_lease_static(lease_id)
    await cb.answer("📌 Lease made static!")
    leases = await r.get_dhcp_leases()
    await send_or_edit(cb, fmt.fmt_dhcp_leases(leases), kb.dhcp_lease_list(leases))


@router.callback_query(F.data.startswith("dhcp:remove:"))
async def dhcp_remove(cb: CallbackQuery):
    lease_id = cb.data.split(":")[2]
    if not ctx.rbac.can(cb.from_user.id, "dhcp.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_dhcp_lease(lease_id)
    await cb.answer("🗑 Lease removed!")
    leases = await r.get_dhcp_leases()
    await send_or_edit(cb, fmt.fmt_dhcp_leases(leases), kb.dhcp_lease_list(leases))


@router.callback_query(F.data == "dhcp:add_static")
async def dhcp_add_static(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "dhcp.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    ctx.sessions.set_state(cb.from_user.id, "dhcp:add:mac")
    await send_or_edit(
        cb,
        "📌 *Add Static DHCP Lease*\n\nEnter MAC address:\nExample: `AA:BB:CC:DD:EE:FF`",
        kb.cancel_keyboard("menu:dhcp"),
    )


@router.callback_query(F.data == "dhcp:servers")
async def dhcp_servers(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    servers = await r.get_dhcp_server()
    lines = [f"🖥 *DHCP Servers* ({len(servers)})\n"]
    for s in servers:
        name = s.get("name", "?")
        iface = s.get("interface", "?")
        pool = s.get("address-pool", "?")
        lease_time = s.get("lease-time", "?")
        disabled = s.get("disabled", "false") == "true"
        icon = "✅" if not disabled else "❌"
        lines.append(f"{icon} `{name}` on `{iface}`\nPool: {pool} | Lease: {lease_time}")
    await send_or_edit(cb, "\n\n".join(lines), kb.dhcp_menu())
