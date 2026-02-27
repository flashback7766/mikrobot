# MikroBot Extended — Setup Guide

**Full WinBox-level MikroTik RouterOS management via Telegram**

Supports RouterOS 6 (NSA) and RouterOS 7 (NSA + SA/standalone Docker)

---

## 📋 Quick Start

### 1. Get a Telegram Bot Token

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow prompts to choose name and username
4. Copy the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Install Dependencies

```bash
cd mikrobot_extended
pip install -r requirements.txt --break-system-packages
```

*(Use `--break-system-packages` on Python 3.11+ or create a virtual environment)*

### 3. Configure the Bot

**Option A: Environment Variables (recommended)**

```bash
export BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
export OWNER_ID="123456789"  # Your Telegram user ID (optional)
```

**Option B: .env File**

Create `.env` in the bot directory:

```env
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
OWNER_ID=123456789
LOG_LEVEL=INFO
```

**How to get your Telegram user ID:**
- Forward any message to [@userinfobot](https://t.me/userinfobot)
- Or skip OWNER_ID — the first person to /start the bot becomes owner

### 4. Run the Bot

```bash
python bot.py
```

You should see:
```
2026-02-18 09:35:39 [MikroBot] INFO: Bot is running. Press Ctrl+C to stop.
```

### 5. Add Your First Router

1. Open Telegram and message your bot
2. Send `/start`
3. If you're the first user, you'll automatically become owner
4. Use `/add_router` or tap "⚙️ Settings" → "🔌 Routers" → "➕ Add Router"
5. Enter router details:
   - Alias: `home` (any name)
   - IP: `192.168.88.1`
   - Username: `admin`
   - Password: (your router password or `-` for empty)
   - Port: `8728` (or `-` for default)

The bot will auto-detect RouterOS version (6 or 7) and connect.

---

## 🔧 Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | **YES** | - | Telegram bot token from @BotFather |
| `OWNER_ID` | No | Auto-bootstrap | Your Telegram user ID (first admin) |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

### Standalone Mode (RouterOS 7 Docker)

If running **inside** a RouterOS 7 Docker container:

```env
STANDALONE=1
MIKROTIK_HOST=172.17.0.1
MIKROTIK_USER=admin
MIKROTIK_PASS=yourpassword
MIKROTIK_PORT=8728
```

The bot will auto-add the router on startup in standalone mode.

---

## 🛡 Security & RBAC

### Roles (highest to lowest)

- 👑 **Owner** — Full access, can manage bot users, add/remove routers
- 🔑 **Admin** — Full router control, cannot manage bot users
- ⚙️ **Operator** — Can view and make limited changes (no firewall/user changes)
- 👁 **Viewer** — Read-only access

### Adding Users

Owners can add users via:
- "⚙️ Settings" → "👥 Bot Users" → "➕ Add User"
- Enter the user's Telegram ID
- Default role is `viewer` — change it after adding

### Permissions Matrix

| Action | Viewer | Operator | Admin | Owner |
|--------|--------|----------|-------|-------|
| View system info | ✅ | ✅ | ✅ | ✅ |
| Toggle interfaces | ❌ | ✅ | ✅ | ✅ |
| Firewall changes | ❌ | ❌ | ✅ | ✅ |
| Add/remove routers | ❌ | ❌ | ❌ | ✅ |
| Manage bot users | ❌ | ❌ | ❌ | ✅ |

---

## 📦 Features Overview

### Core Management
- **📊 System** — Resources, health, routerboard info, reboot
- **🔌 Interfaces** — Enable/disable, traffic stats, Ethernet errors
- **🌐 IP Management** — Addresses, ARP table, IP pools, VLANs

### Security & Routing
- **🛡 Firewall** — Filter rules, NAT, Mangle, address lists, connections
- **🗺 Routes** — Static routes, gateway management
- **🌉 Bridge/VLAN** — Bridge ports, VLAN interfaces

### Network Services
- **📡 DHCP** — Leases, static bindings, DHCP servers
- **📶 Wireless** — SSID/password management, client disconnect, scan
- **🔒 VPN** — PPPoE, L2TP, OpenVPN, WireGuard, PPP secrets
- **🔥 Hotspot** — User management, active sessions, disconnect

### QoS & Traffic
- **📊 Queues** — Simple queues for bandwidth management
- **🌐 DNS** — Settings, cache, flush, set servers
- **🕐 NTP** — Time synchronization settings

### System Tools
- **📁 Files** — Browse, download, delete router files
- **📋 Logs** — View recent, filter by topic, real-time streaming
- **🔧 Tools** — Ping, traceroute, bandwidth test
- **📜 Scripts** — Browse and execute router scripts
- **🔐 Certificates** — View installed certificates
- **📦 Backup** — Create backups, export configuration

### Advanced (RouterOS 7)
- **🔗 WireGuard** — Add peers, manage interfaces
- **🐋 Containers** — Docker container management
- **🗺 BGP/OSPF** — Routing protocol monitoring
- **🌐 IPv6** — Addresses, neighbors

---

## 🐛 Troubleshooting

### "Unauthorized" Error

```
aiogram.exceptions.TelegramUnauthorizedError: Telegram server says - Unauthorized
```

**Solution:** Set `BOT_TOKEN` in `.env` or environment variable:
```bash
export BOT_TOKEN="your_actual_token_here"
```

### "No router connected"

**Solution:** Add a router via `/add_router` first

### "Cannot connect to router"

Check:
1. Router API is enabled: `/ip service print` — ensure `api` or `api-ssl` is running
2. Firewall allows API port (8728 or 8729)
3. Correct IP, username, password
4. Network connectivity between bot and router

### SSL/Port 8729

For encrypted connections:
- Router: Enable `api-ssl` service with certificate
- Bot: Enter port `8729` when adding router

### Logs Don't Stream

- Ensure you have `log.stream` permission (Operator+)
- Use `/stop_logs` to cancel existing stream before starting new one

---

## 🔒 RouterOS API Setup

### Enable API Service

```routeros
/ip service
set api disabled=no
set api port=8728
```

### Create Bot User (recommended)

```routeros
/user add name=telegram-bot group=full password=YourBotPassword
```

Use this username/password when adding the router in Telegram.

### Firewall (if restricted)

Allow API access from bot's IP:

```routeros
/ip firewall filter
add chain=input protocol=tcp dst-port=8728 src-address=YOUR_BOT_IP action=accept
```

---

## 📝 Data Storage

All data stored in `data/` directory:
- `data/rbac.json` — User roles and permissions
- `data/routers.json` — Router credentials (encrypted in production)

**Backup these files** to preserve your configuration.

---

## 🚀 Standalone Docker Mode (ROS7)

Run the bot **inside** a RouterOS 7 Docker container for zero-latency access.

### RouterOS 7 Docker Setup

1. Enable container feature:
```routeros
/container
set registry-url=https://registry-1.docker.io
set tmpdir=disk1/pull
```

2. Pull Python image:
```routeros
/container
add remote-image=python:3.11-slim interface=veth1 root-dir=disk1/mikrobot
```

3. Copy bot files into container's filesystem
4. Set environment variables in container config
5. Start container

The bot will auto-connect to `172.17.0.1` (Docker host gateway) when `STANDALONE=1`.

---

## 💡 Tips & Best Practices

1. **Start with viewer role** for new users, promote as needed
2. **Use comments** when adding firewall rules for easy identification  
3. **Backup regularly** via "📦 Backup" menu
4. **Monitor logs** during changes to catch errors
5. **Test in /tool/ping** before committing routing changes
6. **Use address lists** for dynamic IP blocking (blacklist feature)

---

## 📄 License

Open source — modify and redistribute freely.

---

## 🙏 Support

For bugs or feature requests, provide:
- RouterOS version (`/system resource print`)
- Bot logs (set `LOG_LEVEL=DEBUG`)
- Steps to reproduce

---

**Happy routing! 🎉**
