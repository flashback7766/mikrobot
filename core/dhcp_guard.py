"""
DHCP Guard — DHCP starvation (dhcpig & co.) detection + firewall mitigation.

Two-layer defence:
  1. Bot-side detector (always, when enabled per-router):
     - Sliding-window velocity check over the DHCP lease table
     - Alerts via Telegram when new-lease rate crosses the threshold
     - Optional auto-mitigation: purge offending dynamic leases
  2. Firewall rate-limit rules on the router (opt-in):
     - Rate-limits DHCP (UDP/67) in the input chain
     - All rules tagged with comment="mikrobot-dhcp-guard" for idempotent
       apply/remove, survives reboots, safe to re-run.

Safety:
  - apply_firewall_protection() first removes old guard-tagged rules, then
    adds fresh ones — so re-apply is always clean.
  - Rules are moved to the top of the input chain so they're evaluated first.
  - We never touch rules without the guard tag — user's own rules untouched.
"""

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("DhcpGuard")

GUARD_TAG = "mikrobot-dhcp-guard"
SETTINGS_FILE = Path("data/dhcp_guard.json")


# ─── Settings persistence ─────────────────────────────────────────────────────

@dataclass
class GuardSettings:
    """Per-(user_id, alias) guard settings. Persisted to JSON."""
    enabled: bool = False             # Detector running?
    firewall_applied: bool = False    # Firewall rules installed?

    # Detection thresholds
    window_seconds: int = 60          # Sliding window size
    new_lease_threshold: int = 20     # Max new MACs per window
    total_lease_cap: int = 0          # 0 = disabled; alert if total > cap

    # Firewall rate-limit (packets/sec, burst)
    fw_rate_limit: int = 50
    fw_burst: int = 100

    # Auto-mitigation (aggressive, opt-in)
    auto_purge_flooders: bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "GuardSettings":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


class GuardSettingsStore:
    """JSON-backed per-router settings store. Async save, sync load-at-init."""

    def __init__(self):
        self._data: dict[str, GuardSettings] = {}
        self._lock = asyncio.Lock()
        self._load_sync()

    @staticmethod
    def _key(user_id: int, alias: str) -> str:
        return f"{user_id}:{alias}"

    def _load_sync(self) -> None:
        if not SETTINGS_FILE.exists():
            return
        try:
            raw = json.loads(SETTINGS_FILE.read_text())
            self._data = {k: GuardSettings.from_dict(v) for k, v in raw.items()}
        except Exception as e:
            log.warning(f"Failed to load dhcp_guard settings: {e}")

    async def _save(self) -> None:
        async with self._lock:
            payload = {k: v.to_dict() for k, v in self._data.items()}
            await asyncio.to_thread(
                lambda: (
                    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True),
                    SETTINGS_FILE.write_text(json.dumps(payload, indent=2)),
                )
            )

    def get(self, user_id: int, alias: str) -> GuardSettings:
        return self._data.setdefault(self._key(user_id, alias), GuardSettings())

    async def update(self, user_id: int, alias: str, **kwargs) -> GuardSettings:
        s = self.get(user_id, alias)
        for k, v in kwargs.items():
            if hasattr(s, k):
                setattr(s, k, v)
        await self._save()
        return s

    async def remove(self, user_id: int, alias: str) -> None:
        self._data.pop(self._key(user_id, alias), None)
        await self._save()


# ─── Attack Detector ──────────────────────────────────────────────────────────

@dataclass
class DetectorState:
    """Per-router detection state (in-memory)."""
    last_macs: set[str] = field(default_factory=set)
    # deque of (timestamp, mac) for every new MAC seen within the window
    recent_new_macs: deque = field(default_factory=deque)
    is_attacking: bool = False
    alert_cooldown_until: float = 0.0
    first_seen: bool = False  # skip first poll (don't alert on baseline)


@dataclass
class AttackReport:
    """Structured attack info."""
    new_mac_count: int
    window_seconds: int
    total_leases: int
    sample_macs: list[str]
    started_at: float = field(default_factory=time.time)

    def format_alert(self, alias: str, host: str) -> str:
        shown = self.sample_macs[:5]
        macs = "\n".join(f"  `{m}`" for m in shown) or "  _(none captured)_"
        extra = (
            f"\n  … and {self.new_mac_count - len(shown)} more"
            if self.new_mac_count > len(shown) else ""
        )
        return (
            f"🚨 *DHCP STARVATION ATTACK*\n\n"
            f"Router: *{alias}* (`{host}`)\n"
            f"New leases: *{self.new_mac_count}* in {self.window_seconds}s\n"
            f"Total leases now: *{self.total_leases}*\n\n"
            f"Sample MACs:\n{macs}{extra}"
        )


class DhcpAttackDetector:
    """
    Per-router sliding-window detector.
    Feed lease snapshots via update(); returns AttackReport on detection.
    """

    COOLDOWN_SECONDS = 300  # Min seconds between repeated alerts per router

    def __init__(self):
        self._states: dict[tuple[int, str], DetectorState] = {}

    def reset(self, user_id: int, alias: str) -> None:
        self._states.pop((user_id, alias), None)

    def is_attacking(self, user_id: int, alias: str) -> bool:
        st = self._states.get((user_id, alias))
        return bool(st and st.is_attacking)

    def update(
        self,
        user_id: int,
        alias: str,
        leases: list[dict],
        settings: GuardSettings,
    ) -> Optional[AttackReport]:
        if not settings.enabled:
            return None

        key = (user_id, alias)
        st = self._states.setdefault(key, DetectorState())
        now = time.time()

        macs = {
            l.get("mac-address", "")
            for l in leases
            if l.get("mac-address")
        }

        # Skip first poll: initial MAC set isn't "new", just baseline
        if not st.first_seen:
            st.first_seen = True
            st.last_macs = macs
            return None

        new_this_poll = macs - st.last_macs
        for mac in new_this_poll:
            st.recent_new_macs.append((now, mac))
        st.last_macs = macs

        # Trim old entries from the window
        cutoff = now - settings.window_seconds
        while st.recent_new_macs and st.recent_new_macs[0][0] < cutoff:
            st.recent_new_macs.popleft()

        new_in_window = len(st.recent_new_macs)

        triggered = False
        if new_in_window >= settings.new_lease_threshold:
            triggered = True
        if settings.total_lease_cap > 0 and len(leases) >= settings.total_lease_cap:
            triggered = True

        if triggered:
            # De-dup alerts within cooldown window
            if now < st.alert_cooldown_until:
                return None
            st.alert_cooldown_until = now + self.COOLDOWN_SECONDS
            st.is_attacking = True
            sample_macs = [m for _, m in list(st.recent_new_macs)[-20:]]
            return AttackReport(
                new_mac_count=new_in_window,
                window_seconds=settings.window_seconds,
                total_leases=len(leases),
                sample_macs=sample_macs,
            )

        # Clear attack state when window is quiet again
        if st.is_attacking and not st.recent_new_macs:
            st.is_attacking = False

        return None


# ─── Firewall Protection ──────────────────────────────────────────────────────

async def is_firewall_applied(router) -> bool:
    """Check if guard-tagged firewall rules exist on the router."""
    try:
        rules = await router.get_firewall_filter()
    except Exception:
        return False
    return any(GUARD_TAG in (r.get("comment") or "") for r in rules)


async def apply_firewall_protection(
    router,
    settings: GuardSettings,
) -> tuple[bool, str]:
    """
    Install DHCP guard firewall rules. Idempotent: removes old guard rules
    first, then adds fresh ones. Returns (success, message).

    Rules installed (all tagged with GUARD_TAG in comment):
      1. input chain, UDP/67, limit=rate,burst:packet, action=accept
      2. input chain, UDP/67, action=drop   (catches overflow)
    """
    # Clean slate
    try:
        await remove_firewall_protection(router)
    except Exception as e:
        log.debug(f"pre-apply cleanup failed (non-fatal): {e}")

    try:
        rate = max(1, int(settings.fw_rate_limit))
        burst = max(rate, int(settings.fw_burst))

        # Accept rule (within limit)
        await router.add_firewall_filter({
            "chain": "input",
            "protocol": "udp",
            "dst-port": "67",
            "limit": f"{rate},{burst}:packet",
            "action": "accept",
            "comment": f"{GUARD_TAG}: DHCP rate-limit accept",
        })

        # Drop rule (excess)
        await router.add_firewall_filter({
            "chain": "input",
            "protocol": "udp",
            "dst-port": "67",
            "action": "drop",
            "comment": f"{GUARD_TAG}: DHCP flood drop",
        })

        # Best-effort: move guard rules to the top of input chain so they
        # run before any later catch-all accepts
        try:
            await _move_guard_rules_to_top(router)
        except Exception as e:
            log.debug(f"move-to-top failed (non-fatal): {e}")

        return True, "✅ Firewall rules applied"
    except Exception as e:
        log.error(f"apply_firewall_protection failed: {e}")
        try:
            await remove_firewall_protection(router)
        except Exception:
            pass
        return False, f"❌ Failed to apply: {e}"


async def remove_firewall_protection(router) -> tuple[bool, str]:
    """Remove all rules tagged with GUARD_TAG. Returns (success, message)."""
    try:
        rules = await router.get_firewall_filter()
    except Exception as e:
        return False, f"❌ Cannot list rules: {e}"

    removed = 0
    errors: list[str] = []
    for r in rules:
        if GUARD_TAG in (r.get("comment") or ""):
            try:
                await router.remove_firewall_rule(r[".id"])
                removed += 1
            except Exception as e:
                errors.append(str(e))

    if errors:
        return False, f"⚠️ Removed {removed}, errors: {'; '.join(errors[:2])}"
    return True, f"✅ Removed {removed} guard rule(s)"


async def _move_guard_rules_to_top(router) -> None:
    """Place guard-tagged input rules at position 0 (run first)."""
    rules = await router.get_firewall_filter()
    # Iterate in reverse so that successive moves to position 0 preserve
    # the original order of guard rules
    guard_ids = [
        r[".id"] for r in rules
        if r.get("chain") == "input" and GUARD_TAG in (r.get("comment") or "")
    ]
    for rid in reversed(guard_ids):
        try:
            await router.move_firewall_rule(rid, 0)
        except Exception as e:
            log.debug(f"move failed for {rid}: {e}")


# ─── Auto-mitigation ──────────────────────────────────────────────────────────

async def purge_flood_leases(
    router,
    sample_macs: list[str],
    max_remove: int = 200,
) -> int:
    """
    Remove dynamic leases whose MAC is in sample_macs.
    Returns number of leases removed.
    """
    try:
        leases = await router.get_dhcp_leases()
    except Exception:
        return 0

    mac_set = {m.upper() for m in sample_macs}
    removed = 0
    for lease in leases:
        if removed >= max_remove:
            break
        mac = (lease.get("mac-address") or "").upper()
        if mac in mac_set and lease.get("type", "dynamic") == "dynamic":
            try:
                await router.remove_dhcp_lease(lease[".id"])
                removed += 1
            except Exception:
                pass
    return removed
