"""Disposable T202 paper fixture. All provider traffic uses MockTransport."""

import json
import os
from pathlib import Path
from uuid import uuid4

from browser_checks import provider_fixture as fixture
from sigma import papers, research_sessions
from sigma.projects import create_strategy, initialize_project

root = Path(os.environ["SIGMA_PROJECTS_ROOT"])
path = root / "t202-paper.sigma"
view = initialize_project(path, "T202 paper fixture", "Investigate a bounded mathematical question")
strategy = create_strategy(
    path, "Saved strategy", "Investigate a bounded recurrence."
).project.strategies[0]
archive = json.loads(
    Path(
        "docs/evaluations/fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"
    ).read_text()
)
session = archive["research_sessions"][0]
session_id = str(uuid4())
for artifact in session["artifacts"]:
    artifact.update(
        id=str(uuid4()), project_id=view.project.id, session_id=session_id, strategy_id=strategy.id
    )
session.update(
    id=session_id,
    project_path=str(path),
    project_id=view.project.id,
    strategy_id=strategy.id,
    strategy_title=strategy.title,
    strategy_text=strategy.approach,
    status="ended",
)
research_sessions._save(str(path), session)
info = Path(os.environ["SIGMA_T202_INFO"])
call_log = info.with_suffix(".calls")
call_log.unlink(missing_ok=True)
info.write_text(json.dumps({"path": str(path), "session": session_id, "calls": str(call_log)}))
original_handler = fixture.handler


async def fake_handler(request):
    if request.method != "GET":
        with call_log.open("a", encoding="utf-8") as stream:
            stream.write(json.loads(request.content)["text"]["format"]["name"] + "\n")
    return await original_handler(request)


fixture.handler = fake_handler
# The compiler is an isolated deterministic stand-in; the saved TeX is produced by SIGMA.
papers._compile_pdf = lambda *args, **kwargs: b"%PDF-1.4\n% T202 fixture\n%%EOF\n"
app = fixture.app
