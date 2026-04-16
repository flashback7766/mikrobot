"""Extras handlers: hotspot, bridge, VLAN, queues, scripts detail, backup."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from ui import keyboards as kb
from ui import formatters as fmt

router = Router()


# ── Extras Hub ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:extras")
async def menu_extras(cb: CallbackQuery):
    await send_or_edit(cb, "🌉 *Extras*", kb.extras_menu())


# ── Backup ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:backup")
async def menu_backup(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "system.backup"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    await send_or_edit(cb, "📦 *Backup & Export*", kb.backup_menu())


@router.callback_query(F.data == "backup:create")
async def backup_create(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await cb.answer("💾 Creating backup…")
    filename = await r.create_backup()
    await send_or_edit(cb, f"✅ *Backup created!*\nFile: `{filename}`", kb.backup_menu())


@router.callback_query(F.data == "backup:export")
async def backup_export(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "system.export"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await cb.answer("📜 Exporting…")
    config = await r.export_config()
    if len(config) > 4000:
        from aiogram.types import BufferedInputFile
        doc = BufferedInputFile(config.encode(), filename="export.rsc")
        await cb.message.answer_document(doc, caption="📜 Router configuration export")
    else:
        await cb.message.answer(f"```\n{config}\n```", parse_mode="Markdown")


# ── Hotspot ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:hotspot")
async def menu_hotspot(cb: CallbackQuery):
    await send_or_edit(cb, "🔥 *Hotspot Manager*", kb.hotspot_menu())



@router.callback_query(F.data == "hotspot:users")
async def hotspot_users(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    users = await r.get_hotspot_users()
    await send_or_edit(cb, fmt.fmt_hotspot_users(users), kb.hotspot_users_menu(users))


@router.callback_query(F.data == "hotspot:active")
async def hotspot_active(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    sessions = await r.get_hotspot_active()
    await send_or_edit(cb, fmt.fmt_hotspot_active(sessions), kb.hotspot_active_menu(sessions))


@router.callback_query(F.data.startswith("hotspot:user:"))
async def hotspot_user_detail(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    users = await r.get_hotspot_users()
    u = next((x for x in users if x.get(".id") == id_), {})
    text = (
        f"👤 *Hotspot User: {u.get('name', '?')}*\n"
        f"Profile: `{u.get('profile', 'default')}`\n"
        f"Password: `{u.get('password', '?')}`\n"
        f"Comment: {u.get('comment', '-')}"
    )
    await send_or_edit(cb, text, kb.hotspot_user_detail_menu(id_))


@router.callback_query(F.data.startswith("hotspot:remove:"))
async def hotspot_remove(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    if not await ctx.perm(cb, "dhcp.manage"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_hotspot_user(id_)
    await cb.answer("🗑 User removed")
    users = await r.get_hotspot_users()
    await send_or_edit(cb, fmt.fmt_hotspot_users(users), kb.hotspot_users_menu(users))


@router.callback_query(F.data.startswith("hotspot:kick:"))
async def hotspot_kick(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    if not await ctx.perm(cb, "wireless.disconnect_client"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.disconnect_hotspot_user(id_)
    await cb.answer("🚫 Session disconnected")
    sessions = await r.get_hotspot_active()
    await send_or_edit(cb, fmt.fmt_hotspot_active(sessions), kb.hotspot_active_menu(sessions))


@router.callback_query(F.data == "hotspot:add_prompt")
async def hotspot_add_prompt(cb: CallbackQuery):
    if not await ctx.perm(cb, "dhcp.manage"):
        return
    ctx.sessions.set_state(cb.from_user.id, "hotspot:add:name")
    await send_or_edit(cb, "🔥 *Add Hotspot User*\n\nEnter username:", kb.cancel_keyboard("menu:hotspot"))


# ── Scripts (detail view) ────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:scripts")
async def menu_scripts(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    scripts = await r.get_scripts()
    await send_or_edit(cb, fmt.fmt_scripts(scripts), kb.scripts_menu(scripts))


@router.callback_query(F.data.startswith("script:detail:"))
async def script_detail(cb: CallbackQuery):
    name = ":".join(cb.data.split(":")[2:])
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    scripts = await r.get_scripts()
    s = next((x for x in scripts if x.get("name") == name), {})
    if not s:
        await cb.answer("Script not found.", show_alert=True)
        return
    await send_or_edit(cb, fmt.fmt_script_detail(s), kb.script_detail_menu(name))


@router.callback_query(F.data.startswith("script:run:"))
async def script_run(cb: CallbackQuery):
    name = ":".join(cb.data.split(":")[2:])
    if not await ctx.perm(cb, "system.export"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    try:
        await r.run_script(name)
        await cb.answer(f"▶️ Script '{name}' executed!")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)


# ── Bridge ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:bridge")
async def menu_bridge(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    bridges = await r.get_bridges()
    ports = await r.get_bridge_ports()
    await send_or_edit(cb, fmt.fmt_bridges(bridges, ports), kb.bridge_menu(bridges))


@router.callback_query(F.data.startswith("bridge:detail:"))
async def bridge_detail(cb: CallbackQuery):
    name = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    bridges = await r.get_bridges()
    b = next((x for x in bridges if x.get("name") == name), {})
    ports = await r.get_bridge_ports()
    bridge_ports = [p for p in ports if p.get("bridge") == name]
    port_text = "\n".join(
        f"   🔌 `{p.get('interface', '?')}` [priority: {p.get('priority', '?')}]"
        for p in bridge_ports
    )
    text = (
        f"🌉 *Bridge: {name}*\n"
        f"MAC: `{b.get('mac-address', '?')}`\n"
        f"STP: `{b.get('protocol-mode', 'none')}`\n"
        f"Forward delay: `{b.get('forward-delay', '?')}`\n\n"
        f"*Ports:*\n{port_text or '   (none)'}"
    )
    await send_or_edit(cb, text, kb.bridge_detail_menu(name))


@router.callback_query(F.data.startswith("bridge:ports:"))
async def bridge_ports(cb: CallbackQuery):
    bridge_name = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    ports = await r.get_bridge_ports()
    bridge_ports_list = [p for p in ports if p.get("bridge") == bridge_name]
    builder = InlineKeyboardBuilder()
    for p in bridge_ports_list:
        iface = p.get("interface", "?")
        id_ = p.get(".id", "")
        builder.row(InlineKeyboardButton(
            text=f"🗑 Remove {iface}",
            callback_data=f"bridge:port:remove:{id_}",
        ))
    builder.row(InlineKeyboardButton(text="← Back", callback_data=f"bridge:detail:{bridge_name}"))
    port_lines = "\n".join(f"• `{p.get('interface', '?')}`" for p in bridge_ports_list)
    await send_or_edit(cb, f"🔌 *Ports on {bridge_name}*\n\n{port_lines or 'None'}", builder.as_markup())


@router.callback_query(F.data.startswith("bridge:port:remove:"))
async def bridge_port_remove(cb: CallbackQuery):
    id_ = cb.data.split(":")[3]
    if not await ctx.perm(cb, "ip.manage"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_bridge_port(id_)
    await cb.answer("🗑 Port removed")


# ── VLAN ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "vlan:list")
async def vlan_list(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    vlans = await r.get_vlans()
    await send_or_edit(cb, fmt.fmt_vlans(vlans), kb.vlan_list_menu(vlans))


@router.callback_query(F.data == "vlan:add_prompt")
async def vlan_add_prompt(cb: CallbackQuery):
    if not await ctx.perm(cb, "ip.manage"):
        return
    ctx.sessions.set_state(cb.from_user.id, "vlan:add:name")
    await send_or_edit(cb, "🏷 *Add VLAN*\n\nEnter VLAN name:", kb.cancel_keyboard("vlan:list"))


@router.callback_query(F.data.startswith("vlan:detail:"))
async def vlan_detail(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    vlans = await r.get_vlans()
    v = next((x for x in vlans if x.get(".id") == id_), {})
    text = (
        f"🏷 *VLAN {v.get('vlan-id', '?')}: {v.get('name', '?')}*\n"
        f"Interface: `{v.get('interface', '?')}`\n"
        f"MTU: `{v.get('mtu', '1500')}`"
    )
    await send_or_edit(cb, text, kb.vlan_detail_menu(id_))


@router.callback_query(F.data.startswith("vlan:remove:"))
async def vlan_remove(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    if not await ctx.perm(cb, "ip.manage"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_vlan(id_)
    await cb.answer("🗑 VLAN removed")
    vlans = await r.get_vlans()
    await send_or_edit(cb, fmt.fmt_vlans(vlans), kb.vlan_list_menu(vlans))


# ── Queues ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:queues")
async def menu_queues(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    queues = await r.get_simple_queues()
    await send_or_edit(cb, fmt.fmt_queues(queues), kb.queues_menu(queues))


@router.callback_query(F.data == "queue:add_prompt")
async def queue_add_prompt(cb: CallbackQuery):
    if not await ctx.perm(cb, "firewall.manage"):
        return
    ctx.sessions.set_state(cb.from_user.id, "queue:add:name")
    await send_or_edit(cb, "📊 *Add Queue*\n\nEnter queue name:", kb.cancel_keyboard("menu:queues"))


@router.callback_query(F.data.startswith("queue:detail:"))
async def queue_detail(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    queues = await r.get_simple_queues()
    q = next((x for x in queues if x.get(".id") == id_), {})
    if not q:
        await cb.answer("Queue not found.", show_alert=True)
        return
    disabled = q.get("disabled", "false") == "true"
    await send_or_edit(cb, fmt.fmt_queue_detail(q), kb.queue_detail_menu(id_, disabled))


@router.callback_query(F.data.startswith("queue:enable:") | F.data.startswith("queue:disable:"))
async def queue_toggle(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    if not await ctx.perm(cb, "firewall.manage"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    if "enable" in cb.data:
        await r.enable_simple_queue(id_)
        await cb.answer("✅ Queue enabled")
    else:
        await r.disable_simple_queue(id_)
        await cb.answer("⛔ Queue disabled")
    queues = await r.get_simple_queues()
    await send_or_edit(cb, fmt.fmt_queues(queues), kb.queues_menu(queues))


@router.callback_query(F.data.startswith("queue:remove:"))
async def queue_remove(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    if not await ctx.perm(cb, "firewall.manage"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_simple_queue(id_)
    await cb.answer("🗑 Queue removed")
    queues = await r.get_simple_queues()
    await send_or_edit(cb, fmt.fmt_queues(queues), kb.queues_menu(queues))
