"""Self-contained, dependency-free authenticated browser viewer for the POC."""
HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SIGMA | Containerized ChatGPT connection POC</title>
<style>
  :root { color-scheme: dark; font: 15px system-ui,sans-serif; }
  body { max-width: 1120px; margin: 24px auto; padding: 0 20px; color: #eee; background: #14171a; }
  h1 { font-size: 24px; font-weight: 600; }
  p { color: #c5c6cb; line-height: 1.6; }
  button { background: transparent; border: 1px solid #777; color: #eee;
    border-radius: 5px; padding: 9px 14px; margin: 4px 8px 4px 0; cursor: pointer; }
  button:disabled { opacity: .45; cursor: default; }
  #screen { width: 100%; max-width: 1024px; aspect-ratio: 8/5; object-fit: fill;
    display: block; border: 1px solid #777; margin: 12px 0; outline-offset: 2px;
    background: #090a0b; cursor: crosshair; }
  #screen:focus { outline: 2px solid #bd8967; }
  #status,#result { min-height: 1.5em; overflow-wrap: anywhere; }
  .fine { font-size: 13px; }
</style></head>
<body><h1>Containerized Personal ChatGPT — feasibility test</h1>
<p>This is a single-administrator experiment, not a released Personal ChatGPT
  connection. Chromium and SIGMA's OAuth callback listener run inside the
  same Docker container. No desktop companion or terminal is required for the
  user. Do not use this with other users' accounts.</p>
<p><strong>Security:</strong> The remote display and keyboard events pass through
  your SIGMA server over authenticated HTTPS. The server can observe interactions,
  including credentials entered during sign-in. Do not use this for production
  until that trust boundary and OpenAI's hosted authorization requirements are reviewed.</p>
<div>
  <button id="begin">Open OpenAI chooser in container</button>
  <button id="test" disabled>Send one real test turn</button>
  <a href="/" style="color:#d4a888">Return to SIGMA</a>
</div>
<p id="status" role="status">No sign-in started.</p>
<img id="screen" alt="Live container browser (click to focus and interact)" tabindex="0">
<p class="fine">Click the browser picture to focus it, then type normally. Enter,
  Tab, Backspace and arrow keys are forwarded. This is an interactive remote
  browser, not your Mac's browser. The image may refresh about once per second.</p>
<div id="result" role="status"></div>
<script>
const path='/api/auth-browser-poc';
const frame=document.querySelector('#screen');
const status=document.querySelector('#status');
const result=document.querySelector('#result');
const begin=document.querySelector('#begin');
const test=document.querySelector('#test');
const keyMap={Enter:'Return',Backspace:'BackSpace',Tab:'Tab',
  Escape:'Escape',Delete:'Delete',ArrowLeft:'Left',ArrowRight:'Right',
  ArrowUp:'Up',ArrowDown:'Down',Home:'Home',End:'End'};
let frameURL=null;
let inputQueue=Promise.resolve();
async function api(url,method='GET',body=null) {
 const r=await fetch(path+url,{method,credentials:'same-origin',cache:'no-store',
  headers:method==='GET'?{}:{'Content-Type':'application/json'},
  body:method==='GET'?undefined:JSON.stringify(body||{})});
 if(!r.ok)throw new Error('Request failed ('+r.status+').');
 return method==='GET'&&url==='/frame'?r.blob():r.json();
}
function sendInput(data) {
 inputQueue=inputQueue.then(()=>api('/input','POST',data)).catch(e=>status.textContent=e.message);
}
frame.addEventListener('click',e=>{
 const box=frame.getBoundingClientRect();
 if(!box.width||!box.height)return;
 sendInput({kind:'click',
   x:Math.max(0,Math.min(1279,Math.floor((e.clientX-box.left)*1280/box.width))),
   y:Math.max(0,Math.min(799,Math.floor((e.clientY-box.top)*800/box.height)))});
 frame.focus();
});
frame.addEventListener('keydown',e=>{
 if(e.ctrlKey||e.metaKey||e.altKey)return;
 if(keyMap[e.key]) {e.preventDefault();sendInput({kind:'key',value:keyMap[e.key]});}
 else if(e.key.length===1){e.preventDefault();sendInput({kind:'text',value:e.key});}
});
frame.addEventListener('paste',e=>{
 const value=e.clipboardData?.getData('text/plain')||'';
 if(value&&value.length<=200) {e.preventDefault();sendInput({kind:'text',value});}
});
begin.onclick=async()=>{
 begin.disabled=true;result.textContent='';
 try{await api('/begin','POST');status.textContent='OpenAI chooser launching inside the container.';}
 catch(e){status.textContent=e.message;}
 finally{begin.disabled=false;}
};
test.onclick=async()=>{
 test.disabled=true;result.textContent='Sending one test turn...';
 try{const r=await api('/test','POST');result.textContent='Response ('+r.model+'): '+r.response;}
 catch(e){result.textContent=e.message;}
 finally{test.disabled=false;}
};
async function refresh(){
 try{
   const s=await api('/status');
   status.textContent='Connection: '+s.status+(s.account_label?' ('+s.account_label+')':'');
   test.disabled=s.status!=='connected';
 }catch(e){status.textContent=e.message;test.disabled=true;}
 try{
   const png=await api('/frame');const next=URL.createObjectURL(png);
   const old=frameURL;frameURL=next;frame.src=next;
   if(old)URL.revokeObjectURL(old);
 }catch(e){/* Worker may still be starting. Never show authentication data as errors. */}
}
refresh();setInterval(refresh,1200);
</script></body></html>'''
