# T301 Blue handoff — Context-aware mathematical Markdown

**State:** R4R  
**Branch:** `blue/t301-math-markdown` → `main`  
**Base:** `2cf878a3290e697b408ebdb5d58871690e2c030b`  
**Head:** `c3c0dcbc589f90bb3dfa428e48743bcc291f1169`

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

The full shared fixture is
[`markdown-regression-output.md`](../docs/evaluations/t301/markdown-regression-output.md).
The Chrome evidence is
[`markdown-render.png`](../docs/evaluations/t301/markdown-render.png).

## Verification actually run

- `uv run --locked --no-sync python tests/text_views.py` — passed. Calls the
  real `POST /api/projects/text/convert` endpoint with a deterministic mocked
  provider transport; validates request instructions, one provider dispatch,
  stored output and unchanged source bytes.
- `uv run --with playwright python browser_checks/t301_markdown_math.py` —
  passed in real Chrome against the production `RenderedMarkdown` component
  served by Vite. Verified 20 KaTeX spans and preserved identifiers, inline
  and fenced code, GFM table/list, blockquote, URL/path/date/version, currency,
  escaped and unmatched delimiters. Captured the screenshot linked above.
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

No provider call, paid inference, credential access, or project data change
occurred. Formatting does not verify a mathematical claim.
