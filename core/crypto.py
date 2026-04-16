"""
Password encryption for router credentials stored in data/routers.json.

Uses Fernet symmetric encryption with a key derived from BOT_TOKEN via PBKDF2.
This means:
  - Passwords are encrypted at rest
  - Without BOT_TOKEN the file is useless
  - Migration from plaintext is automatic on first load
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("Crypto")

_SALT = b"mikrobot-credentials-v1"
_ITERATIONS = 100_000
_fernet: Fernet | None = None


def init(bot_token: str):
    """Derive encryption key from BOT_TOKEN and initialize Fernet."""
    global _fernet
    key = hashlib.pbkdf2_hmac("sha256", bot_token.encode(), _SALT, _ITERATIONS)
    _fernet = Fernet(base64.urlsafe_b64encode(key))
    log.debug("Crypto initialized")


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string → base64 ciphertext."""
    if not _fernet:
        raise RuntimeError("Crypto not initialized — call crypto.init() first")
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64 ciphertext → plaintext string."""
    if not _fernet:
        raise RuntimeError("Crypto not initialized — call crypto.init() first")
    return _fernet.decrypt(ciphertext.encode()).decode()


def is_encrypted(value: str) -> bool:
    """Heuristic: Fernet tokens always start with 'gAAAAA'."""
    return value.startswith("gAAAAA")


def ensure_encrypted(value: str) -> str:
    """Encrypt if plaintext, return as-is if already encrypted."""
    if not value:
        return value
    if is_encrypted(value):
        return value
    return encrypt(value)


def safe_decrypt(value: str) -> str:
    """Decrypt if encrypted, return as-is if plaintext (migration path)."""
    if not value:
        return value
    if not is_encrypted(value):
        return value  # Legacy plaintext — will be encrypted on next save
    try:
        return decrypt(value)
    except InvalidToken:
        log.warning("Failed to decrypt credential — token may have changed")
        return value
