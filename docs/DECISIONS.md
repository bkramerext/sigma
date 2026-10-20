# SIGMA decisions
Date: 2026-10-20

1. **Name:** SIGMA means Strategy Investigation, Generation, Measurement & Assessment. RH is the flagship sample, not a claimed proof.
2. **Projects:** Local-first, one portable SQLite-backed .sigma file per project; transactional autosave, open/close and event history.
3. **Vocabulary:** Strategy pool contains high-level approaches; iterations are bounded agent runs; artifacts are durable outputs; events are the audit trail.
4. **Scoring:** Versioned configurable rubric; uncertainty can increase exploratory priority. Verified solution is a terminal status displayed as +infinity.
5. **Interfaces:** argparse CLI and FastAPI/HTMX browser share application services. SSE provides live updates initially.
6. **Agents:** OpenAI Agents SDK executes agent runs; SIGMA controls scheduling, evaluation, budgets, state and persistence.
7. **Engineering:** uv, Python, pytest under tests/, Ruff, Pyright; domain models under models/.
8. **Collaboration:** GitHub is the shared source of truth between ChatGPT and Codex. AGENTS.md and docs/ track requirements, status and decisions. Commit/push tested increments; avoid force-push and secrets.
9. **Scope:** Complete a tested local end-to-end loop before Lean, LaTeX, elaborate visualizations or other domains.
