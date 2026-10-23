# Standalone research Python sandbox proof of concept

Build the image with network access available for the one-time dependency install:

```sh
docker build -t sigma-research-python:0.1 sandbox-poc
printf 'import numpy, scipy, pandas, sympy, matplotlib\nprint("ready")\n' | python sandbox-poc/run.py
uv run --locked --no-sync python sandbox-poc/runtime-check.py
uv run --locked --no-sync python sandbox-poc/agent-workflow-check.py
```

The runtime check exercises isolation, dependencies, limits, and artifact
storage directly. The agent workflow check runs the actual Docker sandbox
through a deterministic Investigator/Skeptic session and retrieves its plot.

Every execution starts a fresh container with no network, a non-root UID, a
read-only root filesystem, a small writable `/tmp`, no Linux capabilities,
no-new-privileges, 512 MiB memory, one CPU, 64 processes and a wall timeout.
The host passes code only over stdin and imposes source/output byte limits.
The image must be built locally; runtime never pulls an image. This is a
container boundary, not a defense against a compromised host kernel or runtime.
