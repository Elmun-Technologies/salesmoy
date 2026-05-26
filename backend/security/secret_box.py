"""Symmetric encryption for credentials stored in the DB.

Used for SalesDoctor passwords today; reusable for any small secret
the integration must persist (we need to *recover* the value to re-login,
so a one-way hash isn't acceptable).

The encryption key is derived from APP_SECRET_KEY so no separate key
needs to be provisioned — operators only need to keep APP_SECRET_KEY
stable. If APP_SECRET_KEY changes, previously-encrypted values become
unreadable; the application falls back to the plaintext value if it
can't decrypt (since old DBs may still hold unencrypted passwords).
"""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from config import get_settings

logger = logging.getLogger(__name__)


# Distinguishes our ciphertext from a legacy plaintext password.
_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    secret = (get_settings().app_secret_key or "").encode("utf-8")
    if not secret:
        raise RuntimeError(
            "APP_SECRET_KEY is empty — refusing to encrypt secrets with a blank key."
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a string. Returns prefixed ciphertext."""
    if not plaintext:
        return ""
    token = _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return _PREFIX + token


def decrypt_secret(stored: Optional[str]) -> str:
    """Decrypt a string previously produced by encrypt_secret.

    If `stored` doesn't carry the encryption prefix, it's treated as
    legacy plaintext and returned as-is — that lets us migrate gradually
    without a blocking data backfill.
    """
    if not stored:
        return ""
    if not stored.startswith(_PREFIX):
        # Legacy / unencrypted value — caller should re-save to encrypt.
        return stored
    try:
        return _fernet().decrypt(stored[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken:
        logger.error(
            "Failed to decrypt stored secret — APP_SECRET_KEY may have changed "
            "since the value was written. Treating as missing."
        )
        return ""
