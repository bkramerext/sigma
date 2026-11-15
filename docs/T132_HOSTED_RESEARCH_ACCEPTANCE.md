# T132 hosted research and execution acceptance

**State:** Offline preparation. This procedure does not authorize provider calls,
production changes, or a hosted test. Local deterministic checks are not hosted
acceptance. Use this with the identity and privacy matrix in
[T134](T134_HOSTED_ACCEPTANCE.md); do not repeat that matrix here.

## Offline checks

Run from the reviewed checkout before the hosted window:

```sh
./sigma test
uv run --locked --no-sync python tests/cloud_research_api.py
uv run --locked --no-sync python tests/cloud_research_sponsored_api.py
uv run --locked --no-sync python tests/python_sandbox.py
uv run --locked --no-sync python tests/sage_execution.py
uv run --locked --no-sync python tests/computational_evidence.py
```

The API scenarios use fake provider transports and authenticated test
principals. They cover hosted proposal, agentic proposal, conversion, paper and
session workflows; sponsor selection; spend/token/queue admission; uncertain
provider outcomes without replay; cross-workspace denial; and saved evidence.
The sandbox scenarios cover Python/Sage settings, resource constraints,
timeouts, errors, artifacts, and execution recovery. These are deterministic
integration/regression checks, not evidence from Google OAuth, a hosted
browser, the production filesystem, or a rootless daemon.

## Target-host sandbox proof

Run only after an operator has approved the host verification window and the
T129 deployment is available. From `/opt/sigma/current`, first verify the
actual mounted state disk and production preflight using the
[operation runbook](OPERATION_RUNBOOK.md). Then run the proof through the
backend's configured socket, without a development override:

```sh
sudo findmnt /srv/sigma-state
sudo /usr/local/libexec/sigma/gce_preflight.py --json
sudo -u sigma-sandbox env DOCKER_HOST=unix:///run/user/$(id -u sigma-sandbox)/docker.sock docker info --format '{{json .SecurityOptions}}'
docker compose --project-name sigma --env-file /etc/sigma/deploy.env \
  -f deploy/compose.yaml -f deploy/compose.gce.yaml \
  exec -T backend python -m sigma.cloud_runtime_check
```

Do not add `--allow-nonrootless-dev`. A nonzero exit, daemon security options
without rootless mode, missing image, or failed isolation assertion is a
failure/blocker; do not bypass it. The smoke creates a temporary project under
backend `/tmp`, runs Python and Sage, checks that each cannot read the state
mount or a host sentinel, connect to the network, or access the sandbox
daemon's socket, verifies artifact and execution-record round trips, compiles
a deterministic TeX fixture, and verifies paper snapshot/PDF persistence. It
does not test the GCE kernel against a determined container escape; that
requires a separate security review.

## Hosted workflow window

Prerequisites: T127/T129/T131 deployment readiness; a recorded release SHA and
healthy preflight; current recoverable backup; approved desktop test origin;
two owner-authorized disposable Google identities; and a separately approved
provider-call window with a named usage ceiling. The request for T132 does not
authorize any live provider call. Without that separate authorization, run
only the offline checks and target-host sandbox proof, and mark paid workflow
rows **BLOCKED** or **UNVERIFIED**.

Use isolated desktop browser profiles. Do not paste tokens, cookies, identity
emails, project text, or raw provider responses into retained evidence. For
each workflow, use a fresh disposable project and record its redacted ID and
the displayed owner usage counters before and after. Trigger each explicitly
approved operation once. If the browser disconnects or a request times out,
stop and inspect the saved session/attempt and usage state; never click retry
until the provider outcome is known. Unknown outcomes stay reserved and are
reported as unknown.

| Workflow | Action and required evidence |
| --- | --- |
| Sponsored proposal | Generate once for the owner project. Confirm the proposal remains an explicit unsaved candidate until accepted, and record the saved project revision plus owner usage delta. |
| Agentic generation | Start one bounded explore/review run. Confirm terminal completion or an explicit failure, per-call accounting, durable run evidence, and no implicit proposal acceptance. |
| Text conversion | Convert a disposable saved project view once. Confirm source digest/revision binding, current result, and no mutation of the underlying research record. |
| Research session | Start one bounded session. Confirm owner-visible progress, call/cost limits, computational tool availability, terminal Outcome/provisional status, and durable events, checkpoints, calls, executions, and artifact references. |
| Python and Sage | Submit deterministic finite computations through the hosted feature. Confirm runtime/version, source hash, bounded status, output, captured artifact bytes/hash, and owner-scoped execution retrieval. The separate target-host proof above is required to claim daemon isolation. |
| Paper generation | Only if explicitly included in the provider approval: create one bounded paper and verify saved TeX, evidence snapshot hash, and PDF hash. Otherwise use an existing fixture paper or record this row as blocked. |
| Persistence | Reload the browser and reopen the same owner project/session/artifacts. A backend restart or recovery check requires a separately approved maintenance window; verify the same IDs/hashes and accounting afterward. |
| Isolation | Apply T134's second-identity direct-reference matrix to the disposable project, session, execution, artifact, and paper IDs. Denied reads/writes must reveal no content and leave owner state and usage unchanged. |

## Evidence record

Retain only sanitized output. For the target-host smoke preserve its JSON
result, including release SHA, daemon rootless observation, Python/Sage image
IDs, redacted execution IDs, isolation observations, artifact names, and PDF
hash. For the hosted workflow record:

```text
Ticket: T132
Outcome: MET / UNMET / BLOCKED / UNVERIFIED
Origin; host identifier (redacted); deployed release SHA:
UTC start/end; elapsed; operator/tester; approved window reference:
Backup ID/time and preflight/health result:
Browser/version and redacted identity labels/roles:
Offline command results and checkout SHA:
Rootless daemon proof command/result and image IDs:
Workflow rows and status; redacted project/session/execution/paper IDs:
Owner usage before/after; global usage reconciliation; authorized ceiling:
Saved artifact/TeX/PDF hashes and persistence result:
Unknown/failing attempts and confirmation that none were retried:
Sanitized evidence links; deviations; remaining owner actions/dependencies:
```

Never claim hosted acceptance from a local fixture, development daemon, mocked
provider, or the existence of a deployment package. Brian/coordinator review
must confirm the actual host/release and evidence; do not self-merge or treat
this checklist as launch approval.
