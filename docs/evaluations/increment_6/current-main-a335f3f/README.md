# Current main release verification: `a335f3f`

## Verdict

**Candidate verification PASS with a narrow test-only correction; current `main`
CI is still red pending review and merge of that correction.** No product source
change was needed. `main` at
`a335f3f782f12128dd4ca65ab4e0e504b35960cb` uses the correct systemd contract
(`RequiresMountsFor=/srv/sigma-state`), while three tests still asserted the
former explicit escaped mount-unit name. The test correction asserts the
service dependencies and mount requirement separately. It does not change
deployment behavior.

## CI and local checks

GitHub Actions run [40259167557](https://github.com/bkramerext/sigma/actions/runs/40259167557)
(run 609, workflow `SIGMA verification`) for exact main SHA
`a335f3f782f12128dd4ca65ab4e0e504b35960cb` concluded **failure**. Job `verify`
failed at step 7 (`Check host safety and environment-isolated lifecycle
tests`): `tests/gce_host.py` expected
`Requires=docker.service sigma-sandbox.service srv-sigma\\x2dstate.mount`.
The full repository verification step was skipped. The main failure was
reproduced locally along with the same stale assertions in
`tests/deployment_package.py` and `tests/host_monitor.py`.

After `./sigma setup` passed, I updated those three test contracts. The actual
transcripts are retained here:

- [Initial full-suite run before correction](full-test-before-fix.txt): FAIL on
  the three stale assertions; the isolated worktree also lacked frontend
  dependencies at that point.
- [Setup](setup.txt): PASS; locked Python and frontend dependencies installed.
- [Focused checks](focused-checks.txt): PASS for continuations, evidence
  feedback, sessions, settings, epistemic continuity, Python/Sage execution,
  computational evidence, and the three deployment tests.
- [Full suite after correction](full-test-after-fix.txt): PASS for
  `env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test`, including Ruff,
  formatting, Pyright (0 errors/warnings), frontend typecheck, and production
  build. Vite emitted its existing >500 kB chunk-size advisory but completed.

The final full run was 2026-10-26 02:30:43–02:32:09 UTC (exit 0). The focused
run was 02:35:31–02:36:17 UTC (exit 0). These were run on current main source
`a335f3f`; the candidate diff is limited to test assertions, this evidence,
and a correction to the browser-check harness described below.

## Real Chrome on actual project copies

`release_browser.py` made path-rebound isolated copies of the actual Increment
5 saved projects. Chrome 156.0.8078.47 exercised each project’s Simple and
Advanced Outcome preferences; saved Conclusion and historical summary;
Conclusion Markdown rendering where the stored conclusion supported offline
rendering; approved source navigation; unapproved historical evidence access;
execution JSON/source/output/provenance versus the API record; and 1440, 390,
and 320 pixel layouts. It verified source session IDs, steps, and artifacts
before/after and recorded no overflow, page errors, or request toasts. The
12 viewport observations are in [browser-observations.json](browser-observations.json),
with screenshots and actual API audit/report exports in [exports](exports/).

The observed projects retained 16 subset-sum sessions and 2 algorithm sessions.
Project IDs are `1e8625bf-12fd-4148-8db9-8878895466fd` and
`d9e7d28c-68a1-4cbb-a05b-00ffc713700f`; each copy’s research-session records
remained equal. No session, provider call, or computation was created during
the browser check. Only the isolated copies’ per-project preference changed.
The underlying role responses in these saved projects are scripted offline
fixtures from Increment 5; the Chrome exercise is real, but it is not evidence
of live model reasoning.

The first browser attempt is retained as
[browser-first-attempt-failure.txt](browser-first-attempt-failure.txt). The
existing browser harness assumed every saved Conclusion started in plain text;
mathematical conclusions now initialize in rendered Markdown and expose
“Show saved Conclusion.” I adjusted the harness to test both toggle directions
when rendered math is available, and to leave provider-backed conversion
untouched for a non-mathematical conclusion. The second actual Chrome run
[passed](browser-run.txt): 12 viewports, no page errors, and direct Inspect
finding focus succeeded. This was a harness expectation defect, not a product
failure.

## Evidence-quality and blind gate

The earlier [release audit](../RELEASE_AUDIT.md) remains the detailed review of
actual Outcomes and reports. This current-main pass found no app-generated
proof, novelty, or independent-verification wording that exceeded its saved
status. One fixture-authored GRAPH-withheld Conclusion still says a bounded
computational observation is supported while the same record says no
computation was observed. The UI preserves its `Incomplete` status; this
contradiction is retained as an evidence-quality limitation, not treated as an
app-verified result. These sessions and reports establish neither model
comprehension nor a research-quality gain.

The existing [frozen blind gate](../BLIND_GATE_FROZEN.md) is ready as a
proposal: it provides exact answer-free MATH/GRAPH/SYMMETRY prompts, an
evaluator-only key, matched four-call SIGMA and single-role arms, evidence-on
and GRAPH evidence-withheld comparison, contamination exclusions, a blinded
0–4 scorer, integrity no-go rules, and proposed maximum authorization of
$1/arm and $7 total. A human must approve the named provider/model/account,
live-call mode, frozen ceilings, and the seven arm runs before any request.
No provider calls were made here. The gate can test a bounded cumulative
usefulness signal against a matched single role and evidence-withheld control;
three task families cannot establish general autonomy or isolate every prompt
and orchestration effect.

## Reproduction

```sh
env -u SIGMA_CLOUD_BOOTSTRAP_ADMIN_EMAIL ./sigma test
uv run --locked --no-sync python tests/continuations.py
uv run --locked --no-sync python tests/research_feedback.py
uv run --locked --no-sync python tests/research_sessions.py
uv run --locked --no-sync python tests/project_settings.py
uv run --locked --no-sync python tests/epistemic_continuity.py
uv run --locked --no-sync python tests/python_sandbox.py
uv run --locked --no-sync python tests/sage_execution.py
uv run --locked --no-sync python tests/computational_evidence.py
SIGMA_RELEASE_OUT="$PWD/docs/evaluations/increment_6/current-main-a335f3f" \
  uv run --with playwright python docs/evaluations/increment_6/release_browser.py
```

All exports, screenshot paths, file sizes and SHA-256 hashes are listed in
[MANIFEST.json](MANIFEST.json). No paid calls, cloud operations, or new research
sessions occurred. The current main CI remains blocked until the test-only fix
PR is reviewed, merged, and its merged-main verification is green. I would
continue with inspectable local research workflows, but I would not treat this
offline evidence as proof of live research effectiveness or a production go
decision.
