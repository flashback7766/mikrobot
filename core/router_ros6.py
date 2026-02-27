"""
RouterOS 6 implementation.
Runs only in NSA mode (bot runs on external PC, connects to router API port 8728/8729).
ROS6 does not support Docker containers.
"""

import asyncio
import logging
from typing import AsyncIterator

from .router_base import RouterBase
from .router_client import RouterAPIClient, APIError

log = logging.getLogger("ROS6")


class RouterROS6(RouterBase):

    def __init__(self, host: str, username: str, password: str, port: int = 8728, use_ssl: bool = False):
        self._client = RouterAPIClient(
            host=host, username=username, password=password,
            port=port, use_ssl=use_ssl, ros_version=6,
        )
        self.host = host

    # ─── Connection ───────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        return await self._client.connect()

    async def close(self):
        await self._client.close()

    @property
    def connected(self) -> bool:
        return self._client.connected

    # ─── System ───────────────────────────────────────────────────────────────

    async def get_system_resource(self) -> dict:
        r = await self._client.command_one("/system/resource/print")
        return r or {}

    async def get_system_identity(self) -> str:
        r = await self._client.command_one("/system/identity/print")
        return r.get("name", "unknown") if r else "unknown"

    async def get_system_routerboard(self) -> dict:
        try:
            r = await self._client.command_one("/system/routerboard/print")
            return r or {}
        except APIError:
            return {}

    async def get_system_health(self) -> dict:
        try:
            r = await self._client.command_one("/system/health/print")
            return r or {}
        except APIError:
            return {}

    async def reboot(self):
        try:
            await self._client.command("/system/reboot")
        except APIError:
            pass  # connection drops immediately on reboot

    # ─── Interfaces ───────────────────────────────────────────────────────────

    async def get_interfaces(self) -> list[dict]:
        return await self._client.command("/interface/print")

    async def enable_interface(self, name: str):
        await self._client.command("/interface/enable", {"numbers": name})

    async def disable_interface(self, name: str):
        await self._client.command("/interface/disable", {"numbers": name})

    async def get_interface_traffic(self, name: str, duration: int = 5) -> dict:
        results = await self._client.command(
            "/interface/monitor-traffic",
            {"interface": name, "once": ""},
        )
        return results[0] if results else {}

    # ─── IP Addresses ─────────────────────────────────────────────────────────

    async def get_ip_addresses(self) -> list[dict]:
        return await self._client.command("/ip/address/print")

    async def add_ip_address(self, address: str, interface: str) -> str:
        result = await self._client.command("/ip/address/add", {
            "address": address, "interface": interface,
        })
        return result[0].get("ret", "") if result else ""

    async def remove_ip_address(self, id_: str):
        await self._client.command("/ip/address/remove", {"numbers": id_})

    # ─── Firewall ─────────────────────────────────────────────────────────────

    async def get_firewall_filter(self) -> list[dict]:
        return await self._client.command("/ip/firewall/filter/print")

    async def add_firewall_filter(self, params: dict) -> str:
        r = await self._client.command("/ip/firewall/filter/add", params)
        return r[0].get("ret", "") if r else ""

    async def remove_firewall_rule(self, id_: str):
        await self._client.command("/ip/firewall/filter/remove", {"numbers": id_})

    async def enable_firewall_rule(self, id_: str):
        await self._client.command("/ip/firewall/filter/enable", {"numbers": id_})

    async def disable_firewall_rule(self, id_: str):
        await self._client.command("/ip/firewall/filter/disable", {"numbers": id_})

    async def move_firewall_rule(self, id_: str, destination: int):
        await self._client.command("/ip/firewall/filter/move", {
            "numbers": id_, "destination": str(destination),
        })

    async def get_firewall_nat(self) -> list[dict]:
        return await self._client.command("/ip/firewall/nat/print")

    async def add_firewall_nat(self, params: dict) -> str:
        r = await self._client.command("/ip/firewall/nat/add", params)
        return r[0].get("ret", "") if r else ""

    async def get_firewall_mangle(self) -> list[dict]:
        return await self._client.command("/ip/firewall/mangle/print")

    async def get_address_list(self, list_name: str | None = None) -> list[dict]:
        queries = []
        if list_name:
            queries = [f"?list={list_name}"]
        return await self._client.command("/ip/firewall/address-list/print", queries=queries)

    async def add_address_list_entry(self, address: str, list_name: str, comment: str = "") -> str:
        params = {"address": address, "list": list_name}
        if comment:
            params["comment"] = comment
        r = await self._client.command("/ip/firewall/address-list/add", params)
        return r[0].get("ret", "") if r else ""

    async def remove_address_list_entry(self, id_: str):
        await self._client.command("/ip/firewall/address-list/remove", {"numbers": id_})

    async def get_connection_tracking(self) -> list[dict]:
        return await self._client.command("/ip/firewall/connection/print")

    # ─── DHCP ─────────────────────────────────────────────────────────────────

    async def get_dhcp_server(self) -> list[dict]:
        return await self._client.command("/ip/dhcp-server/print")

    async def get_dhcp_leases(self) -> list[dict]:
        return await self._client.command("/ip/dhcp-server/lease/print")

    async def add_dhcp_static_lease(self, mac: str, ip: str, comment: str = "") -> str:
        params = {"mac-address": mac, "address": ip, "type": "static"}
        if comment:
            params["comment"] = comment
        r = await self._client.command("/ip/dhcp-server/lease/add", params)
        return r[0].get("ret", "") if r else ""

    async def remove_dhcp_lease(self, id_: str):
        await self._client.command("/ip/dhcp-server/lease/remove", {"numbers": id_})

    async def make_dhcp_lease_static(self, id_: str):
        await self._client.command("/ip/dhcp-server/lease/make-static", {"numbers": id_})

    # ─── Wireless ─────────────────────────────────────────────────────────────

    async def get_wireless_interfaces(self) -> list[dict]:
        try:
            return await self._client.command("/interface/wireless/print")
        except APIError:
            return []

    async def get_wireless_registrations(self) -> list[dict]:
        try:
            return await self._client.command("/interface/wireless/registration-table/print")
        except APIError:
            return []

    async def get_wireless_security_profiles(self) -> list[dict]:
        try:
            return await self._client.command("/interface/wireless/security-profiles/print")
        except APIError:
            return []

    async def set_wireless_ssid(self, interface: str, ssid: str):
        await self._client.command("/interface/wireless/set", {
            "numbers": interface, "ssid": ssid,
        })

    async def set_wireless_password(self, interface: str, password: str):
        # Get security profile for this interface first
        ifaces = await self.get_wireless_interfaces()
        profile_name = "default"
        for i in ifaces:
            if i.get("name") == interface:
                profile_name = i.get("security-profile", "default")
                break
        await self._client.command("/interface/wireless/security-profiles/set", {
            "numbers": profile_name,
            "wpa2-pre-shared-key": password,
            "wpa-pre-shared-key": password,
        })

    async def enable_wireless(self, interface: str):
        await self._client.command("/interface/wireless/enable", {"numbers": interface})

    async def disable_wireless(self, interface: str):
        await self._client.command("/interface/wireless/disable", {"numbers": interface})

    async def disconnect_wireless_client(self, mac: str):
        await self._client.command("/interface/wireless/deauthenticate", {"mac-address": mac})

    async def get_wireless_scan(self, interface: str) -> list[dict]:
        try:
            return await self._client.command(
                "/interface/wireless/scan",
                {"numbers": interface, "duration": "5"},
            )
        except APIError:
            return []

    # ─── VPN ──────────────────────────────────────────────────────────────────

    async def get_pppoe_server(self) -> list[dict]:
        try:
            return await self._client.command("/interface/pppoe-server/server/print")
        except APIError:
            return []

    async def get_pppoe_active(self) -> list[dict]:
        try:
            return await self._client.command("/interface/pppoe-server/active/print")
        except APIError:
            return []

    async def get_l2tp_server(self) -> dict:
        try:
            r = await self._client.command_one("/interface/l2tp-server/server/print")
            return r or {}
        except APIError:
            return {}

    async def get_ovpn_server(self) -> dict:
        try:
            r = await self._client.command_one("/interface/ovpn-server/server/print")
            return r or {}
        except APIError:
            return {}

    async def get_pptp_server(self) -> dict:
        try:
            r = await self._client.command_one("/interface/pptp-server/server/print")
            return r or {}
        except APIError:
            return {}

    async def get_vpn_secrets(self) -> list[dict]:
        return await self._client.command("/ppp/secret/print")

    async def add_vpn_secret(self, name: str, password: str, service: str = "any", profile: str = "default") -> str:
        r = await self._client.command("/ppp/secret/add", {
            "name": name, "password": password,
            "service": service, "profile": profile,
        })
        return r[0].get("ret", "") if r else ""

    async def remove_vpn_secret(self, id_: str):
        await self._client.command("/ppp/secret/remove", {"numbers": id_})

    # ─── File System ──────────────────────────────────────────────────────────

    async def get_files(self) -> list[dict]:
        return await self._client.command("/file/print")

    async def delete_file(self, name: str):
        await self._client.command("/file/remove", {"numbers": name})

    async def get_backup_file(self, name: str) -> bytes:
        """
        Download file via RouterOS API /tool/fetch is not directly supported for downloads.
        This is a placeholder – real implementation requires FTP or direct API trick.
        """
        raise NotImplementedError("File download requires FTP connection to router")

    async def create_backup(self, name: str = "", password: str = "") -> str:
        params: dict = {}
        if name:
            params["name"] = name
        if password:
            params["password"] = password
        await self._client.command("/system/backup/save", params)
        # Find the created file
        files = await self.get_files()
        backup_files = [f for f in files if f.get("name", "").endswith(".backup")]
        if backup_files:
            return backup_files[-1].get("name", "backup.backup")
        return name + ".backup" if name else "backup.backup"

    async def export_config(self) -> str:
        results = await self._client.command("/export")
        return "\n".join(r.get("ret", "") for r in results if r)

    # ─── Logs ─────────────────────────────────────────────────────────────────

    async def get_logs(self, limit: int = 50, topics: str = "") -> list[dict]:
        queries = []
        if topics:
            queries = [f"?topics={topics}"]
        results = await self._client.command("/log/print", queries=queries)
        return results[-limit:]

    async def stream_logs(self, topics: str = "") -> AsyncIterator[dict]:
        params: dict = {"follow": ""}
        if topics:
            params["topics"] = topics
        async for row in self._client.stream("/log/print", params):
            yield row

    # ─── Routing ──────────────────────────────────────────────────────────────

    async def get_routes(self) -> list[dict]:
        return await self._client.command("/ip/route/print")

    async def add_route(self, dst_address: str, gateway: str, distance: int = 1) -> str:
        r = await self._client.command("/ip/route/add", {
            "dst-address": dst_address, "gateway": gateway,
            "distance": str(distance),
        })
        return r[0].get("ret", "") if r else ""

    async def remove_route(self, id_: str):
        await self._client.command("/ip/route/remove", {"numbers": id_})

    # ─── ARP ──────────────────────────────────────────────────────────────────

    async def get_arp(self) -> list[dict]:
        return await self._client.command("/ip/arp/print")

    # ─── DNS ──────────────────────────────────────────────────────────────────

    async def get_dns_settings(self) -> dict:
        r = await self._client.command_one("/ip/dns/print")
        return r or {}

    async def set_dns_servers(self, servers: list[str]):
        await self._client.command("/ip/dns/set", {"servers": ",".join(servers)})

    async def get_dns_cache(self) -> list[dict]:
        return await self._client.command("/ip/dns/cache/print")

    async def flush_dns_cache(self):
        await self._client.command("/ip/dns/cache/flush")

    # ─── NTP ──────────────────────────────────────────────────────────────────

    async def get_ntp_client(self) -> dict:
        r = await self._client.command_one("/system/ntp/client/print")
        return r or {}

    async def set_ntp_servers(self, primary: str, secondary: str = ""):
        params: dict = {"enabled": "yes", "primary-ntp": primary}
        if secondary:
            params["secondary-ntp"] = secondary
        await self._client.command("/system/ntp/client/set", params)

    # ─── Users ────────────────────────────────────────────────────────────────

    async def get_users(self) -> list[dict]:
        return await self._client.command("/user/print")

    async def add_user(self, name: str, password: str, group: str = "read") -> str:
        r = await self._client.command("/user/add", {
            "name": name, "password": password, "group": group,
        })
        return r[0].get("ret", "") if r else ""

    async def remove_user(self, id_: str):
        await self._client.command("/user/remove", {"numbers": id_})

    # ─── Tools ────────────────────────────────────────────────────────────────

    async def ping(self, address: str, count: int = 4) -> list[dict]:
        return await self._client.command("/ping", {
            "address": address, "count": str(count),
        })

    async def traceroute(self, address: str) -> list[dict]:
        return await self._client.command("/tool/traceroute", {
            "address": address, "count": "3",
        })

    async def bandwidth_test(self, address: str, duration: int = 5) -> dict:
        r = await self._client.command_one("/tool/bandwidth-test", {
            "address": address, "duration": str(duration),
        })
        return r or {}

    # ─── IP Pools ─────────────────────────────────────────────────────────────

    async def get_ip_pools(self) -> list[dict]:
        return await self._client.command("/ip/pool/print")

    async def add_ip_pool(self, name: str, ranges: str) -> str:
        r = await self._client.command("/ip/pool/add", {"name": name, "ranges": ranges})
        return r[0].get("ret", "") if r else ""

    async def remove_ip_pool(self, id_: str):
        await self._client.command("/ip/pool/remove", {"numbers": id_})

    # ─── Queues / QoS ─────────────────────────────────────────────────────────

    async def get_simple_queues(self) -> list[dict]:
        return await self._client.command("/queue/simple/print")

    async def add_simple_queue(self, name: str, target: str, max_limit: str = "0/0", comment: str = "") -> str:
        params = {"name": name, "target": target, "max-limit": max_limit}
        if comment:
            params["comment"] = comment
        r = await self._client.command("/queue/simple/add", params)
        return r[0].get("ret", "") if r else ""

    async def remove_simple_queue(self, id_: str):
        await self._client.command("/queue/simple/remove", {"numbers": id_})

    async def enable_simple_queue(self, id_: str):
        await self._client.command("/queue/simple/enable", {"numbers": id_})

    async def disable_simple_queue(self, id_: str):
        await self._client.command("/queue/simple/disable", {"numbers": id_})

    # ─── Hotspot ──────────────────────────────────────────────────────────────

    async def get_hotspot_users(self) -> list[dict]:
        try:
            return await self._client.command("/ip/hotspot/user/print")
        except APIError:
            return []

    async def get_hotspot_active(self) -> list[dict]:
        try:
            return await self._client.command("/ip/hotspot/active/print")
        except APIError:
            return []

    async def add_hotspot_user(self, name: str, password: str, profile: str = "default", comment: str = "") -> str:
        params = {"name": name, "password": password, "profile": profile}
        if comment:
            params["comment"] = comment
        try:
            r = await self._client.command("/ip/hotspot/user/add", params)
            return r[0].get("ret", "") if r else ""
        except APIError as e:
            raise e

    async def remove_hotspot_user(self, id_: str):
        await self._client.command("/ip/hotspot/user/remove", {"numbers": id_})

    async def disconnect_hotspot_user(self, id_: str):
        try:
            await self._client.command("/ip/hotspot/active/remove", {"numbers": id_})
        except APIError:
            pass

    # ─── Scripts ──────────────────────────────────────────────────────────────

    async def get_scripts(self) -> list[dict]:
        try:
            return await self._client.command("/system/script/print")
        except APIError:
            return []

    async def run_script(self, name: str) -> str:
        try:
            await self._client.command("/system/script/run", {"number": name})
            return "ok"
        except APIError as e:
            raise e

    async def add_script(self, name: str, source: str, comment: str = "") -> str:
        params = {"name": name, "source": source}
        if comment:
            params["comment"] = comment
        r = await self._client.command("/system/script/add", params)
        return r[0].get("ret", "") if r else ""

    # ─── Certificates ─────────────────────────────────────────────────────────

    async def get_certificates(self) -> list[dict]:
        try:
            return await self._client.command("/certificate/print")
        except APIError:
            return []

    # ─── Bridges ──────────────────────────────────────────────────────────────

    async def get_bridges(self) -> list[dict]:
        try:
            return await self._client.command("/interface/bridge/print")
        except APIError:
            return []

    async def get_bridge_ports(self) -> list[dict]:
        try:
            return await self._client.command("/interface/bridge/port/print")
        except APIError:
            return []

    async def add_bridge_port(self, bridge: str, interface: str) -> str:
        r = await self._client.command("/interface/bridge/port/add", {
            "bridge": bridge, "interface": interface,
        })
        return r[0].get("ret", "") if r else ""

    async def remove_bridge_port(self, id_: str):
        await self._client.command("/interface/bridge/port/remove", {"numbers": id_})

    # ─── VLANs ────────────────────────────────────────────────────────────────

    async def get_vlans(self) -> list[dict]:
        try:
            return await self._client.command("/interface/vlan/print")
        except APIError:
            return []

    async def add_vlan(self, name: str, vlan_id: int, interface: str) -> str:
        r = await self._client.command("/interface/vlan/add", {
            "name": name, "vlan-id": str(vlan_id), "interface": interface,
        })
        return r[0].get("ret", "") if r else ""

    async def remove_vlan(self, id_: str):
        await self._client.command("/interface/vlan/remove", {"numbers": id_})

    # ─── NAT Extended ─────────────────────────────────────────────────────────

    async def remove_firewall_nat(self, id_: str):
        await self._client.command("/ip/firewall/nat/remove", {"numbers": id_})

    async def add_firewall_mangle(self, params: dict) -> str:
        r = await self._client.command("/ip/firewall/mangle/add", params)
        return r[0].get("ret", "") if r else ""

    async def remove_firewall_mangle(self, id_: str):
        await self._client.command("/ip/firewall/mangle/remove", {"numbers": id_})

    # ─── PPP Profiles ─────────────────────────────────────────────────────────

    async def get_ppp_profiles(self) -> list[dict]:
        try:
            return await self._client.command("/ppp/profile/print")
        except APIError:
            return []

    # ─── Interface Ethernet Stats ──────────────────────────────────────────────

    async def get_interface_ethernet_stats(self) -> list[dict]:
        try:
            return await self._client.command("/interface/ethernet/print")
        except APIError:
            return []
