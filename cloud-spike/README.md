# T22.1 Cloudflare feasibility spike

Continuation of [PR #21](https://github.com/bkramerext/sigma/pull/21), based on
its existing commit `ad06168`. The earlier requirements are retained in
[the ticket](../tickets/t22.1.md). This directory is disposable infrastructure
evidence, separate from SIGMA's local application and research data. Nothing
here is a public research service or a replacement for T22 acceptance.

## Result and bounded architecture choice

**The local compatibility checks pass. A Cloudflare-only scientific execution
service has not passed the isolation gate and must not run generated code.**
Use the ticket's conventional sandbox-host fallback for scientific execution.
For the first three-user implementation, recommend the smaller hybrid: a
Cloudflare Worker/frontend in front of one conventional Linux FastAPI host,
with a durable volume, SQLite authorization/job ledger and isolated Docker
compute. Reuse the typed Python services and existing project packages behind
explicit workspace ownership adapters. This avoids both a D1-to-Python storage
bridge and a second trusted application runtime while isolation is unresolved.
Cloudflare-hosted trusted FastAPI plus D1/R2 remains a viable candidate if later
remote checks justify that extra adapter work. These are recommendations,
not a deployed architecture or a completed T22 migration.

| PR #21 gate | Evidence on 2026-10-23 | Remaining gate |
|---|---|---|
| 1. Worker → FastAPI | Pinned amd64 image builds; Wrangler local Container routing, incremental SSE, three concurrent clients and real Chrome EventSource pass; deploy dry run passes | No remote deployment; real edge TLS, startup, disconnect and rollout behavior unverified |
| 2. Sage sizing | Existing digest-pinned SageMath 10.8 image; exact rational matrix determinant, polynomial factorization and integer factorization pass in three fresh local containers | Real Cloudflare image admission, memory and startup unmeasured |
| 3. Scientific isolation | Local Docker non-root, empty capabilities, no-new-privileges, read-only root, absent credential env/socket, blocked network and bounded tmpfs pass | Cloudflare isolation **not accepted**; use conventional sandbox-host fallback |
| 4. Recoverable jobs | Local D1/R2 restart retains queued work and committed results; expired dispatched attempts become `uncertain`, stay charged and cannot be reclaimed; stale completion rejected | No production scheduler, provider transport, heartbeat, cancellation or research-engine integration |
| 5. Atomic claims | Real Miniflare D1 bindings: concurrent CAS writes, idempotent enqueue, one dispatch, completion races, batch rollback, per-user/global budgets and concurrency pass | Repeat on remote D1; call units here are not dollar/token/time limits |
| 6. Hosted model access | Official API and SIWC hosting constraints checked; Google identity cannot authorize model inference | No live sign-in, credential transfer, entitlement or inference test; hosted model access remains unverified |

## Runtime and security findings

The trusted FastAPI probe has only `/health` and `/events`. The Worker accepts
only GET for those paths, selects one fixed container identity and forwards no
browser cookies, credentials or identity headers. Its container has internet
disabled. No SIGMA project/auth path is exposed, and no generated source is
executed by that image. The container build uses the repository's locked Python
dependencies with hashes. `requirements.txt` is an export of `uv.lock`, not a
new dependency selection.

Cloudflare currently documents `linux/amd64` images, ephemeral disks, possible
container interruption, and separate Worker/Container lifecycles. A long-lived
process or `waitUntil` is not a durable job record. R2 FUSE is not evidence of
POSIX advisory-lock/atomic-publication compatibility with existing packages.
See [getting started](https://developers.cloudflare.com/containers/get-started/)
and [lifecycle FAQ](https://developers.cloudflare.com/containers/faq/).

The important isolation difference is explicit in Cloudflare's
[local development documentation](https://developers.cloudflare.com/containers/guides/local-dev/):
under the `durable_object` scheduling policy, deployed processes retain
root-equivalent Linux capabilities even when run as another user. That
invalidates treating this Docker smoke test as proof of that policy's
isolation; it also does not establish the legacy/default policy's boundary.
Cloudflare now documents Docker-in-Docker support in its
[FAQ](https://developers.cloudflare.com/containers/faq/); claiming it is simply
unsupported would also be wrong. It still requires testing the actual nested
sandbox, network denial, resource controls and hostile workloads remotely.
[Egress controls](https://developers.cloudflare.com/containers/configuration/outbound-traffic/)
provide a useful platform deny policy, but do not establish the full execution
boundary. No network-enabled fallback or shared credential-bearing compute
container is acceptable.

The recommended conventional host retains T19's trusted host/daemon boundary.
Only a trusted runner may access Docker; generated code gets no host/project
mounts, tokens, daemon socket or network. Separate containers per execution,
deadline/cancellation enforcement, aggregate resource admission and hostile
cross-user tests are still required. This is not a claim of VM-grade isolation.
T26 owns production Sage integration and agent tool discovery.

## Scientific measurements

[Raw measurements](evidence/sage-local.json) record the immutable image identity,
three local fresh-container runs and limits. The existing image reports
1,469,325,553 bytes through `docker image inspect`; that is the engine's reported
size, not a verified registry transfer size or Cloudflare disk requirement.
Peak **process RSS** was 422,512–422,976 KiB (about 413 MiB), not total cgroup
memory. End-to-end Docker start + Sage import + checks + shutdown took
23.464, 23.371 and 33.652 seconds on an ARM Docker host using amd64 emulation.
These are not native-cloud cold starts or mathematical proofs. Each run used
1 CPU, 1 GiB memory, 128 processes, 128 MiB `/tmp` and 16 MiB `/work`.
The image's existing non-root UID 1000 is necessary because `/home/sage` is not
traversable by arbitrary UID 65532; no filesystem permissions were weakened.

## D1/R2 and recovery contract

`store.ts` is an internal experimental adapter with real local D1 and R2
bindings, not an exposed HTTP API. Test owner strings stand in for **already
verified** sessions; the test does not prove Google authentication or tenant
isolation for the existing application. Its disposable schema contains
`budgets`, owner-scoped `jobs`, and revisioned `projects`.

One conditional job update and a SQL trigger atomically charge global/user
budgets and reserve concurrency. `RETURNING` identifies the winning job;
D1 `meta.changes` includes trigger effects and must not be compared with one.
This replaces a check-then-write race. D1
[batch transactions](https://developers.cloudflare.com/d1/worker-api/d1-database/)
roll back all statements on error; a zero-row CAS is not itself a SQL error.
Separate operations must explicitly interpret that result.

Dispatch intent is committed **before** any provider I/O. On expired lease,
`dispatched → uncertain` preserves its consumed unit. A job cannot automatically
return to queued; even a crash just before sending is treated conservatively.
An operator/user may authorize a new attempt under a new key and budget after
seeing the ambiguity. The spike does not claim exactly-once external inference.
Queued cancellation prevents dispatch. Stopping already dispatched work requires
a real transport cancellation and reconciliation policy; it is not implemented
here. Active slots expire on recovery rather than on a browser Stop click.

R2 bytes publish first under a unique immutable key, then D1 conditionally
commits their digest/pointer. Concurrent completion publishes one checkpoint;
unreferenced bytes are harmless orphans. Only a committed, owner-authorized
pointer can be read. Missing or corrupt committed bytes fail closed. There is
no cross-service transaction and no claim that an uncheckpointed response was
recovered. Production garbage collection must respect live references and a
conservative grace period.

The fixture recreates Miniflare over the same temporary D1/R2 storage and
verifies surviving records. This is a process-runtime restart test, **not** a
remote backup/restore or deployment recovery exercise. The recommended hybrid
must keep its ledger and project packages on durable storage, checkpoint call
attempts/results, and perform consistent, encrypted off-host backups with a
manifest of artifact digests. Restore into an isolated host, verify identities,
history and ownership, disable inference, mark in-flight attempts uncertain,
then reopen access. That operational exercise remains a T22 acceptance gate.

## Model authorization, independently of website identity

Google OIDC answers who may enter a SIGMA workspace. It supplies no model
credential or billing authorization. Verify issuer, audience, signature,
expiration, nonce and verified email; enforce ACLs on the server before any
model dispatch. A browser identity header is not evidence of any of these.

Official [OpenAI API authentication](https://developers.openai.com/api/reference/overview)
documents server-held API keys or workload federation access tokens.
The initial supported cloud inference choice should be **explicitly configured
API billing**, with server-only credentials and independently enforced bounded
reservations. An unconfigured deployment must deny inference. There is no
automatic fallback from a plan selection to API billing and no copied developer
key in this spike.

Official [SIWC plan usage](https://developers.openai.com/siwc/token-sharing-open-source)
distinguishes open-source/local use from remotely hosted applications, directing
remote-app providers to its interest process. Its
[self-hosted VM instructions](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms)
describe the same user's selected registration, protected transfer, stable host
identity and refresh ownership. They do not establish a generic multi-user
hosted service entitlement. A loopback callback reaches the browser's machine,
not the hosted server. Keep hosted plan mode unavailable until the deployment's
supported registration, permitted use and per-user credential lifecycle are
verified. The existing local SIWC implementation remains in place.

## Reproduction without a cloud account

Prerequisites: existing SIGMA setup, Node 22+, Docker with the **Buildx CLI
plugin installed and discoverable**, and installed Chrome. No Cloudflare login
or model credentials are needed. Wrangler's local toolchain downloads images
at build/setup time; execution uses no model or paid platform calls.

```sh
npm --prefix cloud-spike ci --ignore-scripts --no-audit --no-fund
npm --prefix cloud-spike test
npm --prefix cloud-spike run typecheck
WRANGLER_SEND_METRICS=false npm --prefix cloud-spike run bundle
WRANGLER_SEND_METRICS=false npm --prefix cloud-spike run dev
```

In another terminal:

```sh
uv run --with playwright python cloud-spike/http_probe.py
```

Sage sizing is optional and never pulls an image during execution. First obtain
the exact public digest named in `sage_probe.py` as an explicit setup action,
then run `uv run python cloud-spike/sage_probe.py`. It downloads no Sage runtime
as part of `./sigma test`. This does not replace T26's full hostile-code suite.

No cloud resources are configured by these commands. An eventual remote probe
requires a Cloudflare account, Workers Paid billing, a least-privilege deployment
token, a workers.dev URL and explicit resource IDs for any D1/R2 bindings.
There are no real IDs, secrets or public artifact buckets in this directory.
Do not expose the current localhost-only `sigma.api` on a public host.

## Costs, remote verification and next integration

Verified 2026-10-23 against [Containers pricing](https://developers.cloudflare.com/containers/platform/pricing/):
Containers require Workers Paid ($5/month base); container CPU, provisioned
memory/disk, egress, Workers and Durable Objects add usage charges. D1/R2 and
any conventional Linux host/backups add their own charges. This is not a total
estimate. Inference billing is separate. Three users is a sizing target, not a
spend cap. Instance limits alone do not cap runtime charges; set application
call/time/token/dollar ceilings, concurrency, job deadlines and idle shutdown.
Monitor platform usage and provide an inference kill switch. No paid resource
was provisioned for this spike.

The remote gates are deliberately left open: deploy the trusted probe; measure
native cold starts and image admission against current
[instance limits](https://developers.cloudflare.com/containers/platform/limits/);
exercise actual restart/rollout/stream disconnect; repeat D1 races; then either
establish the full hostile scientific boundary or retain the hybrid. A public
Demo, Google login/ACLs, private workspaces, revocation, budget enforcement,
backup restoration and the complete happy path remain T22 implementation work.

PR #21's running-session pill remains an integration requirement: on Home and
Project, place it immediately left of the existing header pills. Its count must
come from authorized server-persisted session state, across navigation and
restart; guests see no private run counts. Loading/offline must not imply zero,
and uncertain/stopped work must not be advertised as running. This spike adds
no disconnected counter or speculative UI. Verify its eventual desktop/mobile
layout and access controls with the complete hosted workflow.
