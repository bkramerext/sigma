# SIGMA release versions

The product version is the `[project].version` value in `pyproject.toml`. The frontend's `package.json` version must match. Vite checks this at build time and embeds the product version alongside the existing Git build commit in the About dialog.

For each release, update both version fields together, run `./sigma test`, and build and deploy from the intended commit. Tag the tested release commit using the same version prefixed with `v`. The build identifier is the commit SHA, not the release version. Do not increment the product version for every development commit.

Release `0.1.1` was the prior production version. The current release target is `0.1.4`; update the Python project metadata, uv lock, frontend package metadata, and npm lock together. Tag `v0.1.4` only after its selected commit has passed verification and deployment acceptance.
