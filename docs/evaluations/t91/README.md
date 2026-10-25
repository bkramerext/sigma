# T91 local packaged Compose acceptance

This increment exercises the application built from the current `main` commit
through the local Compose edge proxy, packaged Nginx frontend, and FastAPI
backend. It does not exercise Vite. The browser creates a stock sample project,
edits and saves the project description and strategy title, reloads and reopens
it, checks its saved sessions and outcomes, downloads the HTML report, and
repeats the project reopen after forcing backend container recreation. A second
simulated user is denied the first user's project, export, and session evidence.

Run with `./deploy/validate-local.sh` on a machine with Docker Compose, uv, and
the Chrome executable configured by `SIGMA_BROWSER_EXECUTABLE` (default:
`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`). The check uses
disposable local secrets, sessions, and Compose volumes and removes them at exit.
It makes no external Google or inference-provider calls.

## Acceptance matrix

| Check | Result | Evidence or limitation |
| --- | --- | --- |
| Packaged Compose frontend/API/edge and stock sample catalog | PASS | Chrome used the local Compose URL; project path was inside the authenticated user's workspace. |
| Sample copy, project and strategy edits, save, reload, reopen | PASS | Stable project and strategy IDs and edited fields persisted through API inspection and UI reopen. |
| Saved sessions and outcomes | PASS | Five saved sessions loaded; first session showed its Mixed outcome and research artifacts. |
| Report download | PASS | HTML report downloaded through the application's Export dialog and contained the edited title and report sections. |
| Backend container recreation | PASS | Forced backend recreation; same simulated session reopened the project with unchanged IDs and edits. |
| User B isolation from User A project/artifacts | PASS | B's Recent list omitted it; inspect, export, and session/evidence requests returned 404. |
| Local deployment smoke | PASS | Packaged images built, services became healthy, and auth SQLite remained through backend restart and full container recreation. |
| Real Google OAuth | SKIPPED | Browser used ephemeral sessions inserted into disposable local auth storage. This tests authenticated app behavior, not Google sign-in or OAuth. |
| Compiled PDF download | SKIPPED | No saved compiled PDF fixture was available; generating one would require provider work. |
| T100 persistent-disk backend | SKIPPED | This run used Compose's default local storage configuration. T100's separate persistent-disk acceptance is documented in `docs/evaluations/t100/README.md`. |
| T99 inference generation | SKIPPED | No inference was requested; no paid provider calls were made. |

## Scope

This is a local acceptance increment for the current hosted-workspace Compose
path, not evidence of production cloud deployment or a completion claim for all
of T91. Real OAuth, this run's persistent-disk configuration, PDF availability,
and T99 inference remain separate acceptance work.
