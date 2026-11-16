"""Adversarial offline tests for the greenfield multi-user Personal vault."""
from __future__ import annotations

import importlib.util
import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("shared_vault", ROOT / "src/sigma/personal_vault.py")
assert spec and spec.loader
vault_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vault_module)
Vault = vault_module.Vault
VaultError = vault_module.VaultError
A, B = "a" * 32, "b" * 32


def rejects(callback) -> None:
    try:
        callback()
    except VaultError:
        return
    raise AssertionError("Vault accepted invalid credentials or unsafe state")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = root / "users"
        store.mkdir(mode=0o700)
        key = root / "master-key"
        key.write_bytes(os.urandom(32))
        key.chmod(0o600)
        vault = Vault(store, key)
        assert vault.read(A) is None and vault.read(B) is None
        for invalid in ("../a", "user@example.com", A.upper(), "0" * 31, ""):
            rejects(lambda invalid=invalid: vault.read(invalid))
        vault.write(A, {"token": "secret-for-A", "version": 1})
        vault.write(B, {"token": "secret-for-B", "version": 1})
        assert vault.read(A)["token"] == "secret-for-A"
        assert vault.read(B)["token"] == "secret-for-B"
        assert b"secret-for-A" not in (store / (A + ".sealed")).read_bytes()
        assert b"secret-for-B" not in (store / (B + ".sealed")).read_bytes()
        # A copied ciphertext cannot be decrypted as another workspace.
        shutil.copyfile(store / (A + ".sealed"), store / (B + ".sealed"))
        rejects(lambda: vault.read(B))
        assert vault.read(A)["token"] == "secret-for-A"
        raw = bytearray((store / (A + ".sealed")).read_bytes())
        raw[-5] ^= 1
        (store / (A + ".sealed")).write_bytes(raw)
        rejects(lambda: vault.read(A))
        # A weak key file or symlinked key is always rejected.
        key.chmod(0o644)
        rejects(lambda: vault.read(A))
        key.chmod(0o600)
        link = root / "linked-key"
        link.symlink_to(key)
        rejects(lambda: Vault(store, link).read(A))
        # Key material must not be stored beside encrypted credential records.
        inner_key = store / "key"
        inner_key.write_bytes(os.urandom(32))
        inner_key.chmod(0o600)
        rejects(lambda: Vault(store, inner_key).read(A))
    print("PASS shared Personal vault: identity isolation, authenticated encryption, tamper rejection, key permissions")


if __name__ == "__main__":
    main()
