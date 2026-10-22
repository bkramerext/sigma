import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent, type Ref, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import './workspace.css';
import './project-entry.css';
import './strategies.css';
import './project-settings.css';
import './recents.css';
import './copper-controls.css';
import './text-views.css';
import { AIProvider, ConnectionStatus, ManageUsage, PlanWelcome, beginProviderRequest, watchResearchProviderActivity, useAI } from './ai-connection';
import { installRequestErrorToasts, reportRequestFailure, RequestErrorToasts } from './request-toast';
const RenderedMarkdown = lazy(() => import('./RenderedMarkdown'));

// Prospective navigation rail; keep implementation available for later activation.
const ENABLE_WORKSPACE_SIDEBAR = false;

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
type ResearchOutcome = { assessment: 'pending' | 'positive' | 'mixed' | 'negative'; label: string; summary: string; caveats: string[]; basis_artifact_ids: string[]; provisional: boolean };
type ResearchSession = { id: string; session_number: number; strategy_id: string; strategy_title: string; status: 'queued' | 'running' | 'paused' | 'completed' | 'ended' | 'stopped' | 'failed'; model: string; reasoning_effort: string; mode: string; calls_used: number; call_limit: number; cycle: number; cycle_limit?: number; current_question: string; current_action: string; message: string; artifacts: ResearchArtifact[]; steps: ResearchStep[]; events: ResearchEvent[]; created_at: string; updated_at: string; started_at?: string; elapsed_seconds?: number; output_token_limit?: number; estimated_cost_usd?: number | null; cost_status?: string; outcome: ResearchOutcome };
type ResearchLimits = { research_rounds: number; model_calls: number; session_duration_minutes: number; output_tokens_per_call: number; maximum_estimated_cost_usd: number | null };
type ResearchLimitsDraft = { research_rounds: string; model_calls: string; session_duration_minutes: string; output_tokens_per_call: string; maximum_estimated_cost_usd: string };
const limitBounds = {
  research_rounds: [1, 10], model_calls: [2, 20], session_duration_minutes: [1, 120], output_tokens_per_call: [256, 16384],
} as const;
function draftLimits(value: ResearchLimits): ResearchLimitsDraft {
  return { research_rounds: String(value.research_rounds), model_calls: String(value.model_calls), session_duration_minutes: String(value.session_duration_minutes), output_tokens_per_call: String(value.output_tokens_per_call), maximum_estimated_cost_usd: value.maximum_estimated_cost_usd === null ? '' : String(value.maximum_estimated_cost_usd) };
}
function validateLimitDraft(draft: ResearchLimitsDraft): { value: ResearchLimits | null; errors: Partial<Record<keyof ResearchLimitsDraft, string>> } {
  const errors: Partial<Record<keyof ResearchLimitsDraft, string>> = {};
  const value = {} as ResearchLimits;
  for (const key of Object.keys(limitBounds) as Array<keyof typeof limitBounds>) {
    const input = draft[key];
    const [minimum, maximum] = limitBounds[key];
    if (!/^\d+$/.test(input)) { errors[key] = 'Enter a whole number.'; continue; }
    const number = Number(input);
    if (!Number.isSafeInteger(number) || number < minimum || number > maximum) {
      errors[key] = `Enter a whole number from ${minimum} to ${maximum}.`; continue;
    }
    value[key] = number;
  }
  if (draft.maximum_estimated_cost_usd === '') value.maximum_estimated_cost_usd = null;
  else if (!/^(?:\d+(?:\.\d{1,2})?|\.\d{1,2})$/.test(draft.maximum_estimated_cost_usd)) {
    errors.maximum_estimated_cost_usd = 'Enter a USD amount from $0.01 to $100.00, or leave blank for unlimited.';
  } else {
    const cost = Number(draft.maximum_estimated_cost_usd);
    if (!Number.isFinite(cost) || cost < 0.01 || cost > 100) errors.maximum_estimated_cost_usd = 'Enter a USD amount from $0.01 to $100.00, or leave blank for unlimited.';
    else value.maximum_estimated_cost_usd = Math.round(cost * 100) / 100;
  }
  if (!errors.research_rounds && !errors.model_calls && value.model_calls < 2 * value.research_rounds) {
    errors.model_calls = 'Allow at least two model calls per round so each round can include Investigator and Skeptic.';
  }
  return { value: Object.keys(errors).length ? null : value, errors };
}

function displayStrategyTitle(strategy: Strategy | undefined): string {
  if (!strategy) return 'Strategy';
  if (typeof strategy.title === 'string' && strategy.title.trim()) return strategy.title;
  const firstLine = typeof strategy.approach === 'string' ? strategy.approach.split(/\r?\n/, 1)[0].trim() : '';
  return firstLine ? `${firstLine.slice(0, 72)}${firstLine.length > 72 ? '…' : ''}` : 'Untitled strategy';
}

type ProcessControls = { play: () => void; pause: () => void; playDisabled: boolean; pauseDisabled: boolean; playLabel: string; confirming?: boolean; start?: () => void; cancel?: () => void; nextSessionNumber?: number };

function DisclosureChevron({ expanded }: { expanded: boolean }) {
  return <svg aria-hidden="true" className={`disclosure-chevron${expanded ? ' is-expanded' : ''}`} viewBox="0 0 12 12"><path d="m4 2 4 4-4 4"/></svg>;
}

function ResearchSessionContents({ session, expanded, busy, onViewStrategy }: {
  session: ResearchSession; expanded: boolean; busy: boolean;
  onViewStrategy: (id: string) => void;
}) {
  const [activityExpanded, setActivityExpanded] = useState(session.status === 'queued' || session.status === 'running');
  useEffect(() => {
    setActivityExpanded(session.status === 'queued' || session.status === 'running');
  }, [session.status]);
  const active = session.status === 'queued' || session.status === 'running';
  const lastActivity = session.events.at(-1);
  const lastStep = session.steps.at(-1);
  return <div id={`session-content-${session.id}`} className="session-row-content" hidden={!expanded}>
    <section className={`session-outcome outcome-${session.outcome.assessment}`} aria-label="Research outcome">
      <p><strong>Outcome:</strong> <span>{session.outcome.label}{session.outcome.provisional ? ' · provisional' : ''}</span></p>
      <p>{session.outcome.summary}</p>
      {!!session.outcome.caveats.length && <ul>{session.outcome.caveats.map((caveat, index) => <li key={index}>{caveat}</li>)}</ul>}
    </section>
    <div className="session-status-row"><span className={`session-status session-${session.status}`}><i aria-hidden="true"/>{session.status}</span></div>
    <div className="research-session-facts"><p><strong>Model:</strong> {session.model} · {thinkingLabels[session.reasoning_effort] ?? session.reasoning_effort} thinking · {session.mode === 'api_key' ? 'API key billing' : 'ChatGPT plan allowance'}</p>
      <p><strong>Progress:</strong> Cycle {session.cycle} of {session.cycle_limit ?? 3} · {session.calls_used} of {session.call_limit} calls used ({Math.max(0, session.call_limit - session.calls_used)} remaining)</p>
      <p><strong>Elapsed:</strong> {formatDuration(session.elapsed_seconds ?? 0)} · <strong>Output limit:</strong> {session.output_token_limit ?? 4000} tokens per call</p>
      {session.mode === 'api_key' && <p><strong>Estimated API spend:</strong> {session.cost_status === 'available' && typeof session.estimated_cost_usd === 'number' ? `$${session.estimated_cost_usd.toFixed(6)} (estimate)` : 'Unavailable; cost limit cannot be verified'}</p>}
      <p><strong>Current action:</strong> {session.current_action}</p>
      {lastActivity && <p><strong>Last activity:</strong> <time dateTime={lastActivity.timestamp}>{dateLabel(lastActivity.timestamp)}</time></p>}
    </div>
    <p className="research-session-message">{session.message}</p>
    {!!session.current_question && <p><strong>Current focus:</strong> {session.current_question}</p>}
    <div className="research-session-actions">
      <a className="text-view-link" href={`#strategy-${session.strategy_id}`} onClick={event => { event.preventDefault(); onViewStrategy(session.strategy_id); }}>Go to strategy: {session.strategy_title}</a>
    </div>
    {lastStep && ['running', 'interrupted', 'failed'].includes(lastStep.status) && <section className="research-incomplete-step" aria-label="Current or incomplete step"><strong>{lastStep.status === 'running' ? 'In progress' : 'Incomplete step'} · {lastStep.role}</strong><p>Cycle {lastStep.cycle}, call {lastStep.call_number}. {lastStep.status === 'running' ? 'No result has been committed yet.' : lastStep.status === 'interrupted' ? 'This attempt is not a completed research artifact. The provider may have completed it or charged usage; SIGMA will not repeat it automatically because completion is ambiguous.' : 'This attempt failed and is not a completed research artifact.'}</p></section>}
    {!!session.artifacts.length && <section className="research-artifacts" aria-label="Research artifacts"><h3>Research artifacts</h3><ol>{session.artifacts.map(artifact => <li key={artifact.id}><details>
      <summary>Cycle {artifact.sequence} · {artifact.claim_or_question} <span>{artifact.evidence_status}</span></summary>
      <div className="research-artifact-content"><p><strong>Method:</strong> {artifact.method}</p><p><strong>Assumptions:</strong> {artifact.assumptions.join(' · ') || 'None stated'}</p><p><strong>Evidence status:</strong> {artifact.evidence_status}</p><p><strong>Skeptic response:</strong> {artifact.skeptic_response}</p>
        <p><strong>Objections:</strong> {artifact.objections.join(' · ') || 'No concrete objection recorded'}</p><p><strong>Open obligations:</strong> {artifact.open_obligations.join(' · ') || 'None recorded'}</p>
        <p><strong>Coordinator decision:</strong> {artifact.coordinator_decision}</p><p><strong>Next question:</strong> {artifact.next_question || 'No further question; the session ended.'}</p>
        <details><summary>Full validated role outputs</summary><h4>Investigator</h4>{Object.entries(artifact.investigator_output).map(([key, value]) => <p key={key}><strong>{key.replaceAll('_', ' ')}:</strong> {Array.isArray(value) ? value.join(' · ') : String(value)}</p>)}<h4>Skeptic</h4>{Object.entries(artifact.skeptic_output).map(([key, value]) => <p key={key}><strong>{key.replaceAll('_', ' ')}:</strong> {Array.isArray(value) ? value.join(' · ') : String(value)}</p>)}</details>
        <small>{artifact.note}</small>
      </div>
    </details></li>)}</ol></section>}
    {!!session.events.length && <section className="research-activity" aria-label="Recent session activity">
      <h3><button type="button" aria-expanded={activityExpanded} aria-controls={`session-activity-${session.id}`} onClick={() => setActivityExpanded(value => !value)}><DisclosureChevron expanded={activityExpanded}/>Recent activity</button></h3>
      <ol id={`session-activity-${session.id}`} hidden={!activityExpanded}>{session.events.slice(-8).map(event => <li key={event.sequence}><time dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time><span>{event.message}</span></li>)}</ol>
    </section>}
  </div>;
}

function ResearchWorkspace({ path, projectId, strategies, onViewStrategy, onControlsChange }: { path: string; projectId: string; strategies: Strategy[]; onViewStrategy: (id: string) => void; onControlsChange: (controls: ProcessControls) => void }) {
  const eligible = useMemo(() => strategies.filter(strategy => !strategy.removed_at), [strategies]);
  const [sessions, setSessions] = useState<ResearchSession[]>([]);
  const selectedSessionId = useRef('');
  const sessionsLoaded = useRef(false);
  const [pendingStrategyId, setPendingStrategyId] = useState('');
  const [config, setConfig] = useState<{ available: boolean; model: string; reasoning_effort: string; mode: string; binding: string; message: string } | null>(null);
  const [limits, setLimits] = useState<ResearchLimits | null>(null);
  const [confirmStart, setConfirmStart] = useState(false);
  const [confirmRemoveId, setConfirmRemoveId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [readError, setReadError] = useState('');
  const [announcement, setAnnouncement] = useState('');
  const [expanded, setExpanded] = useState(() => window.localStorage.getItem(`sigma.sessionsPane:${path}`) !== 'false');
  const [expandedSessionIds, setExpandedSessionIds] = useState<Set<string>>(() => new Set());
  const readErrorReported = useRef(false);
  const lastAnnouncement = useRef('');
  const idempotencyKey = useRef<string | null>(null);
  const activeSession = sessions.find(item => item.status === 'queued' || item.status === 'running' || item.status === 'paused');
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
    const requestedId = preferredId ?? selectedSessionId.current;
    const firstLoad = !sessionsLoaded.current;
    const chosen = (requestedId ? nextSessions.find(item => item.id === requestedId) : null)
      ?? (!sessionsLoaded.current && !selectedSessionId.current
        ? nextSessions.find(item => item.status === 'queued' || item.status === 'running' || item.status === 'paused') ?? nextSessions[0] ?? null
        : null);
    sessionsLoaded.current = true;
    selectedSessionId.current = chosen?.id ?? '';
    if (firstLoad && chosen) setExpandedSessionIds(current => current.size ? current : new Set([chosen.id]));
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
    const stopWatching = watchResearchProviderActivity(path, projectId);
    const poll = () => {
      if (document.visibilityState === 'visible') void load().catch(reportReadFailure);
    };
    const timer = window.setInterval(poll, 2000);
    document.addEventListener('visibilitychange', poll);
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', poll); stopWatching(); };
  }, [activeSession?.id, activeSession?.status, load, path, projectId, reportReadFailure]);

  async function begin() {
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`);
      const current = await response.json();
      if (!response.ok) throw new Error(current.error ?? 'Could not read AI configuration');
      const limitResponse = await fetch(`/api/projects/research-limits?${new URLSearchParams({ path })}`);
      const currentLimits = await limitResponse.json();
      if (!limitResponse.ok) throw new Error(currentLimits.error ?? 'Could not read research limits');
      if (!validateLimitDraft(draftLimits(currentLimits)).value) {
        throw new Error('Saved research limits need attention. Update them in Project Settings → Limits before starting a session.');
      }
      setConfig(current); setLimits(currentLimits);
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
      const next = await post<ResearchSession>('research-sessions/start', { path, strategy_id: pendingStrategyId, expected_project_id: projectId, expected_binding: config.binding, expected_limits: limits, idempotency_key: idempotencyKey.current });
      idempotencyKey.current = null;
      setConfirmStart(false); selectedSessionId.current = next.id;
      lastAnnouncement.current = `${next.id}:${next.status}:${next.current_action}`;
      await load(next.id);
      revealSession(next.id);
    } catch (cause) { await load().catch(() => {}); setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  async function control(action: 'pause' | 'resume' | 'stop', target: ResearchSession | null = null) {
    if (!target) return;
    setBusy(true); setError('');
    try { await post<ResearchSession>(`research-sessions/${target.id}/control`, { path, action }); await load(target.id); }
    catch (cause) { await load(target.id).catch(() => {}); setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  function revealSession(id: string) {
    setExpanded(true);
    window.localStorage.setItem(`sigma.sessionsPane:${path}`, 'true');
    setExpandedSessionIds(current => new Set(current).add(id));
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const row = document.querySelector<HTMLElement>(`[data-session-id="${CSS.escape(id)}"]`);
      row?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }));
  }

  async function removeSession(target: ResearchSession) {
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/projects/research-sessions/${encodeURIComponent(target.id)}`, {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, expected_updated_at: target.updated_at }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Session removal failed');
      setConfirmRemoveId('');
      setExpandedSessionIds(current => { const next = new Set(current); next.delete(target.id); return next; });
      if (selectedSessionId.current === target.id) selectedSessionId.current = '';
      await load();
      setAnnouncement(`Session #${result.session_number} removed. Strategy and other sessions were kept.`);
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  const interruptedActive = activeSession?.status === 'paused' && activeSession.steps.at(-1)?.status === 'interrupted';
  const playLabel = activeSession?.status === 'paused' ? interruptedActive ? 'Resume unavailable · prior call completion is ambiguous' : 'Resume research session' : 'Start research session';
  const play = useCallback(() => {
    if (busy || readError) return;
    setExpanded(true); window.localStorage.setItem(`sigma.sessionsPane:${path}`, 'true');
    if (activeSession?.status === 'paused') { revealSession(activeSession.id); if (!interruptedActive) void control('resume', activeSession); return; }
    if (activeSession || !eligible.length) return;
    setPendingStrategyId(nextStrategyId);
    setConfirmStart(false);
    void begin();
  }, [activeSession, busy, nextStrategyId, eligible.length, interruptedActive, readError, path]);
  const pause = useCallback(() => {
    if (activeSession?.status === 'running' && !busy && !readError) void control('pause', activeSession);
  }, [activeSession, busy, readError]);
  useEffect(() => {
    onControlsChange({
      play, pause, confirming: confirmStart, start: () => void start(), cancel: () => setConfirmStart(false), nextSessionNumber: Math.max(0, ...sessions.map(item => item.session_number)) + 1,
      playDisabled: busy || !!readError || !eligible.length || confirmStart || (!!activeSession && (activeSession.status !== 'paused' || interruptedActive)),
      pauseDisabled: busy || !!readError || activeSession?.status !== 'running',
      playLabel,
    });
  }, [activeSession, busy, confirmStart, eligible.length, interruptedActive, onControlsChange, pause, play, playLabel, readError, sessions]);

  const orderedSessions = [...sessions].sort((left, right) => left.session_number - right.session_number);

  const runningCount = sessions.filter(item => item.status === 'running' || item.status === 'queued').length;
  return <section className="sessions-pane workspace-pane" aria-labelledby="sessions-heading">
    <header className="workspace-pane-heading sessions-pane-heading">
      <h2 id="sessions-heading" tabIndex={-1}><button type="button" className="workspace-section-disclosure" aria-expanded={expanded} aria-controls="sessions-pane-content" onClick={() => setExpanded(value => { window.localStorage.setItem(`sigma.sessionsPane:${path}`, String(!value)); return !value; })}><DisclosureChevron expanded={expanded}/>Sessions</button></h2>
      <p className="section-count">{sessions.length} {sessions.length === 1 ? 'session' : 'sessions'}, {runningCount} running</p>
    </header>

    <div id="sessions-pane-content" hidden={!expanded}>
    <div className="session-table">
      <div className="session-columns" aria-hidden="true"><span>Session</span><span>Status</span></div>
      {sessions.length ? <ol className="session-list" aria-label="Research sessions">
        {orderedSessions.map(item => {
          const currentAction = readError && activeSession?.id === item.id ? `State unknown · ${item.current_action}` : item.current_action;
          const sessionExpanded = expandedSessionIds.has(item.id);
          return <li className="session-row" key={item.id} data-session-id={item.id}>
            <div className="session-row-heading">
              <div className="session-heading-title-line"><button type="button" className="session-row-disclosure" aria-expanded={sessionExpanded} aria-controls={`session-content-${item.id}`} onClick={() => setExpandedSessionIds(current => { const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next; })}><DisclosureChevron expanded={sessionExpanded}/><span className="session-row-title">Session #{item.session_number}</span></button>{['completed', 'ended', 'stopped', 'failed'].includes(item.status) && <button type="button" className="text-view-link destructive-action session-remove-link" disabled={busy} onClick={() => setConfirmRemoveId(item.id)}>Remove</button>}{(item.status === 'stopped' || item.status === 'paused' && item.steps.at(-1)?.status !== 'interrupted') && <button type="button" className="text-view-link session-remove-link" disabled={busy || !!readError} onClick={() => void control('resume', item)}>Resume</button>}{['queued', 'running', 'paused'].includes(item.status) && <button type="button" className="text-view-link session-remove-link" disabled={busy} onClick={() => void control('stop', item)}>Stop</button>}</div><small className="session-strategy-name">Strategy: {item.strategy_title}</small>
              {['completed', 'stopped', 'failed'].includes(item.status) && confirmRemoveId === item.id && <div className="session-remove-actions"><div className="research-stop-confirm" role="group" aria-label={`Confirm remove Session ${item.session_number}`}><p>Remove Session #{item.session_number} and its saved research record and artifacts? The strategy and other sessions will remain.</p><button type="button" className="text-view-link destructive-action" disabled={busy} onClick={() => void removeSession(item)}>Confirm remove</button><button type="button" className="text-view-link" disabled={busy} onClick={() => setConfirmRemoveId('')}>Keep session</button></div></div>}
            </div>
            <ResearchSessionContents session={{ ...item, current_action: currentAction }} expanded={sessionExpanded} busy={busy} onControl={(action, target) => void control(action, target)} onViewStrategy={onViewStrategy}/>
          </li>;
        })}
      </ol> : !confirmStart && <p className="sessions-empty">No sessions yet. Use Play in Strategies to start one.</p>}
    </div>
    {readError && <p className="error" role="alert">Unable to confirm session state. Last confirmed information is shown: {readError}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    </div>
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
function formatDuration(totalSeconds: number) {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

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
      const result = await response.json() as { export_version: number; project: { title: string }; agentic_runs: unknown[]; research_sessions: ResearchSession[] };
      if (result.export_version !== 2 || !result.project || !Array.isArray(result.agentic_runs) || !Array.isArray(result.research_sessions)) throw new Error('Invalid project export response');
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
          <button type="button" className="settings-cancel" disabled={busy} onClick={() => cancel()}>Cancel</button>
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

function TextViews({ path, scope, strategyId, source, projectTitle, contentClass, onSaved, mathematical, onSettings, settingsDisabled, settingsButtonRef, hideProjectHeading, hideProjectActions = false, modeDisabled = false, onEnterMode, onExitMode }: {
  path: string; scope: 'project' | 'strategy'; strategyId?: string; source: string; projectTitle?: string;
  contentClass: string; onSaved: (view: ProjectView) => void; mathematical: boolean; onSettings?: () => void; settingsDisabled?: boolean; settingsButtonRef?: React.RefObject<HTMLButtonElement | null>; hideProjectHeading?: boolean; hideProjectActions?: boolean; modeDisabled?: boolean; onEnterMode?: () => boolean; onExitMode?: () => void;
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
  const editorForm = useRef<HTMLFormElement>(null);
  const editorArea = useRef<HTMLDivElement>(null);
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
    if (!version?.current || busy || modeDisabled || (onEnterMode && !onEnterMode())) return;
    setDraft(version.body); setEditingFromRendered(fromRendered);
    if (fromRendered) chooseView('rendered');
    setEditing(true); setError('');
  }
  function cancelBodyEdit(restoreFocus = true) {
    setEditing(false);
    onExitMode?.();
    if (editingFromRendered) chooseView('rendered');
    if (restoreFocus) requestAnimationFrame(() => bodyTrigger.current?.focus());
  }
  useEffect(() => {
    if (!editing) return;
    const outside = (event: PointerEvent) => { if (event.target instanceof Node && !editorArea.current?.contains(event.target)) cancelBodyEdit(false); };
    document.addEventListener('pointerdown', outside, true);
    return () => document.removeEventListener('pointerdown', outside, true);
  }, [editing, editingFromRendered]);
  async function convert(targetFormat: TextFormat = format) {
    if (!data || busy) return;
    const controller = new AbortController(); abort.current = controller; setBusy(true); setRendering(true); setError('');
    let finishProviderRequest = () => {};
    try {
      const settingsResponse = await fetch(`/api/projects/proposals/config?${new URLSearchParams({ path })}`, { signal: controller.signal });
      const settings = await settingsResponse.json();
      if (!settingsResponse.ok || !settings.available) { if (settingsResponse.ok) reportRequestFailure(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.'); throw new Error(settings.message ?? settings.error ?? 'Connect AI in the header, then retry.'); }
      finishProviderRequest = beginProviderRequest('text-conversion');
      const response = await fetch('/api/projects/text/convert', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ path, scope, strategy_id: strategyId, target: targetFormat, expected_digest: data.source_digest, expected_binding: settings.binding }) });
      const next = await response.json();
      if (!response.ok) throw new Error(next.error ?? 'Conversion failed; source text was kept.');
      setData(next as TextRepresentations); setDraft(next[targetFormat]?.body ?? ''); chooseView(targetFormat === 'markdown' ? 'rendered' : 'plain');
    } catch (cause) { if (!controller.signal.aborted) { chooseView('plain'); setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); } }
    finally { finishProviderRequest(); if (abort.current === controller) { abort.current = null; setBusy(false); setRendering(false); } }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (!data || busy) return;
    setBusy(true); setError('');
    try {
      const next = await post<ProjectView>('text/source', { path, scope, strategy_id: strategyId, body: draft, format, expected_digest: data.source_digest });
      setEditing(false); onExitMode?.(); onSaved(next);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  const name = scope === 'project' ? 'research problem' : 'strategy approach';
  const plainRecovery = data?.source_format === 'markdown' && !data.plain?.current;
  const renderTooltip = rendering ? (plainRecovery ? 'Converting to Plain' : 'Converting to markdown') : selected === 'rendered' ? 'Show plain text' : plainRecovery ? 'Convert to Plain' : 'Convert to markdown';
  const renderTooltipId = `sigma-render-tooltip-${scope}-${strategyId ?? 'project'}`;
  function closeExport() {
    setExportOpen(false);
    requestAnimationFrame(() => exportTrigger.current?.focus());
  }
  const viewActions = <>
    {mathematical && <TooltipWrap>
      <button type="button" className={`sigma-render-toggle${selected === 'rendered' || rendering ? ' sigma-render-active' : ''}${rendering ? ' sigma-render-pending' : ''}`}
      aria-label={selected === 'rendered' ? `Show plain ${name}` : plainRecovery ? `Convert ${name} to Plain` : `Render ${name} as Markdown`}
      aria-pressed={selected === 'rendered' || rendering} aria-describedby={renderTooltipId}
      disabled={editing || busy} onClick={() => {
        if (selected === 'rendered') { chooseView('plain'); setError(''); }
        else if (data?.markdown?.current) { chooseView('rendered'); setError(''); }
        else { void convert(plainRecovery ? 'plain' : 'markdown'); }
      }}><span aria-hidden="true">{rendering ? "⌛" : "Σ"}</span></button>
      <span id={renderTooltipId} className="sigma-render-tooltip" role="tooltip">{renderTooltip}</span>
    </TooltipWrap>}

    {editing ? <>
      <button type="submit" form={`text-form-${scope}-${strategyId ?? 'project'}`} className="text-view-link" disabled={busy || !draft.trim()}>Save</button>
      <button type="button" className="text-view-link" disabled={busy} onClick={() => cancelBodyEdit()}>Cancel</button>
      </> : data && version && <TooltipWrap><button type="button" className="text-view-link text-view-icon" aria-label={`Edit ${name}`} aria-describedby={`edit-tooltip-${scope}-${strategyId ?? 'project'}`} disabled={modeDisabled} onClick={() => beginBodyEdit(selected === 'rendered')}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg></button><span id={`edit-tooltip-${scope}-${strategyId ?? 'project'}`} className="sigma-render-tooltip" role="tooltip">{`Edit ${name}`}</span></TooltipWrap>}

    {!hideProjectActions && scope === 'project' && !editing && <TooltipWrap><button ref={exportTrigger} type="button" className="copper-button project-download-trigger" aria-label="Download project" aria-describedby="download-project-tooltip" onClick={() => setExportOpen(true)}><svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg></button><span id="download-project-tooltip" className="sigma-render-tooltip" role="tooltip">Download project</span></TooltipWrap>}
    {!hideProjectActions && onSettings && !editing && <TooltipWrap><button ref={settingsButtonRef} type="button" className="text-view-link text-view-icon" aria-label="Project settings" aria-describedby="project-settings-tooltip" disabled={settingsDisabled} onClick={onSettings}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M10 2h4l.6 2.3 1.4.8 2.3-.7 2.8 2.8-.7 2.3.8 1.4L23 11v4l-2.3.6-.8-1.4.7 2.3-2.8 2.8-2.3-.7-1.4.8L14 24h-4l-.6-2.3-1.4-.8-2.3.7-2.8-2.8.7-2.3-.8-1.4L1 15v-4l2.3-.6.8-1.4-.7-2.3 2.8-2.8 2.3.7 1.4-.8L10 2Z" transform="translate(0 -1) scale(1 .95)"/><circle cx="12" cy="12" r="3"/></svg></button><span id="project-settings-tooltip" className="sigma-render-tooltip" role="tooltip">Project settings</span></TooltipWrap>}
  </>;
  return <div ref={editorArea} className={`text-views${scope === 'project' ? ' project-text-views' : ''}${mathematical ? ' math-text-views' : ''}`}>
    {scope === 'project' && exportOpen && <DownloadProjectDialog path={path} title={projectTitle ?? 'project'} onCancel={closeExport}/>}
    <div className="text-view-controls">
      {scope === 'project' && !hideProjectHeading && <h2 className="investigation-heading">Project</h2>}
      {scope === 'project' ? <div className="project-text-actions">{viewActions}</div> : viewActions}
    </div>
    {editing ? <form ref={editorForm} id={`text-form-${scope}-${strategyId ?? 'project'}`} className="text-view-editor" onSubmit={save}>
      <textarea id={`text-editor-${scope}-${strategyId ?? 'project'}`} autoFocus value={draft} maxLength={scope === 'project' ? 20000 : 10000} rows={8} required disabled={busy} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); cancelBodyEdit(); } }}/>
    </form> : current && version ? selected === 'rendered'
      ? <div className={`${contentClass} rendered-text`} aria-label={`Rendered ${name}`}><Suspense fallback={<p>Preparing preview…</p>}><RenderedMarkdown body={version.body}/></Suspense></div>
      : <p className={contentClass}>{version.body}</p>
      : !data ? <p className={contentClass}>{source}</p> : <div className="text-view-missing">
        <p>{version ? 'The previous conversion is out of date with the current source.' : `No ${format === 'markdown' ? 'Markdown' : 'Plain'} representation is stored yet.`}</p>
        {mathematical && plainRecovery && format === 'plain' && <button type="button" className="text-view-link" disabled={busy || modeDisabled} onClick={() => void convert('plain')}>Convert to Plain</button>}
        {version && <details><summary>Inspect previous {format === 'markdown' ? 'Markdown' : 'Plain'} text</summary><pre>{version.body}</pre></details>}
      </div>}
    {busy && !editing && <span className="sr-only" role="status">Converting to Markdown…</span>}
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}

function ProjectPaneTitle({ view, onSaved, disabled, modeDisabled, onEnterMode, onExitMode }: { view: ProjectView; onSaved: (view: ProjectView) => void; disabled: boolean; modeDisabled: boolean; onEnterMode: () => boolean; onExitMode: () => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(view.project.title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => { if (!editing) setDraft(view.project.title); }, [view.project.title, editing]);
  useEffect(() => { if (editing) { input.current?.focus(); input.current?.select(); } }, [editing]);
  useEffect(() => {
    if (!editing) return;
    const outside = (event: PointerEvent) => { if (event.target instanceof Node && !form.current?.contains(event.target)) cancel(false); };
    document.addEventListener('pointerdown', outside, true);
    return () => document.removeEventListener('pointerdown', outside, true);
  }, [editing]);
  function cancel(restoreFocus = true) { setDraft(view.project.title); setError(''); setEditing(false); onExitMode(); if (restoreFocus) requestAnimationFrame(() => trigger.current?.focus()); }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!draft.trim()) { setError('Enter a project title.'); input.current?.focus(); return; }
    setBusy(true); setError('');
    try {
      const current = settingsOf(view);
      const next = await post<ProjectView>('update', { path: view.path, ...current, title: draft, expected: current });
      setEditing(false); onExitMode(); onSaved(next); requestAnimationFrame(() => trigger.current?.focus());
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <div className={`project-pane-title-line${editing ? ' is-renaming' : ''}`}>
    {editing ? <form ref={form} className="project-title-edit-form" onSubmit={save}>
      <label className="sr-only" htmlFor="project-pane-title-input">Project title</label>
      <input ref={input} id="project-pane-title-input" aria-label="Project title" value={draft} maxLength={200} required disabled={busy} onChange={event => { setDraft(event.target.value); setError(''); }} onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); cancel(); } }}/>
      <button type="submit" className="text-view-link" disabled={busy}>Save</button><button type="button" className="text-view-link" disabled={busy} onClick={() => cancel()}>Cancel</button>
      {error && <p role="alert" className="project-title-error">{error}</p>}
    </form> : <><h3 className="current-project">{view.project.title}</h3>
      <button type="button" ref={trigger} className="text-view-link text-view-icon project-title-pencil" aria-label={`Edit project title: ${view.project.title}`} title="Edit project title" disabled={disabled || modeDisabled} onClick={() => { if (onEnterMode()) setEditing(true); }}>
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg>
      </button></>}
  </div>;
}

function Header({ goHome, close, projectArtwork = false, connectionDisabled = false }: { goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; projectArtwork?: boolean; connectionDisabled?: boolean }) {
  return <header className={projectArtwork ? 'site-header project-art-header' : 'site-header'}>
    <div className="brand-block">
      <a href="/" className={projectArtwork ? 'brand project-header-art' : 'brand'} onClick={goHome} aria-label="SIGMA home"><img src={projectArtwork ? '/sigma-project-header.png' : '/sigma-workspace-logo.png'} alt="SIGMA" /></a>
      {projectArtwork ? close && <div className="project-title-line"><button className="project-back" type="button" onClick={close.action} disabled={close.busy} aria-label="Back to Home" title="Back to Home"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m14 5-7 7 7 7M7 12h13"/></svg></button><span className="project-back-label">Back to Home</span></div>
        : <p className="expansion">Strategy Investigation, Generation, Measurement &amp; Assessment</p>}
    </div>
    <div className="header-controls">
    {!close && <span className="local">● Local workspace</span>}
    <ConnectionStatus disabled={connectionDisabled}/>
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

function WorkspaceFrame({ children, goHome, close, connectionDisabled = false }: {
  children: React.ReactNode; goHome: (event: MouseEvent<HTMLAnchorElement>) => void;
  close?: { action: () => void; busy: boolean }; connectionDisabled?: boolean;
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
    <Header goHome={goHome} close={close} projectArtwork connectionDisabled={connectionDisabled}/>
    <div className={`workspace-layout${!ENABLE_WORKSPACE_SIDEBAR ? ' sidebar-disabled' : collapsed ? ' nav-collapsed' : ''}`}>
      {ENABLE_WORKSPACE_SIDEBAR && <nav className="workspace-nav" aria-label="Project navigation">
        <button className="nav-collapse" type="button" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={toggleSidebar}><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={collapsed ? 'm9 6 6 6-6 6' : 'm15 6-6 6 6 6'}/></svg></button>
        <a href="#project-pane-heading" aria-label="Project" title={collapsed ? 'Project' : undefined} onClick={event => { event.preventDefault(); focusWorkspace('project-pane-heading'); }}><WorkspaceIcon name="Settings"/><span>Project</span></a>
        <a href="#sessions-heading" aria-label="Sessions" title={collapsed ? 'Sessions' : undefined} onClick={event => { event.preventDefault(); focusWorkspace('sessions-heading'); }}><WorkspaceIcon name="Analysis"/><span>Sessions</span></a>
        <a href="#pool-heading" aria-current="page" aria-label="Strategies" title={collapsed ? 'Strategies' : undefined} onClick={event => {
          event.preventDefault(); focusWorkspace('pool-heading');
        }}><WorkspaceIcon name="Strategies"/><span>Strategies</span></a>
        {['Renders', 'Analysis', 'References', 'Notes', 'Settings'].map(name =>
          <button key={name} disabled title={collapsed ? `${name} · later` : 'Not available yet'} aria-label={name} aria-describedby="workspace-nav-help">
            <WorkspaceIcon name={name}/><span>{name}</span><small>Later</small>
          </button>)}
        <p id="workspace-nav-help">Other destinations are not available yet.</p>
      </nav>}
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
  const [activeTab, setActiveTab] = useState<'main' | 'limits'>('main');
  const [limitDraft, setLimitDraft] = useState<ResearchLimitsDraft>(() => draftLimits({ research_rounds: 3, model_calls: 6, session_duration_minutes: 30, output_tokens_per_call: 4000, maximum_estimated_cost_usd: null }));
  const [limitsLoaded, setLimitsLoaded] = useState(!initial);
  const limitValidation = validateLimitDraft(limitDraft);
  useEffect(() => { dialog.current?.showModal(); first.current?.focus(); }, []);
  useEffect(() => {
    if (!initial) return;
    const controller = new AbortController();
    fetch(`/api/projects/research-limits?${new URLSearchParams({ path: initial.path })}`, { signal: controller.signal }).then(async response => {
      const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Research limits could not be read');
      setLimitDraft(draftLimits(data)); setLimitsLoaded(true);
    }).catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)); });
    return () => controller.abort();
  }, [initial?.path]);
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
    event.preventDefault(); if (submitting.current || !compatible || (initial && !limitValidation.value) || (!initial && (!destination?.path || destination.exists || previewBusy))) return;
    submitting.current = true; setBusy(true); setError('');
    try {
      const next = await post<ProjectView>(initial ? 'update' : 'create', initial ? { path: initial.path, ...values, expected: settingsOf(initial) } : values);
      if (initial) {
        const response = await fetch('/api/projects/research-limits', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: initial.path, ...limitValidation.value }) });
        const result = await response.json(); if (!response.ok) throw new Error(result.error ?? 'Research limits were not saved');
        setLimitDraft(draftLimits(result));
      }
      onSaved(next);
    }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog ref={dialog} className={`project-settings-dialog ${initial ? 'edit-project-dialog' : 'new-project-dialog'}`} aria-labelledby="project-settings-heading" aria-describedby="project-settings-help" onCancel={event => { event.preventDefault(); if (!submitting.current) onCancel(); }}>
    <form onSubmit={save}>
      <header className="settings-header"><h2 id="project-settings-heading">{initial ? 'Settings' : 'New Project'}</h2>
        <div className="settings-actions"><button type="submit" disabled={busy || !values.ai_model || !compatible || !!pairError || (initial && (!limitsLoaded || !limitValidation.value)) || (!initial && (!values.problem.trim() || previewBusy || !destination?.path || destination.exists))}>{busy ? 'Saving…' : initial ? 'Save' : 'Create'}</button><button className="settings-cancel" type="button" disabled={busy} onClick={() => { if (!submitting.current) onCancel(); }}>Cancel</button></div>
      </header>
      {initial && <div role="tablist" aria-label="Project settings" className="settings-tabs" onKeyDown={event => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) { event.preventDefault(); const next = event.key === 'Home' ? 'main' : event.key === 'End' ? 'limits' : activeTab === 'main' ? 'limits' : 'main'; setActiveTab(next); dialog.current?.querySelector<HTMLButtonElement>(`[data-settings-tab="${next}"]`)?.focus(); } }}>
        <button type="button" role="tab" data-settings-tab="main" id="settings-tab-main" aria-selected={activeTab === 'main'} aria-controls="settings-panel-main" tabIndex={activeTab === 'main' ? 0 : -1} onClick={() => setActiveTab('main')}>Main</button>
        <button type="button" role="tab" data-settings-tab="limits" id="settings-tab-limits" aria-selected={activeTab === 'limits'} aria-controls="settings-panel-limits" tabIndex={activeTab === 'limits' ? 0 : -1} onClick={() => setActiveTab('limits')}>Limits</button>
      </div>}
      <div className="settings-body" id={initial ? 'settings-panel-main' : undefined} role={initial ? 'tabpanel' : undefined} aria-labelledby={initial ? 'settings-tab-main' : undefined} hidden={!!initial && activeTab !== 'main'}><p id="project-settings-help">{initial ? 'Choose how to explore this project. Edit its title and description directly on the project page.' : 'Name a project and choose how to explore it.'}</p>
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
    </fieldset></div>
    {initial && <section id="settings-panel-limits" className="settings-body research-limits-panel" role="tabpanel" aria-labelledby="settings-tab-limits" hidden={activeTab !== 'limits'}>
      <p>These limits apply to future sessions. Existing sessions keep the limits captured when they started.</p>
      <fieldset disabled={busy || !limitsLoaded}>
        <label htmlFor="research-rounds">Research rounds</label><input id="research-rounds" type="number" min={1} max={10} step={1} value={limitDraft.research_rounds} aria-invalid={!!limitValidation.errors.research_rounds} aria-describedby="research-rounds-help research-rounds-error" onChange={event => setLimitDraft(value => ({ ...value, research_rounds: event.target.value }))}/><p id="research-rounds-help" className="settings-hint">Investigator/Skeptic iterations, from 1 to 10.</p>{limitValidation.errors.research_rounds && <p id="research-rounds-error" className="limit-error" role="alert">{limitValidation.errors.research_rounds}</p>}
        <label htmlFor="research-calls">Model calls</label><input id="research-calls" type="number" min={2} max={20} step={1} value={limitDraft.model_calls} aria-invalid={!!limitValidation.errors.model_calls} aria-describedby="research-calls-help research-calls-error" onChange={event => setLimitDraft(value => ({ ...value, model_calls: event.target.value }))}/><p id="research-calls-help" className="settings-hint">Provider request allowance, 2 to 20. At least two calls per round are required for Investigator and Skeptic.</p>{limitValidation.errors.model_calls && <p id="research-calls-error" className="limit-error" role="alert">{limitValidation.errors.model_calls}</p>}
        <label htmlFor="research-duration">Session duration (minutes)</label><input id="research-duration" type="number" min={1} max={120} step={1} value={limitDraft.session_duration_minutes} aria-invalid={!!limitValidation.errors.session_duration_minutes} aria-describedby="research-duration-help research-duration-error" onChange={event => setLimitDraft(value => ({ ...value, session_duration_minutes: event.target.value }))}/><p id="research-duration-help" className="settings-hint">Elapsed wall time from start, 1 to 120 minutes. Time spent paused counts.</p>{limitValidation.errors.session_duration_minutes && <p id="research-duration-error" className="limit-error" role="alert">{limitValidation.errors.session_duration_minutes}</p>}
        <label htmlFor="research-output-tokens">Maximum output tokens per call</label><input id="research-output-tokens" type="number" min={256} max={16384} step={1} value={limitDraft.output_tokens_per_call} aria-invalid={!!limitValidation.errors.output_tokens_per_call} aria-describedby="research-output-help research-output-error" onChange={event => setLimitDraft(value => ({ ...value, output_tokens_per_call: event.target.value }))}/><p id="research-output-help" className="settings-hint">256 to 16,384. SIGMA sends this limit where supported; ChatGPT routing may not expose provider enforcement, so parsed output remains bounded separately.</p>{limitValidation.errors.output_tokens_per_call && <p id="research-output-error" className="limit-error" role="alert">{limitValidation.errors.output_tokens_per_call}</p>}
        <label htmlFor="research-cost-limit">Maximum estimated session cost (USD)</label><input id="research-cost-limit" type="number" min={0.01} max={100} step="0.01" placeholder="Unlimited" value={limitDraft.maximum_estimated_cost_usd} aria-invalid={!!limitValidation.errors.maximum_estimated_cost_usd} aria-describedby="research-cost-help research-cost-error" onChange={event => setLimitDraft(value => ({ ...value, maximum_estimated_cost_usd: event.target.value }))}/><p id="research-cost-help" className="settings-hint">API-key billing only: $0.01 to $100.00, or blank for unlimited. ChatGPT subscription usage is not converted to dollars. Estimates use published prices and reported tokens; unknown prices or missing usage pause further calls when a cap is set.</p>{limitValidation.errors.maximum_estimated_cost_usd && <p id="research-cost-error" className="limit-error" role="alert">{limitValidation.errors.maximum_estimated_cost_usd}</p>}
      </fieldset>
      {!limitsLoaded && <p role="status">Loading saved research limits…</p>}{error && <p role="alert" className="error">{error} <button type="button" className="text-view-link" onClick={async () => { setError(''); try { const response = await fetch(`/api/projects/research-limits?${new URLSearchParams({ path: initial.path })}`); const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'Research limits could not be read'); setLimitDraft(draftLimits(data)); setLimitsLoaded(true); } catch (cause) { setError(errorMessage(cause)); } }}>Retry</button></p>}
    </section>}
    </form>
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
    const currentPath = window.localStorage.getItem('sigma.currentProject');
    setProjects(currentPath ? [...data.projects].sort((a: RecentProject, b: RecentProject) => Number(b.path === currentPath) - Number(a.path === currentPath)) : data.projects); setLoading(false);
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
          <button className="recent-open" disabled={!entry.available || !!opening} onClick={() => void open(entry)}>{entry.path === window.localStorage.getItem('sigma.currentProject') ? <strong className="is-current-project">{entry.title}</strong> : entry.title}</button>
        </div>
        <div className="recent-meta-row"><small>{entry.investigation_type === 'mathematical' ? 'Mathematical' : entry.investigation_type === 'default' ? 'Default' : 'Unavailable'}{entry.strategy_count === null ? '' : ` · ${strategyCount(entry.strategy_count)}`}</small><button className="recent-forget" disabled={!!opening} aria-label={`Remove ${entry.title} from Recent Projects`} title="Remove from Recent Projects; keep all research" onClick={() => void forget(entry)}>Remove</button></div>
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

function StrategyTitleEditor({ strategy, path, onSaved, modeDisabled, onEnterMode, onExitMode, expanded, onToggle, commands }: {
  strategy: Strategy; path: string; onSaved: (view: ProjectView) => void; modeDisabled: boolean; onEnterMode: () => boolean; onExitMode: () => void;
  expanded: boolean; onToggle: () => void; commands: ReactNode;
}) {
  const [editing, setEditing] = useState(false);
  const shownTitle = displayStrategyTitle(strategy);
  const [draft, setDraft] = useState(shownTitle);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => { if (!editing) setDraft(shownTitle); }, [shownTitle, editing]);
  useEffect(() => { if (editing) { input.current?.focus(); input.current?.select(); } }, [editing]);
  useEffect(() => {
    if (!editing) return;
    const outside = (event: PointerEvent) => { if (event.target instanceof Node && !form.current?.contains(event.target)) cancel(false); };
    document.addEventListener('pointerdown', outside, true);
    return () => document.removeEventListener('pointerdown', outside, true);
  }, [editing]);
  function cancel(restoreFocus = true) {
    setEditing(false); onExitMode(); setDraft(shownTitle); setError('');
    if (restoreFocus) requestAnimationFrame(() => trigger.current?.focus());
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
      setEditing(false); onExitMode(); onSaved(next);
      requestAnimationFrame(() => trigger.current?.focus());
    } catch (cause) { setError(errorMessage(cause)); reportRequestFailure(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <div className={`strategy-title-editor${editing ? ' is-renaming' : ''}`}>
    {editing ? <form ref={form} onSubmit={save} className="strategy-rename-form">
      <label className="sr-only" htmlFor={`strategy-title-${strategy.id}`}>Strategy title</label>
      <input ref={input} id={`strategy-title-${strategy.id}`} aria-label="Strategy title" value={draft} maxLength={200} disabled={busy}
        required onChange={event => { setDraft(event.target.value); setError(''); }} onKeyDown={event => { if (event.key === 'Escape' && !busy) { event.preventDefault(); cancel(); } }}/>
      <button type="submit" className="text-view-link" disabled={busy}>Save</button>
      <button type="button" className="text-view-link" disabled={busy} onClick={() => cancel()}>Cancel</button>
    </form> : <div className="strategy-title-line">
      <button type="button" id={`strategy-${strategy.id}`} className="strategy-row-disclosure" aria-expanded={expanded} aria-controls={`strategy-content-${strategy.id}`} onClick={onToggle}><DisclosureChevron expanded={expanded}/><h3>{shownTitle}</h3></button>
      <button type="button" ref={trigger} className="text-view-link text-view-icon strategy-title-pencil" aria-label={`Edit strategy title: ${shownTitle}`} disabled={modeDisabled}
        onClick={() => { if (onEnterMode()) setEditing(true); }}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/></svg></button>
      {commands}
    </div>}
    {error && <p className="error" role="alert">{error}</p>}
  </div>;
}

function StrategyCommands({ strategy, onCommand, disabled = false }: {
  strategy: Strategy; onCommand: (mode: 'remove' | 'stage' | 'fork', strategy: Strategy) => void; disabled?: boolean;
}) {
  const disclosure = useRef<HTMLDetailsElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
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
  return <details className="strategy-commands" name="strategy-commands" ref={disclosure} onToggle={() => {
    setMenuOpen(disclosure.current?.open ?? false);
    positionMenu();
    if (disclosure.current?.open) requestAnimationFrame(() => disclosure.current?.querySelector<HTMLButtonElement>('[role="menuitem"]:not(:disabled)')?.focus());
  }} onClick={() => requestAnimationFrame(positionMenu)} onKeyDown={event => {
    if (event.key === 'Escape' && disclosure.current) {
      event.preventDefault(); event.stopPropagation(); disclosure.current.open = false;
      disclosure.current.querySelector('summary')?.focus();
    }
  }}>
    <summary id={`commands-${strategy.id}`} role="button" className="secondary strategy-toggle" aria-label={`More actions for ${strategy.title}`} aria-haspopup="menu" aria-expanded={menuOpen} aria-disabled={disabled} tabIndex={disabled ? -1 : 0} onClick={event => { if (disabled) event.preventDefault(); }}>
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none">
        <circle cx="8" cy="3" r="1.3" fill="currentColor"/><circle cx="8" cy="8" r="1.3" fill="currentColor"/><circle cx="8" cy="13" r="1.3" fill="currentColor"/>
      </svg>
    </summary>
    <div className="command-panel" role="menu" aria-labelledby={`commands-${strategy.id}`} onKeyDown={event => {
      const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)'));
      const index = items.indexOf(document.activeElement as HTMLButtonElement);
      let next = -1;
      if (event.key === 'ArrowDown') next = (index + 1) % items.length;
      else if (event.key === 'ArrowUp') next = (index - 1 + items.length) % items.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = items.length - 1;
      if (next >= 0 && items.length) { event.preventDefault(); items[next].focus(); }
    }}>
      <button role="menuitem" className="secondary" disabled title="Scheduling is not available yet" aria-describedby={`schedule-explanation-${strategy.id}`}>Schedule</button>
      <button role="menuitem" className="secondary" disabled={disabled} onClick={() => { if (disclosure.current) disclosure.current.open = false; onCommand('fork', strategy); }}>Fork</button>
      <button role="menuitem" className="secondary" disabled title="Artifact reporting is not available yet" aria-describedby={`report-explanation-${strategy.id}`}>Report artifact</button>
      <button role="menuitem" className="secondary" disabled={disabled} onClick={() => { if (disclosure.current) disclosure.current.open = false; onCommand('stage', strategy); }}>Change stage</button>
      <hr role="separator"/>
      <button role="menuitem" className="secondary destructive-action" disabled={disabled} onClick={() => { if (disclosure.current) disclosure.current.open = false; onCommand('remove', strategy); }}>Remove</button>
      <span className="sr-only" id={`schedule-explanation-${strategy.id}`}>Scheduling is not available yet.</span>
      <span className="sr-only" id={`report-explanation-${strategy.id}`}>Artifact reporting is not available yet.</span>
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

function StrategyCreationActions({ buttonRef, disabled, hideNew = false, onManual, onAI }: {
  buttonRef: React.RefObject<HTMLButtonElement | null>; disabled: boolean; hideNew?: boolean; onManual: () => void; onAI: () => void;
}) {
  return <div className="strategy-heading-actions">
    {!hideNew && <button type="button" className="text-view-link" ref={buttonRef} disabled={disabled} onClick={onManual}>New</button>}
    <button type="button" className="text-view-link" disabled={disabled} onClick={onAI}>Generate</button>
  </div>;
}

function ProcessControlsView({ controls, disabled }: { controls: ProcessControls; disabled: boolean }) {
  return <span className="strategy-process-controls" aria-label="Research process controls">
      {controls.confirming ? <>
        <button type="button" className="text-view-link session-start-link" disabled={disabled} onClick={controls.start}>Start session #{controls.nextSessionNumber}</button>
        <button type="button" className="text-view-link session-start-link" disabled={disabled} onClick={controls.cancel}>Cancel</button>
      </> : <>
      <button type="button" className="text-view-link text-view-icon process-control" aria-label={controls.playLabel} title={controls.playLabel} disabled={controls.playDisabled || disabled} onClick={controls.play}>
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6 3.8v12.4L16 10 6 3.8Z"/></svg>
      </button>
      <button type="button" className="text-view-link text-view-icon process-control" aria-label="Pause research session" title="Pause research session" disabled={controls.pauseDisabled || disabled} onClick={controls.pause}>
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5.5 4h3.2v12H5.5zM11.3 4h3.2v12h-3.2z"/></svg>
      </button>
      </>}
  </span>;
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
function GenerateStrategy({ path, projectId, sourceGuard, onSaved, onCancel }: {
  path: string; projectId: string; sourceGuard: string; onSaved: (view: ProjectView) => void; onCancel: () => void;
}) {
  const composer = useRef<HTMLDivElement>(null);
  const request = useRef<AbortController | null>(null);
  const submitting = useRef(false);
  const [config, setConfig] = useState<{ available: boolean; provider: string; mode: string; binding: string; project_id: string; model: string; reasoning_effort: string; message: string } | null>(null);
  const [seed, setSeed] = useState('');
  const ai = useAI();
  const lifetime = useRef(new AbortController());
  const runGuard = useRef('');
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
    runGuard.current = sourceGuard;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError(''); setActivities([]); setCurrentActivity('Preparing run'); setReview(null);
    let finishProviderRequest = () => {};
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
      finishProviderRequest = beginProviderRequest('strategy-generation');
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
    finally { finishProviderRequest(); if (request.current === controller) {
      request.current = null;
      submitting.current = false; setBusy(false); setCancelling(false);
    } }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (submitting.current || !result) return; submitting.current = true; setSaving(true); setError('');
    try {
      if (runGuard.current !== sourceGuard) throw new Error('Project research inputs changed while this strategy was generating. Regenerate against the current project before accepting; this draft is still available for reference.');
      onSaved(await post<ProjectView>('strategies', { path, title, approach, summary, receipt: result.receipt }));
    }
    catch (error) { setError(errorMessage(error)); }
    finally { submitting.current = false; setSaving(false); }
  }
  return <div ref={composer} className="strategy-form proposal-dialog inline-proposal" role="region" aria-labelledby="proposal-heading" aria-describedby="proposal-help" onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); cancel(); } }}>
    <div className="proposal-heading-row"><h2 id="proposal-heading">Generate a strategy</h2><button type="button" className="text-view-link proposal-heading-generate" disabled={(!config?.available && !needsConnection) || busy || saving || ai.connecting} onClick={() => void generate()}>{busy ? cancelling ? 'Cancelling…' : ai.connecting ? 'Connecting…' : 'Generating…' : result ? 'Regenerate' : 'Generate'}</button>{result && <button type="submit" form="proposal-save-form" className="text-view-link proposal-heading-save" disabled={busy || saving}>{saving ? 'Accepting…' : 'Accept'}</button>}<button type="button" className="text-view-link proposal-heading-cancel" disabled={saving || cancelling} onClick={() => void cancel()}>{busy ? cancelling ? 'Cancelling…' : "Cancel request" : "Cancel"}</button></div>
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
  const [downloadOpen, setDownloadOpen] = useState(false);
  const modeOwner = useRef<string | null>(null);
  const [activeMode, setActiveMode] = useState<string | null>(null);
  const enterMode = useCallback((owner: string) => {
    if (modeOwner.current !== null) return false;
    modeOwner.current = owner; setActiveMode(owner); return true;
  }, []);
  const exitMode = useCallback((owner: string) => {
    if (modeOwner.current !== owner) return;
    modeOwner.current = null; setActiveMode(null);
  }, []);
  const editProjectButton = useRef<HTMLButtonElement>(null);
  const [ordering, setOrdering] = useState(false);
  const [previewOrder, setPreviewOrder] = useState<string[] | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const drag = useRef<{ id: string; order: string[]; pointer: number | null } | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const [command, setCommand] = useState<{ mode: 'remove' | 'stage'; strategy: Strategy } | null>(null);
  const [focusStrategy, setFocusStrategy] = useState('');
  const [strategiesExpanded, setStrategiesExpanded] = useState(() => window.localStorage.getItem(`sigma.strategiesPane:${path}`) !== 'false');
  const [collapsedStrategies, setCollapsedStrategies] = useState<Set<string>>(() => new Set());
  const [projectExpanded, setProjectExpanded] = useState(() => window.localStorage.getItem(`sigma.projectPane:${path}`) !== 'false');
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
  }, [view?.project.id, !!error]);
  useEffect(() => {
    if (!focusStrategy || !strategiesExpanded) return;
    const target = document.getElementById(`strategy-${focusStrategy}`);
    requestAnimationFrame(() => { target?.scrollIntoView({ block: 'center', behavior: 'smooth' }); target?.focus(); });
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
  const frame = { goHome, close: { action: close, busy: closing }, connectionDisabled: activeMode !== null };
  function toggleStrategiesPane() {
    setStrategiesExpanded(open => { window.localStorage.setItem(`sigma.strategiesPane:${path}`, String(!open)); return !open; });
  }
  function showStrategy(id: string) {
    setCollapsedStrategies(current => { const next = new Set(current); next.delete(id); return next; });
    if (!strategiesExpanded) {
      setStrategiesExpanded(true);
      window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'true');
    }
    if (id) setFocusStrategy(id);
  }
  function cancel() { setEditing(false); exitMode('new-strategy'); requestAnimationFrame(() => newButton.current?.focus()); }
  function expandStrategies() { setStrategiesExpanded(true); window.localStorage.setItem(`sigma.strategiesPane:${path}`, 'true'); }
  function startNewStrategy() {
    if (!enterMode('new-strategy')) return;
    expandStrategies(); setManualDraft(undefined); setEditing(true);
    requestAnimationFrame(() => document.getElementById('strategy-title')?.focus());
  }
  function startGeneration() {
    if (modeOwner.current !== null || generating) return;
    expandStrategies(); setGenerating(true);
    requestAnimationFrame(() => document.getElementById('proposal-seed')?.focus());
  }
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
      <header className="workspace-pane-heading project-pane-heading"><h2 id="project-pane-heading" ref={heading} tabIndex={-1}><button type="button" className="workspace-section-disclosure" aria-expanded={projectExpanded} aria-controls="project-pane-content" onClick={() => setProjectExpanded(value => { window.localStorage.setItem(`sigma.projectPane:${path}`, String(!value)); return !value; })}><DisclosureChevron expanded={projectExpanded}/>Project</button></h2><div className="project-pane-actions"><button type="button" className="text-view-link text-view-icon" aria-label="Download project" title="Download project" disabled={closing || ordering || !!dragId} onClick={() => setDownloadOpen(true)}><svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg></button><button ref={editProjectButton} type="button" className="text-view-link text-view-icon" aria-label="Project settings" title="Settings" disabled={closing || ordering || !!dragId || activeMode !== null} onClick={() => { if (enterMode('project-settings')) setProjectEditing(true); }}><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M10 2h4l.6 2.3 1.4.8 2.3-.7 2.8 2.8-.7 2.3.8 1.4L23 11v4l-2.3.6-.8-1.4.7 2.3-2.8 2.8-2.3-.7-1.4.8L14 24h-4l-.6-2.3-1.4-.8-2.3.7-2.8-2.8.7-2.3-.8-1.4L1 15v-4l2.3-.6.8-1.4-.7-2.3 2.8-2.8 2.3.7 1.4-.8L10 2Z" transform="translate(0 -1) scale(1 .95)"/><circle cx="12" cy="12" r="3"/></svg></button></div></header>
      <div id="project-pane-content" hidden={!projectExpanded}>
      <ProjectPaneTitle view={view} onSaved={setView} disabled={closing || ordering || !!dragId} modeDisabled={activeMode !== null && activeMode !== 'project-title'} onEnterMode={() => enterMode('project-title')} onExitMode={() => exitMode('project-title')}/>
      <div className="project-pane-content">
        <div className="project-intro" id="project-intro-pane" ref={introPane} style={introHeight === null ? undefined : { height: introHeight, maxHeight: 'min(75dvh, 800px)' }}>
          <TextViews mathematical={project.investigation_type === 'mathematical'} path={view.path} scope="project" source={project.problem} projectTitle={project.title} contentClass="objective" onSaved={setView} hideProjectActions hideProjectHeading modeDisabled={activeMode !== null && activeMode !== 'text-project'} onEnterMode={() => enterMode('text-project')} onExitMode={() => exitMode('text-project')}/>
        </div>
        <div className="project-pane-resizer" role="separator" tabIndex={0} aria-label="Resize project description" aria-controls="project-intro-pane" aria-orientation="horizontal" aria-valuemin={120} aria-valuemax={introMaximum} aria-valuenow={introHeight ?? undefined} title="Drag or use arrow keys to resize the project description"
      onPointerDown={event => { if (event.button !== 0) return; const height = introPane.current?.getBoundingClientRect().height ?? 120; resizeStart.current = { pointer: event.pointerId, y: event.clientY, height }; event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault(); }}
      onPointerMove={event => { const start = resizeStart.current; if (start?.pointer === event.pointerId) setIntroHeight(clampIntro(start.height + event.clientY - start.y)); }}
      onPointerUp={event => { if (resizeStart.current?.pointer === event.pointerId) resizeStart.current = null; }}
      onPointerCancel={event => { if (resizeStart.current?.pointer === event.pointerId) resizeStart.current = null; }}
      onKeyDown={event => { const current = introPane.current?.getBoundingClientRect().height ?? 120; if (event.key === 'ArrowUp' || event.key === 'ArrowDown') { event.preventDefault(); setIntroHeight(clampIntro(current + (event.key === 'ArrowDown' ? 24 : -24))); } else if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); setIntroHeight(event.key === 'Home' ? 120 : introMaximum); } }}><span aria-hidden="true"/></div>
      </div>
      </div>
    </section>
    {error && <p role="alert" className="error">{error}</p>}
    <section className="pool workspace-pane strategies-pane" aria-labelledby="pool-heading">
      <header className="pool-heading workspace-pane-heading strategies-pane-heading">
        <h2 id="pool-heading" tabIndex={-1}><button type="button" className="workspace-section-disclosure" aria-expanded={strategiesExpanded} aria-controls="strategies-pane-content" onClick={toggleStrategiesPane}><DisclosureChevron expanded={strategiesExpanded}/>Strategies</button></h2>
        <div className="strategies-heading-right">
          <StrategyCreationActions buttonRef={newButton} hideNew={generating} disabled={activeMode !== null || generating || closing || ordering || !!dragId} onManual={startNewStrategy} onAI={startGeneration}/>
          <p className="section-count">{strategies.length} strateg{strategies.length === 1 ? 'y' : 'ies'}</p>
          <ProcessControlsView controls={processControls} disabled={activeMode !== null || closing || ordering || !!dragId}/>
        </div>
      </header>
      <div id="strategies-pane-content" hidden={!strategiesExpanded}>
      <p className="sr-only" role="status">{announcement}</p>
      <div id="strategy-composer">{editing && <NewStrategy initialDraft={manualDraft} path={view.path} onCancel={cancel} onSaved={next => {
        const strategy = next.project.strategies[next.project.strategies.length - 1];
        setView(next); setEditing(false); exitMode('new-strategy'); setAnnouncement(`Strategy saved: ${strategy.title}`);
        setFocusStrategy(strategy.id);
      }}/>}
      {generating && <GenerateStrategy path={view.path} projectId={view.project.id} sourceGuard={JSON.stringify({ project_id: project.id, problem: project.problem, strategies: project.strategies.map(item => [item.id, item.title, item.approach, item.removed_at]) })} onCancel={() => { setGenerating(false); requestAnimationFrame(() => newButton.current?.focus()); }} onSaved={next => {
        const strategy = next.project.strategies.at(-1)!; setView(next); setGenerating(false); setFocusStrategy(strategy.id); setAnnouncement('AI-assisted strategy accepted and saved.');
      }}/>}</div>
      {strategies.length ? <div className="strategies-table">
        <div className="strategy-columns" aria-hidden="true"><span>Strategy</span><span>Stage</span></div>
        <ol className="strategy-list" aria-label="Strategies" aria-busy={ordering}>
        {strategies.map(strategy => <li className={`strategy-row${dragId === strategy.id ? ' is-lifted' : ''}`} key={strategy.id} data-strategy-id={strategy.id}>
          <div className="strategy-row-main">
            <StrategyTitleEditor strategy={strategy} path={view.path} onSaved={setView} modeDisabled={activeMode !== null && activeMode !== `strategy-title-${strategy.id}`} onEnterMode={() => enterMode(`strategy-title-${strategy.id}`)} onExitMode={() => exitMode(`strategy-title-${strategy.id}`)} expanded={!collapsedStrategies.has(strategy.id)} onToggle={() => setCollapsedStrategies(current => { const next = new Set(current); if (next.has(strategy.id)) next.delete(strategy.id); else next.add(strategy.id); return next; })} commands={<StrategyCommands strategy={strategy} disabled={activeMode !== null} onCommand={(mode, strategy) => { if (ordering || dragId || activeMode !== null) return; if (mode === 'fork') { if (!enterMode('new-strategy')) return; expandStrategies(); setManualDraft({ title: `${strategy.title} (forked)`, approach: strategy.approach, summary: strategy.summary }); setEditing(true); requestAnimationFrame(() => document.getElementById('strategy-composer')?.scrollIntoView({ block: 'nearest' })); } else setCommand({ mode, strategy }); }}/>} />
            <div id={`strategy-content-${strategy.id}`} className="strategy-expanded" hidden={collapsedStrategies.has(strategy.id)}><TextViews mathematical={project.investigation_type === 'mathematical'} path={view.path} scope="strategy" strategyId={strategy.id} source={strategy.approach} contentClass="strategy-approach" onSaved={setView} modeDisabled={activeMode !== null && activeMode !== `text-strategy-${strategy.id}`} onEnterMode={() => enterMode(`text-strategy-${strategy.id}`)} onExitMode={() => exitMode(`text-strategy-${strategy.id}`)}/></div>
          </div>
          <span className={`stage-label stage-${strategy.stage}`} title="Manually tracked; no strategy runner"><i aria-hidden="true"/>{stageLabels[strategy.stage]}</span>
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
    <ResearchWorkspace path={view.path} projectId={project.id} strategies={strategies} onViewStrategy={showStrategy} onControlsChange={setProcessControls}/>
    {projectEditing && <ProjectSettingsDialog initial={view} onCancel={() => { setProjectEditing(false); exitMode('project-settings'); requestAnimationFrame(() => editProjectButton.current?.focus()); }} onSaved={next => { setView(next); setProjectEditing(false); exitMode('project-settings'); setAnnouncement('Project settings saved.'); requestAnimationFrame(() => editProjectButton.current?.focus()); }}/>}
    {downloadOpen && <DownloadProjectDialog path={view.path} title={project.title} onCancel={() => { setDownloadOpen(false); requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.project-pane-actions [aria-label="Download project"]')?.focus()); }}/>}
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
