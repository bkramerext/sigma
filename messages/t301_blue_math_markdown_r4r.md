# T301 Blue handoff — Context-aware mathematical Markdown

**State:** R4R  
**Branch:** `blue/t301-math-markdown` → `main`  
**Base:** `2cf878a3290e697b408ebdb5d58871690e2c030b`  
**Implementation commit:** `c3c0dcbc589f90bb3dfa428e48743bcc291f1169` (initial implementation; subsequent verification refinements are on the same branch)

**Correction base:** `2cf878a3290e697b408ebdb5d58871690e2c030b` (latest fetched `origin/main`; branch merge-base matches, so no rebase was required)

**PR:** [#314](https://github.com/bkramerext/sigma/pull/314) — open, not merged
**Ticket:** [T301](../tickets/t301.md)

## Implementation

- Refined the existing AI Markdown conversion instructions to classify math
  from sentence meaning and retain code identifiers, paths, URLs, dates,
  versions, currency, delimiters, and Markdown structure.
- Replaced line/token rewrites in the existing KaTeX component with a Markdown
  AST text-node pass. This lets equations, contextual fractions, and indexed
  variables render inside prose, emphasis, lists, blockquotes, and tables while
  protecting code, link labels, and other Markdown nodes.
- Added the focused `remark-gfm` plugin for the existing Markdown renderer's
  tables. Kept the existing ReactMarkdown/remark/KaTeX architecture and visual
  design.
- Added an API regression and an actual Chrome rendering regression using the
  same deterministic output fixture. The API test asserts the original project
  bytes are unchanged.

## Consolidated review corrections

- Equation recognition now requires mathematical structure in the expression
  or a nearby mathematical cue. Bare `x = value`, `x = y`, `x = 3`, and
  configuration assignment examples remain ordinary prose. The regression also
  covers `x_i` in a sentence containing `MAX_RETRY_COUNT`.
- Currency markers are classified individually before remaining dollar signs
  are paired as inline math. This covers multiple prices, prices before or
  after explicit math, multiple independent formulas, escaped/unmatched signs,
  and dollar signs in inline/fenced code.
- Added these adversarial cases to the shared API/render fixture and real Chrome
  regression. The test checks exact KaTeX annotations and rendered literal text;
  updated screenshots are included below.

## Example

Input sent through the application's existing conversion route:

```text
The probability is 1/2. We obtain f(x) = x^2 + 3x. Einstein's equation E = mc^2 relates mass and energy.
The sequence has terms a_n = a_(n-1) + d. The value of x_i is stored in MAX_RETRY_COUNT.
```

Verified fixture response:

```markdown
The probability is $\frac{1}{2}$. We obtain $f(x) = x^2 + 3x$. Einstein's equation $E = mc^2$ relates mass and energy.
The sequence has terms $a_n = a_{n-1} + d$. The value of $x_i$ is stored in MAX_RETRY_COUNT.
```

Adversarial examples in the same actual conversion fixture:

```text
Assignments stay ordinary prose: x = value, x = y, x = 3, and TIMEOUT = 30.
Prices are $5 and $100; a price before math is $5 then $x+1$,
and math before a price is $y$ costs $100. Independent expressions $x$ and $y$ remain separate.
Explicit numeric math $1/2$ remains an expression.
```

The Chrome run confirmed ordinary assignments and prices remain literal text,
while each explicitly delimited expression produces a KaTeX annotation.

The full shared fixture is
[`markdown-regression-output.md`](../docs/evaluations/t301/markdown-regression-output.md).
The Chrome evidence is
[`markdown-render.png`](../docs/evaluations/t301/markdown-render.png) for the
converted fixture and
[`markdown-render-raw-math.png`](../docs/evaluations/t301/markdown-render-raw-math.png)
for bare notation inside source prose.

## Verification actually run

Latest correction verification:

- `git fetch origin main` — passed; latest main and branch merge-base are
  `2cf878a3290e697b408ebdb5d58871690e2c030b`.
- `uv run --locked --no-sync python tests/text_views.py` — passed with the
  expanded ordinary-assignment and currency fixture; actual API route and
  source-byte preservation checks remain enabled.
- `uv run --with playwright python browser_checks/t301_markdown_math.py` —
  passed in real Chrome, checking 25 fixture KaTeX spans and seven raw math
  spans plus literal assignment/currency/code preservation; screenshots were
  recaptured.
- `npm run typecheck && npm run build` — passed; Vite emitted its existing
  large chunk advisory.
- `./sigma test` — passed all steps, including Ruff, formatting, Pyright,
  frontend typecheck, production build, and repository tests. Output is archived
  at [`full-test.txt`](../docs/evaluations/t301/full-test.txt).
- `git diff --check` — passed after all changes.

- `uv run --locked --no-sync python tests/text_views.py` — passed. Calls the
  real `POST /api/projects/text/convert` endpoint with a deterministic mocked
  provider transport; validates request instructions, one provider dispatch,
  stored output and unchanged source bytes.
- `uv run --with playwright python browser_checks/t301_markdown_math.py` —
  passed in real Chrome against the production `RenderedMarkdown` component
  served by Vite. Verified the TeX annotations for 20 KaTeX spans in the
  converted fixture and seven bare math expressions in source prose, including
  the quadratic roots' grouped square root and fraction. Also checked
  identifiers, inline and fenced code, GFM table/list, blockquote,
  URL/path/date/version, currency, escaped and unmatched delimiters. Captured
  both screenshots linked above.
- `npm ci --no-audit --no-fund`, `npm run typecheck`, and `npm run build` —
  passed. Vite emitted the existing advisory for a chunk over 500 kB.
- `./sigma test` — all steps passed, including Ruff, formatting, Pyright,
  frontend typecheck, and production build. Full output is
  [`full-test.txt`](../docs/evaluations/t301/full-test.txt).
- `git diff --check` — passed.

## Acceptance

- **MET:** Existing conversion prompt, deterministic AST recognition and
  KaTeX rendering cover in-sentence math, fractions, subscripts, mixed
  identifiers, multiple equations, Markdown structures, code and malformed or
  escaped delimiters. Shared API/render regression and full suite pass.
- **UNVERIFIED:** Live model classification and semantic-preservation quality.
  No provider calls were made. One optional live request through the existing
  text-conversion path would check the representative corpus. Approximate cost
  is around $0.01 for this fixture at the default model; at configured request
  limits, up to about $0.10 using current standard API pricing. Actual token
  usage and billing path may differ. Current pricing:
  https://developers.openai.com/api/docs/pricing.
- **UNMET:** None in deterministic local acceptance.

## Final review status

- **MET:** Conservative equation classification, literal currency handling
  around explicit delimiters, adversarial API/browser regression coverage,
  source-byte preservation, browser screenshots, typecheck/build/full suite,
  and latest-main reconciliation (no divergence).
- **UNVERIFIED:** Live model semantic classification and quality. No paid/live
  provider calls were made.
- **UNMET:** None known.

**Final tested implementation HEAD:** `54b7903c3b202324952c39cf07681c45c6c7e111`.
All code, fixture and evidence changes were tested at this commit; the handoff
update is a documentation-only commit on top. **Provider calls/cost:** zero.

No provider call, paid inference, credential access, or project data change
occurred. Formatting does not verify a mathematical claim.
