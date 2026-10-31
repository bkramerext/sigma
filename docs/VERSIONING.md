# SIGMA release versions

The product version is the `[project].version` value in `pyproject.toml`. The frontend's `package.json` version must match. Vite checks this at build time and embeds the product version alongside the existing Git build commit in the About dialog.

For each release, update both version fields together, run `./sigma test`, and build and deploy from the intended commit. Create a version tag only when the operator explicitly requests one. The build identifier is the commit SHA, not the release version. Do not increment the product version for every development commit.

Production is v0.1.6 at `0e51d20341ea5656f971e075b466694393e25d97`. The v0.1.7 candidate is being prepared from the latest merged `main`, including domain-authorization PR #389 and maintenance-page PR #385. Update the Python project metadata, uv lock, frontend package metadata, and npm lock together. Deploy the exact tested and merged mainline SHA. No separate release tag is part of this deployment. The build identifier is the full source commit SHA.
