# SIGMA

**Strategy Investigation, Generation, Measurement & Assessment**

SIGMA is installable, local-first software for organizing AI-assisted research into sustained, critical investigations of difficult problems.

Instead of committing to one promising idea, SIGMA is designed to maintain competing **strategies**, investigate their assumptions, test their claims, and preserve what was learned. Independent evaluation and bounded scheduling are intended to help direct effort without mistaking confidence for proof.

## Inspiration

SIGMA grew out of the author's multiday explorations of the **Riemann Hypothesis** with ChatGPT.

There was no realistic expectation that an amateur working with ChatGPT would solve one of mathematics' great unsolved problems. But trying to understand it was hugely educational: each investigation opened up new mathematics, new questions, and new ways to think about evidence.

The experience also exposed weaknesses in free-form AI research. Investigations wandered, earlier findings became hard to recover, and plausible ideas sometimes consumed substantial effort before revealing basic flaws.

SIGMA asks: **Can AI-assisted exploration become a cumulative research process that learns from failure as well as success?**

## How SIGMA is intended to work

- **Strategies:** Competing lines of investigation, each with its own history and possible forks.
- **Research:** Bounded attempts to develop ideas, test assumptions, and gather evidence.
- **Evaluation:** Independent scrutiny of claims, uncertainty, and remaining proof obligations.
- **Scheduling:** Resource-aware allocation of effort, with explicit human control.
- **Artifacts:** Durable records of what was tried, established, refuted, or left unresolved.

One envisioned artifact, **Show Me**, would turn a strategy's actual findings into an accessible, originally illustrated explanation. A failed investigation deserves the same care as a successful one. Presentation may be imaginative; evidence must not be embellished.

## What works today

The current foundation opens local projects, preserves project identity and history, and lets people create and revisit strategies in a browser. CLI, API, and executable scenarios share the same Python services.

**Not implemented yet:** autonomous agents, evaluation, scheduling, forks, and generated research reports. The Riemann Hypothesis is the initial example project, not a claimed solution.

## Getting started

SIGMA runs locally on macOS/Linux with Python, uv, and Node.js.

```sh
./sigma setup
./sigma ui
```

Open http://127.0.0.1:5173.

See **[Getting Started](docs/GETTING-STARTED.md)** for prerequisites, usage, CLI/API commands, testing, and storage cautions. See [Project](docs/PROJECT.md), [Status](docs/STATUS.md), and [Brainstorm](docs/BRAINSTORM.md) for more context.
