# SIGMA Cloud consolidated acceptance (T99 / T137)

This sequence consolidates hosted launch evidence from T99/T131–T137. It is
desktop-only. T99's mocked API/accounting checks and T91/T100/T133 local
browser/export checks are useful prerequisites, but they are **not hosted
passes**. The final go/no-go belongs to the coordinator and owner.

## Evidence rules

- Start with the exact deployed release SHA from the owner/release record. If it
  cannot be established, record the release as unknown and block acceptance.
- Run the read-only public probe from a network outside the VM. It checks the
  DNS A answer against the owner-verified address, app/daemon ports, HTTP to
  HTTPS redirect, trusted certificate, SPA deep link, and hosted API status.
- Every row is `PASS`, `FAIL`, `BLOCKED`, or `NOT RUN`. A local, mocked, code
  review, or test result must identify its evidence kind and cannot be used as
  hosted evidence. `BLOCKED` and `NOT RUN` prevent a GO candidate. A failure
  prevents GO. Even a complete PASS report is only a candidate for coordinator
  and owner review, never an automatic launch decision.
- Do not include secrets, email addresses, cookies, tokens, project contents,
  OAuth callback parameters, or unsanitized response bodies in the report.

## Initialize and probe

From the repository root, after the public hostname and expected static IPv4
have been supplied by the owner:

```sh
uv run python -m sigma.cloud_acceptance \
  --origin https://sigma-research.duckdns.org \
  --expected-ip OWNER_VERIFIED_IPV4 \
  --release-sha DEPLOYED_RELEASE_SHA \
  --output cloud-acceptance-evidence.json
```

This invokes the existing read-only public endpoint validator. Without
`--expected-ip`, the report is initialized with all checks `NOT RUN`; it does
not imply hosted connectivity. The endpoint probe records `PASS` only after
all its DNS, port, redirect, TLS, SPA, and API assertions pass. On probe failure
it records `FAIL`. The command exits nonzero on a failed probe. Fill remaining
rows only with observed evidence, retaining the check IDs and adding concise
evidence references and evidence kind. PASS requires a hosted evidence kind,
an evidence reference, and an exact 40-character deployed release SHA; local
and mocked evidence cannot pass a hosted row. `BLOCKED` should include the
missing authorization or dependency. The command exits nonzero while the
summary is incomplete or failed. Then recompute the summary:

```sh
uv run python -m sigma.cloud_acceptance \
  --finalize cloud-acceptance-evidence.json \
  --output cloud-acceptance-evidence.json
```

Treat the evidence JSON as an append-only acceptance artifact after review.
Keep the sanitized source artifacts and operator confirmations alongside it.

## Hosted sequence and gates

Record UTC start/end, tester, desktop Chrome/Chromium version, canonical
origin, deployed release SHA, operator-confirmed current commit, and evidence
directory. Obtain owner authorization for the named test window and disposable
projects. Stop if storage mount, deployment preflight, hosted health, or
recoverable backup prerequisite fails.

1. **Public ingress and API** — run the command above externally. Capture only
   sanitized status and DNS/TLS evidence. Follow the exact probe with the
   operator's T129 health/preflight record; the probe does not inspect VM
   internals or prove deployment provenance by itself.
2. **Google OAuth and authorization** — follow [T131 hosted OAuth](T131_HOSTED_OAUTH_ACCEPTANCE.md)
   in two clean desktop profiles. Owner authorization and two distinct
   authorized Google identities are required. Include signed-out denial,
   logout invalidation, and rejected-identity behavior. Never expose callback
   codes or session material.
3. **Two-account privacy** — follow [T134 hosted isolation](T134_HOSTED_ACCEPTANCE.md)
   using the separate identities. Verify A/B project, session, report and
   artifact direct references, denied writes without mutation, and owner-only
   usage state. Do not substitute aliases for distinct identities.
4. **Project and research workflow** — with a disposable project, create/save
   a project and strategy, then reload and reopen it. Inspect a saved session,
   Outcome, verification/provisional state and evidence. For a **new real
   provider inference** session, obtain separate explicit provider/budget
   authorization first; record provider, bounded call limits and usage ledger
   before/after. Never use mock inference as hosted provider evidence.
5. **Python/Sage** — use the owner-approved disposable project and the
   existing T132 procedure. Verify Python and Sage as provisioned, captured
   output/provenance, network denial, resource limits and cross-workspace
   denial. Do not broaden access or change sandbox configuration to make a
   check pass. Record unavailable Sage as `BLOCKED` if it is a launch
   requirement.
6. **Outcomes and exports** — follow [T133 acceptance](evaluations/t133/README.md).
   Download audit/text/HTML reports and an already-authorized TeX/PDF paper;
   record filenames, sizes and SHA-256 digests. Generating a new paper that
   requires provider inference needs the same explicit authorization. Reports
   are research records, not independent proof.
7. **Restart and state** — close/reopen the browser, verify the same identity
   and project state, then use the operator-approved application restart
   window and verify IDs/digests again. Do not restart the production service
   outside the documented maintenance procedure.
8. **Backup, restore, rollback** — use [T135/T136 operator runbook](OPERATION_RUNBOOK.md)
   steps with owner/operator authorization. Preserve snapshot identity,
   readiness, restore-verifier output, reconciled owner/workspace/accounting
   evidence, release before/after and rollback result. Never restore over live
   state as an ad hoc test; use the documented isolated recovery procedure.
9. **Monitoring and recovery** — verify configured timers/alerts and safe
   recovery behavior using the documented monitor, host checks, and recovery
   drill. Record observed alerts/actions and service recovery. Do not induce
   production failure without the approved window.

## Required final review

Coordinator review checks the JSON and its referenced evidence, confirms the
release SHA matches the hosted deployment, distinguishes hosted from local or
mocked results, and lists every outstanding owner action. Any `FAIL`,
`BLOCKED`, `NOT RUN`, missing release identity, or missing required evidence
means no-go/incomplete. A complete report still requires explicit coordinator
and owner decision and recorded signoff under T137.

## Local preparation already available

- `./sigma test`: deterministic and mocked service coverage, including T99
  inference/accounting and cloud workspace boundaries.
- `bash deploy/validate-local.sh`: packaged local Compose and desktop Chrome
  workflow where the host Docker environment supports the worktree mount.
- `docs/evaluations/t91/README.md`, `docs/evaluations/t133/README.md`,
  `docs/evaluations/t100/README.md`: local browser, storage, restore, and
  export preparation with explicit limits.
- `deploy/verify_public_endpoint.py`: existing standalone DNS/HTTPS/API probe.

These checks are reported as `local` or `mocked`; none changes a hosted row to
PASS.
