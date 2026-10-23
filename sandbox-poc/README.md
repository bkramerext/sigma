# Standalone research Python sandbox proof of concept

Build the image with network access available for the one-time dependency install:

```sh
docker build -t sigma-research-python:0.1 sandbox-poc
printf 'import numpy, scipy, pandas, sympy, matplotlib\nprint("ready")\n' | python sandbox-poc/run.py
uv run --locked --no-sync python sandbox-poc/runtime-check.py
uv run --locked --no-sync python sandbox-poc/agent-workflow-check.py
uv run --locked --no-sync python sandbox-poc/research-check.py
uv run --locked --no-sync python sandbox-poc/adversarial-check.py
```

The runtime check exercises isolation, dependencies, limits, and artifact
storage directly. The agent workflow check runs the actual Docker sandbox
through a deterministic Investigator/Skeptic session and retrieves its plot.
The scientific check runs eight scripted research workflows with actual
numerical, symbolic and statistical experiments, including revised programs
after exceptions, contradictions and timeout, a misleading printed proof
claim, a 100,000-row CSV, and three simultaneous research strategies. Use `--output-dir <directory>`
to retain their projects, exact code, outputs, CSVs and plots for inspection.
The adversarial check includes a real backend SIGKILL and may take about
30 seconds while the container watchdog expires. These use fixture provider
responses and never make model calls.

For an explicitly authorized live evaluation, `plan-research-check.py --run`
uses only the already selected connected ChatGPT plan. It refuses API-key
billing, never changes billing mode and is not part of any test suite. It can
consume plan allowance, including when a remote call times out. Set
`--rounds 1` for a two-call cap; `--reasoning-effort` and `--output-tokens`
control the saved evaluation project configuration.

Every execution starts a fresh container with no network, a non-root UID, a
read-only root filesystem, a small writable `/tmp`, no Linux capabilities,
no-new-privileges, 512 MiB memory, one CPU, 64 processes and a wall timeout.
The host passes code only over stdin and imposes source/output byte limits.
The image must be built locally; runtime never pulls an image. This is a
container boundary, not a defense against a compromised host kernel or runtime.
