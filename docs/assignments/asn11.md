# A11: Copper Home controls and project catalog toggle

**Status:** Ready for Codex implementation after A10.

## Objective

Refine the existing SIGMA Home screen without changing its approved copper artwork. Replace the current Recent Projects-only area with a two-state **Recent Projects / Stock Projects** segmented toggle, and bring Home controls into the burnished copper palette rather than yellow-gold.

## Visual requirements

- Preserve the exact A10 slogan image, Sigma/background artwork, composition, diagonal beam, and dust. Do not regenerate, crop anew, animate, or replace the approved artwork.
- Keep deep navy backgrounds and cool blue atmospheric elements. Change Home control accents from yellow/gold to **burnished reddish copper**. Reference tones: deep copper `#75402f`, burnished `#a96548`, reflected highlight `#cd9270`, dark bronze `#593428`.
- Retain a convincing, restrained metallic **gradient** on primary buttons (reference: `linear-gradient(115deg, #75402f 0%, #cd9270 48%, #a96548 72%, #593428 100%)`). Use accessible text contrast, visible keyboard focus, and hover/disabled states.
- The toggle should look native to this aesthetic: understated dark navy inactive tab, subtle copper border, copper-gradient selected tab, legible labels. Avoid bright yellow and generic oversized pill styling.
- Apply coordinated copper accents to Home secondary controls, list actions, selected/focus states, and dialogs where applicable, without indiscriminately recoloring unrelated workspace screens.
- Keep the slogan, connection status, Σ/SIGMA artwork, Open/New Project actions, and project section clear and unobstructed. Check narrow screens and laptop viewports.

## Recent Projects tab

- Default tab on initial Home load.
- Show **at most four** projects, sorted by most recently accessed, with existing Open and Forget behaviors, unavailable-project messaging, and loading/error handling.
- Recent entries represent projects the user has actually opened or created. Stock examples must **not** be inserted automatically into recents during installation/startup. Opening a working copy of a stock project should place that working copy in recents.
- Enforce the four-item limit at the source/API as appropriate, not merely by visually hiding surplus entries. Keep the existing recent-project persistence behavior otherwise.

## Stock Projects tab

- Display **all** shipped preconfigured investigations, with no four-item limit and no artificial recency ordering. Initially include the existing mathematical nonconsecutive-subset-sums and historical Jesus/cannabis examples. Catalog should discover or enumerate stock examples in an extensible way, not hardcode a two-entry limit.
- Clearly distinguish stock templates from user work. Selecting a stock project must **create/open an independent working copy** through the normal project creation/opening workflow, without modifying the stock template or its canonical source. Repeated use must be possible, with distinct destination names/IDs and no silent overwrite.
- Present helpful titles and research-mode labels, with accessible actions and useful empty/error states.
- A stock project's presence in the catalog must not make it appear in Recents. Only the user's created/opened working copy belongs there.
- If a destination is needed, use an existing appropriate local-project workflow or ask for it in UI; don't silently write into the checked-in examples directory.

## Engineering expectations

- Inspect current Home, recent-project API/storage, example-installation/startup logic, and tests before editing. Existing versions currently render `RecentProjects` directly in `frontend/src/main.tsx` and load `/api/projects/recent`; do not assume stock catalog endpoints already exist.
- Keep frontend and backend changes narrow, coherent, and covered by tests. Add/adjust tests for four-item recency cap, ordering, absence of auto-seeded examples, unlimited stock enumeration, independent copy creation, and template immutability. Cover switching tabs, opening, keyboard accessibility, and responsive layout.
- Preserve backwards compatibility with already-installed stock examples or existing recent records: do not delete user projects or research history while removing auto-seeding. Existing genuine user recents remain available.
- Run relevant tests/build and report results and any remaining limitations. Do not claim visual verification unless actually performed.

## Out of scope

New artwork, dynamic light effects, new research-engine behavior, cloud hosting, authentication, or a broad sitewide visual redesign.
