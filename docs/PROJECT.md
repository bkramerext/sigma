# SIGMA

**Strategy Investigation, Generation, Measurement & Assessment**

SIGMA is a local-first multi-agent research system for exploring competing approaches to difficult problems. It is designed to generate research directions, investigate them in bounded iterations, assess evidence and remaining proof obligations, allocate effort under explicit constraints, and preserve an auditable history of decisions and outcomes.

The Riemann Hypothesis is an initial example problem, not a claimed solution. The architecture aims to support other research domains.

## Research model
A **strategy** starts with a seed idea and evolves through investigations. Strategies can fork into child strategies; generation numbers describe ancestry, not merit. A **strategy pool** preserves alternatives, evidence, and history rather than overwriting unsuccessful paths.

A configurable **rubric** guides independent evaluators in judging whether a strategy has a promising path toward the project objective. Criteria may require adversarial tests, literature comparison, or evidence gathering. Surviving tests is not proof. A deterministic scheduler allocates bounded research effort using assessments, resource constraints, and explicit human directives. Human priority overrides remain distinct from evaluator judgments.

Iterations are bounded attempts; artifacts preserve results; append-only events record consequential actions, assessments, and decisions.

## Architecture
Web UI, CLI, and executable scenario runner are equal adapters over shared typed application commands and queries. Domain services own invariants and persistence. Agent output is evidence to evaluate, not an authority to obey.

A project is a portable `.sigma/` directory containing a versioned `project.json`
with metadata and event history. The RH seed begins with `.gitkeep` and initializes
on its first open. See [decisions](DECISIONS.md) for atomic publication, validation,
and storage tradeoffs. Generated project state is excluded from Git.

## Implementation
Python and uv; argparse CLI; FastAPI API; React/TypeScript/Vite browser. Agent runtime remains deferred. Source-controlled executable scenarios are the primary acceptance tests, with deterministic fake agents for offline runs. Ruff and Pyright provide static checks.

Build and verify one specification at a time. **Implemented foundation:** [SPEC-001: Project lifecycle](../specs/project-lifecycle.md), extended by [ASN-3: Project page and strategy pool](assignments/asn3.md) with persistent manual strategies. See [status](STATUS.md), [decisions](DECISIONS.md), and [brainstorm](BRAINSTORM.md). Features beyond the bounded assignments are intentionally deferred.
