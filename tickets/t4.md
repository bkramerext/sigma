# ASN-4: Implement the approved SIGMA visual mockup

**Status:** Ready for implementation once the exact approved PNG assets are copied into the repository. This assignment is a visual implementation specification, not authorization to reinterpret the design.

## Canonical reference: approved 2026-10-20 split-screen mockup

The split-screen image is a layout reference **only**: its LEFT Home artwork is a degraded regeneration and MUST NOT be reproduced. Its RIGHT project-workspace layout is approved. The original full-width Home image is the sole authoritative visual source for the Home artwork. The original generated image is available in the design conversation. **Do not use the earlier simplified SVGs as the reference or claim that they are equivalent.**

The approved earlier **1536 × 1024 full-width Home background image** (metallic Σ at upper center, deep navy negative space on left, luminous blue/gold mathematical waves on upper and lower right) remains the *Home background asset*. The split-screen mockup supplies *UI placement and project workspace layout only*, never replacement Home artwork. These are complementary, not competing, approvals.

### Asset handoff — blocking requirement

1. Copy the exact original Home background PNG from the conversation into `assets/sigma-home-background.png`.
2. Copy the exact approved split-screen UI mockup PNG into `assets/sigma-home-and-project-pages.png`.
3. Verify both are the real 1536 × 1024 original PNGs, not redrawn approximations or screenshots of a chat window. Preserve bytes and visual details. Do not proceed to signoff without these two files. The generated artwork has not yet been uploaded to GitHub as of writing this assignment.
4. Create `assets/sigma-header-logo.png` as a **genuinely transparent** extraction of the same metallic Σ + SIGMA mark, matching the mockup. No rectangular background or faux transparency. Use a high-resolution source and inspect edges. Do not replace it with the existing simplified `sigma-logo.svg`.
5. Make runtime assets accessible under `frontend/public/` (copied or via an appropriate build step), with canonical originals retained in `assets/`. No remote image services.

## Home page (left mockup panel)

- Use the **exact approved full-width Home background** as the foundation. The mockup illustrates UI placement only; its regenerated Home art is rejected. Preserve the dramatic blue/copper waves and mathematical notation at the right, with deep dark negative space under controls. Do not rebuild the image in CSS or SVG.
- Metallic, illuminated Σ centered near the upper part of the original artwork, with spaced SIGMA wordmark and concise subtitle. Avoid a second redundant logo overlay if the background already includes the mark.
- Place the **Open a Project** dark translucent panel on the left beneath the branding, as in the mockup: warm copper heading, brief explanatory text, directory path input with folder icon, Browse affordance, and primary copper/gold **Open Project →** action.
- Show **Recent Projects** below as a restrained list with copper folder icons, thin rules and subdued labels. **Do not fabricate recent-project history**: populate only from real persisted data if available; otherwise use an honest empty state. The project names visible in the concept image are illustrative, not seeded records.
- Use warm copper-to-gold metallic gradients on the primary action and icon accents, subtle bronze outlines and highlights, cool blue atmospheric contrast. No flat orange dashboard styling.
- Preserve the existing directory-entry and project-opening functionality. A Browse control must genuinely work if shown; if the local browser security model cannot browse arbitrary folders, provide a truthful supported interaction rather than an inert button.

## Project page (right mockup panel)

- A full-width dark header with the **compact transparent metallic Σ SIGMA logo** at upper left, then the small subtitle “Strategy Investigation, Generation, Measurement & Assessment”.
- Right-side current project selector/title and restrained utility controls **only when functional**. Do not add decorative, inert settings or theme buttons.
- Left vertical navigation in a narrow, almost-black rail. Warm copper outline icons and a softly illuminated active item. The mockup labels are **Overview, Notes, Research, Experiments, Analysis, References, Tasks**; map these to real existing capabilities where applicable. Future features must be clearly disabled/marked as coming later, not fabricated or represented as working.
- Main pane: generous spacing, quiet typography, thin slate borders, copper focus states. Header identifies the opened project. A Project Overview panel and compact secondary panels may show real project information; **do not invent notes, research runs, timestamps, or experiment results** to fill out the reference layout.
- Preserve existing strategy pool, create/edit/remove operations, navigation, persistence and disabled future commands from ASN-3. Do not replace real working surfaces with empty concept cards.
- Keep the workspace atmospheric only through colors, borders and logo. **No cosmic wave background on the project page**.

## Layout and visual fidelity

- The approved split-screen is a **side-by-side design presentation**, **not** a requirement to show Home and Project simultaneously in the app. Each is its own route/view. Reproduce each panel's composition and styling at full viewport width.
- Use the approved artwork and mockup as the visual benchmark for spacing, hierarchy, typography, color, glow and density. The mockup is a visual contract, not a source of invented product features.
- Responsive desktop, tablet, 390px and 320px mobile. Preserve art subject and right-edge waves without stretching or obscuring essential controls; prioritize readable interactions. Use accessible labels, keyboard navigation, visible focus and adequate contrast. Honor reduced-motion preference.
- Maintain a coherent copper/bronze + cool-blue palette. Resist introducing new visual concepts or redesigning the approved art.

## Implementation and validation

1. Confirm the **two exact PNG reference assets** exist under `assets/` before beginning; stop and report a missing-asset blocker rather than silently substituting SVG approximations.
2. Implement the Home overlay and project workspace in the existing React/Vite app. Reuse real application state and existing FastAPI interfaces; avoid speculative APIs.
3. Open the running app in a real browser. Compare screenshots of Home and Project to their respective halves of the approved mockup, and compare the Home background to the exact full-width art. Inspect desktop, tall, tablet and mobile.
4. Run `./sigma test`, frontend build/type checks, and relevant interactive browser checks. Record actual commands and results in `docs/STATUS.md`.
5. No fabricated projects, content, active tools or functionality. If a mockup control cannot be implemented in this assignment, mark it honestly or omit it while retaining the overall layout.
6. Commit implementation only after assets, functional checks and visual verification are complete. Report any remaining differences explicitly.

## Acceptance

The user should recognize the **exact original Home artwork** (never the degraded left mockup) and the right-hand workspace layout: the full-width cosmic Home artwork with the coppery launch UI, and the quiet project workspace with the same compact metallic identity, rail and real working content. The two images must be stored under `assets/` and the running app must use the exact Home background. Existing core behavior must remain intact.
