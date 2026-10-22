import { lazy, Suspense, useCallback, useEffect, useRef, useState, type FormEvent, type MouseEvent, type Ref } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import './workspace.css';
import './investigation-entry.css';
import './strategies.css';
import './investigation-settings.css';
import './recents.css';
import './copper-controls.css';
import './text-views.css';
import { AIProvider, ConnectionStatus, ManageUsage, PlanWelcome, useAI } from './ai-connection';
import { installRequestErrorToasts, reportRequestFailure, RequestErrorToasts } from './request-toast';
const RenderedMarkdown = lazy(() => import('./RenderedMarkdown'));

type Stage = 'draft' | 'ready' | 'exploring' | 'hold';
const stageLabels: Record<Stage, string> = { draft: 'Draft', ready: 'Ready to explore', exploring: 'Exploring', hold: 'On hold' };
type Strategy = {
  id: string;
  title: string;
  approach: string;
  stage: Stage;
  summary: string;
  provenance: { provider: string; model: string; reasoning_effort?: string | null } | null;
  author_kind: 'human';
  created_at: string;
  removed_at?: string | null;
};
type InvestigationView = {
  path: string;
  investigation: {
    id: string;
    title: string;
    problem: string;
    schema_version: number;
    ai_model: string;
    reasoning_effort: string;
    investigation_type: 'default' | 'mathematical';
    events: { sequence: number; kind: string; timestamp: string; strategy_id?: string | null;
      investigation_change?: { previous: Settings; current: Settings } | null;
      order?: string[] | null; stage_change?: { previous: Stage; stage: Stage } | null;
      change?: { previous_title: string; previous_approach: string; title: string; approach: string } | null }[];
    strategies: Strategy[];
    active_order: string[];
  };
};

type TextFormat = 'plain' | 'markdown';
type TextDisplay = 'plain' | 'rendered';
type TextVersion = { body: string; kind: 'authored' | 'ai_derived'; current: boolean; source_digest: string; source_format: TextFormat; created_at: string; provenance: { provider: string; model: string; reasoning_effort: string | null } | null; warnings: string[] };
type TextRepresentations = { source_format: TextFormat; source_digest: string; plain: TextVersion | null; markdown: TextVersion | null };

async function post<T>(route: string, body: object = {}, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/investigations/${route}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error ?? JSON.stringify(data.detail) ?? 'Request failed');
  return data;
}
const errorMessage = (error: unknown) => error instanceof Error ? error.message : String(error);
const investigationUrl = (path: string) => `/investigation?${new URLSearchParams({ path })}`;
const dateLabel = (value: string) => new Date(value).toLocaleString();

function TextViews({ path, scope, strategyId, source, contentClass, onSaved, mathematical, onSettings, settingsDisabled, settingsButtonRef }: {
  path: string; scope: 'investigation' | 'strategy'; strategyId?: string; source: string;
  contentClass: string; onSaved: (view: InvestigationView) => void; mathematical: boolean; onSettings?: () => void; settingsDisabled?: boolean; settingsButtonRef?: React.RefObject<HTMLButtonElement | null>;
}) {
  const [data, setData] = useState<TextRepresentations | null>(null);
  const preferenceKey = `sigma.markdownView:${path}:${scope}:${strategyId ?? ''}`;
  const legacyPreferenceKey = `sigma.markdownView:${path}:${scope === 'investigation' ? 'project' : scope}:${strategyId ?? ''}`;
  const [storedSelected, setSelected] = useState<TextDisplay>(() => (window.localStorage.getItem(preferenceKey) ?? window.localStorage.getItem(legacyPreferenceKey)) === 'rendered' ? 'rendered' : 'plain');
  const selected: TextDisplay = mathematical ? storedSelected : 'plain';
  const [rendering, setRendering] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editingFromRendered, setEditingFromRendered] = useState(false);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const abort = useRef<AbortController | null>(null);
  const bodyTrigger = useRef<HTMLElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError(''); setEditing(false);
    const query = new URLSearchParams({ path, scope, ...(strategyId ? { strategy_id: strategyId } : {}) });
    fetch(`/api/investigations/text?${query}`, { signal: controller.signal }).then(async response => {
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Could not read text views');
      return result as TextRepresentations;
    }).then(result => { setData(result); if (!result.markdown?.current) setSelected('plain'); setDraft(result.markdown?.current ? result.markdown.body : result.plain?.body ?? ''); })
      .catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)); });
    return () => { controller.abort(); abort.current?.abort(); };
  }, [path, scope, strategyId, source]);
  const format: TextFormat = selected === 'plain' ? 'plain' : 'markdown';
  function chooseView(view: TextDisplay) {
    setSelected(view);
    window.localStorage.setItem(preferenceKey, view);
    window.localStorage.setItem(legacyPreferenceKey, view);
  }
  const version = data?.[format];
  const current = version?.current ?? false;
  function beginBodyEdit(fromRendered = false) {
    if (!version?.current || busy) return;
    setDraft(version.body); setEditingFromRendered(fromRendered);
    if (fromRendered) chooseView('rendered');
    setEditing(true); setError('');
  }
  function cancelBodyEdit() {
    setEditing(false);
    if (editingFromRendered) chooseView('rendered');
    requestAnimationFrame(() => bodyTrigger.current?.focus());
  }
  async function convert(targetFormat: TextFormat = format) {
    if (!data || busy) return;
    const controller = new AbortController(); abort.current = controller; setBusy(true); setRendering(true); setError('');
    try {
      const settingsResponse = await fetch(`/api/investigations/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal });
      const settings = await settingsResponse.json();
      if (!settingsResponse.ok || !settings.available) { if (settingsResponse.ok) reportRequestFailure(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.'); throw new Error(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.'); }
      const response = await fetch('/api/investigations/text/convert', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ path, scope, strategy_id: strategyId, target: targetFormat, expected_digest: data.source_digest, expected_binding: settings.binding }) });
      const next = await response.json();
      if (!response.ok) throw new Error(next.error ?? 'Conversion failed; source text was kept.');
      setData(next as TextRepresentations); setDraft(next[targetFormat]?.body ?? ''); chooseView('rendered');
    } catch (cause) { if (!controller.signal.aborted) { chooseView('plain'); setError(errorMessage(cause)); } }
    finally { if (abort.current === controller) { abort.current = null; setBusy(false); setRendering(false); } }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (!data || busy) return;
    setBusy(true); setError('');
    try {
      const next = await post<InvestigationView>('text/source', { path, scope, strategy_id: strategyId, body: draft, format, expected_digest: data.source_digest });
      setEditing(false); onSaved(next);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  const name = scope === 'investigation' ? 'research problem' : 'strategy approach';
  return <div className={`text-views${scope === 'investigation' ? ' investigation-text-views' : ''}${mathematical ? ' math-text-views' : ''}`}>
    <div className="text-view-controls">
      {mathematical && <button type="button" className={`sigma-render-toggle${selected === 'rendered' || rendering ? ' sigma-render-active' : ''}${rendering ? ' sigma-render-pending' : ''}`}
        aria-label={selected === 'rendered' ? `Show plain ${name}` : `Render ${name} as Markdown`}
        aria-pressed={selected === 'rendered' || rendering} title={selected === 'rendered' ? 'Show plain text' : 'Render Markdown'}
        disabled={editing || busy} onClick={() => {
          if (selected === 'rendered') { chooseView('plain'); setError(''); }
          else if (data?.markdown?.current) { chooseView('rendered'); setError(''); }
          else { void convert('markdown'); }
        }}><span aria-hidden="true">{rendering ? "⌛" : "Σ"}</span></button>}
      {editing ? <>
        <button type="submit" form={`text-form-${scope}-${strategyId ?? 'investigation'}`} className="text-view-link" disabled={busy || !draft.trim()}>Save</button>
        <button type="button" className="text-view-link" disabled={busy} onClick={cancelBodyEdit}>Cancel</button>
      </> : data && version && <button type="button" className="text-view-link" onClick={() => beginBodyEdit(selected === 'rendered')}>Edit</button>}
      {onSettings && <button ref={settingsButtonRef} type="button" className="text-view-link" disabled={settingsDisabled} onClick={onSettings}>Settings</button>}
    </div>
    {editing ? <form id={`text-form-${scope}-${strategyId ?? 'investigation'}`} className="text-view-editor" onSubmit={save}>
      <textarea id={`text-editor-${scope}-${strategyId ?? 'investigation'}`} autoFocus value={draft} maxLength={scope === 'investigation' ? 20000 : 10000} rows={8} required disabled={busy} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); cancelBodyEdit(); } }}/>
    </form> : current && version ? selected === 'rendered'
      ? <div className={`${contentClass} rendered-text`} aria-label={`Rendered ${name}`}><Suspense fallback={<p>Preparing preview…</p>}><RenderedMarkdown body={version.body}/></Suspense></div>
      : <p className={contentClass}>{version.body}</p>
      : !data ? <p className={contentClass}>{source}</p> : <div className="text-view-missing">
        <p>{version ? 'The previous conversion is out of date with the current source.' : `No ${format === 'markdown' ? 'Markdown' : 'Plain'} representation is stored yet.`}</p>
        {version && <details><summary>Inspect previous {format === 'markdown' ? 'Markdown' : 'Plain'} text</summary><pre>{version.body}</pre></details>}
      </div>}
    {busy && !editing && <span className="sr-only" role="status">Converting to Markdown…</span>}
    {error && editing && <p role="alert" className="error">{error}</p>}
  </div>;
}

function InlineInvestigationTitle({ view, onSaved, disabled, titleRef }: { view: InvestigationView; onSaved: (view: InvestigationView) => void; disabled: boolean; titleRef?: Ref<HTMLHeadingElement> }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(view.investigation.title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { if (!editing) setDraft(view.investigation.title); }, [view.investigation.title, editing]);
  useEffect(() => { if (editing) { input.current?.focus(); input.current?.select(); } }, [editing]);
  function cancel() { setDraft(view.investigation.title); setError(''); setEditing(false); requestAnimationFrame(() => trigger.current?.focus()); }
  async function save() {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const current = settingsOf(view);
      const next = await post<InvestigationView>('update', { path: view.path, ...current, title: draft, expected: current });
      setEditing(false); onSaved(next); requestAnimationFrame(() => trigger.current?.focus());
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <>
    <h1 ref={titleRef} tabIndex={-1} className="current-investigation" aria-label={view.investigation.title}>
      {editing ? <input ref={input} aria-label="Investigation title" value={draft} maxLength={200} disabled={busy} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); cancel(); } else if (event.key === 'Enter') { event.preventDefault(); void save(); } }}/>
        : <button ref={trigger} className="investigation-title-edit" type="button" onClick={() => setEditing(true)} disabled={disabled} aria-label={`Edit investigation title: ${view.investigation.title}`} title="Click or press Enter to edit investigation title">{view.investigation.title}</button>}
    </h1>
    {editing && <div className="investigation-title-actions"><button type="button" disabled={busy || !draft.trim()} onClick={() => void save()}>Save</button><button type="button" disabled={busy} onClick={cancel}>Cancel</button></div>}
    {error && <p role="alert" className="investigation-title-error">{error}</p>}
  </>;
}

function Header({ goHome, close, investigationTitle, investigationArtwork = false, titleRef, editInvestigation }: { goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; investigationTitle?: string; investigationArtwork?: boolean; titleRef?: Ref<HTMLHeadingElement>; editInvestigation?: { view: InvestigationView; onSaved: (view: InvestigationView) => void; disabled: boolean } }) {
  return <header className={investigationArtwork ? 'site-header investigation-art-header' : 'site-header'}>
    <div className="brand-block">
      <a href="/" className={investigationArtwork ? 'brand investigation-header-art' : 'brand'} onClick={goHome} aria-label="SIGMA home"><img src={investigationArtwork ? '/sigma-investigation-header.png' : '/sigma-workspace-logo.png'} alt="SIGMA" /></a>
      {investigationArtwork ? investigationTitle && <div className="investigation-title-line">
        {close && <button className="investigation-back" type="button" onClick={close.action} disabled={close.busy} aria-label="Close investigation" title="Back to investigations"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m14 5-7 7 7 7M7 12h13"/></svg></button>}
        {editInvestigation ? <InlineInvestigationTitle {...editInvestigation} titleRef={titleRef}/> : <h1 ref={titleRef} tabIndex={-1} className="current-investigation">{investigationTitle}</h1>}
      </div>
        : <p className="expansion">Strategy Investigation, Generation, Measurement &amp; Assessment</p>}
    </div>
    <div className="header-controls">
    {!close && <span className="local">● Local workspace</span>}
    <ConnectionStatus/>
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

function WorkspaceFrame({ children, goHome, close, investigationTitle, titleRef, editInvestigation }: {
  children: React.ReactNode; goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; investigationTitle?: string; titleRef?: Ref<HTMLHeadingElement>; editInvestigation?: { view: InvestigationView; onSaved: (view: InvestigationView) => void; disabled: boolean };
}) {
  const [collapsed, setCollapsed] = useState(() => window.localStorage.getItem('sigma.sidebarCollapsed') === 'true');
  function toggleSidebar() {
    setCollapsed(value => {
      window.localStorage.setItem('sigma.sidebarCollapsed', String(!value));
      return !value;
    });
  }
  return <>
    <a className="workspace-skip" href="#workspace-content" onClick={event => {
      event.preventDefault(); focusWorkspace('workspace-content');
    }}>Skip to investigation content</a>
    <Header goHome={goHome} close={close} investigationTitle={investigationTitle} titleRef={titleRef} editInvestigation={editInvestigation} investigationArtwork/>
    <div className={`workspace-layout${collapsed ? ' nav-collapsed' : ''}`}>
      <nav className="workspace-nav" aria-label="Investigation navigation">
        <button className="nav-collapse" type="button" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={toggleSidebar}><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={collapsed ? 'm9 6 6 6-6 6' : 'm15 6-6 6 6 6'}/></svg></button>
        <a href="#pool-heading" aria-current="page" aria-label="Strategies" title={collapsed ? 'Strategies' : undefined} onClick={event => {
          event.preventDefault(); focusWorkspace('pool-heading');
        }}><WorkspaceIcon name="Strategies"/><span>Strategies</span></a>
        {['Renders', 'Analysis', 'References', 'Notes', 'Settings'].map(name =>
          <button key={name} disabled title={collapsed ? `${name} · later` : 'Not available yet'} aria-label={name} aria-describedby="workspace-nav-help">
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

function InvestigationEntryDialog({ initialPath, onOpen, onCancel }: {
  initialPath: string; onOpen: (view: InvestigationView) => void; onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const first = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const [path, setPath] = useState(initialPath);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { dialog.current?.showModal(); first.current?.focus(); }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current) return; submitting.current = true; setBusy(true); setError('');
    try { onOpen(await post<InvestigationView>('open', { path })); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className="investigation-entry-dialog" aria-labelledby="investigation-entry-heading" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <h2 id="investigation-entry-heading">Open Investigation</h2><p className="entry-help">Choose an existing local investigation by its directory path.</p>
    <form onSubmit={save}><fieldset disabled={busy}><label htmlFor="open-investigation-path">Investigation directory</label><input ref={first} id="open-investigation-path" required value={path} onChange={event => setPath(event.target.value)} aria-describedby="investigation-path-help"/><p id="investigation-path-help" className="entry-hint">Try <code>investigations/rh.sigma</code>, or an absolute path such as <code>/Users/you/investigations/question.sigma</code>. Paths refer to this local server.</p>
    {error && <p className="error" role="alert">{error}</p>}<div className="entry-dialog-actions"><button type="submit">{busy ? 'Opening…' : 'Open Investigation'}</button><button type="button" className="entry-cancel" onClick={onCancel}>Cancel</button></div></fieldset></form>
  </dialog>;
}

type Settings = { title: string; problem: string; investigation_type: ResearchMode; ai_model: string; reasoning_effort: string };
type CatalogChoice = { id: string; label: string; description: string; efforts: string[]; availability: 'available' | 'unavailable' | 'unverified' };
const thinkingLabels: Record<string, string> = { low: 'Low', medium: 'Medium', high: 'High', xhigh: 'Extra high' };
const settingsOf = (view: InvestigationView): Settings => ({ title: view.investigation.title, problem: view.investigation.problem, investigation_type: view.investigation.investigation_type, ai_model: view.investigation.ai_model, reasoning_effort: view.investigation.reasoning_effort });

function InvestigationSettingsDialog({ initial, onSaved, onCancel }: { initial?: InvestigationView; onSaved: (view: InvestigationView) => void; onCancel: () => void }) {
  const ai = useAI();
  const dialog = useRef<HTMLDialogElement>(null);
  const first = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const [values, setValues] = useState<Settings>(() => initial ? settingsOf(initial) : { title: '', problem: '', investigation_type: 'default', ai_model: '', reasoning_effort: 'high' });
  const [catalog, setCatalog] = useState<CatalogChoice[]>([]);
  const [catalogMessage, setCatalogMessage] = useState('Checking model availability…');
  const [destination, setDestination] = useState<Destination | null>(null);
  const [locationError, setLocationError] = useState('');
  const [previewBusy, setPreviewBusy] = useState(!initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { dialog.current?.showModal(); first.current?.focus(); }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/ai/models', { signal: controller.signal }).then(async response => { if (!response.ok) throw new Error('Model catalog unavailable. Check the local server; existing settings are retained.'); return response.json(); }).then(data => {
      setCatalog(data.models); setCatalogMessage(data.message);
      if (!initial) setValues(previous => previous.ai_model ? previous : { ...previous, ai_model: data.default_model, reasoning_effort: data.default_effort });
    }).catch(error => { if (!controller.signal.aborted) setCatalogMessage(errorMessage(error)); });
    return () => controller.abort();
  }, [ai.info?.mode, ai.info?.active_account]);
  useEffect(() => {
    if (initial) return;
    const controller = new AbortController(); setPreviewBusy(true); setDestination(null); setLocationError('');
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/investigations/destination?${new URLSearchParams({ title: values.title })}`, { signal: controller.signal });
        const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Investigation location unavailable');
        setDestination(data);
      } catch (error) { if (!controller.signal.aborted) setLocationError(errorMessage(error)); }
      finally { if (!controller.signal.aborted) setPreviewBusy(false); }
    }, values.title ? 180 : 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [values.title]);
  function change(key: keyof Settings, value: string) { setValues(previous => ({ ...previous, [key]: value })); }
  const selected = catalog.find(model => model.id === values.ai_model);
  const samePair = !!initial && values.ai_model === initial.investigation.ai_model && values.reasoning_effort === initial.investigation.reasoning_effort;
  const compatible = selected?.efforts.includes(values.reasoning_effort) || samePair;
  const pairError = selected && !selected.efforts.includes(values.reasoning_effort) && !samePair ? 'This model does not support the selected Thinking level. Choose a supported level explicitly.' : '';
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current || !compatible || (!initial && (!destination?.path || destination.exists || previewBusy))) return;
    submitting.current = true; setBusy(true); setError('');
    try { onSaved(await post<InvestigationView>(initial ? 'update' : 'create', initial ? { path: initial.path, ...values, expected: settingsOf(initial) } : values)); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className={`investigation-settings-dialog ${initial ? 'edit-investigation-dialog' : 'new-investigation-dialog'}`} aria-labelledby="investigation-settings-heading" aria-describedby="investigation-settings-help" onCancel={event => { event.preventDefault(); if (!submitting.current) onCancel(); }}>
    <form onSubmit={save}>
      <header className="settings-header"><h2 id="investigation-settings-heading">{initial ? 'Investigation Settings' : 'New Investigation'}</h2>
        <div className="settings-actions"><button type="submit" disabled={busy || !values.ai_model || !compatible || !!pairError || (!initial && (!values.problem.trim() || previewBusy || !destination?.path || destination.exists))}>{busy ? 'Saving…' : initial ? 'Save' : 'Create'}</button><button className="settings-cancel" type="button" disabled={busy} onClick={() => { if (!submitting.current) onCancel(); }}>Cancel</button></div>
      </header>
      <div className="settings-body"><p id="investigation-settings-help">{initial ? 'Choose how to explore this investigation. Edit its title and description directly on the investigation page.' : 'Name an investigation and choose how to explore it.'}</p>
      <fieldset disabled={busy}>
      {!initial && <><label htmlFor="investigation-name">Investigation name</label><input ref={first} id="investigation-name" required maxLength={200} value={values.title} onChange={event => change('title', event.target.value)}/>
      <label htmlFor="investigation-problem">Research problem</label><textarea id="investigation-problem" required maxLength={20000} rows={4} value={values.problem} onChange={event => change('problem', event.target.value)}/></>}
      <label htmlFor="investigation-mode">Investigation type</label><select id="investigation-mode" value={values.investigation_type} onChange={event => change('investigation_type', event.target.value)}><option value="default">Default</option><option value="mathematical">Mathematical</option></select>
      <label htmlFor="investigation-model">LLM Model</label><select id="investigation-model" required value={values.ai_model} onChange={event => change('ai_model', event.target.value)} aria-describedby="investigation-model-help">
        {!values.ai_model && <option value="" disabled>Loading reviewed choices…</option>}
        {values.ai_model && !selected && <option value={values.ai_model}>{values.ai_model} · unavailable/unreviewed</option>}
        {catalog.map(model => <option key={model.id} value={model.id}>{model.label}{model.availability === 'available' ? '' : model.availability === 'unavailable' ? ' · unavailable' : ' · access unverified'}</option>)}
      </select>
      <p id="investigation-model-help" className="settings-hint">{ai.info?.mode === 'api_key' ? 'OpenAI API · billed separately. ' : 'ChatGPT plan allowance or credits · connection required for generation. '}{selected?.description} {catalogMessage}{selected?.availability === 'unavailable' ? ' Your selected model is unavailable; it will not be replaced automatically.' : ''}</p>
      <label htmlFor="investigation-thinking">Thinking level</label><select id="investigation-thinking" value={values.reasoning_effort} onChange={event => change('reasoning_effort', event.target.value)}>
        {!selected?.efforts.includes(values.reasoning_effort) && <option value={values.reasoning_effort}>{thinkingLabels[values.reasoning_effort] ?? values.reasoning_effort} · {selected ? 'unsupported' : 'preserved'}</option>}
        {(selected?.efforts ?? []).map(effort => <option key={effort} value={effort}>{thinkingLabels[effort] ?? effort}</option>)}
      </select>
      <p className="settings-hint">Applies to future AI proposals. Higher thinking can take longer and consume more usage. API cost tiers are relative; <a href="https://developers.openai.com/api/docs/pricing" target="_blank" rel="noreferrer">current token prices</a>. Earlier strategy provenance stays unchanged.</p>
      {pairError && <p className="error" role="alert">{pairError}</p>}
      <p className="investigation-destination"><span>Investigation location</span><code>{initial ? initial.path : previewBusy ? 'Checking location…' : destination?.path ?? destination?.root ?? 'Location unavailable'}</code><small>{initial ? 'Editing the display name never renames or moves this directory.' : 'The investigation name determines its directory; existing files are never overwritten.'}</small></p>
      {locationError && <p className="error" role="alert">{locationError}</p>}
      {destination?.exists && <p className="error" role="alert">An investigation or file already exists here. Choose another name.</p>}
      {error && <p className="error" role="alert">{error}</p>}
    </fieldset></div></form>
  </dialog>;
}

type RecentInvestigation = { id: string; path: string; title: string; investigation_type: string | null; strategy_count: number | null; available: boolean; error: string | null };
type StockInvestigation = { id: string; title: string; problem: string; investigation_type: string; strategy_count: number };
const strategyCount = (count: number) => `${count} ${count === 1 ? 'strategy' : 'strategies'}`;
function RecentInvestigations({ onOpen }: { onOpen: (view: InvestigationView) => void }) {
  const [investigations, setInvestigations] = useState<RecentInvestigation[]>([]);
  const [loading, setLoading] = useState(true);
  const [opening, setOpening] = useState('');
  const [error, setError] = useState('');
  const pending = useRef(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch('/api/investigations/recent', { signal });
    const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Recent Investigations unavailable. Open Investigation still works.');
    setInvestigations(data.investigations); setLoading(false);
  }, []);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal).catch(error => { if (!controller.signal.aborted) { setError(errorMessage(error)); setLoading(false); } }); return () => controller.abort(); }, [load]);
  async function open(entry: RecentInvestigation) {
    if (pending.current) return; pending.current = true; setOpening(entry.id); setError('');
    try { onOpen(await post<InvestigationView>('open', { path: entry.path })); }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setOpening(''); }
  }
  async function forget(entry: RecentInvestigation) {
    if (pending.current) return; pending.current = true; setOpening(entry.id); setError('');
    try { await post('recent/forget', { investigation_id: entry.id }); await load(); }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setOpening(''); }
  }
  return <div className="empty home-empty home-recents">
    {loading ? <p role="status">Loading recent investigations…</p> : !investigations.length && <p>No recent investigations yet. Open an investigation or begin a new one.</p>}
    <ul>{investigations.map(entry => <li key={entry.id}>
      <div className="recent-entry">
        <div className="recent-title-row">
          <button className="recent-open" disabled={!entry.available || !!opening} onClick={() => void open(entry)}><strong>{entry.title}</strong></button>
          <button className="recent-forget" disabled={!!opening} aria-label={`Remove ${entry.title} from Recent Investigations`} title="Remove from Recent Investigations; keep all research" onClick={() => void forget(entry)}>Remove</button>
        </div>
        <small>{entry.investigation_type === 'mathematical' ? 'Mathematical' : entry.investigation_type === 'default' ? 'Default' : 'Unavailable'}{entry.strategy_count === null ? '' : ` · ${strategyCount(entry.strategy_count)}`}</small>
        <span title={entry.path}>{entry.path}</span>
      </div>
      {entry.error && <p className="recent-unavailable">{entry.error}</p>}
    </li>)}</ul>
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function StockInvestigations({ onOpen }: { onOpen: (view: InvestigationView) => void }) {
  const [investigations, setInvestigations] = useState<StockInvestigation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [opening, setOpening] = useState('');
  const pending = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    void fetch('/api/investigations/stock', { signal: controller.signal }).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? 'Stock Investigations unavailable.');
      setInvestigations(data.investigations); setLoading(false);
    }).catch(error => { if (!controller.signal.aborted) { setError(errorMessage(error)); setLoading(false); } });
    return () => controller.abort();
  }, []);
  async function open(stock: StockInvestigation) {
    if (pending.current) return; pending.current = true; setOpening(stock.id); setError('');
    try { onOpen(await post<InvestigationView>('stock/open', { stock_id: stock.id })); }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setOpening(''); }
  }
  return <div className="empty home-empty home-stock">
    {loading ? <p role="status">Loading stock investigations…</p> : !investigations.length && !error && <p>No stock investigations are available.</p>}
    <ul>{investigations.map(stock => <li key={stock.id}><button className="stock-open" disabled={!!opening} onClick={() => void open(stock)} aria-label={`Open ${stock.title}`}><strong>{stock.title}</strong><small>{stock.investigation_type === 'mathematical' ? 'Mathematical' : 'Default'} · {strategyCount(stock.strategy_count)}</small></button></li>)}</ul>
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function HomeCatalog({ onOpen }: { onOpen: (view: InvestigationView) => void }) {
  const [tab, setTab] = useState<'recent' | 'stock'>('stock');
  const recent = useRef<HTMLButtonElement>(null);
  const stock = useRef<HTMLButtonElement>(null);
  function switchTab(next: 'recent' | 'stock') { setTab(next); (next === 'recent' ? recent : stock).current?.focus(); }
  return <div className="home-catalog"><div className="catalog-tabs" role="tablist" aria-label="Investigation lists" onKeyDown={event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); switchTab(tab === 'recent' ? 'stock' : 'recent'); }
    if (event.key === 'Home') { event.preventDefault(); switchTab('stock'); }
    if (event.key === 'End') { event.preventDefault(); switchTab('recent'); }
  }}>
    <button ref={stock} id="stock-tab" role="tab" aria-controls="stock-panel" aria-selected={tab === 'stock'} tabIndex={tab === 'stock' ? 0 : -1} onClick={() => setTab('stock')}>Stock Investigations</button>
    <button ref={recent} id="recent-tab" role="tab" aria-controls="recent-panel" aria-selected={tab === 'recent'} tabIndex={tab === 'recent' ? 0 : -1} onClick={() => setTab('recent')}>Recent Investigations</button>
  </div>
    <div id="recent-panel" role="tabpanel" aria-labelledby="recent-tab" hidden={tab !== 'recent'}><RecentInvestigations onOpen={onOpen}/></div>
    <div id="stock-panel" role="tabpanel" aria-labelledby="stock-tab" hidden={tab !== 'stock'}><StockInvestigations onOpen={onOpen}/></div>
  </div>;
}

function Home({ initialPath, currentPath, onOpen, goHome }: {
  initialPath: string; currentPath: string; onOpen: (view: InvestigationView) => void;
  goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const [entry, setEntry] = useState<'open' | 'new' | null>(null);
  const [currentInvestigation, setCurrentInvestigation] = useState<InvestigationView | null>(null);
  const [reopening, setReopening] = useState(false);
  const [currentError, setCurrentError] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  const openButton = useRef<HTMLButtonElement>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  useEffect(() => { document.title = 'SIGMA · Research workspace'; heading.current?.focus(); }, []);
  useEffect(() => {
    if (!currentPath) { setCurrentInvestigation(null); return; }
    const controller = new AbortController();
    fetch(`/api/investigations/inspect?${new URLSearchParams({ path: currentPath })}`, { signal: controller.signal })
      .then(async response => response.ok ? await response.json() as InvestigationView : null)
      .then(setCurrentInvestigation)
      .catch(() => { if (!controller.signal.aborted) setCurrentInvestigation(null); });
    return () => controller.abort();
  }, [currentPath]);
  async function reopenCurrent() {
    if (!currentInvestigation || reopening) return;
    setReopening(true); setCurrentError('');
    try { onOpen(await post<InvestigationView>('open', { path: currentInvestigation.path })); }
    catch (cause) { setCurrentError(errorMessage(cause)); }
    finally { setReopening(false); }
  }
  function cancel() {
    const trigger = entry === 'open' ? openButton : newButton;
    setEntry(null); requestAnimationFrame(() => trigger.current?.focus());
  }
  return <div className="home-shell">
    <div className="home-atmosphere" aria-hidden="true"/>
    <div className="home-content">
    <div className="home-topline"><img className="home-slogan" src="/sigma-slogan-copper-approved.png" alt="Strategy · Investigation · Generation · Measurement · Assessment"/><ConnectionStatus/></div>
    <div className="home-hero">
    {currentInvestigation && <div className="home-current"><p>Current Investigation</p><button type="button" disabled={reopening} onClick={() => void reopenCurrent()}><span className="home-current-title">{currentInvestigation.investigation.title}</span><span className="home-current-arrow" aria-hidden="true"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m10 5 7 7-7 7M17 12H4"/></svg></span></button></div>}
    {currentError && <p role="alert" className="error">{currentError}</p>}
    <h1 ref={heading} tabIndex={-1}>Switch to a new investigation</h1>
    <p className="intro">Open an existing investigation or begin a new investigation.</p>
    </div>
    <div className="home-entry-actions">
      <button ref={openButton} className="copper-button" onClick={() => setEntry('open')}>Open Investigation</button>
      <button ref={newButton} className="copper-button" onClick={() => setEntry('new')}>New Investigation</button>
    </div>
    <HomeCatalog onOpen={onOpen}/>
    {entry === 'open' && <InvestigationEntryDialog initialPath={initialPath} onOpen={onOpen} onCancel={cancel}/>}
    {entry === 'new' && <InvestigationSettingsDialog onSaved={onOpen} onCancel={cancel}/>}
    </div>
  </div>;
}

function StrategyTitleEditor({ strategy, path, onSaved }: {
  strategy: Strategy; path: string; onSaved: (view: InvestigationView) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(strategy.title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { if (!editing) setDraft(strategy.title); }, [strategy.title, editing]);
  useEffect(() => { if (editing) { input.current?.focus(); input.current?.select(); } }, [editing]);
  function cancel() {
    setEditing(false); setDraft(strategy.title); setError('');
    requestAnimationFrame(() => trigger.current?.focus());
  }
  async function save(event: FormEvent) {
    event.preventDefault(); event.stopPropagation();
    if (busy || !draft.trim()) return;
    setBusy(true); setError('');
    try {
      const next = await post<InvestigationView>('strategies/edit', {
        path, strategy_id: strategy.id, title: draft, approach: strategy.approach,
      });
      setEditing(false); onSaved(next);
      requestAnimationFrame(() => trigger.current?.focus());
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <div className={`strategy-title-editor${editing ? ' is-renaming' : ''}`}
    onClick={event => { event.stopPropagation(); }}
    onKeyDown={event => { event.stopPropagation(); if (event.key === 'Escape' && editing && !busy) { event.preventDefault(); cancel(); } }}>
    {editing ? <form onSubmit={save} className="strategy-rename-form">
      <input ref={input} aria-label="Strategy name" value={draft} maxLength={200} disabled={busy}
        required onChange={event => setDraft(event.target.value)}/>
      <button type="submit" className="text-view-link" disabled={busy || !draft.trim()}>Save</button>
      <button type="button" className="text-view-link" disabled={busy} onClick={cancel}>Cancel</button>
    </form> : <h3 id={`strategy-${strategy.id}`} tabIndex={-1}>
      <button type="button" ref={trigger} className="strategy-title-edit" aria-label={`Rename strategy: ${strategy.title}`}
        onClick={() => setEditing(true)}>{strategy.title}</button>
    </h3>}
    {error && <p className="error" role="alert">{error}</p>}
  </div>;
}

function StrategyCommands({ strategy, onCommand }: {
  strategy: Strategy; onCommand: (mode: 'remove' | 'stage' | 'fork', strategy: Strategy) => void;
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
      <button className="secondary" disabled title="Scheduling is not available yet">Pause / Resume</button>
      <button className="secondary" disabled title="Audit reports are not available yet">Audit</button>
      <button className="secondary" disabled title="Additional artifact types are not available yet">Other artifact types</button>
      <button className="secondary" onClick={() => { if (disclosure.current) disclosure.current.open = false; onCommand('stage', strategy); }}>Change stage</button>
      <button className="secondary" onClick={() => { if (disclosure.current) disclosure.current.open = false; onCommand('remove', strategy); }}>Remove</button>
      <button className="secondary" onClick={() => { if (disclosure.current) disclosure.current.open = false; onCommand('fork', strategy); }}>Fork</button>
    </div>
  </details>;
}

function StrategyDialog({ mode, strategy, path, onSaved, onCancel }: {
  mode: 'edit' | 'remove' | 'stage'; strategy: Strategy; path: string;
  onSaved: (view: InvestigationView, mode: 'edit' | 'remove' | 'stage', strategy: Strategy) => void;
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
      const next = await post<InvestigationView>(`strategies/${mode}`, {
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
      ? 'Update the name and description. Earlier text remains in investigation history.'
      : mode === 'stage' ? 'Stages are manually tracked. Exploring means you are investigating; no AI agent is running.' : 'This strategy will leave Strategies. Its idea and history will be kept in the investigation.'}</p>
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

function NewStrategy({ path, onSaved, onCancel, initialDraft }: {
  path: string; initialDraft?: { title: string; approach: string; summary?: string }; onSaved: (view: InvestigationView) => void; onCancel: () => void;
}) {
  const submitting = useRef(false);
  const [title, setTitle] = useState(initialDraft?.title ?? '');
  const [approach, setApproach] = useState(initialDraft?.approach ?? '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const titleInput = useRef<HTMLInputElement>(null);
  useEffect(() => { titleInput.current?.focus(); }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current) return; submitting.current = true; setBusy(true); setError('');
    try { onSaved(await post<InvestigationView>('strategies', { path, title, approach, summary: initialDraft?.summary ?? '' })); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <form className="strategy-form" aria-labelledby="new-strategy-heading" onSubmit={save}
    onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); onCancel(); } }}>
    <div className="new-strategy-heading-row"><h3 id="new-strategy-heading">New strategy</h3><div className="new-strategy-heading-actions"><button type="submit" className="text-view-link" disabled={busy}>{busy ? "Saving…" : "Save"}</button><button type="button" className="text-view-link" disabled={busy} onClick={onCancel}>Cancel</button></div></div>
    <p className="hint">Capture an idea and the approach you want to investigate.</p>
    <fieldset disabled={busy}>
      <label htmlFor="strategy-title">Title</label>
      <input ref={titleInput} id="strategy-title" value={title} maxLength={200} required
        onChange={event => setTitle(event.target.value)} />
      <label htmlFor="strategy-approach">Hypothesis / approach</label>
      <textarea id="strategy-approach" value={approach} maxLength={10000} required rows={5}
        onChange={event => setApproach(event.target.value)} />
      {error && <p role="alert" className="error">{error}</p>}
    </fieldset>
  </form>;
}

function StrategyCreationActions({ buttonRef, disabled, onManual, onAI }: {
  buttonRef: React.RefObject<HTMLButtonElement | null>; disabled: boolean; onManual: () => void; onAI: () => void;
}) {
  return <div className="strategy-heading-actions">
    <button type="button" className="text-view-link" ref={buttonRef} disabled={disabled} onClick={onManual}>New</button>
    <button type="button" className="text-view-link" disabled={disabled} onClick={onAI}>Generate</button>
  </div>;
}

type ProposalResult = { draft: { title: string; summary: string; approach: string; first_tests: string; assumptions: string; failure_modes: string }; provenance: { provider: string; model: string; reasoning_effort?: string | null }; receipt: string };
type AgenticEvent = { type: 'run.started' | 'activity.started' | 'activity.completed' | 'decision' | 'run.completed' | 'run.stopped' | 'run.failed'; sequence: number; run_id: string; kind?: 'explore' | 'challenge' | 'revise'; attempt?: number; summary?: string; outcome?: 'revise' | 'retry' | 'present' | 'stop'; max_calls?: number; draft?: ProposalResult['draft']; receipt?: string; provenance?: ProposalResult['provenance']; assessment?: 'distinct' | 'overlapping' | 'unconvincing'; objections?: string[]; missing_obligations?: string; mechanism_comparison?: string };
function agenticEvent(value: unknown, previous: number, runId: string | null): AgenticEvent {
  if (!value || typeof value !== 'object') throw new Error('Invalid progress event from local server.');
  const event = value as AgenticEvent;
  if (!['run.started', 'activity.started', 'activity.completed', 'decision', 'run.completed', 'run.stopped', 'run.failed'].includes(event.type)
    || event.sequence !== previous + 1 || typeof event.run_id !== 'string' || !/^[a-f0-9]{32}$/.test(event.run_id)
    || (runId !== null && event.run_id !== runId)
    || (event.summary !== undefined && (typeof event.summary !== 'string' || event.summary.length > 500))) throw new Error('Invalid progress event from local server.');
  if (event.type.startsWith('activity.') && (!['explore', 'challenge', 'revise'].includes(event.kind ?? '') || ![1, 2].includes(event.attempt ?? 0))) throw new Error('Invalid activity event from local server.');
  if (event.type === 'activity.completed' && event.kind === 'challenge' && (!['distinct', 'overlapping', 'unconvincing'].includes(event.assessment ?? '') || !Array.isArray(event.objections) || !event.objections.length || event.objections.length > 5 || event.objections.some(item => typeof item !== 'string' || item.length > 500) || typeof event.missing_obligations !== 'string' || typeof event.mechanism_comparison !== 'string')) throw new Error('Invalid reviewer event from local server.');
  if (event.type === 'decision' && (!['revise', 'retry', 'present', 'stop'].includes(event.outcome ?? '') || !event.summary)) throw new Error('Invalid decision event from local server.');
  if (['run.failed', 'run.stopped'].includes(event.type) && !event.summary) throw new Error('Invalid terminal event from local server.');
  if (event.type === 'run.completed' && (!event.draft || !event.receipt || !event.provenance || !['title', 'summary', 'approach', 'first_tests', 'assumptions', 'failure_modes'].every(key => typeof event.draft?.[key as keyof ProposalResult['draft']] === 'string'))) throw new Error('Invalid completed draft from local server.');
  return event;
}
async function readAgenticStream(response: Response, onEvent: (event: AgenticEvent) => void): Promise<void> {
  if (!response.ok) throw new Error(`Local generation request failed (HTTP ${response.status}).`);
  if (!response.headers.get('content-type')?.startsWith('text/event-stream') || !response.body) throw new Error('Local server did not return a progress stream.');
  const reader = response.body.getReader(); const decoder = new TextDecoder();
  let buffer = ''; let sequence = 0; let runId: string | null = null; let terminal: AgenticEvent | null = null;
  let active: { kind: string; attempt: number } | null = null;
  let decision: AgenticEvent['outcome'] | null = null;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
      if (buffer.length > 65536) throw new Error('Progress stream exceeded its limit.');
      let boundary: number;
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
        const lines = frame.split('\n');
        if (lines.length !== 1 || !lines[0].startsWith('data: ')) throw new Error('Invalid progress stream frame.');
        let parsed: unknown;
        try { parsed = JSON.parse(lines[0].slice(6)); } catch { throw new Error('Invalid progress event JSON.'); }
        const event = agenticEvent(parsed, sequence, runId);
        if (terminal) throw new Error('Progress arrived after the run ended.');
        if (sequence === 0 && event.type !== 'run.started' && event.type !== 'run.failed') throw new Error('Progress stream did not start correctly.');
        if (event.type === 'run.started' && (sequence !== 0 || event.max_calls !== 6)) throw new Error('Invalid run start event.');
        if (event.type === 'activity.started') {
          if (active || decision === 'present' || decision === 'stop') throw new Error('Invalid activity order.');
          active = { kind: event.kind!, attempt: event.attempt! };
        }
        if (event.type === 'activity.completed') {
          if (!active || active.kind !== event.kind || active.attempt !== event.attempt || !event.summary) throw new Error('Invalid activity completion.');
          active = null;
        }
        if (event.type === 'decision') {
          if (active) throw new Error('Decision arrived before activity completed.');
          decision = event.outcome!;
        }
        if ((event.type === 'run.completed' && decision !== 'present') || (event.type === 'run.stopped' && decision !== 'stop')) throw new Error('Invalid run outcome.');
        sequence = event.sequence; runId = event.run_id;
        if (['run.completed', 'run.stopped', 'run.failed'].includes(event.type)) terminal = event;
        else onEvent(event);
        if (sequence > 32) throw new Error('Progress stream exceeded its event limit.');
      }
    }
    if (buffer.trim() || !terminal) throw new Error('Generation stream ended before a final result. Nothing was saved.');
    onEvent(terminal);
  } finally { reader.releaseLock(); }
}
function GenerateStrategy({ path, investigationId, onSaved, onCancel, onManual }: {
  path: string; investigationId: string; onManual: (draft: { title: string; approach: string }) => void; onSaved: (view: InvestigationView) => void; onCancel: () => void;
}) {
  const composer = useRef<HTMLDivElement>(null);
  const request = useRef<AbortController | null>(null);
  const submitting = useRef(false);
  const [config, setConfig] = useState<{ available: boolean; provider: string; mode: string; binding: string; investigation_id: string; model: string; reasoning_effort: string; message: string } | null>(null);
  const [seed, setSeed] = useState('');
  const ai = useAI();
  const lifetime = useRef(new AbortController());
  const [result, setResult] = useState<ProposalResult | null>(null);
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [approach, setApproach] = useState('');
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState<AgenticEvent[]>([]);
  const [currentActivity, setCurrentActivity] = useState('');
  const [stopped, setStopped] = useState('');
  useEffect(() => {
    composer.current?.querySelector('textarea')?.focus();
    const controller = new AbortController();
    fetch(`/api/investigations/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal }).then(async response => { if (!response.ok) throw new Error('Could not read AI configuration'); return response.json(); }).then(setConfig).catch(error => { if (!controller.signal.aborted) setError(errorMessage(error)); });
    return () => { controller.abort(); lifetime.current.abort(); request.current?.abort(); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/investigations/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal }).then(response => response.json()).then(setConfig).catch(() => {});
    return () => controller.abort();
  }, [ai.info?.mode, ai.info?.active_account, ai.info?.status]);
  const needsConnection = ai.info?.mode !== 'api_key' && ['disconnected', 'reauth_required', 'unauthorized', 'plan_not_permitted'].includes(ai.info?.status ?? 'disconnected');
  function cancel() { if (saving) return; if (busy) { request.current?.abort(); setCurrentActivity(''); setStopped('Request cancelled locally. Provider computation or billing may already have begun.'); setBusy(false); submitting.current = false; return; } lifetime.current.abort(); onCancel(); }
  async function generate() {
    if (submitting.current) return; submitting.current = true;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError(''); setStopped(''); setProgress([]); setCurrentActivity('');
    try {
      if (needsConnection) {
        const connected = await ai.signIn({ accountId: ai.info?.active_account, enablePlan: ai.info?.status === 'plan_not_permitted', signal: lifetime.current.signal });
        if (!connected || lifetime.current.signal.aborted) return;
      }
      const response = await fetch(`/api/investigations/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal });
      if (!response.ok) throw new Error('Could not read current AI settings. Retry explicitly.');
      const latest = await response.json(); setConfig(latest);
      if (latest.investigation_id !== investigationId) throw new Error('Investigation identity changed during sign-in. Reopen it before generating; your text is retained.');
      if (!latest.available) throw new Error(latest.message);
      if (lifetime.current.signal.aborted) return;
      const stream = await fetch('/api/investigations/proposals/agentic', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path, seed, expected_binding: latest.binding, expected_investigation_id: investigationId }), signal: controller.signal });
      await readAgenticStream(stream, event => {
        setProgress(previous => [...previous, event]);
        if (event.type === 'activity.started') setCurrentActivity(event.summary ?? 'Working');
        if (event.type === 'activity.completed' || event.type === 'decision') setCurrentActivity('');
        if (event.type === 'run.stopped') setStopped(event.summary ?? 'No viable proposal emerged.');
        if (event.type === 'run.failed') setError(event.summary ?? 'Generation failed.');
        if (event.type === 'run.completed' && event.draft && event.receipt && event.provenance) {
          const next = { draft: event.draft, receipt: event.receipt, provenance: event.provenance };
          setResult(next); setTitle(next.draft.title); setSummary(next.draft.summary);
          setApproach(`${next.draft.approach}\n\nFirst tests\n${next.draft.first_tests}\n\nAssumptions\n${next.draft.assumptions}\n\nWays this could fail\n${next.draft.failure_modes}`);
          requestAnimationFrame(() => document.getElementById('proposal-title')?.focus());
        }
      });
    } catch (error) { if (!controller.signal.aborted) setError(errorMessage(error)); }
    finally { if (request.current === controller) { submitting.current = false; setBusy(false); request.current = null; setCurrentActivity(''); } }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current || !result) return; submitting.current = true; setSaving(true); setError('');
    try { onSaved(await post<InvestigationView>('strategies', { path, title, approach, summary, receipt: result.receipt })); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setSaving(false); }
  }
  return <div ref={composer} className="strategy-form proposal-dialog inline-proposal" role="region" aria-labelledby="proposal-heading" aria-describedby="proposal-help" onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); cancel(); } }}>
    <div className="proposal-heading-row"><h2 id="proposal-heading">Generate a strategy</h2>{!busy && <button type="button" className="text-view-link proposal-heading-manual" disabled={saving} onClick={() => { lifetime.current.abort(); onManual({ title, approach: approach || seed }); }}>Continue manually</button>}<button type="button" className="text-view-link proposal-heading-cancel" disabled={saving} onClick={cancel}>{busy ? "Cancel request" : "Cancel"}</button></div>
    {!busy && <p id="proposal-help" className="hint">Explore a direction, challenge it independently, and review the unsaved draft before saving. The reviewer does not verify a proof.</p>}
    <p className="provider-context">{config ? `${config.mode === 'api_key' ? 'OpenAI API · billed separately' : 'Using ChatGPT plan'} · ${config.model} · ${thinkingLabels[config.reasoning_effort] ?? config.reasoning_effort}` : 'Reading AI settings…'}{config?.mode === 'chatgpt' && <ManageUsage/>}</p>
    {config && !config.available && <p role="status" className="hint">{config.message}</p>}
    <details className="proposal-context" open={!result}><summary>Generation context &amp; starting point</summary>
    <label htmlFor="proposal-seed">Starting point <span className="hint">(optional)</span></label>
    <textarea id="proposal-seed" rows={3} maxLength={4000} value={seed} disabled={busy || saving} onChange={event => setSeed(event.target.value)} aria-describedby="seed-help"/>
    <p id="seed-help" className="hint">A hunch, question, technique, observation or constraint—not an assumption to endorse. Leave empty for an independent direction.</p>
    <p className="hint">Generation sends this problem, mode, all strategy titles/approaches (including removed ones), and the starting point to OpenAI. Up to 6 model calls, 2 candidate attempts and 2 minutes per run. Cancelling stops local work; provider usage may already count toward the selected plan or billing mode.</p>
    </details>
    {(busy || progress.length > 0) && <section className="agentic-activity" aria-label="Generation activity">
      {busy && <div className="agentic-filament" aria-hidden="true"/>}
      <p className="agentic-current" role="status" aria-live="polite">{busy ? <><span aria-hidden="true">⌛</span> Generating strategy…</> : currentActivity || (stopped || (error ? 'Run failed' : 'Review the draft below'))}</p>
      <ol>{progress.filter(event => event.type === 'activity.completed' || event.type === 'decision').map(event => <li key={event.sequence}>{event.summary}{event.kind === 'challenge' && event.assessment && <div className="agentic-review"><strong>Reviewer: {event.assessment}</strong><p>{event.mechanism_comparison}</p><ul>{event.objections?.map((objection, index) => <li key={index}>{objection}</li>)}</ul><p>Still to establish: {event.missing_obligations}</p></div>}</li>)}</ol>
    </section>}
    <PlanWelcome/>
    {!busy && <button type="button" className={`${needsConnection ? 'chatgpt-sign-in' : 'secondary'}${busy && !ai.connecting ? ' generating-action' : ''}`} disabled={(!config?.available && !needsConnection) || busy || saving || ai.connecting} onClick={() => void generate()}>{busy ? ai.connecting ? 'Connecting…' : <><span className="generating-hourglass" aria-hidden="true">⌛</span> Generating…</> : needsConnection ? <><img src="/chatgpt-logo-black.svg" alt="" width="20" height="20"/>Continue with ChatGPT</> : result ? 'Regenerate · new request' : 'Generate'}</button>}
    {ai.connecting && <button type="button" onClick={ai.cancelSignIn}>Cancel sign-in</button>}
    {ai.handoff && <a href={ai.handoff} target="_blank" rel="noreferrer">Open sign-in browser</a>}
    {ai.error && <p role="alert" className="error">{ai.error}</p>}
    {stopped && <p role="status" className="hint">{stopped}</p>}
    {error && <p role="alert" className="error">{error}</p>}
    <form onSubmit={save}>
      {result && <fieldset disabled={busy || saving} className="proposal-review">
        <legend>Unsaved draft · Review before accepting</legend>
        <label htmlFor="proposal-title">Title</label><input id="proposal-title" required maxLength={200} value={title} onChange={event => setTitle(event.target.value)}/>
        <label htmlFor="proposal-summary">One-line preview</label><input id="proposal-summary" required maxLength={300} value={summary} onChange={event => setSummary(event.target.value)}/>
        <label htmlFor="proposal-approach">Proposed approach, first tests, assumptions and failure modes</label><textarea id="proposal-approach" required maxLength={10000} rows={9} value={approach} onChange={event => setApproach(event.target.value)}/>
        <p className="hint">AI-assisted suggestion · {result.provenance.provider} / {result.provenance.model}{result.provenance.reasoning_effort ? ` · ${thinkingLabels[result.provenance.reasoning_effort] ?? result.provenance.reasoning_effort} thinking` : ''}. Saving records your acceptance and edits; it does not validate the research.</p>
      </fieldset>}
      <div className="form-actions">
        {result && <button type="submit" disabled={busy || saving}>{saving ? 'Saving…' : 'Save strategy'}</button>}
      </div>
    </form>
  </div>;
}

function InvestigationScreen({ path, initialView, onClose, goHome }: {
  path: string; initialView?: InvestigationView; onClose: () => void;
  goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const [view, setView] = useState<InvestigationView | null>(initialView ?? null);
  const [error, setError] = useState('');
  const [closing, setClosing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [manualDraft, setManualDraft] = useState<{ title: string; approach: string; summary?: string }>();
  const [investigationEditing, setInvestigationEditing] = useState(false);
  const editInvestigationButton = useRef<HTMLButtonElement>(null);
  const [ordering, setOrdering] = useState(false);
  const [previewOrder, setPreviewOrder] = useState<string[] | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const drag = useRef<{ id: string; order: string[]; pointer: number | null } | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const [command, setCommand] = useState<{ mode: 'remove' | 'stage'; strategy: Strategy } | null>(null);
  const [focusStrategy, setFocusStrategy] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  const introPane = useRef<HTMLDivElement>(null);
  const resizeStart = useRef<{ pointer: number; y: number; height: number } | null>(null);
  const [introHeight, setIntroHeight] = useState<number | null>(null);
  useEffect(() => {
    setIntroHeight(null);
    const frame = requestAnimationFrame(() => { if (introPane.current) setIntroHeight(Math.round(introPane.current.getBoundingClientRect().height)); });
    return () => cancelAnimationFrame(frame);
  }, [view?.investigation.id, view?.investigation.title, view?.investigation.problem]);
  useEffect(() => {
    if (initialView) return;
    const controller = new AbortController();
    post<InvestigationView>('open', { path }, controller.signal).then(setView).catch(error => {
      if (!controller.signal.aborted) setError(errorMessage(error));
    });
    return () => controller.abort();
  }, [path]);
  useEffect(() => {
    if (view) document.title = `${view.investigation.title} · SIGMA`;
    else if (error) document.title = 'Investigation unavailable · SIGMA';
    heading.current?.focus();
  }, [view?.investigation.id, view?.investigation.title, !!error]);
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
  const frame = { goHome, close: { action: close, busy: closing }, investigationTitle: view?.investigation.title, titleRef: heading,
    editInvestigation: view ? { view, onSaved: setView, disabled: closing || ordering || !!dragId || editing || generating } : undefined };
  function cancel() { setEditing(false); requestAnimationFrame(() => newButton.current?.focus()); }
  if (!view) return <WorkspaceFrame {...frame}><div className="workspace-state" aria-live="polite">{error ? <>
    <h1 ref={heading} tabIndex={-1}>Investigation unavailable</h1><p role="alert" className="error">{error}</p>
    <p>Close this investigation to choose another directory.</p>
  </> : <p className="intro">Opening investigation…</p>}</div></WorkspaceFrame>;
  const investigation = view.investigation;
  const introMaximum = Math.max(160, Math.min(Math.round(window.innerHeight * .75), 800));
  const clampIntro = (height: number) => Math.max(120, Math.min(introMaximum, Math.round(height)));
  const byId = new Map(investigation.strategies.map(strategy => [strategy.id, strategy]));
  const strategies = (previewOrder ?? investigation.active_order).map(id => byId.get(id)!);
  function pickup(id: string, pointer: number | null) {
    if (ordering || drag.current) return;
    drag.current = { id, order: [...investigation.active_order], pointer }; setDragId(id);
    setPreviewOrder([...investigation.active_order]);
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
    if (active.order.join() === investigation.active_order.join()) { setPreviewOrder(null); setAnnouncement('Order unchanged.'); return; }
    setOrdering(true); setError('');
    try {
      setView(await post<InvestigationView>('strategies/reorder', { path: view!.path, order: active.order, expected_order: investigation.active_order }));
      setAnnouncement('Strategy order saved.');
    } catch (error) { setError(errorMessage(error)); setAnnouncement('Order save failed. Previous order restored.'); }
    finally { setOrdering(false); setPreviewOrder(null); requestAnimationFrame(() => document.getElementById(`grip-${active.id}`)?.focus()); }
  }
  return <WorkspaceFrame {...frame}>
    <div className="investigation-intro" id="investigation-intro-pane" ref={introPane} style={introHeight === null ? undefined : { height: introHeight, maxHeight: 'min(75dvh, 800px)' }}>
      <div className="investigation-description-line"><h2 className="investigation-heading">Investigation</h2></div>
      <TextViews mathematical={investigation.investigation_type === 'mathematical'} path={view.path} scope="investigation" source={investigation.problem} contentClass="objective" onSaved={setView} onSettings={() => setInvestigationEditing(true)} settingsDisabled={closing || ordering || !!dragId || editing || generating} settingsButtonRef={editInvestigationButton}/>
    </div>
    <div className="investigation-pane-resizer" role="separator" tabIndex={0} aria-label="Resize investigation description" aria-controls="investigation-intro-pane" aria-orientation="horizontal" aria-valuemin={120} aria-valuemax={introMaximum} aria-valuenow={introHeight ?? undefined} title="Drag or use arrow keys to resize the investigation description"
      onPointerDown={event => { if (event.button !== 0) return; const height = introPane.current?.getBoundingClientRect().height ?? 120; resizeStart.current = { pointer: event.pointerId, y: event.clientY, height }; event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault(); }}
      onPointerMove={event => { const start = resizeStart.current; if (start?.pointer === event.pointerId) setIntroHeight(clampIntro(start.height + event.clientY - start.y)); }}
      onPointerUp={event => { if (resizeStart.current?.pointer === event.pointerId) resizeStart.current = null; }}
      onPointerCancel={event => { if (resizeStart.current?.pointer === event.pointerId) resizeStart.current = null; }}
      onKeyDown={event => { const current = introPane.current?.getBoundingClientRect().height ?? 120; if (event.key === 'ArrowUp' || event.key === 'ArrowDown') { event.preventDefault(); setIntroHeight(clampIntro(current + (event.key === 'ArrowDown' ? 24 : -24))); } else if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); setIntroHeight(event.key === 'Home' ? 120 : introMaximum); } }}><span aria-hidden="true"/></div>
    {error && <p role="alert" className="error">{error}</p>}
    <section className="pool" aria-labelledby="pool-heading">
      <div className="pool-heading">
        <h2 id="pool-heading" tabIndex={-1}>Strategies</h2>
        <StrategyCreationActions buttonRef={newButton} disabled={editing || generating || investigationEditing || closing || ordering || !!dragId} onManual={() => { setManualDraft(undefined); setEditing(true); }} onAI={() => setGenerating(true)}/>
      </div>
      <p className="hint strategies-intro">Independent avenues of investigation. Stages are manually tracked.</p>
      <p className="sr-only" role="status">{announcement}</p>
      <div id="strategy-composer">{editing && <NewStrategy initialDraft={manualDraft} path={view.path} onCancel={cancel} onSaved={next => {
        const strategy = next.investigation.strategies[next.investigation.strategies.length - 1];
        setView(next); setEditing(false); setAnnouncement(`Strategy saved: ${strategy.title}`);
        setFocusStrategy(strategy.id);
      }}/>}
      {generating && <GenerateStrategy path={view.path} investigationId={view.investigation.id} onManual={draft => { setManualDraft(draft); setGenerating(false); setEditing(true); }} onCancel={() => { setGenerating(false); requestAnimationFrame(() => newButton.current?.focus()); }} onSaved={next => {
        const strategy = next.investigation.strategies.at(-1)!; setView(next); setGenerating(false); setFocusStrategy(strategy.id); setAnnouncement('AI-assisted strategy accepted and saved.');
      }}/>}</div>
      {strategies.length ? <div className="strategies-table">
        <div className="strategy-columns" aria-hidden="true"><span>Strategy</span><span>Stage</span></div>
        <ol className="strategy-list" aria-label="Strategies" aria-busy={ordering}>
        {strategies.map(strategy => <li className={`strategy-row${dragId === strategy.id ? ' is-lifted' : ''}`} key={strategy.id} data-strategy-id={strategy.id}>
          <details className="strategy-detail">
            <summary title="Expand or collapse the full approach"><div className="strategy-title-line"><StrategyTitleEditor strategy={strategy} path={view.path} onSaved={setView}/><svg className="strategy-expand-arrow" viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M7 4 L19 12 L7 20 Z"/></svg></div>
              <span className="strategy-preview">{strategy.summary || strategy.approach.replace(/\s+/g, ' ')}</span>
              {strategy.provenance && <span className="ai-byline">AI-assisted · Human accepted</span>}
            </summary>
            <div className="strategy-expanded"><TextViews mathematical={investigation.investigation_type === 'mathematical'} path={view.path} scope="strategy" strategyId={strategy.id} source={strategy.approach} contentClass="strategy-approach" onSaved={setView}/>
              
            </div>
          </details>
          <span className={`stage-label stage-${strategy.stage}`} title="Manually tracked; no strategy runner"><i aria-hidden="true"/>{stageLabels[strategy.stage]}</span>
          <StrategyCommands strategy={strategy} onCommand={(mode, strategy) => { if (ordering || dragId || editing || generating || investigationEditing) return; if (mode === 'fork') { setManualDraft({ title: `${strategy.title} (forked)`, approach: strategy.approach, summary: strategy.summary }); setEditing(true); requestAnimationFrame(() => document.getElementById('strategy-composer')?.scrollIntoView({ block: 'nearest' })); } else setCommand({ mode, strategy }); }}/>
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
    {investigationEditing && <InvestigationSettingsDialog initial={view} onCancel={() => { setInvestigationEditing(false); requestAnimationFrame(() => editInvestigationButton.current?.focus()); }} onSaved={next => { setView(next); setInvestigationEditing(false); setAnnouncement('Investigation settings saved.'); requestAnimationFrame(() => editInvestigationButton.current?.focus()); }}/>}
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
    <details className="investigation-details">
      <summary>Investigation details &amp; history</summary>
      <dl><dt>Identity</dt><dd>{investigation.id}</dd><dt>Directory</dt><dd>{view.path}</dd><dt>Format version</dt><dd>{investigation.schema_version}</dd><dt>Investigation type</dt><dd>{investigation.investigation_type === 'mathematical' ? 'Mathematical' : 'Default'}</dd><dt>AI model</dt><dd>{investigation.ai_model}</dd><dt>Thinking level</dt><dd>{thinkingLabels[investigation.reasoning_effort] ?? investigation.reasoning_effort}</dd></dl>
      <h3>Event history</h3>
      <ol className="event-list">{investigation.events.map(event => <li key={event.sequence}>
        <span className="sequence">{String(event.sequence).padStart(2, '0')}</span>
        <div><span>{event.kind}</span><time dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time>
          {event.investigation_change && <details className="edit-history"><summary>View investigation changes</summary><dl>{(Object.keys(event.investigation_change.current) as (keyof Settings)[]).filter(key => event.investigation_change!.previous[key] !== event.investigation_change!.current[key]).map(key => <div key={key}><dt>{({ title: 'Investigation name', problem: 'Research problem', investigation_type: 'Investigation type', ai_model: 'AI model', reasoning_effort: 'Thinking level' })[key]}</dt><dd>Before: {event.investigation_change!.previous[key]}<br/>After: {event.investigation_change!.current[key]}</dd></div>)}</dl></details>}
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
      <p className="hint">Opening and inspecting an investigation leaves its history unchanged.</p>
    </details>
  </WorkspaceFrame>;
}

function App() {
  const [openedView, setOpenedView] = useState<InvestigationView | null>(null);
  const [location, setLocation] = useState(() => {
    if (window.location.pathname === '/project') window.history.replaceState(null, '', `/investigation${window.location.search}`);
    return window.location.pathname + window.location.search;
  });
  const [lastPath, setLastPath] = useState(() =>
    new URLSearchParams(window.location.search).get('path') || 'investigations/rh.sigma');
  const [currentPath, setCurrentPath] = useState(() => window.localStorage.getItem('sigma.currentInvestigation') ?? window.localStorage.getItem('sigma.currentProject') ?? '');
  useEffect(() => {
    const normalizeLegacyRoute = () => {
      if (window.location.pathname === '/project') window.history.replaceState(null, '', `/investigation${window.location.search}`);
    };
    normalizeLegacyRoute();
    const pop = () => { normalizeLegacyRoute(); setOpenedView(null); setLocation(window.location.pathname + window.location.search); };
    window.addEventListener('popstate', pop);
    return () => window.removeEventListener('popstate', pop);
  }, []);
  const navigate = useCallback((url: string) => {
    window.history.pushState(null, '', url); setLocation(url); window.scrollTo(0, 0);
  }, []);
  const closeInvestigation = useCallback(() => {
    setOpenedView(null);
    const path = new URLSearchParams(window.location.search).get('path');
    if (path) { setLastPath(path); setCurrentPath(path); window.localStorage.setItem('sigma.currentInvestigation', path); window.localStorage.setItem('sigma.currentProject', path); }
    navigate('/');
  }, [navigate]);
  function goHome(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      event.preventDefault(); setOpenedView(null); navigate('/');
    }
  }
  const url = new URL(location, window.location.origin);
  return <main className={url.pathname === '/' ? 'home-page' : 'workspace-page'}>
    {url.pathname === '/' ? <Home initialPath={lastPath} currentPath={currentPath} goHome={goHome} onOpen={view => {
      setOpenedView(view); setLastPath(view.path); setCurrentPath(view.path); window.localStorage.setItem('sigma.currentInvestigation', view.path); window.localStorage.setItem('sigma.currentProject', view.path); navigate(investigationUrl(view.path));
    }}/> : url.pathname === '/investigation' ? <InvestigationScreen key={location}
      initialView={openedView?.path === url.searchParams.get('path') ? openedView : undefined} path={url.searchParams.get('path') ?? ''} onClose={closeInvestigation} goHome={goHome}/>
      : <><Header goHome={goHome}/><h1>Page not found</h1><a href="/" onClick={goHome}>Return Home</a></>}
  </main>;
}

installRequestErrorToasts();
createRoot(document.getElementById('root')!).render(<AIProvider><App/><RequestErrorToasts/></AIProvider>);
