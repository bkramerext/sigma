# SageMath research execution (T26)

SageMath is an optional computation runtime alongside scientific Python. It is
not a proof checker. The [T26 ticket](../tickets/t26.md) defines the contract.

## Setup and use

Install/start Docker, then explicitly build the desired runtime:

```sh
./sigma sandbox-build --runtime sagemath
./sigma sandbox-capabilities
./sigma sandbox-execute /path/to/project --runtime sagemath --source-file experiment.sage
```

Ordinary `./sigma setup` and `./sigma test` do not download/build Sage. The
Sage image is based on the official 10.8 Linux amd64 image pinned by digest in
`sandbox-poc/Dockerfile.sage`; arm64 hosts require Docker's amd64 emulation.
This was tested on an arm64 host; cold Sage startup was approximately 20–24
seconds under emulation. A native arm64 Sage image is not supplied in T26.
Both builds use the shared bounded container runner; no packages or images are
installed/pulled during research execution.

The CLI prints the persisted execution JSON; a non-completed execution returns
exit status 1. The existing API endpoint
`POST /api/projects/research-executions` accepts `runtime: "sagemath"` with
`source`, `path`, and optional session/strategy/cycle/step provenance. Omitting
`runtime` retains Python behavior. `GET /api/research-tools` returns observed
local runtime capabilities. Image availability is an observation, not a promise
that a later container launch cannot fail.

## Agent contract

Every Investigator and Skeptic request receives explicit coordinator guidance
and an `execution_tools` snapshot with availability, request/result fields,
capabilities, limits, immutable local image ID when present, and setup guidance.
The snapshot is saved on the role step. Cost reservation uses the same request
instructions/schema/context as dispatch. Availability inspection runs off the
async event loop and never starts research programs or pulls images.

The Investigator sets either `sage_code` or `python_code`, with the other null,
or both null. Sage programs use native `.sage` preparsing, including `R.<x>`
and `^` exponentiation. Both fields cannot contain programs. The coordinator
runs the saved proposal before the Skeptic and attaches `sage_execution` or
`python_execution`. The Skeptic cannot dispatch code: it requests a concrete
follow-up experiment through the next Investigator cycle. Installed Sage
facilities may use bundled helper processes; all remain inside the same limits.
Legacy sessions without the branch-aware computation dispatcher receive
explicit unavailable guidance and cannot silently ignore a code proposal.

## Isolation and cancellation

Both runtimes have no network or host/project/credential mounts, a non-root UID,
read-only root filesystem, dropped capabilities, no-new-privileges, one CPU,
64-process limit, 16,000 source bytes (agent proposals additionally 4,000
characters), 32,000 combined stdout/stderr bytes, and up to eight flat regular
artifact files totaling 4 MB. Source is supplied through a fixed stdin protocol,
never interpolated into a shell command. Symlinks and oversized captures fail.

Python retains its 15-second / 512 MiB / 64 MiB temporary-space limits. Sage has
a 60-second total host execution bound, 1 GiB memory with no additional swap,
and 128 MiB temporary space. Both have a separate 16 MiB artifact tmpfs. Sage's
larger, explicit limits accommodate its startup; they do not change Python's
limits. The host watchdog includes startup, and the in-container watchdog
bounds the workload if the host client disappears.

One admission gate is shared by both runtimes per backend process. The research
coordinator also shares one computation queue across strategies. The existing
one-active-research-session policy is preserved. Separate backend processes are
not a host-wide resource scheduler. Docker's daemon/kernel and the pinned image
remain trusted parts of the isolation boundary.

Queued work is not dispatched after stop/cancellation. A dispatched computation
continues only within its hard bound; stop waits for cleanup and preserves its
actual terminal result before preventing further role calls. A stopped session
may therefore retain a completed computation. It does not falsely relabel it
cancelled. On resume, the saved result is reused without another execution.
Backend loss leaves interrupted/uncertain evidence; it does not prove the
program never ran or trigger an automatic rerun. A pending final-cycle review
may finish after resume without authorizing an additional research cycle.

## Evidence, recovery and metrics

New execution records retain explicit runtime/version/syntax, source and its
SHA-256, image ID, limits, status, exit code, exact bounded stdout/stderr, captured
file sizes/hashes, and project/session/strategy/cycle. Sage agent executions also
validate and retain the originating Investigator step, role and saved model/
thinking configuration. Standalone manual executions have no invented agent.
Historical records without a runtime continue to mean Python and are not
rewritten. Finalization binds the result to its reservation and provenance.

Recovery and failure reuse distinguish runtimes. An identical source string in
Python cannot retrieve a Sage result. An unchanged failed source within a
session reuses its recorded failure; a revised experiment can run in the next
cycle. Original source/runtime/cycle/step provenance stays with reused evidence.
Cross-cycle Sage failure reuse also requires matching version, syntax and image
profile. The original cycle's uncertain reservation is preserved even after an
upgrade so a restart cannot duplicate it. Runtime versions are pinned in this
implementation; upgrading the image/runtime is a deliberate deployment change,
not a runtime fallback or automatic retry.

The full result reaches the Skeptic and session evidence. Bounded, explicitly
truncated previews reach peer and subsequent-session context. JSON audit and
paper-source exports preserve the full saved evidence. Metrics keep Python and
Sage run statuses separate, combine captured-file storage once per execution/
file identity, and retain all execution IDs in T24's source inventory. Text and
HTML reports preserve both independent metric groups even with unequal lengths.
Existing Outcome evidence cards expose Sage status, IDs, hashes and a disclosure
for exact source/results without changing T25's hierarchy. Captured binary files
are inspectable through the existing execution artifact API; agents receive
metadata, not image pixels or complete captured file contents.

## Verification

```sh
./sigma test
uv run python sandbox-poc/runtime-check.py
uv run python sandbox-poc/sage-check.py
```

The last two commands require explicitly built images. The Sage check exercises
native syntax, exact algebra, number theory, a counterexample to a proposed
primality certificate, an independently enumerated elliptic-curve point count,
PNG/JSON capture/retrieval, boundary controls, network denial, exceptions, unsafe
artifacts, output/memory limits, timeout and bounded-completion cancellation.
`browser_checks/sage_fixture.py` provides mock provider roles with real Sage;
`browser_checks/sage_execution.py` checks the resulting session/evidence,
metrics, exports and desktop/320px presentation in real Chrome. No live model
calls are made; deterministic agent fixtures do not establish model quality.
