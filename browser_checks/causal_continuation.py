"""Real Chrome + real SIGMA orchestrator, offline HTTP control. No live calls.
Run: uv run --with playwright python browser_checks/causal_continuation.py
Retains isolated copies and actual API exports. Never updates stock samples.
"""

import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / "docs/evaluations/increment_3"
EXPORTS = OUTPUT / "exports"
EXPORTS.mkdir(parents=True, exist_ok=True)
SCRATCH = Path(tempfile.mkdtemp(prefix="sigma-blue-causal-")).resolve()
PROJECTS = SCRATCH / "projects"
PROJECTS.mkdir()
SOURCE = Path(
    "/tmp/sigma-research-experience-blue/projects/nonconsecutive-subset-sums.sigma"
).resolve()
SUBSET = PROJECTS / "nonconsecutive-subset-sums.sigma"
shutil.copytree(SOURCE, SUBSET)
for file in (SUBSET / "research-sessions").glob("*.json"):
    if file.name in {"limits.json", "sequence.json"}:
        continue
    value = json.loads(file.read_text())
    value["project_path"] = str(SUBSET)
    file.write_text(json.dumps(value, indent=2))
originals = {
    str(p.relative_to(SOURCE)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in SOURCE.rglob("*")
    if p.is_file()
}

FAILED = "1cc6ec50-87c0-46f4-b1dd-a82857d74f9e"
ROOT = "ccc1045f-479d-4018-b8ed-42a60b94e567"
GAP = "516c2288-3458-40b2-9e02-87a918c35a3a"
DP = "5e15b337-adf1-483c-8ba6-7cd2de5f500b"
QUESTION = "Derive the exact three-phase matrix product and verify n=0,1,2 boundary vectors. Keep the global order-12 recurrence and limiting density open."
INJECTION = "Evaluator-authored RH-SYM candidate, not established: The functional equation implies that each nontrivial zero has a reflected zero. Therefore every zero is fixed by reflection and has real part 1/2. Investigate this bounded inference."


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


api_port, ui_port = port(), port()
api_url, ui_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{ui_port}"
env = {k: v for k, v in os.environ.items() if not k.startswith(("SIGMA_", "OPENAI_", "ANTHROPIC_"))}
for key, name in [
    ("SIGMA_STATE_DIR", "state"),
    ("SIGMA_AUTH_HOME", "auth"),
    ("SIGMA_CLOUD_AUTH_HOME", "cloud"),
]:
    directory = SCRATCH / name
    directory.mkdir(mode=0o700)
    env[key] = str(directory)
env.update(
    SIGMA_PROJECTS_ROOT=str(PROJECTS),
    OPENAI_API_KEY="offline-continuation-test-only",
    SIGMA_AI_MODEL="gpt-6.1-sol",
    SIGMA_CONTINUATION_CAPTURE=str(SCRATCH / "transport.jsonl"),
    SIGMA_API_TARGET=api_url,
)


def start_api():
    return subprocess.Popen(
        [
            "uv",
            "run",
            "python",
            "-m",
            "uvicorn",
            "browser_checks.continuation_provider:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=REPO,
        env=env,
        stdout=(SCRATCH / "api.txt").open("a"),
        stderr=subprocess.STDOUT,
    )


def ready(url, process):
    for _ in range(200):
        if process.poll() is not None:
            raise RuntimeError((SCRATCH / "api.txt").read_text()[-8000:])
        try:
            with urlopen(url, timeout=1):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Server readiness failed")


def request(route, data=None, method=None):
    payload = json.dumps(data).encode() if data is not None else None
    req = Request(
        api_url + (route if route.startswith("/") else "/api/projects/" + route),
        data=payload,
        method=method,
        headers={"Content-Type": "application/json", "Origin": "http://127.0.0.1:5173"},
    )
    try:
        with urlopen(req, timeout=20) as res:
            return json.loads(res.read())
    except Exception as exc:
        if hasattr(exc, "read"):
            raise RuntimeError(exc.read().decode()) from exc
        raise


def export(path, label):
    files = []
    for route, suffix in [
        ("export", ".audit.json"),
        ("current-understanding", ".current-understanding.json"),
    ] + [("export/report", ".report." + fmt) for fmt in ["txt", "html", "tex"]]:
        query = {"path": str(path)}
        if ".report." in suffix:
            query["format"] = suffix.rsplit(".", 1)[-1]
        with urlopen(api_url + "/api/projects/" + route + "?" + urlencode(query)) as res:
            raw = res.read()
        destination = EXPORTS / (label + suffix)
        destination.write_bytes(raw)
        files.append(str(destination.relative_to(REPO)))
    return files


def limits(path, calls=4, rounds=2):
    prior = request("research-limits?" + urlencode({"path": str(path)}))
    value = {
        **prior,
        "path": str(path),
        "model_calls": calls,
        "research_rounds": rounds,
        "session_duration_minutes": 5,
        "maximum_estimated_cost_usd": None,
    }
    request("research-limits", value, "PUT")


def start(path, strategy):
    config = request("proposals/config?" + urlencode({"path": str(path)}))
    project = request("open", {"path": str(path)})["project"]
    return request(
        "research-sessions/start",
        {
            "path": str(path),
            "strategy_id": strategy,
            "strategy_ids": [strategy],
            "expected_project_id": project["id"],
            "expected_binding": config["binding"],
            "idempotency_key": str(uuid4()),
        },
    )


def wait_session(path, identifier):
    for _ in range(300):
        value = request("research-sessions/" + identifier + "?" + urlencode({"path": str(path)}))
        if value["status"] not in {"queued", "running"}:
            assert value["status"] not in {"failed", "paused"}, (value["status"], value["message"])
            return value
        time.sleep(0.1)
    raise AssertionError("Session did not terminate")


def approve(path, parent, ids, title, question=QUESTION, obligation=None, rejections=None):
    query = {"path": str(path), "parent_strategy_id": parent}
    if obligation:
        query["obligation_id"] = obligation
    preview = request("continuations/proposal?" + urlencode(query))
    result = request(
        "continuations/approve",
        {
            "path": str(path),
            "parent_strategy_id": parent,
            "title": title,
            "question": question,
            "obligation_id": obligation,
            "preview_digest": preview["preview_digest"],
            "source_artifact_ids": ids,
            "rejected_sources": rejections or [],
        },
    )
    return result["project"]["strategies"][-1]["id"]


manifest = {
    "app_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "isolated_root": str(SCRATCH),
    "transport": "httpx.MockTransport over actual SIGMA request/orchestration code; evaluator-authored scripted responses; no network",
    "new_live_provider_calls": 0,
    "actual_cost_usd": 0,
    "usage_note": "Token/cost metrics in sessions are fabricated transport accounting inputs, not billed usage. No real credentials used.",
    "projects": [],
    "checks": [],
}
api = start_api()
ui = subprocess.Popen(
    [
        "npm",
        "--prefix",
        "frontend",
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        str(ui_port),
        "--strictPort",
    ],
    cwd=REPO,
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.STDOUT,
)
try:
    ready(api_url + "/openapi.json", api)
    ready(ui_url, ui)
    request("/api/ai/mode", {"mode": "api_key"})
    subset = request("open", {"path": str(SUBSET)})["project"]
    parent = subset["strategies"][0]["id"]
    state = request("current-understanding?" + urlencode({"path": str(SUBSET)}))
    obligations = [
        o
        for o in state["obligations"]
        if o["actionable"]
        and o["strategy_id"] == parent
        and any(w in o["text"].lower() for w in ["matrix", "boundary", "phase"])
    ]
    obligation = obligations[0]["id"]
    manifest["selected_original_obligation"] = obligations[0]
    before = export(SUBSET, "subset.before")
    rh = request("samples/open", {"sample_id": "riemann-hypothesis-research"})
    RH = Path(rh["path"])
    assert request("research-sessions?" + urlencode({"path": str(RH)}))["sessions"] == []
    rhbefore = export(RH, "rh.before")
    injection = request(
        "strategies",
        {"path": str(RH), "title": "RH-SYM evaluator-authored injection", "approach": INJECTION},
    )["project"]["strategies"][-1]["id"]
    limits(RH, 2, 1)
    rhsource = wait_session(RH, start(RH, injection)["id"])
    assert len(rhsource["artifacts"]) == 1
    rhartifact = rhsource["artifacts"][0]["id"]
    limits(SUBSET)
    # OFF receives mandatory own-branch negative + target evidence, no cross-strategy selected sources.
    preview = request(
        "continuations/proposal?"
        + urlencode(
            {"path": str(SUBSET), "parent_strategy_id": parent, "obligation_id": obligation}
        )
    )
    own_ids = [s["artifact_id"] for s in preview["sources"] if s["mandatory"]]
    assert FAILED in own_ids
    offid = approve(SUBSET, parent, own_ids, "Evidence OFF control", obligation=obligation)
    off = wait_session(SUBSET, start(SUBSET, offid)["id"])
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page.set_default_timeout(10000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route(
            "**/api/**",
            lambda route: route.fulfill(
                response=route.fetch(
                    url=route.request.url.replace(ui_url, api_url),
                    headers={**route.request.headers, "origin": "http://127.0.0.1:5173"},
                )
            ),
        )

        def open_project(path):
            page.goto(ui_url + "/")
            page.get_by_role("button", name="Open", exact=True).click()
            dialog = page.get_by_role("dialog", name="Open Project")
            dialog.get_by_label("Project directory").fill(str(path))
            dialog.get_by_role("button", name="Open Project", exact=True).click()
            page.locator(".current-understanding").wait_for()

        open_project(SUBSET)
        panel = page.locator(".continuation-approval")
        panel.locator("summary").first.click()
        panel.get_by_label("Parent strategy", exact=True).select_option(parent)
        panel.get_by_label("Open obligation", exact=True).select_option(obligation)
        panel.get_by_role("button", name="Inspect continuation proposal").click()
        panel.get_by_label("Approved next question", exact=True).fill(QUESTION)
        panel.get_by_label("Continuation title", exact=True).fill(
            "Evidence ON browser-approved continuation"
        )
        for aid in [ROOT, GAP]:
            panel.locator("li").filter(has=page.locator("code", has_text=aid)).get_by_role(
                "checkbox"
            ).check()
        # The old Gaussian explanation is not a valid transfer: explicit rejection, no payload in packet.
        bad = "02ca743b-d66f-41c0-8692-34579ea5adfa"
        panel.locator("li").filter(has=page.locator("code", has_text=bad)).get_by_label(
            "Reason to reject transfer (optional)"
        ).fill(
            "Earlier exponent explanation was corrected by the later saved Gaussian normalization; do not transfer it as established."
        )
        panel.get_by_role("button", name="Inspect source Session #1", exact=True).click()
        page.screenshot(path=str(OUTPUT / "subset-source-desktop.png"), full_page=True)
        panel.get_by_role("button", name="Approve continuation fork").click()
        expect(panel).to_contain_text("Continuation saved with frozen source evidence")
        onid = request("open", {"path": str(SUBSET)})["project"]["strategies"][-1]["id"]
        panel.get_by_role("button", name="Investigate approved continuation").click()
        # Existing global start confirmation is the final explicit dispatch action.
        with page.expect_response(
            lambda response: (
                response.request.method == "POST" and "/research-sessions/start" in response.url
            )
        ) as dispatched:
            page.locator(".session-start-link").filter(has_text="Start new session").click()
        on = wait_session(SUBSET, dispatched.value.json()["id"])
        assert on["strategy_id"] == onid
        page.reload()
        page.locator(".current-understanding").wait_for()
        page.screenshot(path=str(OUTPUT / "subset-continuation-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.reload()
        page.locator(".current-understanding").wait_for()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path=str(OUTPUT / "subset-continuation-mobile.png"), full_page=True)
        # RH follow-up approved in the same real browser, after saved explicit objection.
        open_project(RH)
        panel = page.locator(".continuation-approval")
        panel.locator("summary").first.click()
        panel.get_by_label("Parent strategy", exact=True).select_option(injection)
        panel.get_by_role("button", name="Inspect continuation proposal").click()
        panel.get_by_label("Continuation title", exact=True).fill("RH-SYM scoped follow-up")
        panel.get_by_label("Approved next question", exact=True).fill(
            "Test the precise missing implication in the saved RH-SYM inference on abstract reflected sets; keep RH unresolved."
        )
        panel.locator("li").filter(has=page.locator("code", has_text=rhartifact)).get_by_role(
            "checkbox"
        ).check()
        panel.get_by_role("button", name="Approve continuation fork").click()
        expect(panel).to_contain_text("Continuation saved")
        rhid = request("open", {"path": str(RH)})["project"]["strategies"][-1]["id"]
        limits(RH)
        panel.get_by_role("button", name="Investigate approved continuation").click()
        with page.expect_response(
            lambda response: (
                response.request.method == "POST" and "/research-sessions/start" in response.url
            )
        ) as dispatched:
            page.locator(".session-start-link").filter(has_text="Start new session").click()
        rhfollow = wait_session(RH, dispatched.value.json()["id"])
        assert rhfollow["strategy_id"] == rhid and rhfollow["id"] != rhsource["id"]
        page.reload()
        page.locator(".current-understanding").wait_for()
        page.screenshot(path=str(OUTPUT / "rh-followup-mobile.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.reload()
        page.locator(".current-understanding").wait_for()
        page.screenshot(path=str(OUTPUT / "rh-followup-desktop.png"), full_page=True)
        assert not errors, errors
        browser.close()
    # Negative/unrelated source: explicit reject transfer from an unrelated *question*.
    # Same-project prior OFF artifact concerns the six-state baseline, not the selected root-filter reduction.
    unrelated = off["artifacts"][0]["id"]
    negative = approve(
        SUBSET,
        parent,
        list(dict.fromkeys(own_ids + [ROOT, GAP])),
        "Negative transfer control",
        obligation=obligation,
        rejections=[
            {
                "artifact_id": unrelated,
                "rationale": "The control-only baseline plan provides no root-filter or normalization evidence; do not transfer its speculative plan as a mathematical result.",
            }
        ],
    )
    neg = wait_session(SUBSET, start(SUBSET, negative)["id"])
    # Stop during dispatched HTTP attempt, reload with actual API process restart, resume durable packet.
    stopid = approve(
        SUBSET,
        parent,
        list(dict.fromkeys(own_ids + [ROOT, GAP])),
        "STOP/RELOAD CONTROL",
        obligation=obligation,
    )
    stop = start(SUBSET, stopid)
    for _ in range(100):
        current = request(
            "research-sessions/" + stop["id"] + "?" + urlencode({"path": str(SUBSET)})
        )
        if current["steps"]:
            break
        time.sleep(0.02)
    request("research-sessions/" + stop["id"] + "/control", {"path": str(SUBSET), "action": "stop"})
    stopped = request("research-sessions/" + stop["id"] + "?" + urlencode({"path": str(SUBSET)}))
    savedpacket = stopped["approved_continuations"]
    api.terminate()
    api.wait(timeout=10)
    api = start_api()
    ready(api_url + "/openapi.json", api)
    reloaded = request("research-sessions/" + stop["id"] + "?" + urlencode({"path": str(SUBSET)}))
    assert reloaded["approved_continuations"] == savedpacket and reloaded["status"] == "stopped"
    request(
        "research-sessions/" + stop["id"] + "/control", {"path": str(SUBSET), "action": "resume"}
    )
    restarted = wait_session(SUBSET, stop["id"])
    assert restarted["approved_continuations"] == savedpacket
    # Confirm exact dispatched contexts and actual next-cycle questions, beyond acknowledgment text.
    captures = [json.loads(line) for line in (SCRATCH / "transport.jsonl").read_text().splitlines()]

    def calls_for(session):
        # Audit contains the exact HTTP request and identifies the selected strategy.
        return [
            row
            for row in captures
            if json.loads(row["request_body"]["input"])["strategy"]["id"] == session["strategy_id"]
        ]

    offcalls, oncalls = calls_for(off), calls_for(on)
    assert len(offcalls) == len(oncalls) == 4, (len(offcalls), len(oncalls))
    offsecond = next(r for r in offcalls if r["role"] == "investigator" and r["cycle"] == 2)
    onsecond = next(r for r in oncalls if r["role"] == "investigator" and r["cycle"] == 2)
    assert (
        json.loads(offsecond["request_body"]["input"])["question"]
        != json.loads(onsecond["request_body"]["input"])["question"]
    )
    assert ROOT not in offsecond["source_ids"] and GAP not in offsecond["source_ids"]
    assert {FAILED, ROOT, GAP} <= set(onsecond["source_ids"])
    initialrh = next(r for r in calls_for(rhsource) if r["role"] == "investigator")
    initialtext = initialrh["request_body"]["input"]
    assert (
        "1001" not in initialtext
        and "toy_function" not in initialtext
        and "pointwise fixation" not in initialtext
    )
    assert all(unrelated not in row["source_ids"] for row in calls_for(neg))
    (OUTPUT / "transport-captures.jsonl").write_text((SCRATCH / "transport.jsonl").read_text())
    (OUTPUT / "control-results.json").write_text(
        json.dumps(
            {
                "off_second_question": json.loads(offsecond["request_body"]["input"])["question"],
                "on_second_question": json.loads(onsecond["request_body"]["input"])["question"],
                "stop_reloaded_same_packet": True,
                "original_ids_preserved": True,
                "first_rh_context_answer_free": True,
                "browser_errors": errors,
                "stop_session": {
                    "id": restarted["id"],
                    "status": restarted["status"],
                    "calls_used": restarted["calls_used"],
                },
            },
            indent=2,
        )
    )
    subsetafter = export(SUBSET, "subset.after")
    rhafter = export(RH, "rh.after")
    for original, original_digest in originals.items():
        assert hashlib.sha256((SOURCE / original).read_bytes()).hexdigest() == original_digest
    manifest["projects"] = [
        {
            "slug": "nonconsecutive-subset-sums",
            "path": str(SUBSET),
            "project_id": subset["id"],
            "source": "Isolated path-rebound copy of actual Increment 2 five deterministic fixture sessions, preserving source IDs/text/history; includes one prior manually authored strategy, no prior session for it.",
            "before": before,
            "after": subsetafter,
            "new_sessions": [
                {
                    "case": name,
                    "id": s["id"],
                    "strategy_id": s["strategy_id"],
                    "calls": s["calls_used"],
                    "artifacts": [a["id"] for a in s["artifacts"]],
                }
                for name, s in [
                    ("evidence_off", off),
                    ("evidence_on", on),
                    ("negative_transfer", neg),
                    ("stop_reload_restart", restarted),
                ]
            ],
        },
        {
            "slug": "riemann-hypothesis-research",
            "path": str(RH),
            "project_id": rh["project"]["id"],
            "source": "Fresh stock copy with original strategies and zero sessions. Evaluator-authored RH-SYM injection saved as separate strategy. Scripted objection, then researcher-approved follow-up.",
            "before": rhbefore,
            "after": rhafter,
            "new_sessions": [
                {
                    "case": name,
                    "id": s["id"],
                    "strategy_id": s["strategy_id"],
                    "calls": s["calls_used"],
                    "artifacts": [a["id"] for a in s["artifacts"]],
                }
                for name, s in [("evaluator_injection", rhsource), ("approved_followup", rhfollow)]
            ],
        },
    ]
    manifest["checks"] = [
        "Actual HTTP dispatch differs in cycle 2 with and without selected cross-strategy sources",
        "Negative transfer rejection retained without accepted payload/citation",
        "Stop/API restart/resume retains exact frozen packet and original session ID",
        "Desktop/390px real Chrome approval, source navigation, actual session start, reload; no page errors; subset mobile no horizontal overflow",
        "Original exercised project source bytes remain unchanged",
    ]
    manifest["omissions"] = [
        "No actual live model reasoning, new mathematical discovery, proof of recurrence/limit or RH",
        "No sandbox computation dispatched; independent exact oracles are evaluator-only",
        "Native Markdown report unsupported; native txt/html/tex and Markdown-valued Conclusions in actual audits retained",
        "PDF and AI TeX paper generation untested; no paid calls authorized",
        "Controlled semantic choice is scripted on exact source IDs; not evidence of generalization or autonomous discovery",
        "Source archive contains historical unsupported assertions and incomplete duties; preservation is not endorsement",
    ]
    manifest["offline_http_calls"] = len(captures)
    (EXPORTS / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(
        json.dumps(
            {
                "result": "PASS",
                "root": str(SCRATCH),
                "offline_calls": len(captures),
                "new_sessions": 6,
                "exports": str(EXPORTS),
            },
            indent=2,
        )
    )
finally:
    for process in [ui, api]:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
