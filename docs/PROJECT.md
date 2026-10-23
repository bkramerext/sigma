# SIGMA

**Strategy Investigation, Generation, Measurement & Assessment**

A local-first research workspace for exploring competing approaches to difficult problems. The Riemann Hypothesis is the initial project, not a claimed solution.

## Research model

- **Strategies** hold distinct candidate approaches. Users can author, generate,
  disable, and fork them from saved findings. A fork starts a new strategy
  identity; it does not rewrite its parent or past sessions.
- **Research sessions** run bounded Investigator/Skeptic cycles for one or
  several enabled strategies. Calls share the configured budget and run with a
  local concurrency cap; the user can inspect each branch, guide later agent
  steps with attributed interventions, and pause, resume, or stop the session.
- **Artifacts and events** preserve attributed claims, methods, objections,
  open obligations, coordinator dispositions, and strategy assessments.
  Unverified model output is not a proof or an independently checked result.
- **Continuity** lets a new session cite a bounded set of prior findings while
  keeping the original session records intact.

## Implementation

Python/uv, FastAPI, argparse CLI, React/TypeScript/Vite. Browser, CLI, and executable scenarios share typed application services.

**Working now:** local project lifecycle; strategy authoring and generation;
bounded single- and multi-strategy research sessions; persistent evidence,
continuity, assessments, forks, report exports, and optional isolated Python
and SageMath execution for finite Investigator computations. Research still has no external
source tool or formal proof checker. Python output is unverified evidence, not a
proof. Live model quality has not been established by the deterministic test
suite.

See [Getting Started](GETTING-STARTED.md) to run, [STATUS](STATUS.md) for verification, [DECISIONS](DECISIONS.md) for storage, and [BRAINSTORM](BRAINSTORM.md) for future ideas.
