"""Loopback OAuth browser routes for SIGMA's user-isolated Personal worker.

The same real account sign-in runs locally and on hosted SIGMA. Chromium and
the callback remain bound to the container loopback; tokens never enter the
SIGMA frontend. Synthetic sign-in exists only for separate offline tests.
"""
from __future__ import annotations

import asyncio
import os
import re
import time
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

import synthetic_signin
from model_gateway import _valid_rpc_key

from sigma import ai_store, chatgpt_auth
from sigma.projects import ProjectError

_shared_real = (
    os.environ.get("SIGMA_PERSONAL_SHARED_VAULT") == "1"
    and os.environ.get("SIGMA_PERSONAL_SHARED_REAL_SIGNIN") == "1"
)
if not _shared_real and os.environ.get("SIGMA_AUTH_POC_LAB") != "1":
    raise RuntimeError("Personal ChatGPT worker is not enabled")

app = FastAPI()
if not _shared_real:
    app.include_router(synthetic_signin.router)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1"])
_ATTEMPT_ID: str | None = None
_SIGNIN_START_LOCK = asyncio.Lock()
_SIGNIN_FAILED = False


def real_signin_enabled() -> bool:
    """The hosted shared worker is real, not a local/synthetic preview."""
    if os.environ.get("SIGMA_PERSONAL_SHARED_VAULT") == "1":
        seed = os.environ.get("SIGMA_AUTH_POC_RPC_SEED", "")
        return (
            os.environ.get("SIGMA_PERSONAL_SHARED_REAL_SIGNIN") == "1"
            and re.fullmatch(r"[0-9a-f]{64}", seed) is not None
        )
    return (
        os.environ.get("SIGMA_AUTH_POC_LAB") == "1"
        and os.environ.get("SIGMA_AUTH_POC_LOCAL_DOCKER") == "1"
        and os.environ.get("SIGMA_AUTH_POC_REAL_SIGNIN") == "1"
    )


def require_real_signin() -> None:
    if not real_signin_enabled():
        raise HTTPException(
            403,
            "Real Personal ChatGPT sign-in is unavailable in this worker.",
        )



def same_origin(request: Request) -> None:
    if request.headers.get("origin") != "http://127.0.0.1:8001":
        raise HTTPException(403, "Invalid browser origin")


def cancel_pending_signin() -> None:
    """Cancel the sole active browser's OAuth attempt in its owning workspace.

    Called only while the shared worker has bound the prior verified workspace,
    on browser close or after a supervisor-enforced timeout. Token records are
    retained; only transient PKCE material and the pending callback expire.
    """
    global _ATTEMPT_ID, _SIGNIN_FAILED
    identifier = _ATTEMPT_ID
    if identifier is not None:
        try:
            chatgpt_auth.cancel(identifier)
        except ProjectError:
            # A completed/expired attempt cannot be replayed into another user.
            pass
        _ATTEMPT_ID = None
    _SIGNIN_FAILED = False


async def _direct_local_signin() -> RedirectResponse:
    """Start fresh OAuth for every explicitly launched browser, never a blank page.

    A saved account remains intact until OAuth succeeds, but is *not* evidence
    that a user's explicit Sponsored -> Personal click should reuse it. The
    disposable Chromium profile opens directly on OpenAI's account chooser.
    """
    global _ATTEMPT_ID, _SIGNIN_FAILED
    require_real_signin()
    _SIGNIN_FAILED = False
    # Do not serve an empty page for saved credentials: that was the white
    # noVNC screen on a second connection attempt. An explicitly started GUI
    # always requests a fresh account chooser without erasing saved tokens.
    async with _SIGNIN_START_LOCK:
        # Opening the isolated browser's start page is a new sign-in, not a
        # replay of its previous OAuth handoff. authorization_url() consumes
        # the URL exactly once. A canceled/recreated Chromium can revisit /
        # while the worker and its in-memory _ATTEMPT_ID survive Docker stop.
        # Reusing that ID raises ProjectError ("already opened") and used to
        # leak a 500 Internal Server Error into the iframe.
        previous_id = _ATTEMPT_ID
        _ATTEMPT_ID = None
        if previous_id:
            try:
                chatgpt_auth.cancel(previous_id)
            except ProjectError:
                # The prior attempt may have completed or expired. It cannot
                # authorize the new browser; never replay a consumed handoff.
                pass
        try:
            attempt = await chatgpt_auth.begin()
            _ATTEMPT_ID = attempt["id"]
            url = chatgpt_auth.authorization_url(_ATTEMPT_ID)
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname != "auth.openai.com":
                raise ProjectError("Unexpected authorization endpoint")
        except ProjectError as exc:
            # No raw OAuth exception or internal server error in the iframe.
            # Also release a partially started attempt before the next retry.
            if _ATTEMPT_ID is not None:
                try:
                    chatgpt_auth.cancel(_ATTEMPT_ID)
                except ProjectError:
                    pass
                _ATTEMPT_ID = None
            _SIGNIN_FAILED = True
            raise HTTPException(503, "Could not start ChatGPT sign-in. Please retry.") from exc
    return RedirectResponse(
        url, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
    )


@app.get("/", response_class=HTMLResponse)
async def index() -> Response:
    if real_signin_enabled():
        return await _direct_local_signin()
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>SIGMA · Container OAuth laboratory</title>
<style>body{font:16px system-ui;margin:3rem auto;max-width:43rem;background:#171b20;
color:#f1f1f1;line-height:1.6;padding:0 1rem}button{padding:.6rem 1rem;margin-right:.5rem}
code{color:#d7b58e}</style></head>
<body><h1>Containerized Personal ChatGPT POC</h1>
<p>Chromium runs in a disposable browser container. An isolated OAuth worker
holds credentials in another container. They share a localhost network only.
<strong>Real ChatGPT sign-in is disabled for this synthetic test.</strong></p>
<button id="start" disabled>Open ChatGPT account chooser (disabled)</button>
<p id="status" role="status">No sign-in started.</p>
<script>
const status=document.getElementById('status');
const start=document.getElementById('start');
if(start.dataset.preview==='1'){
 const observer=new PerformanceObserver(async(list)=>{
  if(!list.getEntries().some(entry=>entry.name==='first-contentful-paint'))return;
  observer.disconnect();
  try{
   await req('/lab-painted');
   start.disabled=false;
  }catch{status.textContent='SIGMA could not confirm the sign-in page. Reopen the browser to try again.';}
 });
 observer.observe({type:'paint',buffered:true});
}
async function req(path) {
 const response=await fetch(path,{method:'POST',cache:'no-store'});
 const data=await response.json();
 if(!response.ok)throw new Error(data.detail||'Request failed');
 return data;
}
start.onclick=async()=>{
 status.textContent='Opening OpenAI sign-in...';
 const popup=window.open('about:blank','_blank');
 try{const r=await req('/begin');
  if(popup){popup.opener=null;popup.location.replace('/open/'+encodeURIComponent(r.id));}
  else status.textContent='Popup blocked. Enable popups for this browser.';
 }catch(e){if(popup)popup.close();status.textContent=String(e);}
};
let last='';
async function poll(){
 try{const r=await fetch('/status',{cache:'no-store'}).then(r=>r.json());
 if(r.attempt&&r.attempt!==last){
  last=r.attempt;
  status.textContent=r.message||('OAuth: '+r.attempt);
 }
 if(!r.attempt&&start.dataset.preview==='1'){
  const preview=await fetch('/preview-state',{cache:'no-store'});
  if(preview.ok&&(await preview.json()).phase==='connected')
   status.textContent='Using your saved ChatGPT authorization.';
 }
 }catch{}
}
setInterval(poll,1800);
</script></body></html>"""
    if synthetic_signin.enabled():
        html = html.replace(
            '<button id="start" disabled>Open ChatGPT account chooser (disabled)</button>',
            '<form method="post" action="/test-signin/begin">'
            '<button type="submit">Choose a test account</button></form>'
            '<button id="start" hidden disabled></button>',
        )
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'",
        },
    )


def _saved_preview_is_authorized() -> bool:
    """Expose only the result of validation, never the stored account record."""
    try:
        state = ai_store.read(ai_store.directory() / "credentials.json")
        account = state["accounts"].get(state["active"]) if state["mode"] == "chatgpt" else None
        return (
            isinstance(account, dict)
            and account.get("plan_authorized") is True
            and bool(account.get("access_token"))
            and float(account.get("expires_at", 0)) > time.time()
        )
    except (OSError, ValueError, TypeError, KeyError, ProjectError):
        return False


@app.get("/preview-state")
async def preview_state() -> dict[str, str]:
    require_real_signin()
    # An explicit reauthorization must complete before existing saved tokens
    # are treated as the result of this browser session. Otherwise a pending
    # chooser gets short-circuited by last week's valid cached credentials.
    attempt = (await status())["attempt"]
    if attempt is not None:
        return {"phase": attempt}
    if _SIGNIN_FAILED:
        return {"phase": "failed"}
    if os.environ.get("SIGMA_PERSONAL_SHARED_VAULT") == "1":
        # A shared-worker window was launched by explicit user intent. An
        # earlier saved account is NOT completion of this new OAuth flow.
        # The frontend verifies the saved account separately before opening
        # the GUI when it is intentionally restoring a Personal session.
        return {"phase": "ready"}
    if await run_in_threadpool(_saved_preview_is_authorized):
        return {"phase": "connected"}
    return {"phase": "ready"}


@app.post("/begin")
async def begin(request: Request) -> dict[str, str]:
    global _ATTEMPT_ID, _SIGNIN_FAILED
    same_origin(request)
    require_real_signin()
    if _ATTEMPT_ID is not None:
        if chatgpt_auth.attempt_status(_ATTEMPT_ID)["status"] == "connecting":
            raise HTTPException(409, "Complete or cancel the previous sign-in")
    try:
        attempt = await chatgpt_auth.begin()
    except ProjectError as exc:
        raise HTTPException(503, "Could not begin ChatGPT authorization. Try again.") from exc
    _ATTEMPT_ID = attempt["id"]
    _SIGNIN_FAILED = False
    return {"id": _ATTEMPT_ID}


@app.get("/open/{identifier}")
async def open_auth(identifier: str) -> RedirectResponse:
    require_real_signin()
    if _ATTEMPT_ID is None or identifier != _ATTEMPT_ID:
        raise HTTPException(404, "Sign-in attempt unavailable")
    url = chatgpt_auth.authorization_url(identifier)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "auth.openai.com":
        raise HTTPException(503, "Unexpected authorization endpoint")
    return RedirectResponse(url, headers={"Cache-Control": "no-store",
                                          "Referrer-Policy": "no-referrer"})


@app.get("/status")
async def status() -> dict[str, str | None]:
    if not real_signin_enabled() or _ATTEMPT_ID is None:
        return {"attempt": None}
    try:
        attempt = chatgpt_auth.attempt_status(_ATTEMPT_ID)
    except ProjectError:
        return {"attempt": "expired", "message": "Sign-in expired. Start another attempt."}
    return {"attempt": attempt["status"], "message": attempt["message"]}


@app.post("/disconnect")
async def disconnect(request: Request) -> dict[str, bool]:
    global _ATTEMPT_ID
    if not _valid_rpc_key(request):
        raise HTTPException(403, "Personal ChatGPT disconnect is unavailable.")
    await chatgpt_auth.disconnect()
    _ATTEMPT_ID = None
    return {"disconnected": True}


@app.post("/verify")
@app.post("/inference")
async def inference_disabled(request: Request) -> None:
    same_origin(request)
    raise HTTPException(403, "Use Personal ChatGPT from the main SIGMA window.")


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ready": True}
