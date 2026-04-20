"""FSM text input handler — all multi-step wizard states dispatched from one @message(F.text)."""

from aiogram import Router, F
from aiogram.types import Message

from handlers import context as ctx
from handlers.base import require_router
from core.rbac import Role
from core.audit import log_action, log_admin
from ui import keyboards as kb
from ui import formatters as fmt
from ui.i18n import t, get_lang

import logging
log = logging.getLogger("FSM")

router = Router()


@router.message(F.text)
async def handle_text(msg: Message):
    uid = msg.from_user.id
    if not ctx.sessions:
        return
    state = ctx.sessions.get_state(uid)
    if state == "idle" or not state:
        return
    await _handle_fsm(msg, uid, state, msg.text.strip())


async def _handle_fsm(msg: Message, uid: int, state: str, text: str):
    data = ctx.sessions.get_data(uid)

    # ── Add Router FSM ──────────────────────────────────────────────────────
    if state == "add_router:alias":
        ctx.sessions.update_data(uid, alias=text)
        ctx.sessions.set_state(uid, "add_router:host")
        lang = get_lang(uid, ctx.sessions)
        await msg.answer(t("fsm.router.host", lang), parse_mode="Markdown")

    elif state == "add_router:host":
        ctx.sessions.update_data(uid, host=text)
        ctx.sessions.set_state(uid, "add_router:user")
        lang = get_lang(uid, ctx.sessions)
        await msg.answer(t("fsm.router.user", lang), parse_mode="Markdown")

    elif state == "add_router:user":
        ctx.sessions.update_data(uid, username=text)
        ctx.sessions.set_state(uid, "add_router:pass")
        lang = get_lang(uid, ctx.sessions)
        await msg.answer(t("fsm.router.pass", lang), parse_mode="Markdown")

    elif state == "add_router:pass":
        password = "" if text == "-" else text
        ctx.sessions.update_data(uid, password=password)
        ctx.sessions.set_state(uid, "add_router:port")
        # Delete the message containing the password for security
        try:
            await msg.delete()
        except Exception:
            pass
        lang = get_lang(uid, ctx.sessions)
        await msg.answer(t("fsm.router.pass_received", lang), parse_mode="Markdown")

    elif state == "add_router:port":
        d = ctx.sessions.get_data(uid)
        alias = d["alias"]  # save before clear_state wipes it
        host = d["host"]
        port = 8728
        use_ssl = False
        if text != "-":
            try:
                port = int(text)
                use_ssl = port == 8729
            except ValueError:
                pass
        lang = get_lang(uid, ctx.sessions)
        await msg.answer(t("fsm.router.connecting", lang), parse_mode="Markdown")
        ok, result = await ctx.rm.add_router(
            user_id=uid,
            alias=alias,
            host=host,
            username=d["username"],
            password=d["password"],
            port=port,
            use_ssl=use_ssl,
        )
        ctx.sessions.clear_state(uid)
        if ok:
            log_admin(uid, "router_add", f"{alias}@{host}")
            # Auto-enable DHCP Guard detector for the new router.
            # Firewall rules stay OFF until the user explicitly opts in,
            # since they can interfere with existing firewall setups.
            if ctx.guard_store is not None:
                try:
                    await ctx.guard_store.update(uid, alias, enabled=True)
                    result += (
                        "\n\n🛡 *DHCP Guard detector auto-enabled*\n"
                        "You'll be alerted if a DHCP starvation attack is detected.\n"
                        "Optionally, apply firewall rate-limit rules now:"
                    )
                    await msg.answer(
                        result, parse_mode="Markdown",
                        reply_markup=kb.post_add_router(),
                    )
                    return
                except Exception as e:
                    log.warning(f"Auto-enable DHCP Guard failed: {e}")
        await msg.answer(result, parse_mode="Markdown", reply_markup=kb.main_menu())

    # ── Firewall Add Rule FSM ───────────────────────────────────────────────
    elif state == "fw:add:src_ip":
        ctx.sessions.update_data(uid, src_address=text if text != "-" else "")
        ctx.sessions.set_state(uid, "fw:add:dst_ip")
        await msg.answer("Destination IP/subnet (or `-` to skip):", parse_mode="Markdown")

    elif state == "fw:add:dst_ip":
        ctx.sessions.update_data(uid, dst_address=text if text != "-" else "")
        ctx.sessions.set_state(uid, "fw:add:dst_port")
        await msg.answer("Destination port (or `-` to skip, e.g. `80`, `80-90`, `80,443`):", parse_mode="Markdown")

    elif state == "fw:add:dst_port":
        ctx.sessions.update_data(uid, dst_port=text if text != "-" else "")
        ctx.sessions.set_state(uid, "fw:add:comment")
        await msg.answer("Comment for this rule (or `-` to skip):", parse_mode="Markdown")

    elif state == "fw:add:comment":
        d = ctx.sessions.get_data(uid)
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
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
            rule_id = await r.add_firewall_filter(params)
            await msg.answer(f"✅ Firewall rule added! ID: `{rule_id}`", parse_mode="Markdown",
                             reply_markup=kb.firewall_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}", reply_markup=kb.firewall_menu())

    # ── Quick Block IP ──────────────────────────────────────────────────────
    elif state == "fw:block_ip":
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            id_ = await r.add_address_list_entry(text, "blacklist", "Blocked via Telegram")
            try:
                await r.add_firewall_filter({
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
        ctx.sessions.update_data(uid, mac=text)
        ctx.sessions.set_state(uid, "dhcp:add:ip")
        await msg.answer("IP address for this lease:\nExample: `192.168.88.50`", parse_mode="Markdown")

    elif state == "dhcp:add:ip":
        ctx.sessions.update_data(uid, ip=text)
        ctx.sessions.set_state(uid, "dhcp:add:comment")
        await msg.answer("Comment/hostname (or `-` to skip):", parse_mode="Markdown")

    elif state == "dhcp:add:comment":
        d = ctx.sessions.get_data(uid)
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            id_ = await r.add_dhcp_static_lease(d["mac"], d["ip"], text if text != "-" else "")
            await msg.answer(f"✅ Static lease added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.dhcp_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}", reply_markup=kb.dhcp_menu())

    # ── Wireless SSID Change ────────────────────────────────────────────────
    elif state.startswith("wifi:set_ssid:"):
        iface_name = state.split(":", 2)[2]
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            await r.set_wireless_ssid(iface_name, text)
            await msg.answer(f"✅ SSID changed to `{text}`", parse_mode="Markdown",
                             reply_markup=kb.wireless_iface_menu(iface_name, False))
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    elif state.startswith("wifi:set_pass:"):
        iface_name = state.split(":", 2)[2]
        if len(text) < 8:
            lang = get_lang(uid, ctx.sessions)
            await msg.answer(t("wifi.pass_short", lang), parse_mode="Markdown")
            return  # stay in same state
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            await r.set_wireless_password(iface_name, text)
            await msg.answer("✅ WiFi password updated.", reply_markup=kb.wireless_iface_menu(iface_name, False))
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── VPN Add Secret ──────────────────────────────────────────────────────
    elif state == "vpn:add:name":
        ctx.sessions.update_data(uid, vpn_name=text)
        ctx.sessions.set_state(uid, "vpn:add:pass")
        await msg.answer("Password for this VPN user:", parse_mode="Markdown")

    elif state == "vpn:add:pass":
        d = ctx.sessions.get_data(uid)
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            id_ = await r.add_vpn_secret(d["vpn_name"], text)
            await msg.answer(f"✅ VPN user `{d['vpn_name']}` added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.vpn_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}", reply_markup=kb.vpn_menu())

    # ── Add Route FSM ───────────────────────────────────────────────────────
    elif state == "route:add:dst":
        ctx.sessions.update_data(uid, dst=text)
        ctx.sessions.set_state(uid, "route:add:gw")
        await msg.answer("Gateway IP or interface name:\nExample: `10.0.0.1` or `ether1`", parse_mode="Markdown")

    elif state == "route:add:gw":
        d = ctx.sessions.get_data(uid)
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            id_ = await r.add_route(d["dst"], text)
            await msg.answer(f"✅ Route `{d['dst']} → {text}` added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.main_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── DNS Set Servers ─────────────────────────────────────────────────────
    elif state == "dns:set_servers":
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        servers = [s.strip() for s in text.replace(",", " ").split()]
        try:
            await r.set_dns_servers(servers)
            await msg.answer(f"✅ DNS servers updated: `{', '.join(servers)}`", parse_mode="Markdown",
                             reply_markup=kb.dns_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── Ping Tool ───────────────────────────────────────────────────────────
    elif state == "tool:ping":
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        lang = get_lang(uid, ctx.sessions)
        await msg.answer(t("tool.pinging", lang, target=text), parse_mode="Markdown")
        try:
            results = await r.ping(text, count=5)
            await msg.answer(fmt.fmt_ping(results, text), parse_mode="Markdown",
                             reply_markup=kb.tools_menu())
        except Exception as e:
            await msg.answer(f"❌ Ping error: {e}", reply_markup=kb.tools_menu())

    # ── Traceroute ──────────────────────────────────────────────────────────
    elif state == "tool:traceroute":
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        await msg.answer(f"🗺 Tracing route to `{text}`…", parse_mode="Markdown")
        try:
            hops = await r.traceroute(text)
            await msg.answer(fmt.fmt_traceroute(hops, text), parse_mode="Markdown",
                             reply_markup=kb.tools_menu())
        except Exception as e:
            await msg.answer(f"❌ Traceroute error: {e}", reply_markup=kb.tools_menu())

    # ── Bandwidth Test ──────────────────────────────────────────────────────
    elif state == "tool:bwtest":
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        await msg.answer(f"📊 Running bandwidth test to `{text}`… (5 sec)", parse_mode="Markdown")
        try:
            result = await r.bandwidth_test(text, duration=5)
            await msg.answer(fmt.fmt_bandwidth_test(result, text), parse_mode="Markdown",
                             reply_markup=kb.tools_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}", reply_markup=kb.tools_menu())

    # ── Add Bot User ────────────────────────────────────────────────────────
    elif state == "admin:add_user":
        ctx.sessions.clear_state(uid)
        try:
            new_uid = int(text)
            await ctx.rbac.set_role(new_uid, Role.VIEWER)
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
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            id_ = await r.add_address_list_entry(text, list_name, "Added via Telegram")
            await msg.answer(f"✅ `{text}` added to `{list_name}` (ID: {id_})", parse_mode="Markdown",
                             reply_markup=kb.firewall_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── IP Address Add ──────────────────────────────────────────────────────
    elif state.startswith("ip:add:"):
        iface = state.split(":", 2)[2]
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            id_ = await r.add_ip_address(text, iface)
            await msg.answer(f"✅ IP `{text}` added to `{iface}` (ID: {id_})", parse_mode="Markdown")
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── IP Address Add (two-step) ───────────────────────────────────────────
    elif state == "ip:add_addr":
        ctx.sessions.update_data(uid, ip_address=text)
        ctx.sessions.set_state(uid, "ip:add_addr:iface")
        await msg.answer("Interface name:\nExample: `ether1`, `bridge1`", parse_mode="Markdown")

    elif state == "ip:add_addr:iface":
        d = ctx.sessions.get_data(uid)
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            id_ = await r.add_ip_address(d["ip_address"], text)
            await msg.answer(f"✅ IP `{d['ip_address']}` added to `{text}`! ID: `{id_}`",
                             parse_mode="Markdown", reply_markup=kb.ip_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── Mangle Add (quick format) ────────────────────────────────────────
    elif state == "mangle:add":
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
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
            id_ = await r.add_firewall_mangle(params)
            await msg.answer(f"✅ Mangle rule added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.firewall_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── IP Pool Add ─────────────────────────────────────────────────────────
    elif state == "ip:pool:add:name":
        ctx.sessions.update_data(uid, pool_name=text)
        ctx.sessions.set_state(uid, "ip:pool:add:ranges")
        await msg.answer("Range(s) for this pool:\nExample: `192.168.100.10-192.168.100.200`",
                         parse_mode="Markdown")

    elif state == "ip:pool:add:ranges":
        d = ctx.sessions.get_data(uid)
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            id_ = await r.add_ip_pool(d["pool_name"], text)
            await msg.answer(f"✅ Pool `{d['pool_name']}` created! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.ip_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── Queue Add ───────────────────────────────────────────────────────────
    elif state == "queue:add:name":
        ctx.sessions.update_data(uid, q_name=text)
        ctx.sessions.set_state(uid, "queue:add:target")
        await msg.answer("Target (IP or subnet):\nExample: `192.168.88.100` or `192.168.88.0/24`",
                         parse_mode="Markdown")

    elif state == "queue:add:target":
        ctx.sessions.update_data(uid, q_target=text)
        ctx.sessions.set_state(uid, "queue:add:limit")
        await msg.answer("Max limit (down/up):\nExample: `10M/5M` or `0/0` for unlimited",
                         parse_mode="Markdown")

    elif state == "queue:add:limit":
        d = ctx.sessions.get_data(uid)
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            id_ = await r.add_simple_queue(d["q_name"], d["q_target"], text)
            await msg.answer(f"✅ Queue `{d['q_name']}` added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.queues_menu([]))
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── Hotspot User Add ────────────────────────────────────────────────────
    elif state == "hotspot:add:name":
        ctx.sessions.update_data(uid, hs_name=text)
        ctx.sessions.set_state(uid, "hotspot:add:pass")
        await msg.answer("Password for this hotspot user:", parse_mode="Markdown")

    elif state == "hotspot:add:pass":
        d = ctx.sessions.get_data(uid)
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            id_ = await r.add_hotspot_user(d["hs_name"], text)
            await msg.answer(f"✅ Hotspot user `{d['hs_name']}` added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.hotspot_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── VLAN Add ────────────────────────────────────────────────────────────
    elif state == "vlan:add:name":
        ctx.sessions.update_data(uid, vlan_name=text)
        ctx.sessions.set_state(uid, "vlan:add:id")
        await msg.answer("VLAN ID (1-4094):", parse_mode="Markdown")

    elif state == "vlan:add:id":
        ctx.sessions.update_data(uid, vlan_id=text)
        ctx.sessions.set_state(uid, "vlan:add:iface")
        await msg.answer("Parent interface:\nExample: `ether1`, `bridge1`", parse_mode="Markdown")

    elif state == "vlan:add:iface":
        d = ctx.sessions.get_data(uid)
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            id_ = await r.add_vlan(d["vlan_name"], int(d["vlan_id"]), text)
            await msg.answer(f"✅ VLAN `{d['vlan_id']}` ({d['vlan_name']}) created! ID: `{id_}`",
                             parse_mode="Markdown", reply_markup=kb.ip_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── NAT Add Rule FSM ────────────────────────────────────────────────────
    elif state == "nat:add:src_addr":
        ctx.sessions.update_data(uid, nat_src=text if text != "-" else "")
        ctx.sessions.set_state(uid, "nat:add:dst_port")
        await msg.answer("Destination port (or `-` to skip):\nExample: `80`, `443`", parse_mode="Markdown")

    elif state == "nat:add:dst_port":
        ctx.sessions.update_data(uid, nat_dst_port=text if text != "-" else "")
        ctx.sessions.set_state(uid, "nat:add:to_addr")
        await msg.answer("To-address (or `-` to skip):\nExample: `192.168.88.10`", parse_mode="Markdown")

    elif state == "nat:add:to_addr":
        ctx.sessions.update_data(uid, nat_to_addr=text if text != "-" else "")
        ctx.sessions.set_state(uid, "nat:add:to_port")
        await msg.answer("To-ports (or `-` to skip):\nExample: `8080`", parse_mode="Markdown")

    elif state == "nat:add:to_port":
        d = ctx.sessions.get_data(uid)
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
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
            id_ = await r.add_firewall_nat(params)
            await msg.answer(f"✅ NAT rule added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.firewall_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}", reply_markup=kb.firewall_menu())

    # ── NTP Set Servers ─────────────────────────────────────────────────────
    elif state == "ntp:set_servers":
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        parts_ntp = text.replace(",", " ").split()
        primary = parts_ntp[0] if parts_ntp else "pool.ntp.org"
        secondary = parts_ntp[1] if len(parts_ntp) > 1 else ""
        try:
            await r.set_ntp_servers(primary, secondary)
            await msg.answer(f"✅ NTP servers updated: `{primary}`" +
                             (f", `{secondary}`" if secondary else ""),
                             parse_mode="Markdown", reply_markup=kb.ntp_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── WireGuard Add Peer ──────────────────────────────────────────────────
    elif state.startswith("wg:add_peer:pubkey:"):
        iface = state.split(":", 3)[3]
        ctx.sessions.update_data(uid, wg_iface=iface, wg_pubkey=text)
        ctx.sessions.set_state(uid, "wg:add_peer:allowed_addr")
        await msg.answer("Allowed address(es):\nExample: `10.0.0.2/32`", parse_mode="Markdown")

    elif state == "wg:add_peer:allowed_addr":
        ctx.sessions.update_data(uid, wg_allowed=text)
        ctx.sessions.set_state(uid, "wg:add_peer:endpoint")
        await msg.answer("Endpoint host:port (or `-` to skip):\nExample: `1.2.3.4:51820`",
                         parse_mode="Markdown")

    elif state == "wg:add_peer:endpoint":
        d = ctx.sessions.get_data(uid)
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
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
            id_ = await r.add_wireguard_peer(
                d["wg_iface"], d["wg_pubkey"], d["wg_allowed"],
                endpoint=endpoint, endpoint_port=endpoint_port,
            )
            await msg.answer(f"✅ WireGuard peer added! ID: `{id_}`", parse_mode="Markdown",
                             reply_markup=kb.vpn_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── Router User Add ─────────────────────────────────────────────────────
    elif state == "sys:add_user:name":
        ctx.sessions.update_data(uid, r_user=text)
        ctx.sessions.set_state(uid, "sys:add_user:pass")
        await msg.answer("Password for this router user:", parse_mode="Markdown")

    elif state == "sys:add_user:pass":
        d = ctx.sessions.get_data(uid)
        ctx.sessions.clear_state(uid)
        r = await require_router(msg, ctx.rm)
        if not r:
            return
        try:
            id_ = await r.add_user(d["r_user"], text, "read")
            await msg.answer(f"✅ Router user `{d['r_user']}` added (read group). ID: `{id_}`",
                             parse_mode="Markdown", reply_markup=kb.system_menu())
        except Exception as e:
            await msg.answer(f"❌ Error: {e}")

    # ── Global Search (qol:find) ────────────────────────────────────────────
    elif state == "qol:find":
        ctx.sessions.clear_state(uid)
        from handlers.qol import _do_search  # avoid circular at module level
        await _do_search(msg, text)

    else:
        ctx.sessions.clear_state(uid)
