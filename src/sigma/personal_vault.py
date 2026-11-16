"""Per-user encrypted credential vault for SIGMA's NEW shared Docker POC.

No legacy per-user-container data is read or migrated. Authentication of the
workspace identity is the responsibility of the trusted SIGMA RPC boundary.
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
import stat
import tempfile
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_SCOPE = re.compile(r"[0-9a-f]{32}\Z")
_AAD = b"sigma-shared-personal-v1:"
_MAX = 1_000_000


class VaultError(RuntimeError):
    """Fail closed without exposing keys, tokens, or paths."""


class Vault:
    def __init__(self, root: Path, key_file: Path) -> None:
        self.root, self.key_file = root, key_file

    def _cipher(self) -> AESGCM:
        try:
            root = self.root.lstat()
            fd = os.open(self.key_file, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                key_info = os.fstat(stream.fileno())
                key = stream.read(33)
            if (
                not stat.S_ISDIR(root.st_mode)
                or root.st_uid != os.geteuid()
                or stat.S_IMODE(root.st_mode) != 0o700
                or not stat.S_ISREG(key_info.st_mode)
                or key_info.st_uid not in (0, os.geteuid())
                or stat.S_IMODE(key_info.st_mode) != 0o600
                or self.key_file.resolve().is_relative_to(self.root.resolve())
                or len(key) != 32
            ):
                raise VaultError("Encrypted credential storage unavailable")
        except OSError as exc:
            raise VaultError("Encrypted credential storage unavailable") from exc
        return AESGCM(key)

    def _path(self, workspace: str) -> Path:
        if not isinstance(workspace, str) or not _SCOPE.fullmatch(workspace):
            raise VaultError("Invalid workspace identity")
        return self.root / (workspace + ".sealed")

    def read(self, workspace: str) -> dict[str, Any] | None:
        cipher, path = self._cipher(), self._path(workspace)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise VaultError("Credential record unavailable") from exc
        try:
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                        or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 2 * _MAX):
                    raise VaultError("Credential record unavailable")
                value = json.loads(stream.read(2 * _MAX + 1))
            if set(value) != {"v", "nonce", "data"} or value["v"] != 1:
                raise ValueError()
            nonce = base64.b64decode(value["nonce"], validate=True)
            data = base64.b64decode(value["data"], validate=True)
            if len(nonce) != 12 or len(data) > _MAX + 16:
                raise ValueError()
            decoded = json.loads(cipher.decrypt(nonce, data, _AAD + workspace.encode()))
            if not isinstance(decoded, dict):
                raise TypeError("Unexpected credential record type")
            return decoded
        except (ValueError, TypeError, KeyError, InvalidTag, UnicodeError) as exc:
            raise VaultError("Invalid, tampered, or wrong-user credential record") from exc

    def write(self, workspace: str, record: dict[str, Any]) -> None:
        cipher, path = self._cipher(), self._path(workspace)
        raw = json.dumps(record, separators=(",", ":")).encode()
        if len(raw) > _MAX:
            raise VaultError("Credential record too large")
        nonce = secrets.token_bytes(12)
        data = cipher.encrypt(nonce, raw, _AAD + workspace.encode())
        sealed = json.dumps({
            "v": 1, "nonce": base64.b64encode(nonce).decode(),
            "data": base64.b64encode(data).decode(),
        }).encode()
        fd, name = tempfile.mkstemp(prefix=".sealed-", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as f:
                os.fchmod(f.fileno(), 0o600)
                f.write(sealed)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, path)
            dfd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        finally:
            Path(name).unlink(missing_ok=True)
