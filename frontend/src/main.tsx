import { useCallback, useEffect, useRef, useState, type FormEvent, type MouseEvent } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import './workspace.css';
import './project-entry.css';
import './strategies.css';

type Stage = 'draft' | 'ready' | 'exploring' | 'hold';
const stageLabels: Record<Stage, string> = { draft: 'Draft', ready: 'Ready to explore', exploring: 'Exploring', hold: 'On hold' };
type Strategy = {
  id: string;
  title: string;
  approach: string;
  stage: Stage;
  summary: string;
  provenance: { provider: string; model: string } | null;
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
    research_mode: 'default' | 'mathematical';
    events: { sequence: number; kind: string; timestamp: string; strategy_id?: string | null;
      order?: string[] | null; stage_change?: { previous: Stage; stage: Stage } | null;
      change?: { previous_title: string; previous_approach: string; title: string; approach: string } | null }[];
    strategies: Strategy[];
    active_order: string[];
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

type ResearchMode = 'default' | 'mathematical';
type Destination = { root: string; path: string | null; exists: boolean };

function ProjectEntryDialog({ mode, initialPath, onOpen, onCancel }: {
  mode: 'open' | 'new'; initialPath: string; onOpen: (view: ProjectView) => void; onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const firstField = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const [path, setPath] = useState(initialPath);
  const [title, setTitle] = useState('');
  const [problem, setProblem] = useState('');
  const [researchMode, setResearchMode] = useState<ResearchMode>('default');
  const [destination, setDestination] = useState<Destination | null>(null);
  const [previewError, setPreviewError] = useState('');
  const [previewBusy, setPreviewBusy] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { dialog.current?.showModal(); firstField.current?.focus(); }, []);
  useEffect(() => {
    if (mode !== 'new') return;
    const controller = new AbortController();
    setPreviewBusy(true); setDestination(null); setPreviewError('');
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/projects/destination?${new URLSearchParams({ title })}`, { signal: controller.signal });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error ?? 'Project location is unavailable');
        setDestination(data);
      } catch (error) {
        if (!controller.signal.aborted) setPreviewError(errorMessage(error));
      } finally { if (!controller.signal.aborted) setPreviewBusy(false); }
    }, title ? 180 : 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [mode, title]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (submitting.current || (mode === 'new' && (!destination?.path || destination.exists || previewBusy))) return;
    submitting.current = true; setBusy(true); setError('');
    try {
      onOpen(await post<ProjectView>(mode === 'open' ? 'open' : 'create', mode === 'open'
        ? { path } : { title, problem, research_mode: researchMode }));
    } catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className="project-entry-dialog" aria-labelledby="project-entry-heading"
    aria-describedby="project-entry-help" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <h2 id="project-entry-heading">{mode === 'open' ? 'Open Project' : 'New Project'}</h2>
    <p id="project-entry-help" className="entry-help">{mode === 'open'
      ? 'Choose an existing local project by its directory path.'
      : 'Give your investigation a name, a problem, and a research mode.'}</p>
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        {mode === 'open' ? <>
          <label htmlFor="open-project-path">Project directory</label>
          <input ref={firstField} id="open-project-path" value={path} required aria-describedby="project-path-help"
            onChange={event => setPath(event.target.value)}/>
          <p id="project-path-help" className="entry-hint">Try <code>projects/rh.sigma</code>, or an absolute path such as <code>/Users/you/projects/question.sigma</code>. Paths refer to this local server.</p>
        </> : <>
          <label htmlFor="new-project-name">Project name</label>
          <input ref={firstField} id="new-project-name" value={title} required maxLength={200}
            onChange={event => setTitle(event.target.value)}/>
          <label htmlFor="new-project-problem">Research problem</label>
          <textarea id="new-project-problem" value={problem} required maxLength={20000} rows={4}
            onChange={event => setProblem(event.target.value)}/>
          <label htmlFor="new-project-mode">Research mode</label>
          <select id="new-project-mode" value={researchMode} onChange={event => setResearchMode(event.target.value as ResearchMode)}>
            <option value="default">Default</option><option value="mathematical">Mathematical</option>
          </select>
          <p className="project-destination" aria-live="polite"><span>Project location</span>
            <code>{previewBusy ? 'Checking location…' : destination?.path ?? destination?.root ?? 'Location unavailable'}</code>
            {!title && destination && <small>The project name determines its directory.</small>}
          </p>
          {previewError && <p role="alert" className="error">{previewError}</p>}
          {destination?.exists && <p role="alert" className="error">A project or file already exists here. Choose another name.</p>}
        </>}
        {error && <p role="alert" className="error">{error}</p>}
        <div className="entry-dialog-actions">
          <button type="submit" disabled={busy || (mode === 'new' && (previewBusy || !destination?.path || destination.exists))}>
            {busy ? mode === 'open' ? 'Opening…' : 'Creating…' : mode === 'open' ? 'Open Project' : 'Create Project'}
          </button>
          <button type="button" className="entry-cancel" onClick={onCancel}>Cancel</button>
        </div>
      </fieldset>
    </form>
  </dialog>;
}

function Home({ initialPath, onOpen, goHome }: {
  initialPath: string; onOpen: (view: ProjectView) => void;
  goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const [entry, setEntry] = useState<'open' | 'new' | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const openButton = useRef<HTMLButtonElement>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  useEffect(() => { document.title = 'SIGMA · Research workspace'; heading.current?.focus(); }, []);
  function cancel() {
    const trigger = entry === 'open' ? openButton : newButton;
    setEntry(null); requestAnimationFrame(() => trigger.current?.focus());
  }
  return <div className="home-shell">
    <div className="home-atmosphere" aria-hidden="true"/>
    <div className="home-content">
    <div className="home-topline"><span>STRATEGY INVESTIGATION · GENERATION · MEASUREMENT · ASSESSMENT</span><span>● LOCAL WORKSPACE</span></div>
    <div className="home-hero"><h1 ref={heading} tabIndex={-1}>Open a Project</h1>
    <p className="intro">Open an existing project or begin a new investigation.</p>
    </div>
    <div className="home-entry-actions">
      <button ref={openButton} onClick={() => setEntry('open')}>Open Project <span aria-hidden="true">↗</span></button>
      <button ref={newButton} className="home-new-project" onClick={() => setEntry('new')}>New Project</button>
    </div>
    <div className="empty home-empty"><h2>Recent Projects</h2><p>No recent project history is available yet.</p></div>
    {entry && <ProjectEntryDialog mode={entry} initialPath={initialPath} onOpen={onOpen} onCancel={cancel}/>}
    </div>
  </div>;
}

function StrategyCommands({ strategy, onCommand }: {
  strategy: Strategy; onCommand: (mode: 'edit' | 'remove' | 'stage', strategy: Strategy) => void;
}) {
  const disclosure = useRef<HTMLDetailsElement>(null);
  function positionMenu() {
    const element = disclosure.current;
    const panel = element?.querySelector<HTMLElement>('.command-panel');
    const trigger = element?.querySelector('summary');
    if (!element?.open || !panel || !trigger) return;
    if (window.innerWidth <= 700) { panel.removeAttribute('style'); return; }
    const rect = trigger.getBoundingClientRect();
    const height = panel.getBoundingClientRect().height;
    panel.style.position = 'fixed'; panel.style.right = 'auto'; panel.style.bottom = 'auto';
    panel.style.top = `${Math.max(16, Math.min(rect.bottom + 4, window.innerHeight - height - 16))}px`;
    panel.style.left = `${Math.max(16, Math.min(rect.right - panel.offsetWidth, window.innerWidth - panel.offsetWidth - 16))}px`;
  }
  useEffect(() => {
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && !disclosure.current?.contains(event.target) && disclosure.current) {
        disclosure.current.open = false;
      }
    }
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, []);
  return <details className="strategy-commands" name="strategy-commands" ref={disclosure} onToggle={positionMenu} onClick={() => requestAnimationFrame(positionMenu)} onKeyDown={event => {
    if (event.key === 'Escape' && disclosure.current) {
      event.preventDefault(); event.stopPropagation(); disclosure.current.open = false;
      disclosure.current.querySelector('summary')?.focus();
    }
  }}>
    <summary id={`commands-${strategy.id}`} className="secondary strategy-toggle" aria-label={`Commands for ${strategy.title}`}>
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none">
        <circle cx="8" cy="3" r="1.3" fill="currentColor"/><circle cx="8" cy="8" r="1.3" fill="currentColor"/><circle cx="8" cy="13" r="1.3" fill="currentColor"/>
      </svg>
    </summary>
    <div className="command-panel">
      <details name={`strategy-command-${strategy.id}`}>
        <summary className="secondary">Scheduling</summary>
        <p id={`schedule-${strategy.id}`} className="hint">Scheduling controls are not available yet.</p>
        <ul aria-describedby={`schedule-${strategy.id}`}>
          {['Pause / Resume'].map(label => <li key={label}>
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
        {(['edit', 'stage', 'remove'] as const).map(mode => <button key={mode} className="secondary" onClick={() => {
          if (disclosure.current) disclosure.current.open = false;
          onCommand(mode, strategy);
        }}>{mode === 'edit' ? 'Edit' : mode === 'stage' ? 'Change stage' : 'Remove'}</button>)}
        <button className="secondary" disabled aria-describedby={`fork-${strategy.id}`}>Fork</button>
        <p id={`fork-${strategy.id}`} className="hint">Forking is not available yet.</p>
      </details>
    </div>
  </details>;
}

function StrategyDialog({ mode, strategy, path, onSaved, onCancel }: {
  mode: 'edit' | 'remove' | 'stage'; strategy: Strategy; path: string;
  onSaved: (view: ProjectView, mode: 'edit' | 'remove' | 'stage', strategy: Strategy) => void;
  onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const nameInput = useRef<HTMLInputElement>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);
  const [stage, setStage] = useState<Stage>(strategy.stage);
  const submitting = useRef(false);
  const [title, setTitle] = useState(strategy.title);
  const [approach, setApproach] = useState(strategy.approach);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    dialog.current?.showModal();
    if (mode === 'edit') nameInput.current?.focus();
    else if (mode === 'stage') dialog.current?.querySelector('select')?.focus();
    else cancelButton.current?.focus();
  }, [mode]);
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current) return; submitting.current = true; setBusy(true); setError('');
    try {
      const next = await post<ProjectView>(`strategies/${mode}`, {
        path, strategy_id: strategy.id, ...(mode === 'edit' ? { title, approach } : mode === 'stage' ? { stage } : {}),
      });
      onSaved(next, mode, strategy);
    } catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog className="strategy-dialog" ref={dialog} aria-labelledby="strategy-dialog-title"
    aria-describedby="strategy-dialog-description" onCancel={event => {
      event.preventDefault(); if (!busy) onCancel();
    }}>
    <h2 id="strategy-dialog-title">{mode === 'edit' ? 'Edit strategy' : mode === 'stage' ? 'Change stage' : `Remove “${strategy.title}”?`}</h2>
    <p id="strategy-dialog-description" className="hint">{mode === 'edit'
      ? 'Update the name and description. Earlier text remains in project history.'
      : mode === 'stage' ? 'Stages are manually tracked. Exploring means you are investigating; no AI agent is running.' : 'This strategy will leave Strategies. Its idea and history will be kept in the project.'}</p>
    <form onSubmit={save}>
      <fieldset disabled={busy}>
        {mode === 'stage' && <><label htmlFor="manual-stage">Manually tracked stage</label><select autoFocus id="manual-stage" value={stage} onChange={event => setStage(event.target.value as Stage)}>{Object.entries(stageLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></>}
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
          <button type="submit" className="secondary">{busy ? 'Saving…' : mode === 'remove' ? 'Remove strategy' : 'Save changes'}</button>
          <button type="button" className="text-button" ref={cancelButton} onClick={onCancel}>Cancel</button>
        </div>
      </fieldset>
    </form>
  </dialog>;
}

function NewStrategy({ path, onSaved, onCancel }: {
  path: string; onSaved: (view: ProjectView) => void; onCancel: () => void;
}) {
  const submitting = useRef(false);
  const [title, setTitle] = useState('');
  const [approach, setApproach] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const titleInput = useRef<HTMLInputElement>(null);
  useEffect(() => { titleInput.current?.focus(); }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current) return; submitting.current = true; setBusy(true); setError('');
    try { onSaved(await post<ProjectView>('strategies', { path, title, approach })); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
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

function SplitStrategyAction({ buttonRef, disabled, onManual, onAI }: {
  buttonRef: React.RefObject<HTMLButtonElement | null>; disabled: boolean; onManual: () => void; onAI: () => void;
}) {
  const menu = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const outside = (event: PointerEvent) => { if (event.target instanceof Node && !menu.current?.contains(event.target) && menu.current) menu.current.open = false; };
    document.addEventListener('pointerdown', outside); return () => document.removeEventListener('pointerdown', outside);
  }, []);
  function choose(action: () => void) { if (disabled) return; if (menu.current) menu.current.open = false; action(); }
  return <div className="new-strategy-split">
    <button className="primary-action" ref={buttonRef} disabled={disabled} onClick={() => choose(onManual)} title="Write manually">＋ New Strategy</button>
    <details ref={menu} onKeyDown={event => { if (event.key === 'Escape' && menu.current) { event.preventDefault(); menu.current.open = false; menu.current.querySelector('summary')?.focus(); } }}>
      <summary aria-label="New Strategy options" aria-disabled={disabled} onClick={event => { if (disabled) event.preventDefault(); }}>⌄</summary>
      <div className="strategy-choice-menu" aria-label="Choose how to create a strategy">
        <button aria-label="Write manually" disabled={disabled} onClick={() => choose(onManual)}><span aria-hidden="true">✎</span><span>Write manually<small>Capture your own approach</small></span></button>
        <button aria-label="Generate with AI" disabled={disabled} onClick={() => choose(onAI)}><span aria-hidden="true">✧</span><span>Generate with AI<small>Start from the research problem or an idea</small></span></button>
      </div>
    </details>
  </div>;
}

type ProposalResult = { draft: { title: string; summary: string; approach: string; first_tests: string; assumptions: string; failure_modes: string }; provenance: { provider: string; model: string }; receipt: string };
function GenerateStrategy({ path, onSaved, onCancel }: {
  path: string; onSaved: (view: ProjectView) => void; onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const request = useRef<AbortController | null>(null);
  const submitting = useRef(false);
  const [config, setConfig] = useState<{ available: boolean; provider: string; model: string; message: string } | null>(null);
  const [seed, setSeed] = useState('');
  const [consent, setConsent] = useState(false);
  const [result, setResult] = useState<ProposalResult | null>(null);
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [approach, setApproach] = useState('');
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    dialog.current?.showModal(); dialog.current?.querySelector('textarea')?.focus();
    const controller = new AbortController();
    fetch('/api/projects/proposals/config', { signal: controller.signal }).then(async response => { if (!response.ok) throw new Error('Could not read AI configuration'); return response.json(); }).then(setConfig).catch(error => { if (!controller.signal.aborted) setError(errorMessage(error)); });
    return () => { controller.abort(); request.current?.abort(); };
  }, []);
  function cancel() { if (saving) return; request.current?.abort(); onCancel(); }
  async function generate() {
    if (submitting.current) return; submitting.current = true;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError('');
    try {
      const next = await post<ProposalResult>('proposals', { path, seed, consent }, controller.signal);
      setResult(next); setTitle(next.draft.title); setSummary(next.draft.summary);
      setApproach(`${next.draft.approach}\n\nFirst tests\n${next.draft.first_tests}\n\nAssumptions\n${next.draft.assumptions}\n\nWays this could fail\n${next.draft.failure_modes}`);
      requestAnimationFrame(() => document.getElementById('proposal-title')?.focus());
    } catch (error) { if (!controller.signal.aborted) setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current || !result) return; submitting.current = true; setSaving(true); setError('');
    try { onSaved(await post<ProjectView>('strategies', { path, title, approach, summary, receipt: result.receipt })); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setSaving(false); }
  }
  return <dialog ref={dialog} className="strategy-dialog proposal-dialog" aria-labelledby="proposal-heading" aria-describedby="proposal-help" onCancel={event => { event.preventDefault(); cancel(); }}>
    <h2 id="proposal-heading">Generate a strategy</h2>
    <p id="proposal-help" className="hint">Propose one distinct research direction. Review and edit the draft before saving. Nothing runs or saves automatically.</p>
    <p className="provider-context">{config ? `${config.provider} · ${config.model}` : 'Reading server configuration…'}</p>
    {config && !config.available && <p role="status" className="hint">{config.message}</p>}
    <details className="proposal-context" open={!result}><summary>Generation context &amp; starting point</summary>
    <label htmlFor="proposal-seed">Starting point <span className="hint">(optional)</span></label>
    <textarea id="proposal-seed" rows={3} maxLength={4000} value={seed} disabled={busy || saving} onChange={event => setSeed(event.target.value)} aria-describedby="seed-help"/>
    <p id="seed-help" className="hint">A hunch, question, technique, observation or constraint—not an assumption to endorse. Leave empty for an independent direction.</p>
    <label className="proposal-consent"><input type="checkbox" checked={consent} disabled={busy || saving} onChange={event => setConsent(event.target.checked)}/><span>I agree to send the project problem, research mode, all existing strategy titles/approaches (including removed ones), and this optional starting point to OpenAI. API usage is billed separately from ChatGPT/Codex.</span></label>
    <p className="hint">One proposal per click, with a 60-second timeout. Oversized project context is rejected without truncation. Cancelling stops the local request; provider usage may already be billed.</p>
    </details>
    <button type="button" className="secondary" disabled={!config?.available || !consent || busy || saving} onClick={() => void generate()}>{busy ? 'Generating…' : result ? 'Regenerate · new API request' : 'Generate draft'}</button>
    <p role="status" className="sr-only">{busy ? 'Generating a draft. No strategy is being saved.' : result ? 'Editable draft ready for review.' : ''}</p>
    {error && <p role="alert" className="error">{error}</p>}
    <form onSubmit={save}>
      {result && <fieldset disabled={busy || saving} className="proposal-review">
        <legend>Unsaved draft · Review before accepting</legend>
        <label htmlFor="proposal-title">Title</label><input id="proposal-title" required maxLength={200} value={title} onChange={event => setTitle(event.target.value)}/>
        <label htmlFor="proposal-summary">One-line preview</label><input id="proposal-summary" required maxLength={300} value={summary} onChange={event => setSummary(event.target.value)}/>
        <label htmlFor="proposal-approach">Proposed approach, first tests, assumptions and failure modes</label><textarea id="proposal-approach" required maxLength={10000} rows={9} value={approach} onChange={event => setApproach(event.target.value)}/>
        <p className="hint">AI-assisted suggestion · {result.provenance.provider} / {result.provenance.model}. Saving records your acceptance and edits; it does not validate the research.</p>
      </fieldset>}
      <div className="form-actions">
        {result && <button type="submit" disabled={busy || saving}>{saving ? 'Saving…' : 'Save strategy'}</button>}
        <button type="button" className="text-button" disabled={saving} onClick={cancel}>{busy ? 'Cancel request' : 'Cancel'}</button>
      </div>
    </form>
  </dialog>;
}

function ProjectScreen({ path, onClose, goHome }: {
  path: string; onClose: () => void;
  goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const [view, setView] = useState<ProjectView | null>(null);
  const [error, setError] = useState('');
  const [closing, setClosing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [ordering, setOrdering] = useState(false);
  const [previewOrder, setPreviewOrder] = useState<string[] | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const drag = useRef<{ id: string; order: string[]; pointer: number | null } | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const [command, setCommand] = useState<{ mode: 'edit' | 'remove' | 'stage'; strategy: Strategy } | null>(null);
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
  useEffect(() => {
    if (!dragId) return;
    function pointerMove(event: PointerEvent) {
      if (drag.current?.pointer !== event.pointerId) return;
      event.preventDefault();
      const rows = Array.from(document.querySelectorAll<HTMLElement>('.strategy-row'));
      const index = rows.findIndex(row => { const r = row.getBoundingClientRect(); return event.clientY >= r.top && event.clientY <= r.bottom; });
      if (index >= 0) moveTo(index);
      if (event.clientY > window.innerHeight - 60) window.scrollBy(0, 16);
      if (event.clientY < 60) window.scrollBy(0, -16);
    }
    function pointerUp(event: PointerEvent) { if (drag.current?.pointer === event.pointerId) void drop(); }
    function pointerCancel(event: PointerEvent) { if (drag.current?.pointer === event.pointerId) cancelDrag(); }
    function escape(event: KeyboardEvent) { if (event.key === 'Escape') { event.preventDefault(); const id = drag.current?.id; cancelDrag(); if (id) document.getElementById(`grip-${id}`)?.focus(); } }
    // Document listeners survive DOM relocation of the captured grip during touch sorting.
    document.addEventListener('pointermove', pointerMove, { passive: false });
    document.addEventListener('pointerup', pointerUp);
    document.addEventListener('pointercancel', pointerCancel);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointermove', pointerMove); document.removeEventListener('pointerup', pointerUp); document.removeEventListener('pointercancel', pointerCancel); document.removeEventListener('keydown', escape); };
  }, [dragId, view]);
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
  const byId = new Map(project.strategies.map(strategy => [strategy.id, strategy]));
  const strategies = (previewOrder ?? project.active_order).map(id => byId.get(id)!);
  function pickup(id: string, pointer: number | null) {
    if (ordering || drag.current) return;
    drag.current = { id, order: [...project.active_order], pointer }; setDragId(id);
    setPreviewOrder([...project.active_order]);
    setAnnouncement(`Picked up ${byId.get(id)!.title}. Arrow keys move, Enter drops, Escape cancels.`);
  }
  function moveTo(index: number) {
    const active = drag.current; if (!active) return;
    const order = [...active.order]; const old = order.indexOf(active.id);
    const target = Math.max(0, Math.min(order.length - 1, index));
    order.splice(old, 1); order.splice(target, 0, active.id);
    active.order = order; setPreviewOrder(order);
    setAnnouncement(`Position ${target + 1} of ${order.length}.`);
  }
  function cancelDrag() {
    drag.current = null; setDragId(null); setPreviewOrder(null); setAnnouncement('Reorder cancelled.');
  }
  async function drop() {
    const active = drag.current; if (!active) return;
    drag.current = null; setDragId(null);
    if (active.order.join() === project.active_order.join()) { setPreviewOrder(null); setAnnouncement('Order unchanged.'); return; }
    setOrdering(true); setError('');
    try {
      setView(await post<ProjectView>('strategies/reorder', { path: view!.path, order: active.order, expected_order: project.active_order }));
      setAnnouncement('Strategy order saved.');
    } catch (error) { setError(errorMessage(error)); setAnnouncement('Order save failed. Previous order restored.'); }
    finally { setOrdering(false); setPreviewOrder(null); requestAnimationFrame(() => document.getElementById(`grip-${active.id}`)?.focus()); }
  }
  return <WorkspaceFrame {...frame}>
    <div className="project-intro">
      <p className="project-eyebrow">Research project</p>
      <SplitStrategyAction buttonRef={newButton} disabled={editing || generating || closing || ordering || !!dragId} onManual={() => setEditing(true)} onAI={() => setGenerating(true)}/>
      <h1 ref={heading} tabIndex={-1}>{project.title}</h1>
      <p className="objective">{project.problem}</p>
    </div>
    {error && <p role="alert" className="error">{error}</p>}
    <section className="pool" aria-labelledby="pool-heading">
      <div className="pool-heading">
        <h2 id="pool-heading" tabIndex={-1}>Strategies</h2>
      </div>
      <p className="hint strategies-intro">Independent avenues of investigation. Stages are manually tracked.</p>
      <p className="sr-only" role="status">{announcement}</p>
      <div id="strategy-composer">{editing && <NewStrategy path={view.path} onCancel={cancel} onSaved={next => {
        const strategy = next.project.strategies[next.project.strategies.length - 1];
        setView(next); setEditing(false); setAnnouncement(`Strategy saved: ${strategy.title}`);
        setFocusStrategy(strategy.id);
      }}/>}</div>
      {strategies.length ? <div className="strategies-table">
        <div className="strategy-columns" aria-hidden="true"><span>Strategy</span><span>Stage</span></div>
        <ol className="strategy-list" aria-label="Strategies" aria-busy={ordering}>
        {strategies.map(strategy => <li className={`strategy-row${dragId === strategy.id ? ' is-lifted' : ''}`} key={strategy.id} data-strategy-id={strategy.id}>
          <details className="strategy-detail">
            <summary title="Expand or collapse the full approach"><h3 aria-label={strategy.title} id={`strategy-${strategy.id}`} tabIndex={-1}>{strategy.title}</h3>
              <span className="strategy-preview">{strategy.summary || strategy.approach.replace(/\s+/g, ' ')}</span>
              {strategy.provenance && <span className="ai-byline">AI-assisted · Human accepted</span>}
            </summary>
            <div className="strategy-expanded"><p className="strategy-approach">{strategy.approach}</p>
              <p className="strategy-byline">{strategy.provenance ? `AI-assisted suggestion · ${strategy.provenance.provider} / ${strategy.provenance.model} · Accepted/edited by a human` : 'Human-authored'} · <time dateTime={strategy.created_at}>{dateLabel(strategy.created_at)}</time></p>
              <code className="strategy-identity">{strategy.id}</code>
            </div>
          </details>
          <span className={`stage-label stage-${strategy.stage}`} title="Manually tracked; no strategy runner"><i aria-hidden="true"/>{stageLabels[strategy.stage]}</span>
          <StrategyCommands strategy={strategy} onCommand={(mode, strategy) => { if (!ordering && !dragId) setCommand({ mode, strategy }); }}/>
          <button id={`grip-${strategy.id}`} className="drag-grip" disabled={ordering || closing}
            aria-label={`Reorder ${strategy.title}`} aria-describedby="reorder-help" aria-pressed={dragId === strategy.id}
            onPointerDown={event => { if (event.button !== 0) return; event.preventDefault(); event.currentTarget.focus(); pickup(strategy.id, event.pointerId); event.currentTarget.setPointerCapture(event.pointerId); }}
            onKeyDown={event => { if (event.key === 'Escape' && drag.current) { event.preventDefault(); cancelDrag(); }
              else if (event.key === ' ' && !drag.current) { event.preventDefault(); pickup(strategy.id, null); }
              else if (drag.current?.id === strategy.id && ['ArrowUp', 'ArrowDown', 'Enter', ' '].includes(event.key)) { event.preventDefault();
                if (event.key === 'ArrowUp' || event.key === 'ArrowDown') moveTo(drag.current.order.indexOf(strategy.id) + (event.key === 'ArrowUp' ? -1 : 1)); else void drop();
              } }}><svg width="12" height="16" viewBox="0 0 12 16" fill="currentColor" aria-hidden="true">{[3,7,11].flatMap(y => [3,7].map(x => <circle key={`${x}-${y}`} cx={x} cy={y} r="1"/>))}</svg></button>
        </li>)}
      </ol></div> : !editing && <div className="pool-empty">
        <h3>Start with an idea worth investigating.</h3>
        <p>Use New strategy to write a hypothesis or approach. Your ideas will be preserved here as you explore them.</p>
      </div>}
      {(dragId || ordering) && <p className="reorder-feedback">{ordering ? 'Saving order…' : 'Moving strategy · Release or press Enter to save · Escape cancels'}</p>}
      <p id="reorder-help" className="sr-only">Drag only the corner grip to reorder. Keyboard: Space picks up, arrows move, Enter drops, Escape cancels. Changes save on drop.</p>
    </section>
    {generating && <GenerateStrategy path={view.path} onCancel={() => { setGenerating(false); requestAnimationFrame(() => newButton.current?.focus()); }} onSaved={next => {
      const strategy = next.project.strategies.at(-1)!; setView(next); setGenerating(false); setFocusStrategy(strategy.id); setAnnouncement('AI-assisted strategy accepted and saved.');
    }}/>}
    {command && <StrategyDialog mode={command.mode} strategy={command.strategy} path={view.path}
      onCancel={() => {
        const id = command.strategy.id;
        setCommand(null);
        requestAnimationFrame(() => document.getElementById(`commands-${id}`)?.focus());
      }} onSaved={(next, mode, strategy) => {
        setView(next); setCommand(null);
        setAnnouncement(mode !== 'remove' ? 'Strategy updated.' : `Removed ${strategy.title} from Strategies. History retained.`);
        requestAnimationFrame(() => document.getElementById(
          mode !== 'remove' ? `strategy-${strategy.id}` : 'pool-heading')?.focus());
      }}/>}
    <details className="project-details">
      <summary>Project details &amp; history</summary>
      <dl><dt>Identity</dt><dd>{project.id}</dd><dt>Directory</dt><dd>{view.path}</dd><dt>Format version</dt><dd>{project.schema_version}</dd><dt>Research mode</dt><dd>{project.research_mode === 'mathematical' ? 'Mathematical' : 'Default'}</dd></dl>
      <h3>Event history</h3>
      <ol className="event-list">{project.events.map(event => <li key={event.sequence}>
        <span className="sequence">{String(event.sequence).padStart(2, '0')}</span>
        <div><span>{event.kind}</span><time dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time>
          {event.stage_change && <p>Manually tracked: {stageLabels[event.stage_change.previous]} → {stageLabels[event.stage_change.stage]}</p>}
          {event.order && <details><summary>Saved order</summary><ol>{event.order.map(id => <li key={id}>{byId.get(id)?.title ?? id}</li>)}</ol></details>}
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
