"""Opt-in local Sage sizing/isolation probe. Never pulls images or runs models."""

import json
import subprocess
import time
from uuid import uuid4

IMAGE = "sagemath/sagemath@sha256:fb96c7fb10d672f3be0d088399db3aeac52650416d1bb71f74f26429ea35778f"

# Fixed trusted program. This does not create a general hosted execution API.
SOURCE = r"""
import json, os, pathlib, resource, socket
from sage.all import PolynomialRing, QQ, ZZ, factor, version
ring = PolynomialRing(QQ, 'x'); x = ring.gen()
assert (x**4 - 1).factor().prod() == x**4 - 1
assert list(factor(ZZ(2)**64 - 1)) == [(3,1),(5,1),(17,1),(257,1),(641,1),(65537,1),(6700417,1)]
matrix = __import__('sage.all', fromlist=['matrix']).matrix(QQ, [[1,2],[3,4]])
assert matrix.det() == -2
assert os.getuid() == 1000
assert not pathlib.Path('/var/run/docker.sock').exists()
assert not any(key in os.environ for key in ('OPENAI_API_KEY','CLOUDFLARE_API_TOKEN','SIGMA_AUTH_HOME'))
status = pathlib.Path('/proc/self/status').read_text()
assert 'CapEff:\t0000000000000000' in status
assert 'NoNewPrivs:\t1' in status
try:
    pathlib.Path('/forbidden').write_text('write')
except OSError:
    pass
else:
    raise AssertionError('root filesystem writable')
for host,port in [('192.0.2.1',80),('198.51.100.1',443),('203.0.113.1',53)]:
    try:
        socket.create_connection((host,port),timeout=0.2)
    except OSError:
        pass
    else:
        raise AssertionError('network available')
pathlib.Path('/work/result.txt').write_text(str((x**4-1).factor()))
print(json.dumps({'sage': version(), 'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 'algebra': 'passed', 'number_theory': 'passed', 'isolation': 'local Docker only'}))
"""


def main() -> None:
    image = json.loads(subprocess.check_output(["docker", "image", "inspect", IMAGE], timeout=10))[
        0
    ]
    samples = []
    for _ in range(3):
        name = "sigma-t221-sage-" + uuid4().hex
        command = [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--platform=linux/amd64",
            "--name",
            name,
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--user=1000:1000",
            "--memory=1g",
            "--memory-swap=1g",
            "--cpus=1",
            "--pids-limit=128",
            "--tmpfs=/tmp:rw,nosuid,nodev,size=128m,mode=1777",
            "--tmpfs=/work:rw,nosuid,nodev,size=16m,mode=1777",
            "--env=HOME=/tmp",
            "--workdir=/work",
            "--entrypoint=/usr/bin/sage",
            IMAGE,
            "-python",
            "-c",
            SOURCE,
        ]
        start = time.monotonic()
        try:
            result = subprocess.run(
                command, check=False, capture_output=True, text=True, timeout=90
            )
            if result.returncode:
                raise RuntimeError(result.stderr[-3000:] or result.stdout[-3000:])
            samples.append(
                {
                    "elapsed_seconds": round(time.monotonic() - start, 3),
                    "result": json.loads(result.stdout),
                }
            )
        finally:
            subprocess.run(
                ["docker", "rm", "-f", name], check=False, capture_output=True, timeout=10
            )
    print(
        json.dumps(
            {
                "image": IMAGE,
                "image_id": image["Id"],
                "architecture": image["Architecture"],
                "docker_inspect_size_bytes": image["Size"],
                "samples": samples,
                "limits": {"memory_mib": 1024, "cpus": 1, "pids": 128},
                "scope": "Local amd64 emulation; no Cloudflare cold-start measurement",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
