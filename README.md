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

No account, key, `.env`, or feature flag is needed for manual research. Use the
small **Connect AI** control in the upper-right, then **Continue with ChatGPT** to
use an eligible ChatGPT plan allowance or credits. Sign-in is remembered, and
Generate can connect in place while retaining your starting point. Plan/app and
workspace limits apply; model listing does not prove inference entitlement.
**Manage usage** links to ChatGPT settings. SIGMA never automatically switches
from plan usage to API-key billing.

**Use API key (advanced)** explicitly selects separate API billing using
`OPENAI_API_KEY` from `.env` or the server environment. `SIGMA_AI_ENABLED` is no
longer required. Choose the model/Thinking level in New/Edit Project; saved choices
and High remain unchanged when account access changes. Curated API cost tiers
are relative, not token price quotes. A Generate click sends the disclosed project
context once; **Save strategy** remains the explicit human acceptance step. No
repeated consent checkbox, automatic generation, or automatic saving.

OAuth credentials live in private application storage outside projects and Git.
All implementation verification uses controlled OAuth/JWKS/SSE fixtures; live
account sign-in, plan inference and billing have **not** been verified or consumed.

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
