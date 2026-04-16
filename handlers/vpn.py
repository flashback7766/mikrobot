"""VPN handlers: PPPoE, L2TP, OpenVPN, PPP secrets/profiles, WireGuard."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from core.router_ros7 import RouterROS7
from ui import keyboards as kb
from ui import formatters as fmt

router = Router()


@router.callback_query(F.data == "menu:vpn")
async def menu_vpn(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "vpn.view"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    await send_or_edit(cb, "🔒 *VPN Manager*", kb.vpn_menu())


@router.callback_query(F.data == "vpn:pppoe")
async def vpn_pppoe(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    active = await r.get_pppoe_active()
    if not active:
        await send_or_edit(cb, "📋 No active PPPoE sessions.", kb.vpn_menu())
        return
    lines = [f"📋 *PPPoE Active Sessions* ({len(active)})\n"]
    for s in active:
        lines.append(f"• `{s.get('name', '?')}` — `{s.get('address', '?')}` [{s.get('uptime', '?')}]")
    await send_or_edit(cb, "\n".join(lines), kb.vpn_menu())


@router.callback_query(F.data == "vpn:secrets")
async def vpn_secrets(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    secrets = await r.get_vpn_secrets()
    page = ctx.sessions.get_page(cb.from_user.id)
    await send_or_edit(cb, f"👤 *PPP Secrets* ({len(secrets)} total)", kb.vpn_secrets_list(secrets, page))


@router.callback_query(F.data.startswith("vpn:secrets:page:"))
async def vpn_secrets_page(cb: CallbackQuery):
    page = int(cb.data.split(":")[3])
    ctx.sessions.set_page(cb.from_user.id, page)
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    secrets = await r.get_vpn_secrets()
    await send_or_edit(cb, f"👤 *PPP Secrets* ({len(secrets)} total)", kb.vpn_secrets_list(secrets, page))


@router.callback_query(F.data.startswith("vpn:secret:remove:"))
async def vpn_secret_remove(cb: CallbackQuery):
    secret_id = cb.data.split(":")[3]
    if not ctx.rbac.can(cb.from_user.id, "vpn.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_vpn_secret(secret_id)
    await cb.answer("🗑 Secret removed")
    secrets = await r.get_vpn_secrets()
    await send_or_edit(cb, f"👤 *PPP Secrets* ({len(secrets)} total)", kb.vpn_secrets_list(secrets))


@router.callback_query(F.data.startswith("vpn:secret:"))
async def vpn_secret_detail(cb: CallbackQuery):
    secret_id = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    secrets = await r.get_vpn_secrets()
    secret = next((s for s in secrets if s.get(".id") == secret_id), None)
    if not secret:
        await cb.answer("Secret not found.", show_alert=True)
        return
    await send_or_edit(cb, fmt.fmt_vpn_secret(secret), kb.vpn_secret_detail(secret_id))


@router.callback_query(F.data == "vpn:add_secret")
async def vpn_add_secret(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "vpn.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    ctx.sessions.set_state(cb.from_user.id, "vpn:add:name")
    await send_or_edit(cb, "👤 *Add VPN User*\n\nEnter username:", kb.cancel_keyboard("menu:vpn"))


@router.callback_query(F.data == "vpn:l2tp")
async def vpn_l2tp(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    l2tp = await r.get_l2tp_server()
    text = (
        f"🔒 *L2TP Server*\n"
        f"Enabled: {'✅' if l2tp.get('enabled') == 'yes' else '❌'}\n"
        f"Auth: `{l2tp.get('authentication', '?')}`"
    )
    await send_or_edit(cb, text, kb.vpn_menu())


@router.callback_query(F.data == "vpn:ovpn")
async def vpn_ovpn(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    ovpn = await r.get_ovpn_server()
    text = (
        f"🔑 *OpenVPN Server*\n"
        f"Enabled: {'✅' if ovpn.get('enabled') == 'yes' else '❌'}\n"
        f"Port: `{ovpn.get('port', '1194')}`"
    )
    await send_or_edit(cb, text, kb.vpn_menu())


@router.callback_query(F.data == "vpn:wg")
async def vpn_wg(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    ifaces = await r.get_wireguard_interfaces()
    peers = await r.get_wireguard_peers()
    if not ifaces:
        await send_or_edit(cb, "🔒 WireGuard not available on this device.", kb.vpn_menu())
        return
    await send_or_edit(cb, fmt.fmt_wireguard_peers(peers), kb.wireguard_menu(ifaces, peers))


@router.callback_query(F.data == "wg:peers")
async def wg_peers(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    peers = await r.get_wireguard_peers()
    await send_or_edit(cb, fmt.fmt_wireguard_peers(peers), kb.wg_peers_list(peers))


@router.callback_query(F.data.startswith("wg:add_peer:"))
async def wg_add_peer(cb: CallbackQuery):
    iface = cb.data.split(":")[2]
    ctx.sessions.set_state(cb.from_user.id, f"wg:add_peer:pubkey:{iface}")
    await send_or_edit(cb, "🔒 *Add WireGuard Peer*\n\nPaste peer's public key:", kb.cancel_keyboard("vpn:wg"))


@router.callback_query(F.data.startswith("wg:remove:"))
async def wg_remove(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    if not await ctx.perm(cb, "vpn.manage"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    if isinstance(r, RouterROS7):
        await r.remove_wireguard_peer(id_)
        await cb.answer("🗑 WG peer removed")
        peers = await r.get_wireguard_peers()
        await send_or_edit(cb, fmt.fmt_wireguard_peers(peers), kb.wg_peers_list(peers))


@router.callback_query(F.data == "vpn:profiles")
async def vpn_profiles(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    profiles = await r.get_ppp_profiles()
    await send_or_edit(cb, fmt.fmt_ppp_profiles(profiles), kb.vpn_menu())
