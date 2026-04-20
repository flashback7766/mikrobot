"""
Keyboard builder – all inline keyboards for the bot UI.
Uses aiogram 3.x InlineKeyboardBuilder.

Menu structure:
  Main Menu
  ├── 📊 System          → info, health, reboot, scheduler, NTP, certs, users
  ├── 🔌 Interfaces      → list, traffic, toggle, eth stats
  ├── 🛡 Firewall        → filter, NAT, mangle, addr lists, connections, block IP
  ├── 📡 DHCP            → leases, servers, static leases
  ├── 📶 Wireless        → APs, clients, SSID/pass, scan
  ├── 🔒 VPN             → PPPoE, L2TP, OpenVPN, PPP secrets, WireGuard
  ├── 🌐 Network         → routes, DNS, IP addresses, ARP, pools, VLANs
  ├── 📋 Logs            → view, filter, stream
  ├── 🔧 Tools           → ping, traceroute, bwtest, scripts, search, quality
  ├── 📦 Backup          → create backup, export config, view files
  ├── 📊 QoS / Queues    → queue list, add, enable/disable
  ├── 🌉 Extras          → hotspot, bridge, containers
  └── ⚙️ Settings        → routers, users, language, bot info
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ui.formatters import _fmt_bytes


def _kb(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Quick builder: rows of (text, callback_data) tuples."""
    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.row(*[InlineKeyboardButton(text=t, callback_data=d) for t, d in row])
    return builder.as_markup()


def _back(cb: str, label: str = "⬅️ Back") -> list[tuple[str, str]]:
    return [(label, cb)]


# ─── Language Selection ───────────────────────────────────────────────────────

def lang_keyboard() -> InlineKeyboardMarkup:
    return _kb(
        [("🇬🇧 English", "lang:en"), ("🇷🇺 Русский", "lang:ru")],
        [("🇦🇲 Հայերեն", "lang:am"), ("🇩🇪 Deutsch", "lang:de")],
        _back("menu:settings"),
    )


# ─── Main Menu ────────────────────────────────────────────────────────────────

def main_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("📊 System", "menu:system"),       ("🔌 Interfaces", "menu:interfaces")],
        [("🛡 Firewall", "menu:firewall"),   ("📡 DHCP", "menu:dhcp")],
        [("📶 Wireless", "menu:wireless"),   ("🔒 VPN", "menu:vpn")],
        [("🌐 Network", "menu:network"),     ("📋 Logs", "menu:logs")],
        [("🔧 Tools", "menu:tools"),         ("📦 Backup", "menu:backup")],
        [("📊 QoS / Queues", "menu:queues"), ("🌉 Extras", "menu:extras")],
        [("⚙️ Settings", "menu:settings")],
    )


# ─── System Menu ──────────────────────────────────────────────────────────────

def system_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("📊 Info", "sys:refresh"),          ("🌡 Health", "sys:health")],
        [("📉 Health Card", "qol:health_card"), ("🔌 Conn Detail", "qol:conn_detail")],
        [("📋 Routerboard", "sys:routerboard"), ("👤 Router Users", "sys:users")],
        [("🔁 Reboot", "sys:reboot"),          ("📅 Scheduler", "sys:scheduler")],
        [("🕐 NTP", "sys:ntp"),               ("🔐 Certificates", "sys:certs")],
        _back("menu:main"),
    )


def reboot_confirm() -> InlineKeyboardMarkup:
    return _kb(
        [("✅ Yes, Reboot!", "sys:reboot_confirm"), ("❌ Cancel", "sys:refresh")],
    )


# ─── Interface Menu ───────────────────────────────────────────────────────────

def interfaces_menu(interfaces: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for iface in interfaces:
        name = iface.get("name", "?")
        running = iface.get("running", "false") == "true"
        disabled = iface.get("disabled", "false") == "true"
        icon = "🟢" if running else ("⛔" if disabled else "🔴")
        builder.row(
            InlineKeyboardButton(text=f"{icon} {name}", callback_data=f"iface:detail:{name}"),
        )
    builder.row(
        InlineKeyboardButton(text="📈 Eth Stats", callback_data="iface:eth_stats"),
        InlineKeyboardButton(text="🔄 Refresh", callback_data="menu:interfaces"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:main"))
    return builder.as_markup()


def interface_detail_menu(name: str, running: bool, disabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "⛔ Disable" if not disabled else "✅ Enable"
    toggle_cb = f"iface:disable:{name}" if not disabled else f"iface:enable:{name}"
    return _kb(
        [("📊 Traffic", f"iface:traffic:{name}"), (toggle_text, toggle_cb)],
        _back("menu:interfaces"),
    )


# ─── Firewall Menu ────────────────────────────────────────────────────────────

def firewall_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("🔍 Filter Rules", "fw:filter"),    ("🔀 NAT Rules", "fw:nat")],
        [("✏️ Mangle Rules", "fw:mangle"),    ("📋 Address Lists", "fw:addrlist")],
        [("🔗 Connections", "fw:connections"), ("🚫 Quick Block IP", "fw:block_ip")],
        [("➕ Add Filter Rule", "fw:add_rule"), ("➕ Add NAT Rule", "nat:add_prompt")],
        [("⚠️ Disable All Rules", "qol:bulk_disable_fw")],
        _back("menu:main"),
    )


def firewall_rule_list(rules: list[dict], page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * per_page
    page_rules = rules[start:start + per_page]

    for rule in page_rules:
        id_ = rule.get(".id", "")
        chain = rule.get("chain", "?")
        action = rule.get("action", "?")
        disabled = rule.get("disabled", "false") == "true"
        comment = rule.get("comment", "")
        proto = rule.get("protocol", "")
        port = rule.get("dst-port", "")
        icon = "⛔" if disabled else "✅"
        label = f"{icon} [{chain}] {action}"
        if proto:
            label += f" {proto}"
        if port:
            label += f":{port}"
        if comment:
            label += f" ({comment[:15]})"
        builder.row(InlineKeyboardButton(text=label[:50], callback_data=f"fw:rule:{id_}"))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"fw:filter:page:{page-1}"))
    if start + per_page < len(rules):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"fw:filter:page:{page+1}"))
    if nav:
        builder.row(*nav)

    builder.row(
        InlineKeyboardButton(text="➕ Add", callback_data="fw:add_rule"),
        InlineKeyboardButton(text="⬅️ Back", callback_data="menu:firewall"),
    )
    return builder.as_markup()


def firewall_rule_detail(id_: str, disabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "✅ Enable" if disabled else "⛔ Disable"
    toggle_cb = f"fw:enable:{id_}" if disabled else f"fw:disable:{id_}"
    return _kb(
        [(toggle_text, toggle_cb), ("🗑 Remove", f"fw:remove:{id_}")],
        [("⬆️ Move Up", f"fw:move_up:{id_}"), ("⬇️ Move Down", f"fw:move_down:{id_}")],
        _back("fw:filter"),
    )


def fw_add_rule_chain() -> InlineKeyboardMarkup:
    return _kb(
        [("input", "fw:add:chain:input"), ("forward", "fw:add:chain:forward")],
        [("output", "fw:add:chain:output")],
        [("❌ Cancel", "menu:firewall")],
    )


def fw_add_rule_action() -> InlineKeyboardMarkup:
    return _kb(
        [("accept", "fw:add:action:accept"), ("drop", "fw:add:action:drop")],
        [("reject", "fw:add:action:reject"), ("log", "fw:add:action:log")],
        [("passthrough", "fw:add:action:passthrough")],
        [("❌ Cancel", "menu:firewall")],
    )


def fw_add_rule_protocol() -> InlineKeyboardMarkup:
    return _kb(
        [("tcp", "fw:add:proto:tcp"), ("udp", "fw:add:proto:udp")],
        [("icmp", "fw:add:proto:icmp"), ("any", "fw:add:proto:any")],
        [("❌ Cancel", "menu:firewall")],
    )


def address_list_menu(lists: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for list_name in lists:
        builder.row(InlineKeyboardButton(text=f"📋 {list_name}", callback_data=f"fw:addrlist:view:{list_name}"))
    builder.row(InlineKeyboardButton(text="➕ Add Entry", callback_data="fw:addrlist:add"))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:firewall"))
    return builder.as_markup()


# ─── DHCP Menu ────────────────────────────────────────────────────────────────

def dhcp_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("📋 Leases", "dhcp:leases"),    ("🖥 Servers", "dhcp:servers")],
        [("➕ Add Static Lease", "dhcp:add_static")],
        [("🛡 DHCP Guard", "dhcpg:menu")],
        _back("menu:main"),
    )


def dhcp_guard_menu(s) -> InlineKeyboardMarkup:
    """DHCP Guard main menu. `s` is a GuardSettings instance."""
    det_btn = "🟢 Detector: ON" if s.enabled else "⚪️ Detector: OFF"
    fw_apply_label = "🛡 Re-apply Firewall" if s.firewall_applied else "🛡 Apply Firewall"
    ap_btn = "🔨 Auto-purge: ON" if s.auto_purge_flooders else "🔨 Auto-purge: OFF"
    return _kb(
        [(det_btn, "dhcpg:detector:toggle")],
        [(fw_apply_label, "dhcpg:fw:apply"), ("🗑 Remove FW", "dhcpg:fw:remove")],
        [("⚙️ Thresholds", "dhcpg:thresholds")],
        [(ap_btn, "dhcpg:autopurge:toggle")],
        _back("menu:dhcp"),
    )


def dhcp_guard_thresholds() -> InlineKeyboardMarkup:
    return _kb(
        [("🔴 Strict — 10 new / 60s", "dhcpg:preset:strict")],
        [("🟡 Balanced — 20 new / 60s", "dhcpg:preset:balanced")],
        [("🟢 Lax — 50 new / 120s", "dhcpg:preset:lax")],
        _back("dhcpg:menu"),
    )


def post_add_router() -> InlineKeyboardMarkup:
    """Shown right after /add_router succeeds — offer to apply firewall guard."""
    return _kb(
        [("🛡 Apply DHCP Guard Firewall", "dhcpg:quicksetup")],
        [("📋 Main Menu", "menu:main")],
    )


def dhcp_lease_list(leases: list[dict], page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * per_page
    for lease in leases[start:start + per_page]:
        id_ = lease.get(".id", "")
        ip = lease.get("address", "?")
        mac = lease.get("mac-address", "?")
        host = lease.get("host-name", "")
        type_ = lease.get("type", "dynamic")
        icon = "📌" if type_ == "static" else "🔄"
        label = f"{icon} {ip} {host or mac[:8]}"
        builder.row(InlineKeyboardButton(text=label[:50], callback_data=f"dhcp:lease:{id_}"))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"dhcp:page:{page-1}"))
    if start + per_page < len(leases):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"dhcp:page:{page+1}"))
    if nav:
        builder.row(*nav)

    builder.row(
        InlineKeyboardButton(text="➕ Add Static", callback_data="dhcp:add_static"),
        InlineKeyboardButton(text="⬅️ Back", callback_data="menu:dhcp"),
    )
    return builder.as_markup()


def dhcp_lease_detail(id_: str, is_dynamic: bool) -> InlineKeyboardMarkup:
    rows = []
    if is_dynamic:
        rows.append([("📌 Make Static", f"dhcp:make_static:{id_}")])
    rows.append([("🗑 Remove", f"dhcp:remove:{id_}"), ("⬅️ Back", "dhcp:leases")])
    return _kb(*rows)


# ─── Wireless Menu ────────────────────────────────────────────────────────────

def wireless_menu(interfaces: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for iface in interfaces:
        name = iface.get("name", "?")
        ssid = iface.get("ssid", "?")
        disabled = iface.get("disabled", "false") == "true"
        icon = "📶" if not disabled else "📵"
        builder.row(InlineKeyboardButton(
            text=f"{icon} {name} ({ssid})",
            callback_data=f"wifi:iface:{name}",
        ))
    builder.row(
        InlineKeyboardButton(text="👥 Clients", callback_data="wifi:clients"),
        InlineKeyboardButton(text="🔄 Refresh", callback_data="menu:wireless"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:main"))
    return builder.as_markup()


def wireless_iface_menu(name: str, disabled: bool) -> InlineKeyboardMarkup:
    toggle = ("✅ Enable", f"wifi:enable:{name}") if disabled else ("⛔ Disable", f"wifi:disable:{name}")
    return _kb(
        [("✏️ Change SSID", f"wifi:set_ssid:{name}"), ("🔑 Change Password", f"wifi:set_pass:{name}")],
        [toggle, ("📡 Scan APs", f"wifi:scan:{name}")],
        _back("menu:wireless"),
    )


def wireless_clients_menu(clients: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for client in clients:
        mac = client.get("mac-address", "?")
        iface = client.get("interface", "?")
        signal = client.get("signal-strength", "?")
        comment = client.get("comment", "")
        label = f"📱 {comment or mac[:11]} {signal} [{iface}]"
        builder.row(InlineKeyboardButton(text=label[:50], callback_data=f"wifi:client:{mac}"))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:wireless"))
    return builder.as_markup()


def wireless_client_detail(mac: str) -> InlineKeyboardMarkup:
    return _kb(
        [("🚫 Disconnect", f"wifi:disconnect:{mac}")],
        _back("wifi:clients"),
    )


# ─── VPN Menu ─────────────────────────────────────────────────────────────────

def vpn_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("📋 PPPoE Active",   "vpn:pppoe"),    ("👤 PPP Secrets",  "vpn:secrets")],
        [("🔒 L2TP Server",    "vpn:l2tp"),     ("🔑 OpenVPN",      "vpn:ovpn")],
        [("🔗 WireGuard",      "vpn:wg"),       ("📋 PPP Profiles", "vpn:profiles")],
        [("➕ Add VPN User",   "vpn:add_secret")],
        _back("menu:main"),
    )


def vpn_secrets_list(secrets: list[dict], page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * per_page
    for secret in secrets[start:start + per_page]:
        id_ = secret.get(".id", "")
        name = secret.get("name", "?")
        service = secret.get("service", "any")
        builder.row(InlineKeyboardButton(
            text=f"👤 {name} [{service}]",
            callback_data=f"vpn:secret:{id_}",
        ))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"vpn:secrets:page:{page-1}"))
    if start + per_page < len(secrets):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"vpn:secrets:page:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(
        InlineKeyboardButton(text="➕ Add", callback_data="vpn:add_secret"),
        InlineKeyboardButton(text="⬅️ Back", callback_data="menu:vpn"),
    )
    return builder.as_markup()


def vpn_secret_detail(id_: str) -> InlineKeyboardMarkup:
    return _kb(
        [("🗑 Remove", f"vpn:secret:remove:{id_}")],
        _back("vpn:secrets"),
    )


# ─── File Menu ────────────────────────────────────────────────────────────────

def files_menu(files: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for f in files[:15]:
        name = f.get("name", "?")
        size = f.get("size", "0")
        type_ = f.get("type", "")
        icon = {"backup": "💾", "script": "📜", "package": "📦"}.get(type_, "📄")
        label = f"{icon} {name} ({_fmt_bytes(int(size))})"
        builder.row(InlineKeyboardButton(text=label[:50], callback_data=f"file:detail:{name}"))
    builder.row(
        InlineKeyboardButton(text="🔄 Refresh", callback_data="menu:files"),
        InlineKeyboardButton(text="⬅️ Back", callback_data="menu:backup"),
    )
    return builder.as_markup()


def file_detail_menu(name: str) -> InlineKeyboardMarkup:
    return _kb(
        [("⬇️ Download", f"file:download:{name}"), ("🗑 Delete", f"file:delete:{name}")],
        _back("menu:files"),
    )


# ─── Logs Menu ────────────────────────────────────────────────────────────────

def logs_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("📋 Last 20", "log:last20"),              ("📋 Last 50", "log:last50")],
        [("🔥 Firewall Logs", "log:filter:firewall"), ("⚠️ Error Logs", "log:filter:error")],
        [("⚙️ System Logs", "log:filter:system"),    ("📡 DHCP Logs", "log:filter:dhcp")],
        [("📡 Stream All", "log:stream"),            ("📡 Stream Firewall", "log:stream:firewall")],
        _back("menu:main"),
    )


def log_stream_stop() -> InlineKeyboardMarkup:
    return _kb([("🔴 Stop Stream", "log:stop")])


# ─── Network Menu (Routes / DNS / IP) ─────────────────────────────────────────

def network_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("🗺 Routes",       "menu:routes"),   ("🌐 DNS",         "menu:dns")],
        [("📍 IP Addresses", "ip:list"),       ("🔁 ARP Table",   "ip:arp")],
        [("🏊 IP Pools",     "ip:pools"),      ("🏷 VLANs",       "vlan:list")],
        _back("menu:main"),
    )


def routes_menu(routes: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for route in routes[:10]:
        id_ = route.get(".id", "")
        dst = route.get("dst-address", "?")
        gw = route.get("gateway", "?")
        active = route.get("active", "false") == "true"
        icon = "🟢" if active else "🔴"
        builder.row(InlineKeyboardButton(
            text=f"{icon} {dst} → {gw}",
            callback_data=f"route:detail:{id_}",
        ))
    builder.row(
        InlineKeyboardButton(text="➕ Add Route", callback_data="route:add"),
        InlineKeyboardButton(text="🔄 Refresh", callback_data="menu:routes"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:network"))
    return builder.as_markup()


def route_detail_menu(id_: str) -> InlineKeyboardMarkup:
    return _kb(
        [("🗑 Remove", f"route:remove:{id_}")],
        _back("menu:routes"),
    )


def dns_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("⚙️ DNS Settings", "dns:settings"), ("📋 DNS Cache",    "dns:cache")],
        [("✏️ Set Servers",  "dns:set_servers"), ("🗑 Flush Cache", "dns:flush")],
        _back("menu:network"),
    )


def ip_menu() -> InlineKeyboardMarkup:
    """Legacy alias → redirects to network_menu."""
    return network_menu()


def ip_address_list_menu(addresses: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for a in addresses:
        addr = a.get("address", "?")
        iface = a.get("interface", "?")
        id_ = a.get(".id", "")
        builder.row(InlineKeyboardButton(
            text=f"📍 {addr} [{iface}]",
            callback_data=f"ip:addr:detail:{id_}",
        ))
    builder.row(
        InlineKeyboardButton(text="➕ Add", callback_data="ip:add_prompt"),
        InlineKeyboardButton(text="🔄 Refresh", callback_data="ip:list"),
        InlineKeyboardButton(text="⬅️ Back", callback_data="menu:network"),
    )
    return builder.as_markup()


def ip_addr_detail_menu(id_: str) -> InlineKeyboardMarkup:
    return _kb(
        [("🗑 Remove", f"ip:remove:{id_}")],
        _back("ip:list"),
    )


def ip_pools_menu(pools: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in pools:
        name = p.get("name", "?")
        ranges = p.get("ranges", "?")
        id_ = p.get(".id", "")
        builder.row(InlineKeyboardButton(
            text=f"🏊 {name} ({ranges})",
            callback_data=f"ip:pool:detail:{id_}",
        ))
    builder.row(
        InlineKeyboardButton(text="➕ Add Pool", callback_data="ip:pool:add_prompt"),
        InlineKeyboardButton(text="⬅️ Back", callback_data="menu:network"),
    )
    return builder.as_markup()


def ip_pool_detail_menu(id_: str) -> InlineKeyboardMarkup:
    return _kb(
        [("🗑 Remove", f"ip:pool:remove:{id_}")],
        _back("ip:pools"),
    )


# ─── Tools Menu ───────────────────────────────────────────────────────────────

def tools_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("🏓 Ping",           "tool:ping"),       ("🗺 Traceroute",    "tool:traceroute")],
        [("📊 Bandwidth Test", "tool:bwtest"),     ("📜 Scripts",       "tool:scripts")],
        [("🔍 Search (find)",  "qol:find"),        ("📡 Conn Quality",  "qol:quality")],
        _back("menu:main"),
    )


# ─── Backup Menu ──────────────────────────────────────────────────────────────

def backup_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("💾 Create Backup", "backup:create"), ("📜 Export Config", "backup:export")],
        [("📁 View Files",    "menu:files")],
        _back("menu:main"),
    )


# ─── QoS / Queues Menu ────────────────────────────────────────────────────────

def queues_menu(queues: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for q in queues:
        name = q.get("name", "?")
        target = q.get("target", "?")
        max_limit = q.get("max-limit", "")
        id_ = q.get(".id", "")
        disabled = q.get("disabled", "false") == "true"
        icon = "⛔" if disabled else "🟢"
        label = f"{icon} {name} → {target}"
        if max_limit:
            label += f" [{max_limit}]"
        builder.row(InlineKeyboardButton(text=label[:50], callback_data=f"queue:detail:{id_}"))
    builder.row(
        InlineKeyboardButton(text="➕ Add Queue", callback_data="queue:add_prompt"),
        InlineKeyboardButton(text="🔄 Refresh", callback_data="menu:queues"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:main"))
    return builder.as_markup()


def queue_detail_menu(id_: str, disabled: bool) -> InlineKeyboardMarkup:
    toggle = ("✅ Enable", f"queue:enable:{id_}") if disabled else ("⛔ Disable", f"queue:disable:{id_}")
    return _kb(
        [toggle, ("🗑 Remove", f"queue:remove:{id_}")],
        _back("menu:queues"),
    )


# ─── Extras Menu (Hotspot, Bridge, Containers) ───────────────────────────────

def extras_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("🔥 Hotspot",    "menu:hotspot"),  ("🌉 Bridge/VLAN", "menu:bridge")],
        [("🐋 Containers", "container:list")],
        _back("menu:main"),
    )


def hotspot_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("👥 Hotspot Users",    "hotspot:users"),      ("🟢 Active Sessions", "hotspot:active")],
        [("➕ Add Hotspot User", "hotspot:add_prompt")],
        _back("menu:extras"),
    )


def hotspot_users_menu(users: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for u in users:
        name = u.get("name", "?")
        id_ = u.get(".id", "")
        profile = u.get("profile", "default")
        builder.row(InlineKeyboardButton(
            text=f"👤 {name} [{profile}]",
            callback_data=f"hotspot:user:{id_}",
        ))
    builder.row(
        InlineKeyboardButton(text="➕ Add User", callback_data="hotspot:add_prompt"),
        InlineKeyboardButton(text="⬅️ Back", callback_data="menu:hotspot"),
    )
    return builder.as_markup()


def hotspot_user_detail_menu(id_: str) -> InlineKeyboardMarkup:
    return _kb(
        [("🗑 Remove", f"hotspot:remove:{id_}")],
        _back("hotspot:users"),
    )


def hotspot_active_menu(sessions: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in sessions:
        name = s.get("user", "?")
        ip = s.get("address", "?")
        id_ = s.get(".id", "")
        builder.row(InlineKeyboardButton(
            text=f"🟢 {name} ({ip})",
            callback_data=f"hotspot:kick:{id_}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:hotspot"))
    return builder.as_markup()


def bridge_menu(bridges: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for b in bridges:
        name = b.get("name", "?")
        running = b.get("running", "false") == "true"
        icon = "🟢" if running else "🔴"
        builder.row(InlineKeyboardButton(
            text=f"{icon} Bridge: {name}",
            callback_data=f"bridge:detail:{name}",
        ))
    builder.row(
        InlineKeyboardButton(text="🏷 VLANs", callback_data="vlan:list"),
        InlineKeyboardButton(text="⬅️ Back", callback_data="menu:extras"),
    )
    return builder.as_markup()


def bridge_detail_menu(name: str) -> InlineKeyboardMarkup:
    return _kb(
        [("🔌 Ports", f"bridge:ports:{name}")],
        _back("menu:bridge"),
    )


def vlan_list_menu(vlans: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for v in vlans:
        name = v.get("name", "?")
        vid = v.get("vlan-id", "?")
        iface = v.get("interface", "?")
        id_ = v.get(".id", "")
        builder.row(InlineKeyboardButton(
            text=f"🏷 VLAN {vid}: {name} [{iface}]",
            callback_data=f"vlan:detail:{id_}",
        ))
    builder.row(
        InlineKeyboardButton(text="➕ Add VLAN", callback_data="vlan:add_prompt"),
        InlineKeyboardButton(text="⬅️ Back", callback_data="menu:bridge"),
    )
    return builder.as_markup()


def vlan_detail_menu(id_: str) -> InlineKeyboardMarkup:
    return _kb(
        [("🗑 Remove", f"vlan:remove:{id_}")],
        _back("vlan:list"),
    )


# ─── Scripts Menu ─────────────────────────────────────────────────────────────

def scripts_menu(scripts: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in scripts:
        name = s.get("name", "?")
        builder.row(InlineKeyboardButton(
            text=f"📜 {name}",
            callback_data=f"script:detail:{name}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:tools"))
    return builder.as_markup()


def script_detail_menu(name: str) -> InlineKeyboardMarkup:
    return _kb(
        [("▶️ Run", f"script:run:{name}")],
        _back("tool:scripts"),
    )


# ─── Settings / Admin Menu ────────────────────────────────────────────────────

def settings_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("🔌 Routers",    "settings:routers"), ("👥 Bot Users",  "settings:users")],
        [("🌐 Language",   "settings:lang"),    ("🐋 Containers", "container:list")],
        [("📊 Bot Status", "qol:health_card"),  ("🔌 Conn Detail","qol:conn_detail")],
        _back("menu:main"),
    )


def routers_menu(router_list: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for r in router_list:
        alias = r["alias"]
        host = r["host"]
        active = r["active"]
        connected = r["connected"]
        ver = r.get("version", 0)
        icon = "🟢" if connected else "🔴"
        star = "⭐ " if active else ""
        builder.row(InlineKeyboardButton(
            text=f"{icon} {star}{alias} ({host}) ROS{ver}",
            callback_data=f"router:select:{alias}",
        ))
    builder.row(InlineKeyboardButton(text="➕ Add Router", callback_data="router:add"))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:settings"))
    return builder.as_markup()


def router_detail_menu(alias: str, is_active: bool) -> InlineKeyboardMarkup:
    rows = []
    if not is_active:
        rows.append([("⭐ Make Active", f"router:activate:{alias}")])
    rows.append([("🗑 Remove", f"router:remove:{alias}"), ("⬅️ Back", "settings:routers")])
    return _kb(*rows)


def bot_users_menu(users: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    role_icons = {"owner": "👑", "admin": "🔑", "operator": "⚙️", "viewer": "👁"}
    for u in users:
        uid = u["user_id"]
        role = u["role"]
        icon = role_icons.get(role, "👤")
        builder.row(InlineKeyboardButton(
            text=f"{icon} {uid} [{role}]",
            callback_data=f"admin:user:{uid}",
        ))
    builder.row(InlineKeyboardButton(text="➕ Add User", callback_data="admin:add_user"))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:settings"))
    return builder.as_markup()


def user_role_menu(uid: int) -> InlineKeyboardMarkup:
    return _kb(
        [("👁 Viewer", f"admin:setrole:{uid}:viewer"), ("⚙️ Operator", f"admin:setrole:{uid}:operator")],
        [("🔑 Admin",  f"admin:setrole:{uid}:admin")],
        [("🗑 Remove", f"admin:removeuser:{uid}"), ("⬅️ Back", "settings:users")],
    )


# ─── WireGuard Menu (ROS7) ────────────────────────────────────────────────────

def wireguard_menu(interfaces: list[dict], peers: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for iface in interfaces:
        name = iface.get("name", "?")
        listen_port = iface.get("listen-port", "?")
        builder.row(InlineKeyboardButton(text=f"🔒 {name} :{listen_port}", callback_data=f"wg:iface:{name}"))
    builder.row(InlineKeyboardButton(text=f"👥 Peers ({len(peers)})", callback_data="wg:peers"))
    if interfaces:
        first_iface = interfaces[0].get("name", "")
        builder.row(InlineKeyboardButton(text="➕ Add Peer", callback_data=f"wg:add_peer:{first_iface}"))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:vpn"))
    return builder.as_markup()


def wg_peers_list(peers: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for peer in peers:
        id_ = peer.get(".id", "")
        iface = peer.get("interface", "?")
        comment = peer.get("comment", peer.get("public-key", "?")[:16])
        builder.row(
            InlineKeyboardButton(text=f"👤 {comment} [{iface}]", callback_data=f"wg:peer:{id_}"),
            InlineKeyboardButton(text="🗑", callback_data=f"wg:remove:{id_}"),
        )
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="vpn:wg"))
    return builder.as_markup()


# ─── Container Menu (ROS7) ────────────────────────────────────────────────────

def container_menu(containers: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for c in containers:
        id_ = c.get(".id", "")
        name = c.get("name", id_[:8])
        status = c.get("status", "stopped")
        icon = "🟢" if status == "running" else "🔴"
        builder.row(InlineKeyboardButton(
            text=f"{icon} {name} [{status}]",
            callback_data=f"container:detail:{id_}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:extras"))
    return builder.as_markup()


def container_detail_menu(id_: str, running: bool) -> InlineKeyboardMarkup:
    action = ("⛔ Stop", f"container:stop:{id_}") if running else ("▶️ Start", f"container:start:{id_}")
    return _kb(
        [action, ("🗑 Remove", f"container:remove:{id_}")],
        _back("container:list"),
    )


# ─── Mangle / NAT Extended ───────────────────────────────────────────────────

def mangle_rule_list(rules: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    per_page = 8
    builder = InlineKeyboardBuilder()
    start = page * per_page
    for r in rules[start:start + per_page]:
        id_ = r.get(".id", "")
        chain = r.get("chain", "?")
        action = r.get("action", "?")
        disabled = r.get("disabled", "false") == "true"
        icon = "⛔" if disabled else "🟠"
        builder.row(InlineKeyboardButton(
            text=f"{icon} [{chain}] → {action} ({id_})",
            callback_data=f"mangle:detail:{id_}",
        ))
    nav = []
    if page > 0:
        nav.append(("◀️ Prev", f"mangle:page:{page - 1}"))
    if start + per_page < len(rules):
        nav.append(("Next ▶️", f"mangle:page:{page + 1}"))
    if nav:
        builder.row(*[InlineKeyboardButton(text=t, callback_data=d) for t, d in nav])
    builder.row(
        InlineKeyboardButton(text="➕ Add", callback_data="mangle:add_prompt"),
        InlineKeyboardButton(text="⬅️ Back", callback_data="menu:firewall"),
    )
    return builder.as_markup()


def mangle_detail_menu(id_: str) -> InlineKeyboardMarkup:
    return _kb(
        [("🗑 Remove", f"mangle:remove:{id_}")],
        _back("fw:mangle"),
    )


def nat_add_type_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("🔀 srcnat", "nat:add:chain:srcnat"), ("🔄 dstnat", "nat:add:chain:dstnat")],
        [("❌ Cancel", "fw:nat")],
    )


def nat_add_action_menu(chain: str) -> InlineKeyboardMarkup:
    if chain == "srcnat":
        return _kb(
            [("masquerade", f"nat:add:action:masquerade:{chain}"),
             ("src-nat", f"nat:add:action:src-nat:{chain}")],
            [("❌ Cancel", "fw:nat")],
        )
    else:
        return _kb(
            [("dst-nat", f"nat:add:action:dst-nat:{chain}"),
             ("redirect", f"nat:add:action:redirect:{chain}")],
            [("❌ Cancel", "fw:nat")],
        )


def nat_rule_detail_menu(id_: str) -> InlineKeyboardMarkup:
    return _kb(
        [("🗑 Remove", f"nat:remove:{id_}")],
        _back("fw:nat"),
    )


# ─── NTP Menu ────────────────────────────────────────────────────────────────

def ntp_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("📋 View NTP", "ntp:view"), ("✏️ Set Servers", "ntp:set_prompt")],
        _back("menu:system"),
    )


# ─── Certificates Menu ────────────────────────────────────────────────────────

def certs_menu(certs: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for c in certs:
        name = c.get("name", "?")
        expires = c.get("invalid-after", "?")
        builder.row(InlineKeyboardButton(
            text=f"🔐 {name} (exp: {expires})",
            callback_data=f"cert:detail:{name}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="menu:system"))
    return builder.as_markup()


# ─── ARP View ────────────────────────────────────────────────────────────────

def arp_menu() -> InlineKeyboardMarkup:
    return _kb(
        [("🔄 Refresh", "ip:arp"), ("⬅️ Back", "menu:network")],
    )


# ─── Confirm / Cancel ─────────────────────────────────────────────────────────

def confirm_keyboard(yes_cb: str, no_cb: str) -> InlineKeyboardMarkup:
    return _kb([(("✅ Confirm", yes_cb)), ("❌ Cancel", no_cb)])


def cancel_keyboard(back_cb: str = "menu:main") -> InlineKeyboardMarkup:
    return _kb([("❌ Cancel", back_cb)])
