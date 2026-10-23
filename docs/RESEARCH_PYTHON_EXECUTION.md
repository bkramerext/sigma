# Research Python execution contract

`sigma.python_sandbox.execute_research_code(path, source, *, session_id,
strategy_id, cycle)` is the typed service boundary for future research-agent
orchestration. A caller submits one untrusted source string and optional UUID
provenance. The call returns an execution record only after the bounded run and
durable project-sidecar write have completed. It has no automatic repair or
provider-call loop.

The local API mirrors this contract:

- `POST /api/projects/research-executions` with `{path, source, session_id?,
  strategy_id?, cycle?}` executes once and returns the saved record.
- `GET /api/projects/research-executions?path=...` lists saved records.
- `GET /api/projects/research-executions/{id}?path=...` retrieves one record.

Each immutable JSON record under the project's private
`research-executions/` directory includes the exact source, project/session/
strategy/cycle references, UTC timestamp, status, exit code, bounded stdout and
stderr, elapsed wall time, image identifier and resource-policy snapshot.
Execution status is `completed`, `failed`, `timeout`, `output_limit`,
`unavailable`, or `busy`. Only one container is admitted per local backend
process; concurrent attempts are captured as busy without starting a container.
A nonzero process exit is never a successful execution. Failed,
timed-out, output-limited, or unavailable attempts are retained as such.

The locally built `sigma-research-python:0.1` image is resolved to its local
immutable SHA-256 image ID and run by that ID; it is never pulled by a research
request. The artifact saves both the tag and resolved ID. It runs as UID 65532 with no network, read-only root, a 64 MiB
non-executable `/tmp`, no Linux capabilities, no-new-privileges, a 512 MiB
memory and swap ceiling, one CPU, 64 processes, 15 seconds wall time, 16,000
UTF-8 source bytes, and 32,000 combined stdout/stderr bytes. There are no host
bind mounts or forwarded credentials. The image contains pinned Python 3.12.8,
NumPy 2.2.2, SciPy 1.15.1, pandas 2.2.3, SymPy 1.13.3 and Matplotlib 3.10.0.

The runtime API is a tool seam, not a claim that agents already invoke it. A18
must explicitly add the call at a research role boundary and attach the returned
execution ID/result to role context and a session artifact. That orchestration
is intentionally not changed by A19. Executed computation remains evidence of
the finite program run, not a proof of a general claim or Lean verification.

The boundary assumes a trusted host kernel, Docker daemon, and image-build
process. Build-time dependency download requires network access; research
containers have none. Users must rebuild the image after changing the pinned
lock or image definition.
