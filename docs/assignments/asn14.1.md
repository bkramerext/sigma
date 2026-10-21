# A14.1: Plain, Markdown, Rendered — lazy AI text representations

**Status:** Ready for Codex implementation after A14.

## Objective

Provide a compact, **copper-themed three-view dropdown** for research text:

- **Plain:** ordinary readable text with conventional ASCII mathematics, such as `a_n`, `>=`, `F_{n+2}`, and `1/3`. It is **not** a display of escaped LaTeX markup and must not be obtained by simply stripping Markdown delimiters.
- **Markdown:** the separate stored source body with Markdown prose and embedded LaTeX math, such as `$a_n$`, `$n \\ge 0$`, `$F_{n+2}$`, or `$$...$$`. Display **literal editable/source text** when selected; do not typeset it in this view.
- **Rendered:** a **deterministic, read-only preview of the Markdown body** using Markdown + LaTeX typesetting. This is NOT a third stored text body and never requires an additional AI call.

These are distinct representations of the same mathematical/research content, and **Plain and Markdown need AI for conversion in either direction**. The AI-generated conversion is a **lazy, persisted cache**, not a browser-only transformation, automatic reformatting of legacy records, or a repeated charge whenever someone switches views.

This work is **A14.1**, a follow-up to A14's completed agentic Generate Strategy prototype. It does **not** change how strategies are researched, evaluated, generated, challenged or saved. See `docs/HUMAN-AI-INTERACTION.md` and `docs/agent-output-design.md`.

## User experience

1. Put a small `View` selector with **Plain · Markdown · Rendered** near the **project research-problem description**. Use the same reusable view component on expanded **strategy approach/description** content. Keep the surrounding workspace layout and typography intact.
2. Match SIGMA's **dark navy and burnished copper** UI: restrained copper border, copper-highlighted selection/focus and accessible contrast; reuse the existing shared styling/tokens, not new gold/yellow controls. Avoid a large toolbar or a separate page.
3. For legacy stock projects and existing human-authored descriptions (whose current fields are plain text), initially choose **Plain**, preserving the original characters verbatim. When Markdown is already available, prefer **Rendered** on a fresh display; optionally remember the viewer's last selection locally. Switching displays must not change the underlying content.
4. When the selected view's stored representation exists **and is current**, show it immediately, without network/provider calls, loading or cost. Rendered draws from current Markdown.
5. When Markdown/Rendered is requested but only Plain exists, show an understated **Generate Markdown** action explaining that a **single AI conversion request** will be sent using the project's current selected model/thinking/account. Clicking is explicit authorization for that request; merely opening the page or changing the selector does **not** send billable AI traffic.
6. When Plain is requested but only Markdown exists, offer **Generate Plain** in the same manner. Convert mathematical meaning into simple readable ASCII conventions, not raw TeX tokens or Markdown source.
7. During conversion, show a subtle copper working indicator and `Converting to Markdown…` / `Converting to Plain…`; allow cancellation and report a truthful error without losing the source. On success, save the conversion durably and show the requested view. Do not declare success until storage succeeds. No fictional percentage/progress.
8. If the AI connection is unavailable or the selected model unsupported, keep available representations viewable/editable and show a clear way to connect/retry later. Do not silently swap providers, models, thinking effort or billing mode.
9. If a conversion exists but is **stale**, clearly mark it `Out of date`. Never silently show it as current. Permit inspecting the previous text if useful, and explicitly **Regenerate** from the current authoritative source; do not discard the previous result prematurely. An unchanged source must never trigger another conversion automatically.
10. Preserve keyboard use, dropdown semantics, focus restoration, reduced motion, text selection/copy, screen-reader status, small screens, and the project's vertically resizable description pane.

### Editing and authority

- **Two independent persisted bodies, one authoritative source.** Support Plain-authored and Markdown-authored content. The selected **view** is not itself an edit to the content. An explicit edit and Save in Plain or Markdown becomes the new authoritative source, leaving the other representation as an inspectable but **stale** derivation until regenerated or separately reconciled.
- Rendered is **never** a separate editor. A user edits the Markdown source then views its deterministic Rendered counterpart.
- When converting, store the result as a **derived representation** with metadata: its originating source format, exact source revision/content digest, creation timestamp and model/provider/thinking attribution. Source text must stay byte-for-byte unchanged by the conversion.
- Preserve both texts and conversion history sufficiently to distinguish an original authored body, an AI conversion and a stale previous conversion. Do not claim AI-created text is human-authored.
- For project or strategy edits, preserve existing identity, strategy history, metadata and concurrency safeguards. If the original text changes while a provider call is pending, reject the stale conversion result rather than attach it to a new revision.
- Plain text already stored in existing project fields remains valid without conversion. Preserve backwards reads of existing project schemas without rewriting on open. On first representation write, migrate safely using the project's existing atomic locking, validation and backup conventions. Choose a clear backward-compatible persistent schema or companion representation structure, document it, and test migration from versions 1–6. Do not create a nonportable browser-only cache.
- **Important:** All domain consumers, including agentic generation, duplicate/novelty checking, CLI and API, must use the **current authoritative representation**, never an obsolete counterpart. Avoid losing Markdown math when feeding prompts. Legacy consumers requiring plain fields must continue to receive meaningful compatible content or an explicit current-source field; do not silently fall back to stale Plain.
- Stock `examples/*/project.json` source fixtures are immutable. Converted representations live in the user's managed/opened copy. Reopening a stock project must reuse previously saved conversions without touching or re-converting the source fixture.

## AI conversion contract

- Implement a small shared, explicit **single-conversion service** that reuses current OpenAI connection/auth, model/thinking selection, billing-mode binding, bounded context/deadline/output, provider error handling and cancellation. **No agent swarm or research iteration** is necessary for formatting conversion.
- Convert **Plain → Markdown+LaTeX** or **Markdown+LaTeX → Plain ASCII conventions**. Instructions must prioritize strict semantic preservation: retain every qualifier, assumption, mathematical assertion, quantifier, numerical constant, scope and caveat. Preserve ordinary prose unless minor markup is needed for readability; do not solve, prove, invent, summarize, strengthen or weaken the research problem.
- Beware ambiguous tokens: `a_n` might mean a subscript in mathematics but an underscore in code; `F_{n+2}` is conventional math but strings and code fences should not be rewritten. Preserve uncertainties or surface an actionable conversion warning rather than confidently altering meaning. Avoid pretending equivalence is mathematically verified by the model.
- Ask for one bounded structured output body and optional public warnings/ambiguity notes. Validate the returned text is nonempty, within stored field limits and plausibly preserves the source. Validation cannot establish mathematical equivalence: label the conversion **AI-generated; review before relying on it**.
- Treat project and strategy content as **untrusted data**, not executable provider instructions. Don't send secrets or unrelated project data: this service needs only the selected text and limited disambiguating context (research mode/topic if necessary). Respect the account identity and selected provider throughout.
- Every request is explicitly triggered and cancellable; **no retries, cascaded conversions, scheduled refreshes or conversion-on-view by default**. Concurrent identical conversion requests should be rejected or coalesced safely; conflicting edits should not overwrite user-authored content. Cache by the actual text revision/hash and direction, not just the view label.
- A successful conversion's **durable save is automatic after the user explicitly clicks Generate**, not a second manual confirmation step; the canonical authored source remains unchanged. If the user later edits that result, normal explicit Save promotes it to an authored source and invalidates the counterpart as needed.

## Deterministic Markdown / LaTeX renderer

- Use one shared safe React renderer, e.g. `react-markdown` + `remark-math` + `rehype-katex` and KaTeX styles; support standard `$...$` inline and `$$...$$` display math. If also supporting ChatGPT-style `\\(...\\)` / `\\[...\\]`, normalize those delimiters carefully or test that parsing handles them correctly. Do not claim support if the parser prints the escape sequences literally.
- Render only from **persisted Markdown source**, never by on-the-fly regex guesses from Plain.
- Disable raw HTML/script execution; KaTeX `trust=false`, safe URL/link schemes, bounded input size, no execution-capable embedded content. Do not load untrusted external resources by default.
- Preserve line breaks, paragraphs, lists and math display without creating horizontal viewport overflow or breaking existing scroll/focus behavior. Use accessible labels/source previews; honor reduced-motion preference.
- **Rendered ⇄ Markdown switching is always a local formatting change with no AI request.**

## Real project example and expected behavior

Use existing stock **Nonconsecutive Subset Sums Modulo 3** as the main regression fixture **without modifying its checked-in ASCII description**. Current source includes:

```text
For each integer n >= 0, let a_n count the subsets S of {1,...,n}
...
Determine a_12 exactly. Finally prove that a_n/F_{n+2} tends to 1/3,
where F_0=0 and F_1=1 are the Fibonacci numbers.
```

After the user selects Markdown/Rendered and explicitly chooses **Generate Markdown**, a *possible correct conversion* should contain LaTeX for `n \\ge 0`, `a_n`, `a_{12}`, the Fibonacci subscripts `F_{n+2}, F_0, F_1` and the ratio `\\frac{a_n}{F_{n+2}}`. The mathematical limit should be preserved faithfully, e.g. `$\\lim_{n\\to\\infty}\\frac{a_n}{F_{n+2}}=\\frac13$`; don't hardcode that exact prose, format or display equation as the universal conversion.
- **Plain:** shows the unchanged stock ASCII text, *not* escaped LaTeX.
- **Markdown:** shows the stored literal Markdown and math delimiters.
- **Rendered:** shows the same Markdown text with genuine mathematical typesetting.
- After closing and reopening the stock project, both Plain and Markdown still exist, and switching is instant and free.
- Independently test the **Markdown → Plain** direction with a Markdown-authoritative fixture; expected Plain conventions are legible and lossy by design but must not look like `\\frac{...}{...}`.
- Source changes mark previously derived text stale; an in-flight conversion of the prior source cannot overwrite it. The immutable repository fixture remains unchanged.

## Verification and delivery

- Implement typed backend services/API, the shared React view control and renderer, and explicit conversion UX without changing unrelated layout/artwork.
- Add deterministic **mock-provider** scenarios for each conversion direction, source immutability, durable cache reuse across reload/server restart, exact 0 provider calls on cached view switches, invalidation/revision hashes, cancellation, disconnect, stale save conflict, invalid/oversized/malformed responses, unavailable account, changed account/model, disabled UI, source editing and legacy migration. No paid calls in tests.
- Add real-browser checks at desktop and mobile widths for dropdown labels, copper styling, inline/display math, literal source visibility, working and failure states, source edit/preview, stale warnings, and no layout overflow. Confirm that cached switching generates **no network requests**.
- Integrate the content representation with `Generate with AI` prompts so that the authoritative text and its mathematical meaning reach the coordinator; keep A14's agent logic otherwise unchanged.
- Keep CLI/API consistent with shared service; do not rewrite legacy project fixtures. Run `./sigma test`, frontend typecheck/build, relevant Chrome/Playwright checks, update `docs/STATUS.md`/`docs/DECISIONS.md` with actual results and rationale, and commit/push code changes with a SHA.
- Preserve all approved Home/project artwork and copper design; do not regenerate any raster assets or modify the critical-line dots here.

## Non-goals

AI-generated scenarios (A12), another research agent, model-led mathematical proof checking, automatic conversion of all project content, automatic charges on page load/view changes, rewriting shipped example files, HTML editing, and general rich-text editor redesign.
