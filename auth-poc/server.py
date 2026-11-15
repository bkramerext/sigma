"""Single-user laboratory OAuth worker. Never exposes the token store to Chromium.

The browser runs in a separate container with a shared NETWORK namespace.
This service is intentionally not a hosted multi-user authorization broker.
"""
from __future__ import annotations

import os
import secrets
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sigma import chat, chatgpt_auth
from sigma.openai_connection import connection

if os.environ.get("SIGMA_AUTH_POC_LAB") != "1":
    raise RuntimeError("This is a local laboratory; hosted integration is not enabled")

app = FastAPI()
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1"])
_ATTEMPT_ID: str | None = None


def same_origin(request: Request) -> None:
    if request.headers.get("origin") != "http://127.0.0.1:8001":
        raise HTTPException(403, "Invalid browser origin")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>SIGMA · Container OAuth laboratory</title>
<style>body{font:16px system-ui;margin:3rem auto;max-width:43rem;background:#171b20;
color:#f1f1f1;line-height:1.6;padding:0 1rem}button{padding:.6rem 1rem;margin-right:.5rem}
code{color:#d7b58e}</style></head>
<body><h1>Containerized Personal ChatGPT POC</h1>
<p>Chromium runs in a disposable browser container. An isolated OAuth worker
holds credentials in another container. They share a localhost network only.
This is not a production-approved hosted integration.</p>
<button id="start">Open ChatGPT account chooser</button>
<button id="verify">Verify model catalog</button>
<button id="infer">Test one real model response</button>
<p id="status" role="status">No sign-in started.</p>
<script>
const status=document.getElementById('status');
async function req(path) {
 const response=await fetch(path,{method:'POST',cache:'no-store'});
 const data=await response.json();
 if(!response.ok)throw new Error(data.detail||'Request failed');
 return data;
}
document.getElementById('start').onclick=async()=>{
 status.textContent='Opening OpenAI sign-in...';
 const popup=window.open('about:blank','_blank');
 try{const r=await req('/begin');
  if(popup)popup.location.replace('/open/'+encodeURIComponent(r.id));
  else status.textContent='Popup blocked. Enable popups for this browser.';
 }catch(e){if(popup)popup.close();status.textContent=String(e);}
};
document.getElementById('verify').onclick=async()=>{
 status.textContent='Checking available models...';
 try{const r=await req('/verify');
 status.textContent=r.connected?'OpenAI model catalog verified.':'Not connected: '+r.status;
 }catch(e){status.textContent=String(e);}
};
document.getElementById('infer').onclick=async()=>{
 status.textContent='Requesting a bounded model response...';
 try{const r=await req('/inference');
 status.textContent=r.completed?'A real Responses API request completed.':'Inference failed.';
 }catch(e){status.textContent=String(e);}
};
let last='';
async function poll(){
 try{const r=await fetch('/status',{cache:'no-store'}).then(r=>r.json());
 if(r.attempt&&r.attempt!==last){last=r.attempt;status.textContent='OAuth: '+r.attempt;}
 }catch{}
}
setInterval(poll,1800);
</script></body></html>""",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'",
        },
    )


@app.post("/begin")
async def begin(request: Request) -> dict[str, str]:
    global _ATTEMPT_ID
    same_origin(request)
    if _ATTEMPT_ID is not None:
        if chatgpt_auth.attempt_status(_ATTEMPT_ID)["status"] == "connecting":
            raise HTTPException(409, "Complete or cancel the previous sign-in")
    attempt = await chatgpt_auth.begin()
    _ATTEMPT_ID = attempt["id"]
    return {"id": _ATTEMPT_ID}


@app.get("/open/{identifier}")
async def open_auth(identifier: str) -> RedirectResponse:
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
    if _ATTEMPT_ID is None:
        return {"attempt": None}
    return {"attempt": chatgpt_auth.attempt_status(_ATTEMPT_ID)["status"]}


@app.post("/verify")
async def verify(request: Request) -> dict[str, str | bool]:
    same_origin(request)
    result = await connection(refresh=True)
    return {
        "connected": result.get("status") == "connected",
        "status": str(result.get("status", "unavailable")),
    }


@app.post("/inference")
async def inference(request: Request) -> dict[str, bool]:
    same_origin(request)
    config = await chat.configuration()
    if not config["available"]:
        raise HTTPException(503, "No verified Personal ChatGPT model available")
    # Deliberately fixed and bounded; not a general-purpose inference proxy.
    result = await chat.respond(
        speaker="ai_1",
        messages=[{"speaker": "human", "text": "Reply with a brief greeting."}],
        conversation_id=secrets.token_hex(16),
        expected_binding=config["binding"],
        model=config["model"],
        reasoning_effort=config["reasoning_effort"],
    )
    return {"completed": bool(result.strip())}


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ready": True}
