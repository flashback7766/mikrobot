"""Network handlers: routes, DNS, IP management, ARP, pools."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from ui import keyboards as kb
from ui import formatters as fmt

router = Router()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:routes")
async def menu_routes(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    routes = await r.get_routes()
    await send_or_edit(cb, fmt.fmt_routes(routes), kb.routes_menu(routes))


@router.callback_query(F.data.startswith("route:detail:"))
async def route_detail(cb: CallbackQuery):
    route_id = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    routes = await r.get_routes()
    route = next((x for x in routes if x.get(".id") == route_id), None)
    if not route:
        await cb.answer("Route not found.", show_alert=True)
        return
    dst = route.get("dst-address", "?")
    gw = route.get("gateway", "?")
    active = "🟢" if route.get("active") == "true" else "🔴"
    text = f"🗺 *Route*\n{active} `{dst}` → `{gw}`\nDistance: `{route.get('distance', '?')}`"
    await send_or_edit(cb, text, kb.route_detail_menu(route_id))


@router.callback_query(F.data.startswith("route:remove:"))
async def route_remove(cb: CallbackQuery):
    route_id = cb.data.split(":")[2]
    if not ctx.rbac.can(cb.from_user.id, "route.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_route(route_id)
    await cb.answer("🗑 Route removed")
    routes = await r.get_routes()
    await send_or_edit(cb, fmt.fmt_routes(routes), kb.routes_menu(routes))


@router.callback_query(F.data == "route:add")
async def route_add(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "route.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    ctx.sessions.set_state(cb.from_user.id, "route:add:dst")
    await send_or_edit(
        cb,
        "🗺 *Add Route*\n\nEnter destination address:\nExample: `10.0.0.0/8` or `0.0.0.0/0`",
        kb.cancel_keyboard("menu:routes"),
    )


# ── DNS ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:dns")
async def menu_dns(cb: CallbackQuery):
    await send_or_edit(cb, "🌐 *DNS Manager*", kb.dns_menu())


@router.callback_query(F.data == "dns:settings")
async def dns_settings(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    settings = await r.get_dns_settings()
    await send_or_edit(cb, fmt.fmt_dns(settings), kb.dns_menu())


@router.callback_query(F.data == "dns:cache")
async def dns_cache(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    cache = await r.get_dns_cache()
    await send_or_edit(cb, fmt.fmt_dns_cache(cache), kb.dns_menu())


@router.callback_query(F.data == "dns:flush")
async def dns_flush(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "dns.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.flush_dns_cache()
    await cb.answer("🗑 DNS cache flushed!")
    settings = await r.get_dns_settings()
    await send_or_edit(cb, fmt.fmt_dns(settings), kb.dns_menu())


@router.callback_query(F.data == "dns:set_servers")
async def dns_set_servers(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "dns.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    ctx.sessions.set_state(cb.from_user.id, "dns:set_servers")
    await send_or_edit(
        cb,
        "🌐 Enter DNS servers (comma or space separated):\nExample: `1.1.1.1 8.8.8.8`",
        kb.cancel_keyboard("menu:dns"),
    )


# ── IP Management ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("menu:ip") | (F.data == "menu:network"))
async def menu_network(cb: CallbackQuery):
    await send_or_edit(cb, "🌐 *Network*", kb.network_menu())


@router.callback_query(F.data == "ip:list")
async def ip_list(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    addrs = await r.get_ip_addresses()
    await send_or_edit(cb, fmt.fmt_ip_addresses(addrs), kb.ip_address_list_menu(addrs))


@router.callback_query(F.data.startswith("ip:addr:detail:"))
async def ip_addr_detail(cb: CallbackQuery):
    id_ = cb.data.split(":")[3]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    addrs = await r.get_ip_addresses()
    addr = next((a for a in addrs if a.get(".id") == id_), {})
    text = (
        f"📍 *IP Address*\n"
        f"`{addr.get('address', '?')}` on `{addr.get('interface', '?')}`\n"
        f"Network: `{addr.get('network', '?')}`"
    )
    await send_or_edit(cb, text, kb.ip_addr_detail_menu(id_))


@router.callback_query(F.data.startswith("ip:remove:"))
async def ip_remove(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    if not await ctx.perm(cb, "ip.manage"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_ip_address(id_)
    await cb.answer("🗑 IP removed")
    addrs = await r.get_ip_addresses()
    await send_or_edit(cb, fmt.fmt_ip_addresses(addrs), kb.ip_address_list_menu(addrs))


@router.callback_query(F.data == "ip:add_prompt")
async def ip_add_prompt(cb: CallbackQuery):
    if not await ctx.perm(cb, "ip.manage"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    ifaces = await r.get_interfaces()
    iface_names = [i.get("name", "?") for i in ifaces[:10]]
    await send_or_edit(
        cb,
        f"📍 *Add IP Address*\n\nEnter address/prefix:\nExample: `192.168.88.1/24`\n\n"
        f"Available interfaces: `{'`, `'.join(iface_names)}`",
        kb.cancel_keyboard("ip:list"),
    )
    ctx.sessions.set_state(cb.from_user.id, "ip:add_addr")


@router.callback_query(F.data == "ip:arp")
async def ip_arp(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    arp = await r.get_arp()
    await send_or_edit(cb, fmt.fmt_arp(arp), kb.arp_menu())


@router.callback_query(F.data == "ip:pools")
async def ip_pools(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    pools = await r.get_ip_pools()
    await send_or_edit(cb, fmt.fmt_ip_pools(pools), kb.ip_pools_menu(pools))


@router.callback_query(F.data == "ip:pool:add_prompt")
async def ip_pool_add(cb: CallbackQuery):
    if not await ctx.perm(cb, "ip.manage"):
        return
    ctx.sessions.set_state(cb.from_user.id, "ip:pool:add:name")
    await send_or_edit(
        cb,
        "🏊 *Add IP Pool*\n\nEnter pool name:\nExample: `dhcp_pool`",
        kb.cancel_keyboard("ip:pools"),
    )


@router.callback_query(F.data.startswith("ip:pool:detail:"))
async def ip_pool_detail(cb: CallbackQuery):
    id_ = cb.data.split(":")[3]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    pools = await r.get_ip_pools()
    pool = next((p for p in pools if p.get(".id") == id_), {})
    await send_or_edit(
        cb,
        f"🏊 *IP Pool: {pool.get('name', '?')}*\nRanges: `{pool.get('ranges', '?')}`",
        kb.ip_pool_detail_menu(id_),
    )


@router.callback_query(F.data.startswith("ip:pool:remove:"))
async def ip_pool_remove(cb: CallbackQuery):
    id_ = cb.data.split(":")[3]
    if not await ctx.perm(cb, "ip.manage"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_ip_pool(id_)
    await cb.answer("🗑 Pool removed")
    pools = await r.get_ip_pools()
    await send_or_edit(cb, fmt.fmt_ip_pools(pools), kb.ip_pools_menu(pools))
