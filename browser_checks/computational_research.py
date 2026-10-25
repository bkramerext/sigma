"""Actual SIGMA Python/Sage sessions under offline provider transport.

Never patches execute, Docker, clocks, output, status or sandbox limits. Uses
isolated copies of the retained actual Increment 3 project and stock Algorithm
Design. Before/after exports come from SIGMA's API. No live provider calls.
"""

import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/evaluations/increment_4"
EXPORTS = OUT / "exports"
EXPORTS.mkdir(parents=True, exist_ok=True)
SCRATCH = Path(tempfile.mkdtemp(prefix="sigma-blue-computational-")).resolve()
PROJECTS = SCRATCH / "projects"
PROJECTS.mkdir()
prior = json.loads((ROOT / "docs/evaluations/increment_3/exports/MANIFEST.json").read_text())
SOURCE = Path(prior["projects"][0]["path"])
SUBSET = PROJECTS / "nonconsecutive-subset-sums.sigma"
shutil.copytree(SOURCE, SUBSET)
source_hashes = {
    str(p.relative_to(SOURCE)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in SOURCE.rglob("*")
    if p.is_file()
}
for file in (SUBSET / "research-sessions").glob("*.json"):
    if file.name in {"limits.json", "sequence.json"}:
        continue
    record = json.loads(file.read_text())
    record["project_path"] = str(SUBSET)
    file.write_text(json.dumps(record, indent=2))

FAILED = "1cc6ec50-87c0-46f4-b1dd-a82857d74f9e"
DP = "5e15b337-adf1-483c-8ba6-7cd2de5f500b"
GAP = "516c2288-3458-40b2-9e02-87a918c35a3a"
SUBSET_QUESTION = "Test the local candidate a_(n+6)=4*a_(n+3)+a_n against exact finite nonconsecutive subset counts. If it fails, preserve the witness and choose a phase/boundary discriminating test. Do not recycle the refuted short recurrence or infer the global recurrence or density limit."
GRAPH_QUESTION = "Test the local insertion conjecture: starting from a DAG, accepting an absent edge u->v whenever the reverse edge v->u is absent preserves acyclicity. Compare against recomputation on a bounded exhaustive graph family. Preserve failures; the full dynamic algorithm, update semantics and complexity remain unresolved."
CASES = SCRATCH / "cases.json"
CASES.write_text("{}")


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


a = port()
api_url = f"http://127.0.0.1:{a}"
env = {k: v for k, v in os.environ.items() if not k.startswith(("SIGMA_", "OPENAI_", "ANTHROPIC_"))}
for key in ["SIGMA_STATE_DIR", "SIGMA_AUTH_HOME", "SIGMA_CLOUD_AUTH_HOME"]:
    directory = SCRATCH / key
    directory.mkdir(mode=0o700)
    env[key] = str(directory)
env.update(
    SIGMA_PROJECTS_ROOT=str(PROJECTS),
    OPENAI_API_KEY="offline-computation-control-only",
    SIGMA_AI_MODEL="gpt-6.1-sol",
    SIGMA_COMPUTATION_CASES=str(CASES),
    SIGMA_COMPUTATION_CAPTURE=str(SCRATCH / "captures.jsonl"),
)


def launch():
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "browser_checks.computation_provider:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(a),
        ],
        cwd=ROOT,
        env=env,
        start_new_session=True,
        stdout=(SCRATCH / "api.txt").open("a"),
        stderr=subprocess.STDOUT,
    )


def ready(process):
    for _ in range(200):
        if process.poll() is not None:
            raise RuntimeError((SCRATCH / "api.txt").read_text()[-6000:])
        try:
            with urlopen(api_url + "/openapi.json", timeout=1):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Server unavailable")


def req(route, data=None, method=None):
    request = Request(
        api_url + (route if route.startswith("/") else "/api/projects/" + route),
        data=json.dumps(data).encode() if data is not None else None,
        method=method,
        headers={"Content-Type": "application/json", "Origin": "http://127.0.0.1:5173"},
    )
    try:
        with urlopen(request, timeout=25) as response:
            return json.loads(response.read())
    except Exception as exc:
        if hasattr(exc, "read"):
            raise RuntimeError(exc.read().decode()) from exc
        raise


def export(path, label):
    paths = []
    for route, suffix in [
        ("export", ".audit.json"),
        ("current-understanding", ".current-understanding.json"),
    ] + [("export/report", ".report." + fmt) for fmt in ["txt", "html", "tex"]]:
        query = {"path": str(path)}
        if ".report." in suffix:
            query["format"] = suffix.rsplit(".", 1)[-1]
        with urlopen(
            api_url + "/api/projects/" + route + "?" + urlencode(query), timeout=25
        ) as response:
            raw = response.read()
        file = EXPORTS / (label + suffix)
        file.write_bytes(raw)
        paths.append(str(file.relative_to(ROOT)))
    return paths


def limits(path, calls=4, rounds=2):
    previous = req("research-limits?" + urlencode({"path": str(path)}))
    req(
        "research-limits",
        {
            **previous,
            "path": str(path),
            "model_calls": calls,
            "research_rounds": rounds,
            "session_duration_minutes": 5,
            "maximum_estimated_cost_usd": None,
        },
        "PUT",
    )


def strategy(path, scenario, mode, parent=None):
    question = SUBSET_QUESTION if scenario == "subset" else GRAPH_QUESTION
    title = f"Computational feedback: {scenario} / {mode}"
    if parent:
        preview = req(
            "continuations/proposal?" + urlencode({"path": str(path), "parent_strategy_id": parent})
        )
        view = req(
            "continuations/approve",
            {
                "path": str(path),
                "parent_strategy_id": parent,
                "title": title,
                "question": question,
                "preview_digest": preview["preview_digest"],
                "source_artifact_ids": [FAILED, DP, GAP],
            },
        )
    else:
        view = req("strategies", {"path": str(path), "title": title, "approach": question})
    identifier = view["project"]["strategies"][-1]["id"]
    cases = json.loads(CASES.read_text())
    cases[identifier] = {"scenario": scenario, "mode": mode}
    CASES.write_text(json.dumps(cases))
    return identifier


def start(path, identifier):
    project = req("open", {"path": str(path)})["project"]
    config = req("proposals/config?" + urlencode({"path": str(path)}))
    return req(
        "research-sessions/start",
        {
            "path": str(path),
            "strategy_id": identifier,
            "strategy_ids": [identifier],
            "expected_project_id": project["id"],
            "expected_binding": config["binding"],
            "idempotency_key": str(uuid4()),
        },
    )


def get(path, identifier):
    return req("research-sessions/" + identifier + "?" + urlencode({"path": str(path)}))


def wait(path, identifier, *, expect_failed=False):
    deadline = time.monotonic() + 160
    while time.monotonic() < deadline:
        session = get(path, identifier)
        if session["status"] not in {"queued", "running"}:
            if expect_failed:
                assert (
                    session["status"] == "failed" and "Computational feedback" in session["message"]
                ), session
            else:
                assert session["status"] not in {"failed", "paused"}, (
                    session["status"],
                    session["message"],
                )
            return session
        time.sleep(0.1)
    raise RuntimeError("Session did not finish")


manifest = {
    "app_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "isolated_root": str(SCRATCH),
    "transport": "offline HTTP script; actual unmodified SIGMA Python/Sage Docker execution",
    "live_provider_calls": 0,
    "actual_cost_usd": 0,
    "accounting": "Synthetic provider token/cost accounting inputs; no billing. Actual container wall durations are saved in execution records.",
    "preflight": "Two actual application execute() diagnostics outside research sessions confirmed Python 3.12.8 and SageMath 10.8. They are not research findings or included in new-session execution counts.",
    "projects": [],
    "runs": [],
}
api = launch()
try:
    ready(api)
    req("/api/ai/mode", {"mode": "api_key"})
    subset = req("open", {"path": str(SUBSET)})["project"]
    parent = subset["strategies"][0]["id"]
    graph = req("samples/open", {"sample_id": "algorithm-design"})
    GRAPH = Path(graph["path"])
    before_subset = export(SUBSET, "subset.before")
    before_graph = export(GRAPH, "algorithm.before")
    for scenario, path, parent_id in [("subset", SUBSET, parent), ("graph", GRAPH, None)]:
        for mode in ["actual", "withheld"]:
            limits(path)
            sid = strategy(path, scenario, mode, parent_id)
            session = wait(path, start(path, sid)["id"])
            manifest["runs"].append(
                {
                    "scenario": scenario,
                    "mode": mode,
                    "project_id": session["project_id"],
                    "session_id": session["id"],
                    "strategy_id": sid,
                    "calls_used": session["calls_used"],
                    "artifact_ids": [a["id"] for a in session["artifacts"]],
                }
            )
    for mode in ["error", "timeout", "sage", "invalid_feedback"]:
        limits(SUBSET, 2, 1)
        sid = strategy(SUBSET, "subset", mode, parent)
        session = wait(SUBSET, start(SUBSET, sid)["id"], expect_failed=mode == "invalid_feedback")
        manifest["runs"].append(
            {
                "scenario": "subset",
                "mode": mode,
                "project_id": session["project_id"],
                "session_id": session["id"],
                "strategy_id": sid,
                "calls_used": session["calls_used"],
                "artifact_ids": [a["id"] for a in session["artifacts"]],
            }
        )
    # Real backend death after a durable execution reservation, before terminal
    # write. The recovered run must be interrupted, never replayed as success.
    limits(SUBSET)
    sid = strategy(SUBSET, "subset", "restart", parent)
    started = start(SUBSET, sid)
    for _ in range(300):
        executions = req("research-executions?" + urlencode({"path": str(SUBSET)}))["executions"]
        running = next(
            (
                e
                for e in executions
                if e.get("session_id") == started["id"] and e["status"] == "running"
            ),
            None,
        )
        if running:
            break
        time.sleep(0.02)
    assert running, "No durable running execution observed"
    os.killpg(api.pid, signal.SIGKILL)
    api.wait(timeout=10)
    time.sleep(0.2)
    api = launch()
    ready(api)
    recovered = get(SUBSET, started["id"])
    assert recovered["status"] == "paused"
    frozen = recovered["approved_continuations"]
    req(
        "research-sessions/" + started["id"] + "/control", {"path": str(SUBSET), "action": "resume"}
    )
    resumed = wait(SUBSET, started["id"])
    assert resumed["approved_continuations"] == frozen
    executions = req("research-executions?" + urlencode({"path": str(SUBSET)}))["executions"]
    same = [e for e in executions if e.get("session_id") == resumed["id"]]
    assert any(e["status"] == "interrupted" for e in same), same
    assert len(same) == 2 and any(e["status"] == "completed" for e in same), same
    manifest["runs"].append(
        {
            "scenario": "subset",
            "mode": "restart",
            "project_id": resumed["project_id"],
            "session_id": resumed["id"],
            "strategy_id": sid,
            "calls_used": resumed["calls_used"],
            "artifact_ids": [a["id"] for a in resumed["artifacts"]],
            "interrupted_execution_id": running["id"],
        }
    )
    after_subset = export(SUBSET, "subset.after")
    after_graph = export(GRAPH, "algorithm.after")
    manifest["projects"] = [
        {
            "slug": "nonconsecutive-subset-sums",
            "path": str(SUBSET),
            "project_id": subset["id"],
            "source": "Isolated path-rebound copy of the actual retained Increment 3 project: five historical deterministic fixture sessions, four prior offline scripted sessions and preserved approval companions. New execution is separately identified.",
            "before": before_subset,
            "after": after_subset,
        },
        {
            "slug": "algorithm-design",
            "path": str(GRAPH),
            "project_id": graph["project"]["id"],
            "source": "Fresh stock Algorithm Design sample with no sessions/strategies, then evaluator-authored bounded local conjectures; no complete solution or counterexample key supplied.",
            "before": before_graph,
            "after": after_graph,
        },
    ]
    captures = (SCRATCH / "captures.jsonl").read_bytes()
    (OUT / "transport-captures.jsonl").write_bytes(captures)
    manifest["offline_provider_calls"] = len(captures.splitlines())
    # Export exact execution service responses and retrieve every captured file
    # through SIGMA's hash/size-checked artifact endpoint (no direct reconstruction).
    for project in manifest["projects"]:
        path = Path(project["path"])
        records = req("research-executions?" + urlencode({"path": str(path)}))["executions"]
        relevant = {
            run["session_id"]
            for run in manifest["runs"]
            if run["project_id"] == project["project_id"]
        }
        for record in records:
            if record.get("session_id") not in relevant:
                continue
            eid = record["id"]
            with urlopen(
                api_url
                + "/api/projects/research-executions/"
                + eid
                + "?"
                + urlencode({"path": str(path)}),
                timeout=25,
            ) as response:
                raw = response.read()
            (EXPORTS / f"execution.{eid}.json").write_bytes(raw)
            for artifact in record.get("artifacts", []):
                name = artifact["filename"]
                with urlopen(
                    api_url
                    + "/api/projects/research-executions/"
                    + eid
                    + "/artifacts/"
                    + name
                    + "?"
                    + urlencode({"path": str(path)}),
                    timeout=25,
                ) as response:
                    raw = response.read()
                assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]
                (EXPORTS / f"execution.{eid}.{name}").write_bytes(raw)
    assert all(
        hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() == value
        for name, value in source_hashes.items()
    )
    (EXPORTS / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(
        json.dumps(
            {
                "result": "PASS",
                "root": str(SCRATCH),
                "sessions": len(manifest["runs"]),
                "offline_calls": manifest["offline_provider_calls"],
                "exports": str(EXPORTS),
            },
            indent=2,
        )
    )
finally:
    if api.poll() is None:
        os.killpg(api.pid, signal.SIGTERM)
        api.wait(timeout=15)
