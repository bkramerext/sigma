# RED R4R — SIGMA v0.1.5 host-preflight runbook correction

**Ticket:** [#337](https://github.com/bkramerext/sigma/issues/337)

**Branch:** `red/v015-stageb-ops-readiness`

**Base:** merged Stage B readiness PR #339 at
`eeab3eb4416c8a7a0110f42ff4352a394439c3e4`.

**Scope:** document the required `--repository /opt/sigma/current` argument
for the installed GCE preflight, record the read-only host result, and
distinguish the active v0.1.4 host preflight from an unperformed v0.1.5 image
build. No production deployment or snapshot is requested.

## Evidence

- Read-only GCE inventory confirmed `sigma-gce-01` RUNNING, state disk READY
  and attached, and snapshot `sigma-state-v014-20261029-0606` READY with source
  `sigma-state`.
- Read-only SSH confirmed checkout and protected `SIGMA_RELEASE` are
  `6fa626bdfc1f07cb873103dfed2323864d4fb280`, `sigma.service` is active, the
  state disk is mounted, and backend/frontend image revision labels match.
- The backup timer is inactive and `/etc/sigma/backup.env` is absent. The
  existing snapshot predates v0.1.4 and remains unverified by restore.
- Running the installed preflight without `--repository` produced one Compose
  configuration failure because the installed checker is copied to
  `/usr/local/libexec/sigma/` and cannot infer `/opt/sigma/current`.
- Re-running the preflight with
  `--repository /opt/sigma/current` returned **23/23 PASS**. This is read-only
  and validates the current v0.1.4 host only.

## Release gates

| Gate | Result | Evidence / condition |
| --- | --- | --- |
| Installed preflight command documented correctly | **MET** | Runbook includes `--repository /opt/sigma/current`. |
| Active v0.1.4 target-host preflight | **MET** | 23/23 checks passed with the explicit repository argument. |
| Candidate v0.1.5 target-host Docker build | **UNVERIFIED** | No candidate image was built. |
| Fresh snapshot and isolated restore verification | **UNMET** | No snapshot or clone created; existing point is stale and untested. |
| Schema 10 rollback to v0.1.4 | **UNMET** | Exact v0.1.4 parser rejects schema 10; no bridge exists. |
| Production cutover | **UNMET** | Not authorized and not performed. |

No provider calls, IAM/configuration change, snapshot, restore, candidate image
build, tag, or cutover was performed. `python -m sigma.cloud_runtime_check`
was not run because it launches a sandbox execution and writes runtime
evidence; it remains an operator-approved exercise. No local SIGMA server was
used.
