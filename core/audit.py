"""
Audit log — records all significant user actions to a rotating log file.
Useful for security review and debugging.

Log format: timestamp | user_id | action | details
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

Path("data").mkdir(exist_ok=True)

_audit = logging.getLogger("Audit")
_audit.setLevel(logging.INFO)
_audit.propagate = False  # Don't spam the main log

_handler = RotatingFileHandler(
    "data/audit.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
    encoding="utf-8",
)
_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
_audit.addHandler(_handler)


def log_action(user_id: int, action: str, details: str = ""):
    """Log a user action."""
    _audit.info(f"{user_id} | {action} | {details}")


def log_admin(user_id: int, action: str, target: str = ""):
    """Log an admin/owner action (role changes, router add/remove)."""
    _audit.warning(f"{user_id} | ADMIN:{action} | {target}")


def log_security(user_id: int, action: str, details: str = ""):
    """Log a security-relevant event (auth failures, permission denied)."""
    _audit.warning(f"{user_id} | SECURITY:{action} | {details}")
