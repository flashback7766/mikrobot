# 🖥 MikroBot — WinBox-level MikroTik Management in Telegram

Full RouterOS management bot. Every feature of WinBox, available in your Telegram.

## ✨ Features

| Category | Features |
|---|---|
| **System** | Resource monitoring, health, routerboard info, reboot, scheduler |
| **Interfaces** | List, enable/disable, live traffic stats, ethernet statistics |
| **Firewall** | Filter rules (CRUD, move, enable/disable), NAT, Mangle, Address Lists, Connection Tracking, Quick Block IP |
| **DHCP** | Leases (view, make static, remove), servers, add static leases |
| **DHCP Guard** 🆕 | DHCP starvation (`dhcpig` etc.) detection + firewall rate-limit + optional auto-purge of flood leases |
| **Wireless** | Interface control, connected clients, SSID/password change, disconnect client, AP scan |
| **VPN** | PPPoE active sessions, L2TP/OpenVPN/PPTP status, PPP secrets (CRUD), WireGuard (ROS7) |
| **File System** | Browse, download, delete router files |
| **Logs** | View last N logs, filter by topic, **real-time streaming** |
| **Routes** | View routing table (IPv4 + IPv6 on ROS7), add/remove static routes |
| **DNS** | Settings, cache view, flush, change servers |
| **Tools** | Ping, Traceroute, Bandwidth Test, Scripts |
| **Backup** | Create `.backup` file, export `.rsc` configuration |
| **Queues** | Simple queue management (add/remove/enable/disable) |
| **Hotspot** | User management, active sessions, kick users |
| **Bridge/VLAN** | Bridge port management, VLAN create/delete |
| **Containers** | Docker container management (ROS7 only) |
| **RBAC** | owner / admin / operator / viewer roles with per-command permissions |
| **Multi-router** | Multiple routers per user, switch between them |
| **Alerts** | CPU/memory threshold alerts, interface down, new device detection, DHCP attack alerts 🆕 |
| **Auto-reconnect** | Watchdog reconnects dropped router connections |
| **Security** | 🔐 Router passwords encrypted at rest (Fernet/PBKDF2) |

## 🗺 Architecture

```
mikrobot/
├── bot.py                     # Entry point
├── config.py                  # Env-based config
├── Dockerfile                 # Docker image
├── docker-compose.yml         # One-command deploy
├── requirements.txt
├── core/
│   ├── api_protocol.py        # RouterOS binary protocol (encode/decode + MD5 auth)
│   ├── router_client.py       # Async TCP client with tag multiplexing + streaming
│   ├── router_base.py         # Abstract interface (50+ methods)
│   ├── router_ros6.py         # RouterOS 6 (NSA only)
│   ├── router_ros7.py         # RouterOS 7 (NSA + SA/Docker) + WireGuard, Containers, IPv6
│   ├── router_manager.py      # Multi-router registry with auto-detection
│   ├── crypto.py              # Fernet password encryption (BOT_TOKEN-derived key)
│   ├── mock_router.py         # Full mock for offline development
│   ├── monitor.py             # Background monitor + Telegram alerts
│   ├── log_streamer.py        # Real-time log streaming to chat
│   ├── watchdog.py            # Auto-reconnect watchdog
│   ├── rbac.py                # Role-based access control
│   └── session.py             # FSM user session state
├── handlers/
│   ├── __init__.py            # Setup + register all sub-routers
│   ├── base.py                # Auth helpers (send_or_edit, require_router)
│   ├── context.py             # Shared state injection + auth middleware
│   ├── commands.py            # /start, /help, /menu, /add_router
│   ├── fsm.py                 # All FSM text-input wizards
│   ├── system.py              # System info, health, reboot, scheduler, NTP, certs
│   ├── interfaces.py          # Interface list/detail/traffic/toggle, eth stats
│   ├── firewall.py            # Filter, NAT, mangle, address lists, add-rule wizard
│   ├── dhcp.py                # Leases, servers, static lease add
│   ├── wireless.py            # WiFi interfaces, clients, SSID/password, scan
│   ├── vpn.py                 # PPPoE, L2TP, OpenVPN, PPP secrets, WireGuard
│   ├── files.py               # File browser, download, delete
│   ├── logs.py                # Log viewer, filter, real-time streaming
│   ├── network.py             # Routes, DNS, IP addresses, ARP, pools
│   ├── tools.py               # Ping, traceroute, bandwidth test, scripts
│   ├── admin.py               # Settings, router/user management, containers
│   └── extras.py              # Hotspot, bridge, VLAN, queues, backup
└── ui/
    ├── keyboards.py           # All inline keyboards
    └── formatters.py          # Data formatters → Markdown text
```

## 📦 RouterOS Protocol

MikroBot uses the **native RouterOS binary API** (port 8728 / SSL 8729):

- **Length encoding**: Variable-width (1–5 bytes)
- **Authentication**:
  - ROS6: Two-step MD5 challenge-response
  - ROS7: Single-step plaintext with MD5 fallback
- **Tag multiplexing**: Multiple concurrent commands with independent response queues
- **Streaming**: `/log/print follow=yes` for real-time logs (cancellable)

## 🚀 Quick Start

### Option 1: Run directly

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
BOT_TOKEN=your_telegram_bot_token
OWNER_ID=your_telegram_user_id   # optional, will auto-bootstrap on first /start
LOG_LEVEL=INFO
```

```bash
python bot.py
```

### Option 2: Docker (recommended)

```bash
cp .env.example .env
# Edit .env with your BOT_TOKEN

docker compose up -d
```

That's it. Logs: `docker compose logs -f`

### First use

1. Send `/start` to your bot
2. You'll be auto-promoted to **owner** (first user)
3. Use `/add_router` to connect your MikroTik

## 🐋 Standalone Mode (RouterOS 7 Docker)

Run MikroBot **inside your router** as a Docker container:

```env
BOT_TOKEN=your_token
OWNER_ID=your_telegram_id
STANDALONE=1
MIKROTIK_HOST=172.17.0.1   # Docker bridge gateway (default)
MIKROTIK_USER=admin
MIKROTIK_PASS=your_password
```

**RouterOS 7 Docker setup:**

```routeros
/container
add remote-image=python:3.12-alpine interface=veth1 root-dir=disk1/mikrobot \
    cmd="python /app/bot.py" envlist=mikrobot-env
```

## 🔐 Security

- **Passwords encrypted at rest** — `data/routers.json` uses Fernet symmetric encryption with a key derived from your `BOT_TOKEN` via PBKDF2 (100k iterations). Without the token, the file is useless.
- **Auto-migration** — existing plaintext passwords are encrypted automatically on first save.
- **Password message deletion** — when adding a router, the message containing your password is deleted from chat.
- **RBAC** — per-action permission checks prevent unauthorized access to destructive operations.

## 👥 RBAC Roles

| Role | What they can do |
|---|---|
| 👑 **owner** | Everything + manage bot users + add/remove routers |
| 🔑 **admin** | Full router control + system backup/export |
| ⚙️ **operator** | Interface toggle, DHCP manage, firewall address lists, wireless manage, VPN view |
| 👁 **viewer** | View-only: system, interfaces, logs, DHCP, wireless, DNS, ping |

Add users via **Settings → Bot Users → Add User** (owner only).

## 🔌 RouterOS Version Matrix

| Feature | ROS 6 | ROS 7 (NSA) | ROS 7 (SA/Docker) |
|---|---|---|---|
| All basic management | ✅ | ✅ | ✅ |
| Firewall, DHCP, VPN | ✅ | ✅ | ✅ |
| Wireless management | ✅ | ✅ | ✅ |
| WireGuard | ❌ | ✅ | ✅ |
| Docker containers | ❌ | ✅ | ✅ |
| IPv6 | Partial | ✅ | ✅ |
| Run inside router | ❌ | NSA | ✅ |

## 📡 Log Streaming

Real-time log streaming works for all topics:

- All logs: tap **📡 Stream Logs**
- Firewall only: tap **📡 Stream Firewall**
- Stop anytime: `/stop_logs` or tap 🔴 Stop

Each log line is color-coded by topic:
🔴 error | 🟡 warning | 🔵 info | 🛡 firewall | 📡 dhcp | 📶 wireless | ⚙️ system

## 🛡 Firewall Manager

Full WinBox-equivalent firewall control:

- View all filter, NAT, and mangle rules with stats (bytes/packets)
- Add rules with interactive wizard (chain → action → protocol → IP → port)
- Enable/disable individual rules
- Move rules up/down in the chain
- Quick block: tap **🚫 Quick Block IP** → enter IP → automatically adds to blacklist + drop rule
- View and manage address lists
- View active connection tracking table

## 🛡 DHCP Guard

Protection against DHCP starvation attacks (`dhcpig`, `Yersinia`, and similar tools that exhaust the DHCP pool by sending forged DHCPDISCOVER packets with random MAC addresses).

**Two-layer defence:**

- **Detector** (auto-enabled on every router you add): polls the lease table every 30s and alerts your Telegram chat the moment new-lease velocity crosses the configured threshold.
- **Firewall rate-limit** (opt-in, one tap after adding a router): installs two input-chain rules on UDP/67 — accept up to `rate,burst:packet`, drop the overflow. All rules tagged with `comment="mikrobot-dhcp-guard"` for clean idempotent apply/remove.

**Optional auto-mitigation:** toggle on to have the bot remove dynamic leases belonging to the flooding MACs. Static leases are never touched.

**Presets** (configurable under 📡 DHCP → 🛡 DHCP Guard → ⚙️ Thresholds):

| Preset | New leases in window triggers alert | Firewall rate,burst |
|---|---|---|
| 🔴 Strict | 10 in 60s | 20,50 |
| 🟡 Balanced (default) | 20 in 60s | 50,100 |
| 🟢 Lax | 50 in 120s | 100,200 |

**Sample alert:**
```
🚨 DHCP STARVATION ATTACK
Router: home (192.168.1.1)
New leases: 127 in 60s
Total leases now: 135
Sample MACs:
  DE:AD:BE:EF:00:04
  DE:AD:BE:EF:00:12
  ... and 122 more
```

5-minute cooldown between alerts for the same router prevents alert storms.
