# Gray spec: README link to Why SIGMA?

**Owner:** Gray
**Current branch:** `gray/t79-unused-images`
**Purpose:** Explain **why SIGMA exists**, not the engineering challenge of building it and not personal motivation or an origin story.

## Copy ownership and target

- The approved, fuller narrative is already committed on this branch at **`docs/WHY_SIGMA.md`**. Treat that file as the canonical prose for README readers. It covers five ideas in natural prose: (1) research continuity rather than one-off plausible answers; (2) Investigator/Skeptic disagreement that changes the research; (3) evidence and epistemic distinctions; (4) cross-domain research with different evidence standards; (5) a falsifiable comparison against simpler assistants. It explicitly **does not assert demonstrated superiority**.
- **Do not paste the full narrative into `README.md`**. Add a prominent, natural link in the README opening, adjacent to the opening product statement, with link text **[Why SIGMA?](docs/WHY_SIGMA.md)**. The existing README features, setup, and limits should remain intact.
- The coordinator has inserted the link on this branch. Review its placement; refine only if readability materially benefits, while preserving all unrelated README edits and the asset-cleanup work.
- Do not add sections on implementation complexity, how the project originated, the creator, or how many agents were used to build SIGMA.
- Do not conflate intended benefits with validated outcomes: the current research-quality caveats in README must remain.
- Preserve the exact sentence **"And we're prepared to simplify SIGMA if the answer is no."** in both the README opening and the linked `docs/WHY_SIGMA.md`. Its candid willingness to abandon needless complexity is an essential part of the product purpose, not optional marketing polish.
- Verify the relative Markdown link, inspect README preview and the linked document, and report commit/test status back to the coordinator. No direct agent-to-agent coordination.
- Green separately owns shorter, collapsible About copy on `green/about-polish`; Gray should not edit Green's UI branch.

**Acceptance:** README exposes a discoverable Why SIGMA link and the separate document is legible standalone, accurately describes the research purpose, and does not overclaim validation.
