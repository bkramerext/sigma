# SIGMA

**Strategy Investigation, Generation, Measurement & Assessment**

**A local research workspace with bounded AI investigation, computational experiments, and durable evidence.**

SIGMA helps people investigate difficult problems through multiple strategies. Its initial showcase is mathematical research, including the Riemann Hypothesis, but projects and sample investigations span other domains.

Instead of treating a long conversation as the research record, SIGMA organizes work as **projects → research sessions → strategies → evidence artifacts**. Research findings, criticisms, experiments, and unresolved obligations can be inspected and revisited.

## What you can do

- **Create research projects and strategies.** Define a problem, choose its domain and difficulty, write or generate competing approaches, enable or disable strategies, and refine them without losing earlier work.
- **Run bounded, concurrent research sessions.** Investigator and Skeptic agents work on selected strategies with a shared model-call budget, visible progress, stop/resume controls, and saved per-strategy histories. Sessions preserve evidence and can carry attributed findings into later work.
- **Coordinate related investigations.** Evidence-linked cross-strategy findings can change a peer strategy's next research question. Contradictions, overlaps, complementary results, and later withdrawals remain inspectable. These relationships are model-reported and are **not automatically verified**.
- **Execute scientific Python experiments.** When appropriate, Investigators can propose code for an isolated Docker sandbox with NumPy, SciPy, pandas, SymPy, and Matplotlib. The Skeptic receives the exact code, result, diagnostics, and execution provenance. Computations and captured files are retained as research evidence.
- **Inspect and publish research artifacts.** View session evidence, export audits or deterministic reports, and use bounded AI authoring to create versioned research papers and compiled PDFs with claims linked to frozen evidence snapshots.
- **Work locally and retain control.** Projects remain on your machine. Manual work does not require an AI account. You choose the connected AI provider and can supervise, stop, and review agent activity.

The included samples cover varying domains and difficulty levels. The Riemann Hypothesis example is an **open research problem**, not an existing proof or claim that SIGMA can solve it.

## Getting started

SIGMA currently runs locally on macOS and Linux. You'll need Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20.19+, and npm.

From the project directory:

```sh
./sigma setup
./sigma start
```

Open **http://127.0.0.1:5173** if the browser does not launch automatically. Choose a sample project or create your own.

To use AI, select **Connect AI** and **Continue with ChatGPT**. Eligible requests use your ChatGPT plan allowance or credits, subject to limits. An optional API-key connection incurs separately billed API usage; SIGMA does not silently switch billing modes.

### Optional scientific Python sandbox

Research Python execution requires a working Docker-compatible container runtime and a locally built image:

```sh
docker build -t sigma-research-python:0.1 sandbox-poc
```

The runtime does not pull or install packages during an experiment. The container has no network access or host project mounts and runs with bounded resources. See [Getting Started](docs/GETTING_STARTED.md) and [Research Python Execution](docs/RESEARCH_PYTHON_EXECUTION.md) for setup, security assumptions, and resource limits.

## Research quality and current limits

**Implemented engineering is not the same as demonstrated scientific discovery.** SIGMA has deterministic tests for orchestration, evidence handoff, cancellation/recovery, isolated computation, and reporting. Early live-agent trials have shown correct handling of a simple mathematical problem and one useful numerical experiment, but **robust independent work on Medium/Hard problems, subtle mathematical error detection, and reliable cross-strategy synthesis remain unproven**.

Research output must distinguish conjecture, finite computation, agent-reviewed argument, and independently verified theorem. Python and model consensus do not constitute formal proof. A Lean-based formal verification capability is only a future proposal.

Future directions include improved evidence-driven coordination, broader scientific tooling such as SageMath, scholarly citation tracking, and deployment beyond local workstations. These are not represented here as shipped features.

SIGMA grew from an investigation into the Riemann Hypothesis and the idea that even an unsolved question should leave a useful, inspectable record of what was tried, what failed, and what remains unknown.
