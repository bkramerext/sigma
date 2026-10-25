# Green spec: Why SIGMA? in About

**Owner:** Green
**Current branch:** `green/about-polish`
**Scope:** Add one collapsible, prose-first section titled **Why SIGMA?** near the top of the existing About dialog. This is product-purpose copy, not an explanation of engineering difficulty or the creator's motivation.

## Exact approved copy

### Why SIGMA?

AI can produce convincing answers, but a convincing answer is not necessarily good research. Difficult questions need continuity: what was learned, what failed, and what remains unknown should shape the next investigation.

SIGMA treats research as cumulative work. Different strategies can be pursued over time, while an Investigator develops ideas and a Skeptic challenges their assumptions and conclusions. The point is not simply to have agents disagree, but to turn criticism into better questions, stronger evidence, and more useful progress.

Claims also need to remain distinguishable from their support. A proposed explanation, a recorded computation, and an independently established result are not the same thing. SIGMA aims to preserve those distinctions across mathematics, science, history, and other complex investigations, while respecting different standards of evidence.

The real test is whether this process produces better research than a simpler AI assistant using comparable resources. **That is SIGMA's hypothesis, not a proven advantage.** And we're prepared to simplify SIGMA if the answer is no.

## UI integration

- Insert a **collapsed by default**, native `<details>` disclosure with `<summary>Why SIGMA?</summary>` directly **after the opening About introduction and before** the existing terms/architecture flow. Keep it above "More capabilities".
- Keep the four paragraphs verbatim, including the final emphasis. This should feel like editorial prose, **not** five cards, a numbered list, a second flow diagram, or a promotional hero.
- Preserve existing About title, introduction, project/strategy/session/agent explanation, interactions, styling conventions, and focus/keyboard behavior. No layout redesign or new dependencies.
- Make the expanded section readable at desktop and narrow mobile widths, with sensible spacing; collapsed state must keep the About box compact.
- Check keyboard toggle and mobile overflow in real Chrome, alongside `./sigma test`; disclose any acceptance not actually exercised.
- This scope covers *why the product exists*, drawing only on the first five motivations: sustained research, productive critique, epistemic integrity, cross-domain use, and testable advantage. Exclude technical architecture difficulty and personal origin story.

**Coordination:** Gray owns the separate README-linked `docs/WHY_SIGMA.md` piece on Gray's branch. Do not edit README from this branch. Notify the coordinator with commit and verification; do not coordinate with Gray directly.
