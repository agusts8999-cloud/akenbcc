"""Local secret encryption for inventory passwords."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from bcc.paths import app_data_dir

log = logging.getLogger(__name__)


class SecretBox:
    """Fernet encryption using machine-local key file."""

    def __init__(self) -> None:
        self._fernet = Fernet(self._load_or_create_key())

    def _key_file(self) -> Path:
        return app_data_dir() / ".vault_key"

    def _load_or_create_key(self) -> bytes:
        app_data_dir().mkdir(parents=True, exist_ok=True)
        path = self._key_file()
        if path.exists():
            return path.read_bytes().strip()
        # Derive from machine entropy + store
        raw = hashlib.sha256(os.urandom(32) + str(path).encode()).digest()
        key = base64.urlsafe_b64encode(raw)
        path.write_bytes(key)
        try:
            if sys.platform.startswith("win"):
                os.chmod(path, 0o600)
            else:
                os.chmod(path, 0o600)
        except OSError:
            pass
        return key

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        if not token:
            return ""
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken:
            log.warning("Gagal decrypt secret (token invalid)")
            return ""
