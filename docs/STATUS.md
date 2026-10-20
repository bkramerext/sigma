# SIGMA status
Updated: 2026-10-20

## Active specification
**SPEC-001: [Project lifecycle](../specs/project-lifecycle.md)**. Approved for implementation, not yet implemented. This is the immediate Codex assignment. Finish and verify this before expanding to agent generation or the dashboard.

## SPEC-001 acceptance
- [ ] Scaffold Python/uv package and argparse console entry point.
- [ ] Implement portable SQLite project creation/open/close and schema validation.
- [ ] Record atomic project.created event; expose read-only info/events CLI.
- [ ] Cover persistence, repeat reads, overwrite refusal, corruption, schema mismatch, atomic failure and ordering in offline tests.
- [ ] Run pytest, Ruff and Pyright; document results and update this status.
- [ ] Commit and push tested implementation.

## Subsequent milestones (not active)
- [ ] RH sample problem and configurable rubric.
- [ ] Bounded real LLM strategy generation with offline fakes.
- [ ] Ranking, scheduler, iterations and independent evaluation.
- [ ] FastAPI/HTMX browser with live agent activity.
- [ ] Reopen and inspect full research history.

## Collaboration protocol
ChatGPT and Codex coordinate through committed specs, docs and code on GitHub. No automatic synchronization of chat histories. Codex should record completed work, actual commands/test results, blockers and next task here after each meaningful increment.

## Open questions
OpenAI API credentials and spending budget not confirmed. Lean and artifact generation deferred.
