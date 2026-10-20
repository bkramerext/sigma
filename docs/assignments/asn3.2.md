# ASN-3.2: SIGMA visual identity and Home page

Context: ASN-3 establishes Home and Project; ASN-3.1 adjusts the Fork menu. This is the approved visual-design implementation.

## Visual source and assets

- Approved generated references from the design conversation (2026-10-20): a cinematic metallic Σ/SIGMA image and a landscape with blue/gold mathematical waves concentrated at the upper-right and lower-right.
- **Repository assets supplied here:** `assets/sigma-logo.svg` (transparent mark/wordmark) and `assets/sigma-atmosphere.svg` (transparent atmospheric overlay). These are **vector recreations of the direction**, not the original generated PNGs. The originals have not been transferred to GitHub; do not claim pixel-identical reproduction.
- The visual standard is **wonder, restraint, anticipation**. This should feel like the threshold to scientific exploration, not a generic dashboard.

## Home implementation

- Make the **whole page** a continuous deep navy-to-black canvas, not a rectangular image/card. Use the supplied SVGs as independent visual layers and improve them as needed to match the approved reference.
- Position atmospheric fields against the **top-right and bottom-right viewport edges**. Keep both anchored as viewport aspect ratio changes; do not center/stretch a single bitmap. The logo should be a focal point, with a quiet area for project selection.
- Use subtle blue/gold lighting, mathematical curves and the RH hints (`ζ(s)`, `Re(s) = ½`). These are references to SIGMA's origin, not research results.
- Compose the launcher as a polished, legible part of the environment. Maintain accessible contrast, obvious actions and focus states.
- Consider a single restrained entrance sequence: faint lines/waves emerge, then the illuminated mark; no looping spectacle. Disable movement for `prefers-reduced-motion`.
- Do not hardcode one screenshot's dimensions. Check large desktop, tall viewport, 390px and 320px mobile.

## Research workspace

- Put `assets/sigma-logo.svg` (or an improved transparent equivalent) at the top, scaled to a compact header mark.
- **True alpha transparency**, not a rectangle whose color happens to match the background.
- Keep the workspace readable, calm and functional; carry over the palette as restrained accents. The Home page is dramatic; the working environment is a scientific instrument.

## Engineering and verification

- Preserve project opening, navigation, persistence, strategies and contextual commands. Do not add research features.
- Prefer modular CSS/SVG and minimal components; no heavyweight theme framework.
- Verify with a real browser at desktop, narrow and tall sizes. Inspect both cloud anchors, launcher contrast, header transparency, focus and reduced-motion behavior.
- Run `./sigma test` and relevant browser checks; record **actual** results in `docs/STATUS.md`.
- Commit and push implementation with a precise message. Do not represent SVG recreations as the original generated raster artwork.

## Acceptance standard

Not just dark styling: the Home page should inspire **awe and curiosity**, and opening a project should feel like moving from mystery into a serious research workspace. If the first visual pass looks generic, revise before delivery.
