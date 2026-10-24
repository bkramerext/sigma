import os
from pathlib import Path
root=Path('/tmp/sigma-research-experience-blue');root.mkdir(exist_ok=True)
for name in list(os.environ):
 if name.startswith(('SIGMA_', 'OPENAI_', 'ANTHROPIC_')): os.environ.pop(name)
for name, sub in [('SIGMA_PROJECTS_ROOT','projects'),('SIGMA_STATE_DIR','state'),('SIGMA_AUTH_HOME','auth'),('SIGMA_CLOUD_AUTH_HOME','cloud-auth')]:
 p=root/sub;p.mkdir(exist_ok=True);p.chmod(0o700);os.environ[name]=str(p)
import httpx
class BlockedClient(httpx.AsyncClient):
 def __init__(self,*args,**kwargs):
  kwargs['transport']=httpx.MockTransport(lambda request: httpx.Response(503,json={'error':'Study: external provider calls disabled'}))
  super().__init__(*args,**kwargs)
httpx.AsyncClient=BlockedClient
from sigma.api import app
import uvicorn
uvicorn.run(app,host='127.0.0.1',port=8067)
