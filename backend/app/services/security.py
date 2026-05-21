"""Security helpers for reversible encryption of sensitive values."""

from __future__ import annotations
from utils import _read_env
from cryptography.fernet import Fernet, InvalidToken


def get_fernet_key() -> str:
    """Load Fernet key from environment.

    The key must be urlsafe base64-encoded (Fernet format).
    """
    key = _read_env("APP_FERNET_KEY", "")
    if not key:
        raise ValueError("Missing APP_FERNET_KEY in environment")
    return key


def encrypt_secret_fernet(value: str, key: str | None = None) -> str:
    """Encrypt a sensitive value using Fernet.

    Uses APP_FERNET_KEY by default.
    """
    clean = (value or "").strip()
    if not clean:
        raise ValueError("Cannot encrypt an empty value")

    fernet = Fernet((key or get_fernet_key()).encode("utf-8"))
    return fernet.encrypt(clean.encode("utf-8")).decode("utf-8")


def decrypt_secret_fernet(value_encrypted: str, key: str | None = None) -> str:
    """Decrypt a Fernet-encrypted value.

    Uses APP_FERNET_KEY by default.
    """
    token = (value_encrypted or "").strip()
    if not token:
        raise ValueError("Cannot decrypt an empty value")

    try:
        fernet = Fernet((key or get_fernet_key()).encode("utf-8"))
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid Fernet token or key") from exc
