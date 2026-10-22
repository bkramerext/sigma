import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent, type Ref } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import './workspace.css';
import './project-entry.css';
import './strategies.css';
import './project-settings.css';
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
type ProjectView = {
  path: string;
  project: {
    id: string;
    title: string;
    problem: string;
    schema_version: number;
    ai_model: string;
    reasoning_effort: string;
    investigation_type: 'default' | 'mathematical';
    events: { sequence: number; kind: string; timestamp: string; strategy_id?: string | null;
      project_change?: { previous: Settings; current: Settings } | null;
      order?: string[] | null; stage_change?: { previous: Stage; stage: Stage } | null;
      change?: { previous_title: string; previous_approach: string; title: string; approach: string } | null }[];
    strategies: Strategy[];
    active_order: string[];
  };
};

type ResearchArtifact = { id: string; sequence: number; claim_or_question: string; method: string; assumptions: string[]; evidence_status: string; skeptic_response: string; objections: string[]; open_obligations: string[]; coordinator_decision: string; next_question: string; note: string; investigator_output: Record<string, unknown>; skeptic_output: Record<string, unknown> };
type ResearchEvent = { sequence: number; timestamp: string; kind: string; role?: string | null; message: string };
type ResearchStep = { id: string; cycle: number; role: string; status: string; started_at: string; finished_at?: string; call_number: number; output?: Record<string, unknown> };
type ResearchSession = { id: string; session_number: number; strategy_id: string; strategy_title: string; status: 'queued' | 'running' | 'paused' | 'completed' | 'stopped' | 'failed'; model: string; reasoning_effort: string; mode: string; calls_used: number; call_limit: number; cycle: number; current_question: string; current_action: string; message: string; artifacts: ResearchArtifact[]; steps: ResearchStep[]; events: ResearchEvent[]; created_at: string; updated_at: string };

function displayStrategyTitle(strategy: Strategy | undefined): string {
  if (!strategy) return 'Strategy';
  if (typeof strategy.title === 'string' && strategy.title.trim()) return strategy.title;
  const firstLine = typeof strategy.approach === 'string' ? strategy.approach.split(/\r?\n/, 1)[0].trim() : '';
  return firstLine ? `${firstLine.slice(0, 72)}${firstLine.length > 72 ? '…' : ''}` : 'Untitled strategy';
}

type ProcessControls = { play: () => void; pause: () => void; playDisabled: boolean; pauseDisabled: boolean; playLabel: string };

function ResearchWorkspace({ path, projectId, strategies, onViewStrategy, onControlsChange }: { path: string; projectId: string; strategies: Strategy[]; onViewStrategy: (id: string) => void; onControlsChange: (controls: ProcessControls) => void }) {
  const eligible = useMemo(() => strategies.filter(strategy => !strategy.removed_at), [strategies]);
  const [sessions, setSessions] = useState<ResearchSession[]>([]);
  const [session, setSession] = useState<ResearchSession | null>(null);
  const selectedSessionId = useRef('');
  const [pendingStrategyId, setPendingStrategyId] = useState('');
  const [config, setConfig] = useState<{ available: boolean; model: string; reasoning_effort: string; mode: string; binding: string; message: string } | null>(null);
  const [confirmStart, setConfirmStart] = useState(false);
  const [confirmStop, setConfirmStop] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [readError, setReadError] = useState('');
  const [announcement, setAnnouncement] = useState('');
  const readErrorReported = useRef(false);
  const lastAnnouncement = useRef('');
  const idempotencyKey = useRef<string | null>(null);
  const activeSession = sessions.find(item => item.status === 'queued' || item.status === 'running' || item.status === 'paused');
  const active = session && (session.status === 'queued' || session.status === 'running');
  const nextStrategyId = eligible[0]?.id ?? '';

  const load = useCallback(async (preferredId?: string, signal?: AbortSignal) => {
    const query = new URLSearchParams({ path });
    const response = await fetch(`/api/projects/research-sessions?${query}`, { signal });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error ?? 'Could not read research sessions');
    const nextSessions = data.sessions as ResearchSession[];
    setSessions(nextSessions);
    readErrorReported.current = false;
    setReadError('');
    const chosen = nextSessions.find(item => item.id === (preferredId ?? selectedSessionId.current))
      ?? nextSessions.find(item => item.status === 'queued' || item.status === 'running' || item.status === 'paused')
      ?? nextSessions[0]
      ?? null;
    selectedSessionId.current = chosen?.id ?? '';
    setSession(chosen);
    if (chosen) {
      const transition = `${chosen.id}:${chosen.status}:${chosen.current_action}`;
      if (chosen.status === 'failed' && lastAnnouncement.current.startsWith(`${chosen.id}:`) && /:(queued|running):/.test(lastAnnouncement.current)) {
        setError(chosen.message);
        reportRequestFailure(chosen.message);
      }
      if (lastAnnouncement.current && transition !== lastAnnouncement.current) {
        setAnnouncement(`Research session ${chosen.session_number}: ${chosen.status}. ${chosen.current_action}.`);
      }
      lastAnnouncement.current = transition;
    }
    return chosen;
  }, [path]);

  const reportReadFailure = useCallback((cause: unknown) => {
    const message = errorMessage(cause);
    setReadError(message);
    if (!readErrorReported.current) reportRequestFailure(message);
    readErrorReported.current = true;
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(undefined, controller.signal).catch(cause => { if (!controller.signal.aborted) reportReadFailure(cause); });
    return () => controller.abort();
  }, [load, reportReadFailure]);

  useEffect(() => {
    if (!activeSession) return;
    const poll = () => {
      if (document.visibilityState === 'visible') void load().catch(reportReadFailure);
    };
    const timer = window.setInterval(poll, 2000);
    document.addEventListener('visibilitychange', poll);
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', poll); };
  }, [activeSession?.id, load, reportReadFailure]);

  async function begin() {
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`);
      const current = await response.json();
      if (!response.ok) throw new Error(current.error ?? 'Could not read AI configuration');
      setConfig(current);
      if (!current.available) throw new Error(current.message ?? 'Connect the selected AI account before investigating');
      setConfirmStart(true);
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  async function start() {
    if (!config || !pendingStrategyId) return;
    setBusy(true); setError('');
    try {
      idempotencyKey.current ??= crypto.randomUUID();
      selectedSessionId.current = '';
      const next = await post<ResearchSession>('research-sessions/start', { path, strategy_id: pendingStrategyId, expected_project_id: projectId, expected_binding: config.binding, idempotency_key: idempotencyKey.current });
      idempotencyKey.current = null;
      setConfirmStart(false); selectedSessionId.current = next.id;
      lastAnnouncement.current = `${next.id}:${next.status}:${next.current_action}`;
      await load(next.id);
    } catch (cause) { await load().catch(() => {}); setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  async function control(action: 'pause' | 'resume' | 'stop', target: ResearchSession | null = session) {
    if (!target) return;
    setBusy(true); setError(''); setConfirmStop(false);
    try { await post<ResearchSession>(`research-sessions/${target.id}/control`, { path, action }); await load(target.id); }
    catch (cause) { await load(target.id).catch(() => {}); setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  const playLabel = activeSession?.status === 'paused' ? 'Resume research session' : 'Start research session';
  const play = useCallback(() => {
    if (busy || readError) return;
    if (activeSession?.status === 'paused') { void control('resume', activeSession); return; }
    if (activeSession || !eligible.length) return;
    setPendingStrategyId(nextStrategyId);
    setConfirmStart(false);
    void begin();
  }, [activeSession, busy, nextStrategyId, eligible.length, readError]);
  const pause = useCallback(() => {
    if (activeSession?.status === 'running' && !busy && !readError) void control('pause', activeSession);
  }, [activeSession, busy, readError]);
  useEffect(() => {
    onControlsChange({
      play, pause,
      playDisabled: busy || !!readError || !eligible.length || confirmStart || (!!activeSession && activeSession.status !== 'paused'),
      pauseDisabled: busy || !!readError || activeSession?.status !== 'running',
      playLabel,
    });
  }, [activeSession, busy, confirmStart, eligible.length, onControlsChange, pause, play, playLabel, readError]);

  const lastActivity = session?.events.at(-1);
  const statusLabel = readError && active ? `State unknown · last confirmed ${session.status}` : session?.status;

  return <section className="research-workspace" aria-labelledby="research-session-heading">
    <header className="research-workspace-header"><div><h2 id="research-session-heading">{session ? `Session #${session.session_number}` : 'Research session'}</h2>
      {session && <p className="research-session-subtitle">{session.strategy_title} · {statusLabel}</p>}</div>
      {sessions.length > 0 && <label className="research-history-control">Session history<select aria-label="Research session history" value={session?.id ?? ''} onChange={event => { selectedSessionId.current = event.target.value; void load(event.target.value); }}>
        {sessions.map(item => <option key={item.id} value={item.id}>#{item.session_number} · {item.strategy_title} · {item.status}</option>)}
      </select></label>}
    </header>

    {activeSession && session?.id !== activeSession.id && <p className="research-active-notice" role="status">Session #{activeSession.session_number} is {activeSession.status} for {activeSession.strategy_title}. <button type="button" className="text-view-link" onClick={() => { selectedSessionId.current = activeSession.id; void load(activeSession.id); }}>View active session</button></p>}

    {!session && !confirmStart && (eligible.length
      ? <p className="research-empty">No research session yet.</p>
      : <p className="research-empty">Create or accept a strategy before starting research. <button type="button" className="text-view-link" onClick={() => onViewStrategy('')}>Show Strategies</button></p>)}
    {confirmStart && config && <div className="research-consent" role="group" aria-label="Confirm research session">
      <p><strong>{displayStrategyTitle(eligible.find(item => item.id === pendingStrategyId))}</strong></p><p>{config.model} · {thinkingLabels[config.reasoning_effort] ?? config.reasoning_effort} thinking · {config.mode === 'api_key' ? 'API key billing' : 'ChatGPT plan allowance'}</p>
      <p>Up to 3 cycles and 6 provider calls. Usage may accrue. Six calls is a request limit, not a cost guarantee. Findings are unverified research notes.</p>
      <p>An already-sent provider request may continue to consume allowance if paused or stopped.</p>
      <div className="research-session-actions"><button type="button" className="primary-action" disabled={busy} onClick={() => void start()}>Confirm and start</button><button type="button" className="text-view-link" disabled={busy} onClick={() => setConfirmStart(false)}>Cancel</button></div>
    </div>}

    {session && <div className="research-session-body">
      <div className="research-session-facts"><p><strong>Model:</strong> {session.model} · {thinkingLabels[session.reasoning_effort] ?? session.reasoning_effort} thinking · {session.mode === 'api_key' ? 'API key billing' : 'ChatGPT plan allowance'}</p>
        <p><strong>Progress:</strong> Cycle {session.cycle} of 3 · {session.calls_used} of {session.call_limit} calls used ({Math.max(0, session.call_limit - session.calls_used)} remaining)</p>
        <p><strong>Current action:</strong> {session.current_action}</p>
        {lastActivity && <p><strong>Last activity:</strong> <time dateTime={lastActivity.timestamp}>{dateLabel(lastActivity.timestamp)}</time></p>}
      </div>
      <p className="research-session-message">{session.message}</p>
      {!!session.current_question && <p><strong>Current question:</strong> {session.current_question}</p>}
      <div className="research-session-actions">
        {(active || session.status === 'paused') && <button type="button" className="text-view-link" disabled={busy} onClick={() => setConfirmStop(true)}>Stop</button>}
        <button type="button" className="text-view-link" onClick={() => onViewStrategy(session.strategy_id)}>View strategy</button>
      </div>
      {confirmStop && <div className="research-stop-confirm" role="group" aria-label="Confirm stop session"><p>Stop session #{session.session_number}? Stopping is terminal and prevents further calls.</p><button type="button" className="text-view-link" disabled={busy} onClick={() => void control('stop')}>Confirm stop</button><button type="button" className="text-view-link" disabled={busy} onClick={() => setConfirmStop(false)}>Keep session</button></div>}
      {session.steps.at(-1) && ['running', 'interrupted', 'failed'].includes(session.steps.at(-1)!.status) && <section className="research-incomplete-step" aria-label="Current or incomplete step"><strong>{session.steps.at(-1)!.status === 'running' ? 'In progress' : 'Incomplete step'} · {session.steps.at(-1)!.role}</strong><p>Cycle {session.steps.at(-1)!.cycle}, call {session.steps.at(-1)!.call_number}. {session.steps.at(-1)!.status === 'running' ? 'No result has been committed yet.' : 'This attempt is not a completed research artifact.'}</p></section>}
      {!!session.events.length && <section className="research-activity" aria-label="Recent session activity"><h3>Recent activity</h3><ol>{session.events.slice(-8).map(event => <li key={event.sequence}><time dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time><span>{event.message}</span></li>)}</ol></section>}
      {!!session.artifacts.length && <section className="research-artifacts" aria-label="Research artifacts"><h3>Research artifacts</h3><ol>{session.artifacts.map(artifact => <li key={artifact.id}><details>
        <summary>Cycle {artifact.sequence} · {artifact.claim_or_question} <span>{artifact.evidence_status}</span></summary>
        <div className="research-artifact-content"><p><strong>Method:</strong> {artifact.method}</p><p><strong>Assumptions:</strong> {artifact.assumptions.join(' · ') || 'None stated'}</p><p><strong>Evidence status:</strong> {artifact.evidence_status}</p><p><strong>Skeptic response:</strong> {artifact.skeptic_response}</p>
          <p><strong>Objections:</strong> {artifact.objections.join(' · ') || 'No concrete objection recorded'}</p><p><strong>Open obligations:</strong> {artifact.open_obligations.join(' · ') || 'None recorded'}</p>
          <p><strong>Coordinator decision:</strong> {artifact.coordinator_decision}</p><p><strong>Next question:</strong> {artifact.next_question || 'No further question; the session ended.'}</p>
          <details><summary>Full validated role outputs</summary><h4>Investigator</h4>{Object.entries(artifact.investigator_output).map(([key, value]) => <p key={key}><strong>{key.replaceAll('_', ' ')}:</strong> {Array.isArray(value) ? value.join(' · ') : String(value)}</p>)}<h4>Skeptic</h4>{Object.entries(artifact.skeptic_output).map(([key, value]) => <p key={key}><strong>{key.replaceAll('_', ' ')}:</strong> {Array.isArray(value) ? value.join(' · ') : String(value)}</p>)}</details>
          <small>{artifact.note}</small>
        </div>
      </details></li>)}</ol></section>}
    </div>}
    {readError && <p className="error" role="alert">Unable to confirm session state. Last confirmed information is shown: {readError}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
  </section>;
}

type TextFormat = 'plain' | 'markdown';
type TextDisplay = 'plain' | 'rendered';
type TextVersion = { body: string; kind: 'authored' | 'ai_derived'; current: boolean; source_digest: string; source_format: TextFormat; created_at: string; provenance: { provider: string; model: string; reasoning_effort: string | null } | null; warnings: string[] };
type TextRepresentations = { source_format: TextFormat; source_digest: string; plain: TextVersion | null; markdown: TextVersion | null };

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

function DownloadProjectDialog({ path, title, onCancel }: { path: string; title: string; onCancel: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const defaultName = `sigma-${(title || 'project').replace(/[^a-z0-9_-]+/gi, '-').replace(/^-|-$/g, '').slice(0, 80) || 'project'}.json`;
  const [filename, setFilename] = useState(defaultName);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { dialog.current?.showModal(); input.current?.focus(); input.current?.select(); }, []);
  function cancel() { if (!submitting.current) onCancel(); }
  async function exportFile(event: FormEvent) {
    event.preventDefault();
    if (submitting.current) return;
    const chosen = filename.trim();
    if (!chosen || chosen === '.' || chosen === '..' || /[\/\\<>:"|?*\x00-\x1f]/.test(chosen)) {
      setError('Enter a valid filename without path separators or reserved characters.');
      return;
    }
    const downloadName = /\.json$/i.test(chosen) ? chosen : `${chosen}.json`;
    submitting.current = true; setBusy(true); setError('');
    try {
      const response = await fetch(`/api/projects/export?${new URLSearchParams({ path })}`, { cache: 'no-store' });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.error ?? detail?.detail ?? 'Project export failed');
      }
      const result = await response.json() as { export_version: number; project: { title: string }; agentic_runs: unknown[] };
      if (result.export_version !== 1 || !result.project || !Array.isArray(result.agentic_runs)) throw new Error('Invalid project export response');
      const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2) + '\n'], { type: 'application/json' }));
      try {
        const link = document.createElement('a');
        link.href = url; link.download = downloadName;
        document.body.appendChild(link); link.click(); link.remove();
      } finally { URL.revokeObjectURL(url); }
      onCancel();
    } catch (cause) { setError(errorMessage(cause)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className="project-settings-dialog export-project-dialog" aria-labelledby="export-project-heading"
    onCancel={event => { event.preventDefault(); cancel(); }}>
    <form onSubmit={exportFile}>
      <header className="settings-header">
        <h2 id="export-project-heading">Export</h2>
        <div className="settings-actions">
          <button type="submit" className="export-download-icon" aria-label={busy ? 'Downloading project' : 'Download project'} disabled={busy || !filename.trim()}>
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </button>
          <button type="button" className="settings-cancel" disabled={busy} onClick={cancel}>Cancel</button>
        </div>
      </header>
      <div className="settings-body">
        <label className="sr-only" htmlFor="export-project-filename">Proposed filename</label>
        <input ref={input} id="export-project-filename" value={filename} maxLength={180} required disabled={busy} spellCheck={false}
          onChange={event => { setFilename(event.target.value); setError(''); }}/>
        {error && <p className="error" role="alert">{error}</p>}
      </div>
    </form>
  </dialog>;
}

function TooltipWrap({ children }: { children: React.ReactNode }) {
  const [dismissed, setDismissed] = useState(false);
  return <span className={`sigma-render-tooltip-wrap${dismissed ? ' tooltip-dismissed' : ''}`}
    onClickCapture={() => setDismissed(true)}
    onMouseLeave={() => setDismissed(false)}
    onBlur={event => { if (!event.currentTarget.matches(':hover')) setDismissed(false); }}>
    {children}
  </span>;
}

function TextViews({ path, scope, strategyId, source, projectTitle, contentClass, onSaved, mathematical, onSettings, settingsDisabled, settingsButtonRef, hideProjectHeading }: {
  path: string; scope: 'project' | 'strategy'; strategyId?: string; source: string; projectTitle?: string;
  contentClass: string; onSaved: (view: ProjectView) => void; mathematical: boolean; onSettings?: () => void; settingsDisabled?: boolean; settingsButtonRef?: React.RefObject<HTMLButtonElement | null>; hideProjectHeading?: boolean;
}) {
  const [data, setData] = useState<TextRepresentations | null>(null);
  const preferenceKey = `sigma.markdownView:${path}:${scope}:${strategyId ?? ''}`;
  const [storedSelected, setSelected] = useState<TextDisplay>(() => window.localStorage.getItem(preferenceKey) === 'rendered' ? 'rendered' : 'plain');
  const selected: TextDisplay = mathematical ? storedSelected : 'plain';
  const [rendering, setRendering] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editingFromRendered, setEditingFromRendered] = useState(false);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const exportTrigger = useRef<HTMLButtonElement>(null);
  const [error, setError] = useState('');
  const abort = useRef<AbortController | null>(null);
  const bodyTrigger = useRef<HTMLElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError(''); setEditing(false);
    const query = new URLSearchParams({ path, scope, ...(strategyId ? { strategy_id: strategyId } : {}) });
    fetch(`/api/projects/text?${query}`, { signal: controller.signal }).then(async response => {
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
      const settingsResponse = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal });
      const settings = await settingsResponse.json();
      if (!settingsResponse.ok || !settings.available) { if (settingsResponse.ok) reportRequestFailure(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.'); throw new Error(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.'); }
      const response = await fetch('/api/projects/text/convert', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
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
      const next = await post<ProjectView>('text/source', { path, scope, strategy_id: strategyId, body: draft, format, expected_digest: data.source_digest });
      setEditing(false); onSaved(next);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  const name = scope === 'project' ? 'research problem' : 'strategy approach';
  const renderTooltip = rendering ? 'Converting to markdown' : selected === 'rendered' ? 'Show plain text' : 'Convert to markdown';
  const renderTooltipId = `sigma-render-tooltip-${scope}-${strategyId ?? 'project'}`;
  function closeExport() {
    setExportOpen(false);
    requestAnimationFrame(() => exportTrigger.current?.focus());
  }
  const viewActions = <>
    {mathematical && <TooltipWrap>
      <button type="button" className={`sigma-render-toggle${selected === 'rendered' || rendering ? ' sigma-render-active' : ''}${rendering ? ' sigma-render-pending' : ''}`}
      aria-label={selected === 'rendered' ? `Show plain ${name}` : `Render ${name} as Markdown`}
      aria-pressed={selected === 'rendered' || rendering} aria-describedby={renderTooltipId}
      disabled={editing || busy} onClick={() => {
        if (selected === 'rendered') { chooseView('plain'); setError(''); }
        else if (data?.markdown?.current) { chooseView('rendered'); setError(''); }
        else { void convert('markdown'); }
      }}><span aria-hidden="true">{rendering ? "⌛" : "Σ"}</span></button>
      <span id={renderTooltipId} className="sigma-render-tooltip" role="tooltip">{renderTooltip}</span>
    </TooltipWrap>}

    {editing ? <>
      <button type="submit" form={`text-form-${scope}-${strategyId ?? 'project'}`} className="text-view-link" disabled={busy || !draft.trim()}>Save</button>
      <button type="button" className="text-view-link" disabled={busy} onClick={cancelBodyEdit}>Cancel</button>
    </> : data && version && <TooltipWrap><button type="button" className="text-view-link text-view-icon" aria-label={`Edit ${name}`} aria-describedby={`edit-tooltip-${scope}-${strategyId ?? 'project'}`} onClick={() => beginBodyEdit(selected === 'rendered')}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg></button><span id={`edit-tooltip-${scope}-${strategyId ?? 'project'}`} className="sigma-render-tooltip" role="tooltip">{`Edit ${name}`}</span></TooltipWrap>}

    {scope === 'project' && !editing && <TooltipWrap><button ref={exportTrigger} type="button" className="copper-button project-download-trigger" aria-label="Download project" aria-describedby="download-project-tooltip" onClick={() => setExportOpen(true)}><svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg></button><span id="download-project-tooltip" className="sigma-render-tooltip" role="tooltip">Download project</span></TooltipWrap>}    {onSettings && !editing && <TooltipWrap><button ref={settingsButtonRef} type="button" className="text-view-link text-view-icon" aria-label="Project settings" aria-describedby="project-settings-tooltip" disabled={settingsDisabled} onClick={onSettings}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M10 2h4l.6 2.3 1.4.8 2.3-.7 2.8 2.8-.7 2.3.8 1.4L23 11v4l-2.3.6-.8-1.4.7 2.3-2.8 2.8-2.3-.7-1.4.8L14 24h-4l-.6-2.3-1.4-.8-2.3.7-2.8-2.8.7-2.3-.8-1.4L1 15v-4l2.3-.6.8-1.4-.7-2.3 2.8-2.8 2.3.7 1.4-.8L10 2Z" transform="translate(0 -1) scale(1 .95)"/><circle cx="12" cy="12" r="3"/></svg></button><span id="project-settings-tooltip" className="sigma-render-tooltip" role="tooltip">Project settings</span></TooltipWrap>}
  </>;
  return <div className={`text-views${scope === 'project' ? ' project-text-views' : ''}${mathematical ? ' math-text-views' : ''}`}>
    {scope === 'project' && exportOpen && <DownloadProjectDialog path={path} title={projectTitle ?? 'project'} onCancel={closeExport}/>}
    <div className="text-view-controls">
      {scope === 'project' && !hideProjectHeading && <h2 className="investigation-heading">Project</h2>}
      {scope === 'project' ? <div className="project-text-actions">{viewActions}</div> : viewActions}
    </div>
    {editing ? <form id={`text-form-${scope}-${strategyId ?? 'project'}`} className="text-view-editor" onSubmit={save}>
      <textarea id={`text-editor-${scope}-${strategyId ?? 'project'}`} autoFocus value={draft} maxLength={scope === 'project' ? 20000 : 10000} rows={8} required disabled={busy} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); cancelBodyEdit(); } }}/>
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

function ProjectPaneTitle({ view, onSaved, expanded, onToggle, disabled, headingRef }: { view: ProjectView; onSaved: (view: ProjectView) => void; expanded: boolean; onToggle: () => void; disabled: boolean; headingRef?: Ref<HTMLHeadingElement> }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(view.project.title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { if (!editing) setDraft(view.project.title); }, [view.project.title, editing]);
  useEffect(() => { if (editing) { input.current?.focus(); input.current?.select(); } }, [editing]);
  function cancel() { setDraft(view.project.title); setError(''); setEditing(false); requestAnimationFrame(() => trigger.current?.focus()); }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!draft.trim()) { setError('Enter a project title.'); input.current?.focus(); return; }
    setBusy(true); setError('');
    try {
      const current = settingsOf(view);
      const next = await post<ProjectView>('update', { path: view.path, ...current, title: draft, expected: current });
      setEditing(false); onSaved(next); requestAnimationFrame(() => trigger.current?.focus());
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <>
    <div className="project-pane-title-line">
      <h1 id="project-pane-heading" ref={headingRef} tabIndex={-1} className="current-project">
        <button type="button" className="project-pane-disclosure" aria-expanded={expanded} aria-controls="project-pane-content" onClick={onToggle}><span>Project: {view.project.title}</span><svg className={`project-pane-chevron${expanded ? ' is-expanded' : ''}`} viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4 19 12 7 20Z"/></svg></button>
      </h1>
      <button ref={trigger} type="button" className="text-view-link text-view-icon project-title-pencil" aria-label={`Edit project title: ${view.project.title}`} title="Edit project title" disabled={disabled || editing} onClick={() => setEditing(true)}>
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg>
      </button>
    </div>
    {editing && <form className="project-title-edit-form" onSubmit={save}>
      <label className="sr-only" htmlFor="project-pane-title-input">Project title</label>
      <input ref={input} id="project-pane-title-input" aria-label="Project title" value={draft} maxLength={200} required disabled={busy} onChange={event => { setDraft(event.target.value); setError(''); }} onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); cancel(); } }}/>
      <button type="submit" className="text-view-link" disabled={busy}>Save</button><button type="button" className="text-view-link" disabled={busy} onClick={cancel}>Cancel</button>
      {error && <p role="alert" className="project-title-error">{error}</p>}
    </form>}
  </>;
}

function Header({ goHome, close, projectArtwork = false }: { goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; projectArtwork?: boolean }) {
  return <header className={projectArtwork ? 'site-header project-art-header' : 'site-header'}>
    <div className="brand-block">
      <a href="/" className={projectArtwork ? 'brand project-header-art' : 'brand'} onClick={goHome} aria-label="SIGMA home"><img src={projectArtwork ? '/sigma-project-header.png' : '/sigma-workspace-logo.png'} alt="SIGMA" /></a>
      {projectArtwork ? close && <div className="project-title-line"><button className="project-back" type="button" onClick={close.action} disabled={close.busy} aria-label="Close project" title="Back to projects"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m14 5-7 7 7 7M7 12h13"/></svg></button></div>
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

function WorkspaceFrame({ children, goHome, close }: {
  children: React.ReactNode; goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean };
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
    }}>Skip to project content</a>
    <Header goHome={goHome} close={close} projectArtwork/>
    <div className={`workspace-layout${collapsed ? ' nav-collapsed' : ''}`}>
      <nav className="workspace-nav" aria-label="Project navigation">
        <button className="nav-collapse" type="button" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={toggleSidebar}><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={collapsed ? 'm9 6 6 6-6 6' : 'm15 6-6 6 6 6'}/></svg></button>
        <a href="#project-pane-heading" aria-label="Project" title={collapsed ? 'Project' : undefined} onClick={event => { event.preventDefault(); focusWorkspace('project-pane-heading'); }}><WorkspaceIcon name="Settings"/><span>Project</span></a>
        <a href="#research-session-heading" aria-label="Research session" title={collapsed ? 'Research session' : undefined} onClick={event => { event.preventDefault(); focusWorkspace('research-session-heading'); }}><WorkspaceIcon name="Analysis"/><span>Research session</span></a>
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

function ProjectEntryDialog({ initialPath, onOpen, onCancel }: {
  initialPath: string; onOpen: (view: ProjectView) => void; onCancel: () => void;
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
    try { onOpen(await post<ProjectView>('open', { path })); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className="project-entry-dialog" aria-labelledby="project-entry-heading" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <h2 id="project-entry-heading">Open Project</h2><p className="entry-help">Choose an existing local project by its directory path.</p>
    <form onSubmit={save}><fieldset disabled={busy}><label htmlFor="open-project-path">Project directory</label><input ref={first} id="open-project-path" required value={path} onChange={event => setPath(event.target.value)} aria-describedby="project-path-help"/><p id="project-path-help" className="entry-hint">Try <code>projects/rh.sigma</code>, or an absolute path such as <code>/Users/you/projects/question.sigma</code>. Paths refer to this local server.</p>
    {error && <p className="error" role="alert">{error}</p>}<div className="entry-dialog-actions"><button type="submit">{busy ? 'Opening…' : 'Open Project'}</button><button type="button" className="entry-cancel" onClick={onCancel}>Cancel</button></div></fieldset></form>
  </dialog>;
}

type Settings = { title: string; problem: string; investigation_type: ResearchMode; ai_model: string; reasoning_effort: string };
type CatalogChoice = { id: string; label: string; description: string; efforts: string[]; availability: 'available' | 'unavailable' | 'unverified' };
const thinkingLabels: Record<string, string> = { low: 'Low', medium: 'Medium', high: 'High', xhigh: 'Extra high' };
const settingsOf = (view: ProjectView): Settings => ({ title: view.project.title, problem: view.project.problem, investigation_type: view.project.investigation_type, ai_model: view.project.ai_model, reasoning_effort: view.project.reasoning_effort });

function ProjectSettingsDialog({ initial, onSaved, onCancel }: { initial?: ProjectView; onSaved: (view: ProjectView) => void; onCancel: () => void }) {
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
        const response = await fetch(`/api/projects/destination?${new URLSearchParams({ title: values.title })}`, { signal: controller.signal });
        const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Project location unavailable');
        setDestination(data);
      } catch (error) { if (!controller.signal.aborted) setLocationError(errorMessage(error)); }
      finally { if (!controller.signal.aborted) setPreviewBusy(false); }
    }, values.title ? 180 : 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [values.title]);
  function change(key: keyof Settings, value: string) { setValues(previous => ({ ...previous, [key]: value })); }
  const selected = catalog.find(model => model.id === values.ai_model);
  const samePair = !!initial && values.ai_model === initial.project.ai_model && values.reasoning_effort === initial.project.reasoning_effort;
  const compatible = selected?.efforts.includes(values.reasoning_effort) || samePair;
  const pairError = selected && !selected.efforts.includes(values.reasoning_effort) && !samePair ? 'This model does not support the selected Thinking level. Choose a supported level explicitly.' : '';
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current || !compatible || (!initial && (!destination?.path || destination.exists || previewBusy))) return;
    submitting.current = true; setBusy(true); setError('');
    try { onSaved(await post<ProjectView>(initial ? 'update' : 'create', initial ? { path: initial.path, ...values, expected: settingsOf(initial) } : values)); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className={`project-settings-dialog ${initial ? 'edit-project-dialog' : 'new-project-dialog'}`} aria-labelledby="project-settings-heading" aria-describedby="project-settings-help" onCancel={event => { event.preventDefault(); if (!submitting.current) onCancel(); }}>
    <form onSubmit={save}>
      <header className="settings-header"><h2 id="project-settings-heading">{initial ? 'Settings' : 'New Project'}</h2>
        <div className="settings-actions"><button type="submit" disabled={busy || !values.ai_model || !compatible || !!pairError || (!initial && (!values.problem.trim() || previewBusy || !destination?.path || destination.exists))}>{busy ? 'Saving…' : initial ? 'Save' : 'Create'}</button><button className="settings-cancel" type="button" disabled={busy} onClick={() => { if (!submitting.current) onCancel(); }}>Cancel</button></div>
      </header>
      <div className="settings-body"><p id="project-settings-help">{initial ? 'Choose how to explore this project. Edit its title and description directly on the project page.' : 'Name a project and choose how to explore it.'}</p>
      <fieldset disabled={busy}>
      {!initial && <><label htmlFor="project-name">Project name</label><input ref={first} id="project-name" required maxLength={200} value={values.title} onChange={event => change('title', event.target.value)}/>
      <label htmlFor="project-problem">Research problem</label><textarea id="project-problem" required maxLength={20000} rows={4} value={values.problem} onChange={event => change('problem', event.target.value)}/></>}
      <label htmlFor="project-mode">Research mode</label><select id="project-mode" value={values.investigation_type} onChange={event => change('investigation_type', event.target.value)}><option value="default">Default</option><option value="mathematical">Mathematical</option></select>
      <label htmlFor="project-model">LLM Model</label><select id="project-model" required value={values.ai_model} onChange={event => change('ai_model', event.target.value)} aria-describedby="project-model-help">
        {!values.ai_model && <option value="" disabled>Loading reviewed choices…</option>}
        {values.ai_model && !selected && <option value={values.ai_model}>{values.ai_model} · unavailable/unreviewed</option>}
        {catalog.map(model => <option key={model.id} value={model.id}>{model.label}{model.availability === 'available' ? '' : model.availability === 'unavailable' ? ' · unavailable' : ' · access unverified'}</option>)}
      </select>
      <p id="project-model-help" className="settings-hint">{ai.info?.mode === 'api_key' ? 'OpenAI API · billed separately. ' : 'ChatGPT plan allowance or credits · connection required for generation. '}{selected?.description} {catalogMessage}{selected?.availability === 'unavailable' ? ' Your selected model is unavailable; it will not be replaced automatically.' : ''}</p>
      <label htmlFor="project-thinking">Thinking level</label><select id="project-thinking" value={values.reasoning_effort} onChange={event => change('reasoning_effort', event.target.value)}>
        {!selected?.efforts.includes(values.reasoning_effort) && <option value={values.reasoning_effort}>{thinkingLabels[values.reasoning_effort] ?? values.reasoning_effort} · {selected ? 'unsupported' : 'preserved'}</option>}
        {(selected?.efforts ?? []).map(effort => <option key={effort} value={effort}>{thinkingLabels[effort] ?? effort}</option>)}
      </select>
      <p className="settings-hint">Applies to future AI proposals. Higher thinking can take longer and consume more usage. API cost tiers are relative; <a href="https://developers.openai.com/api/docs/pricing" target="_blank" rel="noreferrer">current token prices</a>. Earlier strategy provenance stays unchanged.</p>
      {pairError && <p className="error" role="alert">{pairError}</p>}
      <p className="project-destination"><span>Project location</span><code>{initial ? initial.path : previewBusy ? 'Checking location…' : destination?.path ?? destination?.root ?? 'Location unavailable'}</code><small>{initial ? 'Editing the display name never renames or moves this directory.' : 'The project name determines its directory; existing files are never overwritten.'}</small></p>
      {locationError && <p className="error" role="alert">{locationError}</p>}
      {destination?.exists && <p className="error" role="alert">That name is already used by another project, or the location is occupied. Choose another name.</p>}
      {error && <p className="error" role="alert">{error}</p>}
    </fieldset></div></form>
  </dialog>;
}

type RecentProject = { id: string; path: string; title: string; investigation_type: string | null; strategy_count: number | null; available: boolean; error: string | null };
type SampleProject = { id: string; title: string; problem: string; investigation_type: string; strategy_count: number };
const strategyCount = (count: number) => `${count} ${count === 1 ? 'strategy' : 'strategies'}`;
function RecentProjects({ onOpen }: { onOpen: (view: ProjectView) => void }) {
  const [projects, setProjects] = useState<RecentProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [opening, setOpening] = useState('');
  const [error, setError] = useState('');
  const pending = useRef(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch('/api/projects/recent', { signal });
    const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Recent Projects unavailable. Open Project still works.');
    setProjects(data.projects); setLoading(false);
  }, []);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal).catch(error => { if (!controller.signal.aborted) { setError(errorMessage(error)); setLoading(false); } }); return () => controller.abort(); }, [load]);
  async function open(entry: RecentProject) {
    if (pending.current) return; pending.current = true; setOpening(entry.id); setError('');
    try { onOpen(await post<ProjectView>('open', { path: entry.path })); }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setOpening(''); }
  }
  async function forget(entry: RecentProject) {
    if (pending.current) return; pending.current = true; setOpening(entry.id); setError('');
    try { await post('recent/forget', { project_id: entry.id }); await load(); }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setOpening(''); }
  }
  return <div className="empty home-empty home-recents">
    {loading ? <p role="status">Loading recent projects…</p> : !projects.length && <p>No recent projects yet. Open a project or begin a new project.</p>}
    <ul>{projects.map(entry => <li key={entry.id}>
      <div className="recent-entry">
        <div className="recent-title-row">
          <button className="recent-open" disabled={!entry.available || !!opening} onClick={() => void open(entry)}><strong>{entry.title}</strong></button>
          <button className="recent-forget" disabled={!!opening} aria-label={`Remove ${entry.title} from Recent Projects`} title="Remove from Recent Projects; keep all research" onClick={() => void forget(entry)}>Remove</button>
        </div>
        <small>{entry.investigation_type === 'mathematical' ? 'Mathematical' : entry.investigation_type === 'default' ? 'Default' : 'Unavailable'}{entry.strategy_count === null ? '' : ` · ${strategyCount(entry.strategy_count)}`}</small>
        <span title={entry.path}>{entry.path}</span>
      </div>
      {entry.error && <p className="recent-unavailable">{entry.error}</p>}
    </li>)}</ul>
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function SampleProjects({ onOpen }: { onOpen: (view: ProjectView) => void }) {
  const [projects, setProjects] = useState<SampleProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [opening, setOpening] = useState('');
  const pending = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    void fetch('/api/projects/samples', { signal: controller.signal }).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? 'Samples unavailable.');
      setProjects(data.projects); setLoading(false);
    }).catch(error => { if (!controller.signal.aborted) { setError(errorMessage(error)); setLoading(false); } });
    return () => controller.abort();
  }, []);
  async function open(sample: SampleProject) {
    if (pending.current) return; pending.current = true; setOpening(sample.id); setError('');
    try {
      const copy = await post<ProjectView>('samples/open', { sample_id: sample.id });
      // A Sample opens as a saved working copy, which now belongs in Recent.
      window.localStorage.setItem('sigma.homeCatalogTab', 'recent');
      onOpen(copy);
    }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setOpening(''); }
  }
  return <div className="empty home-empty home-samples">
    {loading ? <p role="status">Loading sample projects…</p> : !projects.length && !error && <p>No sample projects are available.</p>}
    <ul>{projects.map(sample => <li key={sample.id}><button className="sample-open" disabled={!!opening} onClick={() => void open(sample)} aria-label={`Open ${sample.title}`}><strong>{sample.title}</strong><small>{sample.investigation_type === 'mathematical' ? 'Mathematical' : 'Default'} · {strategyCount(sample.strategy_count)}</small></button></li>)}</ul>
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function HomeCatalog({ onOpen }: { onOpen: (view: ProjectView) => void }) {
  const [tab, setTab] = useState<'recent' | 'samples'>(() =>
    window.localStorage.getItem('sigma.homeCatalogTab') === 'recent' ? 'recent' : 'samples');
  useEffect(() => { window.localStorage.setItem('sigma.homeCatalogTab', tab); }, [tab]);
  const recent = useRef<HTMLButtonElement>(null);
  const samples = useRef<HTMLButtonElement>(null);
  function switchTab(next: 'recent' | 'samples') { setTab(next); (next === 'recent' ? recent : samples).current?.focus(); }
  return <div className="home-catalog"><div className="catalog-tabs" role="tablist" aria-label="Project lists" onKeyDown={event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); switchTab(tab === 'samples' ? 'recent' : 'samples'); }
    if (event.key === 'Home') { event.preventDefault(); switchTab('samples'); }
    if (event.key === 'End') { event.preventDefault(); switchTab('recent'); }
  }}>
    <button ref={samples} id="samples-tab" role="tab" aria-controls="samples-panel" aria-selected={tab === 'samples'} tabIndex={tab === 'samples' ? 0 : -1} onClick={() => setTab('samples')}>Samples</button>
    <button ref={recent} id="recent-tab" role="tab" aria-controls="recent-panel" aria-selected={tab === 'recent'} tabIndex={tab === 'recent' ? 0 : -1} onClick={() => setTab('recent')}>Recent</button>
  </div>
    <div id="recent-panel" role="tabpanel" aria-labelledby="recent-tab" hidden={tab !== 'recent'}><RecentProjects onOpen={onOpen}/></div>
    <div id="samples-panel" role="tabpanel" aria-labelledby="samples-tab" hidden={tab !== 'samples'}><SampleProjects onOpen={onOpen}/></div>
  </div>;
}

function Home({ initialPath, onOpen }: {
  initialPath: string; onOpen: (view: ProjectView) => void;
}) {
  const [entry, setEntry] = useState<'open' | 'new' | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const openButton = useRef<HTMLButtonElement>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  const shell = useRef<HTMLDivElement>(null);
  useEffect(() => { document.title = 'SIGMA · Research workspace'; heading.current?.focus(); }, []);
  useEffect(() => {
    // CSS background-size: cover scales the source image by the larger of
    // viewport-width/image-width and viewport-height/image-height. Apply
    // that exact same factor to the beam overlay, anchored at image top/center.
    const background = new Image();
    const updateScale = () => {
      if (!background.naturalWidth || !background.naturalHeight) return;
      const scale = Math.max(
        window.innerWidth / background.naturalWidth,
        window.innerHeight / background.naturalHeight,
      );
      shell.current?.style.setProperty('--home-art-scale', String(scale));
    };
    background.addEventListener('load', updateScale);
    window.addEventListener('resize', updateScale);
    background.src = '/sigma-home-background-copper.png';
    if (background.complete) updateScale();
    return () => {
      background.removeEventListener('load', updateScale);
      window.removeEventListener('resize', updateScale);
    };
  }, []);
  function cancel() {
    const trigger = entry === 'open' ? openButton : newButton;
    setEntry(null); requestAnimationFrame(() => trigger.current?.focus());
  }
  return <div ref={shell} className="home-shell">
    <div className="home-atmosphere" aria-hidden="true"/>
    <div className="home-content">
      <div className="home-topline"><ConnectionStatus/></div>
      <section className="home-projects" aria-labelledby="home-projects-heading">
        <div className="home-projects-heading">
          <h1 id="home-projects-heading" ref={heading} tabIndex={-1}>Projects</h1>
          <button type="button" ref={newButton} className="home-project-action" onClick={() => setEntry('new')}>New</button>
          <button type="button" ref={openButton} className="home-project-action" onClick={() => setEntry('open')}>Open</button>
        </div>
        <HomeCatalog onOpen={onOpen}/>
      </section>
      <img className="home-slogan" src="/sigma-slogan-copper-approved.png" alt="Strategy · Investigation · Generation · Measurement · Assessment"/>
      {entry === 'open' && <ProjectEntryDialog initialPath={initialPath} onOpen={onOpen} onCancel={cancel}/>}
      {entry === 'new' && <ProjectSettingsDialog onSaved={onOpen} onCancel={cancel}/>}
    </div>
  </div>;
}

function StrategyTitleEditor({ strategy, path, onSaved }: {
  strategy: Strategy; path: string; onSaved: (view: ProjectView) => void;
}) {
  const [editing, setEditing] = useState(false);
  const shownTitle = displayStrategyTitle(strategy);
  const [draft, setDraft] = useState(shownTitle);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (!editing) setDraft(shownTitle); }, [shownTitle, editing]);
  useEffect(() => { if (editing) { input.current?.focus(); input.current?.select(); } }, [editing]);
  function cancel() {
    setEditing(false); setDraft(shownTitle); setError('');
    requestAnimationFrame(() => trigger.current?.focus());
  }
  async function save(event: FormEvent) {
    event.preventDefault(); event.stopPropagation();
    if (busy) return;
    if (!draft.trim()) { setError('Enter a strategy title.'); input.current?.focus(); return; }
    setBusy(true); setError('');
    try {
      const next = await post<ProjectView>('strategies/edit', {
        path, strategy_id: strategy.id, title: draft, approach: strategy.approach,
      });
      setEditing(false); onSaved(next);
      requestAnimationFrame(() => trigger.current?.focus());
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <div className={`strategy-title-editor${editing ? ' is-renaming' : ''}`}>
    {editing ? <form onSubmit={save} className="strategy-rename-form">
      <label className="sr-only" htmlFor={`strategy-title-${strategy.id}`}>Strategy title</label>
      <input ref={input} id={`strategy-title-${strategy.id}`} aria-label="Strategy title" value={draft} maxLength={200} disabled={busy}
        required onChange={event => { setDraft(event.target.value); setError(''); }} onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); cancel(); } }}/>
      <button type="submit" className="text-view-link" disabled={busy}>Save</button>
      <button type="button" className="text-view-link" disabled={busy} onClick={cancel}>Cancel</button>
    </form> : <h3>
      <button type="button" ref={trigger} className="text-view-link text-view-icon strategy-title-pencil" aria-label={`Edit strategy title: ${shownTitle}`}
        onClick={() => setEditing(true)}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg></button>
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

function NewStrategy({ path, onSaved, onCancel, initialDraft }: {
  path: string; initialDraft?: { title: string; approach: string; summary?: string }; onSaved: (view: ProjectView) => void; onCancel: () => void;
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
    try { onSaved(await post<ProjectView>('strategies', { path, title, approach, summary: initialDraft?.summary ?? '' })); }
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

function StrategyCreationActions({ buttonRef, disabled, onManual, onAI, processControls }: {
  buttonRef: React.RefObject<HTMLButtonElement | null>; disabled: boolean; onManual: () => void; onAI: () => void; processControls: ProcessControls;
}) {
  return <div className="strategy-heading-actions">
    <button type="button" className="text-view-link" ref={buttonRef} disabled={disabled} onClick={onManual}>New</button>
    <button type="button" className="text-view-link" disabled={disabled} onClick={onAI}>Generate</button>
    <span className="strategy-process-controls" aria-label="Research process controls">
      <button type="button" className="text-view-link text-view-icon process-control" aria-label={processControls.playLabel} title={processControls.playLabel} disabled={processControls.playDisabled || disabled} onClick={processControls.play}>
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6 3.8v12.4L16 10 6 3.8Z"/></svg>
      </button>
      <button type="button" className="text-view-link text-view-icon process-control" aria-label="Pause research session" title="Pause research session" disabled={processControls.pauseDisabled || disabled} onClick={processControls.pause}>
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5.5 4h3.2v12H5.5zM11.3 4h3.2v12h-3.2z"/></svg>
      </button>
    </span>
  </div>;
}

type ProposalResult = { draft: { title: string; summary: string; approach: string; first_tests: string; assumptions: string; failure_modes: string }; provenance: { provider: string; model: string; reasoning_effort?: string | null }; receipt: string };
type AgenticEvent = { type: string; sequence: number; run_id: string; kind?: 'explore' | 'challenge' | 'revise' | null; attempt?: number | null; summary?: string | null; outcome?: 'revise' | 'retry' | 'present' | 'stop' | null; max_calls?: number | null; draft?: ProposalResult['draft'] | null; provenance?: ProposalResult['provenance'] | null; receipt?: string | null; assessment?: 'distinct' | 'overlapping' | 'unconvincing' | null; objections?: string[] | null; missing_obligations?: string | null; mechanism_comparison?: string | null };
const activityLabels = { explore: 'Exploring a candidate', challenge: 'Independent challenge', revise: 'Targeted revision' } as const;
async function readAgenticStream(response: Response, onEvent: (event: AgenticEvent) => void): Promise<AgenticEvent> {
  if (!response.ok) { let detail = `HTTP ${response.status}`; try { const body = await response.json(); detail = body.error ?? body.detail ?? detail; } catch {} throw new Error(String(detail)); }
  if (!response.body) throw new Error('The server returned no progress stream. Nothing was saved.');
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let sequence = 0; let runId = ''; let terminal: AgenticEvent | null = null;
  const consume = (chunk: string) => {
    buffer += chunk; const records = buffer.split(/\r?\n\r?\n/); buffer = records.pop() ?? '';
    for (const record of records) {
      const data = record.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
      if (!data) continue;
      let event: AgenticEvent; try { event = JSON.parse(data) as AgenticEvent; } catch { throw new Error('The server sent malformed progress data. You can retry; nothing was saved.'); }
      if (!['run.started', 'activity.started', 'activity.completed', 'decision', 'run.completed', 'run.stopped', 'run.failed'].includes(event?.type)) throw new Error('The server sent an unknown progress event. You can retry; nothing was saved.');
      if (!event || typeof event.type !== 'string' || !Number.isInteger(event.sequence) || event.sequence !== sequence + 1 || typeof event.run_id !== 'string' || !/^[0-9a-f]{32}$/.test(event.run_id)) throw new Error('The progress stream was incomplete or out of order. You can retry; nothing was saved.');
      if (runId && event.run_id !== runId) throw new Error('The progress stream changed run identity. You can retry; nothing was saved.');
      if (terminal) throw new Error('The server sent progress after its terminal event. You can retry; nothing was saved.');
      sequence = event.sequence; runId = event.run_id;
      const activityKind = event.kind === 'explore' || event.kind === 'challenge' || event.kind === 'revise';
      if (event.type === 'run.started' && event.max_calls !== 6) throw new Error('The server sent an invalid run limit. You can retry; nothing was saved.');
      if (event.type.startsWith('activity.') && (!activityKind || !Number.isInteger(event.attempt) || (event.attempt ?? 0) < 1 || (event.attempt ?? 0) > 2)) throw new Error('The server sent an invalid activity event. You can retry; nothing was saved.');
      if (event.type === 'activity.completed' && typeof event.summary !== 'string') throw new Error('The server sent an incomplete activity result. You can retry; nothing was saved.');
      if (event.type === 'activity.completed' && event.kind === 'challenge' && (!event.assessment || !Array.isArray(event.objections) || typeof event.missing_obligations !== 'string' || typeof event.mechanism_comparison !== 'string')) throw new Error('The server sent an incomplete reviewer summary. You can retry; nothing was saved.');
      if (event.type === 'decision' && (!['revise', 'retry', 'present', 'stop'].includes(event.outcome ?? '') || typeof event.summary !== 'string')) throw new Error('The server sent an invalid coordinator decision. You can retry; nothing was saved.');
      if (['run.stopped', 'run.failed'].includes(event.type) && typeof event.summary !== 'string') throw new Error('The server sent an incomplete terminal result. You can retry; nothing was saved.');
      if (event.type === 'run.completed') {
        const fields = ['title', 'summary', 'approach', 'first_tests', 'assumptions', 'failure_modes'];
        if (!event.draft || typeof event.receipt !== 'string' || !event.receipt || !event.provenance || typeof event.provenance.provider !== 'string' || typeof event.provenance.model !== 'string' || fields.some(key => typeof event.draft?.[key as keyof ProposalResult['draft']] !== 'string')) throw new Error('The completed stream did not include a complete draft and receipt. You can retry; nothing was saved.');
      }
      if (['run.completed', 'run.stopped', 'run.failed'].includes(event.type)) terminal = event;
      onEvent(event);
    }
  };
  try { while (true) { const { done, value } = await reader.read(); if (done) break; consume(decoder.decode(value, { stream: true })); } consume(decoder.decode()); }
  catch (error) { await reader.cancel().catch(() => {}); throw error; }
  if (buffer.trim()) consume('\n\n');
  if (!terminal) throw new Error('The progress stream ended without a final result. You can retry; nothing was saved.');
  return terminal;
}
function GenerateStrategy({ path, projectId, onSaved, onCancel, onNew }: {
  path: string; projectId: string; onSaved: (view: ProjectView) => void; onCancel: () => void; onNew: () => void;
}) {
  const composer = useRef<HTMLDivElement>(null);
  const request = useRef<AbortController | null>(null);
  const submitting = useRef(false);
  const [config, setConfig] = useState<{ available: boolean; provider: string; mode: string; binding: string; project_id: string; model: string; reasoning_effort: string; message: string } | null>(null);
  const [seed, setSeed] = useState('');
  const ai = useAI();
  const lifetime = useRef(new AbortController());
  const [result, setResult] = useState<ProposalResult | null>(null);
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [approach, setApproach] = useState('');
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [activities, setActivities] = useState<string[]>([]);
  const [currentActivity, setCurrentActivity] = useState('');
  const [review, setReview] = useState<AgenticEvent | null>(null);
  useEffect(() => {
    composer.current?.querySelector('textarea')?.focus();
    const controller = new AbortController();
    fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal }).then(async response => { if (!response.ok) throw new Error('Could not read AI configuration'); return response.json(); }).then(setConfig).catch(error => { if (!controller.signal.aborted) setError(errorMessage(error)); });
    return () => { controller.abort(); lifetime.current.abort(); request.current?.abort(); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal }).then(response => response.json()).then(setConfig).catch(() => {});
    return () => controller.abort();
  }, [ai.info?.mode, ai.info?.active_account, ai.info?.status]);
  const needsConnection = ai.info?.mode !== 'api_key' && ['disconnected', 'reauth_required', 'unauthorized', 'plan_not_permitted'].includes(ai.info?.status ?? 'disconnected');
  async function cancel() {
    if (saving || cancelling) return;
    if (busy) {
      setCancelling(true);
      if (ai.connecting) ai.cancelSignIn();
      request.current?.abort();
      return;
    }
    lifetime.current.abort(); onCancel();
  }
  async function generate() {
    if (submitting.current) return; submitting.current = true;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError(''); setActivities([]); setCurrentActivity('Preparing run'); setReview(null);
    try {
      if (needsConnection) {
        const connected = await ai.signIn({ accountId: ai.info?.active_account, enablePlan: ai.info?.status === 'plan_not_permitted', signal: lifetime.current.signal });
        if (!connected || lifetime.current.signal.aborted) return;
      }
      const response = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal });
      if (!response.ok) throw new Error('Could not read current AI settings. Retry explicitly.');
      const latest = await response.json(); setConfig(latest);
      if (latest.project_id !== projectId) throw new Error('Project identity changed during sign-in. Reopen it before generating; your text is retained.');
      if (!latest.available) throw new Error(latest.message);
      if (lifetime.current.signal.aborted) return;
      const stream = await fetch('/api/projects/proposals/agentic', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path, seed, expected_binding: latest.binding, expected_project_id: projectId }), signal: controller.signal });
      const terminal = await readAgenticStream(stream, event => {
        if (event.type === 'activity.started' && event.kind) setCurrentActivity(`${activityLabels[event.kind]}${event.attempt ? ` · attempt ${event.attempt}` : ''}`);
        if (event.type === 'activity.completed' && event.kind) {
          setActivities(previous => [...previous, `${activityLabels[event.kind!]}${event.attempt ? ` · attempt ${event.attempt}` : ''}: ${event.summary ?? 'completed'}`]);
          if (event.kind === 'challenge') setReview(event);
          setCurrentActivity('');
        }
        if (event.type === 'decision') { setActivities(previous => [...previous, `Decision · ${event.outcome}: ${event.summary}`]); setCurrentActivity(''); }
        if (event.type === 'run.started') setCurrentActivity('Starting bounded run · up to 6 model calls');
      });
      if (terminal.type === 'run.completed' && terminal.draft && terminal.receipt && terminal.provenance) {
        const next: ProposalResult = { draft: terminal.draft, receipt: terminal.receipt, provenance: terminal.provenance };
        setResult(next); setTitle(next.draft.title); setSummary(next.draft.summary); setApproach(next.draft.approach); setCurrentActivity('Ready for your review');
        requestAnimationFrame(() => document.getElementById('proposal-title')?.focus());
      } else if (terminal.type === 'run.stopped') { setCurrentActivity('Run stopped'); setError(`${terminal.summary ?? 'No viable candidate was found.'} Nothing was saved. You can retry with different guidance.`); }
      else { setCurrentActivity('Run failed'); throw new Error(terminal.summary ?? 'The run failed. No strategy was saved.'); }
    } catch (error) {
      if (controller.signal.aborted) { setCurrentActivity('Run cancelled'); setError('Run cancelled. Nothing was saved. If generation had started, its evidence will be retained in project export. You can retry.'); }
      else { const message = errorMessage(error); setCurrentActivity('Run could not be completed'); setError(message); reportRequestFailure(message); }
    }
    finally { if (request.current === controller) {
      request.current = null;
      submitting.current = false; setBusy(false); setCancelling(false);
    } }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current || !result) return; submitting.current = true; setSaving(true); setError('');
    try { onSaved(await post<ProjectView>('strategies', { path, title, approach, summary, receipt: result.receipt })); }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setSaving(false); }
  }
  return <div ref={composer} className="strategy-form proposal-dialog inline-proposal" role="region" aria-labelledby="proposal-heading" aria-describedby="proposal-help" onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); cancel(); } }}>
    <div className="proposal-heading-row"><h2 id="proposal-heading">Generate a strategy</h2><button type="button" className="text-view-link proposal-heading-new" disabled={busy || saving || cancelling} onClick={onNew}>New</button><button type="button" className="text-view-link proposal-heading-generate" disabled={(!config?.available && !needsConnection) || busy || saving || ai.connecting} onClick={() => void generate()}>{busy ? cancelling ? 'Cancelling…' : ai.connecting ? 'Connecting…' : 'Generating…' : result ? 'Regenerate' : 'Generate'}</button>{result && <button type="submit" form="proposal-save-form" className="text-view-link proposal-heading-save" disabled={busy || saving}>{saving ? 'Accepting…' : 'Accept'}</button>}<button type="button" className="text-view-link proposal-heading-cancel" disabled={saving || cancelling} onClick={() => void cancel()}>{busy ? cancelling ? 'Cancelling…' : "Cancel request" : "Cancel"}</button></div>
    {!busy && <p id="proposal-help" className="hint">Explore and independently challenge a candidate, then review the editable, unsaved draft before accepting.</p>}
    <p className="provider-context">{config ? `${config.mode === 'api_key' ? 'OpenAI API · billed separately' : 'Using ChatGPT plan'} · ${config.model} · ${thinkingLabels[config.reasoning_effort] ?? config.reasoning_effort}` : 'Reading AI settings…'} · maximum 6 calls / 2 candidates{config?.mode === 'chatgpt' && <ManageUsage/>}</p>
    {config && !config.available && <p role="status" className="hint">{config.message}</p>}
    <details className="proposal-context" open={!result}><summary>Generation context &amp; starting point (optional)</summary>
    <label htmlFor="proposal-seed" className="sr-only">Starting point (optional)</label>
    <textarea id="proposal-seed" rows={3} maxLength={4000} value={seed} disabled={busy || saving} onChange={event => setSeed(event.target.value)} aria-describedby="seed-help"/>
    <p id="seed-help" className="hint">An optional idea or proposed mechanism, not an assumption to accept uncritically. Leave empty for an independent solution.</p>
    <p className="hint">Generation sends this problem, mode, all strategy titles/approaches (including removed ones), and the starting point to OpenAI. Cancelling disconnects the active run; provider usage may already count toward the selected plan or billing mode.</p>
    </details>
    {(busy || activities.length > 0 || currentActivity) && <section className="agentic-activity" aria-label="Generation progress" aria-live="polite">
      {busy && <span className="agentic-filament" aria-hidden="true"/>}
      {currentActivity && <p className="agentic-current">{currentActivity}</p>}
      {activities.length > 0 && <ol>{activities.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ol>}
    </section>}
    {review && <section className="agentic-review" aria-label="Independent review"><strong>Independent review · {review.assessment}</strong><p>{review.summary}</p><p>{review.mechanism_comparison}</p><ul>{review.objections?.map((objection, index) => <li key={index}>{objection}</li>)}</ul><p><strong>Still to establish:</strong> {review.missing_obligations}</p></section>}
    <p className="sr-only" role="status" aria-live="polite">{busy ? currentActivity || 'Generating strategy…' : ''}</p>
    <PlanWelcome/>
    {ai.connecting && <button type="button" onClick={ai.cancelSignIn}>Cancel sign-in</button>}
    {ai.handoff && <a href={ai.handoff} target="_blank" rel="noreferrer">Open sign-in browser</a>}
    {ai.error && <p role="alert" className="error">{ai.error}</p>}
    {error && <p role="alert" className="error">{error}</p>}
    <form id="proposal-save-form" onSubmit={save}>
      {result && <fieldset disabled={busy || saving} className="proposal-review">
        <legend>Unsaved draft · Review before accepting</legend>
        <label htmlFor="proposal-title">Title</label><input id="proposal-title" required maxLength={200} value={title} onChange={event => setTitle(event.target.value)}/>
        <label htmlFor="proposal-summary">Description</label><input id="proposal-summary" required maxLength={300} value={summary} onChange={event => setSummary(event.target.value)}/>
        <label htmlFor="proposal-approach">Plan</label><textarea id="proposal-approach" required maxLength={10000} rows={9} value={approach} onChange={event => setApproach(event.target.value)}/>
        <p className="hint">AI-assisted suggestion · {result.provenance.provider} / {result.provenance.model}{result.provenance.reasoning_effort ? ` · ${thinkingLabels[result.provenance.reasoning_effort] ?? result.provenance.reasoning_effort} thinking` : ''}. Accepting saves your edits and records your acceptance; reviewer obligations remain open as shown above.</p>
      </fieldset>}
    </form>
  </div>;
}

function ProjectScreen({ path, initialView, onClose, goHome }: {
  path: string; initialView?: ProjectView; onClose: () => void;
  goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const [view, setView] = useState<ProjectView | null>(initialView ?? null);
  const [error, setError] = useState('');
  const [closing, setClosing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [manualDraft, setManualDraft] = useState<{ title: string; approach: string; summary?: string }>();
  const [projectEditing, setProjectEditing] = useState(false);
  const editProjectButton = useRef<HTMLButtonElement>(null);
  const [ordering, setOrdering] = useState(false);
  const [previewOrder, setPreviewOrder] = useState<string[] | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const drag = useRef<{ id: string; order: string[]; pointer: number | null } | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const [command, setCommand] = useState<{ mode: 'remove' | 'stage'; strategy: Strategy } | null>(null);
  const [focusStrategy, setFocusStrategy] = useState('');
  const [projectExpanded, setProjectExpanded] = useState(() => window.localStorage.getItem(`sigma.projectPane:${path}`) !== 'false');
  const [strategiesExpanded, setStrategiesExpanded] = useState(() => window.localStorage.getItem(`sigma.strategiesPane:${path}`) !== 'false');
  const [processControls, setProcessControls] = useState<ProcessControls>({ play: () => {}, pause: () => {}, playDisabled: true, pauseDisabled: true, playLabel: 'Start research session' });
  const heading = useRef<HTMLHeadingElement>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  const introPane = useRef<HTMLDivElement>(null);
  const resizeStart = useRef<{ pointer: number; y: number; height: number } | null>(null);
  const [introHeight, setIntroHeight] = useState<number | null>(null);
  useEffect(() => {
    setIntroHeight(null);
    const frame = requestAnimationFrame(() => { if (introPane.current) setIntroHeight(Math.round(introPane.current.getBoundingClientRect().height)); });
    return () => cancelAnimationFrame(frame);
  }, [view?.project.id, view?.project.title, view?.project.problem]);
  useEffect(() => {
    if (initialView) return;
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
  }, [view?.project.id, view?.project.title, !!error]);
  useEffect(() => {
    if (!focusStrategy || !strategiesExpanded) return;
    const target = document.getElementById(`strategy-${focusStrategy}`);
    const details = target?.closest<HTMLDetailsElement>('details.strategy-detail');
    if (details) details.open = true;
    requestAnimationFrame(() => target?.focus());
  }, [focusStrategy, strategiesExpanded]);
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
  const frame = { goHome, close: { action: close, busy: closing } };
  function toggleProjectPane() {
    setProjectExpanded(open => { window.localStorage.setItem(`sigma.projectPane:${path}`, String(!open)); return !open; });
  }
  function toggleStrategiesPane() {
    setStrategiesExpanded(open => { window.localStorage.setItem(`sigma.strategiesPane:${path}`, String(!open)); return !open; });
  }
  function showStrategy(id: string) {
    if (!strategiesExpanded) {
      setStrategiesExpanded(true);
      window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'true');
    }
    if (id) setFocusStrategy(id);
  }
  function cancel() { setEditing(false); requestAnimationFrame(() => newButton.current?.focus()); }
  if (!view) return <WorkspaceFrame {...frame}><div className="workspace-state" aria-live="polite">{error ? <>
    <h1 ref={heading} tabIndex={-1}>Project unavailable</h1><p role="alert" className="error">{error}</p>
    <p>Close this project to choose another directory.</p>
  </> : <p className="intro">Opening project…</p>}</div></WorkspaceFrame>;
  const project = view.project;
  const introMaximum = Math.max(160, Math.min(Math.round(window.innerHeight * .75), 800));
  const clampIntro = (height: number) => Math.max(120, Math.min(introMaximum, Math.round(height)));
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
    <section className="workspace-pane project-pane" aria-labelledby="project-pane-heading">
      <header className="workspace-pane-heading project-pane-heading"><ProjectPaneTitle view={view} onSaved={setView} expanded={projectExpanded} onToggle={toggleProjectPane} disabled={closing || ordering || !!dragId} headingRef={heading}/></header>
      <div id="project-pane-content" hidden={!projectExpanded}>
        <div className="project-intro" id="project-intro-pane" ref={introPane} style={introHeight === null ? undefined : { height: introHeight, maxHeight: 'min(75dvh, 800px)' }}>
          <TextViews mathematical={project.investigation_type === 'mathematical'} path={view.path} scope="project" source={project.problem} projectTitle={project.title} contentClass="objective" onSaved={setView} onSettings={() => setProjectEditing(true)} settingsDisabled={closing || ordering || !!dragId || editing || generating} settingsButtonRef={editProjectButton} hideProjectHeading/>
        </div>
        <div className="project-pane-resizer" role="separator" tabIndex={0} aria-label="Resize project description" aria-controls="project-intro-pane" aria-orientation="horizontal" aria-valuemin={120} aria-valuemax={introMaximum} aria-valuenow={introHeight ?? undefined} title="Drag or use arrow keys to resize the project description"
      onPointerDown={event => { if (event.button !== 0) return; const height = introPane.current?.getBoundingClientRect().height ?? 120; resizeStart.current = { pointer: event.pointerId, y: event.clientY, height }; event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault(); }}
      onPointerMove={event => { const start = resizeStart.current; if (start?.pointer === event.pointerId) setIntroHeight(clampIntro(start.height + event.clientY - start.y)); }}
      onPointerUp={event => { if (resizeStart.current?.pointer === event.pointerId) resizeStart.current = null; }}
      onPointerCancel={event => { if (resizeStart.current?.pointer === event.pointerId) resizeStart.current = null; }}
      onKeyDown={event => { const current = introPane.current?.getBoundingClientRect().height ?? 120; if (event.key === 'ArrowUp' || event.key === 'ArrowDown') { event.preventDefault(); setIntroHeight(clampIntro(current + (event.key === 'ArrowDown' ? 24 : -24))); } else if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); setIntroHeight(event.key === 'Home' ? 120 : introMaximum); } }}><span aria-hidden="true"/></div>
      </div>
    </section>
    {error && <p role="alert" className="error">{error}</p>}
    <ResearchWorkspace path={view.path} projectId={project.id} strategies={strategies} onViewStrategy={showStrategy} onControlsChange={setProcessControls}/>
    <section className="pool workspace-pane strategies-pane" aria-labelledby="pool-heading">
      <header className="pool-heading workspace-pane-heading strategies-pane-heading">
        <h2 id="pool-heading" tabIndex={-1}><button type="button" aria-expanded={strategiesExpanded} aria-controls="strategies-pane-content" onClick={toggleStrategiesPane}>Strategies</button></h2>
        <p>{strategies.length} strateg{strategies.length === 1 ? 'y' : 'ies'}</p>
        <StrategyCreationActions buttonRef={newButton} disabled={editing || generating || projectEditing || closing || ordering || !!dragId} onManual={() => { setManualDraft(undefined); setEditing(true); }} onAI={() => setGenerating(true)} processControls={processControls}/>
      </header>
      <div id="strategies-pane-content" hidden={!strategiesExpanded}>
      <p className="sr-only" role="status">{announcement}</p>
      <div id="strategy-composer">{editing && <NewStrategy initialDraft={manualDraft} path={view.path} onCancel={cancel} onSaved={next => {
        const strategy = next.project.strategies[next.project.strategies.length - 1];
        setView(next); setEditing(false); setAnnouncement(`Strategy saved: ${strategy.title}`);
        setFocusStrategy(strategy.id);
      }}/>}
      {generating && <GenerateStrategy path={view.path} projectId={view.project.id} onNew={() => { setGenerating(false); setManualDraft(undefined); setEditing(true); }} onCancel={() => { setGenerating(false); requestAnimationFrame(() => newButton.current?.focus()); }} onSaved={next => {
        const strategy = next.project.strategies.at(-1)!; setView(next); setGenerating(false); setFocusStrategy(strategy.id); setAnnouncement('AI-assisted strategy accepted and saved.');
      }}/>}</div>
      {strategies.length ? <div className="strategies-table">
        <div className="strategy-columns" aria-hidden="true"><span>Strategy</span><span>Stage</span></div>
        <ol className="strategy-list" aria-label="Strategies" aria-busy={ordering}>
        {strategies.map(strategy => <li className={`strategy-row${dragId === strategy.id ? ' is-lifted' : ''}`} key={strategy.id} data-strategy-id={strategy.id}>
          <div className="strategy-row-main">
            <details className="strategy-detail">
              <summary id={`strategy-${strategy.id}`} title="Expand or collapse this strategy"><span>Strategy: {displayStrategyTitle(strategy)}</span><svg className="strategy-expand-arrow" viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M7 4 L19 12 L7 20 Z"/></svg></summary>
              <div className="strategy-expanded"><TextViews mathematical={project.investigation_type === 'mathematical'} path={view.path} scope="strategy" strategyId={strategy.id} source={strategy.approach} contentClass="strategy-approach" onSaved={setView}/></div>
            </details>
            <StrategyTitleEditor strategy={strategy} path={view.path} onSaved={setView}/>
          </div>
          <span className={`stage-label stage-${strategy.stage}`} title="Manually tracked; no strategy runner"><i aria-hidden="true"/>{stageLabels[strategy.stage]}</span>
          <StrategyCommands strategy={strategy} onCommand={(mode, strategy) => { if (ordering || dragId || editing || generating || projectEditing) return; if (mode === 'fork') { setManualDraft({ title: `${strategy.title} (forked)`, approach: strategy.approach, summary: strategy.summary }); setEditing(true); requestAnimationFrame(() => document.getElementById('strategy-composer')?.scrollIntoView({ block: 'nearest' })); } else setCommand({ mode, strategy }); }}/>
          <button id={`grip-${strategy.id}`} className="drag-grip" disabled={ordering || closing}
            aria-label={`Reorder ${strategy.title}`} aria-describedby="reorder-help" aria-pressed={dragId === strategy.id}
            onPointerDown={event => { if (event.button !== 0) return; event.preventDefault(); event.currentTarget.focus(); pickup(strategy.id, event.pointerId); event.currentTarget.setPointerCapture(event.pointerId); }}
            onKeyDown={event => { if (event.key === 'Escape' && drag.current) { event.preventDefault(); cancelDrag(); }
              else if (event.key === ' ' && !drag.current) { event.preventDefault(); pickup(strategy.id, null); }
              else if (drag.current?.id === strategy.id && ['ArrowUp', 'ArrowDown', 'Enter', ' '].includes(event.key)) { event.preventDefault();
                if (event.key === 'ArrowUp' || event.key === 'ArrowDown') moveTo(drag.current.order.indexOf(strategy.id) + (event.key === 'ArrowUp' ? -1 : 1)); else void drop();
              } }}><svg width="12" height="16" viewBox="0 0 12 16" fill="currentColor" aria-hidden="true">{[3,7,11].flatMap(y => [3,7].map(x => <circle key={`${x}-${y}`} cx={x} cy={y} r="1"/>))}</svg></button>
        </li>)}
      </ol></div> : !editing && <p className="pool-empty">No strategies yet.</p>}
      {(dragId || ordering) && <p className="reorder-feedback">{ordering ? 'Saving order…' : 'Moving strategy · Release or press Enter to save · Escape cancels'}</p>}
      <p id="reorder-help" className="sr-only">Drag only the corner grip to reorder. Keyboard: Space picks up, arrows move, Enter drops, Escape cancels. Changes save on drop.</p>
      </div>
    </section>
    {projectEditing && <ProjectSettingsDialog initial={view} onCancel={() => { setProjectEditing(false); requestAnimationFrame(() => editProjectButton.current?.focus()); }} onSaved={next => { setView(next); setProjectEditing(false); setAnnouncement('Project settings saved.'); requestAnimationFrame(() => editProjectButton.current?.focus()); }}/>}
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
      <dl><dt>Identity</dt><dd>{project.id}</dd><dt>Directory</dt><dd>{view.path}</dd><dt>Format version</dt><dd>{project.schema_version}</dd><dt>Research mode</dt><dd>{project.investigation_type === 'mathematical' ? 'Mathematical' : 'Default'}</dd><dt>AI model</dt><dd>{project.ai_model}</dd><dt>Thinking level</dt><dd>{thinkingLabels[project.reasoning_effort] ?? project.reasoning_effort}</dd></dl>
      <h3>Event history</h3>
      <ol className="event-list">{project.events.map(event => <li key={event.sequence}>
        <span className="sequence">{String(event.sequence).padStart(2, '0')}</span>
        <div><span>{event.kind}</span><time dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time>
          {event.project_change && <details className="edit-history"><summary>View project changes</summary><dl>{(Object.keys(event.project_change.current) as (keyof Settings)[]).filter(key => event.project_change!.previous[key] !== event.project_change!.current[key]).map(key => <div key={key}><dt>{({ title: 'Project name', problem: 'Research problem', investigation_type: 'Research mode', ai_model: 'AI model', reasoning_effort: 'Thinking level' })[key]}</dt><dd>Before: {event.project_change!.previous[key]}<br/>After: {event.project_change!.current[key]}</dd></div>)}</dl></details>}
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
  const [openedView, setOpenedView] = useState<ProjectView | null>(null);
  const [location, setLocation] = useState(() => window.location.pathname + window.location.search);
  const [lastPath, setLastPath] = useState(() =>
    new URLSearchParams(window.location.search).get('path') || 'projects/rh.sigma');
  useEffect(() => {
    const pop = () => { setOpenedView(null); setLocation(window.location.pathname + window.location.search); };
    window.addEventListener('popstate', pop);
    return () => window.removeEventListener('popstate', pop);
  }, []);
  const navigate = useCallback((url: string) => {
    window.history.pushState(null, '', url); setLocation(url); window.scrollTo(0, 0);
  }, []);
  const closeProject = useCallback(() => {
    setOpenedView(null);
    const path = new URLSearchParams(window.location.search).get('path');
    if (path) { setLastPath(path); window.localStorage.setItem('sigma.currentProject', path); }
    navigate('/');
  }, [navigate]);
  function goHome(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      event.preventDefault(); setOpenedView(null); navigate('/');
    }
  }
  const url = new URL(location, window.location.origin);
  return <main className={url.pathname === '/' ? 'home-page' : 'workspace-page'}>
    {url.pathname === '/' ? <Home initialPath={lastPath} onOpen={view => {
      setOpenedView(view); setLastPath(view.path); window.localStorage.setItem('sigma.currentProject', view.path); navigate(projectUrl(view.path));
    }}/> : url.pathname === '/project' ? <ProjectScreen key={location}
      initialView={openedView?.path === url.searchParams.get('path') ? openedView : undefined} path={url.searchParams.get('path') ?? ''} onClose={closeProject} goHome={goHome}/>
      : <><Header goHome={goHome}/><h1>Page not found</h1><a href="/" onClick={goHome}>Return Home</a></>}
  </main>;
}

installRequestErrorToasts();
createRoot(document.getElementById('root')!).render(<AIProvider><App/><RequestErrorToasts/></AIProvider>);
