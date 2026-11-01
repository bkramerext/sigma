# Blue handoff — Issue #415 saved-session render isolation

Branch: `blue/issue-415-session-render`  
Base: current `main` at `48c1fb23`, with candidate `30b84a43` inspected and retained as the starting point.  
Status: ready for review; no merge performed.

## Finding

The supplied `sigma-debug.json` was not present in the workspace or issue metadata during this investigation, so the exact AI Agent Reliability project payload could not be replayed. The reproduction used a private temporary project made from the checked-in T17.8 saved-session fixture, with six sessions and a deliberately malformed saved artifact. No original project or research data was touched.

On unpatched candidate `30b84a4315a79e07e0a1211c597c55377503b350`, real Chrome reproduced a blank page from the malformed session. The first uncaught exception was:

```text
TypeError: Cannot convert undefined or null to object
    at Object.keys (<anonymous>)
    at frontend/src/main.tsx:192:74
    at Array.some (<anonymous>)
    at stoppedSessionGuidance (frontend/src/main.tsx:192:48)
    at frontend/src/main.tsx:5021:32
    at frontend/src/main.tsx:5065:15
    at Array.map (<anonymous>)
    at ResearchWorkspace (frontend/src/main.tsx:4885:214)
```

The statement is `Object.keys(artifact.investigator_output)` in stopped-session guidance. A null/missing nested `investigator_output` field throws while React renders the session list. This reproduction disproves the `strategy_runs` hypothesis for this crash mechanism: the optional `strategy_runs` accesses were not involved. The `/api/projects/open` and `/api/projects/research-sessions` responses were HTTP 200, which locates this reproduced failure in React rendering rather than backend project loading or API serialization.

The same fixture also exercises malformed fields in expanded session details. React reported errors in both `<StoppedSessionNotice>` and `<ResearchSessionContents>`; the corrected UI logs the message and React component stack while confining the error to the affected session row. The exact malformed field in the unavailable owner bundle remains unverified.

## Changes

- `frontend/src/main.tsx`: normalize render-critical session fields, show a pane-level warning for records lacking usable IDs, and isolate each session row and stopped-session notice with React error boundaries. The boundaries retain concise diagnostics in the browser console and provide an export-preservation message in the UI. Normalization is display-only; the stored record and export bytes are unchanged.
- `browser_checks/issue415_session_render_isolation.py`: real-Chrome regression using an isolated six-session project. It includes a synthetic 14-turn display, malformed nested artifact, a missing-ID API record, Advanced Outcome, F5 while the deterministic backend mock is running, and project-bundle download.

No backend or scheduler changes were needed. No provider calls were made.

## Verification

- `./sigma test` — passed all configured steps, including Ruff, Pyright, frontend typecheck, and production build. Existing large-chunk advisory remains.
- `uv run --with playwright python browser_checks/issue415_session_render_isolation.py` — passed in real Chrome. Six saved session files exported; malformed sessions localized; 14-turn display and Advanced Outcome survived refresh; deterministic mock backend statuses progressed `running → running → ended` with saved evidence; no stop/control request; zero uncaught page exceptions. The `ended` transition is the deterministic mock's expected completion, with no provider calls.
- Candidate baseline run — failed with the uncaught exception and blank body shown above.
- Candidate production build before correction — failed TypeScript due implicit `any` in the new `nextSessions` callbacks; the branch now explicitly types the normalized list and passes typecheck/build.

## Verification limit

The attached private 6.7 MB bundle was not available locally and its URL was absent from issue #415's API body/comments. The issue owner's original project, its six session IDs, and its saved artifacts have therefore not been validated in Chrome or exported in this run. Please attach the bundle to the PR/review thread for a direct replay before claiming the exact target project is accepted. The user-facing fix and regression test cover the observed frontend failure class without modifying that project.
