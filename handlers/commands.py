"""
Command handlers: /start, /help, /menu, /add_router, /stop_logs + QoL shortcuts.

QoL commands:
  /status   — Dashboard: bot uptime, router health, active sessions
  /ping     — Quick ping shortcut (no menu diving)
  /backup   — Quick backup shortcut
  /who      — Who's online (connected users)
  /routers  — Quick router list
"""

import time
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from ui import keyboards as kb
from ui import formatters as fmt
from ui.i18n import t, get_lang

router = Router()


# ── Core Commands ─────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(msg: Message):
    uid = msg.from_user.id
    lang = get_lang(uid, ctx.sessions)
    name = msg.from_user.first_name or "User"
    role = ctx.rbac.get_role(uid)
    role_str = f" ({role.to_str()})" if role else ""
    await msg.answer(
        t("start.welcome", lang, name=name, role=role_str),
        parse_mode="Markdown",
        reply_markup=kb.main_menu(),
    )


@router.message(Command("menu"))
async def cmd_menu(msg: Message):
    await msg.answer("📋 Main Menu", reply_markup=kb.main_menu())


@router.message(Command("add_router"))
async def cmd_add_router(msg: Message):
    if not ctx.rbac.can(msg.from_user.id, "router.add"):
        lang = get_lang(msg.from_user.id, ctx.sessions)
        await msg.answer(t("err.no_permission", lang))
        return
    uid = msg.from_user.id
    lang = get_lang(uid, ctx.sessions)
    ctx.sessions.set_state(uid, "add_router:alias")
    await msg.answer(
        t("fsm.router.alias", lang),
        parse_mode="Markdown",
        reply_markup=kb.cancel_keyboard("menu:main"),
    )


@router.message(Command("stop_logs"))
async def cmd_stop_logs(msg: Message):
    await ctx.sessions.stop_log_stream(msg.from_user.id)
    await msg.answer("🔴 Log stream stopped.")


@router.message(Command("cancel"))
async def cmd_cancel(msg: Message):
    """
    Universal cancel command — clears any active FSM state and returns user to menu.
    Works regardless of which wizard/flow the user is in.
    """
    uid = msg.from_user.id
    state = ctx.sessions.get_state(uid) if ctx.sessions else None

    ctx.sessions.clear_state(uid)

    if state and state not in ("idle", None, ""):
        await msg.answer(
            f"❌ *Cancelled.* Returned to main menu.",
            parse_mode="Markdown",
            reply_markup=kb.main_menu(),
        )
    else:
        await msg.answer(
            "📋 *Main Menu*",
            parse_mode="Markdown",
            reply_markup=kb.main_menu(),
        )


@router.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "🗺 *MikroBot Help*\n\n"
        "*Quick Commands:*\n"
        "/start — Main menu\n"
        "/status — 📊 Dashboard (uptime, health, sessions)\n"
        "/ping `host` — 🏓 Quick ping\n"
        "/find `query` — 🔍 Global search (IP, MAC, hostname)\n"
        "/backup — 💾 Quick backup\n"
        "/routers — 🔌 Router list\n"
        "/who — 👥 Bot users\n"
        "/quality — 📡 Connection quality test\n"
        "/add\\_router — Connect a MikroTik router\n"
        "/stop\\_logs — Stop log streaming\n"
        "/cancel — ❌ Cancel current action, return to menu\n\n"
        "*Menu Sections:*\n"
        "📊 System | 🔌 Interfaces | 🛡 Firewall\n"
        "📡 DHCP | 📶 Wireless | 🔒 VPN\n"
        "🌐 Network (Routes/DNS/IP) | 📋 Logs\n"
        "🔧 Tools | 📦 Backup | 📊 QoS/Queues\n"
        "🌉 Extras (Hotspot/Bridge/Containers)\n"
        "⚙️ Settings",
        parse_mode="Markdown",
    )


# ── Dashboard (/status) ──────────────────────────────────────────────────────

@router.message(Command("status"))
async def cmd_status(msg: Message):
    uid = msg.from_user.id
    lines = ["📊 *MikroBot Dashboard*\n"]

    # Bot info
    lines.append(f"⏱ Uptime: `{ctx.get_uptime()}`")
    lines.append(f"👥 Sessions: `{ctx.sessions.active_count()}` active / `{ctx.sessions.total_count()}` total")
    lines.append(f"👤 Users: `{len(ctx.rbac.get_all_users())}`")
    lines.append("")

    # Router status
    router_list = ctx.rm.get_router_list(uid)
    if router_list:
        lines.append("*Routers:*")
        for r in router_list:
            alias = r.get("alias", "?")
            host = r.get("host", "?")
            active = "⭐" if r.get("active") else "  "
            connected = r.get("connected", False)
            icon = "🟢" if connected else "🔴"
            lines.append(f"{active}{icon} `{alias}` ({host})")

        # Quick system info for active router
        active_r = ctx.rm.get_active(uid)
        if active_r:
            lines.append("")
            try:
                res = await active_r.get_system_resource()
                identity = await active_r.get_system_identity()
                name = identity.get("name", "?")
                cpu = res.get("cpu-load", "?")
                mem_used = int(res.get("total-memory", 0)) - int(res.get("free-memory", 0))
                mem_total = int(res.get("total-memory", 1))
                mem_pct = int(mem_used / mem_total * 100) if mem_total else 0
                uptime = res.get("uptime", "?")
                version = res.get("version", "?")

                # CPU bar
                cpu_val = int(cpu) if str(cpu).isdigit() else 0
                cpu_bar = "█" * (cpu_val // 10) + "░" * (10 - cpu_val // 10)
                mem_bar = "█" * (mem_pct // 10) + "░" * (10 - mem_pct // 10)

                lines.append(f"*Active: {name}* (ROS {version})")
                lines.append(f"CPU: `[{cpu_bar}]` {cpu}%")
                lines.append(f"RAM: `[{mem_bar}]` {mem_pct}%")
                lines.append(f"Uptime: `{uptime}`")
            except Exception:
                lines.append("_Could not fetch router stats._")
    else:
        lines.append("🔌 No routers connected.")
        lines.append("Use /add\\_router to connect.")

    await msg.answer("\n".join(lines), parse_mode="Markdown", reply_markup=kb.main_menu())


# ── Quick Ping (/ping host) ──────────────────────────────────────────────────

@router.message(Command("ping"))
async def cmd_ping(msg: Message):
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        ctx.sessions.set_state(msg.from_user.id, "tool:ping")
        await msg.answer("🏓 Enter hostname or IP to ping:", reply_markup=kb.cancel_keyboard("menu:main"))
        return

    target = parts[1].strip()
    r = await require_router(msg, ctx.rm)
    if not r:
        return
    await msg.answer(f"🏓 Pinging `{target}`…", parse_mode="Markdown")
    try:
        results = await r.ping(target, count=5)
        await msg.answer(fmt.fmt_ping(results, target), parse_mode="Markdown")
    except Exception as e:
        await msg.answer(f"❌ Ping error: `{e}`", parse_mode="Markdown")


# ── Quick Backup (/backup) ───────────────────────────────────────────────────

@router.message(Command("backup"))
async def cmd_backup(msg: Message):
    if not ctx.rbac.can(msg.from_user.id, "system.backup"):
        await msg.answer("🚫 Insufficient permissions.")
        return
    r = await require_router(msg, ctx.rm)
    if not r:
        return
    await msg.answer("💾 Creating backup…")
    try:
        filename = await r.create_backup()
        await msg.answer(f"✅ *Backup created!*\nFile: `{filename}`", parse_mode="Markdown")
    except Exception as e:
        await msg.answer(f"❌ Backup error: `{e}`", parse_mode="Markdown")


# ── Quick Router List (/routers) ─────────────────────────────────────────────

@router.message(Command("routers"))
async def cmd_routers(msg: Message):
    router_list = ctx.rm.get_router_list(msg.from_user.id)
    if not router_list:
        await msg.answer("🔌 No routers connected.\nUse /add\\_router to connect.", parse_mode="Markdown")
        return
    lines = [f"🔌 *Your Routers* ({len(router_list)})\n"]
    for r in router_list:
        alias = r.get("alias", "?")
        host = r.get("host", "?")
        active = "⭐" if r.get("active") else "  "
        connected = r.get("connected", False)
        icon = "🟢" if connected else "🔴"
        lines.append(f"{active}{icon} `{alias}` — `{host}`")
    await msg.answer("\n".join(lines), parse_mode="Markdown", reply_markup=kb.main_menu())


# ── Who's Online (/who) ──────────────────────────────────────────────────────

@router.message(Command("who"))
async def cmd_who(msg: Message):
    if not ctx.rbac.can(msg.from_user.id, "user.view"):
        await msg.answer("🚫 Insufficient permissions.")
        return
    users = ctx.rbac.get_all_users()
    lines = [f"👥 *Bot Users* ({len(users)})\n"]
    role_emoji = {"owner": "👑", "admin": "🔑", "operator": "⚙️", "viewer": "👁"}
    for u in users:
        uid = u["user_id"]
        role = u["role"]
        emoji = role_emoji.get(role, "❓")
        owner_tag = " ⭐" if u.get("is_owner") else ""
        lines.append(f"{emoji} `{uid}` — {role}{owner_tag}")
    await msg.answer("\n".join(lines), parse_mode="Markdown")


# ── Navigation callback ──────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:main")
async def menu_main(cb: CallbackQuery):
    ctx.sessions.clear_state(cb.from_user.id)
    await send_or_edit(cb, "📋 *Main Menu*", kb.main_menu())
