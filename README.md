# 🖥 MikroBot — WinBox-level MikroTik Management in Telegram

Full RouterOS management bot. Every feature of WinBox, available in your Telegram.

## ✨ Features

| Category | Features |
|---|---|
| **System** | Resource monitoring, health, routerboard info, reboot, scheduler |
| **Interfaces** | List, enable/disable, live traffic stats |
| **Firewall** | Filter rules (CRUD, move, enable/disable), NAT, Mangle, Address Lists, Connection Tracking, Quick Block IP |
| **DHCP** | Leases (view, make static, remove), servers, add static leases |
| **Wireless** | Interface control, connected clients, SSID/password change, disconnect client, AP scan |
| **VPN** | PPPoE active sessions, L2TP/OpenVPN/PPTP status, PPP secrets (CRUD), WireGuard (ROS7) |
| **File System** | Browse, download, delete router files |
| **Logs** | View last N logs, filter by topic, **real-time streaming** |
| **Routes** | View routing table (IPv4 + IPv6 on ROS7), add/remove static routes |
| **DNS** | Settings, cache view, flush, change servers |
| **Tools** | Ping, Traceroute, Bandwidth Test, Scripts (ROS7) |
| **Backup** | Create `.backup` file, export `.rsc` configuration |
| **Containers** | Docker container management (ROS7 only) |
| **RBAC** | owner / admin / operator / viewer roles with per-command permissions |
| **Multi-router** | Multiple routers per user, switch between them |
| **Alerts** | CPU/memory threshold alerts, interface down, new device detection |
| **Auto-reconnect** | Watchdog reconnects dropped router connections |

## 🗺 Architecture

```
mikrobot/
├── bot.py                    # Entry point
├── config.py                 # Env-based config
├── requirements.txt
├── core/
│   ├── api_protocol.py       # RouterOS binary protocol (encode/decode + MD5 auth)
│   ├── router_client.py      # Async TCP client with tag multiplexing + streaming
│   ├── router_base.py        # Abstract interface (50+ methods)
│   ├── router_ros6.py        # RouterOS 6 (NSA only)
│   ├── router_ros7.py        # RouterOS 7 (NSA + SA/Docker) + WireGuard, Containers, IPv6
│   ├── router_manager.py     # Multi-router registry with auto-detection
│   ├── mock_router.py        # Full mock for offline development
│   ├── monitor.py            # Background monitor + Telegram alerts
│   ├── log_streamer.py       # Real-time log streaming to chat
│   ├── watchdog.py           # Auto-reconnect watchdog
│   ├── rbac.py               # Role-based access control
│   └── session.py            # FSM user session state
├── handlers/
│   ├── base.py               # Auth helpers
│   └── callbacks.py          # All UI handlers (FSM + callbacks)
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

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

Create a `.env` file:

```env
BOT_TOKEN=your_telegram_bot_token
OWNER_ID=your_telegram_user_id   # optional, will auto-bootstrap on first /start
LOG_LEVEL=INFO
```

### 3. Run

```bash
python bot.py
```

### 4. First use

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

The bot will auto-connect to the host router on startup via the Docker bridge interface.

**RouterOS 7 Docker setup:**

```routeros
/container
add remote-image=python:3.12-alpine interface=veth1 root-dir=disk1/mikrobot \
    cmd="python /app/bot.py" envlist=mikrobot-env
```

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
| BGP/OSPF routing | ❌ | ✅ | ✅ |
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
