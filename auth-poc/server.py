"""One-container browser + loopback OAuth feasibility experiment.

The service is intentionally inaccessible outside the container. An operator
uses the remote Chromium via a host-loopback-bound noVNC endpoint. Do not
expose this UI publicly: it displays an interactive OpenAI login session.
"""

from __future__ import annotations

import asyncio
import html
import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from sigma import chatgpt_auth
from sigma.openai_connection import connection

_BROWSER: subprocess.Popen[bytes] | None = None
_ATTEMPT_ID: str | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _BROWSER
    # Fixed internal URL; no attacker-controlled redirects or command arguments.
    _BROWSER = subprocess.Popen(
        [
            "/usr/bin/chromium",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--password-store=basic",
            "--user-data-dir=/tmp/chromium",
            "--window-size=1280,800",
            "--app=http://127.0.0.1:8001/",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "DISPLAY": ":99"},
    )
    try:
        yield
    finally:
        if _BROWSER and _BROWSER.poll() is None:
            _BROWSER.terminate()
            try:
                await asyncio.to_thread(_BROWSER.wait, timeout=3)
            except subprocess.TimeoutExpired:
                _BROWSER.kill()


app = FastAPI(lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>SIGMA · Container localhost OAuth POC</title>
<style>body{font:16px system-ui;margin:3rem auto;max-width:43rem;
background:#171b20;color:#f1f1f1;line-height:1.6;padding:0 1rem}
button{padding:0.6rem 1rem}code{color:#d7b58e}</style></head>
<body><h1>SIGMA containerized ChatGPT authentication POC</h1>
<p>This entire browser is running inside Docker. A successful sign-in proves
the browser and callback listener share a container-local <code>127.0.0.1</code>.
It does <strong>not</strong> establish OpenAI permission for a hosted multi-user service.</p>
<button id="start">Open ChatGPT account chooser</button>
<button id="verify">Verify Personal model access</button>
<p id="status" role="status">No sign-in started.</p>
<script>
const status = document.getElementById('status');
async function request(path, method) {
  const response = await fetch(path, {method,cache:'no-store'});
  const data = await response.json();
  if(!response.ok) throw new Error(data.detail || 'Request failed');
  return data;
}
document.getElementById('start').onclick=async()=>{
  status.textContent='Opening OpenAI sign-in in this container...';
  try { await request('/begin','POST'); }
  catch(e){ status.textContent=String(e); }
};
document.getElementById('verify').onclick=async()=>{
  status.textContent='Checking the account against OpenAI...';
  try { const r=await request('/verify','POST');
    status.textContent=r.connected ? 'Verified: Personal ChatGPT connection is usable.'
                                  : 'Not connected: '+r.status; }
  catch(e){status.textContent=String(e);}
};
async function poll(){
  try { const r=await request('/status','GET');
    if(r.attempt && r.attempt!=='connecting') status.textContent='OAuth: '+r.attempt;
  } catch {}
}
setInterval(poll,1800);
</script></body></html>""",
        headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"},
    )


@app.post("/begin")
async def begin() -> dict[str, str]:
    global _ATTEMPT_ID
    if _ATTEMPT_ID is not None:
        try:
            if chatgpt_auth.attempt_status(_ATTEMPT_ID)["status"] == "connecting":
                raise HTTPException(409, "Complete or cancel the existing sign-in.")
        except ValueError:
            pass
    attempt = await chatgpt_auth.begin()
    _ATTEMPT_ID = attempt["id"]
    target = chatgpt_auth.authorization_url(_ATTEMPT_ID)
    # The URL comes only from SIGMA's pinned OpenAI discovery and was checked by
    # chatgpt_auth; never accept a user-supplied navigation target.
    if not target.startswith(chatgpt_auth.ISSUER + "/"):
        raise HTTPException(503, "Unexpected provider authorization endpoint.")
    if _BROWSER is None or _BROWSER.poll() is not None:
        raise HTTPException(503, "Chromium is not running.")
    subprocess.Popen(
        ["/usr/bin/chromium", "--user-data-dir=/tmp/chromium", target],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={**os.environ, "DISPLAY": ":99"},
    )
    return {"status": "connecting"}


@app.get("/status")
async def status() -> dict[str, str | None]:
    if _ATTEMPT_ID is None:
        return {"attempt": None}
    try:
        state = chatgpt_auth.attempt_status(_ATTEMPT_ID)
        return {"attempt": state["status"]}
    except Exception:
        return {"attempt": "unavailable"}


@app.post("/verify")
async def verify() -> dict[str, str | bool]:
    # Existing SIGMA connection logic performs provider-side model discovery.
    result = await connection(refresh=True)
    return {"connected": result.get("status") == "connected", "status": str(result.get("status", "unavailable"))}


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ready": _BROWSER is not None and _BROWSER.poll() is None}
