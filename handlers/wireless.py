"""Wireless handlers: interfaces, clients, SSID/password, scan."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from ui import keyboards as kb
from ui import formatters as fmt

router = Router()


@router.callback_query(F.data == "menu:wireless")
async def menu_wireless(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "wireless.view"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    ifaces = await r.get_wireless_interfaces()
    if not ifaces:
        await cb.answer("No wireless interfaces found.", show_alert=True)
        return
    await send_or_edit(cb, "📶 *Wireless Manager*", kb.wireless_menu(ifaces))


@router.callback_query(F.data.startswith("wifi:iface:"))
async def wifi_iface(cb: CallbackQuery):
    name = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    ifaces = await r.get_wireless_interfaces()
    iface = next((i for i in ifaces if i.get("name") == name), {})
    if not iface:
        await cb.answer("Interface not found.", show_alert=True)
        return
    ssid = iface.get("ssid", "?")
    freq = iface.get("frequency", "?")
    band = iface.get("band", "?")
    disabled = iface.get("disabled", "false") == "true"
    text = (
        f"📶 *Interface: {name}*\n"
        f"SSID: `{ssid}`\n"
        f"Frequency: `{freq} MHz`\n"
        f"Band: `{band}`\n"
        f"Status: {'⛔ Disabled' if disabled else '✅ Active'}"
    )
    await send_or_edit(cb, text, kb.wireless_iface_menu(name, disabled))


@router.callback_query(F.data == "wifi:clients")
async def wifi_clients(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    clients = await r.get_wireless_registrations()
    await send_or_edit(cb, fmt.fmt_wireless_clients(clients), kb.wireless_clients_menu(clients))


@router.callback_query(F.data.startswith("wifi:client:"))
async def wifi_client_detail(cb: CallbackQuery):
    parts = cb.data.split(":")
    mac = ":".join(parts[2:])
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    clients = await r.get_wireless_registrations()
    client = next((c for c in clients if c.get("mac-address") == mac), {})
    if not client:
        await cb.answer("Client not found.", show_alert=True)
        return
    text = (
        f"📱 *WiFi Client*\n"
        f"MAC: `{mac}`\n"
        f"Interface: `{client.get('interface', '?')}`\n"
        f"Signal: `{client.get('signal-strength', '?')}`\n"
        f"TX Rate: `{client.get('tx-rate', '?')}`\n"
        f"RX Rate: `{client.get('rx-rate', '?')}`\n"
        f"Uptime: `{client.get('uptime', '?')}`"
    )
    await send_or_edit(cb, text, kb.wireless_client_detail(mac))


@router.callback_query(F.data.startswith("wifi:disconnect:"))
async def wifi_disconnect(cb: CallbackQuery):
    mac = ":".join(cb.data.split(":")[2:])
    if not ctx.rbac.can(cb.from_user.id, "wireless.disconnect_client"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.disconnect_wireless_client(mac)
    await cb.answer(f"🚫 {mac} disconnected")
    await send_or_edit(cb, "📶 *Wireless Manager*", kb.wireless_menu(await r.get_wireless_interfaces()))


@router.callback_query(F.data.startswith("wifi:enable:") | F.data.startswith("wifi:disable:"))
async def wifi_toggle(cb: CallbackQuery):
    name = cb.data.split(":")[2]
    if not ctx.rbac.can(cb.from_user.id, "wireless.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    if "enable" in cb.data:
        await r.enable_wireless(name)
        await cb.answer(f"✅ {name} enabled")
    else:
        await r.disable_wireless(name)
        await cb.answer(f"⛔ {name} disabled")
    ifaces = await r.get_wireless_interfaces()
    await send_or_edit(cb, "📶 *Wireless Manager*", kb.wireless_menu(ifaces))


@router.callback_query(F.data.startswith("wifi:set_ssid:"))
async def wifi_set_ssid(cb: CallbackQuery):
    name = cb.data.split(":")[2]
    if not ctx.rbac.can(cb.from_user.id, "wireless.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    ctx.sessions.set_state(cb.from_user.id, f"wifi:set_ssid:{name}")
    await send_or_edit(cb, f"✏️ Enter new SSID for `{name}`:", kb.cancel_keyboard("menu:wireless"))


@router.callback_query(F.data.startswith("wifi:set_pass:"))
async def wifi_set_pass(cb: CallbackQuery):
    name = cb.data.split(":")[2]
    if not ctx.rbac.can(cb.from_user.id, "wireless.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    ctx.sessions.set_state(cb.from_user.id, f"wifi:set_pass:{name}")
    await send_or_edit(cb, f"🔑 Enter new WiFi password for `{name}` (min 8 chars):", kb.cancel_keyboard("menu:wireless"))


@router.callback_query(F.data.startswith("wifi:scan:"))
async def wifi_scan(cb: CallbackQuery):
    name = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await cb.answer("📡 Scanning…")
    results = await r.get_wireless_scan(name)
    await send_or_edit(cb, fmt.fmt_wireless_scan(results), kb.wireless_iface_menu(name, False))
