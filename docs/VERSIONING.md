# SIGMA release versions

The product version is the `[project].version` value in `pyproject.toml`. The frontend's `package.json` version must match. Vite checks this at build time and embeds the product version alongside the existing Git build commit in the About dialog.

For each release, update both version fields together, run `./sigma test`, and build and deploy from the intended commit. Tag the tested release commit using the same version prefixed with `v`. The build identifier is the commit SHA, not the release version. Do not increment the product version for every development commit.

Production is v0.1.5. The v0.1.6 release candidate is being prepared from merged main; update the Python project metadata, uv lock, frontend package metadata, and npm lock together. Do not tag `v0.1.6` until its selected commit has passed deployment acceptance and the operator authorizes the tag. The build identifier is the full source commit SHA.
