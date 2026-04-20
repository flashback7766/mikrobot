"""
DHCP Guard handlers — UI for DHCP starvation protection.

Menu structure (from DHCP menu → 🛡 DHCP Guard):
  • Toggle detector on/off
  • Apply / Remove firewall rate-limit rules
  • Pick preset (strict / balanced / lax)
  • Toggle auto-purge of flooder leases

Plus a quicksetup callback used right after /add_router.
"""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from core.dhcp_guard import (
    GuardSettings,
    apply_firewall_protection,
    remove_firewall_protection,
    is_firewall_applied,
)
from ui import keyboards as kb

log = logging.getLogger("DhcpGuardHandler")

router = Router()


def _active_alias(user_id: int) -> str:
    entry = ctx.rm.get_active_entry(user_id)
    return entry.alias if entry else ""


def _active_host(user_id: int) -> str:
    entry = ctx.rm.get_active_entry(user_id)
    return entry.host if entry else ""


def _status_text(
    s: GuardSettings,
    fw_on_router: bool,
    attacking: bool,
    alias: str,
    host: str,
) -> str:
    status_line = "🚨 *ATTACK IN PROGRESS*" if attacking else "🟢 Quiet"

    detector = "🟢 ON" if s.enabled else "⚪️ OFF"
    fw_setting = "🟢 ON" if s.firewall_applied else "⚪️ OFF"
    fw_actual = "🟢 installed" if fw_on_router else "🔴 not installed"
    autoblock = "🟢" if s.auto_purge_flooders else "⚪️"

    return (
        f"🛡 *DHCP Guard* — `{alias}` (`{host}`)\n\n"
        f"*Status:* {status_line}\n\n"
        f"*Detector:* {detector}\n"
        f"*Firewall (desired):* {fw_setting}\n"
        f"*Firewall (on router):* {fw_actual}\n\n"
        f"*Thresholds:*\n"
        f"  • Window: `{s.window_seconds}s`\n"
        f"  • New-lease alert: `{s.new_lease_threshold}`\n"
        f"  • Total-lease cap: `{s.total_lease_cap or 'off'}`\n\n"
        f"*Firewall rate-limit:* `{s.fw_rate_limit},{s.fw_burst}:packet`\n\n"
        f"*Auto-mitigation:*\n"
        f"  {autoblock} Purge flooder leases on attack\n"
    )


async def _ensure_context(cb: CallbackQuery) -> bool:
    """Check guard_store is wired and router is active."""
    if ctx.guard_store is None or ctx.guard_detector is None:
        await cb.answer("⚠️ DHCP Guard not initialised.", show_alert=True)
        return False
    return True


# ─── Main menu ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "dhcpg:menu")
async def dhcpg_menu(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "dhcp.guard.view"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    if not await _ensure_context(cb):
        return

    uid = cb.from_user.id
    alias = _active_alias(uid)
    host = _active_host(uid)
    if not alias:
        await send_or_edit(cb, "⚠️ No active router.", kb.dhcp_menu())
        return

    r = await require_router(cb, ctx.rm)
    if not r:
        return

    settings = ctx.guard_store.get(uid, alias)
    fw_on_router = await is_firewall_applied(r)
    attacking = ctx.guard_detector.is_attacking(uid, alias)

    await send_or_edit(
        cb,
        _status_text(settings, fw_on_router, attacking, alias, host),
        kb.dhcp_guard_menu(settings),
    )


# ─── Detector toggle ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "dhcpg:detector:toggle")
async def dhcpg_detector_toggle(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "dhcp.guard.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    if not await _ensure_context(cb):
        return
    uid = cb.from_user.id
    alias = _active_alias(uid)
    if not alias:
        await cb.answer("No router.", show_alert=True)
        return
    s = ctx.guard_store.get(uid, alias)
    new_val = not s.enabled
    await ctx.guard_store.update(uid, alias, enabled=new_val)
    ctx.guard_detector.reset(uid, alias)  # clear state on any toggle
    await cb.answer("Detector " + ("ENABLED" if new_val else "DISABLED"))
    await dhcpg_menu(cb)


# ─── Firewall apply / remove ─────────────────────────────────────────────────

@router.callback_query(F.data == "dhcpg:fw:apply")
async def dhcpg_fw_apply(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "dhcp.guard.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    if not await _ensure_context(cb):
        return
    uid = cb.from_user.id
    alias = _active_alias(uid)
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    settings = ctx.guard_store.get(uid, alias)
    ok, msg = await apply_firewall_protection(r, settings)
    if ok:
        await ctx.guard_store.update(uid, alias, firewall_applied=True)
    await cb.answer(msg, show_alert=True)
    await dhcpg_menu(cb)


@router.callback_query(F.data == "dhcpg:fw:remove")
async def dhcpg_fw_remove(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "dhcp.guard.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    if not await _ensure_context(cb):
        return
    uid = cb.from_user.id
    alias = _active_alias(uid)
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    ok, msg = await remove_firewall_protection(r)
    if ok:
        await ctx.guard_store.update(uid, alias, firewall_applied=False)
    await cb.answer(msg, show_alert=True)
    await dhcpg_menu(cb)


# ─── Auto-purge toggle ───────────────────────────────────────────────────────

@router.callback_query(F.data == "dhcpg:autopurge:toggle")
async def dhcpg_autopurge_toggle(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "dhcp.guard.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    if not await _ensure_context(cb):
        return
    uid = cb.from_user.id
    alias = _active_alias(uid)
    s = ctx.guard_store.get(uid, alias)
    await ctx.guard_store.update(uid, alias, auto_purge_flooders=not s.auto_purge_flooders)
    await cb.answer("Toggled")
    await dhcpg_menu(cb)


# ─── Threshold presets ───────────────────────────────────────────────────────

@router.callback_query(F.data == "dhcpg:thresholds")
async def dhcpg_thresholds_menu(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "dhcp.guard.view"):
        await cb.answer("🚫", show_alert=True)
        return
    await send_or_edit(
        cb,
        "⚙️ *DHCP Guard — Thresholds*\n\n"
        "Pick a preset. `new_leases/window_seconds` is the alert trigger. "
        "Firewall rate is `packets/sec,burst`.\n\n"
        "  • *Strict*: small network, few devices\n"
        "  • *Balanced*: typical home/office network\n"
        "  • *Lax*: guest WiFi / large network\n",
        kb.dhcp_guard_thresholds(),
    )


@router.callback_query(F.data.startswith("dhcpg:preset:"))
async def dhcpg_preset(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "dhcp.guard.manage"):
        await cb.answer("🚫", show_alert=True)
        return
    if not await _ensure_context(cb):
        return
    preset = cb.data.split(":", 2)[2]
    uid = cb.from_user.id
    alias = _active_alias(uid)
    if not alias:
        await cb.answer("No router.", show_alert=True)
        return

    presets = {
        "strict":   dict(window_seconds=60,  new_lease_threshold=10, fw_rate_limit=20,  fw_burst=50),
        "balanced": dict(window_seconds=60,  new_lease_threshold=20, fw_rate_limit=50,  fw_burst=100),
        "lax":      dict(window_seconds=120, new_lease_threshold=50, fw_rate_limit=100, fw_burst=200),
    }
    if preset not in presets:
        await cb.answer("Unknown preset", show_alert=True)
        return
    await ctx.guard_store.update(uid, alias, **presets[preset])
    await cb.answer(f"Preset '{preset}' applied")
    await dhcpg_menu(cb)


# ─── Quick-setup (called right after /add_router) ────────────────────────────

@router.callback_query(F.data == "dhcpg:quicksetup")
async def dhcpg_quicksetup(cb: CallbackQuery):
    """Enable detector + try to install firewall rules with balanced preset."""
    if not ctx.rbac.can(cb.from_user.id, "dhcp.guard.manage"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    if not await _ensure_context(cb):
        return
    uid = cb.from_user.id
    alias = _active_alias(uid)
    if not alias:
        await cb.answer("No router.", show_alert=True)
        return

    # Balanced preset + enable detector
    await ctx.guard_store.update(
        uid, alias,
        enabled=True,
        window_seconds=60, new_lease_threshold=20,
        fw_rate_limit=50, fw_burst=100,
    )

    r = await require_router(cb, ctx.rm)
    if not r:
        await cb.answer("Router unavailable.", show_alert=True)
        return

    settings = ctx.guard_store.get(uid, alias)
    ok, fw_msg = await apply_firewall_protection(r, settings)
    if ok:
        await ctx.guard_store.update(uid, alias, firewall_applied=True)

    await send_or_edit(
        cb,
        "🛡 *DHCP Guard enabled*\n\n"
        f"• Detector: 🟢 ON — alerts land in this chat\n"
        f"• Firewall: {fw_msg}\n\n"
        "Fine-tune in *DHCP → 🛡 DHCP Guard*.",
        kb.main_menu(),
    )
