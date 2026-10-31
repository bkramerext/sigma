# IN 1 — Phase 1 checkpoint

**Branch:** `blue/sovereign-ai-federation`  
**Pushed HEAD:** `ca73bc153cd8e429d12075de9c8fa6dd64f9abc3`  
**Round:** 1 (canonical mailbox; the former `blue_session` numbering is historical and was not continued)

## Completed

- Added the Hard / Computer Science **Sovereign AI Federation** stock sample with three complementary strategies. Its scope distinguishes MindRouter's documented on-campus gateway, quota/fair-share and inference capabilities from proposed federation, and frames ownership cost, task quality, fairness, sovereignty, security, reliability and a stop/go pilot as research questions rather than fabricated measurements.
- Added a default-off **Include diagrams (experimental)** option in paper generation only. The implementation uses a bounded validated diagram representation and deterministic escaped TeX rendering, preserves the generation checkpoint, and has compile-recovery behavior. It is not exposed in Research Play.
- Preserved two synthetic renderer fixtures under `docs/evaluations/issue_393_394/mock_fixture/`: `paper-text-only.tex/.pdf` and `paper.tex/.pdf`. Both use the exact same frozen project snapshot (`3dcae814d22543d99e4be11f89c0123f8a29d9c7958ca5147f48b7a187c2142e`) and mock draft; the control removes only the optional diagram field. The paired files and fixture provenance are recorded in `manifest.json`. All seven recorded SHA-256 values were rechecked against the files.
- Both fixture PDFs compiled through the local SIGMA/Tectonic path. The diagram PDF is three pages. Page 2 was rasterized and visually inspected; architecture labels, arrows, edge legend, trust boundary and caption are readable. These fixtures contain no research sessions and are explicitly synthetic, not research findings.
- Resolved the real-Chrome sample-open failure by configuring the fixture server's existing origin hook for Vite's isolated port 5194. The browser script then passed: sample opens; paper checkbox is default-off; preference persists across reload and can be unchecked. No paper-generation or provider request was made.

## Checks

Passed on the canonical branch after cherry-picking the implementation and before this report commit:

- `uv run --locked ruff check src/sigma/papers.py src/sigma/api.py tests/papers.py browser_checks/issue393_diagram_option.py`
- `uv run --locked python tests/papers.py` (includes local Tectonic compilation and the focused paper-generation cases)
- `uv run --locked python tests/project_reports.py`
- `npm run typecheck`
- Stock sample discovery, independent copy, and complete SIGMA project-bundle export
- Real Chrome `browser_checks/issue393_diagram_option.py` with the fixture origin setting documented in `browser_checks/README.md`
- `git diff --check`; SHA-256 verification of all seven manifest files

I did not run full `./sigma test`; this is not a final CI claim. No live Investigator/Skeptic calls were made. Provider calls: 0. Provider spend: $0.00.

## Phase status

- **MET:** stock sample; opt-in/default-off paper diagram path; bounded safe TeX representation; same-evidence synthetic diagram/control fixture pair; local compilation and visual figure inspection; migrated implementation and artifacts on the canonical branch.
- **UNMET:** bona fide saved Investigator/Skeptic research; substantive research-based conventional and diagram-enabled papers; critical comparison of real evidence, cost model, routing quality and source fidelity; full final CI.
- **UNVERIFIED:** diagram rendering and paper quality on actual saved research; realistic university cost conclusions (no institutional data or measurements have been gathered); independent coordinator review.
- **Authorization blocker:** no live/paid model call is authorized by OUT 1. I have not inferred approval from available credentials. Engineering work proceeded offline.

Please review the pushed code and fixtures and send the next numbered assignment when ready. I will not start live research without explicit bounded spend authorization.
