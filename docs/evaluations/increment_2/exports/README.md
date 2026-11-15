# Actual exercised SIGMA project exports — Increment 2 baseline

These are **actual SIGMA export API response bytes**, not manually reconstructed
research summaries. Captured before implementing Increment 2's current-state
projection, on app revision `f553934b9db37472e92339200857bf45246691c5`.
[MANIFEST.json](MANIFEST.json) lists exact file sizes/hashes, project and session
IDs, retained source-file hashes, evidence classes and actual activities.

| Project | Actual activity and evidence class | Complete audit | Deterministic reports |
|---|---|---|---|
| Maximum Regions historical working copy | Opened/read in Chrome; proof and criticism inspection; findings-fork draft cancelled; historical provider record, no new inference | [JSON](maximum-regions-archived.audit.json) | [Text](maximum-regions-archived.report.txt), [HTML](maximum-regions-archived.report.html), [TeX](maximum-regions-archived.report.tex) |
| Nonconsecutive working copy | Five archived deterministic fixture sessions inspected in Chrome; evaluator-authored proof-obligation continuation saved/reopened; no live research | [JSON](nonconsecutive-subset-sums.audit.json) | [Text](nonconsecutive-subset-sums.report.txt), [HTML](nonconsecutive-subset-sums.report.html), [TeX](nonconsecutive-subset-sums.report.tex) |
| Maximum Regions stock working copy | Manual bound/attainment strategy fork saved/reopened in Chrome; zero sessions, distinct from historical archive | [JSON](maximum-regions-by-lines.audit.json) | [Text](maximum-regions-by-lines.report.txt), [HTML](maximum-regions-by-lines.report.html), [TeX](maximum-regions-by-lines.report.tex) |

Each audit includes project/strategy events, strategies, full exported sessions,
Outcomes, artifacts, computations and saved role outputs. Nothing was trimmed
from SIGMA's standard audit. Standard internal auth/guard exclusions still apply.
SIGMA projects public Outcomes when exporting; stored session files are not
rewritten, and their original hashes were identical before/after export.

No fresh research session, provider call, independent verification, AI paper or
PDF compilation occurred. TeX reports are generated deterministic **source**,
not AI-authored papers or compiled PDFs. The original Maximum Regions argument
was not enriched with synthetic structured steps.

**Markdown limitation:** the current app has no native Markdown project-report
export. We do not relabel a plain-text report or a manually written summary as
an actual SIGMA Markdown export. Markdown-valued Conclusion fields, including
explicit historical fallbacks where no Conclusion was saved, remain in the full
JSON audits. The text, HTML and TeX outputs are the formats SIGMA actually offers.

Reproduce against the retained disposable working copies with
`uv run python docs/evaluations/increment_2/exports/export_projects.py` from the
repository root. The capture uses the real API via FastAPI TestClient, with
isolated auth/state and blocked external provider transport. It writes response
bytes unchanged and asserts source immutability. Future Increment 2 evidence
will add actual current-understanding API outputs rather than replace these
baseline exports or fabricate new research history.
