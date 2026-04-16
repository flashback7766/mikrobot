"""Interface handlers: list, detail, traffic, enable/disable, ethernet stats."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from ui import keyboards as kb
from ui import formatters as fmt

router = Router()


@router.callback_query(F.data == "menu:interfaces")
async def menu_interfaces(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    ifaces = await r.get_interfaces()
    await send_or_edit(cb, fmt.fmt_interfaces(ifaces), kb.interfaces_menu(ifaces))


@router.callback_query(F.data.startswith("iface:detail:"))
async def iface_detail(cb: CallbackQuery):
    name = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    ifaces = await r.get_interfaces()
    iface = next((i for i in ifaces if i.get("name") == name), {})
    if not iface:
        await cb.answer("Interface not found.", show_alert=True)
        return
    running = iface.get("running", "false") == "true"
    disabled = iface.get("disabled", "false") == "true"
    await send_or_edit(cb, fmt.fmt_interface_detail(iface), kb.interface_detail_menu(name, running, disabled))


@router.callback_query(F.data.startswith("iface:traffic:"))
async def iface_traffic(cb: CallbackQuery):
    name = cb.data.split(":")[2]
    if not ctx.rbac.can(cb.from_user.id, "interface.monitor"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await cb.answer("📊 Sampling traffic…")
    t = await r.get_interface_traffic(name)
    text = fmt.fmt_traffic(t)
    ifaces = await r.get_interfaces()
    iface = next((i for i in ifaces if i.get("name") == name), {"disabled": "false", "running": "true"})
    await send_or_edit(cb, text, kb.interface_detail_menu(
        name,
        iface.get("running", "true") == "true",
        iface.get("disabled", "false") == "true",
    ))


@router.callback_query(F.data.startswith("iface:enable:") | F.data.startswith("iface:disable:"))
async def iface_toggle(cb: CallbackQuery):
    parts = cb.data.split(":")
    name = parts[2]
    if not ctx.rbac.can(cb.from_user.id, "interface.toggle"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    if "enable" in cb.data:
        await r.enable_interface(name)
        await cb.answer(f"✅ {name} enabled")
    else:
        await r.disable_interface(name)
        await cb.answer(f"⛔ {name} disabled")
    ifaces = await r.get_interfaces()
    await send_or_edit(cb, fmt.fmt_interfaces(ifaces), kb.interfaces_menu(ifaces))


@router.callback_query(F.data == "iface:eth_stats")
async def iface_eth_stats(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    stats = await r.get_interface_ethernet_stats()
    if not stats:
        await cb.answer("No Ethernet stats available.", show_alert=True)
        return
    lines = ["📊 *Ethernet Statistics*\n"]
    for s in stats[:15]:
        name = s.get("name", "?")
        rx_err = s.get("rx-error", "0")
        tx_err = s.get("tx-error", "0")
        rx_drop = s.get("rx-drop", "0")
        tx_drop = s.get("tx-drop", "0")
        lines.append(f"`{name}` | err RX/TX: {rx_err}/{tx_err} | drop: {rx_drop}/{tx_drop}")
    await send_or_edit(cb, "\n".join(lines), kb.interfaces_menu([]))
