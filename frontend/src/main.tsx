import { useCallback, useEffect, useRef, useState, type FormEvent, type MouseEvent } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import './workspace.css';

type Strategy = {
  id: string;
  title: string;
  approach: string;
  author_kind: 'human';
  created_at: string;
  removed_at?: string | null;
};
type ProjectView = {
  path: string;
  project: {
    id: string;
    title: string;
    problem: string;
    schema_version: number;
    events: { sequence: number; kind: string; timestamp: string; strategy_id?: string | null;
      change?: { previous_title: string; previous_approach: string; title: string; approach: string } | null }[];
    strategies: Strategy[];
  };
};

async function post<T>(route: string, body: object = {}, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/projects/${route}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error ?? JSON.stringify(data.detail) ?? 'Request failed');
  return data;
}
const errorMessage = (error: unknown) => error instanceof Error ? error.message : String(error);
const projectUrl = (path: string) => `/project?${new URLSearchParams({ path })}`;
const dateLabel = (value: string) => new Date(value).toLocaleString();

function Header({ goHome, close, projectTitle }: { goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; projectTitle?: string }) {
  return <header className="site-header">
    <div className="brand-block">
      <a href="/" className="brand" onClick={goHome} aria-label="SIGMA home"><img src="/sigma-workspace-logo.png" alt="SIGMA" /></a>
      <p className="expansion">Strategy Investigation, Generation, Measurement &amp; Assessment</p>
    </div>
    <div className="header-controls">
    {projectTitle && <span className="current-project" title={projectTitle}>{projectTitle}</span>}
    {close ? <button className="text-button close-project" onClick={close.action} disabled={close.busy}>
      Close project
    </button> : <span className="local">● Local workspace</span>}
    </div>
  </header>;
}

function WorkspaceIcon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    Strategies: 'M3 3h6v6H3z M15 3h6v6h-6z M3 15h6v6H3z M15 15h6v6h-6z',
    Renders: 'M5 3h10l4 4v14H5z M14 3v5h5 M8 12h8 M8 16h6',
    Analysis: 'M4 20h17 M6 16v-5 M11 16V4 M16 16V8 M21 16v-3',
    References: 'M12 5c-3-2-6-2-10-1v16c4-1 7-1 10 1 3-2 6-2 10-1V4c-4-1-7-1-10 1v16',
    Notes: 'M5 3h14v18H5z M8 8h8 M8 12h8 M8 16h5',
    Settings: 'M12 3v3 M12 18v3 M3 12h3 M18 12h3 M6 6l2 2 M16 16l2 2 M6 18l2-2 M16 8l2-2 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  };
  return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
    strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;
}

function focusWorkspace(id: string) {
  const target = document.getElementById(id) ?? document.getElementById('workspace-content');
  target?.focus(); target?.scrollIntoView({ block: 'start' });
}

function WorkspaceFrame({ children, goHome, close, projectTitle }: {
  children: React.ReactNode; goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; projectTitle?: string;
}) {
  return <>
    <a className="workspace-skip" href="#workspace-content" onClick={event => {
      event.preventDefault(); focusWorkspace('workspace-content');
    }}>Skip to project content</a>
    <Header goHome={goHome} close={close} projectTitle={projectTitle}/>
    <div className="workspace-layout">
      <nav className="workspace-nav" aria-label="Project navigation">
        <a href="#pool-heading" aria-current="page" onClick={event => {
          event.preventDefault(); focusWorkspace('pool-heading');
        }}><WorkspaceIcon name="Strategies"/><span>Strategies</span></a>
        {['Renders', 'Analysis', 'References', 'Notes', 'Settings'].map(name =>
          <button key={name} disabled title="Not available yet" aria-describedby="workspace-nav-help">
            <WorkspaceIcon name={name}/><span>{name}</span><small>Later</small>
          </button>)}
        <p id="workspace-nav-help">Other destinations are not available yet.</p>
      </nav>
      <div id="workspace-content" className="workspace-content" tabIndex={-1}>{children}</div>
    </div>
  </>;
}

function Home({ initialPath, onOpen, goHome }: {
  initialPath: string; onOpen: (view: ProjectView) => void;
  goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const [path, setPath] = useState(initialPath);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { document.title = 'SIGMA · Research workspace'; heading.current?.focus(); }, []);
  async function open(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { onOpen(await post<ProjectView>('open', { path })); }
    catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  return <div className="home-shell">
    <div className="home-atmosphere" aria-hidden="true"/>
    <div className="home-content">
    <div className="home-topline"><span>STRATEGY INVESTIGATION · GENERATION · MEASUREMENT · ASSESSMENT</span><span>● LOCAL WORKSPACE</span></div>
    <div className="home-hero"><h1 ref={heading} tabIndex={-1}>Open a Project</h1>
    <p className="intro">Every discovery begins with a question. Open a research project to explore its possibilities.</p>
    </div>
    <form className="open-form" onSubmit={open}>
      <label htmlFor="path">PROJECT DIRECTORY</label>
      <div className="input-row">
        <input id="path" value={path} onChange={event => setPath(event.target.value)} required disabled={busy}/>
        <button disabled={busy}>{busy ? 'Opening…' : 'Open Project'} <span aria-hidden="true">↗</span></button>
      </div>
      <p className="hint">Enter a local SIGMA project directory.</p>
    </form>
    {error && <p role="alert" className="error">{error}</p>}
    <div className="empty home-empty"><h2>Recent Projects</h2><p>No recent project history is available yet. You can open the included <strong>projects/rh.sigma</strong> directory above.</p></div>
    </div>
  </div>;
}

function StrategyCommands({ strategy, onCommand }: {
  strategy: Strategy; onCommand: (mode: 'edit' | 'remove', strategy: Strategy) => void;
}) {
  const disclosure = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && !disclosure.current?.contains(event.target) && disclosure.current) {
        disclosure.current.open = false;
      }
    }
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, []);
  return <details className="strategy-commands" name="strategy-commands" ref={disclosure} onKeyDown={event => {
    if (event.key === 'Escape' && disclosure.current) {
      event.preventDefault(); event.stopPropagation(); disclosure.current.open = false;
      disclosure.current.querySelector('summary')?.focus();
    }
  }}>
    <summary id={`commands-${strategy.id}`} className="secondary strategy-toggle" aria-label={`Commands for ${strategy.title}`}>
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none">
        <path d="m6 3 5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </summary>
    <div className="command-panel">
      <details name={`strategy-command-${strategy.id}`}>
        <summary className="secondary">Scheduling</summary>
        <p id={`schedule-${strategy.id}`} className="hint">Scheduling controls are not available yet.</p>
        <ul aria-describedby={`schedule-${strategy.id}`}>
          {['Promote', 'Demote', 'Pause / Resume'].map(label => <li key={label}>
            <button className="secondary" disabled aria-describedby={`schedule-${strategy.id}`}>{label}</button>
          </li>)}
        </ul>
      </details>
      <details name={`strategy-command-${strategy.id}`}>
        <summary className="secondary">Artifact</summary>
        <p id={`audit-${strategy.id}`} className="hint">Audit reports are not available yet. They will record investigation steps, evidence and tests, and answers to rubric questions.</p>
        <button className="secondary" disabled aria-describedby={`audit-${strategy.id}`}>Audit</button>
        <p id={`artifacts-${strategy.id}`} className="hint">Additional artifact types are not specified yet.</p>
        <button className="secondary" disabled aria-describedby={`artifacts-${strategy.id}`}>Other artifact types</button>
      </details>
      <details name={`strategy-command-${strategy.id}`}>
        <summary className="secondary">Actions</summary>
        {(['edit', 'remove'] as const).map(mode => <button key={mode} className="secondary" onClick={() => {
          if (disclosure.current) disclosure.current.open = false;
          onCommand(mode, strategy);
        }}>{mode === 'edit' ? 'Edit' : 'Remove'}</button>)}
        <button className="secondary" disabled aria-describedby={`fork-${strategy.id}`}>Fork</button>
        <p id={`fork-${strategy.id}`} className="hint">Forking is not available yet.</p>
      </details>
    </div>
  </details>;
}

function StrategyDialog({ mode, strategy, path, onSaved, onCancel }: {
  mode: 'edit' | 'remove'; strategy: Strategy; path: string;
  onSaved: (view: ProjectView, mode: 'edit' | 'remove', strategy: Strategy) => void;
  onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const nameInput = useRef<HTMLInputElement>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);
  const [title, setTitle] = useState(strategy.title);
  const [approach, setApproach] = useState(strategy.approach);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    dialog.current?.showModal();
    if (mode === 'edit') nameInput.current?.focus();
    else cancelButton.current?.focus();
  }, [mode]);
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const next = await post<ProjectView>(`strategies/${mode}`, {
        path, strategy_id: strategy.id, ...(mode === 'edit' ? { title, approach } : {}),
      });
      onSaved(next, mode, strategy);
    } catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  return <dialog className="strategy-dialog" ref={dialog} aria-labelledby="strategy-dialog-title"
    aria-describedby="strategy-dialog-description" onCancel={event => {
      event.preventDefault(); if (!busy) onCancel();
    }}>
    <h2 id="strategy-dialog-title">{mode === 'edit' ? 'Edit strategy' : `Remove “${strategy.title}”?`}</h2>
    <p id="strategy-dialog-description" className="hint">{mode === 'edit'
      ? 'Update the name and description. Earlier text remains in project history.'
      : 'This strategy will leave the pool. Its idea and history will be kept in the project.'}</p>
    <form onSubmit={save}>
      <fieldset disabled={busy}>
        {mode === 'edit' && <>
          <label htmlFor="edit-strategy-name">Name</label>
          <input ref={nameInput} id="edit-strategy-name" value={title} required maxLength={200}
            onChange={event => setTitle(event.target.value)}/>
          <label htmlFor="edit-strategy-description">Description</label>
          <textarea id="edit-strategy-description" value={approach} required maxLength={10000} rows={5}
            onChange={event => setApproach(event.target.value)}/>
        </>}
        {error && <p role="alert" className="error">{error}</p>}
        <div className="form-actions">
          <button type="submit" className="secondary">{busy ? 'Saving…' : mode === 'edit' ? 'Save changes' : 'Remove strategy'}</button>
          <button type="button" className="text-button" ref={cancelButton} onClick={onCancel}>Cancel</button>
        </div>
      </fieldset>
    </form>
  </dialog>;
}

function NewStrategy({ path, onSaved, onCancel }: {
  path: string; onSaved: (view: ProjectView) => void; onCancel: () => void;
}) {
  const [title, setTitle] = useState('');
  const [approach, setApproach] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const titleInput = useRef<HTMLInputElement>(null);
  useEffect(() => { titleInput.current?.focus(); }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { onSaved(await post<ProjectView>('strategies', { path, title, approach })); }
    catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  return <form className="strategy-form" aria-labelledby="new-strategy-heading" onSubmit={save}
    onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); onCancel(); } }}>
    <h3 id="new-strategy-heading">New strategy</h3>
    <p className="hint">Capture an idea and the approach you want to investigate.</p>
    <fieldset disabled={busy}>
      <label htmlFor="strategy-title">Title</label>
      <input ref={titleInput} id="strategy-title" value={title} maxLength={200} required
        onChange={event => setTitle(event.target.value)} />
      <label htmlFor="strategy-approach">Hypothesis / approach</label>
      <textarea id="strategy-approach" value={approach} maxLength={10000} required rows={5}
        onChange={event => setApproach(event.target.value)} />
      {error && <p role="alert" className="error">{error}</p>}
      <div className="form-actions">
        <button type="submit">{busy ? 'Saving…' : 'Save strategy'}</button>
        <button type="button" className="text-button" onClick={onCancel}>Cancel</button>
      </div>
    </fieldset>
  </form>;
}

function ProjectScreen({ path, onClose, goHome }: {
  path: string; onClose: () => void;
  goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const [view, setView] = useState<ProjectView | null>(null);
  const [error, setError] = useState('');
  const [closing, setClosing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [announcement, setAnnouncement] = useState('');
  const [command, setCommand] = useState<{ mode: 'edit' | 'remove'; strategy: Strategy } | null>(null);
  const [focusStrategy, setFocusStrategy] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    post<ProjectView>('open', { path }, controller.signal).then(setView).catch(error => {
      if (!controller.signal.aborted) setError(errorMessage(error));
    });
    return () => controller.abort();
  }, [path]);
  useEffect(() => {
    if (view) document.title = `${view.project.title} · SIGMA`;
    else if (error) document.title = 'Project unavailable · SIGMA';
    heading.current?.focus();
  }, [view?.project.id, !!error]);
  useEffect(() => {
    if (focusStrategy) document.getElementById(`strategy-${focusStrategy}`)?.focus();
  }, [focusStrategy]);
  async function close() {
    setClosing(true); setError('');
    try { await post('close'); onClose(); }
    catch (error) { setError(errorMessage(error)); setClosing(false); }
  }
  const frame = { goHome, close: { action: close, busy: closing }, projectTitle: view?.project.title };
  function cancel() { setEditing(false); requestAnimationFrame(() => newButton.current?.focus()); }
  if (!view) return <WorkspaceFrame {...frame}><div className="workspace-state" aria-live="polite">{error ? <>
    <h1 ref={heading} tabIndex={-1}>Project unavailable</h1><p role="alert" className="error">{error}</p>
    <p>Close this project to choose another directory.</p>
  </> : <p className="intro">Opening project…</p>}</div></WorkspaceFrame>;
  const project = view.project;
  const strategies = project.strategies.filter(strategy => !strategy.removed_at);
  return <WorkspaceFrame {...frame}>
    <div className="project-intro">
      <h1 ref={heading} tabIndex={-1}>{project.title}</h1>
      <p className="objective">{project.problem}</p>
    </div>
    {error && <p role="alert" className="error">{error}</p>}
    <section className="pool" aria-labelledby="pool-heading">
      <div className="pool-heading">
        <h2 id="pool-heading" tabIndex={-1}>Strategy pool</h2>
        <div className="pool-buttons">
          <button className="primary-action" ref={newButton} onClick={() => setEditing(true)}
            disabled={editing || closing} aria-expanded={editing} aria-controls="strategy-composer">New strategy</button>
          <button className="secondary" disabled aria-describedby="generation-help">Generate strategy</button>
        </div>
      </div>
      <p id="generation-help" className="hint generation-help">Generation is unavailable. Agent generation is planned for a later release.</p>
      <p className="sr-only" role="status">{announcement}</p>
      <div id="strategy-composer">{editing && <NewStrategy path={view.path} onCancel={cancel} onSaved={next => {
        const strategy = next.project.strategies[next.project.strategies.length - 1];
        setView(next); setEditing(false); setAnnouncement(`Strategy saved: ${strategy.title}`);
        setFocusStrategy(strategy.id);
      }}/>}</div>
      {strategies.length ? <ol className="strategy-list">
        {strategies.map(strategy => <li className="strategy-row" key={strategy.id}>
          <div className="strategy-heading">
            <StrategyCommands strategy={strategy} onCommand={(mode, strategy) => setCommand({ mode, strategy })}/>
            <h3 id={`strategy-${strategy.id}`} tabIndex={-1}>{strategy.title}</h3>
          </div>
          <p className="strategy-approach">{strategy.approach}</p>
          <p className="strategy-byline">Human-authored · <time dateTime={strategy.created_at}>{dateLabel(strategy.created_at)}</time></p>
        </li>)}
      </ol> : !editing && <div className="pool-empty">
        <h3>Start with an idea worth investigating.</h3>
        <p>Use New strategy to write a hypothesis or approach. Your ideas will be preserved here as you explore them.</p>
      </div>}
    </section>
    {command && <StrategyDialog mode={command.mode} strategy={command.strategy} path={view.path}
      onCancel={() => {
        const id = command.strategy.id;
        setCommand(null);
        requestAnimationFrame(() => document.getElementById(`commands-${id}`)?.focus());
      }} onSaved={(next, mode, strategy) => {
        setView(next); setCommand(null);
        setAnnouncement(mode === 'edit' ? 'Strategy updated.' : `Removed ${strategy.title} from the pool. History retained.`);
        requestAnimationFrame(() => document.getElementById(
          mode === 'edit' ? `strategy-${strategy.id}` : 'pool-heading')?.focus());
      }}/>}
    <details className="project-details">
      <summary>Project details &amp; history</summary>
      <dl><dt>Identity</dt><dd>{project.id}</dd><dt>Directory</dt><dd>{view.path}</dd><dt>Format version</dt><dd>{project.schema_version}</dd></dl>
      <h3>Event history</h3>
      <ol className="event-list">{project.events.map(event => <li key={event.sequence}>
        <span className="sequence">{String(event.sequence).padStart(2, '0')}</span>
        <div><span>{event.kind}</span><time dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time>
          {event.change && <details className="edit-history"><summary>View changes</summary>
            <dl><dt>Name before</dt><dd>{event.change.previous_title}</dd>
              <dt>Name after</dt><dd>{event.change.title}</dd>
              <dt>Description before</dt><dd>{event.change.previous_approach}</dd>
              <dt>Description after</dt><dd>{event.change.approach}</dd></dl>
          </details>}
        </div>
      </li>)}</ol>
      <p className="hint">Opening and inspecting a project leave its history unchanged.</p>
    </details>
  </WorkspaceFrame>;
}

function App() {
  const [location, setLocation] = useState(() => window.location.pathname + window.location.search);
  const [lastPath, setLastPath] = useState(() =>
    new URLSearchParams(window.location.search).get('path') || 'projects/rh.sigma');
  useEffect(() => {
    const pop = () => setLocation(window.location.pathname + window.location.search);
    window.addEventListener('popstate', pop);
    return () => window.removeEventListener('popstate', pop);
  }, []);
  const navigate = useCallback((url: string) => {
    window.history.pushState(null, '', url); setLocation(url); window.scrollTo(0, 0);
  }, []);
  const closeProject = useCallback(() => {
    const path = new URLSearchParams(window.location.search).get('path');
    if (path) setLastPath(path);
    navigate('/');
  }, [navigate]);
  function goHome(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      event.preventDefault(); navigate('/');
    }
  }
  const url = new URL(location, window.location.origin);
  return <main className={url.pathname === '/' ? 'home-page' : 'workspace-page'}>
    {url.pathname === '/' ? <Home initialPath={lastPath} goHome={goHome} onOpen={view => {
      setLastPath(view.path); navigate(projectUrl(view.path));
    }}/> : url.pathname === '/project' ? <ProjectScreen key={location}
      path={url.searchParams.get('path') ?? ''} onClose={closeProject} goHome={goHome}/>
      : <><Header goHome={goHome}/><h1>Page not found</h1><a href="/" onClick={goHome}>Return Home</a></>}
  </main>;
}

createRoot(document.getElementById('root')!).render(<App/>);
