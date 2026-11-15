"""Single-user laboratory OAuth worker. Never exposes the token store to Chromium.

The browser runs in a separate container with a shared NETWORK namespace.
This service is intentionally not a hosted multi-user authorization broker.
"""
from __future__ import annotations

import os
import time
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

import synthetic_signin

from sigma import ai_store, chatgpt_auth
from sigma.projects import ProjectError

if os.environ.get("SIGMA_AUTH_POC_LAB") != "1":
    raise RuntimeError("This is a local laboratory; hosted integration is not enabled")

app = FastAPI()
app.include_router(synthetic_signin.router)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1"])
_ATTEMPT_ID: str | None = None
_LAB_PAINTED = False


def real_signin_enabled() -> bool:
    return (
        os.environ.get("SIGMA_AUTH_POC_LOCAL_DOCKER") == "1"
        and os.environ.get("SIGMA_AUTH_POC_REAL_SIGNIN") == "1"
    )


def require_real_signin() -> None:
    if not real_signin_enabled():
        raise HTTPException(
            403,
            "Real ChatGPT sign-in is available only in the explicit local authorization preview.",
        )



def same_origin(request: Request) -> None:
    if request.headers.get("origin") != "http://127.0.0.1:8001":
        raise HTTPException(403, "Invalid browser origin")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
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
<button id="verify" disabled>Verify model catalog (disabled)</button>
<button id="infer" disabled>Test one real model response (disabled)</button>
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
    if real_signin_enabled():
        html = html.replace(
            '<strong>Real ChatGPT sign-in is disabled for this synthetic test.</strong>',
            '<strong>Local ChatGPT authorization preview. Inference is disabled.</strong>'
            ' The sign-in result appears at the top of the SIGMA window.',
        ).replace(
            '<button id="start" disabled>Open ChatGPT account chooser (disabled)</button>',
            '<button id="start" data-preview="1" disabled>Continue with ChatGPT</button>',
        )
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'",
        },
    )


@app.post("/lab-painted")
async def lab_painted(request: Request) -> dict[str, bool]:
    global _LAB_PAINTED
    same_origin(request)
    require_real_signin()
    _LAB_PAINTED = True
    return {"ready": True}


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
    attempt = (await status())["attempt"]
    if attempt is not None:
        return {"phase": attempt}
    if await run_in_threadpool(_saved_preview_is_authorized):
        return {"phase": "connected"}
    return {"phase": "ready" if _LAB_PAINTED else "rendering"}


@app.post("/begin")
async def begin(request: Request) -> dict[str, str]:
    global _ATTEMPT_ID
    same_origin(request)
    require_real_signin()
    if not _LAB_PAINTED:
        raise HTTPException(409, "The sign-in page has not rendered yet.")
    if _ATTEMPT_ID is not None:
        if chatgpt_auth.attempt_status(_ATTEMPT_ID)["status"] == "connecting":
            raise HTTPException(409, "Complete or cancel the previous sign-in")
    try:
        attempt = await chatgpt_auth.begin()
    except ProjectError as exc:
        raise HTTPException(503, "Could not begin ChatGPT authorization. Try again.") from exc
    _ATTEMPT_ID = attempt["id"]
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


@app.post("/verify")
@app.post("/inference")
async def inference_disabled(request: Request) -> None:
    same_origin(request)
    raise HTTPException(403, "Model verification and inference are disabled in this preview.")


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ready": True}
