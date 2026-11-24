from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import BASE_DIR

_KEY_PATH = BASE_DIR / "data" / ".credential_key"


def _load_or_create_key() -> bytes:
    _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _KEY_PATH.is_file():
        data = _KEY_PATH.read_bytes().strip()
        if data:
            return data
    key = Fernet.generate_key()
    _KEY_PATH.write_bytes(key)
    try:
        os.chmod(_KEY_PATH, 0o600)
    except OSError:
        pass
    return key


def encrypt_secret(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    return Fernet(_load_or_create_key()).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    try:
        return Fernet(_load_or_create_key()).decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""


def secret_hint(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    if len(value) <= 8:
        return "••••"
    return f"{value[:3]}••••{value[-4:]}"
