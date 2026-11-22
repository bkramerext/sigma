# Red — PR #924 production hotpatch verification

**SIGMA | DEPLOYMENT SUCCEEDED** — 2026-11-22 UTC (2026-11-21 PST).

Production: <https://sigma-research.duckdns.org> on existing `sigma-gce-01`.
Deployed `main` SHA: `cef25725202604ae87ce8113641d4e1d25e17404`, version 0.4.4.
Previous healthy SHA: `20d9cba2271175a00c1ffde03e3854002102f59b`.

The operator explicitly authorized merging and deploying PR #924 through final
production verification. PR #924 was open; all five workflows passed on its
exact head `420fca270a187747b66e739644abb730bb70e806`. Red reviewed the three-file
patch and merged with that expected-head guard. The resulting immutable merge
SHA above is the deployed build. It includes the previously merged publication
page and the requested 404, download-spacing and browser-regression corrections.

All merged-SHA workflows passed before deployment:

- [Ruff lint and format](https://github.com/bkramerext/sigma/actions/runs/44991526457)
- [Frontend build](https://github.com/bkramerext/sigma/actions/runs/44991526526)
- [SIGMA verification](https://github.com/bkramerext/sigma/actions/runs/44991526469): eight test shards and two-creator real PDF acceptance.
- [Browser verification](https://github.com/bkramerext/sigma/actions/runs/44991526474): all three shards and the aggregate gate, including the corrected hosted-sponsored regression.

## Backup, compatibility and deployment

Used the established keyless IAP/OS Login path impersonating the host-only
release SSH service account. No Owner deployment, IAM changes, resources,
configuration redesign, schema migrations or paid inference were performed.

Before cutover, the service, backend/frontend/Personal containers and host Caddy
were healthy. The existing state disk was mounted at `/srv/sigma-state`; boot
and state disks had 53 GB and 28 GB free respectively. Five ledger rows marked
running were historical auxiliary records from November 5, predating the
running backend; all research rows were paused or terminal. These were retained.

Under maintenance, stopped SIGMA and all its writer containers, synced, copied
the entire state tree with ownership/metadata preserved to the separate existing
boot disk, and checked it using `rsync -aHAXnci --delete`: zero differences.
Backup parent is root-owned mode 0700:

`/var/backups/sigma-state-hotpatch-pr924-20261122T055827Z/state`

The complete backup retains all 15 zero-byte provider-slot lock files. As in
the established procedure, only a separate verifier view omits that lock-only
directory. The existing read-only verifier passed all three SQLite integrity
checks, identity/workspace mappings, projects, assets, saved paper hashes and
accounting checks. Normal service was restored immediately after the copy.

Inspected the entire deployed-to-candidate diff. Existing storage, project,
paper, authentication, workspace and research-accounting implementations,
dependencies and deployment files are unchanged; the already-merged Lean
Explorer additions do not migrate those stores. No migration was invoked.

Executed successfully, with both flags supported by the checks above:

```sh
sudo python3 /opt/sigma/current/deploy/deploy-gce-release.py cef25725202604ae87ce8113641d4e1d25e17404 --backup-verified --schema-compatible
```

The guarded helper reported passing container health, release identity and
state mount checks. Its rollback procedure was retained; no rollback was needed.

## Production acceptance

Real Chrome, fresh anonymous context, desktop 1440×1000 and mobile 390×844:

- **MET:** `/papers/unpacking-alpoge` returns 200 and displays the publication without sign-in.
- **MET:** Both actual manuscript links return 200 and contain valid PDF/TeX content. PDF: 953,997 bytes; TeX: 278,823 bytes. Full hashes are in the linked results.
- **MET:** Heading bottom margin is 7px, downloads top margin is 0px, and measured vertical gap is 7px at both widths.
- **MET:** An invalid URL displays “Page not found,” no public header/logo/image element, and the original full-page copper background.
- **MET:** Return Home navigates to `/` at both widths. The normal first-visit welcome dialog was dismissed through “Let's get started”; the initial automation attempt timed out because that dialog intercepted the click. The corrected check passed without bypassing interactions or changing application code.
- **MET:** Backend, frontend and Personal containers healthy; `sigma`, private broker and Caddy services active; backend deployment readiness passed; maintenance OFF; protected release pin and running image labels match the deployed SHA.
- **MET:** The existing edge is host Caddy with `SIGMA_HOST_DIRECT=true`. Docker edge is intentionally scaled to zero by the established configuration, not an unhealthy or missing required container. No routing configuration was changed.
- **MET:** All schemas and every table row in the authentication, workspace mapping and research accounting databases match the backup. All 285 existing workspace file hashes are unchanged. Post-deploy verifier again passed: 3 identities/workspaces, 24 projects, 74 assets, one matching saved TeX/PDF pair and 124 accounting rows.
- **MET:** Public authentication status is enabled/ready; anonymous protected API returns 401; Google login-start returns 302 to `accounts.google.com`.
- **UNVERIFIED:** A fresh authenticated Google callback/account session was not exercised. Existing authentication records are unchanged, and no research or paper generation was initiated in production.

Browser evidence: [measured results](artifacts/pr924-production/results.json),
[desktop publication](artifacts/pr924-production/publication-1440.jpg),
[mobile publication](artifacts/pr924-production/publication-390.jpg),
[desktop 404](artifacts/pr924-production/not-found-1440.jpg),
[mobile 404](artifacts/pr924-production/not-found-390.jpg).

## Local verification details

Ran the full `./sigma test` on the exact deployed SHA. It finished with two
failed steps (`tests/project_collaboration.py`, four cases; `tests/research_qa.py`)
caused by the macOS noncanonical temporary-directory path. Both passed when
rerun with `TMPDIR=/private/tmp`; collaboration ran all 49 cases. The full run
skipped the offline-pairs script and frontend build after those failures; both
were then run explicitly and passed (72 synthetic records / 36 pairs, zero
model calls; successful frontend build). All other full-run steps passed.

Both Ruff commands passed using the repository's complete CI scope:
`src tests sigma deploy browser_checks scripts docs/evaluations`.
An additional unscoped root lint/format invocation reported pre-existing
findings in directories outside that CI scope; no unrelated source was changed.
Exact-SHA Linux CI passed independently. This handoff does not claim the initial
macOS `./sigma test` invocation returned zero.

The verified boot-disk backup remains available for the established guarded
rollback procedure. This evidence commit does not alter the deployed SHA.
