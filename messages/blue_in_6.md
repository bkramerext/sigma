# BLUE IN 6 — current-main release verification

**Date:** 2026-10-26 (UTC)  
**Verified main:** `a335f3f782f12128dd4ca65ab4e0e504b35960cb`  
**Candidate fix:** PR [#180](https://github.com/bkramerext/sigma/pull/180), head `beb43f5a88b3f234309c254f78dc7895687dd664`, open and not merged.

## Verdict

The current-main release gate is **FAIL pending a narrow test-only correction**. Main CI run [40259167557](https://github.com/bkramerext/sigma/actions/runs/40259167557) failed at the host safety/lifecycle test step because three tests expected the former explicit escaped mount-unit dependency. The current service uses `RequiresMountsFor=/srv/sigma-state`; its unit contract is correct. The rest of that main verification was skipped. PR #180 updates those three assertions and includes a current-main verification bundle. The PR has no product source changes. Its workflow status was not yet available when this report was published.

On that candidate, setup passed, focused research and host tests passed, and the full `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test` passed, including Ruff, format, Pyright (0 errors/warnings), frontend typecheck, and production build. Actual transcripts are in the verification bundle below. Ruff and formatting were rechecked after the browser-harness correction.

## Real browser and evidence quality

Chrome 156.0.8078.47 exercised actual saved Increment 5 project copies, including Simple/Advanced preferences, stored Conclusion versus historical summary, Markdown toggling, approved source navigation, unapproved historical evidence, execution JSON/source/output/provenance, and 1440/390/320 widths. Twelve viewport observations passed without page errors or overflow. Session records remained unchanged; there were zero new sessions and zero provider calls. This verifies the UI against scripted offline data, not live reasoning or research effectiveness.

One fixture-authored GRAPH-withheld Conclusion describes a bounded computational observation while its record says no computation was observed. The application retains the `Incomplete` status; this is a content-quality limitation and should not be presented as a verified result. The frozen blind gate is a bounded proposal, with matched four-call SIGMA/single-role arms, three task families, contamination controls, blind scoring and no-go rules. Its proposed maximum is $7 total ($1 per arm), but live execution requires explicit human authorization for provider, model, account, mode, ceilings and runs. It cannot establish general autonomy or isolate every orchestration effect.

## Evidence

All current-main evidence is committed under `docs/evaluations/increment_6/current-main-a335f3f/`:

- `README.md` — CI/local/browser results and evidence-quality assessment.
- `full-test-before-fix.txt`, `setup.txt`, `focused-checks.txt`, `full-test-after-fix.txt` — actual command transcripts.
- `browser-run.txt`, `browser-observations.json`, `copy-provenance.json`, screenshots, and `exports/` — actual browser observations and copied-project report/audit exports.
- `MANIFEST.json` — byte sizes and SHA-256 for every evidence file.

The main CI log failure is described with its workflow URL and exact assertion in `README.md`. Earlier Increment 5 missing logs were not reconstructed. No paid provider calls, GCE operations, or new research sessions were made.

## Assessment

I would continue local workflow and deployment verification after the test-only CI correction is reviewed and merged. I would not make a production-go or research-effectiveness claim while main CI is red and the blind gate has not been explicitly authorized and run.
