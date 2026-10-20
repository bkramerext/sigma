# SIGMA project brief

SIGMA = Strategy Investigation, Generation, Measurement & Assessment. Build a local-first multi-agent research platform for the Onebrief engineering candidacy. The Riemann Hypothesis is the flagship sample (`rh.sigma`), not a claimed solution. The software should eventually be domain-independent.

## History and motivation
Extended RH explorations repeatedly generated approaches, ranked them, investigated selected ones, reported back, and reprioritized. Work touched zeta and Hardy Z, partial-sum spirals and tail corrections, and alternative mathematical perspectives. No RH proof was established. The key lesson: attractive identities, numerical observations and plausible prose can masquerade as progress. Require explicit proof obligations, independent criticism, evidence, and failure criteria. Do not oversell research paths.

## Domain model
- Project: problem statement, assumptions, versioned rubric, budget, strategy pool, event history, artifacts, configuration. Open/close in browser or CLI; store in portable SQLite-backed .sigma file.
- Strategy: high-level approach in the strategy pool; states proposed, active, on_ice, discarded, failed, succeeded. Ranked by configurable rubric. New poorly understood strategies can score highly on information value.
- Iteration: one bounded agentic run on a strategy; states queued, running, completed, failed, cancelled, error. Report objective, attempt, discoveries, evidence, invalid assumptions, unresolved obligations, next steps and resource use. Iteration completion is not strategy success.
- Artifact: durable output such as strategy description, LaTeX paper, Lean formalization or report, tied to a specific historical state. Eventually allow generating from any selected event in both UI and CLI.
- Event: ordered immutable record of transitions, actor, time, before/after states, rationale, evidence and rubric version. Replay decisions without rerunning LLM calls.

## Workflow
`sigma generate --project=rh.sigma` proposes multiple strategies into the strategy pool. Evaluator scores/ranks independently; scheduler assigns bounded iterations to agents; iteration findings trigger rescoring and possible reallocation. Show ranked strategies and which are executing in a real-time browser. Record full alternative histories. Verified success is a semantic terminal state displayed as +infinity, never a self-awarded numeric score.

## Implementation defaults
Python with uv and pyproject.toml; models in models/ (project.py, strategy.py, strategy_pool.py, iteration.py, rubric.py, event.py, artifact.py). OpenAI Agents SDK for agent runs; custom deterministic orchestration, scheduling, budgets and scoring. FastAPI/Uvicorn + HTML templates/HTMX + SSE for browser; argparse CLI. Both interfaces call shared services. SQLite for portable .sigma project files. pytest tests in tests/, Ruff, Pyright. Ordinary tests mock LLM calls and incur no API charges. ChatGPT Pro does not include API usage.

## Milestone 1
Implement a real, tested vertical slice: open/close rh.sigma, generate candidate strategies, rank them with configurable rubric, schedule an iteration, show running agent activity in browser, persist a structured report and auditable events, close/reopen without data loss. Provide setup/demo instructions. Do not claim simulated activity is live.

## Deferred
Lean verification, LaTeX/PDF artifact generation, historical artifact UI, dependency graph, sophisticated scheduling, cloud deployment, authentication, wargaming adapters.

## Owner and collaboration
Owner is an experienced principal engineer with Python/C++, compilers, static analysis, AWS distributed data systems, observability, performance and LLM integration experience. Values modularity, deterministic machinery, tests, cost discipline and iterative shipping. Curious about novel mathematics and multi-agent engineering but explicitly requires ideas not to outrun implementation. Prefers concise, substantive, skeptical communication. Web/agent SDK/Lean familiarity are unknown, not presumed weaknesses. Codex implements and tests; ChatGPT discusses product and reviews; GitHub docs/commits are the shared source of truth.
