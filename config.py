"""
Configuration – reads from environment variables or .env file.

Required:
  BOT_TOKEN          – Telegram bot token from @BotFather

Optional:
  OWNER_ID           – Telegram user ID of the first owner (skip to auto-bootstrap on first /start)
  LOG_LEVEL          – Logging level: DEBUG | INFO | WARNING | ERROR (default: INFO)

Standalone (ROS7 Docker) mode – if running inside router container:
  MIKROTIK_HOST      – Router API host (default: 172.17.0.1)
  MIKROTIK_USER      – Router API username (default: admin)
  MIKROTIK_PASS      – Router API password
  STANDALONE=1       – Set to auto-add the configured router on startup
"""

import os
import sys
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

log = logging.getLogger("Config")


def _require_env(key: str, hint: str = "") -> str:
    val = os.environ.get(key, "").strip()
    _PLACEHOLDERS = {"", "PUT_TOKEN_HERE", "your_token_here", "change_me"}
    if val in _PLACEHOLDERS:
        msg = (
            f"\n{'='*60}\n"
            f"  FATAL: Required environment variable '{key}' is not set.\n"
            + (f"  Hint: {hint}\n" if hint else "")
            + f"{'='*60}\n"
        )
        sys.stderr.write(msg)
        sys.exit(1)
    return val


def _optional_int(key: str, default: int | None = None) -> int | None:
    raw = os.environ.get(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        log.warning(f"Config: {key}='{raw}' is not a valid integer, using default {default}")
        return default


def _optional_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip() or default


def _optional_bool(key: str) -> bool:
    return os.environ.get(key, "").lower() in ("1", "true", "yes")


def _valid_log_level(level: str) -> str:
    if level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        log.warning(f"Config: LOG_LEVEL='{level}' is invalid, defaulting to INFO")
        return "INFO"
    return level.upper()


# ─── Required ─────────────────────────────────────────────────────────────────

BOT_TOKEN: str = _require_env(
    "BOT_TOKEN",
    hint="Get your token from @BotFather on Telegram",
)

# ─── Optional ─────────────────────────────────────────────────────────────────

OWNER_ID: int | None = _optional_int("OWNER_ID")
LOG_LEVEL: str = _valid_log_level(_optional_str("LOG_LEVEL", "INFO"))

# ─── Standalone (SA) mode ─────────────────────────────────────────────────────

STANDALONE: bool = _optional_bool("STANDALONE")
MIKROTIK_HOST: str = _optional_str("MIKROTIK_HOST", "172.17.0.1")
MIKROTIK_USER: str = _optional_str("MIKROTIK_USER", "admin")
MIKROTIK_PASS: str = _optional_str("MIKROTIK_PASS", "")
MIKROTIK_PORT: int = _optional_int("MIKROTIK_PORT", 8728) or 8728
