# DHCP Guard — Changes

Adds DHCP starvation attack protection (against `dhcpig`, `Yersinia`,
and similar lease-exhaustion tools) to MikroBot. When you connect a
router, the detector turns on automatically and alerts your Telegram
chat the moment an attack begins. Optional firewall rate-limit rules
stop the flood at the router itself.

## How protection works

**Two layers:**

1. **Bot-side detector** (automatic on router add)
   - Sliding-window velocity check over the DHCP lease table
   - Polls every 30s (piggybacks on the existing `Monitor._poll_router`)
   - Triggers an alert when "new MACs in window" crosses threshold
   - 5-minute cooldown between duplicate alerts per router

2. **Firewall rate-limit** (opt-in, one tap after adding a router)
   - `/ip firewall filter` input chain: UDP/67 rate-limited
   - `accept` up to `<rate>,<burst>:packet`, `drop` the overflow
   - All rules tagged `comment="mikrobot-dhcp-guard"` so apply/remove
     is fully idempotent — they never clash with your own rules
   - Rules moved to the top of the input chain so they run first

**Optional auto-mitigation** (off by default, toggle in menu):
- When attack is detected, dynamic leases belonging to the sampled
  flood MACs are deleted. Only dynamic leases, never static.

## New files

| File | Purpose |
|---|---|
| `core/dhcp_guard.py` | `GuardSettings`, `GuardSettingsStore` (JSON-persisted), `DhcpAttackDetector` (sliding-window), `apply_firewall_protection`, `remove_firewall_protection`, `purge_flood_leases` |
| `handlers/dhcp_guard.py` | Telegram UI: toggle detector, apply/remove firewall, 3 threshold presets, auto-purge toggle, quick-setup post-`/add_router` |

## Modified files

| File | Change |
|---|---|
| `bot.py` | Instantiates `GuardSettingsStore`/`DhcpAttackDetector`, passes to `handlers.setup()` and `Monitor(...)` |
| `core/monitor.py` | Constructor accepts `guard_store`/`guard_detector`; `_poll_router()` feeds lease snapshot into detector; new `_handle_dhcp_attack()` sends alert + runs opt-in auto-purge; `on_router_removed()` also cleans guard state |
| `core/rbac.py` | Two new permissions: `dhcp.guard.view` (VIEWER), `dhcp.guard.manage` (OPERATOR) |
| `handlers/__init__.py` | Imports and registers `dhcp_guard_router`; `setup()` accepts and forwards guard deps |
| `handlers/context.py` | Adds `guard_store` and `guard_detector` to shared state; `init()` accepts them |
| `handlers/fsm.py` | On successful `/add_router`, auto-enables detector for the new router and shows `post_add_router()` keyboard with quick-setup button |
| `ui/keyboards.py` | Adds `🛡 DHCP Guard` button to `dhcp_menu()`; new `dhcp_guard_menu()`, `dhcp_guard_thresholds()`, `post_add_router()` |

## Data added

New file: `data/dhcp_guard.json` — auto-created on first save. Stores
per-(user_id, alias) `GuardSettings`. Delete it anytime to reset to
defaults; the detector will just re-create it.

## Thresholds (defaults)

| Preset | Window | New-lease alert | FW rate | FW burst |
|---|---|---|---|---|
| Strict | 60s | 10 | 20 pps | 50 |
| Balanced (default) | 60s | 20 | 50 pps | 100 |
| Lax | 120s | 50 | 100 pps | 200 |

## User flow

**On adding a router:**
1. User runs `/add_router`, enters host/user/pass/port as before
2. On success, detector is auto-enabled for this router
3. User sees a keyboard with `🛡 Apply DHCP Guard Firewall` button
4. Tapping it installs the rate-limit rules (Balanced preset)

**Managing later:** `📡 DHCP → 🛡 DHCP Guard` from main menu.

**On attack:** Telegram alert like:
```
🚨 DHCP STARVATION ATTACK
Router: home (192.168.1.1)
New leases: 127 in 60s
Total leases now: 135
Sample MACs:
  DE:AD:BE:EF:00:04
  DE:AD:BE:EF:00:12
  ...
  … and 122 more
```

## Safety notes

- Firewall rules are **not** applied automatically. They need one explicit
  tap. Rationale: custom firewall setups can conflict with rate-limits,
  so opt-in is safer than silent side-effects.
- Detector is off if `guard_store` is `None` — fully backward compatible.
- All guard rules are tagged; removing them never touches other rules.
- First poll per router is skipped as "baseline" — existing leases
  won't trigger a false alarm on bot startup.
- Cooldown prevents alert storms: max 1 alert per router per 5 minutes.

## RBAC

- `dhcp.guard.view` — VIEWER and above (see status)
- `dhcp.guard.manage` — OPERATOR and above (toggle, apply firewall,
  change presets, run auto-purge)

Matches the existing `dhcp.view`/`dhcp.manage` roles for consistency.

## Testing

The detector has been validated with a simulated attack:
- 5 existing clients baseline → no alert
- 3 new clients growth → no alert
- 30 new MACs in one poll → alert fires
- Immediate follow-up with more new MACs → silenced by cooldown
- Independent state per (user_id, alias) confirmed

## Limitations / honest disclosure

1. **Firewall rate-limit is global**, not per-source-MAC. Good
   legitimate clients can be dropped during an active attack — but the
   DHCP server is protected from exhaustion. If you need per-MAC rate
   limit, add `bridge filter` rules separately (out of scope here).
2. **DHCPDISCOVER has src=0.0.0.0**, so an IP-based address-list
   blocker is not effective at that stage. That's why we don't try to
   "add attacker to blacklist" — we rate-limit the protocol itself and
   purge their leases after the fact.
3. **Auto-purge deletes dynamic leases by MAC**. If a real client got
   unlucky and its MAC appeared in a flood sample, its lease gets
   removed — but the client will re-request and reconnect within
   seconds. No static leases are ever touched.
4. **The detector uses a 30s poll interval** (inherited from existing
   Monitor). A very fast attack (5s burst) may complete between polls
   but still be seen on the next poll because the lease table retains
   the new MACs.
