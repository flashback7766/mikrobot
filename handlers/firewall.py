"""Firewall handlers: filter rules, NAT, mangle, address lists, connection tracking."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from ui import keyboards as kb
from ui import formatters as fmt

router = Router()


# ── Firewall Menu ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:firewall")
async def menu_firewall(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "firewall.view"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    await send_or_edit(cb, "🛡 *Firewall Manager*", kb.firewall_menu())


# ── Filter Rules ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "fw:filter")
async def fw_filter(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    rules = await r.get_firewall_filter()
    page = ctx.sessions.get_page(cb.from_user.id)
    await send_or_edit(cb, f"🛡 *Firewall Filter Rules* ({len(rules)} total)", kb.firewall_rule_list(rules, page))


@router.callback_query(F.data.startswith("fw:filter:page:"))
async def fw_filter_page(cb: CallbackQuery):
    page = int(cb.data.split(":")[3])
    ctx.sessions.set_page(cb.from_user.id, page)
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    rules = await r.get_firewall_filter()
    await send_or_edit(cb, f"🛡 *Filter Rules* ({len(rules)} total)", kb.firewall_rule_list(rules, page))


@router.callback_query(F.data.startswith("fw:rule:"))
async def fw_rule_detail(cb: CallbackQuery):
    rule_id = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    rules = await r.get_firewall_filter()
    rule = next((x for x in rules if x.get(".id") == rule_id), None)
    if not rule:
        await cb.answer("Rule not found.", show_alert=True)
        return
    disabled = rule.get("disabled", "false") == "true"
    await send_or_edit(cb, fmt.fmt_firewall_rule(rule), kb.firewall_rule_detail(rule_id, disabled))


@router.callback_query(F.data.startswith("fw:enable:") | F.data.startswith("fw:disable:"))
async def fw_toggle(cb: CallbackQuery):
    rule_id = cb.data.split(":")[2]
    if not ctx.rbac.can(cb.from_user.id, "firewall.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    if "enable" in cb.data:
        await r.enable_firewall_rule(rule_id)
        await cb.answer("✅ Rule enabled")
    else:
        await r.disable_firewall_rule(rule_id)
        await cb.answer("⛔ Rule disabled")
    rules = await r.get_firewall_filter()
    await send_or_edit(cb, f"🛡 *Filter Rules* ({len(rules)} total)", kb.firewall_rule_list(rules, 0))


@router.callback_query(F.data.startswith("fw:remove:"))
async def fw_remove(cb: CallbackQuery):
    rule_id = cb.data.split(":")[2]
    if not ctx.rbac.can(cb.from_user.id, "firewall.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_firewall_rule(rule_id)
    await cb.answer("🗑 Rule removed")
    rules = await r.get_firewall_filter()
    await send_or_edit(cb, f"🛡 *Filter Rules* ({len(rules)} total)", kb.firewall_rule_list(rules, 0))


@router.callback_query(F.data.startswith("fw:move_up:") | F.data.startswith("fw:move_down:"))
async def fw_move(cb: CallbackQuery):
    rule_id = cb.data.split(":")[2]
    if not ctx.rbac.can(cb.from_user.id, "firewall.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    rules = await r.get_firewall_filter()
    ids = [x.get(".id") for x in rules]
    try:
        idx = ids.index(rule_id)
    except ValueError:
        await cb.answer("Rule not found.", show_alert=True)
        return
    if "up" in cb.data:
        dest = max(0, idx - 1)
    else:
        dest = min(len(rules) - 1, idx + 1)
    await r.move_firewall_rule(rule_id, dest)
    await cb.answer(f"Moved to position {dest}")
    rules = await r.get_firewall_filter()
    await send_or_edit(cb, f"🛡 *Filter Rules* ({len(rules)} total)", kb.firewall_rule_list(rules, 0))


# ── NAT ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "fw:nat")
async def fw_nat(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    rules = await r.get_firewall_nat()
    lines = [f"🔀 *NAT Rules* ({len(rules)} total)\n"]
    for rule in rules:
        id_ = rule.get(".id", "?")
        chain = rule.get("chain", "?")
        action = rule.get("action", "?")
        to = rule.get("to-addresses", rule.get("to-ports", ""))
        comment = rule.get("comment", "")
        icon = "⛔" if rule.get("disabled", "false") == "true" else "🟢"
        lines.append(
            f"{icon} `{id_}` [{chain}] → `{action}`"
            + (f" to `{to}`" if to else "")
            + (f" | {comment}" if comment else "")
        )
    builder = InlineKeyboardBuilder()
    for rule in rules:
        id_ = rule.get(".id", "?")
        builder.row(InlineKeyboardButton(
            text=f"[{rule.get('chain', '?')}] {rule.get('action', '?')} ({id_})",
            callback_data=f"nat:detail:{id_}",
        ))
    builder.row(
        InlineKeyboardButton(text="➕ Add NAT Rule", callback_data="nat:add_prompt"),
        InlineKeyboardButton(text="← Back", callback_data="menu:firewall"),
    )
    await send_or_edit(cb, "\n".join(lines)[:4096], builder.as_markup())


@router.callback_query(F.data.startswith("nat:detail:"))
async def nat_detail(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    rules = await r.get_firewall_nat()
    rule = next((x for x in rules if x.get(".id") == id_), {})
    if not rule:
        await cb.answer("NAT rule not found.", show_alert=True)
        return
    await send_or_edit(cb, fmt.fmt_nat_detail(rule), kb.nat_rule_detail_menu(id_))


@router.callback_query(F.data.startswith("nat:remove:"))
async def nat_remove(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    if not await ctx.perm(cb, "firewall.manage"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_firewall_nat(id_)
    await cb.answer("🗑 NAT rule removed")
    await send_or_edit(cb, "🔀 *NAT Manager*", kb.firewall_menu())


@router.callback_query(F.data == "nat:add_prompt")
async def nat_add_prompt(cb: CallbackQuery):
    if not await ctx.perm(cb, "firewall.manage"):
        return
    await send_or_edit(cb, "🔀 *Add NAT Rule*\n\nSelect chain:", kb.nat_add_type_menu())


@router.callback_query(F.data.startswith("nat:add:chain:"))
async def nat_add_chain(cb: CallbackQuery):
    chain = cb.data.split(":")[3]
    ctx.sessions.update_data(cb.from_user.id, nat_chain=chain)
    await send_or_edit(cb, f"NAT chain: `{chain}`\nSelect action:", kb.nat_add_action_menu(chain))


@router.callback_query(F.data.startswith("nat:add:action:"))
async def nat_add_action(cb: CallbackQuery):
    parts = cb.data.split(":")
    action = parts[3]
    chain = parts[4]
    ctx.sessions.update_data(cb.from_user.id, nat_action=action, nat_chain=chain)
    ctx.sessions.set_state(cb.from_user.id, "nat:add:src_addr")
    await send_or_edit(
        cb,
        f"Action: `{action}` on `{chain}`\n\nSource IP/subnet (or `-` to skip):",
        kb.cancel_keyboard("fw:nat"),
    )


# ── Connection Tracking ──────────────────────────────────────────────────────

@router.callback_query(F.data == "fw:connections")
async def fw_connections(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    conns = await r.get_connection_tracking()
    lines = [f"🔗 *Active Connections* ({len(conns)})\n"]
    for c in conns[:15]:
        src = c.get("src-address", "?")
        dst = c.get("dst-address", "?")
        proto = c.get("protocol", "?")
        state = c.get("state", "?")
        lines.append(f"`{src}` → `{dst}` [{proto}/{state}]")
    await send_or_edit(cb, "\n".join(lines), kb.firewall_menu())


# ── Address Lists ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "fw:addrlist")
async def fw_addrlist(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    entries = await r.get_address_list()
    list_names = list(dict.fromkeys(e.get("list", "") for e in entries))
    await send_or_edit(cb, fmt.fmt_address_list(entries), kb.address_list_menu(list_names))


@router.callback_query(F.data.startswith("fw:addrlist:view:"))
async def fw_addrlist_view(cb: CallbackQuery):
    list_name = cb.data.split(":")[3]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    entries = await r.get_address_list(list_name)
    text = fmt.fmt_address_list(entries)
    builder_kb = kb.confirm_keyboard(f"fw:addrlist:add_prompt:{list_name}", "fw:addrlist")
    await send_or_edit(cb, text or f"📋 *{list_name}* — empty", builder_kb)


@router.callback_query(F.data.startswith("fw:addrlist:add_prompt:"))
async def fw_addrlist_add_prompt(cb: CallbackQuery):
    list_name = cb.data.split(":")[3]
    ctx.sessions.set_state(cb.from_user.id, f"fw:addrlist:add:{list_name}")
    await send_or_edit(cb, f"Enter IP/subnet to add to `{list_name}`:", kb.cancel_keyboard("fw:addrlist"))


@router.callback_query(F.data == "fw:addrlist:add")
async def fw_addrlist_add(cb: CallbackQuery):
    ctx.sessions.set_state(cb.from_user.id, "fw:addrlist:add_choose_list")
    await send_or_edit(
        cb,
        "Enter `list_name:ip_address` format:\nExample: `blacklist:1.2.3.4`",
        kb.cancel_keyboard("fw:addrlist"),
    )


# ── Add Rule Wizard ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "fw:add_rule")
async def fw_add_rule(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "firewall.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    await send_or_edit(cb, "🛡 *Add Firewall Rule*\n\nStep 1: Select chain:", kb.fw_add_rule_chain())


@router.callback_query(F.data.startswith("fw:add:chain:"))
async def fw_add_chain(cb: CallbackQuery):
    chain = cb.data.split(":")[3]
    ctx.sessions.set_state(cb.from_user.id, "fw:add_rule")
    ctx.sessions.update_data(cb.from_user.id, chain=chain)
    await send_or_edit(cb, "Step 2: Select action:", kb.fw_add_rule_action())


@router.callback_query(F.data.startswith("fw:add:action:"))
async def fw_add_action(cb: CallbackQuery):
    action = cb.data.split(":")[3]
    ctx.sessions.update_data(cb.from_user.id, action=action)
    await send_or_edit(cb, "Step 3: Select protocol:", kb.fw_add_rule_protocol())


@router.callback_query(F.data.startswith("fw:add:proto:"))
async def fw_add_proto(cb: CallbackQuery):
    proto = cb.data.split(":")[3]
    ctx.sessions.update_data(cb.from_user.id, protocol=proto)
    ctx.sessions.set_state(cb.from_user.id, "fw:add:src_ip")
    await send_or_edit(
        cb,
        "Step 4: Enter source IP/subnet (or `-` to skip):",
        kb.cancel_keyboard("fw:filter"),
    )


@router.callback_query(F.data == "fw:block_ip")
async def fw_block_ip(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "firewall.address_list.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    ctx.sessions.set_state(cb.from_user.id, "fw:block_ip")
    await send_or_edit(
        cb,
        "🚫 *Quick Block IP*\n\nEnter IP address or subnet to block:",
        kb.cancel_keyboard("menu:firewall"),
    )


# ── Mangle ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "fw:mangle")
async def fw_mangle(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    rules = await r.get_firewall_mangle()
    page = ctx.sessions.get_page(cb.from_user.id)
    await send_or_edit(cb, fmt.fmt_mangle_rules(rules), kb.mangle_rule_list(rules, page))


@router.callback_query(F.data.startswith("mangle:page:"))
async def mangle_page(cb: CallbackQuery):
    page = int(cb.data.split(":")[2])
    ctx.sessions.set_page(cb.from_user.id, page)
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    rules = await r.get_firewall_mangle()
    await send_or_edit(cb, fmt.fmt_mangle_rules(rules), kb.mangle_rule_list(rules, page))


@router.callback_query(F.data.startswith("mangle:detail:"))
async def mangle_detail(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    rules = await r.get_firewall_mangle()
    rule = next((x for x in rules if x.get(".id") == id_), {})
    if not rule:
        await cb.answer("Rule not found.", show_alert=True)
        return
    chain = rule.get("chain", "?")
    action = rule.get("action", "?")
    mark = rule.get("new-routing-mark", rule.get("new-packet-mark", ""))
    text = (
        f"🔀 *Mangle Rule {id_}*\n"
        f"Chain: `{chain}` | Action: `{action}`\n"
        + (f"Mark: `{mark}`\n" if mark else "")
        + f"Comment: {rule.get('comment', '-')}"
    )
    await send_or_edit(cb, text, kb.mangle_detail_menu(id_))


@router.callback_query(F.data.startswith("mangle:remove:"))
async def mangle_remove(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    if not await ctx.perm(cb, "firewall.manage"):
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.remove_firewall_mangle(id_)
    await cb.answer("🗑 Mangle rule removed")
    rules = await r.get_firewall_mangle()
    await send_or_edit(cb, fmt.fmt_mangle_rules(rules), kb.mangle_rule_list(rules, 0))


@router.callback_query(F.data == "mangle:add_prompt")
async def mangle_add_prompt(cb: CallbackQuery):
    if not await ctx.perm(cb, "firewall.manage"):
        return
    await send_or_edit(
        cb,
        "🔀 *Add Mangle Rule*\n\nEnter in format:\n`chain action [src-address] [comment]`\n"
        "Example: `prerouting mark-packet 192.168.1.0/24 voip`",
        kb.cancel_keyboard("fw:mangle"),
    )
    ctx.sessions.set_state(cb.from_user.id, "mangle:add")
