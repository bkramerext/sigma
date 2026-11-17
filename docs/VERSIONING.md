# SIGMA release versions

The product version is the `[project].version` value in `pyproject.toml`. The frontend's `package.json` version must match. Vite checks this at build time and embeds the product version alongside the existing Git build commit in the About dialog.

For each release, update both version fields together, run `./sigma test`, and build and deploy from the intended commit. Create a version tag only when the operator explicitly requests one. The build identifier is the commit SHA, not the release version. Do not increment the product version for every development commit.

Production is v0.4.3 at exact merged `main` SHA `613b14156adf8b0a0856ce2eda3cac2cf89d9b07` (PR #886, including #885). The Python project metadata and frontend package metadata are aligned at 0.4.3. The operator accepted the production candidate on November 17, 2026. The build identifier is the full source commit SHA.
