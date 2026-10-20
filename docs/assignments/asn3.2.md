# ASN-3.2: SIGMA visual identity and Home page

Context: ASN-3 provides the project launcher and research workspace. ASN-3.1 relocates Fork under Actions. This assignment applies the approved visual direction without changing research behavior.

## Goal

Make the **entire Home page** feel like the approved SIGMA artwork: deep navy/near-black, luminous icy blue and restrained warm gold, mathematical diagrams, and flowing wave/cloud fields. Keep the project launcher legible and functional. Give the **Project workspace** a compact, transparent-background variant of the SIGMA logo in its top header.

## Approved visual direction

Two generated reference images were approved in chat on 2026-10-20:
1. A large metallic Greek capital sigma with SIGMA wordmark, blue/gold illumination and subtle mathematical diagrams on a dark field.
2. A wider Home composition: smaller SIGMA emblem near the upper middle, broad quiet dark space on the left, bright wave/cloud fields on the **upper-right and lower-right**, with subtle zeta/RH mathematical references.

**Asset handoff:** The images currently exist as conversation-generated PNG files, not in the GitHub repository. Do not pretend they are already available in the checkout. Obtain the approved images from the project owner before final visual verification, or implement a faithful, maintainable CSS/SVG recreation and explicitly note the difference. Do not use unrelated stock imagery or silently replace the approved design.

## Home

- Theme the whole viewport, not a framed hero card. Dark navy/black base with icy blue and gold accents.
- Anchor atmospheric cloud/wave effects to **top-right and bottom-right**; they should remain anchored on resizing, including tall/narrow viewports. Do not stretch a fixed raster image in a way that moves or distorts them.
- Keep enough negative space for the launcher and make all project actions readable with sufficient contrast.
- Preserve the RH tease: subtle mathematical graphics such as `ζ(s)` and `Re(s) = 1/2`. These are atmospheric references, not claims of results.
- Avoid excessive animation and respect reduced-motion preferences.
- Keep responsive layout, focus states, and accessibility intact.

## Research workspace

- Use a **transparent-background** SIGMA mark/wordmark in the top header, smaller and quieter than Home.
- Do not place a dark rectangular image behind the header logo.
- Keep the research content restrained and easy to read for long sessions. Carry the palette into subtle accents rather than replicating Home's atmospheric effects across the working surface.
- Prefer a proper transparent asset (SVG if faithful, otherwise alpha-channel PNG); do not fake transparency with a background-colored rectangle.

## Engineering boundaries

- Preserve all project navigation, project data, strategy creation, command hierarchy, and disabled-action explanations.
- Keep visuals modular: separate mark/wordmark, atmosphere, and page content. Avoid hardcoded screenshot-sized positioning.
- Prefer a small set of well-structured styles/components over introducing a theming framework.
- No fake functionality, no changes to research persistence or agent behavior.

## Verification and delivery

1. Inspect Home and Project in a real browser at desktop, 390px and 320px widths, and a tall viewport; verify upper-right/lower-right anchors and readable launcher.
2. Check keyboard navigation, focus contrast, and reduced motion.
3. Verify the workspace logo has genuine transparency and remains legible on its actual header.
4. Run `./sigma test` and relevant browser checks; record observed results in `docs/STATUS.md`.
5. Commit and push the implementation with a specific message. If approved image assets are unavailable, report that blocker and do not claim visual fidelity was verified.

## Scope

This is a visual/UI assignment only. Do not add research features, restructure the workspace, or change the research model.
