"""
RouterOS 7 implementation.

Supports two modes:
  NSA (Not Standalone): Bot runs on external PC, connects to router via API port 8728/8729.
  SA  (Standalone):     Bot runs inside a ROS7 Docker container on the router itself.
                        In SA mode, the host is typically 172.17.0.1 (Docker gateway)
                        and credentials come from environment variables.

ROS7 additions over ROS6:
  - WireGuard VPN
  - Docker container management
  - IPv6 full support
  - REST API (port 80/443) – we still use binary API for consistency
  - New /routing/ path structure (vs /ip/route/ for static)
  - BGP, OSPF under /routing/
"""

import asyncio
import logging
import os
from typing import AsyncIterator

from .router_ros6 import RouterROS6
from .router_client import APIError

log = logging.getLogger("ROS7")


class RouterROS7(RouterROS6):
    """
    RouterOS 7. Inherits ROS6 and overrides/adds ROS7-specific paths.
    """

    def __init__(
        self,
        host: str | None = None,
        username: str | None = None,
        password: str | None = None,
        port: int = 8728,
        use_ssl: bool = False,
        standalone: bool = False,
    ):
        """
        standalone=True: running inside router Docker container.
        In that case, credentials can come from environment variables:
          MIKROTIK_HOST, MIKROTIK_USER, MIKROTIK_PASS
        and host defaults to 172.17.0.1 (Docker bridge gateway).
        """
        self.standalone = standalone

        if standalone:
            host = host or os.environ.get("MIKROTIK_HOST", "172.17.0.1")
            username = username or os.environ.get("MIKROTIK_USER", "admin")
            password = password or os.environ.get("MIKROTIK_PASS", "")

        super().__init__(
            host=host or "192.168.88.1",
            username=username or "admin",
            password=password or "",
            port=port,
            use_ssl=use_ssl,
        )
        # Override client ros_version
        self._client.ros_version = 7

    # ─── System (ROS7 overrides) ──────────────────────────────────────────────

    async def get_system_health(self) -> dict:
        """ROS7 uses /system/health/print differently on some boards."""
        try:
            results = await self._client.command("/system/health/print")
            if results:
                # ROS7 returns list of {name, value, type}
                if isinstance(results[0], dict) and "name" in results[0]:
                    return {r["name"]: r.get("value", "") for r in results}
                return results[0]
        except APIError:
            pass
        return {}

    # ─── Routing (ROS7 uses /ip/route for static, /routing/ for dynamic) ──────

    async def get_routes(self) -> list[dict]:
        """ROS7: /ip/route/print still works for IPv4 static routes."""
        routes = await self._client.command("/ip/route/print")
        # Also get IPv6 routes
        try:
            ipv6 = await self._client.command("/ipv6/route/print")
            for r in ipv6:
                r["_ipv6"] = True
            routes.extend(ipv6)
        except APIError:
            pass
        return routes

    # ─── WireGuard (ROS7 only) ────────────────────────────────────────────────

    async def get_wireguard_interfaces(self) -> list[dict]:
        try:
            return await self._client.command("/interface/wireguard/print")
        except APIError:
            return []

    async def get_wireguard_peers(self) -> list[dict]:
        try:
            return await self._client.command("/interface/wireguard/peers/print")
        except APIError:
            return []

    async def add_wireguard_interface(self, name: str, listen_port: int = 13231) -> str:
        try:
            r = await self._client.command("/interface/wireguard/add", {
                "name": name,
                "listen-port": str(listen_port),
            })
            return r[0].get("ret", "") if r else ""
        except APIError as e:
            raise e

    async def add_wireguard_peer(
        self,
        interface: str,
        public_key: str,
        allowed_address: str,
        endpoint: str = "",
        endpoint_port: int = 0,
        keepalive: int = 25,
    ) -> str:
        params = {
            "interface": interface,
            "public-key": public_key,
            "allowed-address": allowed_address,
        }
        if endpoint:
            params["endpoint-address"] = endpoint
        if endpoint_port:
            params["endpoint-port"] = str(endpoint_port)
        if keepalive:
            params["persistent-keepalive"] = str(keepalive)
        try:
            r = await self._client.command("/interface/wireguard/peers/add", params)
            return r[0].get("ret", "") if r else ""
        except APIError as e:
            raise e

    async def remove_wireguard_peer(self, id_: str):
        await self._client.command("/interface/wireguard/peers/remove", {"numbers": id_})

    # ─── ROS7 Scripts (uses /system/script same path, but supports more features) ─

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

    # ─── ROS7 Routing (BGP/OSPF) ─────────────────────────────────────────────

    async def get_bgp_peers(self) -> list[dict]:
        try:
            return await self._client.command("/routing/bgp/peer/print")
        except APIError:
            try:
                return await self._client.command("/routing/bgp/connection/print")
            except APIError:
                return []

    async def get_ospf_instances(self) -> list[dict]:
        try:
            return await self._client.command("/routing/ospf/instance/print")
        except APIError:
            return []

    # ─── ROS7 IPv6 ───────────────────────────────────────────────────────────

    async def get_ipv6_addresses(self) -> list[dict]:
        try:
            return await self._client.command("/ipv6/address/print")
        except APIError:
            return []

    async def get_ipv6_neighbors(self) -> list[dict]:
        try:
            return await self._client.command("/ipv6/neighbor/print")
        except APIError:
            return []

    # ─── Docker Containers (ROS7 SA/NSA) ─────────────────────────────────────

    async def get_container_list(self) -> list[dict]:
        try:
            return await self._client.command("/container/print")
        except APIError:
            return []

    async def start_container(self, id_: str):
        try:
            await self._client.command("/container/start", {"numbers": id_})
        except APIError as e:
            raise e

    async def stop_container(self, id_: str):
        try:
            await self._client.command("/container/stop", {"numbers": id_})
        except APIError as e:
            raise e

    async def remove_container(self, id_: str):
        try:
            await self._client.command("/container/remove", {"numbers": id_})
        except APIError as e:
            raise e

    async def get_container_envs(self, id_: str) -> list[dict]:
        try:
            return await self._client.command("/container/envs/print", {"numbers": id_})
        except APIError:
            return []

    async def get_container_mounts(self) -> list[dict]:
        try:
            return await self._client.command("/container/mounts/print")
        except APIError:
            return []

    # ─── IPv6 ─────────────────────────────────────────────────────────────────

    async def get_ipv6_addresses(self) -> list[dict]:
        try:
            return await self._client.command("/ipv6/address/print")
        except APIError:
            return []

    async def get_ipv6_firewall_filter(self) -> list[dict]:
        try:
            return await self._client.command("/ipv6/firewall/filter/print")
        except APIError:
            return []

    async def get_ipv6_neighbors(self) -> list[dict]:
        """IPv6 neighbor discovery table (equivalent of ARP for IPv6)."""
        try:
            return await self._client.command("/ipv6/neighbor/print")
        except APIError:
            return []

    # ─── BGP / OSPF (ROS7 routing) ───────────────────────────────────────────

    async def get_bgp_connections(self) -> list[dict]:
        try:
            return await self._client.command("/routing/bgp/connection/print")
        except APIError:
            return []

    async def get_ospf_instances(self) -> list[dict]:
        try:
            return await self._client.command("/routing/ospf/instance/print")
        except APIError:
            return []

    # ─── Certificate Manager ─────────────────────────────────────────────────

    async def get_certificates(self) -> list[dict]:
        try:
            return await self._client.command("/certificate/print")
        except APIError:
            return []

    async def generate_self_signed_cert(self, common_name: str, days: int = 3650) -> str:
        """
        Generate and sign a self-signed certificate.
        Returns the certificate name.
        """
        name = common_name.replace(" ", "_")
        # Add cert template
        await self._client.command("/certificate/add", {
            "name": name,
            "common-name": common_name,
            "days-valid": str(days),
            "key-size": "2048",
            "key-usage": "digital-signature,key-encipherment,tls-server,tls-client",
        })
        # Sign it
        await self._client.command("/certificate/sign", {"numbers": name, "ca-crl-host": ""})
        return name

    # ─── VLAN (ROS7 bridge VLAN filtering) ───────────────────────────────────

    async def get_bridge_vlans(self) -> list[dict]:
        try:
            return await self._client.command("/interface/bridge/vlan/print")
        except APIError:
            return []

    async def get_bridge_ports(self) -> list[dict]:
        try:
            return await self._client.command("/interface/bridge/port/print")
        except APIError:
            return []

    # ─── Scheduler / Scripts ─────────────────────────────────────────────────

    async def get_scheduler_entries(self) -> list[dict]:
        return await self._client.command("/system/scheduler/print")

    async def get_scripts(self) -> list[dict]:
        return await self._client.command("/system/script/print")

    async def run_script(self, name: str):
        await self._client.command("/system/script/run", {"number": name})

    # ─── WiFi (wifi-qcom / wifiwave2 — ROS7 new wireless package) ────────────

    async def get_wireless_interfaces(self) -> list[dict]:
        """
        ROS7 supports two wireless stacks:
          - Legacy: /interface/wireless  (wifi-qcom-ac, older chips)
          - New:    /interface/wifi      (wifi-qcom, hAP ax2/ax3, newer chips)
        Try new stack first, fall back to legacy.
        """
        try:
            result = await self._client.command("/interface/wifi/print")
            if result:
                # Normalize field names to match legacy format expected by formatters
                normalized = []
                for r in result:
                    r.setdefault("ssid", r.get("configuration.ssid", r.get("name", "?")))
                    r.setdefault("frequency", r.get("radio-frequency", "?"))
                    r.setdefault("band", r.get("radio-mac", ""))
                    normalized.append(r)
                return normalized
        except Exception:
            pass
        # Fall back to legacy wireless
        try:
            return await self._client.command("/interface/wireless/print")
        except Exception:
            return []

    async def get_wireless_registrations(self) -> list[dict]:
        """Connected clients — try new wifi stack first, then legacy."""
        try:
            result = await self._client.command("/interface/wifi/registration-table/print")
            if result:
                return result
        except Exception:
            pass
        try:
            return await self._client.command("/interface/wireless/registration-table/print")
        except Exception:
            return []
