# SIGMA

**Strategy Investigation, Generation, Measurement & Assessment**

**Explore difficult questions without losing the thread.**

SIGMA is a research workspace for people investigating problems with more than one plausible approach. It is particularly suited to mathematical exploration, where promising ideas must be tested against precise assumptions, evidence, and counterexamples.

Instead of letting a long conversation or a growing collection of notes become the research record, SIGMA organizes an investigation into **strategies** you can develop, compare, revisit, and set aside without losing the work that led to them.

## What you can do

- **Give a problem a home.** Create a project around a question worth exploring and return to it whenever you like.
- **Explore competing strategies.** Write down different approaches, refine them, organize their priority, and track where each stands.
- **Use AI as a collaborator.** Ask ChatGPT to suggest a direction from your research problem and optional starting idea. Review and edit its proposal before deciding whether to keep it.
- **Keep your research history.** Changes to strategies are recorded, so earlier thinking remains available even as your investigation evolves.
- **Work on your own terms.** Manual research requires no AI account. Projects live locally, and AI suggestions are never saved without your approval.

SIGMA includes a sample mathematical investigation with several contrasting strategies to help you get started.

## Getting started

SIGMA currently runs locally on macOS and Linux. You'll need Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20.19+, and npm.

From the project directory:

```sh
./sigma setup
./sigma ui
```

Open **http://127.0.0.1:5173** in your browser. Start with the included example or create your own project, then add a strategy.

To explore with AI, select **Connect AI** and **Continue with ChatGPT**. Eligible requests use your ChatGPT plan allowance or credits, subject to applicable limits. An optional API-key connection uses separately billed API usage; SIGMA never switches billing modes without your choice.

For detailed setup and usage instructions, see [Getting Started](docs/GETTING-STARTED.md).

## Where SIGMA is headed

The longer-term vision is a research environment in which independent AI agents can investigate competing strategies, challenge one another's reasoning, test claims, and help assess which directions deserve further effort.

**Today, SIGMA is a workspace for human-led investigation with optional AI strategy proposals.** Autonomous research agents, independent evaluation, and formal proof verification are future ambitions, not current features.

SIGMA grew from exploratory work on the Riemann Hypothesis and a simple realization: even when a difficult problem remains unsolved, the investigation should leave behind something more valuable than a conversation. It should preserve what was tried, what failed, what remains uncertain, and what might be worth trying next.
