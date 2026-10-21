"""Two fresh processes contend for one expired, rotating SIWC credential record."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from chatgpt import sign_in
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from jwt.algorithms import RSAAlgorithm
from siwc_fixture import Fixture

from sigma import chatgpt_auth as auth
from sigma.ai_store import directory, transaction

REAL_CLIENT = httpx.AsyncClient


async def worker(pem):
    fixture = Fixture()
    loaded = serialization.load_pem_private_key(pem.read_bytes(), password=None)
    assert isinstance(loaded, RSAPrivateKey)
    fixture.key = loaded
    fixture.jwk = RSAAlgorithm.to_jwk(fixture.key.public_key(), as_dict=True)
    fixture.jwk.update(kid="sigma-explicit-fixture", use="sig", alg="RS256")
    fixture.serial = os.getpid() * 10
    async with transaction() as stored:
        account = stored["accounts"][stored["active"]]
        fixture.refreshes[account["refresh_token"]] = {
            "subject": account["subject"],
            "issued": account["client_id"],
        }

    async def handler(request):
        if request.url.path.endswith("/token"):
            # Amplify contention while the actual cross-process lock is held.
            await asyncio.sleep(0.2)
        return fixture.handler(request)

    def client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    with patch("httpx.AsyncClient", side_effect=client):
        state = await auth.session()
        assert state["status"] == "connected"
    print(json.dumps({"status": state["status"], "refreshes": fixture.refreshed}))


async def checks(root):
    fixture = Fixture()

    def client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(fixture.handler), **kwargs)

    with patch("httpx.AsyncClient", side_effect=client):
        _, result = await sign_in(fixture)
        assert result["status"] == "connected"
    async with transaction() as stored:
        account_id, host = stored["active"], stored["ext_agent_host_id"]
        account = stored["accounts"][account_id]
        issued, previous = account["client_id"], account["refresh_token"]
        account["expires_at"] = account["earliest_refresh_at"] = time.time() - 1
    pem = root / "fixture-only.pem"
    with pem.open("wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(
            fixture.key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    processes = [
        await asyncio.create_subprocess_exec(
            sys.executable,
            __file__,
            "--worker",
            str(pem),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        for _ in range(2)
    ]
    async with asyncio.timeout(20):
        byte_results = await asyncio.gather(*(process.communicate() for process in processes))
    results = [(output.decode(), error.decode()) for output, error in byte_results]
    assert all(process.returncode == 0 for process in processes), [error for _, error in results]
    assert sum(json.loads(output)["refreshes"] for output, _ in results) == 1
    async with transaction() as stored:
        assert stored["ext_agent_host_id"] == host and stored["active"] == account_id
        assert stored["accounts"][account_id]["client_id"] == issued
        assert stored["accounts"][account_id]["refresh_token"] != previous
    assert all(previous not in output + error for output, error in results)
    assert (directory() / "credentials.json").stat().st_mode & 0o777 == 0o600
    print(
        "PASS restart/session reuse and real cross-process rotating refresh serialize to one exchange; stable host/account/client and private atomic storage"
    )


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        asyncio.run(worker(Path(sys.argv[2])))
        return
    with (
        TemporaryDirectory() as temporary,
        patch.dict(os.environ, {"SIGMA_AUTH_HOME": str(Path(temporary) / "auth")}),
    ):
        asyncio.run(checks(Path(temporary)))


if __name__ == "__main__":
    main()
