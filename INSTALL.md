# DHCP Guard — Installation

This patch layout mirrors your project directory, so installation is a
plain copy.

## Option 1 — apply over existing checkout (recommended)

```bash
# From the directory containing this patch folder:
cp -r mikrobot-dhcp-guard/core/*     /path/to/mikrobot/core/
cp -r mikrobot-dhcp-guard/handlers/* /path/to/mikrobot/handlers/
cp -r mikrobot-dhcp-guard/ui/*       /path/to/mikrobot/ui/
cp    mikrobot-dhcp-guard/bot.py     /path/to/mikrobot/

# Restart the bot
cd /path/to/mikrobot
python bot.py
# or, if dockerised:
docker compose restart
```

The copy overwrites:
- `bot.py`
- `core/monitor.py`
- `core/rbac.py`
- `handlers/__init__.py`
- `handlers/context.py`
- `handlers/fsm.py`
- `ui/keyboards.py`

And adds two new files:
- `core/dhcp_guard.py`
- `handlers/dhcp_guard.py`

## Option 2 — git workflow (safer)

```bash
cd /path/to/mikrobot
git checkout -b feature/dhcp-guard
# copy files as above
git add -A
git diff --stat
# review, commit, push, open PR
git commit -m "feat: DHCP starvation protection (detector + FW rate-limit)"
```

## Option 3 — unpack from scratch

If you don't have a clone yet:

```bash
git clone https://github.com/flashback7766/mikrobot.git
cd mikrobot
cp -r /path/to/mikrobot-dhcp-guard/core/*     core/
cp -r /path/to/mikrobot-dhcp-guard/handlers/* handlers/
cp -r /path/to/mikrobot-dhcp-guard/ui/*       ui/
cp    /path/to/mikrobot-dhcp-guard/bot.py     .
python bot.py
```

## Verification after install

1. Start the bot. Logs should include normal startup, plus any existing
   routers will reconnect as before — no new warnings expected.
2. Send `/menu` → `📡 DHCP`. The menu should show a new `🛡 DHCP Guard`
   button.
3. Tap it. Status page should read:
   ```
   Detector: ⚪ OFF   (for existing routers)
   Firewall (on router): 🔴 not installed
   ```
4. Tap `⚪ Detector: OFF` — it flips to `🟢 ON`.
5. Simulate activity (or just wait) — detector runs every 30s, you can
   verify in the bot logs it's polling.

## Verifying against a live attack (optional)

On a **test network only**, against a lab router:
```bash
# Install dhcpig (or clone: https://github.com/kamorin/DHCPig)
pip install scapy
sudo python pig.py eth0
```
Within ~30s you should see the Telegram alert. Stop dhcpig with Ctrl+C.

## Rollback

If anything breaks:
```bash
cd /path/to/mikrobot
git checkout main -- bot.py core/ handlers/ ui/
rm -f core/dhcp_guard.py handlers/dhcp_guard.py data/dhcp_guard.json
```

Or just re-clone from GitHub.

## Troubleshooting

**"DHCP Guard not initialised" alert:**
Bot started with `guard_store=None`. Means `bot.py` wasn't updated.
Re-copy `bot.py`.

**Firewall button does nothing:**
Check the bot user has `dhcp.guard.manage` role (OPERATOR or higher).
Owner and admin always have it. For a viewer, promote them via
`Settings → Bot Users`.

**Rules applied but no traffic blocked during attack:**
MikroTik evaluates filter rules top-to-bottom. If you have a broad
`accept established,related` rule above the guard rules, DHCP packets
may slip through. The applier tries to move guard rules to the top,
but if they landed below your own rules, move them manually in
`🛡 Firewall → Filter Rules`.

**False alarms on bot restart:**
The detector skips the first poll per router (treats current leases as
baseline). If you still see false alarms, raise the threshold: 
`🛡 DHCP Guard → ⚙️ Thresholds → Lax`.
