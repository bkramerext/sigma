# Red R4R — SIGMA v0.1.5 release preparation

**Ticket:** [#337](https://github.com/bkramerext/sigma/issues/337)

**Branch:** `red/v0.1.5-release` from `main` at
`5d1a4f51c4a2cd33b0854a19564d37bebac15b3d` (#330 merge)

**Candidate release commit:**
`2026f1e5b167ec76289ba2335d369603e4f377ee`

**Production observed:** v0.1.4 configured and running at
`6fa626bdfc1f07cb873103dfed2323864d4fb280`

**State:** Stage A R4R; Stage B not authorized or performed; do not self-merge.

The release candidate SHA above is the version-bump commit. The final PR head
adds this handoff record only; use the candidate SHA above as the exact
deployment build input after review/merge and Stage B authorization.

## Change

Aligned `pyproject.toml`, `uv.lock`, frontend `package.json`, and both npm lock
version fields to 0.1.5. Updated versioning guidance, production inventory,
status, and this handoff. No v0.1.5 tag was created. PR #330's source SHA is the
branch baseline, not the release commit.

## Production compatibility and recovery

Read-only GCE inspection on 2026-10-29 confirmed the running VM, active service,
mounted state disk UUID and restrictive mount, root-owned mode-0600 deploy env,
configured release SHA, healthy backend/frontend image labels, and passing
public endpoint probe. The live source is `6fa626b…`, not the prior docs'
`2761c0e…`; reconcile this provenance discrepancy before cutover. The READY
30 GB snapshot `sigma-state-v014-20261029-0606` is sourced from `sigma-state`,
but predates v0.1.4 and has not been restore-tested. The daily backup timer and
success marker are absent. A fresh consistent snapshot and isolated restore
verification are required before cutover; neither was created here.

Compatibility review: no destructive state migration was found in #330, and
no auth/workspace SQLite schema change is introduced between live SHA `6fa626b…`
and the candidate. Existing project schema versions remain readable. The
candidate may write project schema 10 when inference provenance is saved; the
deployed binary only accepts earlier versions, so code rollback is not
generally safe after that write. Production project/paper/checkpoint/ledger
contents were not inspected, and older-binary compatibility for newly generated
paper bundles remains unverified. Do not assert schema-compatible rollback
until the operator and coordinator resolve these limits.

## Verification

- `./sigma test` — PASS after locked frontend dependencies were installed.
  Ruff, formatting (310 files), Pyright (0 diagnostics), frontend typecheck and
  production build passed; optional graph-present sandbox scenario skipped
  because its local image is unavailable.
- `uv build --out-dir /tmp/sigma-v015-dist` — PASS; built 0.1.5 wheel and sdist.
- Release image source/label and deployment automation tests — PASS as part of
  the full suite. Actual backend/frontend Docker image build — UNVERIFIED because
  the local Docker daemon is unavailable.
- Public endpoint verifier — PASS in read-only mode against the live endpoint.
- Browser checks used an isolated fixture backend and temporary Vite instance;
  no paid provider call was made. Existing issue #329/#328 checks failed stale
  progress-label assertions after fast synthesis/PDF generation proceeded. Do
  not treat browser acceptance as passed; update checks or provide current
  browser evidence before release approval.
- No tests targeted the human's local SIGMA server. No production state was
  changed.

## Exact-SHA procedure prepared for Stage B

Only after PR review/merge and separate operator go/no-go, verify the full
candidate SHA, exact deployed SHA, current state-disk mount and a recent
restore-verified recovery point; announce maintenance. Stage B is blocked until
the snapshot and rollback compatibility gaps above are resolved. Then, from the
reviewed candidate checkout staged at `/opt/sigma/current`, run the runbook's
guarded upgrade:

```sh
sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py CANDIDATE_FULL_40_CHAR_SHA \
  --backup-verified --schema-compatible
```

The helper exports and builds images from the exact SHA, verifies source labels,
preflights the host, changes only the protected release pin, restarts through
systemd, and checks backend/frontend health plus running edge. Afterward verify
image/release records, public HTTPS/API, auth gates, workspace isolation, saved
projects/research/papers, and spending obligations per the runbook. No provider
inference is authorized.

If verified schema compatibility and backup assertions still hold, guarded
code rollback to the observed previous release is:

```sh
sudo /opt/sigma/current/deploy/rollback-gce-release.sh \
  6fa626bdfc1f07cb873103dfed2323864d4fb280 \
  --backup-verified --schema-compatible
```

The old backend/frontend tags were observed present on the host, but this does
not establish rollback safety for state written by the candidate. The helper
does not rewind project files, SQLite state, papers, or charges. If data/schema
compatibility is unknown, stop; use the separately authorized restore process
and declare the data-loss interval rather than claiming code rollback is safe.

## Disposition requested

Independent review of the version bump, production-state discrepancy, recovery
gate, and rollback limits. Stage B is deliberately not included in this R4R.
