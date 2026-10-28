# Issue #286 project export

`concurrent-session-limits.sigma.json` is the byte-preserved output of
SIGMA's `projects.export_complete_project` export path after the real-Chrome
Limits exercise.

- Source project ID: `d6fc83e6-2e54-4fee-b9fb-ffc33135609d`
- Source project: disposable copy of the “Counting Constrained Binary Strings”
  sample created through the browser workflow under the isolated provider
  fixture's temporary project root.
- Source session IDs/numbers: none; the browser exercise saved settings only and
  did not run research.
- Activity: Limits UI loaded the default `1`, rejected `0`, saved an 80 digit
  positive integer, and reloaded the saved value at a 390px viewport.
- Export bytes: 2,699; JSON bundle version: 1.
- Included project setting: `max_concurrent_sessions` is the exact saved
  80 digit value. Project and strategy data are the existing sample copy.
- Provider calls, costs, live OAuth, and deployment: none.
- Capture app commit: `f3fea3a7a6222ea2a03f23c8cd18c0d59d0bc39a`.
- Publishing/report commit: see the branch handoff for the final SHA.
- Omitted data: no research session records existed in this exercised project.
