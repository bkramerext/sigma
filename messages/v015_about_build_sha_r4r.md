# RED R4R — v0.1.5 About build SHA

**Issue:** #337 follow-up: production About showed build `unknown`.
**Branch:** `red/v015-about-build-sha`, based on current `main` at
`db560f3ab0014d7b455ad7a114a65e3d2bf37fd2`.
**Cause:** release images are built from a Git archive, which has no `.git`;
the frontend Docker build did not receive the requested source SHA. Vite's
fallback therefore rendered `unknown`.

**Correction:** `deploy/release_image.py` passes the full release SHA to the
frontend Docker build as `SIGMA_BUILD_COMMIT`. The frontend Dockerfile exposes
that value to Vite; Vite embeds the seven-character prefix. Added a regression
assertion and made the release runbook require checking the generated bundle.

**Verification:** `python3 tests/release_image.py` passed (3 tests). A frontend
production build with `SIGMA_BUILD_COMMIT=aa23f4b393f4ef657471705f467f9beecbb0689a`
passed and emitted `aa23f4b` into the JavaScript bundle. `git diff --check`
passed. Full `./sigma test`, exact-head CI, merged release build, and production
verification remain pending.

No paid provider calls or production changes occurred during this correction.
No local SIGMA server was contacted. Existing authorization for self-review,
self-merge, and the bounded v0.1.5 quick-patch deployment applies; do not tag
v0.1.5 without separate authorization.
