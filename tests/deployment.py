"""Fail-closed production startup and private-volume backup checks."""

from __future__ import annotations

import os
import stat
import sys
import tarfile
import tempfile
from pathlib import Path

from sigma.deployment import DeploymentConfigurationError, validate_production_configuration

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ops.data_archive import backup, restore


def assert_raises(call, error):
    try:
        call()
    except error:
        return
    raise AssertionError(f"expected {error.__name__}")


with tempfile.TemporaryDirectory(prefix="sigma-deploy-test-") as temporary:
    root = Path(temporary)
    data = root / "private-data"
    data.mkdir(mode=0o700)
    data.chmod(0o700)
    marker = data / ".sigma-deployment-volume-v1"
    marker.write_bytes(b"SIGMA durable cloud data volume v1\n")
    marker.chmod(0o600)
    demo_dir = root / "image" / "cloud-demo"
    demo_dir.mkdir(parents=True)
    demo_file = Path(__file__).resolve().parents[1] / "cloud-demo/handshake-demo-audit.json"
    (demo_dir / demo_file.name).write_bytes(demo_file.read_bytes())
    auth = data / "auth"
    auth.mkdir(mode=0o700)
    auth.chmod(0o700)
    env = {
        "SIGMA_CLOUD_AUTH_ENABLED": "true",
        "GOOGLE_OIDC_CLIENT_ID": "fixture-client.apps.googleusercontent.com",
        "GOOGLE_OIDC_CLIENT_SECRET": "deterministic-fixture-secret",
        "SIGMA_CLOUD_PUBLIC_ORIGIN": "https://sigma.example.test",
        "SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL": "admin@example.test",
        "SIGMA_CLOUD_ADMIN_CONTACT_EMAIL": "admin@example.test",
        "SIGMA_CLOUD_AUTH_HOME": str(auth),
        "SIGMA_CLOUD_WORKSPACES_ROOT": str(data / "workspaces"),
        "SIGMA_CLOUD_DEMO_AUDIT": str(demo_dir / demo_file.name),
        "SIGMA_PERSISTENT_DATA_ROOT": str(data),
    }
    previous = {key: os.environ.get(key) for key in env}
    try:
        os.environ.update(env)
        result = validate_production_configuration()
        assert result["data_root"] == str(data.resolve())
        assert Path(result["auth_database"]).is_file()
        workspace = Path(result["workspace_root"])
        assert workspace.is_dir() and workspace.is_relative_to(data.resolve()), (workspace, data)

        os.environ.pop("GOOGLE_OIDC_CLIENT_SECRET")
        assert_raises(validate_production_configuration, DeploymentConfigurationError)
        os.environ.update(env)
        os.environ["SIGMA_CLOUD_PUBLIC_ORIGIN"] = "http://sigma.example.test"
        assert_raises(validate_production_configuration, DeploymentConfigurationError)
        os.environ.update(env)
        data.chmod(0o755)
        assert_raises(validate_production_configuration, DeploymentConfigurationError)
        data.chmod(0o700)
        os.environ.update(env)
        marker.unlink()
        assert_raises(validate_production_configuration, DeploymentConfigurationError)
        marker.write_bytes(b"SIGMA durable cloud data volume v1\n")
        marker.chmod(0o600)
        os.environ.update(env)
        os.environ["SIGMA_CLOUD_DEMO_AUDIT"] = str(data / "private-demo.json")
        (data / "private-demo.json").write_bytes(demo_file.read_bytes())
        (data / "private-demo.json").chmod(0o600)
        assert_raises(validate_production_configuration, DeploymentConfigurationError)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    sample = data / "workspace" / "project.sigma" / "project.json"
    sample.parent.mkdir(parents=True, mode=0o700)
    sample.write_text('{"fixture":true}', encoding="utf-8")
    sample.chmod(0o600)
    archive = root / "backup.tar.gz"
    backup(data, archive)
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    restored = root / "restored"
    restore(archive, restored)
    assert (restored / "workspace/project.sigma/project.json").read_text() == '{"fixture":true}'
    assert stat.S_IMODE((restored / "workspace").stat().st_mode) == 0o700

    occupied = root / "occupied"
    occupied.mkdir()
    (occupied / "keep").touch()
    assert_raises(lambda: restore(archive, occupied), ValueError)
    alias = root / "restore-alias"
    alias.symlink_to(restored, target_is_directory=True)
    assert_raises(lambda: restore(archive, alias), ValueError)

    malicious = root / "malicious.tar.gz"
    with tarfile.open(malicious, "w:gz") as tar:
        info = tarfile.TarInfo("../../escape")
        info.size = 1
        import io

        tar.addfile(info, io.BytesIO(b"x"))
    assert_raises(lambda: restore(malicious, root / "unsafe"), ValueError)
    assert not (root.parent / "escape").exists()

print("production startup and private-volume backup checks passed")
