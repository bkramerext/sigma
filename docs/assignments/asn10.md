# A10: Static copper slogan artwork on Home

**Status:** Ready for implementation once the approved source image is available in the repository.

## Objective

Replace the small upper-left Home slogan with a **non-interactive static graphic derived directly from the approved copper-lettering still image**. Preserve the original engraved serif letterforms, copper reflections, diagonal beam, and atmospheric dust. Do not attempt to recreate the approved still with CSS gradients, SVG typography, particles, canvas, JavaScript animation or a new image-generation pass.

The approved source is the still image depicting the complete phrase:

**STRATEGY · INVESTIGATION · GENERATION · MEASUREMENT · ASSESSMENT**

It has enlarged initial capitals, a copper engraved finish, sharp local reflections, a visible light beam from a cursor, and dust against a dark background. The original still is **one line**. Preserve that exact design rather than silently reconstructing it as two lines. The earlier two-line layout was intended to accommodate an interactive/retypeset alternative; this assignment prioritizes pixel fidelity to the accepted still.

## Required asset

A copy of the exact approved source image must be added to the repository as `assets/sigma-copper-slogan-reference.png` (original 1672 × 941 PNG). A lossless crop of the same approved image spanning its illuminated lettering/beam is also available from the design handoff as `sigma-copper-slogan-banner.png` (1672 × 490, cropped from y=235 through y=724). Keep original source intact.

**Asset handoff is mandatory.** If the source image is missing, stop and ask for it. Do not fetch a visually similar stock graphic, generate a replacement, or synthesize a near-match. A textual assignment alone cannot transfer a binary image.

## Layout and integration

- Use the actual approved raster artwork, not a typographic recreation. The image already encodes the exact engraved surface, edge highlights, dust and beam; all of those remain **static**.
- Replace only the current Home top-line slogan element. Inspect the current React Home markup (`frontend/src/main.tsx`), `.home-topline` in `frontend/src/style.css`, and the existing background asset before editing. Keep the Home background, metallic SIGMA artwork, upper-right AI connection control, and project-entry functionality intact.
- The source image includes a very dark background. It must **not** appear as an opaque rectangular insert that hides the approved Home artwork. Test an unobtrusive blend (for example `mix-blend-mode: screen`) or derive a transparent foreground from the approved raster **without redrawing the letters or discarding the beam/dust**. Evaluate visually in a real browser. If integrating it cleanly proves impossible, report that instead of substituting newly rendered lettering.
- Present at a comfortably readable desktop size and maintain the source aspect ratio. Avoid stretching, distorted letter spacing, clipping important words or covering functional UI. Account for the existing Home composition; do not place the artwork where it obscures the central metallic emblem or dialog/entry actions.
- On narrow layouts, use a deliberate accessible fallback if the whole image would become illegibly small. Keep the complete slogan available as text to assistive technology. Do not distort the artwork to force it onto mobile.
- The image is decoration, not a control: no hover effect, pointer reaction, script-driven light, canvas overlay, cursor trail, or loop animation. Respect reduced-motion preferences automatically by introducing no motion.
- Static interface text may be non-selectable, but do not disable selecting/copying user-entered research content.

## Verification

1. Verify source fidelity: the committed source PNG is the exact approved image, and derived crops/transparency preserve the source's engraved copper, specular highlights, visible beam and dark dust.
2. Open Home in a real browser and inspect at 1440×900, 1280×720, 390×844, and 320×700. Check with the real original Home artwork behind the graphic; do not assess it on a fabricated plain background.
3. Verify the complete slogan remains readable and does not overlap or diminish the ConnectionStatus control or the Home actions. For mobile, verify an explicit responsive alternative rather than unreadably shrinking the long raster.
4. Verify the image is truly static; moving the cursor anywhere on the page does not alter the graphic. No runtime rendering loop should be added.
5. Run `./sigma test`, frontend typecheck/build and the relevant existing Home browser checks. Update verification notes as normal; do not claim tests that were not run.

## Out of scope

No cursor lighting, kinetic typography, WebGL, simulated physics, interactive scintillation, material reconstruction, new background artwork, homepage redesign or alteration to the project workspace. Keep scope strictly to a tasteful static Home slogan rendered from the approved image.
