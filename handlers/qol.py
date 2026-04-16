"""
QoL handlers — Quality of Life features that don't fit a single domain.

Features:
  - /quality   — API connection quality test (latency, jitter, loss)
  - /find      — Global search across all router entities
  - Favorite commands (quick-access bookmarks)
  - Connection detail view (host, version, ROS type)
  - Quick reboot confirm shortcut
  - Router health card with progress bars
"""

import asyncio

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from core.quality import check_api_latency, fmt_quality
from ui import keyboards as kb
from ui import formatters as fmt

router = Router()


# ── Connection Quality Test (/quality) ───────────────────────────────────────

@router.message(Command("quality"))
async def cmd_quality(msg: Message):
    r = await require_router(msg, ctx.rm)
    if not r:
        return
    sent = await msg.answer("📡 Testing connection quality…")
    result = await check_api_latency(r, samples=5)
    text = (
        "📡 *Connection Quality*\n\n"
        f"{fmt_quality(result)}\n\n"
        f"Samples: `5` | Timeout: `5s`"
    )
    await sent.edit_text(text, parse_mode="Markdown")


@router.callback_query(F.data == "qol:quality")
async def cb_quality(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await cb.answer("📡 Testing…")
    result = await check_api_latency(r, samples=3)
    await send_or_edit(cb, f"📡 *Connection Quality*\n\n{fmt_quality(result)}", kb.main_menu())


# ── Global Search (/find) ────────────────────────────────────────────────────

@router.message(Command("find"))
async def cmd_find(msg: Message):
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        ctx.sessions.set_state(msg.from_user.id, "qol:find")
        await msg.answer(
            "🔍 *Global Search*\n\n"
            "Enter search term (IP, MAC, hostname, interface name):\n"
            "Example: `192.168.88` or `AA:BB` or `ether1`",
            parse_mode="Markdown",
            reply_markup=kb.cancel_keyboard("menu:main"),
        )
        return
    await _do_search(msg, parts[1].strip())


@router.callback_query(F.data == "qol:find")
async def cb_find(cb: CallbackQuery):
    ctx.sessions.set_state(cb.from_user.id, "qol:find")
    await send_or_edit(
        cb,
        "🔍 *Global Search*\n\nEnter IP, MAC, hostname, or interface name:",
        kb.cancel_keyboard("menu:main"),
    )


async def _do_search(source: Message, query: str):
    """Search across DHCP leases, ARP, interfaces, firewall address lists."""
    if isinstance(source, Message):
        msg = source
        send = msg.answer
    else:
        send = source.message.answer

    r = await require_router(source, ctx.rm)
    if not r:
        return

    await send(f"🔍 Searching `{query}`…", parse_mode="Markdown")
    q = query.lower()
    results = []

    try:
        # DHCP leases
        leases = await r.get_dhcp_leases()
        for l in leases:
            if (q in l.get("mac-address", "").lower() or
                    q in l.get("address", "").lower() or
                    q in l.get("host-name", "").lower() or
                    q in l.get("comment", "").lower()):
                results.append(f"📡 *DHCP Lease*: `{l.get('address', '?')}` | `{l.get('mac-address', '?')}` | {l.get('host-name', '-')}")
    except Exception:
        pass

    try:
        # ARP table
        arp = await r.get_arp()
        for a in arp:
            if q in a.get("address", "").lower() or q in a.get("mac-address", "").lower():
                results.append(f"📋 *ARP*: `{a.get('address', '?')}` → `{a.get('mac-address', '?')}` on `{a.get('interface', '?')}`")
    except Exception:
        pass

    try:
        # Interfaces
        ifaces = await r.get_interfaces()
        for i in ifaces:
            if (q in i.get("name", "").lower() or
                    q in i.get("mac-address", "").lower() or
                    q in i.get("comment", "").lower()):
                status = "🟢" if i.get("running") == "true" else "🔴"
                results.append(f"🔌 *Interface*: {status} `{i.get('name', '?')}` [{i.get('type', '?')}]")
    except Exception:
        pass

    try:
        # IP addresses
        addrs = await r.get_ip_addresses()
        for a in addrs:
            if q in a.get("address", "").lower() or q in a.get("interface", "").lower():
                results.append(f"📍 *IP*: `{a.get('address', '?')}` on `{a.get('interface', '?')}`")
    except Exception:
        pass

    try:
        # Firewall address lists
        alist = await r.get_address_list()
        for a in alist:
            if q in a.get("address", "").lower() or q in a.get("list", "").lower():
                results.append(f"🛡 *AddrList*: `{a.get('address', '?')}` in `{a.get('list', '?')}`")
    except Exception:
        pass

    try:
        # DNS cache
        cache = await r.get_dns_cache()
        for c in cache:
            if q in c.get("name", "").lower() or q in c.get("address", "").lower():
                results.append(f"🌐 *DNS*: `{c.get('name', '?')}` → `{c.get('address', '?')}`")
    except Exception:
        pass

    if not results:
        await send(f"🔍 No results for `{query}`", parse_mode="Markdown")
        return

    header = f"🔍 *Search: `{query}`* — {len(results)} result(s)\n\n"
    body = "\n".join(results[:20])
    if len(results) > 20:
        body += f"\n\n_…and {len(results) - 20} more_"
    await send(header + body, parse_mode="Markdown")


# ── Router Health Card ────────────────────────────────────────────────────────

@router.callback_query(F.data == "qol:health_card")
async def health_card(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await cb.answer("📊 Loading…")

    res = await r.get_system_resource()
    identity = await r.get_system_identity()

    cpu = int(res.get("cpu-load", 0))
    mem_free = int(res.get("free-memory", 0))
    mem_total = int(res.get("total-memory", 1))
    mem_used = mem_total - mem_free
    mem_pct = int(mem_used / mem_total * 100)

    hdd_free = int(res.get("free-hdd-space", 0))
    hdd_total = int(res.get("total-hdd-space", 1))
    hdd_pct = int((hdd_total - hdd_free) / hdd_total * 100) if hdd_total > 0 else 0

    def bar(pct: int, width: int = 12) -> str:
        filled = round(pct / 100 * width)
        color = "🟥" if pct > 85 else "🟨" if pct > 60 else "🟩"
        return color * filled + "⬜" * (width - filled)

    def _fmt(b: int) -> str:
        if b > 1024**3:
            return f"{b / 1024**3:.1f}GB"
        if b > 1024**2:
            return f"{b / 1024**2:.0f}MB"
        return f"{b / 1024:.0f}KB"

    text = (
        f"📊 *{identity.get('name', 'Router')} — Health Card*\n\n"
        f"🖥 CPU\n`{bar(cpu)}` {cpu}%\n\n"
        f"💾 RAM\n`{bar(mem_pct)}` {mem_pct}% ({_fmt(mem_used)}/{_fmt(mem_total)})\n\n"
        f"💿 Disk\n`{bar(hdd_pct)}` {hdd_pct}% ({_fmt(hdd_total - hdd_free)}/{_fmt(hdd_total)})\n\n"
        f"⏱ Uptime: `{res.get('uptime', '?')}`\n"
        f"🔧 ROS: `{res.get('version', '?')}`\n"
        f"🏷 Board: `{res.get('board-name', '?')}`"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Refresh", callback_data="qol:health_card"),
        InlineKeyboardButton(text="⬅ Back", callback_data="menu:system"),
    )
    await send_or_edit(cb, text, builder.as_markup())


# ── Quick Reboot Confirm ──────────────────────────────────────────────────────

@router.callback_query(F.data == "qol:reboot_now")
async def qol_reboot_now(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "system.reboot"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await cb.answer("🔁 Rebooting…")
    await r.reboot()
    await cb.message.edit_text(
        "🔁 *Reboot command sent.*\n\nRouter will be back in ~30 seconds.\n"
        "Use /status to check when it's back online.",
        parse_mode="Markdown",
    )


# ── Connection Detail View ────────────────────────────────────────────────────

@router.callback_query(F.data == "qol:conn_detail")
async def conn_detail(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return

    uid = cb.from_user.id
    router_list = ctx.rm.get_router_list(uid)
    active_entry = next((e for e in router_list if e.get("active")), None)

    if not active_entry:
        await cb.answer("No active router.", show_alert=True)
        return

    # Get API quality
    quality = await check_api_latency(r, samples=2)

    text = (
        f"🔌 *Connection Details*\n\n"
        f"*Alias:* `{active_entry.get('alias', '?')}`\n"
        f"*Host:* `{active_entry.get('host', '?')}`\n"
        f"*Port:* `{active_entry.get('port', 8728)}`\n"
        f"*SSL:* {'✅' if active_entry.get('use_ssl') else '❌'}\n"
        f"*User:* `{active_entry.get('username', '?')}`\n"
        f"*ROS Version:* `{active_entry.get('ros_version', '?')}`\n"
        f"*Standalone:* {'✅' if active_entry.get('standalone') else '❌'}\n\n"
        f"*API Quality:*\n{fmt_quality(quality)}"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Health Card", callback_data="qol:health_card"),
        InlineKeyboardButton(text="📡 Test Quality", callback_data="qol:quality"),
    )
    builder.row(InlineKeyboardButton(text="⬅ Back", callback_data="menu:settings"))
    await send_or_edit(cb, text, builder.as_markup())


# ── Bulk Operations LoL helper ────────────────────────────────────────────────

@router.callback_query(F.data == "qol:bulk_disable_fw")
async def qol_bulk_disable_fw(cb: CallbackQuery):
    """Panic button — disables ALL firewall filter rules at once."""
    if not ctx.rbac.can(cb.from_user.id, "firewall.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    # Show confirmation first
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚠️ YES, Disable ALL", callback_data="qol:bulk_disable_fw_confirm"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="menu:firewall"),
    )
    await send_or_edit(
        cb,
        "⚠️ *Disable ALL Firewall Rules?*\n\n"
        "This will disable EVERY filter rule!\n"
        "Use this for emergency troubleshooting only.",
        builder.as_markup(),
    )


@router.callback_query(F.data == "qol:bulk_disable_fw_confirm")
async def qol_bulk_disable_fw_confirm(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "firewall.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await cb.answer("⚠️ Disabling all rules…")
    rules = await r.get_firewall_filter()
    count = 0
    for rule in rules:
        if rule.get("disabled", "false") != "true":
            try:
                await r.disable_firewall_rule(rule[".id"])
                count += 1
            except Exception:
                pass
    await send_or_edit(
        cb,
        f"✅ *Done!* Disabled {count} firewall rule(s).\n\nUse Firewall → Filter Rules to re-enable.",
        kb.firewall_menu(),
    )


# ── IP Lookup (whois-style) ───────────────────────────────────────────────────

@router.message(Command("ip"))
async def cmd_ip_lookup(msg: Message):
    """Check if an IP is in DHCP leases, ARP, firewall address lists."""
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer(
            "🔎 *IP Lookup*\n\nUsage: `/ip 192.168.88.100`\n"
            "Searches: DHCP leases, ARP, address lists, routes",
            parse_mode="Markdown",
        )
        return
    query = parts[1].strip()
    await _do_search(msg, query)


# ── Cancel FSM callback ───────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery):
    ctx.sessions.clear_state(cb.from_user.id)
    await cb.answer("❌ Cancelled")
    await send_or_edit(cb, "📋 *Main Menu*", kb.main_menu())
