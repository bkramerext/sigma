import { useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type ProjectView = {
  path: string;
  project: { id: string; title: string; problem: string; schema_version: number;
    events: { sequence: number; kind: string; timestamp: string }[] };
};
async function post(route: string, body: object = {}) {
  const response = await fetch(`/api/projects/${route}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error ?? JSON.stringify(data.detail) ?? 'Request failed');
  return data;
}
function App() {
  const [path, setPath] = useState('projects/rh.sigma');
  const [view, setView] = useState<ProjectView | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function open(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { setView(await post('open', { path })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  async function close() {
    setBusy(true); setError('');
    try { await post('close'); setView(null); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return <main>
    <header><a href="/" className="brand">Σ <span>SIGMA</span></a><span className="local">● Local workspace</span></header>
    <p className="eyebrow">STRATEGY · INVESTIGATION · MEASUREMENT</p>
    <h1>A place for the next question.</h1>
    <p className="intro">Open a research project to inspect its objective and recorded history.</p>
    <form onSubmit={open}>
      <label htmlFor="path">Project directory</label>
      <div className="input-row"><input id="path" value={path} onChange={e => setPath(e.target.value)} required disabled={busy}/><button disabled={busy}>{busy ? 'Working…' : view ? 'Open / switch' : 'Open project'} <span>↗</span></button></div>
      <p className="hint">Use a local .sigma directory. The RH seed initializes on its first open.</p>
    </form>
    {error && <div role="alert" className="error">{error}</div>}
    {view ? <article>
      <div className="project-heading"><div><p className="eyebrow">PROJECT / OPEN</p><h2>{view.project.title}</h2></div><button className="secondary" disabled={busy} onClick={close}>Close project</button></div>
      <p className="objective">{view.project.problem}</p>
      <dl><dt>Identity</dt><dd>{view.project.id}</dd><dt>Directory</dt><dd>{view.path}</dd><dt>Format version</dt><dd>{view.project.schema_version}</dd></dl>
      <section><h3>Event history <span>{view.project.events.length}</span></h3><ol>{view.project.events.map(e => <li key={e.sequence}><span className="sequence">{String(e.sequence).padStart(2, '0')}</span><div><strong>{e.kind}</strong><time dateTime={e.timestamp}>{new Date(e.timestamp).toLocaleString()}</time></div></li>)}</ol><p className="hint">Opening and inspecting a project leave its history unchanged.</p></section>
    </article> : <div className="empty"><span>◌</span><h2>Your research starts with a project.</h2><p>Open the included Riemann Hypothesis seed above.</p></div>}
    <footer>Strategy Investigation, Generation, Measurement &amp; Assessment</footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
