import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { relativeModelCostRank } from './model-cost';
import './model-pill.css';

type Model = { id: string; label: string; efforts: string[]; relative_cost: string; availability?: string };
type Prefs = { ai_model: string; reasoning_effort: string };
type Choice = { model: Model; effort: string };
const levels = ['low','medium','high','xhigh'];
function compatible(model: Model, effort: string): string | null {
  if (model.efforts.includes(effort)) return effort;
  const old = levels.indexOf(effort);
  return [...model.efforts].sort((a,b) => Math.abs(levels.indexOf(a)-old)-Math.abs(levels.indexOf(b)-old) || levels.indexOf(a)-levels.indexOf(b))[0] ?? null;
}
/** Original cycling Model pill, adapted to user-scoped research settings. */
export default function ModelPill() {
  const [prefs,setPrefs] = useState<Prefs | null>(null);
  const [models,setModels] = useState<Model[]>([]);
  const [ready,setReady] = useState(false);
  const [busy,setBusy] = useState(false);
  const [pending,setPending] = useState<Choice | null>(null);
  const [error,setError] = useState('');
  const anchor = useRef<HTMLButtonElement>(null);
  const confirm = useRef<HTMLButtonElement>(null);
  const [position,setPosition] = useState({left:-10000,top:-10000});
  useEffect(() => {
    let live = true, serial = 0;
    const refresh = () => {
      const request = ++serial;
      void Promise.all([
        fetch('/api/user-preferences/research-settings',{cache:'no-store',headers:{'X-Sigma-Error-Handled':'true'}}),
        fetch('/api/ai/models',{cache:'no-store',headers:{'X-Sigma-Error-Handled':'true'}}),
      ]).then(async ([p,m]) => {
        const nextPrefs = p.ok ? await p.json() as Prefs : null;
        const catalog = m.ok ? await m.json() as {models?:Model[]} : null;
        if (!live || request !== serial) return;
        setPrefs(nextPrefs);
        setModels(Array.isArray(catalog?.models) ? catalog.models : []);
      }).catch(() => { /* Preserve the last known model on transient failures. */ })
        .finally(() => { if (live && request===serial) setReady(true); });
    };
    refresh();
    window.addEventListener('sigma-research-settings-updated',refresh);
    window.addEventListener('focus',refresh);
    return () => { live=false; window.removeEventListener('sigma-research-settings-updated',refresh); window.removeEventListener('focus',refresh); };
  },[]);
  useEffect(() => {
    if (!pending) return;
    const place = () => {
      const rect=anchor.current?.getBoundingClientRect();
      if (!rect) return;
      const width=Math.min(320,window.innerWidth-16),height=145;
      setPosition({left:Math.max(8,Math.min(rect.right-width,window.innerWidth-width-8)),
        top:rect.bottom+height+8<window.innerHeight ? rect.bottom+8 : Math.max(8,rect.top-height-8)});
    };
    place();
    confirm.current?.focus();
    const escape=(e:KeyboardEvent) => { if(e.key==='Escape'){e.preventDefault();setPending(null);anchor.current?.focus();} };
    window.addEventListener('resize',place);
    window.addEventListener('scroll',place,true);
    document.addEventListener('keydown',escape,true);
    return () => {window.removeEventListener('resize',place);window.removeEventListener('scroll',place,true);document.removeEventListener('keydown',escape,true);};
  },[pending]);
  const current=models.find(m=>m.id===prefs?.ai_model);
  const modelLabel=current ? current.label.split(' · ')[0]+' '+current.relative_cost : prefs?.ai_model ?? 'Unavailable';
  const available=models.filter(m=>m.availability!=='unavailable'&&m.efforts.length>0)
    .sort((a,b)=>relativeModelCostRank(a.relative_cost)-relativeModelCostRank(b.relative_cost)||a.label.localeCompare(b.label));
  const index=available.findIndex(m=>m.id===prefs?.ai_model);
  const next=available.length>1 ? available[(index+1)%available.length] : index<0 ? available[0] : undefined;
  const nextEffort=next&&prefs?compatible(next,prefs.reasoning_effort):null;
  const effortNotice=nextEffort&&prefs&&nextEffort!==prefs.reasoning_effort ? ' The next model also changes Thinking to '+nextEffort+'.' : '';
  const help='The selected model is '+modelLabel+'. Its relative published API token cost is '+(current?.relative_cost??'unknown')+
    '. Click to cycle through reviewed model options, cheapest to most expensive.'+effortNotice+(error?' '+error:'');
  async function save(choice:Choice) {
    if (!prefs||busy) return;
    setBusy(true);setError('');
    try {
      const res=await fetch('/api/user-preferences/research-settings',{method:'PUT',
        headers:{'Content-Type':'application/json','X-Sigma-Error-Handled':'true'},
        body:JSON.stringify({ai_model:choice.model.id,reasoning_effort:choice.effort})});
      const data=await res.json();
      if(!res.ok) throw new Error(data.detail??'Could not change model.');
      setPrefs(data as Prefs);
      window.dispatchEvent(new Event('sigma-research-settings-updated'));
    } catch(e) {setError(e instanceof Error?e.message:String(e));}
    finally {setBusy(false);setPending(null);anchor.current?.focus();}
  }
  function cycle() {
    if(!next||!nextEffort||!prefs||busy) return;
    const choice={model:next,effort:nextEffort};
    if(current&&relativeModelCostRank(next.relative_cost)>relativeModelCostRank(current.relative_cost)) setPending(choice);
    else void save(choice);
  }
  return <div className="model-cycle-container">
    <button ref={anchor} className="model-cycle-pill" type="button" title={help} data-tooltip={help}
      aria-label={'Model '+modelLabel+'. '+help} disabled={!ready||busy||!prefs||!nextEffort||!!pending}
      onClick={cycle}>Model · {modelLabel}</button>
    {error&&<span className="model-cycle-error" role="alert">{error}</span>}
    {pending&&createPortal(<div className="model-cycle-confirm" role="dialog" aria-label={'Confirm switch to '+pending.model.label}
      style={position}>
      <p>Switch to <strong>{pending.model.label.split(' · ')[0]}</strong> ({pending.model.relative_cost})? This model has a higher relative published API token cost.
        {pending.effort!==prefs?.reasoning_effort&&' Thinking will change to '+pending.effort+'.'}</p>
      <div className="model-cycle-confirm-actions">
        <button ref={confirm} type="button" disabled={busy} onClick={()=>void save(pending)}>Switch model</button>
        <button type="button" onClick={()=>{setPending(null);anchor.current?.focus();}}>Cancel</button>
      </div>
    </div>,document.body)}
  </div>;
}
