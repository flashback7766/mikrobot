"""
Text formatters – convert router data dicts to human-readable Telegram messages.
All output is Markdown-safe.
"""

from datetime import datetime
from core.log_streamer import TOPIC_EMOJI


def _safe(v) -> str:
    return str(v) if v is not None else "—"


def _yn(v) -> str:
    return "✅" if str(v).lower() in ("yes", "true", "1") else "❌"


def _fmt_bytes(b) -> str:
    b = int(b)
    if b < 1024:
        return f"{b} B"
    elif b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 ** 3:
        return f"{b / 1024 ** 2:.1f} MB"
    else:
        return f"{b / 1024 ** 3:.2f} GB"


def _fmt_bps(bps) -> str:
    bps = int(bps)
    if bps < 1000:
        return f"{bps} bps"
    elif bps < 1_000_000:
        return f"{bps / 1000:.1f} Kbps"
    elif bps < 1_000_000_000:
        return f"{bps / 1_000_000:.1f} Mbps"
    else:
        return f"{bps / 1_000_000_000:.2f} Gbps"


# ─── System ───────────────────────────────────────────────────────────────────

def fmt_system(res: dict, identity: str, health: dict | None = None) -> str:
    total_mem = int(res.get("total-memory", 1))
    free_mem = int(res.get("free-memory", 0))
    used_mem = total_mem - free_mem
    mem_pct = int(used_mem / total_mem * 100) if total_mem else 0

    total_hdd = int(res.get("total-hdd-space", 1))
    free_hdd = int(res.get("free-hdd-space", 0))
    used_hdd = total_hdd - free_hdd
    hdd_pct = int(used_hdd / total_hdd * 100) if total_hdd else 0

    cpu = res.get("cpu-load", "?")
    uptime = res.get("uptime", "?")
    version = res.get("version", "?")
    board = res.get("board-name", "?")
    arch = res.get("architecture-name", "?")

    bar_len = 10

    def bar(pct):
        filled = int(pct * bar_len / 100)
        return "█" * filled + "░" * (bar_len - filled)

    lines = [
        f"🖥 *{identity}*",
        f"📋 RouterOS `{version}`",
        f"🖩 Board: `{board}` ({arch})",
        f"⏱ Uptime: `{uptime}`",
        "",
        f"⚡ CPU: `{cpu}%` [{bar(int(cpu) if str(cpu).isdigit() else 0)}]",
        f"💾 RAM: `{mem_pct}%` [{bar(mem_pct)}] ({_fmt_bytes(used_mem)}/{_fmt_bytes(total_mem)})",
        f"💿 Disk: `{hdd_pct}%` [{bar(hdd_pct)}] ({_fmt_bytes(used_hdd)}/{_fmt_bytes(total_hdd)})",
    ]

    if health:
        temp = health.get("temperature") or health.get("cpu-temperature")
        if temp:
            lines.append(f"🌡 Temp: `{temp}°C`")

    return "\n".join(lines)


def fmt_routerboard(rb: dict) -> str:
    if not rb:
        return "ℹ️ Not a RouterBoard device."
    return (
        f"🖥 *RouterBoard Info*\n"
        f"Model: `{rb.get('model', rb.get('board-name', '?'))}`\n"
        f"Serial: `{rb.get('serial-number', '?')}`\n"
        f"Firmware: `{rb.get('current-firmware', '?')}`\n"
        f"Factory FW: `{rb.get('factory-firmware', '?')}`\n"
        f"Upgrade FW: `{rb.get('upgrade-firmware', '?')}`"
    )


# ─── Interfaces ───────────────────────────────────────────────────────────────

def fmt_interfaces(interfaces: list[dict]) -> str:
    lines = ["🔌 *Interfaces*\n"]
    for iface in interfaces:
        name = iface.get("name", "?")
        running = iface.get("running", "false") == "true"
        disabled = iface.get("disabled", "false") == "true"
        rx = _fmt_bytes(iface.get("rx-byte", 0))
        tx = _fmt_bytes(iface.get("tx-byte", 0))
        mac = iface.get("mac-address", "")
        comment = iface.get("comment", "")

        icon = "🟢" if running else ("⛔" if disabled else "🔴")
        lines.append(
            f"{icon} `{name}`{f' — {comment}' if comment else ''}\n"
            f"   ↓ {rx}  ↑ {tx}"
            + (f"\n   MAC: `{mac}`" if mac else "")
        )
    return "\n\n".join(lines)


def fmt_interface_detail(iface: dict) -> str:
    name = iface.get("name", "?")
    type_ = iface.get("type", "?")
    running = iface.get("running", "false") == "true"
    disabled = iface.get("disabled", "false") == "true"
    mtu = iface.get("mtu", "?")
    rx = _fmt_bytes(iface.get("rx-byte", 0))
    tx = _fmt_bytes(iface.get("tx-byte", 0))
    rx_pkt = iface.get("rx-packet", "?")
    tx_pkt = iface.get("tx-packet", "?")
    rx_err = iface.get("rx-error", "0")
    tx_err = iface.get("tx-error", "0")
    mac = iface.get("mac-address", "?")
    comment = iface.get("comment", "")

    icon = "🟢" if running else ("⛔" if disabled else "🔴")
    return (
        f"{icon} *Interface: {name}*\n"
        f"Type: `{type_}` | MTU: `{mtu}`\n"
        f"MAC: `{mac}`\n"
        f"{f'Comment: {comment}' if comment else ''}\n\n"
        f"📥 RX: `{rx}` ({rx_pkt} pkts, {rx_err} err)\n"
        f"📤 TX: `{tx}` ({tx_pkt} pkts, {tx_err} err)"
    )


def fmt_traffic(t: dict) -> str:
    name = t.get("name", "?")
    rx = _fmt_bps(t.get("rx-bits-per-second", 0))
    tx = _fmt_bps(t.get("tx-bits-per-second", 0))
    rx_pps = t.get("rx-packets-per-second", "?")
    tx_pps = t.get("tx-packets-per-second", "?")
    return (
        f"📊 *Traffic: {name}*\n"
        f"↓ RX: `{rx}` ({rx_pps} pps)\n"
        f"↑ TX: `{tx}` ({tx_pps} pps)"
    )


# ─── Firewall ─────────────────────────────────────────────────────────────────

def fmt_firewall_rule(rule: dict) -> str:
    id_ = rule.get(".id", "?")
    chain = rule.get("chain", "?")
    action = rule.get("action", "?")
    disabled = rule.get("disabled", "false") == "true"
    proto = rule.get("protocol", "")
    src_ip = rule.get("src-address", "")
    dst_ip = rule.get("dst-address", "")
    src_port = rule.get("src-port", "")
    dst_port = rule.get("dst-port", "")
    conn_state = rule.get("connection-state", "")
    comment = rule.get("comment", "")
    bytes_ = _fmt_bytes(rule.get("bytes", 0))
    packets = rule.get("packets", "?")

    action_icons = {
        "accept": "✅",
        "drop": "🚫",
        "reject": "↩️",
        "log": "📋",
        "passthrough": "➡️",
    }
    a_icon = action_icons.get(action, "❓")

    lines = [
        f"{a_icon} *Rule ID: {id_}*" + (" ⛔ DISABLED" if disabled else ""),
        f"Chain: `{chain}` | Action: `{action}`",
    ]
    if proto:
        lines.append(f"Protocol: `{proto}`")
    if src_ip:
        lines.append(f"Src IP: `{src_ip}`" + (f":{src_port}" if src_port else ""))
    if dst_ip:
        lines.append(f"Dst IP: `{dst_ip}`" + (f":{dst_port}" if dst_port else ""))
    if conn_state:
        lines.append(f"State: `{conn_state}`")
    if comment:
        lines.append(f"Comment: _{comment}_")
    lines.append(f"Stats: `{bytes_}` / `{packets}` pkts")
    return "\n".join(lines)


def fmt_nat_rule(rule: dict) -> str:
    id_ = rule.get(".id", "?")
    chain = rule.get("chain", "?")
    action = rule.get("action", "?")
    dst_addr = rule.get("dst-address", "")
    to_addr = rule.get("to-addresses", "")
    to_port = rule.get("to-ports", "")
    out_iface = rule.get("out-interface", "")
    in_iface = rule.get("in-interface", "")
    comment = rule.get("comment", "")
    bytes_ = _fmt_bytes(rule.get("bytes", 0))
    return (
        f"🔀 *NAT Rule ID: {id_}*\n"
        f"Chain: `{chain}` | Action: `{action}`\n"
        + (f"Dst: `{dst_addr}`\n" if dst_addr else "")
        + (f"To: `{to_addr}`" + (f":{to_port}" if to_port else "") + "\n" if to_addr else "")
        + (f"Out: `{out_iface}`\n" if out_iface else "")
        + (f"In: `{in_iface}`\n" if in_iface else "")
        + (f"Comment: _{comment}_\n" if comment else "")
        + f"Stats: `{bytes_}`"
    )


def fmt_address_list(entries: list[dict]) -> str:
    if not entries:
        return "📋 *Address List* — empty"
    lines = ["📋 *Address List Entries*\n"]
    for e in entries:
        id_ = e.get(".id", "?")
        list_ = e.get("list", "?")
        address = e.get("address", "?")
        comment = e.get("comment", "")
        timeout = e.get("timeout", "")
        lines.append(
            f"• `{address}` → `{list_}`"
            + (f" _{comment}_" if comment else "")
            + (f" (expires: {timeout})" if timeout else "")
            + f" [ID: {id_}]"
        )
    return "\n".join(lines)


# ─── DHCP ─────────────────────────────────────────────────────────────────────

def fmt_dhcp_leases(leases: list[dict], page: int = 0, per_page: int = 6) -> str:
    total = len(leases)
    start = page * per_page
    page_leases = leases[start:start + per_page]
    lines = [f"📡 *DHCP Leases* ({total} total, page {page+1})\n"]
    for lease in page_leases:
        ip = lease.get("address", "?")
        mac = lease.get("mac-address", "?")
        host = lease.get("host-name", "")
        type_ = lease.get("type", "dynamic")
        status = lease.get("status", "?")
        expires = lease.get("expires-after", "")
        icon = "📌" if type_ == "static" else "🔄"
        lines.append(
            f"{icon} `{ip}` — `{mac}`\n"
            f"   Host: `{host or '?'}` | Status: {status}"
            + (f" | Expires: {expires}" if expires and expires != "never" else "")
        )
    return "\n\n".join(lines)


def fmt_dhcp_lease_detail(lease: dict) -> str:
    ip = lease.get("address", "?")
    mac = lease.get("mac-address", "?")
    host = lease.get("host-name", "?")
    type_ = lease.get("type", "dynamic")
    status = lease.get("status", "?")
    expires = lease.get("expires-after", "never")
    comment = lease.get("comment", "")
    return (
        f"📡 *DHCP Lease Detail*\n"
        f"IP: `{ip}`\n"
        f"MAC: `{mac}`\n"
        f"Hostname: `{host}`\n"
        f"Type: `{type_}`\n"
        f"Status: `{status}`\n"
        f"Expires: `{expires}`"
        + (f"\nComment: _{comment}_" if comment else "")
    )


# ─── Wireless ─────────────────────────────────────────────────────────────────

def fmt_wireless_clients(clients: list[dict]) -> str:
    if not clients:
        return "📶 *WiFi Clients* — none connected"
    lines = [f"📶 *WiFi Clients* ({len(clients)} connected)\n"]
    for c in clients:
        mac = c.get("mac-address", "?")
        iface = c.get("interface", "?")
        signal = c.get("signal-strength", "?")
        tx_rate = c.get("tx-rate", "?")
        rx_rate = c.get("rx-rate", "?")
        uptime = c.get("uptime", "?")
        comment = c.get("comment", "")
        lines.append(
            f"📱 `{mac}`{f' ({comment})' if comment else ''}\n"
            f"   [{iface}] Signal: `{signal}` | ↑{tx_rate} ↓{rx_rate} | Up: {uptime}"
        )
    return "\n\n".join(lines)


def fmt_wireless_scan(results: list[dict]) -> str:
    if not results:
        return "📡 *WiFi Scan* — no APs found"
    lines = [f"📡 *WiFi Scan Results* ({len(results)} APs)\n"]
    for ap in sorted(results, key=lambda x: int(x.get("signal", "-999")), reverse=True):
        ssid = ap.get("ssid", "(hidden)")
        bssid = ap.get("bssid", "?")
        signal = ap.get("signal", "?")
        channel = ap.get("channel", "?")
        security = ap.get("security", "none")
        bars = "█" * max(0, min(5, (int(signal) + 90) // 10)) if str(signal).lstrip("-").isdigit() else "?"
        lines.append(f"📶 `{ssid}` {bars}\n   BSSID: `{bssid}` | Ch: {channel} | {security} | `{signal}dBm`")
    return "\n\n".join(lines)


# ─── VPN ──────────────────────────────────────────────────────────────────────

def fmt_vpn_status(pppoe: list[dict], l2tp: dict, ovpn: dict) -> str:
    lines = ["🔒 *VPN Status*\n"]
    lines.append(f"PPPoE Active Sessions: `{len(pppoe)}`")
    if pppoe:
        for s in pppoe[:3]:
            lines.append(f"  • `{s.get('name', '?')}` — `{s.get('address', '?')}` [{s.get('uptime', '?')}]")
    lines.append(f"\nL2TP Server: {'✅ Enabled' if l2tp.get('enabled') == 'yes' else '❌ Disabled'}")
    lines.append(f"OpenVPN Server: {'✅ Enabled' if ovpn.get('enabled') == 'yes' else '❌ Disabled'}")
    return "\n".join(lines)


def fmt_vpn_secret(secret: dict) -> str:
    name = secret.get("name", "?")
    service = secret.get("service", "any")
    profile = secret.get("profile", "default")
    routes = secret.get("routes", "")
    limit = secret.get("limit-bytes-in", "")
    return (
        f"👤 *PPP Secret: {name}*\n"
        f"Service: `{service}`\n"
        f"Profile: `{profile}`"
        + (f"\nRoutes: `{routes}`" if routes else "")
        + (f"\nBW Limit In: `{limit}`" if limit else "")
    )


# ─── Logs ─────────────────────────────────────────────────────────────────────


def fmt_logs(entries: list[dict]) -> str:
    if not entries:
        return "📋 *Logs* — empty"
    lines = [f"📋 *Logs* (last {len(entries)})\n"]
    for e in entries:
        time_ = e.get("time", "")
        topics = e.get("topics", "")
        msg = e.get("message", "")
        topic_list = [t.strip() for t in topics.split(",")]
        emoji = next((TOPIC_EMOJI[t] for t in topic_list if t in TOPIC_EMOJI), "📋")
        lines.append(f"{emoji} `{time_}` {msg}")
    return "\n".join(lines)


# ─── Routes ───────────────────────────────────────────────────────────────────

def fmt_routes(routes: list[dict]) -> str:
    if not routes:
        return "🗺 *Routes* — empty"
    lines = [f"🗺 *Routing Table* ({len(routes)} entries)\n"]
    for r in routes:
        dst = r.get("dst-address", "?")
        gw = r.get("gateway", "?")
        dist = r.get("distance", "?")
        active = r.get("active", "false") == "true"
        static = r.get("static", r.get(".type", ""))
        ipv6 = r.get("_ipv6", False)
        icon = "🟢" if active else "🔴"
        tag = "🌐" if ipv6 else ""
        lines.append(f"{icon}{tag} `{dst}` → `{gw}` (dist: {dist})")
    return "\n".join(lines)


# ─── DNS ──────────────────────────────────────────────────────────────────────

def fmt_dns(settings: dict) -> str:
    servers = settings.get("servers", "none")
    remote = settings.get("allow-remote-requests", "no")
    cache_size = settings.get("cache-size", "?")
    cache_ttl = settings.get("cache-max-ttl", "?")
    return (
        f"🌐 *DNS Settings*\n"
        f"Servers: `{servers}`\n"
        f"Allow Remote Requests: {_yn(remote == 'yes')}\n"
        f"Cache Size: `{cache_size}` KB\n"
        f"Max TTL: `{cache_ttl}`"
    )


def fmt_dns_cache(entries: list[dict]) -> str:
    if not entries:
        return "🌐 *DNS Cache* — empty"
    lines = [f"🌐 *DNS Cache* ({len(entries)} entries)\n"]
    for e in entries[:20]:
        name = e.get("name", "?")
        addr = e.get("address", "?")
        ttl = e.get("ttl", "?")
        type_ = e.get("type", "A")
        lines.append(f"• `{name}` → `{addr}` [{type_}] TTL:{ttl}")
    return "\n".join(lines)


# ─── Tools ────────────────────────────────────────────────────────────────────

def fmt_ping(results: list[dict], address: str) -> str:
    sent = len(results)
    received = sum(1 for r in results if r.get("received", "0") != "0")
    loss = int((sent - received) / sent * 100) if sent else 100
    times = [int(r.get("time", 0)) for r in results if r.get("received", "0") != "0"]
    avg = sum(times) // len(times) if times else 0
    min_ = min(times) if times else 0
    max_ = max(times) if times else 0

    lines = [
        f"🏓 *Ping: {address}*\n",
        f"Sent: {sent} | Received: {received} | Loss: {loss}%",
        f"RTT min/avg/max: {min_}/{avg}/{max_} ms",
        "",
    ]
    for r in results:
        recv = r.get("received", "0") != "0"
        time_ = r.get("time", "?")
        ttl = r.get("ttl", "?")
        lines.append(
            ("✅" if recv else "❌") +
            (f" {time_}ms TTL={ttl}" if recv else " Timeout")
        )
    return "\n".join(lines)


def fmt_traceroute(hops: list[dict], address: str) -> str:
    lines = [f"🗺 *Traceroute: {address}*\n"]
    for hop in hops:
        n = hop.get("count", "?")
        addr = hop.get("address", "???")
        time_ = hop.get("time", "?")
        status = hop.get("status", "")
        if status == "timed-out" or addr == "0.0.0.0":
            lines.append(f"`{n:>2}.` * * * (timed out)")
        else:
            lines.append(f"`{n:>2}.` `{addr}` — {time_}ms")
    return "\n".join(lines)


def fmt_bandwidth_test(result: dict, address: str) -> str:
    tx = _fmt_bps(result.get("tx-total-average", 0))
    rx = _fmt_bps(result.get("rx-total-average", 0))
    lost = result.get("lost-packets", "0")
    return (
        f"📊 *Bandwidth Test: {address}*\n"
        f"↑ TX: `{tx}`\n"
        f"↓ RX: `{rx}`\n"
        f"Lost packets: `{lost}`"
    )


# ─── Files ────────────────────────────────────────────────────────────────────

def fmt_files(files: list[dict]) -> str:
    if not files:
        return "📁 *Files* — empty"
    lines = [f"📁 *Router Files* ({len(files)})\n"]
    for f in files:
        name = f.get("name", "?")
        size = int(f.get("size", 0))
        created = f.get("creation-time", "?")
        type_ = f.get("type", "")
        icon = {"backup": "💾", "script": "📜", "package": "📦"}.get(type_, "📄")
        lines.append(f"{icon} `{name}`\n   {_fmt_bytes(size)} | {created}")
    # Telegram message limit is 4096 chars — truncate safely
    result = "\n\n".join(lines)
    if len(result) > 3800:
        result = result[:3800]
        # Don't leave a broken backtick open
        if result.count("`") % 2 != 0:
            result = result.rsplit("`", 1)[0]
        result += f"\n\n…and more files (showing first {len(lines)-1})"
    return result


# ─── Users ────────────────────────────────────────────────────────────────────

def fmt_router_users(users: list[dict]) -> str:
    if not users:
        return "👤 *Router Users* — none"
    lines = [f"👤 *Router Users* ({len(users)})\n"]
    for u in users:
        name = u.get("name", "?")
        group = u.get("group", "?")
        last = u.get("last-logged-in", "never")
        addr = u.get("address", "")
        lines.append(
            f"• `{name}` [{group}]"
            + (f" | Last: {last}" if last != "never" else "")
            + (f" | IP: {addr}" if addr else "")
        )
    return "\n".join(lines)


# ─── WireGuard ────────────────────────────────────────────────────────────────

def fmt_wireguard_peers(peers: list[dict]) -> str:
    if not peers:
        return "🔒 *WireGuard Peers* — none configured"
    lines = [f"🔒 *WireGuard Peers* ({len(peers)})\n"]
    for p in peers:
        iface = p.get("interface", "?")
        pub_key = p.get("public-key", "?")[:20] + "…"
        allowed = p.get("allowed-address", "?")
        endpoint = p.get("endpoint-address", "")
        endpoint_port = p.get("endpoint-port", "")
        last_hs = p.get("last-handshake", "never")
        comment = p.get("comment", "")
        lines.append(
            f"👤 {comment or pub_key}\n"
            f"   [{iface}] `{allowed}`"
            + (f"\n   Endpoint: `{endpoint}:{endpoint_port}`" if endpoint else "")
            + f"\n   Last handshake: {last_hs}"
        )
    return "\n\n".join(lines)


# ─── IP Addresses ─────────────────────────────────────────────────────────────

def fmt_ip_addresses(addresses: list[dict]) -> str:
    if not addresses:
        return "📍 *IP Addresses* — none configured"
    lines = [f"📍 *IP Addresses* ({len(addresses)})\n"]
    for a in addresses:
        addr = a.get("address", "?")
        iface = a.get("interface", "?")
        network = a.get("network", "?")
        invalid = a.get("invalid", "false") == "true"
        dynamic = a.get("dynamic", "false") == "true"
        flags = []
        if dynamic:
            flags.append("dynamic")
        if invalid:
            flags.append("⚠️ invalid")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"• `{addr}` on `{iface}` (net: {network}){flag_str}")
    return "\n".join(lines)


# ─── ARP Table ────────────────────────────────────────────────────────────────

def fmt_arp(entries: list[dict]) -> str:
    if not entries:
        return "🔁 *ARP Table* — empty"
    lines = [f"🔁 *ARP Table* ({len(entries)} entries)\n"]
    for e in entries:
        ip = e.get("address", "?")
        mac = e.get("mac-address", "?")
        iface = e.get("interface", "?")
        status = e.get("status", "?")
        icon = "🟢" if status == "reachable" else "🔴" if status == "failed" else "⚪"
        lines.append(f"{icon} `{ip}` → `{mac}` [{iface}]")
    return "\n".join(lines)


# ─── IP Pools ─────────────────────────────────────────────────────────────────

def fmt_ip_pools(pools: list[dict]) -> str:
    if not pools:
        return "🏊 *IP Pools* — none configured"
    lines = [f"🏊 *IP Pools* ({len(pools)})\n"]
    for p in pools:
        name = p.get("name", "?")
        ranges = p.get("ranges", "?")
        next_pool = p.get("next-pool", "")
        lines.append(f"• `{name}`: `{ranges}`" + (f" → {next_pool}" if next_pool else ""))
    return "\n".join(lines)


# ─── Queues / QoS ─────────────────────────────────────────────────────────────

def fmt_queues(queues: list[dict]) -> str:
    if not queues:
        return "📊 *Simple Queues* — none configured"
    lines = [f"📊 *Simple Queues* ({len(queues)})\n"]
    for q in queues:
        name = q.get("name", "?")
        target = q.get("target", "?")
        max_limit = q.get("max-limit", "0/0")
        disabled = q.get("disabled", "false") == "true"
        icon = "⛔" if disabled else "🟢"
        comment = q.get("comment", "")
        lines.append(
            f"{icon} `{name}`\n"
            f"   Target: `{target}` | Limit: `{max_limit}`"
            + (f" | {comment}" if comment else "")
        )
    return "\n\n".join(lines)


def fmt_queue_detail(q: dict) -> str:
    name = q.get("name", "?")
    target = q.get("target", "?")
    max_limit = q.get("max-limit", "0/0")
    burst_limit = q.get("burst-limit", "0/0")
    burst_time = q.get("burst-time", "0/0s")
    priority = q.get("priority", "8/8")
    disabled = q.get("disabled", "false") == "true"
    return (
        f"📊 *Queue: {name}*\n"
        f"Target: `{target}`\n"
        f"Max Limit: `{max_limit}`\n"
        f"Burst Limit: `{burst_limit}`\n"
        f"Burst Time: `{burst_time}`\n"
        f"Priority: `{priority}`\n"
        f"Status: {'⛔ Disabled' if disabled else '✅ Active'}"
    )


# ─── Hotspot ──────────────────────────────────────────────────────────────────

def fmt_hotspot_users(users: list[dict]) -> str:
    if not users:
        return "🔥 *Hotspot Users* — none configured"
    lines = [f"🔥 *Hotspot Users* ({len(users)})\n"]
    for u in users:
        name = u.get("name", "?")
        profile = u.get("profile", "default")
        limit_uptime = u.get("limit-uptime", "")
        limit_bytes = u.get("limit-bytes-total", "")
        lines.append(
            f"• `{name}` [{profile}]"
            + (f" | Uptime: {limit_uptime}" if limit_uptime else "")
            + (f" | Quota: {int(limit_bytes)//1024//1024}MB" if limit_bytes and limit_bytes != "0" else "")
        )
    return "\n".join(lines)


def fmt_hotspot_active(sessions: list[dict]) -> str:
    if not sessions:
        return "🔥 *Hotspot* — no active sessions"
    lines = [f"🔥 *Active Sessions* ({len(sessions)})\n"]
    for s in sessions:
        user = s.get("user", "?")
        ip = s.get("address", "?")
        mac = s.get("mac-address", "?")
        uptime = s.get("uptime", "?")
        rx = s.get("bytes-in", "0")
        tx = s.get("bytes-out", "0")
        lines.append(
            f"👤 `{user}` — `{ip}`\n"
            f"   MAC: `{mac}` | Up: {uptime}\n"
            f"   ↓ {int(rx)//1024}KB ↑ {int(tx)//1024}KB"
        )
    return "\n\n".join(lines)


# ─── Scripts ──────────────────────────────────────────────────────────────────

def fmt_scripts(scripts: list[dict]) -> str:
    if not scripts:
        return "📜 *Scripts* — none configured"
    lines = [f"📜 *Scripts* ({len(scripts)})\n"]
    for s in scripts:
        name = s.get("name", "?")
        last_run = s.get("last-started", "never")
        run_count = s.get("run-count", "0")
        comment = s.get("comment", "")
        lines.append(
            f"• `{name}` | Runs: {run_count} | Last: {last_run}"
            + (f"\n  {comment}" if comment else "")
        )
    return "\n".join(lines)


def fmt_script_detail(s: dict) -> str:
    name = s.get("name", "?")
    source = s.get("source", "")[:500]
    last_run = s.get("last-started", "never")
    run_count = s.get("run-count", "0")
    comment = s.get("comment", "")
    return (
        f"📜 *Script: {name}*\n"
        f"Runs: {run_count} | Last: {last_run}\n"
        + (f"Comment: {comment}\n" if comment else "")
        + f"\n```\n{source}{'...' if len(s.get('source',''))>500 else ''}\n```"
    )


# ─── Bridge ───────────────────────────────────────────────────────────────────

def fmt_bridges(bridges: list[dict], ports: list[dict]) -> str:
    if not bridges:
        return "🌉 *Bridges* — none configured"
    lines = [f"🌉 *Bridges* ({len(bridges)})\n"]
    for b in bridges:
        name = b.get("name", "?")
        running = b.get("running", "false") == "true"
        stp = b.get("protocol-mode", "none")
        icon = "🟢" if running else "🔴"
        bridge_ports = [p.get("interface", "?") for p in ports if p.get("bridge") == name]
        lines.append(
            f"{icon} `{name}` [STP: {stp}]\n"
            f"   Ports: {', '.join(bridge_ports) if bridge_ports else 'none'}"
        )
    return "\n\n".join(lines)


def fmt_vlans(vlans: list[dict]) -> str:
    if not vlans:
        return "🏷 *VLANs* — none configured"
    lines = [f"🏷 *VLANs* ({len(vlans)})\n"]
    for v in vlans:
        name = v.get("name", "?")
        vid = v.get("vlan-id", "?")
        iface = v.get("interface", "?")
        running = v.get("running", "false") == "true"
        icon = "🟢" if running else "🔴"
        lines.append(f"{icon} `VLAN {vid}` ({name}) on `{iface}`")
    return "\n".join(lines)


# ─── Mangle ───────────────────────────────────────────────────────────────────

def fmt_mangle_rules(rules: list[dict]) -> str:
    if not rules:
        return "🔀 *Mangle Rules* — none configured"
    lines = [f"🔀 *Mangle Rules* ({len(rules)})\n"]
    for r in rules:
        chain = r.get("chain", "?")
        action = r.get("action", "?")
        id_ = r.get(".id", "?")
        disabled = r.get("disabled", "false") == "true"
        src = r.get("src-address", "")
        dst = r.get("dst-address", "")
        comment = r.get("comment", "")
        icon = "⛔" if disabled else "🟠"
        match_str = " | ".join(filter(None, [f"src:{src}" if src else "", f"dst:{dst}" if dst else ""]))
        lines.append(
            f"{icon} `{id_}` [{chain}] → `{action}`"
            + (f"\n   {match_str}" if match_str else "")
            + (f" | {comment}" if comment else "")
        )
    return "\n".join(lines)


# ─── NAT Detail ───────────────────────────────────────────────────────────────

def fmt_nat_detail(r: dict) -> str:
    chain = r.get("chain", "?")
    action = r.get("action", "?")
    src = r.get("src-address", "any")
    dst = r.get("dst-address", "any")
    to_addr = r.get("to-addresses", "")
    to_ports = r.get("to-ports", "")
    proto = r.get("protocol", "any")
    dst_port = r.get("dst-port", "")
    in_iface = r.get("in-interface", "")
    out_iface = r.get("out-interface", "")
    comment = r.get("comment", "")
    return (
        f"🔀 *NAT Rule*\n"
        f"Chain: `{chain}` | Action: `{action}`\n"
        f"Protocol: `{proto}`\n"
        f"Src: `{src}` → Dst: `{dst}`"
        + (f"\nDst Port: `{dst_port}`" if dst_port else "")
        + (f"\nTo: `{to_addr}`" if to_addr else "")
        + (f" Port: `{to_ports}`" if to_ports else "")
        + (f"\nIn: `{in_iface}`" if in_iface else "")
        + (f"\nOut: `{out_iface}`" if out_iface else "")
        + (f"\n💬 {comment}" if comment else "")
    )


# ─── Certificates ─────────────────────────────────────────────────────────────

def fmt_certificates(certs: list[dict]) -> str:
    if not certs:
        return "🔐 *Certificates* — none installed"
    lines = [f"🔐 *Certificates* ({len(certs)})\n"]
    for c in certs:
        name = c.get("name", "?")
        common_name = c.get("common-name", "?")
        expires = c.get("invalid-after", "?")
        fingerprint = c.get("fingerprint", "?")[:20]
        trusted = c.get("trusted", "no")
        icon = "✅" if trusted == "yes" else "⚠️"
        lines.append(
            f"{icon} `{name}` ({common_name})\n"
            f"   Expires: {expires}\n"
            f"   SHA: `{fingerprint}…`"
        )
    return "\n\n".join(lines)


# ─── NTP ──────────────────────────────────────────────────────────────────────

def fmt_ntp(ntp: dict) -> str:
    enabled = ntp.get("enabled", "no")
    primary = ntp.get("primary-ntp", ntp.get("servers", "?"))
    secondary = ntp.get("secondary-ntp", "")
    last_sync = ntp.get("last-update-from", "never")
    drift = ntp.get("offset", "?")
    return (
        f"🕐 *NTP Client*\n"
        f"Enabled: {'✅' if enabled == 'yes' else '❌'}\n"
        f"Primary: `{primary}`"
        + (f"\nSecondary: `{secondary}`" if secondary else "")
        + f"\nLast sync: `{last_sync}`"
        + (f"\nOffset: `{drift}ms`" if drift and drift != "?" else "")
    )


# ─── PPP Profiles ─────────────────────────────────────────────────────────────

def fmt_ppp_profiles(profiles: list[dict]) -> str:
    if not profiles:
        return "📋 *PPP Profiles* — none"
    lines = [f"📋 *PPP Profiles* ({len(profiles)})\n"]
    for p in profiles:
        name = p.get("name", "?")
        local = p.get("local-address", "")
        remote = p.get("remote-address", "")
        rate_limit = p.get("rate-limit", "")
        lines.append(
            f"• `{name}`"
            + (f" | Local: {local}" if local else "")
            + (f" | Pool: {remote}" if remote else "")
            + (f" | Limit: {rate_limit}" if rate_limit else "")
        )
    return "\n".join(lines)
