"""Admin handlers: settings, router management, bot users, containers, language."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from core.router_ros7 import RouterROS7
from core.rbac import Role
from core.audit import log_admin
from ui import keyboards as kb
from ui.i18n import t, get_lang

router = Router()


# ── Settings ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:settings")
async def menu_settings(cb: CallbackQuery):
    await send_or_edit(cb, "⚙️ *Settings*", kb.settings_menu())


@router.callback_query(F.data == "settings:lang")
async def settings_lang(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id, ctx.sessions)
    await send_or_edit(cb, t("settings.lang_prompt", lang), kb.lang_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def lang_select(cb: CallbackQuery):
    new_lang = cb.data.split(":")[1]
    ctx.sessions.set_language(cb.from_user.id, new_lang)
    await cb.answer(t("settings.lang_set", new_lang))
    await send_or_edit(cb, "📋 Main Menu", kb.main_menu())


# ── Router Management ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "settings:routers")
async def settings_routers(cb: CallbackQuery):
    uid = cb.from_user.id
    router_list = ctx.rm.get_router_list(uid)
    if not router_list:
        text = "🔌 *Your Routers*\n\nNo routers connected yet.\nUse ➕ Add Router."
    else:
        text = f"🔌 *Your Routers* ({len(router_list)} connected)"
    await send_or_edit(cb, text, kb.routers_menu(router_list))


@router.callback_query(F.data.startswith("router:select:"))
async def router_select(cb: CallbackQuery):
    alias = cb.data.split(":")[2]
    router_list = ctx.rm.get_router_list(cb.from_user.id)
    entry = next((r for r in router_list if r["alias"] == alias), None)
    if not entry:
        await cb.answer("Router not found.", show_alert=True)
        return
    is_active = entry.get("active", False)
    await send_or_edit(
        cb,
        f"🔌 *Router: {alias}*\nHost: `{entry['host']}`\nROS{entry['version']}",
        kb.router_detail_menu(alias, is_active),
    )


@router.callback_query(F.data.startswith("router:activate:"))
async def router_activate(cb: CallbackQuery):
    alias = cb.data.split(":")[2]
    if ctx.rm.switch_router(cb.from_user.id, alias):
        await cb.answer(f"⭐ Switched to {alias}")
    router_list = ctx.rm.get_router_list(cb.from_user.id)
    await send_or_edit(cb, "🔌 *Your Routers*", kb.routers_menu(router_list))


@router.callback_query(F.data.startswith("router:remove:"))
async def router_remove(cb: CallbackQuery):
    alias = cb.data.split(":")[2]
    if not ctx.rbac.can(cb.from_user.id, "router.remove"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    await ctx.rm.remove_router(cb.from_user.id, alias)
    log_admin(cb.from_user.id, "router_remove", alias)
    await cb.answer(f"🗑 {alias} removed")
    router_list = ctx.rm.get_router_list(cb.from_user.id)
    await send_or_edit(cb, "🔌 *Your Routers*", kb.routers_menu(router_list))


@router.callback_query(F.data == "router:add")
async def router_add(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "router.add"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    ctx.sessions.set_state(cb.from_user.id, "add_router:alias")
    await send_or_edit(
        cb,
        "➕ *Add Router*\n\nStep 1/5: Enter a name (alias) for this router:",
        kb.cancel_keyboard("settings:routers"),
    )


# ── Bot Users ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "settings:users")
async def settings_users(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "user.view"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    users = ctx.rbac.get_all_users()
    await send_or_edit(cb, f"👥 *Bot Users* ({len(users)})", kb.bot_users_menu(users))


@router.callback_query(F.data.startswith("admin:user:"))
async def admin_user(cb: CallbackQuery):
    target_uid = int(cb.data.split(":")[2])
    if not ctx.rbac.can(cb.from_user.id, "user.role.change"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    role = ctx.rbac.get_role(target_uid)
    text = f"👤 *User ID: {target_uid}*\nCurrent role: `{role.to_str() if role else 'none'}`"
    await send_or_edit(cb, text, kb.user_role_menu(target_uid))


@router.callback_query(F.data.startswith("admin:setrole:"))
async def admin_setrole(cb: CallbackQuery):
    parts = cb.data.split(":")
    target_uid = int(parts[2])
    new_role_str = parts[3]
    if not ctx.rbac.can(cb.from_user.id, "user.role.change"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    new_role = Role.from_str(new_role_str)
    await ctx.rbac.set_role(target_uid, new_role)
    log_admin(cb.from_user.id, "role_change", f"{target_uid} → {new_role_str}")
    await cb.answer(f"✅ User {target_uid} → {new_role_str}")
    users = ctx.rbac.get_all_users()
    await send_or_edit(cb, f"👥 *Bot Users* ({len(users)})", kb.bot_users_menu(users))


@router.callback_query(F.data.startswith("admin:removeuser:"))
async def admin_removeuser(cb: CallbackQuery):
    target_uid = int(cb.data.split(":")[2])
    if not ctx.rbac.can(cb.from_user.id, "user.remove"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    await ctx.rbac.remove_user(target_uid)
    log_admin(cb.from_user.id, "user_remove", str(target_uid))
    await cb.answer(f"🗑 User {target_uid} removed")
    users = ctx.rbac.get_all_users()
    await send_or_edit(cb, f"👥 *Bot Users* ({len(users)})", kb.bot_users_menu(users))


@router.callback_query(F.data == "admin:add_user")
async def admin_add_user(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "user.add"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    ctx.sessions.set_state(cb.from_user.id, "admin:add_user")
    await send_or_edit(cb, "👤 *Add Bot User*\n\nEnter the Telegram user ID:", kb.cancel_keyboard("settings:users"))


# ── Containers (ROS7) ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "container:list")
async def container_list(cb: CallbackQuery):
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    containers = await r.get_container_list()
    if not containers:
        await send_or_edit(cb, "🐋 No containers on this device.", kb.settings_menu())
        return
    await send_or_edit(cb, f"🐋 *Docker Containers* ({len(containers)})", kb.container_menu(containers))


@router.callback_query(F.data.startswith("container:detail:"))
async def container_detail(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    containers = await r.get_container_list()
    c = next((x for x in containers if x.get(".id") == id_), {})
    status = c.get("status", "stopped")
    name = c.get("name", id_[:8])
    text = (
        f"🐋 *Container: {name}*\n"
        f"ID: `{id_}`\n"
        f"Status: `{status}`\n"
        f"Image: `{c.get('remote-image', '?')}`"
    )
    await send_or_edit(cb, text, kb.container_detail_menu(id_, status == "running"))


@router.callback_query(F.data.startswith("container:start:"))
async def container_start(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    if isinstance(r, RouterROS7):
        await r.start_container(id_)
        await cb.answer("▶️ Container starting…")


@router.callback_query(F.data.startswith("container:stop:"))
async def container_stop(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    if isinstance(r, RouterROS7):
        await r.stop_container(id_)
        await cb.answer("⛔ Container stopping…")


@router.callback_query(F.data.startswith("container:remove:"))
async def container_remove_handler(cb: CallbackQuery):
    id_ = cb.data.split(":")[2]
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    if isinstance(r, RouterROS7):
        await r.remove_container(id_)
        await cb.answer("🗑 Container removed")
