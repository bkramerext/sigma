import { useEffect, useRef, useState } from 'react';
import './style.css';

type SessionLogEvent = { seq: number; timestamp: string; type: string; request_id?: string; role?: string; round?: number; strategy_id?: string; step_id?: string; status?: string; [key: string]: unknown };
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
  const [session, setSession] = useState<{ number: number; status: string } | null>(null);
  const [shortName, setShortName] = useState('Research Project');
  const [filter, setFilter] = useState('all');
  const [following, setFollowing] = useState(true);
  const [now, setNow] = useState(() => Date.now());
  const [error, setError] = useState('');
  const list = useRef<HTMLOListElement>(null);
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
        const response = await fetch(`/api/projects/research-sessions/${encodeURIComponent(sessionId)}/log?${query}`, { credentials: 'same-origin' });
        if (!response.ok) throw new Error(response.status === 401 ? 'Sign in to view this session log.' : 'This session log is unavailable or access was denied.');
        const data = await response.json() as { events: SessionLogEvent[]; cursor: number; short_name: string; session: { number: number; status: string } };
        if (!alive) return;
        const fresh = data.events.filter(event => !seen.current.has(event.seq));
        fresh.forEach(event => seen.current.add(event.seq));
        if (fresh.length) setEvents(current => [...current, ...fresh]);
        cursor.current = Math.max(cursor.current, data.cursor);
        setShortName(data.short_name); setSession(data.session); setError('');
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
  }, [shortName, session]);
  useEffect(() => { if (following && list.current) list.current.scrollTop = list.current.scrollHeight; }, [events, following]);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
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
  return <main className="session-log-page" onWheel={() => setFollowing(false)} onTouchMove={() => setFollowing(false)}>
    <header><h1>{shortName}, Session {session?.number ?? '…'}</h1><p>Live provider traffic and operational events · {session?.status ?? 'loading'}</p><div><label>Show <select value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All events</option><option value="investigator">Investigator</option><option value="skeptic">Skeptic</option><option value="provider">Provider calls</option><option value="session_event">Session events</option></select></label> <button type="button" onClick={() => setFollowing(value => !value)}>{following ? 'Following' : 'Resume follow'}</button> <a href={`/api/projects/research-sessions/${encodeURIComponent(sessionId)}/log/download?${new URLSearchParams({ path })}`}>Download Log</a></div></header>
    {error && <p role="alert">{error}</p>}
    <ol ref={list} className="session-log-events" aria-live="polite">{shown.map(event => {
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

