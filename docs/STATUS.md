# SIGMA status

## #436 Unified Project Types

Acceptance review for `red/436-project-types`:

| Criterion | Status | Evidence |
|---|---|---|
| One source-controlled built-in catalog; per-owner durable custom types with validation and isolation | MET | `src/sigma/data/builtin_project_types.json`, `src/sigma/project_types.py`, `tests/project_types.py` |
| Required name/scope; optional description/based-on; icon and reference URLs; unique names | MET | Service and API persistence tests; rejected duplicate and unsafe URL tests |
| Based-on copies values independently without runtime inheritance | MET | Project Types dialog copies parent values and icon; stored custom record has independent values and origin metadata |
| Literature/open-book icon; Stories of Your Life uses Literature; Other absent from available catalog | MET | Built-in catalog and sample project data; Chrome catalog check |
| Existing project/session/export compatibility and project-owned type snapshots | MET | Schema 11 migration, existing project/session tests, delete/export browser check |
| Canonical icon rendering, custom encoded icon persistence, Math-only LEAN behavior metadata | MET | Catalog renderer, data URI persistence/validation tests, built-in behavior assertion |
| Project Types navigation/dialog, read-only built-ins, editable custom types, groups, ordering, references, Save/Cancel | MET | `browser_checks/project_types_436.py`; real Chrome screenshots under `docs/evaluations/t436/evidence/` |
| AI icon edit endpoint uses built-in icon references; no uploads; failure preserves prior icon | MET (mocked) | `src/sigma/project_type_icons.py`, mocked request/failure tests |
| Real paid AI icon generation using an operator-connected API key | UNVERIFIED | No live provider call was authorized. Endpoint is disabled by default with `SIGMA_PROJECT_TYPE_IMAGE_GENERATION_ENABLED`; model/account billing is the user's separate OpenAI API billing. |
| Deleted-type warning, safe snapshot continuation or replacement, unsafe-snapshot blocking, no silent reassignment | MET | Service/API tests and real Chrome deletion/start-warning/export flow |
| Running sessions remain frozen if a type is deleted; references are retained without changing methodology or paper authoring | MET | Session records freeze project type settings; reference fields are stored only. #440/#443 integration behavior was not changed. |
| #440/#443 coordination status | UNVERIFIED | The GitHub issue lookup returned 404 for both references in this environment; no implementation dependency was taken. |

### Verification

- `./sigma test` — PASS (all steps).
- `npm run typecheck` and `npm run build` — PASS.
- `ruff check`, `ruff format --check`, and `pyright` — PASS.
- Real Chrome acceptance — PASS using the local deterministic API fixture, with no provider calls. It creates a custom type, verifies copied open-book icon and ordering, deletes the type while a project refers to it, confirms the project remains open/exportable and its snapshot remains in the downloaded bundle, and checks that the modal warning appears before any session/config request. Screenshots are in `docs/evaluations/t436/evidence/`.
- `tests/epistemic_continuity.py` reports its existing optional graph-present case as skipped because the local Python sandbox image is unavailable; graph-withheld checks pass.
