# MikroBot — API Reference

> **Version**: 2.0 | **Protocol**: RouterOS Binary API (port 8728/8729)
> **Base classes**: `RouterBase` → `RouterROS6` → `RouterROS7`

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [HTTP Healthcheck API](#http-healthcheck-api)
3. [RouterOS API Methods](#routeros-api-methods)
   - [Connection](#connection)
   - [System](#system)
   - [Interfaces](#interfaces)
   - [IP Management](#ip-management)
   - [Firewall](#firewall)
   - [DHCP](#dhcp)
   - [Wireless](#wireless)
   - [VPN / PPP](#vpn--ppp)
   - [Files & Backup](#files--backup)
   - [Logs](#logs)
   - [Routing](#routing)
   - [DNS](#dns)
   - [Tools (Ping / Traceroute)](#tools)
   - [IP Pools](#ip-pools)
   - [Queues (QoS)](#queues-qos)
   - [Hotspot](#hotspot)
   - [Scripts](#scripts)
   - [Certificates](#certificates)
   - [Bridge & VLAN](#bridge--vlan)
   - [NTP](#ntp)
   - [Router Users](#router-users)
   - [ROS7 Extras](#ros7-extras)
4. [RouterManager API](#routermanager-api)
5. [RBAC API](#rbac-api)
6. [SessionManager API](#sessionmanager-api)
7. [Crypto API](#crypto-api)
8. [Audit API](#audit-api)
9. [Connection Quality API](#connection-quality-api)
10. [Error Reference](#error-reference)

---

## Architecture Overview

```
bot.py
 ├── core/
 │   ├── router_manager.py   — Multi-router registry (asyncio.Lock protected)
 │   ├── router_base.py      — Abstract RouterBase interface
 │   ├── router_ros6.py      — RouterOS 6 implementation
 │   ├── router_ros7.py      — RouterOS 7 (extends ROS6)
 │   ├── rbac.py             — Role-Based Access Control
 │   ├── session.py          — FSM session state management
 │   ├── crypto.py           — Fernet password encryption
 │   ├── audit.py            — Rotating audit log
 │   ├── healthcheck.py      — HTTP health/metrics server
 │   ├── quality.py          — API connection quality metrics
 │   ├── monitor.py          — Router health monitor
 │   └── watchdog.py         — Auto-reconnect watchdog
 ├── handlers/               — Aiogram router modules (14 domain modules)
 └── ui/
     ├── keyboards.py        — Inline keyboard builders
     ├── formatters.py       — Text formatters
     └── i18n.py             — Translations (en/ru/de/am)
```

**Thread safety**: All writes to `data/routers.json` are serialised via `asyncio.Lock()` in `RouterManager._write_lock`. Disk I/O is offloaded to a thread via `asyncio.to_thread()`.

---

## HTTP Healthcheck API

The bot exposes an embedded HTTP server on port **8080** (configurable).

### `GET /ping`

Liveness probe. Always returns 200 while the process is running.

```
Response: 200 text/plain
pong
```

### `GET /health`

Readiness probe with structured JSON.

```json
{
  "status":    "ok",
  "uptime_s":  3621,
  "routers":   3,
  "connected": 2,
  "sessions":  1,
  "timestamp": "2024-04-16T14:00:00+00:00"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | `"ok"` \| `"degraded"` | Overall health |
| `uptime_s` | `int` | Bot process uptime in seconds |
| `routers` | `int` | Total configured routers (all users) |
| `connected` | `int` | Routers currently connected |
| `sessions` | `int` | Active user FSM sessions |
| `timestamp` | `string` | ISO-8601 UTC |

**HTTP Status**: `200` if ok, `503` if degraded.

### `GET /metrics`

Prometheus-compatible plain text metrics.

```
# HELP mikrobot_uptime_seconds Bot process uptime in seconds
# TYPE mikrobot_uptime_seconds gauge
mikrobot_uptime_seconds 3621

# HELP mikrobot_routers_total Total configured routers
# TYPE mikrobot_routers_total gauge
mikrobot_routers_total 3

# HELP mikrobot_routers_connected Currently connected routers
# TYPE mikrobot_routers_connected gauge
mikrobot_routers_connected 2

# HELP mikrobot_sessions_active Active user sessions
# TYPE mikrobot_sessions_active gauge
mikrobot_sessions_active 1
```

**Docker usage** (`docker-compose.yml`):
```yaml
healthcheck:
  test: ["CMD", "wget", "-qO-", "http://localhost:8080/ping"]
  interval: 30s
  timeout: 5s
```

---

## RouterOS API Methods

All methods are `async` and raise exceptions on router errors.
Import path: `from core.router_ros6 import RouterROS6` or `from core.router_ros7 import RouterROS7`.

### Connection

```python
RouterROS6(host, username, password, port=8728, use_ssl=False)
RouterROS7(host, username, password, port=8728, use_ssl=False, standalone=False)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `connect()` | `bool` | Connect to RouterOS API. Returns `True` on success |
| `close()` | `None` | Close the API connection |
| `connected` | `bool` (property) | `True` if currently connected |

---

### System

| Method | Returns | Description |
|--------|---------|-------------|
| `get_system_resource()` | `dict` | CPU load, memory, disk, uptime, version |
| `get_system_identity()` | `dict` | `{"name": "MyRouter"}` |
| `get_system_routerboard()` | `dict` | Board model, serial, firmware |
| `get_system_health()` | `dict` | Temperature, voltage, fan speed |
| `reboot()` | `None` | Send reboot command |

**`get_system_resource()` response fields:**
```
cpu-load          CPU usage percentage (str)
total-memory      Total RAM in bytes (str)
free-memory       Free RAM in bytes (str)
total-hdd-space   Total disk in bytes (str)
free-hdd-space    Free disk in bytes (str)
uptime            Human-readable uptime e.g. "3d2h15m"
version           RouterOS version string
board-name        Hardware model
```

---

### Interfaces

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_interfaces()` | — | `list[dict]` | All interfaces with status |
| `enable_interface(name)` | `name: str` | `None` | Enable interface by name |
| `disable_interface(name)` | `name: str` | `None` | Disable interface |
| `get_interface_traffic(name, duration)` | `name: str`, `duration: int = 5` | `dict` | TX/RX bytes sampled over duration seconds |
| `get_interface_ethernet_stats()` | — | `list[dict]` | Ethernet port statistics |

---

### IP Management

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_ip_addresses()` | — | `list[dict]` | All IP addresses with interface |
| `add_ip_address(address, interface)` | `address: str` (CIDR), `interface: str` | `str` | Returns new entry ID |
| `remove_ip_address(id_)` | `id_: str` | `None` | Remove by `.id` |
| `get_arp()` | — | `list[dict]` | ARP table entries |
| `get_ip_pools()` | — | `list[dict]` | IP address pools |
| `add_ip_pool(name, ranges)` | `name: str`, `ranges: str` | `str` | e.g. `"192.168.1.10-192.168.1.100"` |
| `remove_ip_pool(id_)` | `id_: str` | `None` | — |

---

### Firewall

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_firewall_filter()` | — | `list[dict]` | Filter rules |
| `add_firewall_filter(params)` | `params: dict` | `str` | Returns new rule ID |
| `remove_firewall_rule(id_)` | `id_: str` | `None` | — |
| `enable_firewall_rule(id_)` | `id_: str` | `None` | — |
| `disable_firewall_rule(id_)` | `id_: str` | `None` | — |
| `move_firewall_rule(id_, destination)` | `id_: str`, `destination: int` | `None` | Move to position |
| `get_firewall_nat()` | — | `list[dict]` | NAT rules |
| `add_firewall_nat(params)` | `params: dict` | `str` | Returns new rule ID |
| `remove_firewall_nat(id_)` | `id_: str` | `None` | — |
| `get_firewall_mangle()` | — | `list[dict]` | Mangle rules |
| `add_firewall_mangle(params)` | `params: dict` | `str` | Returns new rule ID |
| `remove_firewall_mangle(id_)` | `id_: str` | `None` | — |
| `get_address_list(list_name)` | `list_name: str \| None` | `list[dict]` | Filter by list name or all |
| `add_address_list_entry(address, list_name, comment)` | see sig | `str` | Returns new entry ID |
| `remove_address_list_entry(id_)` | `id_: str` | `None` | — |
| `get_connection_tracking()` | — | `list[dict]` | Active connections |

**`add_firewall_filter(params)` example:**
```python
await router.add_firewall_filter({
    "chain": "forward",
    "action": "drop",
    "src-address": "10.0.0.0/8",
    "protocol": "tcp",
    "dst-port": "80,443",
    "comment": "Block LAN to WAN HTTP",
})
```

---

### DHCP

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_dhcp_server()` | — | `list[dict]` | DHCP server configs |
| `get_dhcp_leases()` | — | `list[dict]` | All leases (static + dynamic) |
| `add_dhcp_static_lease(mac, ip, comment)` | `mac: str`, `ip: str`, `comment: str = ""` | `str` | Returns lease ID |
| `remove_dhcp_lease(id_)` | `id_: str` | `None` | — |
| `make_dhcp_lease_static(id_)` | `id_: str` | `None` | Convert dynamic → static |

---

### Wireless

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_wireless_interfaces()` | — | `list[dict]` | Wireless interfaces with SSID |
| `get_wireless_registrations()` | — | `list[dict]` | Connected clients (signal, MAC) |
| `get_wireless_security_profiles()` | — | `list[dict]` | Security profiles |
| `set_wireless_ssid(interface, ssid)` | `interface: str`, `ssid: str` | `None` | Change SSID |
| `set_wireless_password(interface, password)` | `interface: str`, `password: str` | `None` | Change WPA2 password |
| `enable_wireless(interface)` | `interface: str` | `None` | — |
| `disable_wireless(interface)` | `interface: str` | `None` | — |
| `disconnect_wireless_client(mac)` | `mac: str` | `None` | Kick client |
| `get_wireless_scan(interface)` | `interface: str` | `list[dict]` | Scan nearby APs (~5s) |

---

### VPN / PPP

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_pppoe_server()` | — | `list[dict]` | PPPoE server config |
| `get_pppoe_active()` | — | `list[dict]` | Active PPPoE sessions |
| `get_l2tp_server()` | — | `dict` | L2TP server status |
| `get_ovpn_server()` | — | `dict` | OpenVPN server status |
| `get_pptp_server()` | — | `dict` | PPTP server status |
| `get_vpn_secrets()` | — | `list[dict]` | PPP secrets (VPN users) |
| `add_vpn_secret(name, password, service, profile)` | see sig | `str` | Returns secret ID |
| `remove_vpn_secret(id_)` | `id_: str` | `None` | — |
| `get_ppp_profiles()` | — | `list[dict]` | PPP profiles |

---

### Files & Backup

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_files()` | — | `list[dict]` | Files on router flash |
| `delete_file(name)` | `name: str` | `None` | Delete file |
| `get_backup_file(name)` | `name: str` | `bytes` | Download backup file content |
| `create_backup(name, password)` | `name: str = ""`, `password: str = ""` | `str` | Creates backup, returns filename |
| `export_config()` | — | `str` | Full router config as `.rsc` text |

---

### Logs

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_logs(limit, topics)` | `limit: int = 50`, `topics: str = ""` | `list[dict]` | Recent log entries, optionally filtered |
| `stream_logs(topics)` | `topics: str = ""` | `AsyncIterator[dict]` | Async generator for live log streaming |

**Topics filter examples**: `"firewall"`, `"dhcp"`, `"system"`, `"!debug,!packet"`.

---

### Routing

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_routes()` | — | `list[dict]` | IP routing table |
| `add_route(dst_address, gateway, distance)` | see sig | `str` | Returns route ID |
| `remove_route(id_)` | `id_: str` | `None` | — |

---

### DNS

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_dns_settings()` | — | `dict` | Servers, allow-remote, cache-size |
| `set_dns_servers(servers)` | `servers: list[str]` | `None` | e.g. `["1.1.1.1", "8.8.8.8"]` |
| `get_dns_cache()` | — | `list[dict]` | Cached DNS entries |
| `flush_dns_cache()` | — | `None` | Clear DNS cache |

---

### Tools

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `ping(address, count)` | `address: str`, `count: int = 4` | `list[dict]` | Returns per-packet results |
| `traceroute(address)` | `address: str` | `list[dict]` | Hop-by-hop routing trace |
| `bandwidth_test(address, duration)` | `address: str`, `duration: int = 5` | `dict` | Requires btest server on target |

**`ping()` response item fields:**
```
seq           Sequence number
host          Target host
time          RTT in ms (str)
size          Packet size
status        "timeout" | "reply"
```

---

### IP Pools

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_ip_pools()` | — | `list[dict]` | — |
| `add_ip_pool(name, ranges)` | `name: str`, `ranges: str` | `str` | Returns pool ID |
| `remove_ip_pool(id_)` | `id_: str` | `None` | — |

---

### Queues (QoS)

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_simple_queues()` | — | `list[dict]` | Simple queue list |
| `add_simple_queue(name, target, max_limit, comment)` | see sig | `str` | `max_limit` format: `"10M/5M"` |
| `remove_simple_queue(id_)` | `id_: str` | `None` | — |
| `enable_simple_queue(id_)` | `id_: str` | `None` | — |
| `disable_simple_queue(id_)` | `id_: str` | `None` | — |

---

### Hotspot

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_hotspot_users()` | — | `list[dict]` | — |
| `get_hotspot_active()` | — | `list[dict]` | Active sessions |
| `add_hotspot_user(name, password, profile, comment)` | see sig | `str` | Returns user ID |
| `remove_hotspot_user(id_)` | `id_: str` | `None` | — |
| `disconnect_hotspot_user(id_)` | `id_: str` | `None` | Kick active session |

---

### Scripts

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_scripts()` | — | `list[dict]` | All scripts with source |
| `run_script(name)` | `name: str` | `str` | Output of script execution |
| `add_script(name, source, comment)` | see sig | `str` | Returns script ID |

---

### Certificates

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_certificates()` | — | `list[dict]` | Certs with expiry |

**ROS7 only:**

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `generate_self_signed_cert(common_name, days)` | see sig | `str` | Returns cert name |

---

### Bridge & VLAN

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_bridges()` | — | `list[dict]` | Bridge interfaces |
| `get_bridge_ports()` | — | `list[dict]` | All bridge port assignments |
| `add_bridge_port(bridge, interface)` | see sig | `str` | Returns port ID |
| `remove_bridge_port(id_)` | `id_: str` | `None` | — |
| `get_vlans()` | — | `list[dict]` | VLAN interfaces |
| `add_vlan(name, vlan_id, interface)` | see sig | `str` | Returns VLAN ID |
| `remove_vlan(id_)` | `id_: str` | `None` | — |

---

### NTP

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_ntp_client()` | — | `dict` | NTP settings and sync status |
| `set_ntp_servers(primary, secondary)` | `primary: str`, `secondary: str = ""` | `None` | — |

---

### Router Users

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_users()` | — | `list[dict]` | RouterOS user accounts |
| `add_user(name, password, group)` | `group: str = "read"` | `str` | Returns user ID |
| `remove_user(id_)` | `id_: str` | `None` | — |

---

### ROS7 Extras

These methods are only available on `RouterROS7`:

| Method | Returns | Description |
|--------|---------|-------------|
| `get_wireguard_interfaces()` | `list[dict]` | WireGuard interfaces |
| `get_wireguard_peers()` | `list[dict]` | WireGuard peers |
| `add_wireguard_interface(name, listen_port)` | `str` | Creates WG interface |
| `add_wireguard_peer(interface, public_key, allowed_address, endpoint, endpoint_port)` | `str` | Adds WG peer |
| `remove_wireguard_peer(id_)` | `None` | — |
| `get_container_list()` | `list[dict]` | Docker containers |
| `start_container(id_)` | `None` | — |
| `stop_container(id_)` | `None` | — |
| `remove_container(id_)` | `None` | — |
| `get_bgp_peers()` | `list[dict]` | BGP peer status |
| `get_ospf_instances()` | `list[dict]` | OSPF instances |
| `get_ipv6_addresses()` | `list[dict]` | IPv6 address list |
| `get_ipv6_neighbors()` | `list[dict]` | IPv6 neighbor discovery |
| `get_bridge_vlans()` | `list[dict]` | Bridge VLAN table (ROS7 format) |
| `generate_self_signed_cert(common_name, days)` | `str` | Generates cert, returns name |

---

## RouterManager API

```python
from core.router_manager import RouterManager

rm = RouterManager()
```

**Thread safety**: All writes protected by `asyncio.Lock()`.

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `add_router(user_id, alias, host, username, password, port, use_ssl, ros_version, standalone)` | see sig | `tuple[bool, str]` | Connect + register. Returns `(success, message)` |
| `remove_router(user_id, alias)` | see sig | `bool` | Disconnect and remove |
| `switch_router(user_id, alias)` | see sig | `bool` | Set active router |
| `get_active(user_id)` | `user_id: int` | `RouterBase \| None` | Get active router object |
| `get_active_entry(user_id)` | `user_id: int` | `RouterEntry \| None` | Get entry with metadata |
| `get_router_list(user_id)` | `user_id: int` | `list[dict]` | Summary list for UI |
| `has_routers(user_id)` | `user_id: int` | `bool` | — |
| `iter_all_entries()` | — | `Iterator[tuple[int, str, RouterEntry]]` | All `(uid, alias, entry)` |
| `reconnect_all()` | — | `None` | Reconnect all disconnected routers concurrently |
| `get_or_mock(user_id)` | `user_id: int` | `RouterBase` | Real router or MockRouter fallback |

---

## RBAC API

```python
from core.rbac import RBACManager, Role

rbac = RBACManager()
```

**Roles** (ascending permissions): `VIEWER` → `OPERATOR` → `ADMIN` → `OWNER`

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `bootstrap_owner(uid)` | `uid: int` | `None` | Register first user as owner |
| `is_bootstrapped()` | — | `bool` | Has any user been registered |
| `is_known(uid)` | `uid: int` | `bool` | Is user in the registry |
| `get_role(uid)` | `uid: int` | `Role \| None` | User's role |
| `set_role(uid, role)` | `uid: int`, `role: Role` | `None` | Assign role, persists to disk |
| `remove_user(uid)` | `uid: int` | `None` | Remove from registry |
| `get_all_users()` | — | `list[dict]` | All registered users |
| `can(uid, permission)` | `uid: int`, `permission: str` | `bool` | Check permission |
| `require(uid, permission)` | — | `None` | Raises `PermissionError` if denied |

**Permission strings** (examples):
```
router.add           router.remove
firewall.manage      interface.manage
system.reboot        system.backup       system.export
dhcp.manage          dns.manage          ip.manage
route.manage         wireless.manage     vpn.manage
user.view            user.add            user.remove         user.role.change
```

---

## SessionManager API

```python
from core.session import SessionManager

sessions = SessionManager()
```

| Method | Params | Returns | Description |
|--------|--------|---------|-------------|
| `get_state(uid)` | `uid: int` | `str \| None` | Current FSM state key |
| `set_state(uid, state)` | `uid: int`, `state: str` | `None` | Set FSM state |
| `clear_state(uid)` | `uid: int` | `None` | Reset to idle |
| `get_data(uid)` | `uid: int` | `dict` | FSM wizard data |
| `update_data(uid, **kwargs)` | — | `None` | Merge into wizard data |
| `get_language(uid)` | `uid: int` | `str` | User language (`"en"` default) |
| `set_language(uid, lang)` | `uid: int`, `lang: str` | `None` | Persist language choice |
| `active_count()` | — | `int` | Sessions with non-idle state |
| `total_count()` | — | `int` | Total tracked users |
| `start_cleanup_loop()` | — | `None` | Start background expiry task (5min timeout) |
| `stop_cleanup_loop()` | — | `None` | Cancel cleanup task |

---

## Crypto API

```python
from core import crypto

crypto.init(bot_token)          # Must call once at startup
encrypted = crypto.encrypt("mypassword")
plaintext = crypto.decrypt(encrypted)
encrypted = crypto.ensure_encrypted(value)   # No-op if already encrypted
plaintext = crypto.safe_decrypt(value)       # No-op if plaintext
```

**Key derivation**: PBKDF2-HMAC-SHA256, 100,000 iterations, salt = SHA256(BOT_TOKEN).
**Cipher**: Fernet (AES-128-CBC + HMAC-SHA256).

> ⚠️ **Important**: Changing `BOT_TOKEN` breaks decryption of existing `data/routers.json` passwords.

---

## Audit API

```python
from core.audit import log_action, log_admin

log_action(user_id, action, detail="")   # General action log
log_admin(user_id, action, detail="")    # Privileged/admin action log
```

Output: `data/audit.log` (rotating, 5MB × 3 files).

**Log format:**
```
2024-04-16 14:00:00 [AUDIT] user=123456 action=router_add detail=office@192.168.1.1
2024-04-16 14:01:00 [ADMIN] user=123456 action=role_change detail=789012 → admin
```

---

## Connection Quality API

```python
from core.quality import check_api_latency, fmt_quality, quality_emoji

result = await check_api_latency(router, samples=5)
# → {"latency_ms": 12.3, "jitter_ms": 2.1, "success": True, "loss_pct": 0}

text = fmt_quality(result)
# → "⚡ Latency: `12.3ms` | Jitter: `2.1ms` | Loss: `0%`"

emoji = quality_emoji(latency_ms=12.3, loss_pct=0)
# → "⚡"  (excellent)
# → "🟢"  (good, <100ms)
# → "🟡"  (ok, 100-500ms)
# → "🔴"  (poor, >500ms)
# → "💀"  (unreachable)
```

---

## Error Reference

| Exception | Cause | Handler behaviour |
|-----------|-------|-------------------|
| `ConnectionResetError` | Router dropped the connection | Shows "Router connection lost" |
| `TimeoutError` / `asyncio.TimeoutError` | API call timeout (>5s) | Shows "Router not responding" |
| `ConnectionRefusedError` | Port closed / API not enabled | Shows "API refused connection" |
| `OSError` | Network unreachable | Shows "Cannot reach the router" |
| `PermissionError` | RBAC check failed | Shows user-friendly denial |
| `TelegramBadRequest` | Message not modified | Silently ignored |

All unhandled exceptions are caught by `ErrorHandlerMiddleware`, logged with full traceback to stdout, and a user-friendly alert is shown.

---

## i18n API

```python
from ui.i18n import t, get_lang

lang = get_lang(user_id, sessions)      # "en" | "ru" | "de" | "am"
text = t("err.no_router", lang)
text = t("fsm.router.alias", lang)
text = t("fw.blocked", lang, ip="1.2.3.4")
```

Supported language codes: `en` (English), `ru` (Русский), `de` (Deutsch), `am` (Հայerен).
Falls back to `"en"` if key or language is missing.
