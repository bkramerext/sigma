# Research Python execution contract

`sigma.python_sandbox.execute_research_code(path, source, *, session_id,
strategy_id, cycle)` is the typed service boundary used by the A18 portfolio
research loop. An Investigator may return `python_code` (or `null`) in its
strict response. The proposal is limited to 4,000 characters and checked
against the sandbox's 16,000-byte source bound. SIGMA executes a nonempty proposal once before the Skeptic
call. Before dispatch, the service durably reserves the exact proposal and
provenance. A process-held file lock distinguishes an active reservation from
one left behind by a dead backend, including inspection from another process.
The call returns after the bounded run and durable terminal write. A stale
reservation is exposed as `interrupted`: the code may have run, and no result
can be inferred. Recovery never reruns that uncertain proposal automatically.
Final records are immutable. There is no automatic repair or additional
provider call.

An Investigator's proposal text predates execution. Its statements that a run
is still proposed are preserved as history; the attached execution supplies
the later status. The Skeptic synthesizes that result and retires resolved
execution obligations without requiring a cycle just to rewrite the proposal.

The Skeptic receives the full Investigator output, including the exact source
and a `python_execution` record with execution ID, status, exit code,
stdout/stderr, duration, resource snapshot, and captured file metadata. The
same nested record is retained in the Investigator step and the committed
session artifact. A stop or pause during execution waits for the bounded
container to finish, stores its terminal record, and then preserves the user's
control action. Timeouts, nonzero exits, output-limit stops, unavailable images,
and busy admission remain explicit statuses. Identical failed, timed-out,
output-limited, or interrupted source in a later cycle of the same strategy
and session reuses the original evidence and its original cycle provenance,
with an explicit reuse reason. Changed source can run; busy/unavailable runs
can be attempted again after the environment recovers. Serialized provider input is
bounded at 256,000 characters so the Skeptic can inspect complete bounded code
and output without an unbounded request.

The session event stream records execution start and terminal status with the
execution ID. Project JSON audit exports and A20 paper evidence snapshots retain
the exact proposed source and full execution record. Captured binary files stay
in the private project sidecar and can be retrieved through the execution
artifact endpoint.
Peer strategies and later sessions receive attributed computation previews,
including source and terminal status, with explicit stdout/stderr truncation
flags. Full evidence remains unchanged in the original record. Binary plots
and datasets are available through the API; models receive their metadata and
printed summaries, not their pixels or complete contents.

The local API mirrors this contract:

- `POST /api/projects/research-executions` with `{path, source}` and an optional
  complete `{session_id, strategy_id, cycle}` tuple executes once and returns
  the saved record.
- `GET /api/projects/research-executions?path=...` lists saved records.
- `GET /api/projects/research-executions/{id}?path=...` retrieves one record.
- `GET /api/projects/research-executions/{id}/artifacts/{filename}?path=...`
  retrieves one captured output file after project, filename, size, and SHA-256
  checks.

Each immutable JSON record under the project's private
`research-executions/` directory includes the exact source, project/session/
strategy/cycle references, UTC timestamp, status, exit code, bounded stdout and
stderr, elapsed wall time, image identifier and resource-policy snapshot.
Captured files are restricted to small regular files with flat names. Their
content is stored separately under the same private sidecar, and the record
contains media type, byte size, and SHA-256. The runtime uses a private 16 MiB
tmpfs for `/artifacts`; the host copies files out while the container is still
alive and persists them with the record.
Session, strategy, and cycle references must be supplied together and are
checked against the selected project's saved session. Sample projects cannot
receive execution records; open a sample copy first.
Execution status is `running`, `interrupted`, `completed`, `failed`, `timeout`,
`output_limit`, `unavailable`, or `busy`. Only one container is admitted per local backend
process. Research branches take turns through a cancellable gate before
dispatch, so concurrent proposals do not waste a cycle on busy admission.
Waiting proposals emit `python.queued`; cancellation or an expired session
deadline prevents their dispatch. Direct API attempts during an admitted run
are captured as busy without starting a container.
A nonzero process exit is never a successful execution. Failed,
timed-out, output-limited, or unavailable attempts are retained as such.
Artifact collection errors are retained separately as `artifact_error`, without
replacing program stdout/stderr. Such a run is `failed` even if the program
exited zero. UTF-8 display text uses replacement decoding; when a stream is not
valid UTF-8, its exact bytes are also retained as `stdout_base64` or
`stderr_base64`. The execution JSON bound is 384,000 bytes to accommodate JSON
escaping of the bounded source/output. Session and context caps remain in
force; print summaries and save datasets as files instead of flooding output.

The locally built `sigma-research-python:0.1` image is resolved to its local
immutable SHA-256 image ID and run by that ID; it is never pulled by a research
request. The artifact saves both the tag and resolved ID. It runs as UID 65532 with no network, read-only root, a 64 MiB
non-executable `/tmp`, no Linux capabilities, no-new-privileges, a 512 MiB
memory and swap ceiling, one CPU, 64 processes, 15 seconds wall time, 16,000
UTF-8 source bytes, and 32,000 combined stdout/stderr bytes. There are no host
bind mounts or forwarded credentials. The image contains pinned Python 3.12.8,
NumPy 2.2.2, SciPy 1.15.1, pandas 2.2.3, SymPy 1.13.3 and Matplotlib 3.10.0.
Artifact capture has at most five seconds and shares the remaining execution
deadline; it cannot extend a near-deadline program by another capture window.
Runtime inspection, kill/removal and process reaping also have finite timeouts.

Investigator Python is optional and intended for finite, deterministic checks.
The Skeptic must assess both program and result. Executed computation remains
evidence of the finite program run, not a proof of a general claim or Lean
verification. The standalone `sandbox-poc/runtime-check.py` demonstrates the
service on the line-arrangement question: enumerate the insertion recurrence
through 12 lines, compare it to the formula (79 regions), run exact/numeric and
linear-algebra checks, and save a Matplotlib plot for later retrieval.
`sandbox-poc/agent-workflow-check.py` runs that production service through a
fixture-backed Investigator/Skeptic session and retrieves the resulting PNG.

The boundary assumes a trusted host kernel, Docker daemon, and image-build
process. Build-time dependency download requires network access; research
containers have none. Users must rebuild the image after changing the pinned
lock or image definition.

The agent guidance supplies the exact limits, fresh-filesystem semantics and
`/artifacts` path. It asks for discriminating experiments, fixed seeds,
controls, conditioning/tolerance checks, and concrete revised experiments
after failure. The Skeptic must inspect source as well as output: a hardcoded
answer, a small residual, a successful exit, and metadata about a plot do not
establish the claimed result. Numerical contradiction and operational failure
require different follow-up questions.

`sandbox-poc/research-check.py` exercises seven scientific scenarios plus a
three-strategy portfolio (eight workflows, fourteen proposals) with real Docker
and scripted provider responses, including a 100,000-row captured dataset.
`adversarial-check.py`
attacks output/artifact handling, cancellation, concurrent admission, resource
exhaustion, and a real backend SIGKILL with detached-child cleanup. Neither
tests live model judgment. `plan-research-check.py --run` is an explicit bounded
live evaluation that refuses every billing mode except an already connected
ChatGPT plan. It is never invoked by the regression suite.
