"""Isolated T201 browser fixture with a deterministic in-process fake provider."""

import json
import os
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import httpx

from browser_checks import provider_fixture as fixture
from sigma import research_sessions
from sigma.projects import create_strategy, initialize_project
from tests.research_sessions import investigation, provider_response, skeptic

root = Path(os.environ["SIGMA_PROJECTS_ROOT"])
path = root / "t201-overflow.sigma"
view = initialize_project(path, "T201 overflow fixture", "A bounded mathematical question")
strategy = create_strategy(
    path, "Overflowing strategy", "Investigate boundary cases."
).project.strategies[0]
archive = json.loads(
    Path(
        "docs/evaluations/fixtures/t17-8-answer-free/live-session-91e96112-27ce-412e-841f-5cbf67cbba75.json"
    ).read_text()
)
session = archive["research_sessions"][0]
session_id = str(uuid4())
template = session["artifacts"][0]
artifacts = []
for i in range(25):
    artifact = deepcopy(template)
    artifact.update(
        id=str(uuid4()),
        project_id=view.project.id,
        session_id=session_id,
        strategy_id=strategy.id,
        sequence=i + 1,
        open_obligations=[f"Resolve fixture boundary obligation {i}."],
    )
    artifact["skeptic_output"] = {}
    artifacts.append(artifact)
session.update(
    id=session_id,
    project_path=str(path),
    project_id=view.project.id,
    strategy_id=strategy.id,
    strategy_title=strategy.title,
    strategy_text=strategy.approach,
    status="completed",
    artifacts=artifacts,
)
research_sessions._save(str(path), session)
limits = research_sessions.get_limits(str(path))
research_sessions.save_limits(str(path), {**limits, "research_rounds": 1, "model_calls": 2})
index = research_sessions._prior_session_obligations_index(str(path), str(uuid4()), [strategy.id])
call_log = Path(os.environ["SIGMA_T201_INFO"]).with_suffix(".calls")
call_log.unlink(missing_ok=True)
Path(os.environ["SIGMA_T201_INFO"]).write_text(
    json.dumps(
        {
            "path": str(path),
            "session": session_id,
            "strategy": strategy.id,
            "omitted": index[4][strategy.id][0],
            "calls": str(call_log),
        }
    )
)
original_handler = fixture.handler


async def safe_handler(request):
    if request.method == "GET":
        return await original_handler(request)
    payload = json.loads(request.content)
    kind = payload["text"]["format"]["name"]
    if kind not in {"research_investigator", "research_skeptic"}:
        raise AssertionError(f"Unexpected provider fixture call: {kind}")
    with call_log.open("a", encoding="utf-8") as stream:
        stream.write(kind + "\n")
    output = investigation(1) if kind == "research_investigator" else skeptic(1)
    return httpx.Response(200, json=provider_response(output))


fixture.handler = safe_handler
app = fixture.app
