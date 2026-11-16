# SIGMA low-memory Personal ChatGPT: greenfield shared-container POC

**Status: incomplete / draft. Do not merge or deploy.** No legacy data migration.

## Target

* One shared Personal ChatGPT Docker container, with one credential/model service
  for every SIGMA user. Do not create a Docker project or pair of containers
  per user.
* Per-user AEAD-encrypted credentials in one private, persistent store.
  Use independently authenticated SIGMA workspace IDs as associated data.
  The 32-byte encryption key is delivered via a protected file **outside**
  the data volume; never in the image, browser profile, request, or logs.
* A single Chromium sign-in at a time, **on demand only**, with ephemeral
  browser profile, separate sandboxed browser UID, and immediate shutdown
  after success/cancel/timeout. No idle browser process during research.
* The trusted SIGMA backend derives the workspace from verified Google
  identity and talks to the service over authenticated local IPC.
  Every account lookup, refresh, inference, and disconnect is user-scoped;
  no account IDs or paths chosen by clients. Never fall back to Sponsored.
* User-facing ChatGPT pill/dialog, real account chooser, all model request
  paths (research, papers, markdown, Q/A, brainstorm), Stop/Resume and
  disconnect behave exactly as before.
* Keep research Python/Sage containers temporary and isolated. Host Caddy
  ultimately routes directly to backend/frontend; eliminate Docker edge.

## Already implemented on this branch

The new `auth-poc/shared_vault.py` provides workspace-bound AES-GCM
encryption, private file/owner checks, atomic writes, and tamper rejection.
`tests/shared_personal_vault.py` exercises two-user isolation, ciphertext
swapping, corruption, symlinks and key permissions. The Docker CI workflow
runs the tests inside the existing Python worker image, which already has
the cryptography dependency.

The vault is not yet connected to a shared service, and **the existing
experimental worker/browser Compose layout still runs**. Do not call this
an implemented one-container system until integration and acceptance pass.

## Security and acceptance gates

Encryption at rest does not prevent a compromised shared decrypting service
from accessing multiple accounts. We accept a simpler POC boundary only
with (a) strict authenticated request scoping, (b) browser process isolation
from vault keys and tokens, (c) no public credential/browser ports,
(d) maximum one sign-in browser, (e) explicit memory limits and measured
real idle/peak RSS, and (f) two-user adversarial checks.

No production credentials exist in this experimental container topology,
so there is **nothing to migrate**. Do not write migration tooling or
compatibility shims for the previous per-user container experiment.

Keep this PR in draft until the shared container is actually wired into
`./sigma start --prod` and hosted deployment config, actual account chooser
and inference pass, all application request paths are audited, and rollback
is tested. Hosted plan-usage authorization must be independently verified.
