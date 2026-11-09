import { useEffect, useRef, useState } from 'react';
import './style.css';
import SigmaSelect from './SigmaSelect';

type SessionLogEvent = { seq: number; timestamp: string; type: string; request_id?: string; role?: string; round?: number; strategy_id?: string; step_id?: string; status?: string; [key: string]: unknown };
type SessionState = { number: number; status: string; current_action?: string; termination_reason_code?: string; reason?: string; message?: string };
type ReferencePreparation = {
  selected_count: number | null;
  verified_count: number;
  references: { title: string; url: string; retrieval_status: string; reason?: string | null; http_status?: number | null; excerpt_present: boolean; excerpt_integrity?: boolean | null; content_hash_recorded?: boolean }[];
  compiler: { status: string; attempt_count: number; reason?: string | null; source_hash_match?: boolean | null; retrieved_excerpts_used: string; attempts: { number?: number; status?: string; failure_type?: string; http_status?: number | null; error_code?: string; validation_failure?: string; usage_status?: string; token_usage?: { input_tokens?: number; output_tokens?: number } | null; retry_decision?: string; reason?: string | null }[] };
  guidance_disposition: string;
  strategy_count?: number | null;
};
function displayError(error: unknown): string {
  return error instanceof Error ? error.message : 'The session log could not be loaded.';
}

export default function SessionLogPage() {
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get('session_log') ?? '';
  const path = params.get('path') ?? '';
  const [events, setEvents] = useState<SessionLogEvent[]>([]);
  const cursor = useRef(0);
  const seen = useRef(new Set<number>());
  const [session, setSession] = useState<SessionState | null>(null);
  const [shortName, setShortName] = useState('Research Project');
  const [projectTitle, setProjectTitle] = useState('');
  const [filter, setFilter] = useState('all');
  const [following, setFollowing] = useState(true);
  const [jumpVisible, setJumpVisible] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [error, setError] = useState('');
  const [copyError, setCopyError] = useState('');
  const [copyState, setCopyState] = useState<'idle' | 'copying' | 'copied'>('idle');
  const copyTimer = useRef<number | null>(null);
  const [referencePreparation, setReferencePreparation] = useState<ReferencePreparation | null>(null);
  const list = useRef<HTMLOListElement>(null);
  const downloadUrl = `/api/projects/research-sessions/${encodeURIComponent(sessionId)}/log/download?${new URLSearchParams({ path })}`;
  const copyLog = async () => {
    if (copyState === 'copying') return;
    if (copyTimer.current !== null) { window.clearTimeout(copyTimer.current); copyTimer.current = null; }
    setCopyState('copying');
    setCopyError('');
    try {
      // Never copy the filtered or incrementally loaded preview. Download and
      // Copy fetch the exact same full, current server-rendered export.
      const response = await fetch(downloadUrl, { credentials: 'same-origin', cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } });
      if (!response.ok) throw new Error('Could not fetch the complete session log.');
      await navigator.clipboard.writeText(await response.text());
      setCopyState('copied');
      if (copyTimer.current !== null) window.clearTimeout(copyTimer.current);
      copyTimer.current = window.setTimeout(() => { setCopyState('idle'); copyTimer.current = null; }, 1600);
    } catch {
      setCopyState('idle');
      setCopyError('Could not copy the session log. Check clipboard permissions and try again.');
    }
  };
  useEffect(() => () => { if (copyTimer.current !== null) window.clearTimeout(copyTimer.current); }, []);
  useEffect(() => {
    if (!sessionId || !path) { setError('Session log link is incomplete.'); return; }
    let alive = true;
    let timer = 0;
    let fetching = false;
    const refresh = async () => {
      if (!alive || fetching) return;
      fetching = true;
      try {
        const query = new URLSearchParams({ path, after: String(cursor.current) });
        const response = await fetch(`/api/projects/research-sessions/${encodeURIComponent(sessionId)}/log?${query}`, { credentials: 'same-origin', headers: { 'X-Sigma-Error-Handled': 'true' } });
        if (!response.ok) throw new Error(response.status === 401 ? 'Sign in to view this session log.' : 'This session log is unavailable or access was denied.');
        const data = await response.json() as { events: SessionLogEvent[]; cursor: number; short_name: string; project_title: string; session: SessionState; reference_preparation?: ReferencePreparation };
        if (!alive) return;
        const fresh = data.events.filter(event => !seen.current.has(event.seq));
        fresh.forEach(event => seen.current.add(event.seq));
        if (fresh.length) setEvents(current => [...current, ...fresh]);
        cursor.current = Math.max(cursor.current, data.cursor);
        setShortName(data.short_name); setProjectTitle(data.project_title); setSession(data.session); setReferencePreparation(data.reference_preparation ?? null); setError('');
      } catch (cause) { if (alive) setError(displayError(cause)); }
      finally {
        fetching = false;
        if (alive) timer = window.setTimeout(() => { void refresh(); }, 1000);
      }
    };
    void refresh();
    return () => { alive = false; window.clearTimeout(timer); };
  }, [sessionId, path]);
  useEffect(() => {
    if (!session) return;
    const title = `${shortName}, Session ${session.number}`;
    document.title = title;
  }, [projectTitle, shortName, session]);
  useEffect(() => { if (following && list.current) list.current.scrollTop = list.current.scrollHeight; }, [events, following]);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  const compilationLabel = referencePreparation?.compiler.status === 'completed' ? 'succeeded' : ['fallback', 'interrupted', 'failed'].includes(referencePreparation?.compiler.status ?? '') ? 'failed/degraded' : referencePreparation?.compiler.status ?? 'unknown/not recorded';
  const calls = new Map<string, SessionLogEvent>();
  for (const event of events) if (event.request_id && event.type === 'provider_response' || event.request_id && event.type === 'provider_failure') calls.set(event.request_id, event);
  const shown = events.filter(event => {
    if (['provider_response', 'provider_failure'].includes(event.type)) return false;
    if (filter === 'all') return true;
    if (filter === 'investigator' || filter === 'skeptic') return event.role === filter || event.type === 'provider_request' && event.role === filter;
    if (filter === 'provider') return event.type.startsWith('provider_');
    if (filter === 'session_event') return event.type === 'session_event';
    return event.type === filter;
  });
  const updateScrollState = () => {
    const node = list.current;
    if (!node) return;
    const atBottom = node.scrollHeight - node.clientHeight - node.scrollTop <= 24;
    setJumpVisible(!atBottom);
    if (atBottom) setFollowing(true);
    else setFollowing(false);
  };
  const jumpToEnd = () => {
    const node = list.current;
    if (node) node.scrollTop = node.scrollHeight;
    setFollowing(true);
    setJumpVisible(false);
  };
  return <main className="session-log-page">
    <header><h1>{projectTitle || shortName}, Session {session?.number ?? '…'}</h1><p>Live provider traffic and operational events · {session?.status ?? 'loading'}</p><div className="session-log-toolbar"><label className="session-log-show">Show <SigmaSelect ariaLabel="Show events" value={filter} onChange={setFilter}
      options={[{ value: 'all', label: 'All events' }, { value: 'investigator', label: 'Investigator' },
        { value: 'skeptic', label: 'Skeptic' }, { value: 'provider', label: 'Provider calls' },
        { value: 'session_event', label: 'Session events' }]}/></label> {jumpVisible && <button className="session-log-secondary-action" type="button" onClick={jumpToEnd}>Jump to end</button>}
      <button type="button" className="session-log-toolbar-icon workspace-icon-button text-copy-button" aria-label="Copy log to clipboard" data-tooltip={copyState === 'copied' ? 'Copied log to clipboard' : 'Copy log to clipboard'} data-tooltip={copyState === 'copied' ? 'Copied' : 'Copy log to clipboard'} disabled={copyState === 'copying'} onClick={() => { void copyLog(); }}>{copyState === 'copied' ? <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 4 4L19 6"/></svg> : <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>}</button>
      <a className="session-log-toolbar-icon workspace-icon-button session-log-download" href={downloadUrl} aria-label="Download session log" data-tooltip="Download session log" data-tooltip="Download session log"><svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg></a>
    </div></header>
    {copyState === 'copied' && <p role="status" className="session-log-copy-status">Copied log to clipboard.</p>}
    {copyError && <p role="alert" className="session-log-copy-error">{copyError}</p>}
    {error && <p role="alert">{error}</p>}
    {session && ['paused', 'stopped', 'failed', 'ended', 'completed'].includes(session.status) && <section aria-label="Saved session status" className="session-log-reference-summary">
      <p><strong>Status:</strong> {session.status} · <strong>Stage:</strong> {session.current_action || 'not recorded'} · <strong>Reason code:</strong> {session.termination_reason_code || 'not recorded'}</p>
      <p>{session.reason || session.message || 'No stop reason recorded.'}</p>
    </section>}
    {referencePreparation && <section className={`session-log-reference-summary${['fallback', 'interrupted', 'failed', 'skipped', 'disabled'].includes(referencePreparation.compiler.status) || referencePreparation.compiler.source_hash_match === false || referencePreparation.references.some(ref => ref.retrieval_status !== 'retrieved' || ref.excerpt_integrity !== true) ? ' session-log-reference-degraded' : ''}`} aria-label="Research reference preparation">
      <p><strong>Research references:</strong> {referencePreparation.selected_count ?? 'unknown/not recorded'} selected · {referencePreparation.verified_count} retrieved with verified excerpts · Compilation {compilationLabel} ({referencePreparation.compiler.attempt_count}/3 attempts) · {referencePreparation.guidance_disposition}</p>
      {referencePreparation.selected_count !== null && referencePreparation.verified_count < referencePreparation.selected_count && <p className="session-log-reference-warning" role="alert">Some selected methodology references were not retrieved with verified excerpts.</p>}
      {referencePreparation.compiler.reason && referencePreparation.compiler.status !== 'completed' && <p className="session-log-reference-warning" role="alert">{referencePreparation.compiler.reason}</p>}
      <details><summary>Reference sources and compilation diagnostics</summary>
        <ul>{referencePreparation.references.map((ref, index) => <li key={index}>
          <strong>{ref.title}</strong> · {/^https?:\/\//.test(ref.url) ? <a href={ref.url} target="_blank" rel="noopener noreferrer">{ref.url}</a> : (ref.url || 'URL unknown/not recorded')}
          <div>Retrieval: {ref.retrieval_status} · HTTP {ref.http_status ?? 'unknown/not recorded'} · Reason: {ref.reason ?? 'none recorded'} · Excerpt: {ref.excerpt_present ? 'present' : 'absent'} · Excerpt integrity: {ref.excerpt_integrity === true ? 'verified' : ref.excerpt_integrity === false ? 'invalid/missing hash' : 'unknown/not recorded'}</div>
        </li>)}</ul>
        <p>Compiler used retrieved excerpts: {referencePreparation.compiler.retrieved_excerpts_used}.</p>
        {referencePreparation.compiler.source_hash_match === false && <p role="alert" className="session-log-reference-warning">Compiled source snapshot hash mismatch.</p>}
        <ol>{referencePreparation.compiler.attempts.map((attempt, index) => <li key={index}>Attempt {attempt.number ?? index + 1}: {attempt.status ?? 'unknown'} · HTTP {attempt.http_status ?? 'unknown/not recorded'} · Code {attempt.error_code ?? 'unknown/not recorded'} · Failure {attempt.failure_type ?? 'none'} · Validation {attempt.validation_failure ?? 'none'} · Usage {attempt.usage_status ?? 'unknown/not recorded'}{attempt.token_usage ? ` (${attempt.token_usage.input_tokens ?? '?'} input / ${attempt.token_usage.output_tokens ?? '?'} output tokens)` : ''} · Retry {attempt.retry_decision ?? 'unknown/not recorded'}{attempt.reason && <div>{attempt.reason}</div>}</li>)}</ol>
      </details>
    </section>}
    <ol ref={list} onScroll={updateScrollState} className="session-log-events" aria-live="polite">{shown.map(event => {
      const paired = event.request_id ? calls.get(event.request_id) : undefined;
      if (event.type === 'provider_request') {
        const elapsed = Math.max(0, Math.floor((now - Date.parse(event.timestamp)) / 1000));
        const duration = typeof paired?.duration_seconds === 'number' ? `${paired.duration_seconds}s` : `in flight · ${elapsed}s`;
        return <li key={`call-${event.request_id}`}><details><summary><time>{new Date(event.timestamp).toLocaleTimeString()}</time> · Round {String(event.round ?? '—')} · {String(event.role ?? 'Agent')} · {String(event.status ?? 'request')} · {duration} · {event.request_id}</summary><h2>Sent request</h2>{Array.isArray(event.peer_evidence_available) && event.peer_evidence_available.length > 0 && <p>Cross-strategy evidence available: {event.peer_evidence_available.join(', ')}. Included in this actual request: {Array.isArray(event.peer_evidence_in_actual_request) ? event.peer_evidence_in_actual_request.join(', ') || 'none' : 'not recorded'}.</p>}<pre>{JSON.stringify(event.request, null, 2)}</pre>{paired ? <><h2>{paired.type === 'provider_failure' ? 'Failure' : 'Provider response'}</h2><p>Response received <time>{new Date(paired.timestamp).toLocaleTimeString()}</time></p><pre>{JSON.stringify(paired.type === 'provider_failure' ? paired.provider_error : paired.response, null, 2)}</pre>{typeof paired.response_wire === 'string' && <details><summary>Raw provider response</summary><pre>{paired.response_wire}</pre></details>}<p>Model {String(event.model ?? 'unknown')} · {String(paired.duration_seconds ?? '—')}s · Usage {JSON.stringify(paired.usage ?? {})} · Estimated cost ${String(paired.estimated_cost_usd ?? 'unavailable')}</p></> : <p>Waiting for provider response…</p>}</details></li>;
      }
      if (event.request_id) return null;
      const eventText = event.type === 'cross_strategy_artifact_availability'
        ? `${String(event.source_artifact_id ?? 'Artifact')} from ${String(event.source_strategy_id ?? 'a strategy')} is ${String(event.availability ?? 'available')} for ${String(event.target_strategy_id ?? 'the receiving strategy')}.`
        : `${String(event.event_kind ?? event.type)}: ${String(event.message ?? event.status ?? '')}`;
      return <li key={`event-${event.seq}`}><time>{new Date(event.timestamp).toLocaleTimeString()}</time> · {eventText}</li>;
    })}</ol>
  </main>;
}

