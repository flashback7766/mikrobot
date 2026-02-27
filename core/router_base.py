"""
Abstract RouterBase – defines the full interface every router implementation must expose.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class RouterBase(ABC):

    # ─── Connection ───────────────────────────────────────────────────────────

    @abstractmethod
    async def connect(self) -> bool:
        ...

    @abstractmethod
    async def close(self):
        ...

    @property
    @abstractmethod
    def connected(self) -> bool:
        ...

    # ─── System ───────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_system_resource(self) -> dict:
        """cpu-load, free-memory, total-memory, uptime, ros-version, board-name, etc."""
        ...

    @abstractmethod
    async def get_system_identity(self) -> str:
        ...

    @abstractmethod
    async def get_system_routerboard(self) -> dict:
        """board-name, serial-number, firmware, etc. Empty dict if not routerboard."""
        ...

    @abstractmethod
    async def get_system_health(self) -> dict:
        """voltage, temperature, fan-speed. Empty if not supported."""
        ...

    @abstractmethod
    async def reboot(self):
        ...

    # ─── Interfaces ───────────────────────────────────────────────────────────

    @abstractmethod
    async def get_interfaces(self) -> list[dict]:
        """All interfaces with name, type, running, disabled, rx-byte, tx-byte, etc."""
        ...

    @abstractmethod
    async def enable_interface(self, name: str):
        ...

    @abstractmethod
    async def disable_interface(self, name: str):
        ...

    @abstractmethod
    async def get_interface_traffic(self, name: str, duration: int = 5) -> dict:
        """rx-bits-per-second, tx-bits-per-second snapshot."""
        ...

    # ─── IP Addresses ─────────────────────────────────────────────────────────

    @abstractmethod
    async def get_ip_addresses(self) -> list[dict]:
        ...

    @abstractmethod
    async def add_ip_address(self, address: str, interface: str) -> str:
        """Returns .id of created entry."""
        ...

    @abstractmethod
    async def remove_ip_address(self, id_: str):
        ...

    # ─── Firewall ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_firewall_filter(self) -> list[dict]:
        ...

    @abstractmethod
    async def add_firewall_filter(self, params: dict) -> str:
        ...

    @abstractmethod
    async def remove_firewall_rule(self, id_: str):
        ...

    @abstractmethod
    async def enable_firewall_rule(self, id_: str):
        ...

    @abstractmethod
    async def disable_firewall_rule(self, id_: str):
        ...

    @abstractmethod
    async def move_firewall_rule(self, id_: str, destination: int):
        ...

    @abstractmethod
    async def get_firewall_nat(self) -> list[dict]:
        ...

    @abstractmethod
    async def add_firewall_nat(self, params: dict) -> str:
        ...

    @abstractmethod
    async def get_firewall_mangle(self) -> list[dict]:
        ...

    @abstractmethod
    async def get_address_list(self, list_name: str | None = None) -> list[dict]:
        ...

    @abstractmethod
    async def add_address_list_entry(self, address: str, list_name: str, comment: str = "") -> str:
        ...

    @abstractmethod
    async def remove_address_list_entry(self, id_: str):
        ...

    @abstractmethod
    async def get_connection_tracking(self) -> list[dict]:
        ...

    # ─── DHCP ─────────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_dhcp_server(self) -> list[dict]:
        ...

    @abstractmethod
    async def get_dhcp_leases(self) -> list[dict]:
        ...

    @abstractmethod
    async def add_dhcp_static_lease(self, mac: str, ip: str, comment: str = "") -> str:
        ...

    @abstractmethod
    async def remove_dhcp_lease(self, id_: str):
        ...

    @abstractmethod
    async def make_dhcp_lease_static(self, id_: str):
        ...

    # ─── Wireless ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_wireless_interfaces(self) -> list[dict]:
        ...

    @abstractmethod
    async def get_wireless_registrations(self) -> list[dict]:
        """Connected WiFi clients."""
        ...

    @abstractmethod
    async def get_wireless_security_profiles(self) -> list[dict]:
        ...

    @abstractmethod
    async def set_wireless_ssid(self, interface: str, ssid: str):
        ...

    @abstractmethod
    async def set_wireless_password(self, interface: str, password: str):
        ...

    @abstractmethod
    async def enable_wireless(self, interface: str):
        ...

    @abstractmethod
    async def disable_wireless(self, interface: str):
        ...

    @abstractmethod
    async def disconnect_wireless_client(self, mac: str):
        ...

    @abstractmethod
    async def get_wireless_scan(self, interface: str) -> list[dict]:
        """Available APs scan result."""
        ...

    # ─── VPN ──────────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_pppoe_server(self) -> list[dict]:
        ...

    @abstractmethod
    async def get_pppoe_active(self) -> list[dict]:
        ...

    @abstractmethod
    async def get_l2tp_server(self) -> dict:
        ...

    @abstractmethod
    async def get_ovpn_server(self) -> dict:
        ...

    @abstractmethod
    async def get_pptp_server(self) -> dict:
        ...

    @abstractmethod
    async def get_vpn_secrets(self) -> list[dict]:
        ...

    @abstractmethod
    async def add_vpn_secret(self, name: str, password: str, service: str = "any", profile: str = "default") -> str:
        ...

    @abstractmethod
    async def remove_vpn_secret(self, id_: str):
        ...

    # ─── File System ──────────────────────────────────────────────────────────

    @abstractmethod
    async def get_files(self) -> list[dict]:
        ...

    @abstractmethod
    async def delete_file(self, name: str):
        ...

    @abstractmethod
    async def get_backup_file(self, name: str) -> bytes:
        """Download a file via the FTP/API method. Returns raw bytes."""
        ...

    @abstractmethod
    async def create_backup(self, name: str = "", password: str = "") -> str:
        """Trigger /system backup save. Returns filename."""
        ...

    @abstractmethod
    async def export_config(self) -> str:
        """Return full /export as text."""
        ...

    # ─── Logs ─────────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_logs(self, limit: int = 50, topics: str = "") -> list[dict]:
        ...

    @abstractmethod
    async def stream_logs(self, topics: str = "") -> AsyncIterator[dict]:
        ...

    # ─── Routing ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_routes(self) -> list[dict]:
        ...

    @abstractmethod
    async def add_route(self, dst_address: str, gateway: str, distance: int = 1) -> str:
        ...

    @abstractmethod
    async def remove_route(self, id_: str):
        ...

    # ─── ARP ──────────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_arp(self) -> list[dict]:
        ...

    # ─── DNS ──────────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_dns_settings(self) -> dict:
        ...

    @abstractmethod
    async def set_dns_servers(self, servers: list[str]):
        ...

    @abstractmethod
    async def get_dns_cache(self) -> list[dict]:
        ...

    @abstractmethod
    async def flush_dns_cache(self):
        ...

    # ─── NTP ──────────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_ntp_client(self) -> dict:
        ...

    @abstractmethod
    async def set_ntp_servers(self, primary: str, secondary: str = ""):
        ...

    # ─── Users ────────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_users(self) -> list[dict]:
        ...

    @abstractmethod
    async def add_user(self, name: str, password: str, group: str = "read") -> str:
        ...

    @abstractmethod
    async def remove_user(self, id_: str):
        ...

    # ─── Tools ────────────────────────────────────────────────────────────────

    @abstractmethod
    async def ping(self, address: str, count: int = 4) -> list[dict]:
        ...

    @abstractmethod
    async def traceroute(self, address: str) -> list[dict]:
        ...

    @abstractmethod
    async def bandwidth_test(self, address: str, duration: int = 5) -> dict:
        ...

    # ─── IP Pools ─────────────────────────────────────────────────────────────

    async def get_ip_pools(self) -> list[dict]: return []
    async def add_ip_pool(self, name: str, ranges: str) -> str: return ""
    async def remove_ip_pool(self, id_: str): pass

    # ─── Queues / QoS ─────────────────────────────────────────────────────────

    async def get_simple_queues(self) -> list[dict]: return []
    async def add_simple_queue(self, name: str, target: str, max_limit: str = "0/0", comment: str = "") -> str: return ""
    async def remove_simple_queue(self, id_: str): pass
    async def enable_simple_queue(self, id_: str): pass
    async def disable_simple_queue(self, id_: str): pass

    # ─── Hotspot ──────────────────────────────────────────────────────────────

    async def get_hotspot_users(self) -> list[dict]: return []
    async def get_hotspot_active(self) -> list[dict]: return []
    async def add_hotspot_user(self, name: str, password: str, profile: str = "default", comment: str = "") -> str: return ""
    async def remove_hotspot_user(self, id_: str): pass
    async def disconnect_hotspot_user(self, id_: str): pass

    # ─── Scripts ──────────────────────────────────────────────────────────────

    async def get_scripts(self) -> list[dict]: return []
    async def run_script(self, name: str) -> str: return ""
    async def add_script(self, name: str, source: str, comment: str = "") -> str: return ""

    # ─── Certificates ─────────────────────────────────────────────────────────

    async def get_certificates(self) -> list[dict]: return []

    # ─── Bridges ──────────────────────────────────────────────────────────────

    async def get_bridges(self) -> list[dict]: return []
    async def get_bridge_ports(self) -> list[dict]: return []
    async def add_bridge_port(self, bridge: str, interface: str) -> str: return ""
    async def remove_bridge_port(self, id_: str): pass

    # ─── VLANs ────────────────────────────────────────────────────────────────

    async def get_vlans(self) -> list[dict]: return []
    async def add_vlan(self, name: str, vlan_id: int, interface: str) -> str: return ""
    async def remove_vlan(self, id_: str): pass

    # ─── NAT Extended ─────────────────────────────────────────────────────────

    async def remove_firewall_nat(self, id_: str): pass
    async def add_firewall_mangle(self, params: dict) -> str: return ""
    async def remove_firewall_mangle(self, id_: str): pass

    # ─── PPP Profiles ─────────────────────────────────────────────────────────

    async def get_ppp_profiles(self) -> list[dict]: return []

    # ─── Interface Ethernet Stats ──────────────────────────────────────────────

    async def get_interface_ethernet_stats(self) -> list[dict]: return []

    # ─── ROS7-only ────────────────────────────────────────────────────────────

    async def get_container_list(self) -> list[dict]:
        """ROS7 Docker containers. Returns [] on ROS6."""
        return []

    async def get_wireguard_interfaces(self) -> list[dict]:
        """ROS7 WireGuard. Returns [] on ROS6."""
        return []

    async def get_wireguard_peers(self) -> list[dict]:
        return []
