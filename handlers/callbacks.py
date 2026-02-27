"""
Main callback router – dispatches all callback_data to the right handler.

Callback data convention:
  menu:<section>        – navigate to menu
  sys:<action>          – system actions
  iface:<action>:<name> – interface actions
  fw:<action>           – firewall actions
  dhcp:<action>         – DHCP actions
  wifi:<action>         – wireless actions
  vpn:<action>          – VPN actions
  file:<action>         – file actions
  log:<action>          – log actions
  route:<action>        – route actions
  dns:<action>          – DNS actions
  tool:<action>         – tools
  backup:<action>       – backup
  router:<action>       – router management
  admin:<action>        – RBAC admin
  settings:<action>     – settings
  lang:<code>           – language select
  wg:<action>           – WireGuard (ROS7)
  container:<action>    – Docker containers (ROS7)
"""

import asyncio
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, Document
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from aiogram.filters import Command

from core.rbac import RBACManager, Role
from core.session import SessionManager
from core.router_manager import RouterManager
from core.monitor import Monitor
from core.log_streamer import stream_logs_to_chat
from core.router_ros7 import RouterROS7

from ui import keyboards as kb
from ui import formatters as fmt
from handlers.base import send_or_edit, check_auth, require_router

log = logging.getLogger("Handlers")

router = Router()

# ─── Shared Context (injected at startup) ────────────────────────────────────

_rm: RouterManager = None
_rbac: RBACManager = None
_sessions: SessionManager = None
_bot = None


def setup(rm: RouterManager, rbac: RBACManager, sessions: SessionManager, bot):
    global _rm, _rbac, _sessions, _bot
    _rm = rm
    _rbac = rbac
    _sessions = sessions
    _bot = bot


# ─── Permission check shortcut ────────────────────────────────────────────────

async def _perm(cb: CallbackQuery, perm: str) -> bool:
    if not _rbac.can(cb.from_user.id, perm):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return False
    return True


# ─── Commands ────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(msg: Message):
    if not await check_auth(msg, _rbac):
        return
    await msg.answer(
        "🖥 *MikroBot — WinBox in Telegram*\n\n"
        "Full RouterOS management from your phone.\n"
        "Use /add\\_router to connect your first MikroTik device,\n"
        "or tap the menu below.",
        parse_mode="Markdown",
        reply_markup=kb.main_menu(),
    )


@router.message(Command("menu"))
async def cmd_menu(msg: Message):
    if not await check_auth(msg, _rbac):
        return
    await msg.answer("📋 Main Menu", reply_markup=kb.main_menu())


@router.message(Command("add_router"))
async def cmd_add_router(msg: Message):
    if not await check_auth(msg, _rbac, "router.add"):
        return
    _sessions.set_state(msg.from_user.id, "add_router:alias")
    await msg.answer(
        "➕ *Add Router*\n\nStep 1/5: Enter a name (alias) for this router:\n"
        "Example: `home`, `office`, `vps`",
        parse_mode="Markdown",
        reply_markup=kb.cancel_keyboard("menu:main"),
    )


@router.message(Command("stop_logs"))
async def cmd_stop_logs(msg: Message):
    if not await check_auth(msg, _rbac):
        return
    await _sessions.stop_log_stream(msg.from_user.id)
    await msg.answer("🔴 Log stream stopped.")


@router.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "🖥 *MikroBot Help*\n\n"
        "/start — Main menu\n"
        "/add\\_router — Connect a MikroTik router\n"
        "/stop\\_logs — Stop log streaming\n"
        "/menu — Show main menu\n\n"
        "*Available sections:*\n"
        "📊 System | 🔌 Interfaces | 🛡 Firewall\n"
        "📡 DHCP | 📶 Wireless | 🔒 VPN\n"
        "📁 Files | 📋 Logs | 🗺 Routes\n"
        "🌐 DNS | 🔧 Tools | 📦 Backup",
        parse_mode="Markdown",
    )


# ─── FSM Text Input Handler ───────────────────────────────────────────────────

@router.message(F.text)
async def handle_text(msg: Message):
    uid = msg.from_user.id
    if not _sessions:
        return
    state = _sessions.get_state(uid)
    if state == "idle" or not state:
        return
    await _handle_fsm(msg, uid, state, msg.text.strip())


async def _handle_fsm(msg: Message, uid: int, state: str, text: str):
    data = _sessions.get_data(uid)

    # ── Add Router FSM ──────────────────────────────────────────────────────
    if state == "add_router:alias":
        _sessions.update_data(uid, alias=text)
        _sessions.set_state(uid, "add_router:host")
        await msg.answer("Step 2/5: Enter router IP address:\nExample: `192.168.88.1`", parse_mode="Markdown")

    elif state == "add_router:host":
        _sessions.update_data(uid, host=text)
        _sessions.set_state(uid, "add_router:user")
        await msg.answer("Step 3/5: Enter username:\nExample: `admin`", parse_mode="Markdown")

    elif state == "add_router:user":
        _sessions.update_data(uid, username=text)
        _sessions.set_state(uid, "add_router:pass")
        await msg.answer("Step 4/5: Enter password (send `-` for empty password):", parse_mode="Markdown")

    elif state == "add_router:pass":
        password = "" if text == "-" else text
        _sessions.update_data(uid, password=password)
        _sessions.set_state(uid, "add_router:port")
        await msg.answer(
            "Step 5/5: Enter API port (default: `8728`, SSL: `8729`, or send `-` for default):",
            parse_mode="Markdown",
        )

    elif state == "add_router:port":
        d = _sessions.get_data(uid)
        port = 8728
        use_ssl = False
        if text != "-":
            try:
                port = int(text)
                use_ssl = port == 8729
            except ValueError:
                pass
        await msg.answer("⏳ Connecting to router… please wait.", parse_mode="Markdown")
        ok, result = await _rm.add_router(
            user_id=uid,
            alias=d["alias"],
            host=d["host"],
            username=d["username"],
            password=d["password"],
            port=port,
            use_ssl=use_ssl,
        )
        _sessions.clear_state(uid)
        await msg.answer(result, parse_mode="Markdown", reply_markup=kb.main_menu())

    # ── Firewall Add Rule FSM ───────────────────────────────────────────────
    elif state == "fw:add:src_ip":
        _sessions.update_data(uid, src_address=text if text != "-" else "")
        _sessions.set_state(uid, "fw:add:dst_ip")
        await msg.answer("Destination IP/subnet (or `-` to skip):", parse_mode="Markdown")

    elif state == "fw:add:dst_ip":
        _sessions.update_data(uid, dst_address=text if text != "-" else "")
        _sessions.set_state(uid, "fw:add:dst_port")
        await msg.answer("Destination port (or `-` to skip, e.g. `80`, `80-90`, `80,443`):", parse_mode="Markdown")

    elif state == "fw:add:dst_port":
        _sessions.update_data(uid, dst_port=text if text != "-" else "")
        _sessions.set_state(uid, "fw:add:comment")
        await msg.answer("Comment for this rule (or `-` to skip):", parse_mode="Markdown")

    elif state == "fw:add:comment":
        d = _sessions.get_data(uid)
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        params = {
            "chain": d.get("chain", "forward"),
            "action": d.get("action", "drop"),
        }
        if d.get("protocol") and d["protocol"] != "any":
            params["protocol"] = d["protocol"]
        if d.get("src_address"):
            params["src-address"] = d["src_address"]
        if d.get("dst_address"):
            params["dst-address"] = d["dst_address"]
        if d.get("dst_port"):
            params["dst-port"] = d["dst_port"]
        if text != "-":
            params["comment"] = text
        try:
            rule_id = await router.add_firewall_filter(params)
            await msg.answer(f"✅ Firewall rule added! ID: `{rule_id}`", parse_mode="Markdown",
                             reply_markup=kb.firewall_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}", reply_markup=kb.firewall_menu())

    # ── Quick Block IP ──────────────────────────────────────────────────────
    elif state == "fw:block_ip":
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            id_ = await router.add_address_list_entry(text, "blacklist", "Blocked via Telegram")
            # Also add drop rule for blacklist
            try:
                await router.add_firewall_filter({
                    "chain": "forward",
                    "src-address-list": "blacklist",
                    "action": "drop",
                    "comment": "Drop blacklist (auto)",
                })
            except Exception:
                pass
            await msg.answer(f"🚫 `{text}` added to blacklist (ID: {id_})", parse_mode="Markdown",
                             reply_markup=kb.firewall_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}", reply_markup=kb.firewall_menu())

    # ── DHCP Add Static Lease FSM ───────────────────────────────────────────
    elif state == "dhcp:add:mac":
        _sessions.update_data(uid, mac=text)
        _sessions.set_state(uid, "dhcp:add:ip")
        await msg.answer("IP address for this lease:\nExample: `192.168.88.50`", parse_mode="Markdown")

    elif state == "dhcp:add:ip":
        _sessions.update_data(uid, ip=text)
        _sessions.set_state(uid, "dhcp:add:comment")
        await msg.answer("Comment/hostname (or `-` to skip):", parse_mode="Markdown")

    elif state == "dhcp:add:comment":
        d = _sessions.get_data(uid)
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            id_ = await router.add_dhcp_static_lease(d["mac"], d["ip"], text if text != "-" else "")
            await msg.answer(f"✅ Static lease added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.dhcp_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}", reply_markup=kb.dhcp_menu())

    # ── Wireless SSID Change ────────────────────────────────────────────────
    elif state.startswith("wifi:set_ssid:"):
        iface_name = state.split(":", 2)[2]
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            await router.set_wireless_ssid(iface_name, text)
            await msg.answer(f"✅ SSID changed to `{text}`", parse_mode="Markdown",
                             reply_markup=kb.wireless_iface_menu(iface_name, False))
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    elif state.startswith("wifi:set_pass:"):
        iface_name = state.split(":", 2)[2]
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            await router.set_wireless_password(iface_name, text)
            await msg.answer(f"✅ WiFi password updated.", reply_markup=kb.wireless_iface_menu(iface_name, False))
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── VPN Add Secret ──────────────────────────────────────────────────────
    elif state == "vpn:add:name":
        _sessions.update_data(uid, vpn_name=text)
        _sessions.set_state(uid, "vpn:add:pass")
        await msg.answer("Password for this VPN user:", parse_mode="Markdown")

    elif state == "vpn:add:pass":
        d = _sessions.get_data(uid)
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            id_ = await router.add_vpn_secret(d["vpn_name"], text)
            await msg.answer(f"✅ VPN user `{d['vpn_name']}` added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.vpn_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}", reply_markup=kb.vpn_menu())

    # ── Add Route FSM ───────────────────────────────────────────────────────
    elif state == "route:add:dst":
        _sessions.update_data(uid, dst=text)
        _sessions.set_state(uid, "route:add:gw")
        await msg.answer("Gateway IP or interface name:\nExample: `10.0.0.1` or `ether1`", parse_mode="Markdown")

    elif state == "route:add:gw":
        d = _sessions.get_data(uid)
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            id_ = await router.add_route(d["dst"], text)
            await msg.answer(f"✅ Route `{d['dst']} → {text}` added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.main_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── DNS Set Servers ─────────────────────────────────────────────────────
    elif state == "dns:set_servers":
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        servers = [s.strip() for s in text.replace(",", " ").split()]
        try:
            await router.set_dns_servers(servers)
            await msg.answer(f"✅ DNS servers updated: `{', '.join(servers)}`", parse_mode="Markdown",
                             reply_markup=kb.dns_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── Ping Tool ───────────────────────────────────────────────────────────
    elif state == "tool:ping":
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        await msg.answer(f"🏓 Pinging `{text}`…", parse_mode="Markdown")
        try:
            results = await router.ping(text, count=5)
            await msg.answer(fmt.fmt_ping(results, text), parse_mode="Markdown",
                             reply_markup=kb.tools_menu())
        except Exception as e:
            await msg.answer(f"❌ Ping error: {e}", reply_markup=kb.tools_menu())

    # ── Traceroute ──────────────────────────────────────────────────────────
    elif state == "tool:traceroute":
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        await msg.answer(f"🗺 Tracing route to `{text}`…", parse_mode="Markdown")
        try:
            hops = await router.traceroute(text)
            await msg.answer(fmt.fmt_traceroute(hops, text), parse_mode="Markdown",
                             reply_markup=kb.tools_menu())
        except Exception as e:
            await msg.answer(f"❌ Traceroute error: {e}", reply_markup=kb.tools_menu())

    # ── Bandwidth Test ──────────────────────────────────────────────────────
    elif state == "tool:bwtest":
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        await msg.answer(f"📊 Running bandwidth test to `{text}`… (5 sec)", parse_mode="Markdown")
        try:
            result = await router.bandwidth_test(text, duration=5)
            await msg.answer(fmt.fmt_bandwidth_test(result, text), parse_mode="Markdown",
                             reply_markup=kb.tools_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}", reply_markup=kb.tools_menu())

    # ── Add Bot User ────────────────────────────────────────────────────────
    elif state == "admin:add_user":
        _sessions.clear_state(uid)
        try:
            new_uid = int(text)
            await _rbac.set_role(new_uid, Role.VIEWER)
            await msg.answer(
                f"✅ User `{new_uid}` added with role `viewer`.\n"
                "Use the admin panel to change their role.",
                parse_mode="Markdown",
                reply_markup=kb.settings_menu(),
            )
        except ValueError:
            await msg.answer("❌ Invalid Telegram user ID (must be a number).")

    # ── Address List Add ────────────────────────────────────────────────────
    elif state.startswith("fw:addrlist:add:"):
        list_name = state.split(":", 3)[3]
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            id_ = await router.add_address_list_entry(text, list_name, "Added via Telegram")
            await msg.answer(f"✅ `{text}` added to `{list_name}` (ID: {id_})", parse_mode="Markdown",
                             reply_markup=kb.firewall_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── IP Address Add ──────────────────────────────────────────────────────
    elif state.startswith("ip:add:"):
        iface = state.split(":", 2)[2]
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            id_ = await router.add_ip_address(text, iface)
            await msg.answer(f"✅ IP `{text}` added to `{iface}` (ID: {id_})", parse_mode="Markdown")
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── IP Address Add (two-step) ───────────────────────────────────────────
    elif state == "ip:add_addr":
        _sessions.update_data(uid, ip_address=text)
        _sessions.set_state(uid, "ip:add_addr:iface")
        await msg.answer("Interface name:\nExample: `ether1`, `bridge1`", parse_mode="Markdown")

    elif state == "ip:add_addr:iface":
        d = _sessions.get_data(uid)
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            id_ = await router.add_ip_address(d["ip_address"], text)
            await msg.answer(f"✅ IP `{d['ip_address']}` added to `{text}`! ID: `{id_}`",
                             parse_mode="Markdown", reply_markup=kb.ip_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── Mangle Add (quick format) ────────────────────────────────────────
    elif state == "mangle:add":
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        words = text.strip().split()
        if len(words) < 2:
            await msg.answer("❌ Format: `chain action [src-address] [comment]`", parse_mode="Markdown")
            return
        params = {"chain": words[0], "action": words[1]}
        if len(words) > 2:
            params["src-address"] = words[2]
        if len(words) > 3:
            params["comment"] = " ".join(words[3:])
        try:
            id_ = await router.add_firewall_mangle(params)
            await msg.answer(f"✅ Mangle rule added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.firewall_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── IP Pool Add ─────────────────────────────────────────────────────────
    elif state == "ip:pool:add:name":
        _sessions.update_data(uid, pool_name=text)
        _sessions.set_state(uid, "ip:pool:add:ranges")
        await msg.answer("Range(s) for this pool:\nExample: `192.168.100.10-192.168.100.200`",
                         parse_mode="Markdown")

    elif state == "ip:pool:add:ranges":
        d = _sessions.get_data(uid)
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            id_ = await router.add_ip_pool(d["pool_name"], text)
            await msg.answer(f"✅ Pool `{d['pool_name']}` created! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.ip_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── Queue Add ───────────────────────────────────────────────────────────
    elif state == "queue:add:name":
        _sessions.update_data(uid, q_name=text)
        _sessions.set_state(uid, "queue:add:target")
        await msg.answer("Target (IP or subnet):\nExample: `192.168.88.100` or `192.168.88.0/24`",
                         parse_mode="Markdown")

    elif state == "queue:add:target":
        _sessions.update_data(uid, q_target=text)
        _sessions.set_state(uid, "queue:add:limit")
        await msg.answer("Max limit (down/up):\nExample: `10M/5M` or `0/0` for unlimited",
                         parse_mode="Markdown")

    elif state == "queue:add:limit":
        d = _sessions.get_data(uid)
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            id_ = await router.add_simple_queue(d["q_name"], d["q_target"], text)
            await msg.answer(f"✅ Queue `{d['q_name']}` added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.queues_menu([]))
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── Hotspot User Add ────────────────────────────────────────────────────
    elif state == "hotspot:add:name":
        _sessions.update_data(uid, hs_name=text)
        _sessions.set_state(uid, "hotspot:add:pass")
        await msg.answer("Password for this hotspot user:", parse_mode="Markdown")

    elif state == "hotspot:add:pass":
        d = _sessions.get_data(uid)
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            id_ = await router.add_hotspot_user(d["hs_name"], text)
            await msg.answer(f"✅ Hotspot user `{d['hs_name']}` added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.hotspot_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── VLAN Add ────────────────────────────────────────────────────────────
    elif state == "vlan:add:name":
        _sessions.update_data(uid, vlan_name=text)
        _sessions.set_state(uid, "vlan:add:id")
        await msg.answer("VLAN ID (1-4094):", parse_mode="Markdown")

    elif state == "vlan:add:id":
        _sessions.update_data(uid, vlan_id=text)
        _sessions.set_state(uid, "vlan:add:iface")
        await msg.answer("Parent interface:\nExample: `ether1`, `bridge1`", parse_mode="Markdown")

    elif state == "vlan:add:iface":
        d = _sessions.get_data(uid)
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            id_ = await router.add_vlan(d["vlan_name"], int(d["vlan_id"]), text)
            await msg.answer(f"✅ VLAN `{d['vlan_id']}` ({d['vlan_name']}) created! ID: `{id_}`",
                             parse_mode="Markdown", reply_markup=kb.ip_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── NAT Add Rule FSM ────────────────────────────────────────────────────
    elif state == "nat:add:src_addr":
        _sessions.update_data(uid, nat_src=text if text != "-" else "")
        _sessions.set_state(uid, "nat:add:dst_port")
        await msg.answer("Destination port (or `-` to skip):\nExample: `80`, `443`", parse_mode="Markdown")

    elif state == "nat:add:dst_port":
        _sessions.update_data(uid, nat_dst_port=text if text != "-" else "")
        _sessions.set_state(uid, "nat:add:to_addr")
        await msg.answer("To-address (or `-` to skip):\nExample: `192.168.88.10`", parse_mode="Markdown")

    elif state == "nat:add:to_addr":
        _sessions.update_data(uid, nat_to_addr=text if text != "-" else "")
        _sessions.set_state(uid, "nat:add:to_port")
        await msg.answer("To-ports (or `-` to skip):\nExample: `8080`", parse_mode="Markdown")

    elif state == "nat:add:to_port":
        d = _sessions.get_data(uid)
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        params = {
            "chain": d.get("nat_chain", "dstnat"),
            "action": d.get("nat_action", "dst-nat"),
        }
        if d.get("nat_src"):
            params["src-address"] = d["nat_src"]
        if d.get("nat_dst_port"):
            params["dst-port"] = d["nat_dst_port"]
            params["protocol"] = "tcp"
        if d.get("nat_to_addr"):
            params["to-addresses"] = d["nat_to_addr"]
        if text != "-":
            params["to-ports"] = text
        try:
            id_ = await router.add_firewall_nat(params)
            await msg.answer(f"✅ NAT rule added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.firewall_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}", reply_markup=kb.firewall_menu())

    # ── NTP Set Servers ─────────────────────────────────────────────────────
    elif state == "ntp:set_servers":
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        parts_ntp = text.replace(",", " ").split()
        primary = parts_ntp[0] if parts_ntp else "pool.ntp.org"
        secondary = parts_ntp[1] if len(parts_ntp) > 1 else ""
        try:
            await router.set_ntp_servers(primary, secondary)
            await msg.answer(f"✅ NTP servers updated: `{primary}`" +
                             (f", `{secondary}`" if secondary else ""),
                             parse_mode="Markdown", reply_markup=kb.ntp_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── WireGuard Add Peer ──────────────────────────────────────────────────
    elif state.startswith("wg:add_peer:pubkey:"):
        iface = state.split(":", 3)[3]
        _sessions.update_data(uid, wg_iface=iface, wg_pubkey=text)
        _sessions.set_state(uid, "wg:add_peer:allowed_addr")
        await msg.answer("Allowed address(es):\nExample: `10.0.0.2/32`", parse_mode="Markdown")

    elif state == "wg:add_peer:allowed_addr":
        d = _sessions.get_data(uid)
        _sessions.update_data(uid, wg_allowed=text)
        _sessions.set_state(uid, "wg:add_peer:endpoint")
        await msg.answer("Endpoint host:port (or `-` to skip):\nExample: `1.2.3.4:51820`",
                         parse_mode="Markdown")

    elif state == "wg:add_peer:endpoint":
        d = _sessions.get_data(uid)
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        endpoint = ""
        endpoint_port = 0
        if text != "-" and ":" in text:
            ep_parts = text.rsplit(":", 1)
            endpoint = ep_parts[0]
            try:
                endpoint_port = int(ep_parts[1])
            except ValueError:
                pass
        try:
            id_ = await router.add_wireguard_peer(
                d["wg_iface"], d["wg_pubkey"], d["wg_allowed"],
                endpoint=endpoint, endpoint_port=endpoint_port,
            )
            await msg.answer(f"✅ WireGuard peer added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.vpn_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── Router User Add ─────────────────────────────────────────────────────
    elif state == "sys:add_user:name":
        _sessions.update_data(uid, r_user=text)
        _sessions.set_state(uid, "sys:add_user:pass")
        await msg.answer("Password for this router user:", parse_mode="Markdown")

    elif state == "sys:add_user:pass":
        d = _sessions.get_data(uid)
        _sessions.clear_state(uid)
        router = await require_router(msg, _rm)
        if not router:
            return
        try:
            id_ = await router.add_user(d["r_user"], text, "read")
            await msg.answer(f"✅ Router user `{d['r_user']}` added (read group). ID: `{id_}`",
                             parse_mode="Markdown", reply_markup=kb.system_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    else:
        _sessions.clear_state(uid)


# ─── Callback Handlers ────────────────────────────────────────────────────────

@router.callback_query()
async def handle_callback(cb: CallbackQuery):
    uid = cb.from_user.id
    if not await check_auth(cb, _rbac):
        return

    data = cb.data
    parts = data.split(":")

    # ── Language ─────────────────────────────────────────────────────────
    if data.startswith("lang:"):
        lang = parts[1]
        _sessions.set_language(uid, lang)
        await cb.answer(f"Language set!")
        await send_or_edit(cb, "📋 Main Menu", kb.main_menu())

    # ── Main Menu ─────────────────────────────────────────────────────────
    elif data == "menu:main":
        _sessions.clear_state(uid)
        await send_or_edit(cb, "📋 *Main Menu*", kb.main_menu())

    # ── System ────────────────────────────────────────────────────────────
    elif data in ("menu:system", "sys:refresh"):
        router = await require_router(cb, _rm)
        if not router:
            return
        res = await router.get_system_resource()
        identity = await router.get_system_identity()
        health = await router.get_system_health()
        text = fmt.fmt_system(res, identity, health)
        await send_or_edit(cb, text, kb.system_menu())

    elif data == "sys:health":
        router = await require_router(cb, _rm)
        if not router:
            return
        health = await router.get_system_health()
        if not health:
            await cb.answer("No health data available on this device.", show_alert=True)
            return
        lines = ["🌡 *System Health*\n"]
        for k, v in health.items():
            lines.append(f"• {k}: `{v}`")
        await send_or_edit(cb, "\n".join(lines), kb.system_menu())

    elif data == "sys:routerboard":
        router = await require_router(cb, _rm)
        if not router:
            return
        rb = await router.get_system_routerboard()
        await send_or_edit(cb, fmt.fmt_routerboard(rb), kb.system_menu())

    elif data == "sys:reboot":
        if not _rbac.can(uid, "system.reboot"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        await send_or_edit(cb, "⚠️ *Confirm Reboot?*\nThis will disconnect all clients!", kb.reboot_confirm())

    elif data == "sys:reboot_confirm":
        if not _rbac.can(uid, "system.reboot"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await cb.answer("🔁 Rebooting…")
        await router.reboot()
        await cb.message.edit_text("🔁 *Reboot command sent.*\nRouter will be back in ~30 seconds.", parse_mode="Markdown")

    elif data == "sys:users":
        if not _rbac.can(uid, "user.view"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        users = await router.get_users()
        await send_or_edit(cb, fmt.fmt_router_users(users), kb.system_menu())

    elif data == "sys:scheduler":
        router = await require_router(cb, _rm)
        if not router:
            return
        if isinstance(router, RouterROS7):
            entries = await router.get_scheduler_entries()
            if not entries:
                await cb.answer("No scheduled tasks.", show_alert=True)
                return
            lines = ["📅 *Scheduler*\n"]
            for e in entries:
                name = e.get("name", "?")
                interval = e.get("interval", e.get("on-event", "?"))
                disabled = e.get("disabled", "false") == "true"
                icon = "⏸" if disabled else "▶️"
                lines.append(f"{icon} `{name}` — {interval}")
            await send_or_edit(cb, "\n".join(lines), kb.system_menu())
        else:
            await cb.answer("Scheduler not available on this router type.", show_alert=True)

    # ── Interfaces ────────────────────────────────────────────────────────
    elif data == "menu:interfaces":
        router = await require_router(cb, _rm)
        if not router:
            return
        ifaces = await router.get_interfaces()
        text = fmt.fmt_interfaces(ifaces)
        await send_or_edit(cb, text, kb.interfaces_menu(ifaces))

    elif data.startswith("iface:detail:"):
        name = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        ifaces = await router.get_interfaces()
        iface = next((i for i in ifaces if i.get("name") == name), {})
        if not iface:
            await cb.answer("Interface not found.", show_alert=True)
            return
        running = iface.get("running", "false") == "true"
        disabled = iface.get("disabled", "false") == "true"
        text = fmt.fmt_interface_detail(iface)
        await send_or_edit(cb, text, kb.interface_detail_menu(name, running, disabled))

    elif data.startswith("iface:traffic:"):
        name = parts[2]
        if not _rbac.can(uid, "interface.monitor"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await cb.answer("📊 Sampling traffic…")
        t = await router.get_interface_traffic(name)
        text = fmt.fmt_traffic(t)
        ifaces = await router.get_interfaces()
        iface = next((i for i in ifaces if i.get("name") == name), {"disabled": "false", "running": "true"})
        await send_or_edit(cb, text, kb.interface_detail_menu(
            name,
            iface.get("running", "true") == "true",
            iface.get("disabled", "false") == "true",
        ))

    elif data.startswith("iface:enable:") or data.startswith("iface:disable:"):
        action, name = parts[0], parts[2]
        if not _rbac.can(uid, "interface.toggle"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        if "enable" in action:
            await router.enable_interface(name)
            await cb.answer(f"✅ {name} enabled")
        else:
            await router.disable_interface(name)
            await cb.answer(f"⛔ {name} disabled")
        # Refresh
        ifaces = await router.get_interfaces()
        await send_or_edit(cb, fmt.fmt_interfaces(ifaces), kb.interfaces_menu(ifaces))

    # ── Firewall ──────────────────────────────────────────────────────────
    elif data == "menu:firewall":
        if not _rbac.can(uid, "firewall.view"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        await send_or_edit(cb, "🛡 *Firewall Manager*", kb.firewall_menu())

    elif data == "fw:filter":
        router = await require_router(cb, _rm)
        if not router:
            return
        rules = await router.get_firewall_filter()
        page = _sessions.get_page(uid)
        text = f"🛡 *Firewall Filter Rules* ({len(rules)} total)"
        await send_or_edit(cb, text, kb.firewall_rule_list(rules, page))

    elif data.startswith("fw:filter:page:"):
        page = int(parts[3])
        _sessions.set_page(uid, page)
        router = await require_router(cb, _rm)
        if not router:
            return
        rules = await router.get_firewall_filter()
        await send_or_edit(cb, f"🛡 *Filter Rules* ({len(rules)} total)", kb.firewall_rule_list(rules, page))

    elif data.startswith("fw:rule:"):
        rule_id = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        rules = await router.get_firewall_filter()
        rule = next((r for r in rules if r.get(".id") == rule_id), None)
        if not rule:
            await cb.answer("Rule not found.", show_alert=True)
            return
        text = fmt.fmt_firewall_rule(rule)
        disabled = rule.get("disabled", "false") == "true"
        await send_or_edit(cb, text, kb.firewall_rule_detail(rule_id, disabled))

    elif data.startswith("fw:enable:") or data.startswith("fw:disable:"):
        rule_id = parts[2]
        if not _rbac.can(uid, "firewall.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        if "enable" in data:
            await router.enable_firewall_rule(rule_id)
            await cb.answer("✅ Rule enabled")
        else:
            await router.disable_firewall_rule(rule_id)
            await cb.answer("⛔ Rule disabled")
        rules = await router.get_firewall_filter()
        await send_or_edit(cb, f"🛡 *Filter Rules* ({len(rules)} total)", kb.firewall_rule_list(rules, 0))

    elif data.startswith("fw:remove:"):
        rule_id = parts[2]
        if not _rbac.can(uid, "firewall.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_firewall_rule(rule_id)
        await cb.answer("🗑 Rule removed")
        rules = await router.get_firewall_filter()
        await send_or_edit(cb, f"🛡 *Filter Rules* ({len(rules)} total)", kb.firewall_rule_list(rules, 0))

    elif data.startswith("fw:move_up:") or data.startswith("fw:move_down:"):
        rule_id = parts[2]
        if not _rbac.can(uid, "firewall.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        rules = await router.get_firewall_filter()
        ids = [r.get(".id") for r in rules]
        try:
            idx = ids.index(rule_id)
        except ValueError:
            await cb.answer("Rule not found.", show_alert=True)
            return
        if "up" in data:
            dest = max(0, idx - 1)
        else:
            dest = min(len(rules) - 1, idx + 1)
        await router.move_firewall_rule(rule_id, dest)
        await cb.answer(f"Moved to position {dest}")
        rules = await router.get_firewall_filter()
        await send_or_edit(cb, f"🛡 *Filter Rules* ({len(rules)} total)", kb.firewall_rule_list(rules, 0))

    elif data == "fw:nat":
        router = await require_router(cb, _rm)
        if not router:
            return
        rules = await router.get_firewall_nat()
        lines = [f"🔀 *NAT Rules* ({len(rules)} total)\n"]
        for r in rules:
            lines.append(fmt.fmt_nat_rule(r))
            lines.append("—" * 20)
        await send_or_edit(cb, "\n".join(lines)[:4096], kb.firewall_menu())

    elif data == "fw:connections":
        router = await require_router(cb, _rm)
        if not router:
            return
        conns = await router.get_connection_tracking()
        lines = [f"🔗 *Active Connections* ({len(conns)})\n"]
        for c in conns[:15]:
            src = c.get("src-address", "?")
            dst = c.get("dst-address", "?")
            proto = c.get("protocol", "?")
            state = c.get("state", "?")
            lines.append(f"`{src}` → `{dst}` [{proto}/{state}]")
        await send_or_edit(cb, "\n".join(lines), kb.firewall_menu())

    elif data == "fw:addrlist":
        router = await require_router(cb, _rm)
        if not router:
            return
        entries = await router.get_address_list()
        list_names = list(dict.fromkeys(e.get("list", "") for e in entries))
        text = fmt.fmt_address_list(entries)
        await send_or_edit(cb, text, kb.address_list_menu(list_names))

    elif data.startswith("fw:addrlist:view:"):
        list_name = parts[3]
        router = await require_router(cb, _rm)
        if not router:
            return
        entries = await router.get_address_list(list_name)
        text = fmt.fmt_address_list(entries)
        # Add entry button
        builder_kb = kb.confirm_keyboard(f"fw:addrlist:add_prompt:{list_name}", "fw:addrlist")
        await send_or_edit(cb, text or f"📋 *{list_name}* — empty", builder_kb)

    elif data.startswith("fw:addrlist:add_prompt:"):
        list_name = parts[3]
        _sessions.set_state(uid, f"fw:addrlist:add:{list_name}")
        await send_or_edit(cb, f"Enter IP/subnet to add to `{list_name}`:", kb.cancel_keyboard("fw:addrlist"))

    elif data == "fw:addrlist:add":
        _sessions.set_state(uid, "fw:addrlist:add_choose_list")
        await send_or_edit(cb, "Enter `list_name:ip_address` format:\nExample: `blacklist:1.2.3.4`",
                           kb.cancel_keyboard("fw:addrlist"))

    elif data == "fw:add_rule":
        if not _rbac.can(uid, "firewall.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        await send_or_edit(cb, "🛡 *Add Firewall Rule*\n\nStep 1: Select chain:", kb.fw_add_rule_chain())

    elif data.startswith("fw:add:chain:"):
        _sessions.set_state(uid, "fw:add_rule")
        _sessions.update_data(uid, chain=parts[3])
        await send_or_edit(cb, "Step 2: Select action:", kb.fw_add_rule_action())

    elif data.startswith("fw:add:action:"):
        _sessions.update_data(uid, action=parts[3])
        await send_or_edit(cb, "Step 3: Select protocol:", kb.fw_add_rule_protocol())

    elif data.startswith("fw:add:proto:"):
        _sessions.update_data(uid, protocol=parts[3])
        _sessions.set_state(uid, "fw:add:src_ip")
        await send_or_edit(cb, "Step 4: Enter source IP/subnet (or `-` to skip):", kb.cancel_keyboard("fw:filter"))

    elif data == "fw:block_ip":
        if not _rbac.can(uid, "firewall.address_list.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        _sessions.set_state(uid, "fw:block_ip")
        await send_or_edit(cb, "🚫 *Quick Block IP*\n\nEnter IP address or subnet to block:", kb.cancel_keyboard("menu:firewall"))

    # ── DHCP ──────────────────────────────────────────────────────────────
    elif data == "menu:dhcp":
        if not _rbac.can(uid, "dhcp.view"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        await send_or_edit(cb, "📡 *DHCP Manager*", kb.dhcp_menu())

    elif data == "dhcp:leases":
        router = await require_router(cb, _rm)
        if not router:
            return
        leases = await router.get_dhcp_leases()
        page = _sessions.get_page(uid)
        text = fmt.fmt_dhcp_leases(leases, page)
        await send_or_edit(cb, text, kb.dhcp_lease_list(leases, page))

    elif data.startswith("dhcp:page:"):
        page = int(parts[2])
        _sessions.set_page(uid, page)
        router = await require_router(cb, _rm)
        if not router:
            return
        leases = await router.get_dhcp_leases()
        await send_or_edit(cb, fmt.fmt_dhcp_leases(leases, page), kb.dhcp_lease_list(leases, page))

    elif data.startswith("dhcp:lease:"):
        lease_id = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        leases = await router.get_dhcp_leases()
        lease = next((l for l in leases if l.get(".id") == lease_id), None)
        if not lease:
            await cb.answer("Lease not found.", show_alert=True)
            return
        text = fmt.fmt_dhcp_lease_detail(lease)
        is_dynamic = lease.get("type", "dynamic") == "dynamic"
        await send_or_edit(cb, text, kb.dhcp_lease_detail(lease_id, is_dynamic))

    elif data.startswith("dhcp:make_static:"):
        lease_id = parts[2]
        if not _rbac.can(uid, "dhcp.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.make_dhcp_lease_static(lease_id)
        await cb.answer("📌 Lease made static!")
        leases = await router.get_dhcp_leases()
        await send_or_edit(cb, fmt.fmt_dhcp_leases(leases), kb.dhcp_lease_list(leases))

    elif data.startswith("dhcp:remove:"):
        lease_id = parts[2]
        if not _rbac.can(uid, "dhcp.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_dhcp_lease(lease_id)
        await cb.answer("🗑 Lease removed!")
        leases = await router.get_dhcp_leases()
        await send_or_edit(cb, fmt.fmt_dhcp_leases(leases), kb.dhcp_lease_list(leases))

    elif data == "dhcp:add_static":
        if not _rbac.can(uid, "dhcp.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        _sessions.set_state(uid, "dhcp:add:mac")
        await send_or_edit(cb, "📌 *Add Static DHCP Lease*\n\nEnter MAC address:\nExample: `AA:BB:CC:DD:EE:FF`",
                           kb.cancel_keyboard("menu:dhcp"))

    elif data == "dhcp:servers":
        router = await require_router(cb, _rm)
        if not router:
            return
        servers = await router.get_dhcp_server()
        lines = [f"🖥 *DHCP Servers* ({len(servers)})\n"]
        for s in servers:
            name = s.get("name", "?")
            iface = s.get("interface", "?")
            pool = s.get("address-pool", "?")
            lease_time = s.get("lease-time", "?")
            disabled = s.get("disabled", "false") == "true"
            icon = "✅" if not disabled else "❌"
            lines.append(f"{icon} `{name}` on `{iface}`\nPool: {pool} | Lease: {lease_time}")
        await send_or_edit(cb, "\n\n".join(lines), kb.dhcp_menu())

    # ── Wireless ──────────────────────────────────────────────────────────
    elif data == "menu:wireless":
        if not _rbac.can(uid, "wireless.view"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        ifaces = await router.get_wireless_interfaces()
        if not ifaces:
            await cb.answer("No wireless interfaces found.", show_alert=True)
            return
        await send_or_edit(cb, "📶 *Wireless Manager*", kb.wireless_menu(ifaces))

    elif data.startswith("wifi:iface:"):
        name = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        ifaces = await router.get_wireless_interfaces()
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

    elif data == "wifi:clients":
        router = await require_router(cb, _rm)
        if not router:
            return
        clients = await router.get_wireless_registrations()
        text = fmt.fmt_wireless_clients(clients)
        await send_or_edit(cb, text, kb.wireless_clients_menu(clients))

    elif data.startswith("wifi:client:"):
        mac = ":".join(parts[2:])
        router = await require_router(cb, _rm)
        if not router:
            return
        clients = await router.get_wireless_registrations()
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

    elif data.startswith("wifi:disconnect:"):
        mac = ":".join(parts[2:])
        if not _rbac.can(uid, "wireless.disconnect_client"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.disconnect_wireless_client(mac)
        await cb.answer(f"🚫 {mac} disconnected")
        await send_or_edit(cb, "📶 *Wireless Manager*", kb.wireless_menu(await router.get_wireless_interfaces()))

    elif data.startswith("wifi:enable:") or data.startswith("wifi:disable:"):
        name = parts[2]
        if not _rbac.can(uid, "wireless.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        if "enable" in data:
            await router.enable_wireless(name)
            await cb.answer(f"✅ {name} enabled")
        else:
            await router.disable_wireless(name)
            await cb.answer(f"⛔ {name} disabled")
        ifaces = await router.get_wireless_interfaces()
        await send_or_edit(cb, "📶 *Wireless Manager*", kb.wireless_menu(ifaces))

    elif data.startswith("wifi:set_ssid:"):
        name = parts[2]
        if not _rbac.can(uid, "wireless.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        _sessions.set_state(uid, f"wifi:set_ssid:{name}")
        await send_or_edit(cb, f"✏️ Enter new SSID for `{name}`:", kb.cancel_keyboard("menu:wireless"))

    elif data.startswith("wifi:set_pass:"):
        name = parts[2]
        if not _rbac.can(uid, "wireless.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        _sessions.set_state(uid, f"wifi:set_pass:{name}")
        await send_or_edit(cb, f"🔑 Enter new WiFi password for `{name}` (min 8 chars):", kb.cancel_keyboard("menu:wireless"))

    elif data.startswith("wifi:scan:"):
        name = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        await cb.answer("📡 Scanning…")
        results = await router.get_wireless_scan(name)
        text = fmt.fmt_wireless_scan(results)
        await send_or_edit(cb, text, kb.wireless_iface_menu(name, False))

    # ── VPN ───────────────────────────────────────────────────────────────
    elif data == "menu:vpn":
        if not _rbac.can(uid, "vpn.view"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        await send_or_edit(cb, "🔒 *VPN Manager*", kb.vpn_menu())

    elif data == "vpn:pppoe":
        router = await require_router(cb, _rm)
        if not router:
            return
        active = await router.get_pppoe_active()
        if not active:
            await send_or_edit(cb, "📋 No active PPPoE sessions.", kb.vpn_menu())
            return
        lines = [f"📋 *PPPoE Active Sessions* ({len(active)})\n"]
        for s in active:
            lines.append(f"• `{s.get('name', '?')}` — `{s.get('address', '?')}` [{s.get('uptime', '?')}]")
        await send_or_edit(cb, "\n".join(lines), kb.vpn_menu())

    elif data == "vpn:secrets":
        router = await require_router(cb, _rm)
        if not router:
            return
        secrets = await router.get_vpn_secrets()
        page = _sessions.get_page(uid)
        await send_or_edit(cb, f"👤 *PPP Secrets* ({len(secrets)} total)", kb.vpn_secrets_list(secrets, page))

    elif data.startswith("vpn:secrets:page:"):
        page = int(parts[3])
        _sessions.set_page(uid, page)
        router = await require_router(cb, _rm)
        if not router:
            return
        secrets = await router.get_vpn_secrets()
        await send_or_edit(cb, f"👤 *PPP Secrets* ({len(secrets)} total)", kb.vpn_secrets_list(secrets, page))

    elif data.startswith("vpn:secret:remove:"):
        secret_id = parts[3]
        if not _rbac.can(uid, "vpn.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_vpn_secret(secret_id)
        await cb.answer("🗑 Secret removed")
        secrets = await router.get_vpn_secrets()
        await send_or_edit(cb, f"👤 *PPP Secrets* ({len(secrets)} total)", kb.vpn_secrets_list(secrets))

    elif data.startswith("vpn:secret:"):
        secret_id = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        secrets = await router.get_vpn_secrets()
        secret = next((s for s in secrets if s.get(".id") == secret_id), None)
        if not secret:
            await cb.answer("Secret not found.", show_alert=True)
            return
        await send_or_edit(cb, fmt.fmt_vpn_secret(secret), kb.vpn_secret_detail(secret_id))

    elif data == "vpn:add_secret":
        if not _rbac.can(uid, "vpn.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        _sessions.set_state(uid, "vpn:add:name")
        await send_or_edit(cb, "👤 *Add VPN User*\n\nEnter username:", kb.cancel_keyboard("menu:vpn"))

    elif data == "vpn:l2tp":
        router = await require_router(cb, _rm)
        if not router:
            return
        l2tp = await router.get_l2tp_server()
        text = (
            f"🔒 *L2TP Server*\n"
            f"Enabled: {'✅' if l2tp.get('enabled') == 'yes' else '❌'}\n"
            f"Auth: `{l2tp.get('authentication', '?')}`"
        )
        await send_or_edit(cb, text, kb.vpn_menu())

    elif data == "vpn:ovpn":
        router = await require_router(cb, _rm)
        if not router:
            return
        ovpn = await router.get_ovpn_server()
        text = (
            f"🔑 *OpenVPN Server*\n"
            f"Enabled: {'✅' if ovpn.get('enabled') == 'yes' else '❌'}\n"
            f"Port: `{ovpn.get('port', '1194')}`"
        )
        await send_or_edit(cb, text, kb.vpn_menu())

    elif data == "vpn:wg":
        router = await require_router(cb, _rm)
        if not router:
            return
        ifaces = await router.get_wireguard_interfaces()
        peers = await router.get_wireguard_peers()
        if not ifaces:
            await send_or_edit(cb, "🔒 WireGuard not available on this device.", kb.vpn_menu())
            return
        await send_or_edit(cb, fmt.fmt_wireguard_peers(peers), kb.wireguard_menu(ifaces, peers))

    elif data == "wg:peers":
        router = await require_router(cb, _rm)
        if not router:
            return
        peers = await router.get_wireguard_peers()
        await send_or_edit(cb, fmt.fmt_wireguard_peers(peers), kb.wg_peers_list(peers))

    # ── Files ─────────────────────────────────────────────────────────────
    elif data == "menu:files":
        if not _rbac.can(uid, "file.view"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        files = await router.get_files()
        text = fmt.fmt_files(files)
        await send_or_edit(cb, text, kb.files_menu(files))

    elif data.startswith("file:detail:"):
        name = ":".join(parts[2:])
        router = await require_router(cb, _rm)
        if not router:
            return
        files = await router.get_files()
        f = next((x for x in files if x.get("name") == name), None)
        if not f:
            await cb.answer("File not found.", show_alert=True)
            return
        size = int(f.get("size", 0))
        text = (
            f"📄 *File: {name}*\n"
            f"Size: `{size:,}` bytes\n"
            f"Created: `{f.get('creation-time', '?')}`\n"
            f"Type: `{f.get('type', 'unknown')}`"
        )
        await send_or_edit(cb, text, kb.file_detail_menu(name))

    elif data.startswith("file:download:"):
        name = ":".join(parts[2:])
        if not _rbac.can(uid, "file.download"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        try:
            content = await router.get_backup_file(name)
            await cb.answer("⬇️ Preparing download…")
            from aiogram.types import BufferedInputFile
            doc = BufferedInputFile(content, filename=name.split("/")[-1])
            await cb.message.answer_document(doc, caption=f"📄 `{name}`", parse_mode="Markdown")
        except NotImplementedError:
            await cb.answer("⚠️ Download requires FTP access to the router.", show_alert=True)
        except Exception as e:
            await cb.answer(f"❌ Error: {e}", show_alert=True)

    elif data.startswith("file:delete:"):
        name = ":".join(parts[2:])
        if not _rbac.can(uid, "file.delete"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.delete_file(name)
        await cb.answer(f"🗑 {name} deleted")
        files = await router.get_files()
        await send_or_edit(cb, fmt.fmt_files(files), kb.files_menu(files))

    # ── Logs ──────────────────────────────────────────────────────────────
    elif data == "menu:logs":
        await send_or_edit(cb, "📋 *Log Viewer*", kb.logs_menu())

    elif data.startswith("log:last"):
        limit = int(data.replace("log:last", ""))
        router = await require_router(cb, _rm)
        if not router:
            return
        logs = await router.get_logs(limit=limit)
        text = fmt.fmt_logs(logs)
        await send_or_edit(cb, text, kb.logs_menu())

    elif data.startswith("log:filter:"):
        topics = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        logs = await router.get_logs(limit=30, topics=topics)
        text = fmt.fmt_logs(logs)
        await send_or_edit(cb, text, kb.logs_menu())

    elif data.startswith("log:stream"):
        if not _rbac.can(uid, "log.stream"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        topics = parts[2] if len(parts) > 2 else ""
        await _sessions.stop_log_stream(uid)
        stop_event = asyncio.Event()

        async def _stream():
            await stream_logs_to_chat(router, _bot, uid, topics=topics, stop_event=stop_event)

        task = asyncio.create_task(_stream())
        _sessions.set_log_task(uid, task)
        await cb.answer("📡 Log stream started!")
        await cb.message.answer("📡 *Log stream active.* Use /stop\\_logs to stop.", parse_mode="Markdown",
                                reply_markup=kb.log_stream_stop())

    elif data == "log:stop":
        await _sessions.stop_log_stream(uid)
        await cb.answer("🔴 Stopped")
        await send_or_edit(cb, "📋 *Log Viewer*", kb.logs_menu())

    # ── Routes ────────────────────────────────────────────────────────────
    elif data == "menu:routes":
        router = await require_router(cb, _rm)
        if not router:
            return
        routes = await router.get_routes()
        await send_or_edit(cb, fmt.fmt_routes(routes), kb.routes_menu(routes))

    elif data.startswith("route:detail:"):
        route_id = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        routes = await router.get_routes()
        route = next((r for r in routes if r.get(".id") == route_id), None)
        if not route:
            await cb.answer("Route not found.", show_alert=True)
            return
        dst = route.get("dst-address", "?")
        gw = route.get("gateway", "?")
        active = "🟢" if route.get("active") == "true" else "🔴"
        text = f"🗺 *Route*\n{active} `{dst}` → `{gw}`\nDistance: `{route.get('distance', '?')}`"
        await send_or_edit(cb, text, kb.route_detail_menu(route_id))

    elif data.startswith("route:remove:"):
        route_id = parts[2]
        if not _rbac.can(uid, "route.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_route(route_id)
        await cb.answer("🗑 Route removed")
        routes = await router.get_routes()
        await send_or_edit(cb, fmt.fmt_routes(routes), kb.routes_menu(routes))

    elif data == "route:add":
        if not _rbac.can(uid, "route.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        _sessions.set_state(uid, "route:add:dst")
        await send_or_edit(cb, "🗺 *Add Route*\n\nEnter destination address:\nExample: `10.0.0.0/8` or `0.0.0.0/0`",
                           kb.cancel_keyboard("menu:routes"))

    # ── DNS ───────────────────────────────────────────────────────────────
    elif data == "menu:dns":
        await send_or_edit(cb, "🌐 *DNS Manager*", kb.dns_menu())

    elif data == "dns:settings":
        router = await require_router(cb, _rm)
        if not router:
            return
        settings = await router.get_dns_settings()
        await send_or_edit(cb, fmt.fmt_dns(settings), kb.dns_menu())

    elif data == "dns:cache":
        router = await require_router(cb, _rm)
        if not router:
            return
        cache = await router.get_dns_cache()
        await send_or_edit(cb, fmt.fmt_dns_cache(cache), kb.dns_menu())

    elif data == "dns:flush":
        if not _rbac.can(uid, "dns.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.flush_dns_cache()
        await cb.answer("🗑 DNS cache flushed!")
        settings = await router.get_dns_settings()
        await send_or_edit(cb, fmt.fmt_dns(settings), kb.dns_menu())

    elif data == "dns:set_servers":
        if not _rbac.can(uid, "dns.manage"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        _sessions.set_state(uid, "dns:set_servers")
        await send_or_edit(cb, "🌐 Enter DNS servers (comma or space separated):\nExample: `1.1.1.1 8.8.8.8`",
                           kb.cancel_keyboard("menu:dns"))

    # ── Tools ─────────────────────────────────────────────────────────────
    elif data == "menu:tools":
        await send_or_edit(cb, "🔧 *Network Tools*", kb.tools_menu())

    elif data == "tool:ping":
        _sessions.set_state(uid, "tool:ping")
        await send_or_edit(cb, "🏓 Enter hostname or IP to ping:", kb.cancel_keyboard("menu:tools"))

    elif data == "tool:traceroute":
        _sessions.set_state(uid, "tool:traceroute")
        await send_or_edit(cb, "🗺 Enter hostname or IP for traceroute:", kb.cancel_keyboard("menu:tools"))

    elif data == "tool:bwtest":
        if not _rbac.can(uid, "tool.bandwidth_test"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        _sessions.set_state(uid, "tool:bwtest")
        await send_or_edit(cb, "📊 Enter target IP for bandwidth test\n(requires Bandwidth Test tool on target):", kb.cancel_keyboard("menu:tools"))

    elif data == "tool:scripts":
        router = await require_router(cb, _rm)
        if not router:
            return
        if isinstance(router, RouterROS7):
            scripts = await router.get_scripts()
            if not scripts:
                await cb.answer("No scripts found.", show_alert=True)
                return
            lines = [f"📜 *Scripts* ({len(scripts)})\n"]
            for s in scripts:
                name = s.get("name", "?")
                lines.append(f"• `{name}`")
            await send_or_edit(cb, "\n".join(lines), kb.tools_menu())
        else:
            await cb.answer("Scripts view requires RouterOS 7.", show_alert=True)

    # ── Backup ────────────────────────────────────────────────────────────
    elif data == "menu:backup":
        if not _rbac.can(uid, "system.backup"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        await send_or_edit(cb, "📦 *Backup & Export*", kb.backup_menu())

    elif data == "backup:create":
        router = await require_router(cb, _rm)
        if not router:
            return
        await cb.answer("💾 Creating backup…")
        filename = await router.create_backup()
        await send_or_edit(cb, f"✅ *Backup created!*\nFile: `{filename}`", kb.backup_menu())

    elif data == "backup:export":
        if not _rbac.can(uid, "system.export"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await cb.answer("📜 Exporting…")
        config = await router.export_config()
        if len(config) > 4000:
            from aiogram.types import BufferedInputFile
            doc = BufferedInputFile(config.encode(), filename="export.rsc")
            await cb.message.answer_document(doc, caption="📜 Router configuration export")
        else:
            await cb.message.answer(f"```\n{config}\n```", parse_mode="Markdown")

    # ── Settings ──────────────────────────────────────────────────────────
    elif data == "menu:settings":
        await send_or_edit(cb, "⚙️ *Settings*", kb.settings_menu())

    elif data == "settings:lang":
        await send_or_edit(cb, "🌐 *Select Language*", kb.lang_keyboard())

    elif data == "settings:routers":
        router_list = _rm.get_router_list(uid)
        if not router_list:
            text = "🔌 *Your Routers*\n\nNo routers connected yet.\nUse ➕ Add Router."
        else:
            text = f"🔌 *Your Routers* ({len(router_list)} connected)"
        await send_or_edit(cb, text, kb.routers_menu(router_list))

    elif data.startswith("router:select:"):
        alias = parts[2]
        router_list = _rm.get_router_list(uid)
        entry = next((r for r in router_list if r["alias"] == alias), None)
        if not entry:
            await cb.answer("Router not found.", show_alert=True)
            return
        is_active = entry.get("active", False)
        await send_or_edit(cb, f"🔌 *Router: {alias}*\nHost: `{entry['host']}`\nROS{entry['version']}",
                           kb.router_detail_menu(alias, is_active))

    elif data.startswith("router:activate:"):
        alias = parts[2]
        if _rm.switch_router(uid, alias):
            await cb.answer(f"⭐ Switched to {alias}")
        router_list = _rm.get_router_list(uid)
        await send_or_edit(cb, f"🔌 *Your Routers*", kb.routers_menu(router_list))

    elif data.startswith("router:remove:"):
        alias = parts[2]
        if not _rbac.can(uid, "router.remove"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        await _rm.remove_router(uid, alias)
        await cb.answer(f"🗑 {alias} removed")
        router_list = _rm.get_router_list(uid)
        await send_or_edit(cb, "🔌 *Your Routers*", kb.routers_menu(router_list))

    elif data == "router:add":
        if not _rbac.can(uid, "router.add"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        _sessions.set_state(uid, "add_router:alias")
        await send_or_edit(cb,
            "➕ *Add Router*\n\nStep 1/5: Enter a name (alias) for this router:",
            kb.cancel_keyboard("settings:routers"),
        )

    elif data == "settings:users":
        if not _rbac.can(uid, "user.view"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        users = _rbac.get_all_users()
        await send_or_edit(cb, f"👥 *Bot Users* ({len(users)})", kb.bot_users_menu(users))

    elif data.startswith("admin:user:"):
        target_uid = int(parts[2])
        if not _rbac.can(uid, "user.role.change"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        role = _rbac.get_role(target_uid)
        text = f"👤 *User ID: {target_uid}*\nCurrent role: `{role.to_str() if role else 'none'}`"
        await send_or_edit(cb, text, kb.user_role_menu(target_uid))

    elif data.startswith("admin:setrole:"):
        target_uid = int(parts[2])
        new_role_str = parts[3]
        if not _rbac.can(uid, "user.role.change"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        new_role = Role.from_str(new_role_str)
        await _rbac.set_role(target_uid, new_role)
        await cb.answer(f"✅ User {target_uid} → {new_role_str}")
        users = _rbac.get_all_users()
        await send_or_edit(cb, f"👥 *Bot Users* ({len(users)})", kb.bot_users_menu(users))

    elif data.startswith("admin:removeuser:"):
        target_uid = int(parts[2])
        if not _rbac.can(uid, "user.remove"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        await _rbac.remove_user(target_uid)
        await cb.answer(f"🗑 User {target_uid} removed")
        users = _rbac.get_all_users()
        await send_or_edit(cb, f"👥 *Bot Users* ({len(users)})", kb.bot_users_menu(users))

    elif data == "admin:add_user":
        if not _rbac.can(uid, "user.add"):
            await cb.answer("🚫 Insufficient permissions.", show_alert=True)
            return
        _sessions.set_state(uid, "admin:add_user")
        await send_or_edit(cb, "👤 *Add Bot User*\n\nEnter the Telegram user ID:", kb.cancel_keyboard("settings:users"))

    # ── Containers (ROS7) ─────────────────────────────────────────────────
    elif data == "container:list":
        router = await require_router(cb, _rm)
        if not router:
            return
        containers = await router.get_container_list()
        if not containers:
            await send_or_edit(cb, "🐋 No containers on this device.", kb.settings_menu())
            return
        await send_or_edit(cb, f"🐋 *Docker Containers* ({len(containers)})", kb.container_menu(containers))

    elif data.startswith("container:detail:"):
        id_ = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        containers = await router.get_container_list()
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

    elif data.startswith("container:start:"):
        id_ = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        if isinstance(router, RouterROS7):
            await router.start_container(id_)
            await cb.answer("▶️ Container starting…")

    elif data.startswith("container:stop:"):
        id_ = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        if isinstance(router, RouterROS7):
            await router.stop_container(id_)
            await cb.answer("⛔ Container stopping…")

    elif data.startswith("container:remove:"):
        id_ = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        if isinstance(router, RouterROS7):
            await router.remove_container(id_)
            await cb.answer("🗑 Container removed")

    # ── IP Management ─────────────────────────────────────────────────────
    elif data == "menu:ip":
        await send_or_edit(cb, "🌐 *IP Management*", kb.ip_menu())

    elif data == "ip:list":
        router = await require_router(cb, _rm)
        if not router:
            return
        addrs = await router.get_ip_addresses()
        await send_or_edit(cb, fmt.fmt_ip_addresses(addrs), kb.ip_address_list_menu(addrs))

    elif data.startswith("ip:addr:detail:"):
        id_ = parts[3]
        router = await require_router(cb, _rm)
        if not router:
            return
        addrs = await router.get_ip_addresses()
        addr = next((a for a in addrs if a.get(".id") == id_), {})
        text_ = f"📍 *IP Address*\n`{addr.get('address', '?')}` on `{addr.get('interface', '?')}`\nNetwork: `{addr.get('network', '?')}`"
        await send_or_edit(cb, text_, kb.ip_addr_detail_menu(id_))

    elif data.startswith("ip:remove:"):
        id_ = parts[2]
        if not await _perm(cb, "ip.manage"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_ip_address(id_)
        await cb.answer("🗑 IP removed")
        addrs = await router.get_ip_addresses()
        await send_or_edit(cb, fmt.fmt_ip_addresses(addrs), kb.ip_address_list_menu(addrs))

    elif data == "ip:add_prompt":
        if not await _perm(cb, "ip.manage"):
            return
        ifaces = await (await require_router(cb, _rm)).get_interfaces() if _rm.get_active(uid) else []
        iface_names = [i.get("name", "?") for i in ifaces[:10]]
        await send_or_edit(cb, f"📍 *Add IP Address*\n\nEnter address/prefix:\nExample: `192.168.88.1/24`\n\nAvailable interfaces: `{'`, `'.join(iface_names)}`",
                           kb.cancel_keyboard("ip:list"))
        # We'll use a generic state with prompt for iface after
        _sessions.set_state(uid, "ip:add_addr")

    elif data == "ip:arp":
        router = await require_router(cb, _rm)
        if not router:
            return
        arp = await router.get_arp()
        await send_or_edit(cb, fmt.fmt_arp(arp), kb.arp_menu())

    elif data == "ip:pools":
        router = await require_router(cb, _rm)
        if not router:
            return
        pools = await router.get_ip_pools()
        await send_or_edit(cb, fmt.fmt_ip_pools(pools), kb.ip_pools_menu(pools))

    elif data == "ip:pool:add_prompt":
        if not await _perm(cb, "ip.manage"):
            return
        _sessions.set_state(uid, "ip:pool:add:name")
        await send_or_edit(cb, "🏊 *Add IP Pool*\n\nEnter pool name:\nExample: `dhcp_pool`", kb.cancel_keyboard("ip:pools"))

    elif data.startswith("ip:pool:detail:"):
        id_ = parts[3]
        router = await require_router(cb, _rm)
        if not router:
            return
        pools = await router.get_ip_pools()
        pool = next((p for p in pools if p.get(".id") == id_), {})
        text_ = f"🏊 *IP Pool: {pool.get('name', '?')}*\nRanges: `{pool.get('ranges', '?')}`"
        await send_or_edit(cb, text_, kb.ip_pool_detail_menu(id_))

    elif data.startswith("ip:pool:remove:"):
        id_ = parts[3]
        if not await _perm(cb, "ip.manage"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_ip_pool(id_)
        await cb.answer("🗑 Pool removed")
        pools = await router.get_ip_pools()
        await send_or_edit(cb, fmt.fmt_ip_pools(pools), kb.ip_pools_menu(pools))

    # ── Queues / QoS ──────────────────────────────────────────────────────
    elif data == "menu:queues":
        router = await require_router(cb, _rm)
        if not router:
            return
        queues = await router.get_simple_queues()
        await send_or_edit(cb, fmt.fmt_queues(queues), kb.queues_menu(queues))

    elif data == "queue:add_prompt":
        if not await _perm(cb, "firewall.manage"):
            return
        _sessions.set_state(uid, "queue:add:name")
        await send_or_edit(cb, "📊 *Add Queue*\n\nEnter queue name:", kb.cancel_keyboard("menu:queues"))

    elif data.startswith("queue:detail:"):
        id_ = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        queues = await router.get_simple_queues()
        q = next((x for x in queues if x.get(".id") == id_), {})
        if not q:
            await cb.answer("Queue not found.", show_alert=True)
            return
        disabled = q.get("disabled", "false") == "true"
        await send_or_edit(cb, fmt.fmt_queue_detail(q), kb.queue_detail_menu(id_, disabled))

    elif data.startswith("queue:enable:") or data.startswith("queue:disable:"):
        id_ = parts[2]
        if not await _perm(cb, "firewall.manage"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        if "enable" in data:
            await router.enable_simple_queue(id_)
            await cb.answer("✅ Queue enabled")
        else:
            await router.disable_simple_queue(id_)
            await cb.answer("⛔ Queue disabled")
        queues = await router.get_simple_queues()
        await send_or_edit(cb, fmt.fmt_queues(queues), kb.queues_menu(queues))

    elif data.startswith("queue:remove:"):
        id_ = parts[2]
        if not await _perm(cb, "firewall.manage"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_simple_queue(id_)
        await cb.answer("🗑 Queue removed")
        queues = await router.get_simple_queues()
        await send_or_edit(cb, fmt.fmt_queues(queues), kb.queues_menu(queues))

    # ── Mangle Rules ──────────────────────────────────────────────────────
    elif data == "fw:mangle":
        router = await require_router(cb, _rm)
        if not router:
            return
        rules = await router.get_firewall_mangle()
        page = _sessions.get_page(uid)
        await send_or_edit(cb, fmt.fmt_mangle_rules(rules), kb.mangle_rule_list(rules, page))

    elif data.startswith("mangle:page:"):
        page = int(parts[2])
        _sessions.set_page(uid, page)
        router = await require_router(cb, _rm)
        if not router:
            return
        rules = await router.get_firewall_mangle()
        await send_or_edit(cb, fmt.fmt_mangle_rules(rules), kb.mangle_rule_list(rules, page))

    elif data.startswith("mangle:detail:"):
        id_ = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        rules = await router.get_firewall_mangle()
        r = next((x for x in rules if x.get(".id") == id_), {})
        if not r:
            await cb.answer("Rule not found.", show_alert=True)
            return
        chain = r.get("chain", "?")
        action = r.get("action", "?")
        new_ttl = r.get("new-routing-mark", r.get("new-packet-mark", ""))
        text_ = (
            f"🔀 *Mangle Rule {id_}*\n"
            f"Chain: `{chain}` | Action: `{action}`\n"
            + (f"Mark: `{new_ttl}`\n" if new_ttl else "")
            + f"Comment: {r.get('comment', '-')}"
        )
        await send_or_edit(cb, text_, kb.mangle_detail_menu(id_))

    elif data.startswith("mangle:remove:"):
        id_ = parts[2]
        if not await _perm(cb, "firewall.manage"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_firewall_mangle(id_)
        await cb.answer("🗑 Mangle rule removed")
        rules = await router.get_firewall_mangle()
        await send_or_edit(cb, fmt.fmt_mangle_rules(rules), kb.mangle_rule_list(rules, 0))

    elif data == "mangle:add_prompt":
        if not await _perm(cb, "firewall.manage"):
            return
        await send_or_edit(cb, "🔀 *Add Mangle Rule*\n\nEnter in format:\n`chain action [src-address] [comment]`\nExample: `prerouting mark-packet 192.168.1.0/24 voip`",
                           kb.cancel_keyboard("fw:mangle"))
        _sessions.set_state(uid, "mangle:add")

    # ── NAT Extended ──────────────────────────────────────────────────────
    elif data.startswith("fw:nat"):
        router = await require_router(cb, _rm)
        if not router:
            return
        rules = await router.get_firewall_nat()
        lines = [f"🔀 *NAT Rules* ({len(rules)} total)\n"]
        for r in rules:
            id_ = r.get(".id", "?")
            chain = r.get("chain", "?")
            action = r.get("action", "?")
            to = r.get("to-addresses", r.get("to-ports", ""))
            comment = r.get("comment", "")
            icon = "⛔" if r.get("disabled", "false") == "true" else "🟢"
            lines.append(f"{icon} `{id_}` [{chain}] → `{action}`" + (f" to `{to}`" if to else "") + (f" | {comment}" if comment else ""))
        builder = InlineKeyboardBuilder()
        for r in rules:
            id_ = r.get(".id", "?")
            builder.row(InlineKeyboardButton(text=f"[{r.get('chain','?')}] {r.get('action','?')} ({id_})", callback_data=f"nat:detail:{id_}"))
        builder.row(
            InlineKeyboardButton(text="➕ Add NAT Rule", callback_data="nat:add_prompt"),
            InlineKeyboardButton(text="← Back", callback_data="menu:firewall"),
        )
        await send_or_edit(cb, "\n".join(lines)[:4096], builder.as_markup())

    elif data.startswith("nat:detail:"):
        id_ = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        rules = await router.get_firewall_nat()
        r = next((x for x in rules if x.get(".id") == id_), {})
        if not r:
            await cb.answer("NAT rule not found.", show_alert=True)
            return
        await send_or_edit(cb, fmt.fmt_nat_detail(r), kb.nat_rule_detail_menu(id_))

    elif data.startswith("nat:remove:"):
        id_ = parts[2]
        if not await _perm(cb, "firewall.manage"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_firewall_nat(id_)
        await cb.answer("🗑 NAT rule removed")
        await send_or_edit(cb, "🔀 *NAT Manager*", kb.firewall_menu())

    elif data == "nat:add_prompt":
        if not await _perm(cb, "firewall.manage"):
            return
        await send_or_edit(cb, "🔀 *Add NAT Rule*\n\nSelect chain:", kb.nat_add_type_menu())

    elif data.startswith("nat:add:chain:"):
        chain = parts[3]
        _sessions.update_data(uid, nat_chain=chain)
        await send_or_edit(cb, f"NAT chain: `{chain}`\nSelect action:", kb.nat_add_action_menu(chain))

    elif data.startswith("nat:add:action:"):
        action = parts[3]
        chain = parts[4]
        _sessions.update_data(uid, nat_action=action, nat_chain=chain)
        _sessions.set_state(uid, "nat:add:src_addr")
        await send_or_edit(cb, f"Action: `{action}` on `{chain}`\n\nSource IP/subnet (or `-` to skip):", kb.cancel_keyboard("fw:nat"))

    # ── Hotspot ───────────────────────────────────────────────────────────
    elif data == "menu:hotspot":
        await send_or_edit(cb, "🔥 *Hotspot Manager*", kb.hotspot_menu())

    elif data == "hotspot:users":
        router = await require_router(cb, _rm)
        if not router:
            return
        users = await router.get_hotspot_users()
        await send_or_edit(cb, fmt.fmt_hotspot_users(users), kb.hotspot_users_menu(users))

    elif data == "hotspot:active":
        router = await require_router(cb, _rm)
        if not router:
            return
        sessions = await router.get_hotspot_active()
        await send_or_edit(cb, fmt.fmt_hotspot_active(sessions), kb.hotspot_active_menu(sessions))

    elif data.startswith("hotspot:user:"):
        id_ = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        users = await router.get_hotspot_users()
        u = next((x for x in users if x.get(".id") == id_), {})
        text_ = (
            f"👤 *Hotspot User: {u.get('name', '?')}*\n"
            f"Profile: `{u.get('profile', 'default')}`\n"
            f"Password: `{u.get('password', '?')}`\n"
            f"Comment: {u.get('comment', '-')}"
        )
        await send_or_edit(cb, text_, kb.hotspot_user_detail_menu(id_))

    elif data.startswith("hotspot:remove:"):
        id_ = parts[2]
        if not await _perm(cb, "dhcp.manage"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_hotspot_user(id_)
        await cb.answer("🗑 User removed")
        users = await router.get_hotspot_users()
        await send_or_edit(cb, fmt.fmt_hotspot_users(users), kb.hotspot_users_menu(users))

    elif data.startswith("hotspot:kick:"):
        id_ = parts[2]
        if not await _perm(cb, "wireless.disconnect_client"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.disconnect_hotspot_user(id_)
        await cb.answer("🚫 Session disconnected")
        sessions = await router.get_hotspot_active()
        await send_or_edit(cb, fmt.fmt_hotspot_active(sessions), kb.hotspot_active_menu(sessions))

    elif data == "hotspot:add_prompt":
        if not await _perm(cb, "dhcp.manage"):
            return
        _sessions.set_state(uid, "hotspot:add:name")
        await send_or_edit(cb, "🔥 *Add Hotspot User*\n\nEnter username:", kb.cancel_keyboard("menu:hotspot"))

    # ── Scripts ───────────────────────────────────────────────────────────
    elif data == "menu:scripts":
        router = await require_router(cb, _rm)
        if not router:
            return
        scripts = await router.get_scripts()
        await send_or_edit(cb, fmt.fmt_scripts(scripts), kb.scripts_menu(scripts))

    elif data.startswith("script:detail:"):
        name = ":".join(parts[2:])
        router = await require_router(cb, _rm)
        if not router:
            return
        scripts = await router.get_scripts()
        s = next((x for x in scripts if x.get("name") == name), {})
        if not s:
            await cb.answer("Script not found.", show_alert=True)
            return
        await send_or_edit(cb, fmt.fmt_script_detail(s), kb.script_detail_menu(name))

    elif data.startswith("script:run:"):
        name = ":".join(parts[2:])
        if not await _perm(cb, "system.export"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        try:
            await router.run_script(name)
            await cb.answer(f"▶️ Script '{name}' executed!")
        except Exception as e:
            await cb.answer(f"❌ Error: {e}", show_alert=True)

    # ── Bridge / VLAN ─────────────────────────────────────────────────────
    elif data == "menu:bridge":
        router = await require_router(cb, _rm)
        if not router:
            return
        bridges = await router.get_bridges()
        ports = await router.get_bridge_ports()
        await send_or_edit(cb, fmt.fmt_bridges(bridges, ports), kb.bridge_menu(bridges))

    elif data.startswith("bridge:detail:"):
        name = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        bridges = await router.get_bridges()
        b = next((x for x in bridges if x.get("name") == name), {})
        ports = await router.get_bridge_ports()
        bridge_ports = [p for p in ports if p.get("bridge") == name]
        port_text = "\n".join(f"   🔌 `{p.get('interface','?')}` [priority: {p.get('priority','?')}]" for p in bridge_ports)
        text_ = (
            f"🌉 *Bridge: {name}*\n"
            f"MAC: `{b.get('mac-address','?')}`\n"
            f"STP: `{b.get('protocol-mode','none')}`\n"
            f"Forward delay: `{b.get('forward-delay','?')}`\n\n"
            f"*Ports:*\n{port_text or '   (none)'}"
        )
        await send_or_edit(cb, text_, kb.bridge_detail_menu(name))

    elif data.startswith("bridge:ports:"):
        bridge_name = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        ports = await router.get_bridge_ports()
        bridge_ports = [p for p in ports if p.get("bridge") == bridge_name]
        builder = InlineKeyboardBuilder()
        for p in bridge_ports:
            iface = p.get("interface", "?")
            id_ = p.get(".id", "")
            builder.row(InlineKeyboardButton(
                text=f"🗑 Remove {iface}",
                callback_data=f"bridge:port:remove:{id_}",
            ))
        builder.row(InlineKeyboardButton(text="← Back", callback_data=f"bridge:detail:{bridge_name}"))
        port_lines = "\n".join(f"• `{p.get('interface','?')}`" for p in bridge_ports)
        await send_or_edit(cb, f"🔌 *Ports on {bridge_name}*\n\n{port_lines or 'None'}", builder.as_markup())

    elif data.startswith("bridge:port:remove:"):
        id_ = parts[3]
        if not await _perm(cb, "ip.manage"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_bridge_port(id_)
        await cb.answer("🗑 Port removed")

    elif data == "vlan:list":
        router = await require_router(cb, _rm)
        if not router:
            return
        vlans = await router.get_vlans()
        await send_or_edit(cb, fmt.fmt_vlans(vlans), kb.vlan_list_menu(vlans))

    elif data == "vlan:add_prompt":
        if not await _perm(cb, "ip.manage"):
            return
        _sessions.set_state(uid, "vlan:add:name")
        await send_or_edit(cb, "🏷 *Add VLAN*\n\nEnter VLAN name:", kb.cancel_keyboard("vlan:list"))

    elif data.startswith("vlan:detail:"):
        id_ = parts[2]
        router = await require_router(cb, _rm)
        if not router:
            return
        vlans = await router.get_vlans()
        v = next((x for x in vlans if x.get(".id") == id_), {})
        text_ = (
            f"🏷 *VLAN {v.get('vlan-id','?')}: {v.get('name','?')}*\n"
            f"Interface: `{v.get('interface','?')}`\n"
            f"MTU: `{v.get('mtu','1500')}`"
        )
        await send_or_edit(cb, text_, kb.vlan_detail_menu(id_))

    elif data.startswith("vlan:remove:"):
        id_ = parts[2]
        if not await _perm(cb, "ip.manage"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_vlan(id_)
        await cb.answer("🗑 VLAN removed")
        vlans = await router.get_vlans()
        await send_or_edit(cb, fmt.fmt_vlans(vlans), kb.vlan_list_menu(vlans))

    # ── NTP ───────────────────────────────────────────────────────────────
    elif data == "sys:ntp":
        router = await require_router(cb, _rm)
        if not router:
            return
        ntp = await router.get_ntp_client()
        await send_or_edit(cb, fmt.fmt_ntp(ntp), kb.ntp_menu())

    elif data == "ntp:view":
        router = await require_router(cb, _rm)
        if not router:
            return
        ntp = await router.get_ntp_client()
        await send_or_edit(cb, fmt.fmt_ntp(ntp), kb.ntp_menu())

    elif data == "ntp:set_prompt":
        if not await _perm(cb, "system.export"):
            return
        _sessions.set_state(uid, "ntp:set_servers")
        await send_or_edit(cb, "🕐 *Set NTP Servers*\n\nEnter servers (space/comma separated):\nExample: `pool.ntp.org 1.1.1.1`",
                           kb.cancel_keyboard("sys:ntp"))

    # ── Certificates ──────────────────────────────────────────────────────
    elif data == "sys:certs":
        router = await require_router(cb, _rm)
        if not router:
            return
        certs = await router.get_certificates()
        await send_or_edit(cb, fmt.fmt_certificates(certs), kb.certs_menu(certs))

    elif data.startswith("cert:detail:"):
        name = ":".join(parts[2:])
        router = await require_router(cb, _rm)
        if not router:
            return
        certs = await router.get_certificates()
        c = next((x for x in certs if x.get("name") == name), {})
        if not c:
            await cb.answer("Certificate not found.", show_alert=True)
            return
        lines = [f"🔐 *Certificate: {name}*"]
        for k, v in c.items():
            if not k.startswith("."):
                lines.append(f"`{k}`: {v}")
        await send_or_edit(cb, "\n".join(lines), kb.certs_menu([]))

    # ── System extended ───────────────────────────────────────────────────
    elif data == "sys:add_user":
        if not await _perm(cb, "ip.manage"):
            return
        _sessions.set_state(uid, "sys:add_user:name")
        await send_or_edit(cb, "👤 *Add Router User*\n\nEnter username:", kb.cancel_keyboard("sys:users_detail"))

    elif data.startswith("sys:remove_user:"):
        id_ = parts[2]
        if not await _perm(cb, "system.reboot"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        await router.remove_user(id_)
        await cb.answer("🗑 User removed")
        users = await router.get_users()
        await send_or_edit(cb, fmt.fmt_router_users(users), kb.system_menu())

    # ── WireGuard Add Peer ────────────────────────────────────────────────
    elif data.startswith("wg:add_peer:"):
        iface = parts[2]
        _sessions.set_state(uid, f"wg:add_peer:pubkey:{iface}")
        await send_or_edit(cb, "🔒 *Add WireGuard Peer*\n\nPaste peer's public key:", kb.cancel_keyboard("vpn:wg"))

    elif data.startswith("wg:remove:"):
        id_ = parts[2]
        if not await _perm(cb, "vpn.manage"):
            return
        router = await require_router(cb, _rm)
        if not router:
            return
        if isinstance(router, RouterROS7):
            await router.remove_wireguard_peer(id_)
            await cb.answer("🗑 WG peer removed")
            peers = await router.get_wireguard_peers()
            await send_or_edit(cb, fmt.fmt_wireguard_peers(peers), kb.wg_peers_list(peers))

    # ── PPP Profiles ──────────────────────────────────────────────────────
    elif data == "vpn:profiles":
        router = await require_router(cb, _rm)
        if not router:
            return
        profiles = await router.get_ppp_profiles()
        await send_or_edit(cb, fmt.fmt_ppp_profiles(profiles), kb.vpn_menu())

    # ── Ethernet Stats ────────────────────────────────────────────────────
    elif data == "iface:eth_stats":
        router = await require_router(cb, _rm)
        if not router:
            return
        stats = await router.get_interface_ethernet_stats()
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

    else:
        await cb.answer(f"Unknown action: {data[:30]}", show_alert=True)
