import { useEffect, useRef, useState } from 'react';
import './style.css';
import RenderedMarkdown from './RenderedMarkdown';
import { projectTranscript, groupTranscriptTurns, transcriptCategories, type TranscriptIntervention, type TranscriptRole } from './session-transcript';
import './session-transcript.css';

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
  return error instanceof Error ? error.message : 'The session transcript could not be loaded.';
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
  const [enabledCategories, setEnabledCategories] = useState<TranscriptRole[]>(transcriptCategories.map(category => category.value));
  const [interventions, setInterventions] = useState<TranscriptIntervention[]>([]);
  const [expandedEntries, setExpandedEntries] = useState<Record<string, boolean>>({});
  const [renderMarkdown, setRenderMarkdown] = useState(false);
  const [following, setFollowing] = useState(true);
  const [jumpVisible, setJumpVisible] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [error, setError] = useState('');
  const [copyError, setCopyError] = useState('');
  const [copyState, setCopyState] = useState<'idle' | 'copying' | 'copied'>('idle');
  const copyTimer = useRef<number | null>(null);
  const [referencePreparation, setReferencePreparation] = useState<ReferencePreparation | null>(null);
  const list = useRef<HTMLOListElement>(null);
  const downloadUrl = `/api/projects/research-sessions/${encodeURIComponent(sessionId)}/log/download?${new URLSearchParams({ path, format: 'transcript' })}`;
  const copyLog = async () => {
    if (copyState === 'copying') return;
    if (copyTimer.current !== null) { window.clearTimeout(copyTimer.current); copyTimer.current = null; }
    setCopyState('copying');
    setCopyError('');
    try {
      // Never copy the filtered or incrementally loaded preview. Download and
      // Copy fetch the exact same full, current server-rendered export.
      const response = await fetch(downloadUrl, { credentials: 'same-origin', cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } });
      if (!response.ok) throw new Error('Could not fetch the complete session transcript.');
      await navigator.clipboard.writeText(await response.text());
      setCopyState('copied');
      if (copyTimer.current !== null) window.clearTimeout(copyTimer.current);
      copyTimer.current = window.setTimeout(() => { setCopyState('idle'); copyTimer.current = null; }, 1600);
    } catch {
      setCopyState('idle');
      setCopyError('Could not copy the session transcript. Check clipboard permissions and try again.');
    }
  };
  useEffect(() => () => { if (copyTimer.current !== null) window.clearTimeout(copyTimer.current); }, []);
  useEffect(() => {
    if (!sessionId || !path) { setError('Session transcript link is incomplete.'); return; }
    let alive = true;
    let timer = 0;
    let fetching = false;
    const refresh = async () => {
      if (!alive || fetching) return;
      fetching = true;
      try {
        const query = new URLSearchParams({ path, after: String(cursor.current) });
        const response = await fetch(`/api/projects/research-sessions/${encodeURIComponent(sessionId)}/log?${query}`, { credentials: 'same-origin', headers: { 'X-Sigma-Error-Handled': 'true' } });
        if (!response.ok) throw new Error(response.status === 401 ? 'Sign in to view this session transcript.' : 'This session transcript is unavailable or access was denied.');
        const data = await response.json() as { events: SessionLogEvent[]; cursor: number; short_name: string; project_title: string; session: SessionState; reference_preparation?: ReferencePreparation; interventions?: TranscriptIntervention[] };
        if (!alive) return;
        const fresh = data.events.filter(event => !seen.current.has(event.seq));
        fresh.forEach(event => seen.current.add(event.seq));
        if (fresh.length) setEvents(current => [...current, ...fresh]);
        cursor.current = Math.max(cursor.current, data.cursor);
        setShortName(data.short_name); setProjectTitle(data.project_title); setSession(data.session); setReferencePreparation(data.reference_preparation ?? null); setInterventions(data.interventions ?? []); setError('');
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
  useEffect(() => { if (following && list.current) list.current.scrollTop = 0; }, [events, following]);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  const compilationLabel = referencePreparation?.compiler.status === 'completed' ? 'succeeded' : ['fallback', 'interrupted', 'failed'].includes(referencePreparation?.compiler.status ?? '') ? 'failed/degraded' : referencePreparation?.compiler.status ?? 'unknown/not recorded';
  const shownGroups = groupTranscriptTurns(
    projectTranscript(events, interventions).filter(entry => enabledCategories.includes(entry.role)),
  );
  const allSelected = enabledCategories.length === transcriptCategories.length;
  const toggleCategory = (category: TranscriptRole) => {
    setEnabledCategories(current => current.includes(category)
      ? current.filter(value => value !== category) : [...current, category]);
  };
  const updateScrollState = () => {
    const node = list.current;
    if (!node) return;
    const atLatest = node.scrollTop <= 24;
    setJumpVisible(!atLatest);
    setFollowing(atLatest);
  };
  const jumpToEnd = () => {
    const node = list.current;
    if (node) node.scrollTop = 0;
    setFollowing(true);
    setJumpVisible(false);
  };
  return <main className="session-log-page">
    <header><h1>{projectTitle || shortName}, Session {session?.number ?? '…'} — Transcript</h1>
      <p>Research conversation · {session?.status ?? 'loading'}</p>
      <div className="session-log-toolbar session-transcript-toolbar">
        <fieldset className="session-transcript-filters">
          <legend><button type="button" className="text-view-link session-transcript-toggle-all"
            onClick={() => setEnabledCategories(allSelected ? [] : transcriptCategories.map(category => category.value))}
            aria-label={allSelected ? 'Deselect all transcript categories' : 'Select all transcript categories'}>Show</button></legend>
          {transcriptCategories.map(category => <label key={category.value}>
            <input type="checkbox" checked={enabledCategories.includes(category.value)}
              onChange={() => toggleCategory(category.value)}/>{category.label}
          </label>)}
        </fieldset>
        {jumpVisible && <button className="session-log-secondary-action" type="button" onClick={jumpToEnd}>Jump to latest</button>}
        <button type="button"
          className={`sigma-render-toggle sigma-unified-markdown workspace-icon-button${renderMarkdown ? ' sigma-render-active' : ''}`}
          aria-label={renderMarkdown ? 'Show plain transcript' : 'Render transcript as Markdown'}
          aria-pressed={renderMarkdown}
          data-tooltip={renderMarkdown ? 'Show plain text' : 'Render as Markdown'}
          onClick={() => setRenderMarkdown(current => !current)}>
          <svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none"
            xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z"
              fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg>
        </button>
        <button type="button" className="session-log-toolbar-icon workspace-icon-button text-copy-button"
          aria-label="Copy transcript to clipboard" data-tooltip={copyState === 'copied' ? 'Copied' : 'Copy transcript to clipboard'}
          disabled={copyState === 'copying'} onClick={() => { void copyLog(); }}>
          {copyState === 'copied'
            ? <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 4 4L19 6"/></svg>
            : <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2h3"/></svg>}</button>
        <a className="session-log-toolbar-icon workspace-icon-button session-log-download" href={downloadUrl}
          aria-label="Download session transcript" data-tooltip="Download session transcript"><svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg></a>
    </div></header>
    {copyState === 'copied' && <p role="status" className="session-log-copy-status">Copied transcript to clipboard.</p>}
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
    <ol ref={list} onScroll={updateScrollState} className="session-log-events session-transcript-events" aria-live="polite">
      {shownGroups.map(group => <li key={group.key} className="session-transcript-turn">
        <header className="session-transcript-turn-heading">
          <strong>{group.label}</strong>
          {group.entries.find(entry => entry.strategyId)?.strategyId &&
            <span>Strategy {group.entries.find(entry => entry.strategyId)?.strategyId}</span>}
          <time dateTime={group.latestTimestamp}>{new Date(group.latestTimestamp).toLocaleString()}</time>
        </header>
        <ol className="session-transcript-turn-entries">
          {group.entries.map(entry => {
            const expanded = expandedEntries[entry.id] ?? entry.role !== 'other';
            return <li key={entry.id} className={'session-transcript-entry chat-history-entry chat-history-' + entry.role}>
              <div className="session-transcript-entry-heading">
                <button type="button" className="chat-disclosure-button" aria-expanded={expanded}
                  aria-controls={'transcript-entry-' + entry.id}
                  onClick={() => setExpandedEntries(current => ({ ...current, [entry.id]: !expanded }))}>
                  <svg aria-hidden="true" className={'disclosure-chevron' + (expanded ? ' is-expanded' : '')} viewBox="0 0 12 12">
                    <path d="m4 2 4 4-4 4"/>
                  </svg>
                  <strong>{entry.title}</strong>
                </button>
                <time dateTime={entry.timestamp}>{new Date(entry.timestamp).toLocaleString()}</time>
              </div>
              <div id={'transcript-entry-' + entry.id} hidden={!expanded}>
                {renderMarkdown
                  ? <div className="session-transcript-markdown"><RenderedMarkdown body={entry.text}/></div>
                  : <pre className="session-transcript-plain">{entry.text}</pre>}
                {entry.request !== undefined && <details className="session-transcript-provider-details">
                  <summary>Request and response details</summary>
                  <pre>{JSON.stringify(entry.request, null, 2)}</pre>
                  {entry.response !== undefined && <pre>{JSON.stringify(entry.response, null, 2)}</pre>}
                </details>}
              </div>
            </li>;
          })}
        </ol>
      </li>)}
    </ol>
  </main>;
}

