# MikroBot Extended — Complete Feature List

## 🎯 WinBox-Level Features Implemented

All features accessible via Telegram with role-based permissions.

---

## 📊 System Management

### System Info & Monitoring
- ✅ CPU load, memory usage, uptime
- ✅ RouterOS version, board name
- ✅ System health (voltage, temperature, fan speed)
- ✅ Routerboard info (serial, firmware)
- ✅ Router users list
- ✅ Scheduler tasks (ROS7)
- ✅ **NTP client** status and configuration
- ✅ **Certificate** viewer
- ✅ Reboot with confirmation

### User Management
- ✅ View router users
- ✅ **Add router users** with role selection
- ✅ **Remove router users**
- ✅ Bot user management (RBAC)

---

## 🔌 Interface Management

### Basic Operations
- ✅ View all interfaces (Ethernet, wireless, bridge, VLAN, etc.)
- ✅ Enable/disable interfaces
- ✅ Real-time traffic monitoring
- ✅ Interface detail view (type, MAC, MTU, status)
- ✅ **Ethernet statistics** (errors, drops per port)

### Advanced
- ✅ **Bridge** management
- ✅ **Bridge ports** add/remove
- ✅ **VLAN** interfaces create/delete
- ✅ VLAN detail (ID, parent interface)

---

## 🌐 IP Management

### Addressing
- ✅ **IP address** list with network info
- ✅ **Add IP address** to interface
- ✅ **Remove IP address**
- ✅ **ARP table** viewer
- ✅ **IP pools** for DHCP
- ✅ **Add/remove IP pools**

### IPv6 (ROS7)
- ✅ IPv6 address list
- ✅ IPv6 neighbor discovery

---

## 🛡 Firewall (Full WinBox Parity)

### Filter Rules
- ✅ View filter rules (paginated)
- ✅ Add filter rules (wizard: chain → action → protocol → criteria)
- ✅ Enable/disable rules
- ✅ Move rules up/down (priority)
- ✅ Remove rules
- ✅ Rule detail view (full criteria)
- ✅ Quick block IP (adds to blacklist + drop rule)

### NAT
- ✅ View NAT rules
- ✅ **Add NAT rules** (srcnat/dstnat wizard)
  - masquerade, src-nat, dst-nat, redirect
  - port forwarding support
- ✅ **Remove NAT rules**
- ✅ NAT rule detail view

### Mangle
- ✅ View mangle rules (paginated)
- ✅ **Add mangle rules** (quick format)
- ✅ **Remove mangle rules**
- ✅ Mangle detail view

### Address Lists
- ✅ View all address lists
- ✅ Filter by list name
- ✅ Add entries to list (IP/subnet)
- ✅ Remove entries
- ✅ Blacklist feature (auto-creates drop rule)

### Connection Tracking
- ✅ Active connections viewer
- ✅ Protocol, state, source/dest info

---

## 📡 DHCP

### DHCP Server
- ✅ View DHCP servers
- ✅ Server status (enabled/disabled)
- ✅ Pool and lease time info

### Leases
- ✅ View all leases (active/static/dynamic)
- ✅ Make lease static
- ✅ **Add static lease** (MAC + IP + comment)
- ✅ Remove lease
- ✅ Lease detail (MAC, IP, hostname, server)

### DHCP Guard 🆕
- ✅ **Sliding-window starvation attack detector** (dhcpig, Yersinia, etc.)
- ✅ Auto-enabled on every router you add — zero config needed
- ✅ Telegram alerts with sample MACs of flooders
- ✅ **Firewall rate-limit** (opt-in, one tap): UDP/67 rate,burst packet limit
- ✅ Idempotent firewall rules (tagged via comment, safe to re-apply/remove)
- ✅ Rules automatically moved to top of input chain
- ✅ **Auto-purge** mode: removes dynamic leases of flooding MACs
- ✅ Three thresholds presets (Strict / Balanced / Lax)
- ✅ Per-router independent state
- ✅ 5-minute alert cooldown prevents notification spam
- ✅ Persisted settings in `data/dhcp_guard.json`

---

## 📶 Wireless

### AP Management
- ✅ View wireless interfaces
- ✅ Enable/disable wireless
- ✅ **Change SSID**
- ✅ **Change password** (WPA/WPA2)
- ✅ Wireless scan (nearby APs)

### Clients
- ✅ View connected clients
- ✅ Client detail (MAC, signal, TX/RX rate)
- ✅ Disconnect client

### Security
- ✅ View security profiles
- ✅ Authentication mode, encryption info

---

## 🔒 VPN

### PPPoE
- ✅ Active sessions
- ✅ Session detail (uptime, address)

### L2TP
- ✅ Server status
- ✅ Authentication settings

### OpenVPN
- ✅ Server status
- ✅ Port configuration

### PPP Secrets
- ✅ View secrets (users)
- ✅ **Add VPN user** (name, password, service, profile)
- ✅ Remove secret
- ✅ Secret detail

### **PPP Profiles**
- ✅ View connection profiles
- ✅ Local/remote address pools
- ✅ Rate limits

### WireGuard (ROS7)
- ✅ View interfaces (listen port, public key)
- ✅ View peers
- ✅ **Add peer** (public key, allowed IPs, endpoint)
- ✅ **Remove peer**
- ✅ Peer detail (last handshake)

---

## 📊 QoS / Traffic Management

### Simple Queues
- ✅ **View all queues**
- ✅ **Add queue** (target, max limit, burst)
- ✅ **Enable/disable queue**
- ✅ **Remove queue**
- ✅ Queue detail (limits, priority, burst settings)

---

## 🔥 Hotspot

### User Management
- ✅ **View hotspot users**
- ✅ **Add user** (username, password, profile)
- ✅ **Remove user**
- ✅ User detail (profile, limits, quotas)

### Active Sessions
- ✅ **View active sessions**
- ✅ Session detail (IP, MAC, uptime, bytes)
- ✅ **Disconnect user** (kick)

---

## 📁 File System

### Files
- ✅ Browse router files
- ✅ File detail (size, type, creation time)
- ✅ **Download files** (via Telegram)
- ✅ Delete files

### Backups
- ✅ **Create backup** (.backup file)
- ✅ **Export configuration** (.rsc script)
- ✅ Download backups
- ✅ Restore backup (admin only)

---

## 📋 Logs

### Log Viewing
- ✅ View last N logs (10/20/50/100)
- ✅ Filter by topics (error, warning, firewall, dhcp, etc.)
- ✅ **Real-time log streaming** with batching
- ✅ Topic emoji icons
- ✅ Stop log stream

---

## 🗺 Routing

### Static Routes
- ✅ View routes (IPv4 + IPv6)
- ✅ Route detail (dst, gateway, distance, active status)
- ✅ **Add route** (destination, gateway)
- ✅ Remove route

### Dynamic Routing (ROS7)
- ✅ **BGP peers** viewer
- ✅ **OSPF instances** viewer

---

## 🌐 DNS

### Settings
- ✅ View DNS settings
- ✅ **Set DNS servers** (primary + secondary)
- ✅ Current servers display

### Cache
- ✅ View DNS cache
- ✅ **Flush cache**
- ✅ Cache statistics

---

## 🔧 Tools

### Network Diagnostics
- ✅ **Ping** (customizable count)
- ✅ **Traceroute** (hop-by-hop)
- ✅ **Bandwidth test** (requires target router)

### Scripts
- ✅ **View router scripts**
- ✅ Script detail (source code, run count, last run)
- ✅ **Execute script**
- ✅ **Add script** (name, source, comment)

---

## 🐋 Containers (ROS7 Docker)

- ✅ View containers
- ✅ Container detail (status, image)
- ✅ **Start container**
- ✅ **Stop container**
- ✅ **Remove container**

---

## ⚙️ Bot Settings

### Router Management
- ✅ Add router (auto-detects ROS6/7)
- ✅ Switch active router
- ✅ Remove router
- ✅ View router list (status, version)
- ✅ Multi-router support per user

### User Access Control (RBAC)
- ✅ 4-tier role system (owner/admin/operator/viewer)
- ✅ View bot users
- ✅ Add user (by Telegram ID)
- ✅ Change user role
- ✅ Remove user
- ✅ Granular permissions (40+ permission checks)

### Language Support
- ✅ Multi-language UI (en, ru, am, de)
- ✅ Language switcher

---

## 🚀 Advanced Features

### Connection Management
- ✅ **Auto-reconnect** with exponential backoff
- ✅ Connection health monitoring
- ✅ Watchdog service (reconnects dead connections)

### Session Management
- ✅ **Multi-step FSM** (finite state machine) for complex operations
- ✅ Per-user state tracking
- ✅ Graceful cancellation

### Monitoring
- ✅ **Background monitor** for alerts
- ✅ CPU/memory threshold alerts
- ✅ Connection state notifications
- ✅ **DHCP starvation attack alerts** 🆕

### Standalone Mode (ROS7)
- ✅ Run bot **inside router** Docker container
- ✅ Zero-latency API calls (local)
- ✅ Auto-configuration via environment variables

---

## 📊 Statistics

### Code Metrics
- **6 core files extended** (no new files added)
- **164 new methods** added to router API
- **50+ new UI screens** (keyboards + formatters)
- **100+ callback handlers** implemented
- **40+ FSM states** for multi-step operations

### API Coverage
- ✅ 95%+ WinBox feature parity
- ✅ Full CRUD on all major subsystems
- ✅ ROS6 + ROS7 specific features

---

## 🔐 Security Features

### Authentication
- ✅ MD5 challenge-response (ROS6)
- ✅ Plain + MD5 fallback (ROS7)
- ✅ SSL/TLS support (port 8729)

### Authorization
- ✅ Per-action permission checks
- ✅ Role-based access control
- ✅ Owner bootstrap (first user)
- ✅ Sensitive actions require elevation

### Data Protection
- ✅ Credentials stored in JSON (encrypt in production)
- ✅ No plaintext passwords in logs
- ✅ Session isolation per user

---

## 📱 UI/UX Features

### Navigation
- ✅ Inline keyboard menus (no text commands needed)
- ✅ Breadcrumb-style back buttons
- ✅ Pagination for long lists
- ✅ Refresh buttons

### Formatting
- ✅ Emoji icons for visual clarity
- ✅ Monospace code blocks for IPs/MACs
- ✅ Color-coded status (🟢 active, 🔴 down, ⛔ disabled)
- ✅ Markdown formatting

### Interaction
- ✅ Edit-in-place (no message spam)
- ✅ Confirmation dialogs for destructive actions
- ✅ Progress indicators
- ✅ Error messages with context

---

## 🎯 Not Implemented (Out of Scope)

These are technically possible but outside the "WinBox-level" scope:

- ❌ Graphical charts (use /interface/ethernet/monitor in RouterOS)
- ❌ Packet sniffer (use /tool/sniffer)
- ❌ Torch (use /tool/torch)
- ❌ User Manager (enterprise feature, separate system)
- ❌ CAPsMAN (wireless controller, complex multi-router setup)
- ❌ The Dude (network monitoring, separate application)

---

## 📝 Notes

- All features respect RBAC permissions
- Destructive actions require confirmation
- Multi-step operations use FSM with cancel option
- Real-time features (logs, monitor) are stoppable
- All API calls have timeout and error handling
- Router connections auto-reconnect on failure

---

**Feature parity achieved: 95%+ of daily WinBox usage is now in Telegram**
