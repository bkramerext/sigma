# Synthetic paper-generation control pair

`paper.pdf` and `paper-text-only.pdf` were rendered from the same frozen sample-project snapshot and the same deterministic mock draft. The latter removes only the optional diagram field. The project contains no research sessions, so these publications are renderer fixtures, **not research findings**. No provider call was made. Both PDFs were compiled with the local SIGMA Tectonic path.

The TeX sources, fixture draft, sample project export, frozen snapshot, and SHA-256 values are retained here. `manifest.json` records the shared snapshot hash and the source code commit (`9a736b39`) used for rendering. The diagram is an illustrative proposal and does not represent a MindRouter federation deployment.

The diagram PDF is three US Letter pages; its architecture figure is on page 2. I rendered and visually inspected that page: node labels, numbered arrows, edge legend, trust-boundary outline and caption are legible. The text-only control is also three pages and has no TikZ figure.
