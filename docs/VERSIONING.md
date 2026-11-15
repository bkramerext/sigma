# SIGMA release versions

The product version is the `[project].version` value in `pyproject.toml`. The frontend's `package.json` version must match. Vite checks this at build time and embeds the product version alongside the existing Git build commit in the About dialog.

For each release, update both version fields together, run `./sigma test`, and build and deploy from the intended commit. Create a version tag only when the operator explicitly requests one. The build identifier is the commit SHA, not the release version. Do not increment the product version for every development commit.

Production is v0.1.7 at exact merged `main` SHA `802e9b6b7da5829868070f760e17280cd8a927f2`, including domain-authorization PR #389 and maintenance-page PR #385. The Python project metadata, uv lock, frontend package metadata, and npm lock are aligned at 0.1.7. No separate release tag was created. The build identifier is the full source commit SHA.
