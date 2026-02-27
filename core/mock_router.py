"""
Mock Router – implements all RouterBase methods with realistic fake data.
Used when no real router is available (development / demo mode).
"""

import asyncio
import random
import string
from datetime import datetime, timedelta
from typing import AsyncIterator

from .router_base import RouterBase


def _rand_mac():
    return ":".join(f"{random.randint(0, 255):02X}" for _ in range(6))


def _rand_ip(prefix="192.168.88"):
    return f"{prefix}.{random.randint(2, 254)}"


class MockRouter(RouterBase):

    def __init__(self):
        self._connected = True
        self._uptime_start = datetime.now() - timedelta(days=2, hours=4, minutes=33)
        self._interfaces = [
            {"name": "ether1", "type": "ether", "running": "true", "disabled": "false",
             "rx-byte": str(random.randint(10**8, 10**10)), "tx-byte": str(random.randint(10**8, 10**10)),
             "mac-address": "AA:BB:CC:DD:EE:01", "comment": "WAN"},
            {"name": "ether2", "type": "ether", "running": "true", "disabled": "false",
             "rx-byte": str(random.randint(10**8, 10**10)), "tx-byte": str(random.randint(10**8, 10**10)),
             "mac-address": "AA:BB:CC:DD:EE:02", "comment": "LAN"},
            {"name": "wlan1", "type": "wlan", "running": "true", "disabled": "false",
             "rx-byte": str(random.randint(10**7, 10**9)), "tx-byte": str(random.randint(10**7, 10**9)),
             "mac-address": "AA:BB:CC:DD:EE:03", "comment": "WiFi 2.4GHz"},
            {"name": "wlan2", "type": "wlan", "running": "true", "disabled": "false",
             "rx-byte": str(random.randint(10**7, 10**9)), "tx-byte": str(random.randint(10**7, 10**9)),
             "mac-address": "AA:BB:CC:DD:EE:04", "comment": "WiFi 5GHz"},
        ]
        self._firewall_filter = [
            {".id": "*1", "chain": "input", "protocol": "icmp", "action": "accept", "comment": "Allow ping", "disabled": "false", "bytes": "1024"},
            {".id": "*2", "chain": "input", "protocol": "tcp", "dst-port": "8291", "action": "accept", "comment": "Allow WinBox", "disabled": "false", "bytes": "512"},
            {".id": "*3", "chain": "forward", "connection-state": "established,related", "action": "accept", "comment": "Allow established", "disabled": "false", "bytes": "50000"},
            {".id": "*4", "chain": "forward", "connection-state": "invalid", "action": "drop", "comment": "Drop invalid", "disabled": "false", "bytes": "128"},
            {".id": "*5", "chain": "input", "action": "drop", "comment": "Drop all input", "disabled": "false", "bytes": "256"},
        ]
        self._firewall_nat = [
            {".id": "*1", "chain": "srcnat", "out-interface": "ether1", "action": "masquerade",
             "comment": "Masquerade WAN", "disabled": "false", "bytes": "100000"},
        ]
        self._dhcp_leases = [
            {"address": "192.168.88.10", "mac-address": "AA:11:BB:22:CC:33",
             "host-name": "desktop-pc", "type": "static", "status": "bound",
             "expires-after": "23:59:00", ".id": "*1"},
            {"address": "192.168.88.11", "mac-address": "DD:44:EE:55:FF:66",
             "host-name": "laptop", "type": "dynamic", "status": "bound",
             "expires-after": "10:22:00", ".id": "*2"},
            {"address": "192.168.88.12", "mac-address": "11:22:33:44:55:66",
             "host-name": "phone", "type": "dynamic", "status": "bound",
             "expires-after": "05:00:00", ".id": "*3"},
        ]
        self._address_list = [
            {".id": "*1", "list": "blacklist", "address": "185.220.101.1", "comment": "TOR exit"},
            {".id": "*2", "list": "blacklist", "address": "45.142.212.0/24", "comment": "Known attacker"},
            {".id": "*3", "list": "whitelist", "address": "192.168.88.0/24", "comment": "LAN"},
        ]
        self._vpn_secrets = [
            {".id": "*1", "name": "user1", "password": "pass1", "service": "any", "profile": "default"},
            {".id": "*2", "name": "user2", "password": "pass2", "service": "l2tp", "profile": "default"},
        ]
        self._routes = [
            {".id": "*1", "dst-address": "0.0.0.0/0", "gateway": "10.0.0.1", "distance": "1",
             "active": "true", "static": "true"},
            {".id": "*2", "dst-address": "192.168.88.0/24", "gateway": "ether2", "distance": "0",
             "active": "true", "static": "false"},
        ]
        self._files = [
            {"name": "backup.backup", "size": "48000", "creation-time": "2025-01-15 10:00:00", "type": "backup"},
            {"name": "flash/config.rsc", "size": "12000", "creation-time": "2025-01-10 08:30:00", "type": "script"},
        ]
        self._log_topics = ["system", "info", "warning", "error", "firewall", "dhcp", "wireless"]
        self._wireless_clients = [
            {"mac-address": "11:22:33:44:55:66", "interface": "wlan1", "signal-strength": "-65dBm",
             "tx-rate": "54Mbps", "rx-rate": "54Mbps", "uptime": "01:23:00", "comment": "phone"},
            {"mac-address": "AA:BB:CC:DD:EE:FF", "interface": "wlan2", "signal-strength": "-50dBm",
             "tx-rate": "300Mbps", "rx-rate": "300Mbps", "uptime": "03:45:00", "comment": "laptop"},
        ]

    # ─── Connection ───────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        return True

    async def close(self):
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    # ─── System ───────────────────────────────────────────────────────────────

    async def get_system_resource(self) -> dict:
        uptime = datetime.now() - self._uptime_start
        total_h = int(uptime.total_seconds() // 3600)
        d, h = divmod(total_h, 24)
        m = int((uptime.total_seconds() % 3600) // 60)
        return {
            "uptime": f"{d}d{h:02d}:{m:02d}:00",
            "version": "7.12.1 (stable)",
            "build-time": "Jan/15/2025 08:00:00",
            "cpu-load": str(random.randint(5, 45)),
            "free-memory": str(random.randint(20, 80) * 1024 * 1024),
            "total-memory": str(256 * 1024 * 1024),
            "free-hdd-space": str(random.randint(10, 50) * 1024 * 1024),
            "total-hdd-space": str(128 * 1024 * 1024),
            "board-name": "RB4011iGS+",
            "architecture-name": "arm64",
            "cpu": "ARM Cortex-A57",
            "cpu-count": "4",
            "cpu-frequency": "1400",
        }

    async def get_system_identity(self) -> str:
        return "MikroBot-Demo"

    async def get_system_routerboard(self) -> dict:
        return {
            "routerboard": "true",
            "board-name": "RB4011iGS+",
            "model": "RB4011iGS+",
            "serial-number": "DEMO0001",
            "firmware-type": "ipq40xx",
            "factory-firmware": "7.1.5",
            "current-firmware": "7.12.1",
            "upgrade-firmware": "7.12.1",
        }

    async def get_system_health(self) -> dict:
        return {
            "temperature": str(random.randint(35, 55)),
            "cpu-temperature": str(random.randint(40, 70)),
        }

    async def reboot(self):
        self._connected = False

    # ─── Interfaces ───────────────────────────────────────────────────────────

    async def get_interfaces(self) -> list[dict]:
        ifaces = []
        for i in self._interfaces:
            iface = dict(i)
            iface["rx-byte"] = str(int(i["rx-byte"]) + random.randint(1000, 100000))
            iface["tx-byte"] = str(int(i["tx-byte"]) + random.randint(1000, 100000))
            ifaces.append(iface)
        return ifaces

    async def enable_interface(self, name: str):
        for i in self._interfaces:
            if i["name"] == name:
                i["running"] = "true"
                i["disabled"] = "false"

    async def disable_interface(self, name: str):
        for i in self._interfaces:
            if i["name"] == name:
                i["running"] = "false"
                i["disabled"] = "true"

    async def get_interface_traffic(self, name: str, duration: int = 5) -> dict:
        return {
            "name": name,
            "rx-bits-per-second": str(random.randint(100000, 100_000_000)),
            "tx-bits-per-second": str(random.randint(100000, 50_000_000)),
            "rx-packets-per-second": str(random.randint(10, 5000)),
            "tx-packets-per-second": str(random.randint(10, 5000)),
        }

    # ─── IP Addresses ─────────────────────────────────────────────────────────

    async def get_ip_addresses(self) -> list[dict]:
        return [
            {".id": "*1", "address": "10.0.0.2/24", "interface": "ether1", "network": "10.0.0.0", "dynamic": "false"},
            {".id": "*2", "address": "192.168.88.1/24", "interface": "ether2", "network": "192.168.88.0", "dynamic": "false"},
            {".id": "*3", "address": "192.168.89.1/24", "interface": "wlan1", "network": "192.168.89.0", "dynamic": "false"},
        ]

    async def add_ip_address(self, address: str, interface: str) -> str:
        return f"*{random.randint(10, 99)}"

    async def remove_ip_address(self, id_: str):
        pass

    # ─── Firewall ─────────────────────────────────────────────────────────────

    async def get_firewall_filter(self) -> list[dict]:
        return list(self._firewall_filter)

    async def add_firewall_filter(self, params: dict) -> str:
        new_id = f"*{random.randint(100, 999)}"
        rule = dict(params)
        rule[".id"] = new_id
        rule.setdefault("disabled", "false")
        rule.setdefault("bytes", "0")
        self._firewall_filter.append(rule)
        return new_id

    async def remove_firewall_rule(self, id_: str):
        self._firewall_filter = [r for r in self._firewall_filter if r.get(".id") != id_]

    async def enable_firewall_rule(self, id_: str):
        for r in self._firewall_filter:
            if r.get(".id") == id_:
                r["disabled"] = "false"

    async def disable_firewall_rule(self, id_: str):
        for r in self._firewall_filter:
            if r.get(".id") == id_:
                r["disabled"] = "true"

    async def move_firewall_rule(self, id_: str, destination: int):
        pass  # No-op in mock

    async def get_firewall_nat(self) -> list[dict]:
        return list(self._firewall_nat)

    async def add_firewall_nat(self, params: dict) -> str:
        return f"*{random.randint(100, 999)}"

    async def get_firewall_mangle(self) -> list[dict]:
        return []

    async def get_address_list(self, list_name: str | None = None) -> list[dict]:
        if list_name:
            return [e for e in self._address_list if e.get("list") == list_name]
        return list(self._address_list)

    async def add_address_list_entry(self, address: str, list_name: str, comment: str = "") -> str:
        new_id = f"*{random.randint(100, 999)}"
        self._address_list.append({".id": new_id, "list": list_name, "address": address, "comment": comment})
        return new_id

    async def remove_address_list_entry(self, id_: str):
        self._address_list = [e for e in self._address_list if e.get(".id") != id_]

    async def get_connection_tracking(self) -> list[dict]:
        return [
            {"src-address": _rand_ip(), "dst-address": _rand_ip("8.8"),
             "protocol": random.choice(["tcp", "udp"]), "state": "established"}
            for _ in range(random.randint(5, 20))
        ]

    # ─── DHCP ─────────────────────────────────────────────────────────────────

    async def get_dhcp_server(self) -> list[dict]:
        return [{"name": "dhcp1", "interface": "ether2", "address-pool": "dhcp_pool",
                 "lease-time": "1d", "disabled": "false"}]

    async def get_dhcp_leases(self) -> list[dict]:
        return list(self._dhcp_leases)

    async def add_dhcp_static_lease(self, mac: str, ip: str, comment: str = "") -> str:
        new_id = f"*{random.randint(100, 999)}"
        self._dhcp_leases.append({
            "address": ip, "mac-address": mac, "host-name": comment or "new-device",
            "type": "static", "status": "bound", "expires-after": "never", ".id": new_id,
        })
        return new_id

    async def remove_dhcp_lease(self, id_: str):
        self._dhcp_leases = [l for l in self._dhcp_leases if l.get(".id") != id_]

    async def make_dhcp_lease_static(self, id_: str):
        for l in self._dhcp_leases:
            if l.get(".id") == id_:
                l["type"] = "static"

    # ─── Wireless ─────────────────────────────────────────────────────────────

    async def get_wireless_interfaces(self) -> list[dict]:
        return [
            {"name": "wlan1", "ssid": "HomeNetwork", "frequency": "2437", "band": "2ghz-b/g/n",
             "security-profile": "default", "disabled": "false", "running": "true",
             "tx-power": "20", "channel-width": "20/40MHz"},
            {"name": "wlan2", "ssid": "HomeNetwork_5G", "frequency": "5180", "band": "5ghz-n/ac",
             "security-profile": "default", "disabled": "false", "running": "true",
             "tx-power": "20", "channel-width": "20/40/80MHz"},
        ]

    async def get_wireless_registrations(self) -> list[dict]:
        return list(self._wireless_clients)

    async def get_wireless_security_profiles(self) -> list[dict]:
        return [
            {"name": "default", "mode": "dynamic-keys", "authentication-types": "wpa2-psk",
             "wpa2-pre-shared-key": "supersecret123", "group-key-update": "5m"},
        ]

    async def set_wireless_ssid(self, interface: str, ssid: str):
        pass

    async def set_wireless_password(self, interface: str, password: str):
        pass

    async def enable_wireless(self, interface: str):
        pass

    async def disable_wireless(self, interface: str):
        pass

    async def disconnect_wireless_client(self, mac: str):
        self._wireless_clients = [c for c in self._wireless_clients if c.get("mac-address") != mac]

    async def get_wireless_scan(self, interface: str) -> list[dict]:
        return [
            {"ssid": f"Network-{i}", "bssid": _rand_mac(), "signal": str(random.randint(-80, -30)),
             "channel": str(random.choice([1, 6, 11, 36, 48, 149])), "security": "WPA2"}
            for i in range(random.randint(3, 8))
        ]

    # ─── VPN ──────────────────────────────────────────────────────────────────

    async def get_pppoe_server(self) -> list[dict]:
        return [{"name": "pppoe-in1", "interface": "ether1", "enabled": "yes"}]

    async def get_pppoe_active(self) -> list[dict]:
        return [{"name": "pppoe-user1", "address": "10.0.0.5", "caller-id": _rand_mac(), "uptime": "02:30:00"}]

    async def get_l2tp_server(self) -> dict:
        return {"enabled": "yes", "authentication": "chap,mschap1,mschap2"}

    async def get_ovpn_server(self) -> dict:
        return {"enabled": "no", "port": "1194"}

    async def get_pptp_server(self) -> dict:
        return {"enabled": "no"}

    async def get_vpn_secrets(self) -> list[dict]:
        return list(self._vpn_secrets)

    async def add_vpn_secret(self, name: str, password: str, service: str = "any", profile: str = "default") -> str:
        new_id = f"*{random.randint(100, 999)}"
        self._vpn_secrets.append({".id": new_id, "name": name, "password": password,
                                   "service": service, "profile": profile})
        return new_id

    async def remove_vpn_secret(self, id_: str):
        self._vpn_secrets = [s for s in self._vpn_secrets if s.get(".id") != id_]

    # ─── File System ──────────────────────────────────────────────────────────

    async def get_files(self) -> list[dict]:
        return list(self._files)

    async def delete_file(self, name: str):
        self._files = [f for f in self._files if f.get("name") != name]

    async def get_backup_file(self, name: str) -> bytes:
        return b"# Mock backup file\n# This is a demo\n/system identity set name=Demo\n"

    async def create_backup(self, name: str = "", password: str = "") -> str:
        fname = (name or "backup") + ".backup"
        self._files.append({
            "name": fname, "size": str(random.randint(40000, 60000)),
            "creation-time": datetime.now().strftime("%b/%d/%Y %H:%M:%S"),
            "type": "backup",
        })
        return fname

    async def export_config(self) -> str:
        return (
            "# RouterOS 7.12.1\n"
            "# Software ID = DEMO-0001\n"
            "/system identity set name=MikroBot-Demo\n"
            "/ip address add address=192.168.88.1/24 interface=ether2\n"
            "/ip dhcp-server add interface=ether2 name=dhcp1\n"
            "/ip firewall nat add chain=srcnat out-interface=ether1 action=masquerade\n"
        )

    # ─── Logs ─────────────────────────────────────────────────────────────────

    async def get_logs(self, limit: int = 50, topics: str = "") -> list[dict]:
        entries = []
        base_time = datetime.now()
        for i in range(min(limit, 30)):
            t = base_time - timedelta(seconds=i * 30)
            topic = random.choice(self._log_topics)
            entries.append({
                "time": t.strftime("%b/%d %H:%M:%S"),
                "topics": topic,
                "message": self._fake_log_message(topic),
            })
        return list(reversed(entries))

    async def stream_logs(self, topics: str = "") -> AsyncIterator[dict]:
        while True:
            await asyncio.sleep(random.uniform(2, 8))
            topic = random.choice(self._log_topics)
            yield {
                "time": datetime.now().strftime("%b/%d %H:%M:%S"),
                "topics": topic,
                "message": self._fake_log_message(topic),
            }

    @staticmethod
    def _fake_log_message(topic: str) -> str:
        messages = {
            "system": ["router rebooted", "configuration changed", "user logged in"],
            "info": ["interface ether1 link up", "DHCP pool almost full"],
            "warning": ["high CPU load detected", "memory usage above 80%"],
            "error": ["failed to connect to NTP server", "OSPF neighbor lost"],
            "firewall": [f"forward: in:ether1 out:ether2, src-mac {_rand_mac()}, proto TCP",
                         f"input drop: src-ip {_rand_ip('185.220')}"],
            "dhcp": [f"assigned {_rand_ip()} to {_rand_mac()}", "lease renewed"],
            "wireless": [f"client {_rand_mac()} connected", f"client {_rand_mac()} disconnected"],
        }
        options = messages.get(topic, ["event occurred"])
        return random.choice(options)

    # ─── Routing ──────────────────────────────────────────────────────────────

    async def get_routes(self) -> list[dict]:
        return list(self._routes)

    async def add_route(self, dst_address: str, gateway: str, distance: int = 1) -> str:
        new_id = f"*{random.randint(100, 999)}"
        self._routes.append({".id": new_id, "dst-address": dst_address, "gateway": gateway,
                              "distance": str(distance), "active": "true", "static": "true"})
        return new_id

    async def remove_route(self, id_: str):
        self._routes = [r for r in self._routes if r.get(".id") != id_]

    # ─── ARP ──────────────────────────────────────────────────────────────────

    async def get_arp(self) -> list[dict]:
        return [
            {"address": "192.168.88.10", "mac-address": "AA:11:BB:22:CC:33", "interface": "ether2", "complete": "yes"},
            {"address": "192.168.88.11", "mac-address": "DD:44:EE:55:FF:66", "interface": "ether2", "complete": "yes"},
        ]

    # ─── DNS ──────────────────────────────────────────────────────────────────

    async def get_dns_settings(self) -> dict:
        return {"servers": "1.1.1.1,8.8.8.8", "allow-remote-requests": "yes",
                "cache-max-ttl": "1w", "cache-size": "2048"}

    async def set_dns_servers(self, servers: list[str]):
        pass

    async def get_dns_cache(self) -> list[dict]:
        return [{"name": "example.com", "address": "93.184.216.34", "ttl": "3600", "type": "A"},
                {"name": "google.com", "address": "142.250.185.78", "ttl": "300", "type": "A"}]

    async def flush_dns_cache(self):
        pass

    # ─── NTP ──────────────────────────────────────────────────────────────────

    async def get_ntp_client(self) -> dict:
        return {"enabled": "yes", "primary-ntp": "0.pool.ntp.org",
                "secondary-ntp": "1.pool.ntp.org", "server-dns-names": "", "mode": "unicast"}

    async def set_ntp_servers(self, primary: str, secondary: str = ""):
        pass

    # ─── Users ────────────────────────────────────────────────────────────────

    async def get_users(self) -> list[dict]:
        return [
            {".id": "*1", "name": "admin", "group": "full", "last-logged-in": datetime.now().strftime("%b/%d/%Y %H:%M:%S"), "address": ""},
            {".id": "*2", "name": "read-only", "group": "read", "last-logged-in": "never", "address": ""},
        ]

    async def add_user(self, name: str, password: str, group: str = "read") -> str:
        return f"*{random.randint(10, 99)}"

    async def remove_user(self, id_: str):
        pass

    # ─── Tools ────────────────────────────────────────────────────────────────

    async def ping(self, address: str, count: int = 4) -> list[dict]:
        results = []
        for i in range(count):
            await asyncio.sleep(0.1)
            loss = random.random() < 0.1
            results.append({
                "host": address,
                "sent": str(i + 1),
                "received": "0" if loss else "1",
                "time": "0" if loss else str(random.randint(1, 50)),
                "ttl": "64" if not loss else "",
            })
        return results

    async def traceroute(self, address: str) -> list[dict]:
        hops = []
        for i in range(1, random.randint(5, 12)):
            await asyncio.sleep(0.05)
            hops.append({
                "address": _rand_ip(f"10.{i}"),
                "time": str(random.randint(1, 100)),
                "count": str(i),
                "status": "timed-out" if random.random() < 0.1 else "",
            })
        hops.append({"address": address, "time": str(random.randint(20, 200)), "count": str(len(hops) + 1), "status": ""})
        return hops

    async def bandwidth_test(self, address: str, duration: int = 5) -> dict:
        return {
            "tx-total-average": str(random.randint(10_000_000, 100_000_000)),
            "rx-total-average": str(random.randint(10_000_000, 100_000_000)),
            "lost-packets": str(random.randint(0, 5)),
            "random-data": "true",
        }
