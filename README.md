# SIGMA

**Strategy Investigation, Generation, Measurement & Assessment**

SIGMA makes branching research investigations manageable and trackable. Difficult
problems—especially in mathematics—invite several competing avenues at once.
Ideas can diverge, stall, be compared, revisited and eventually evaluated without
losing the assumptions, earlier text and history that explain how you got there.

The current application organizes those avenues as **strategies** within portable
local projects. It helps a person keep research coherent; it does not claim that
an appealing argument, finite experiment or AI suggestion is a proof.

## What works today

- Browser-first local projects with a shared Create/Edit form, stable identity, research problem, mode, AI model and Thinking level.
- Manual strategy creation, editing, removal from the active list, full approaches
  and retained audit history.
- Persistent drag ordering with pointer/touch and keyboard controls, plus explicitly
  **human-maintained** Draft, Ready to explore, Exploring and On hold stages.
- Optional AI proposals: one direction per explicit request, an optional starting
  point, editable draft review, and human acceptance before anything is saved.
  Accepted suggestions retain provider/model provenance. Manual writing works
  without AI configuration.
- Shared typed Python services behind the browser, CLI, API and executable scenarios.

**Future ambitions:** actual forks and branch lineage, autonomous investigations,
independent evaluators, Lean verification, LaTeX artifacts, scheduling and generated
research reports. These are not implemented. Exploring means the person is
investigating; no agent or proof checker is running.

## Inspiration

SIGMA grew out of the author's multiday explorations of the Riemann Hypothesis
with ChatGPT. There was no realistic expectation that an amateur working with AI
would solve it. The educational value was in the mathematics, questions and
critical examination of evidence. Free-form conversations also made earlier
findings hard to recover and sometimes let plausible ideas consume effort before
basic flaws emerged. SIGMA aims to make that exploration cumulative, including
what was learned from failure. The RH seed is an example project, not a solution.

## Get started

Requires macOS/Linux, Python 3.11+, uv, Node.js 20.19+ and npm.

```sh
./sigma setup
./sigma ui
```

Open http://127.0.0.1:5173. Use Open Project or New Project, then **New Strategy**
to write manually or choose **Generate with AI** from its adjacent dropdown.

`./sigma ui` automatically loads this checkout’s gitignored `.env` and restarts
its own previous instance. Existing shell variables take precedence. Ctrl+C stops
both servers; unrelated port listeners are never terminated.

AI is off by default. Set `SIGMA_AI_ENABLED=1` and `OPENAI_API_KEY` in `.env`
(simple assignments or quoted `export` syntax), then run `./sigma ui` again.
No manual sourcing or PID cleanup is needed. Choose the project model and Thinking
level in New Project or the pencil beside its name.
The reviewed choices are Luna · Economy ($), Sol · Balanced ($$), and Astra ·
Advanced ($$$); these are relative cost tiers, not price quotes. New projects
prefer Sol/High when account access is verified. Offline defaults and unavailable
choices are clearly qualified; no generation request silently substitutes models.
`SIGMA_AI_MODEL` is only a reviewed-model bootstrap override for legacy files.
Do not put a key in frontend code or Git. API billing is separate from ChatGPT or
Codex access. The dialog requires consent before transmitting the project problem,
mode, all strategy titles/approaches and optional seed. No generation calls happen on load or while typing; cached non-generating
model-list checks provide connection health and account availability. Tests use identified fixtures and make no paid calls.

See **[Getting Started](docs/GETTING-STARTED.md)** for setup, keyboard controls,
provider limits, CLI/API commands and storage limitations. [Status](docs/STATUS.md)
records actual verification; [Project](docs/PROJECT.md) and
[Brainstorm](docs/BRAINSTORM.md) describe the longer-term direction.

The small **OpenAI API** indicator checks actual API authentication/reachability.
Green does not establish model generation, credit, quota or billing. Its details
show the last check and a Retry action; no paid generation lights the indicator.

Close Project currently returns Home without saving or flushing anything—changes
are already saved by explicit actions. When real running agents exist, closing
will need active-work confirmation and an explicit policy for whether they continue.
A8 does not introduce such agents or an imaginary confirmation.
