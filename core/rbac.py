"""
Role-Based Access Control (RBAC) for MikroBot.

Roles (highest to lowest):
  owner    – full access, can manage bot users, add/remove routers
  admin    – full router control, cannot manage bot users
  operator – can view and make limited changes (no firewall/user changes)
  viewer   – read-only access

CHANGES vs original:
  - _load() / _save() now use asyncio.to_thread() to avoid blocking the event loop
  - Added async_save() / async_load() public async variants
  - Synchronous _load() is kept only for __init__ (before the event loop starts)
"""

import asyncio
import json
import logging
from enum import IntEnum
from pathlib import Path
from typing import Optional
from functools import wraps

from aiogram.types import Message, CallbackQuery

log = logging.getLogger("RBAC")

RBAC_FILE = Path("data/rbac.json")


class Role(IntEnum):
    VIEWER = 1
    OPERATOR = 2
    ADMIN = 3
    OWNER = 4

    @classmethod
    def from_str(cls, s: str) -> "Role":
        return {
            "viewer": cls.VIEWER,
            "operator": cls.OPERATOR,
            "admin": cls.ADMIN,
            "owner": cls.OWNER,
        }.get(s.lower(), cls.VIEWER)

    def to_str(self) -> str:
        return self.name.lower()

    def emoji(self) -> str:
        return {
            Role.VIEWER: "👁",
            Role.OPERATOR: "⚙️",
            Role.ADMIN: "🔑",
            Role.OWNER: "👑",
        }[self]


# ─── Permission Map ───────────────────────────────────────────────────────────

PERMISSIONS: dict[str, Role] = {
    # System
    "system.view": Role.VIEWER,
    "system.reboot": Role.ADMIN,
    "system.export": Role.ADMIN,
    "system.backup": Role.ADMIN,
    "system.backup.restore": Role.OWNER,

    # Interfaces
    "interface.view": Role.VIEWER,
    "interface.toggle": Role.OPERATOR,
    "interface.monitor": Role.VIEWER,

    # IP / Routes
    "ip.view": Role.VIEWER,
    "ip.manage": Role.ADMIN,
    "route.view": Role.VIEWER,
    "route.manage": Role.ADMIN,

    # Firewall
    "firewall.view": Role.OPERATOR,
    "firewall.manage": Role.ADMIN,
    "firewall.nat.view": Role.OPERATOR,
    "firewall.nat.manage": Role.ADMIN,
    "firewall.address_list.view": Role.OPERATOR,
    "firewall.address_list.manage": Role.OPERATOR,

    # DHCP
    "dhcp.view": Role.VIEWER,
    "dhcp.manage": Role.OPERATOR,

    # Wireless
    "wireless.view": Role.VIEWER,
    "wireless.manage": Role.OPERATOR,
    "wireless.disconnect_client": Role.OPERATOR,

    # VPN
    "vpn.view": Role.OPERATOR,
    "vpn.manage": Role.ADMIN,

    # Files
    "file.view": Role.OPERATOR,
    "file.download": Role.ADMIN,
    "file.delete": Role.ADMIN,

    # Logs
    "log.view": Role.VIEWER,
    "log.stream": Role.OPERATOR,

    # Tools
    "tool.ping": Role.VIEWER,
    "tool.traceroute": Role.OPERATOR,
    "tool.bandwidth_test": Role.OPERATOR,

    # Router management (bot-level)
    "router.add": Role.OWNER,
    "router.remove": Role.OWNER,
    "router.switch": Role.ADMIN,

    # Bot user management
    "user.view": Role.ADMIN,
    "user.add": Role.OWNER,
    "user.remove": Role.OWNER,
    "user.role.change": Role.OWNER,

    # DNS
    "dns.view": Role.VIEWER,
    "dns.manage": Role.ADMIN,
}


class RBACManager:

    def __init__(self):
        self._roles: dict[int, Role] = {}
        self._owner_id: Optional[int] = None
        self._write_lock = asyncio.Lock()
        # Synchronous load only during __init__ (before event loop is running)
        self._load_sync()

    # ─── Persistence ──────────────────────────────────────────────────────────

    def _load_sync(self) -> None:
        """Synchronous load — only safe to call before the event loop starts."""
        if not RBAC_FILE.exists():
            return
        try:
            data = json.loads(RBAC_FILE.read_text())
            self._owner_id = data.get("owner_id")
            for uid_str, role_str in data.get("roles", {}).items():
                self._roles[int(uid_str)] = Role.from_str(role_str)
        except Exception as e:
            log.warning(f"Failed to load RBAC: {e}")

    def _build_payload(self) -> dict:
        return {
            "owner_id": self._owner_id,
            "roles": {str(uid): role.to_str() for uid, role in self._roles.items()},
        }

    def _write_sync(self) -> None:
        """Actual file write — called via asyncio.to_thread to stay off the event loop."""
        RBAC_FILE.parent.mkdir(parents=True, exist_ok=True)
        RBAC_FILE.write_text(json.dumps(self._build_payload(), indent=2))

    async def _save(self) -> None:
        """Non-blocking async save — offloads disk write to a thread pool."""
        async with self._write_lock:
            payload = self._build_payload()
            await asyncio.to_thread(
                lambda: (
                    RBAC_FILE.parent.mkdir(parents=True, exist_ok=True),
                    RBAC_FILE.write_text(json.dumps(payload, indent=2)),
                )
            )

    # ─── Bootstrap ────────────────────────────────────────────────────────────

    async def bootstrap_owner(self, user_id: int) -> bool:
        """Set the first owner. Returns False if an owner already exists."""
        if self._owner_id is not None:
            return False
        self._owner_id = user_id
        self._roles[user_id] = Role.OWNER
        await self._save()
        return True

    def is_bootstrapped(self) -> bool:
        return self._owner_id is not None

    # ─── Role Management ──────────────────────────────────────────────────────

    async def set_role(self, user_id: int, role: Role) -> None:
        self._roles[user_id] = role
        await self._save()

    async def remove_user(self, user_id: int) -> None:
        self._roles.pop(user_id, None)
        await self._save()

    def get_role(self, user_id: int) -> Optional[Role]:
        return self._roles.get(user_id)

    def get_all_users(self) -> list[dict]:
        return [
            {"user_id": uid, "role": role.to_str(), "is_owner": uid == self._owner_id}
            for uid, role in self._roles.items()
        ]

    def is_known(self, user_id: int) -> bool:
        return user_id in self._roles

    # ─── Permission Checking ──────────────────────────────────────────────────

    def can(self, user_id: int, permission: str) -> bool:
        role = self._roles.get(user_id)
        if role is None:
            return False
        required = PERMISSIONS.get(permission, Role.OWNER)
        return role >= required

    def require(self, user_id: int, permission: str) -> bool:
        """Raises PermissionError with a descriptive message if access is denied."""
        if not self.can(user_id, permission):
            role = self._roles.get(user_id)
            role_str = role.to_str() if role else "unknown"
            required = PERMISSIONS.get(permission, Role.OWNER)
            raise PermissionError(
                f"🚫 Access denied.\n"
                f"Your role: `{role_str}` | Required: `{required.to_str()}`"
            )
        return True


# ─── Decorator for handlers ───────────────────────────────────────────────────

def require_permission(permission: str):
    """
    Decorator for aiogram handlers.
    Usage: @require_permission("firewall.manage")
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            rbac: Optional[RBACManager] = None
            user_id: Optional[int] = None
            msg_or_cb = None

            for arg in args:
                if isinstance(arg, (Message, CallbackQuery)):
                    msg_or_cb = arg
                    user_id = arg.from_user.id
                    break

            if msg_or_cb is None:
                for v in kwargs.values():
                    if isinstance(v, (Message, CallbackQuery)):
                        msg_or_cb = v
                        user_id = v.from_user.id
                        break

            rbac = kwargs.get("rbac")

            if rbac and user_id:
                if not rbac.is_known(user_id):
                    if isinstance(msg_or_cb, Message):
                        await msg_or_cb.answer("🚫 You are not authorized. Contact the bot owner.")
                    elif isinstance(msg_or_cb, CallbackQuery):
                        await msg_or_cb.answer("🚫 Not authorized.", show_alert=True)
                    return
                try:
                    rbac.require(user_id, permission)
                except PermissionError as e:
                    if isinstance(msg_or_cb, Message):
                        await msg_or_cb.answer(str(e), parse_mode="Markdown")
                    elif isinstance(msg_or_cb, CallbackQuery):
                        await msg_or_cb.answer(str(e), show_alert=True)
                    return

            return await func(*args, **kwargs)
        return wrapper
    return decorator
