import { useEffect, useMemo, useRef, useState } from 'react';
import './style.css';
import RenderedMarkdown from './RenderedMarkdown';
import { projectTranscript, groupTranscriptTurns, paginateTranscriptTurns, transcriptDefaultExpanded, convertibleTranscriptEntry, supervisorDisplay, transcriptRoleLabel, formatTranscriptMarkdown, type TranscriptIntervention, type TranscriptEntry, type TranscriptSavedStep } from './session-transcript';
import './session-transcript.css';

type SessionLogEvent = { seq: number; timestamp: string; type: string; request_id?: string; role?: string; round?: number; strategy_id?: string; step_id?: string; status?: string; [key: string]: unknown };
export type SessionState = { number: number; status: string; session_settings?: { brainstorm_mode?: boolean; name?: string }; current_action?: string; termination_reason_code?: string; reason?: string; message?: string };
function displayError(error: unknown): string {
  return error instanceof Error ? error.message : 'The session transcript could not be loaded.';
}

function CopyTranscriptEntryButton({ title, text }: { title: string; text: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current !== null) window.clearTimeout(timer.current); }, []);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (timer.current !== null) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => { setCopied(false); timer.current = null; }, 1600);
    } catch { setCopied(false); }
  };
  return <button type="button" className="session-transcript-entry-copy"
    aria-label={copied ? `Copied ${title}` : `Copy ${title}`}
    data-tooltip={copied ? 'Copied' : ['Investigator', 'Skeptic'].includes(title) ? 'Copy text' : `Copy ${title}`} disabled={!text} onClick={() => { void copy(); }}>
    {copied
      ? <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 4 4L19 6"/></svg>
      : <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>}
  </button>;
}

export default function SessionLogPage({ onSessionChange, resetSignal = 0 }: { onSessionChange?: (session: SessionState) => void; resetSignal?: number }) {
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get('session_log') ?? '';
  const path = params.get('path') ?? '';
  // The key makes state, cursor, selected Markdown rows and async work
  // session-local even when navigation reuses this route.
  return <SessionLogContent key={JSON.stringify([path, sessionId])}
    path={path} sessionId={sessionId} onSessionChange={onSessionChange} resetSignal={resetSignal}/>;
}

function SessionLogContent({ path, sessionId, onSessionChange, resetSignal }: {
  path: string; sessionId: string; onSessionChange?: (session: SessionState) => void; resetSignal: number;
}) {
  const [events, setEvents] = useState<SessionLogEvent[]>([]);
  const cursor = useRef(0);
  const seen = useRef(new Set<number>());
  const stateVersion = useRef('');
  const [savedSteps, setSavedSteps] = useState<TranscriptSavedStep[]>([]);
  const [session, setSession] = useState<SessionState | null>(null);
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);
  const [shortName, setShortName] = useState('Research Project');
  const [projectTitle, setProjectTitle] = useState('');
  const [projectId, setProjectId] = useState('');
  const [interventions, setInterventions] = useState<TranscriptIntervention[]>([]);
  const [expandedEntries, setExpandedEntries] = useState<Record<string, boolean>>({});
  // The Session title is the sole reset control for canonical expansion.
  useEffect(() => { setExpandedEntries({}); }, [resetSignal]);
  const [markdownEntries, setMarkdownEntries] = useState<Set<string>>(() => new Set());
  const [seenMarkdownEntries, setSeenMarkdownEntries] = useState<Set<string>>(() => new Set());
  const [formattedEntries, setFormattedEntries] = useState<Record<string, { source: string; body: string }>>({});
  const formattedEntriesRef = useRef<Record<string, { source: string; body: string }>>({});
  const conversionQueue = useRef<TranscriptEntry[]>([]);
  const conversionQueued = useRef(new Set<string>());
  const conversionWorker = useRef(false);
  const conversionAbort = useRef<AbortController | null>(null);
  const markdownEnabled = useRef(false);
  const selectedMarkdownEntries = useRef(new Set<string>());
  const [, setMarkdownError] = useState('');
  const [, setError] = useState('');
  const list = useRef<HTMLOListElement>(null);
  const [visibleTurnCount, setVisibleTurnCount] = useState(20);
  const entries = useMemo(() => projectTranscript(events, interventions, savedSteps, session?.status),
    [events, interventions, savedSteps, session?.status]);
  const convertibleEntries = useRef(new Map<string, string>());
  useEffect(() => {
    convertibleEntries.current = new Map(entries.filter(convertibleTranscriptEntry)
      .map(entry => [entry.id, entry.text]));
  }, [entries]);
  useEffect(() => {
    if (!sessionId || !path) { setError('Session transcript link is incomplete.'); return; }
    cursor.current = 0;
    seen.current.clear();
    stateVersion.current = '';
    setEvents([]);
    setSavedSteps([]);
    setInterventions([]);
    setSession(null);
    setInitialLoadComplete(false);
    let alive = true;
    let timer = 0;
    let fetching = false;
    let delay = 1000;
    const controller = new AbortController();
    const refresh = async () => {
      if (!alive || fetching) return;
      fetching = true;
      try {
        const query = new URLSearchParams({
          path, after: String(cursor.current), state_version: stateVersion.current,
        });
        const response = await fetch(`/api/projects/research-sessions/${encodeURIComponent(sessionId)}/log?${query}`, { credentials: 'same-origin', signal: controller.signal, headers: { 'X-Sigma-Error-Handled': 'true' } });
        if (!response.ok) throw new Error(response.status === 401 ? 'Sign in to view this session transcript.' : 'This session transcript is unavailable or access was denied.');
        const data = await response.json() as { events: SessionLogEvent[]; cursor: number; short_name: string; project_title: string; project_id?: string; session: SessionState; interventions?: TranscriptIntervention[];
          transcript_state?: TranscriptSavedStep[]; transcript_state_version?: string };
        if (!alive) return;
        const fresh = data.events.filter(event => !seen.current.has(event.seq));
        fresh.forEach(event => seen.current.add(event.seq));
        if (fresh.length) setEvents(current => [...current, ...fresh]);
        cursor.current = Math.max(cursor.current, data.cursor);
        if (data.transcript_state !== undefined) setSavedSteps(data.transcript_state);
        if (data.transcript_state_version !== undefined) stateVersion.current = data.transcript_state_version;
        setShortName(data.short_name); setProjectTitle(data.project_title); if (data.project_id) setProjectId(data.project_id); setSession(data.session); onSessionChange?.(data.session);
        const nextInterventions = data.interventions ?? [];
        setInterventions(current => JSON.stringify(current) === JSON.stringify(nextInterventions) ? current : nextInterventions);
        delay = ['running', 'queued'].includes(data.session.status) ? 1000 : 5000;
        setError(''); setInitialLoadComplete(true);
      } catch (cause) { if (alive) { setError(displayError(cause)); setInitialLoadComplete(true); } }
      finally {
        fetching = false;
        if (alive) timer = window.setTimeout(() => { void refresh(); }, delay);
      }
    };
    void refresh();
    return () => { alive = false; controller.abort(); window.clearTimeout(timer); };
  }, [sessionId, path]);
  useEffect(() => {
    if (!session) return;
    const title = `${shortName}, Session ${session.number}`;
    document.title = title;
  }, [projectTitle, shortName, session]);
  // Queue formatting only after a transcript row has entered the scroll viewport.
  // A long historical transcript must not trigger hundreds of paid conversions
  // merely because the user enabled Markdown.
  useEffect(() => {
    if (!markdownEntries.size || !list.current || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(changes => {
      const newlySeen = changes.filter(change => change.isIntersecting);
      if (!newlySeen.length) return;
      setSeenMarkdownEntries(current => {
        const next = new Set(current);
        for (const change of newlySeen) {
          const id = change.target.getAttribute('data-transcript-entry');
          if (id) next.add(id);
        }
        return next.size === current.size ? current : next;
      });
    }, { root: null });
    list.current.querySelectorAll('[data-transcript-entry]').forEach(node => observer.observe(node));
    return () => observer.disconnect();
  }, [markdownEntries, events, expandedEntries, visibleTurnCount]);

  // The existing Markdown action formats saved provider text with the same
  // metered converter as other SIGMA research blocks. The original transcript
  // and Copy/Download remain byte-for-byte unchanged. Only accepted, visible
  // transcript content is queued; never send arbitrary browser-authored text.
  useEffect(() => {
    if (!markdownEntries.size || !projectId) return;
    const eligible = entries.filter(entry =>
      markdownEntries.has(entry.id) &&
      seenMarkdownEntries.has(entry.id) &&
      entry.role !== 'other' &&
      (expandedEntries[entry.id] ?? transcriptDefaultExpanded(entry)) &&
      convertibleTranscriptEntry(entry));
    for (const entry of eligible) {
      if (formattedEntriesRef.current[entry.id]?.source === entry.text || conversionQueued.current.has(entry.id)) continue;
      conversionQueued.current.add(entry.id);
      conversionQueue.current.push(entry);
    }
    if (conversionWorker.current || !conversionQueue.current.length) return;
    conversionWorker.current = true;
    const drain = async () => {
      try {
        while (conversionQueue.current.length && markdownEnabled.current) {
          const entry = conversionQueue.current.shift()!;
          // An entry may have been deselected while another paid conversion ran.
          // Do not dispatch formatting for a row the user has switched off.
          if (!selectedMarkdownEntries.current.has(entry.id)
            || convertibleEntries.current.get(entry.id) !== entry.text) {
            conversionQueued.current.delete(entry.id);
            continue;
          }
          const controller = new AbortController();
          conversionAbort.current = controller;
          try {
            const settingsResponse = await fetch(
              `/api/projects/proposals/config?${new URLSearchParams({ path, purpose: 'markdown' })}`,
              { signal: controller.signal, cache: 'no-store' },
            );
            const settings = await settingsResponse.json();
            if (!settingsResponse.ok || !settings.available || !settings.binding)
              throw new Error(settings.message ?? 'Markdown formatting is unavailable.');
            if (controller.signal.aborted || !selectedMarkdownEntries.current.has(entry.id)
              || convertibleEntries.current.get(entry.id) !== entry.text) continue;
            const response = await fetch('/api/projects/text/convert', {
              method: 'POST', signal: controller.signal,
              headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
              body: JSON.stringify({
                path, scope: 'session-transcript', session_id: sessionId,
                field_path: `event.${entry.sequence}`, target: 'markdown',
                expected_digest: 'server-snapshot',
                expected_project_id: projectId, expected_binding: settings.binding,
              }),
            });
            const result = await response.json();
            if (!response.ok || typeof result.body !== 'string')
              throw new Error(result.error ?? result.detail ?? 'Transcript Markdown formatting failed.');
            if (!controller.signal.aborted && markdownEnabled.current
              && convertibleEntries.current.get(entry.id) === entry.text
              && selectedMarkdownEntries.current.has(entry.id)) {
              const next = { ...formattedEntriesRef.current, [entry.id]: { source: entry.text, body: result.body } };
              formattedEntriesRef.current = next;
              setFormattedEntries(next);
              setMarkdownError('');
            }
          } catch (cause) {
            if (!controller.signal.aborted) {
              setMarkdownError(displayError(cause));
              conversionQueue.current = [];
              break;
            }
          } finally {
            if (conversionAbort.current === controller) conversionAbort.current = null;
          }
        }
      } finally {
        conversionWorker.current = false;
      }
    };
    void drain();
  }, [markdownEntries, entries, projectId, path, sessionId, expandedEntries, seenMarkdownEntries]);

  const toggleEntryMarkdown = (entry: TranscriptEntry) => {
    const next = new Set(markdownEntries);
    if (next.has(entry.id)) next.delete(entry.id);
    else {
      next.add(entry.id);
      setExpandedEntries(current => ({ ...current, [entry.id]: true }));
    }
    markdownEnabled.current = next.size > 0;
    selectedMarkdownEntries.current = next;
    setMarkdownEntries(next);
    if (!next.size) {
      conversionAbort.current?.abort();
      conversionQueue.current = [];
      conversionQueued.current = new Set(Object.keys(formattedEntriesRef.current));
      setSeenMarkdownEntries(new Set());
      setMarkdownError('');
    }
  };
  useEffect(() => () => {
    markdownEnabled.current = false;
    selectedMarkdownEntries.current.clear();
    convertibleEntries.current.clear();
    conversionQueue.current = [];
    conversionAbort.current?.abort();
  }, []);
  const allGroups = useMemo(() => groupTranscriptTurns(entries
    .filter(entry => entry.role !== 'other' || entry.historyNotice || entry.correlationUnknown
      || entry.title.startsWith('Raw response') || entry.title.startsWith('Provider '))), [entries]);
  const { shownGroups, remainingTurns } = paginateTranscriptTurns(allGroups, visibleTurnCount);
  const activeTurnKey = ['running', 'queued'].includes(session?.status ?? '')
    ? allGroups.find(group => group.entries.some(entry => !entry.correlationUnknown && typeof entry.round === 'number' && entry.round > 0))?.key
    : undefined;
  const strategyIds = [...new Set(allGroups.flatMap(group =>
    group.entries.filter(entry => !entry.correlationUnknown).map(entry => entry.strategyId).filter((id): id is string => !!id)))].sort();
  const strategySuffix = (group: (typeof allGroups)[number]) => {
    const id = group.entries.find(entry => !entry.correlationUnknown && entry.strategyId)?.strategyId;
    return id ? ` · Strategy ${strategyIds.indexOf(id) + 1}` : '';
  };
  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return Number.isNaN(date.getTime()) ? timestamp : new Intl.DateTimeFormat(undefined, {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit',
    }).format(date);
  };
  const entryName = (entry: TranscriptEntry): string => {
    const roleLabel = transcriptRoleLabel(entry.role, entry.brainstormMode === true);
    const needsLabel = entry.reconstructed || (!entry.pending &&
      (entry.title.startsWith('Provider ') || entry.title.startsWith('Raw ')
        || entry.title === 'Response not retained' || entry.title === 'Accepted response'));
    const name = roleLabel && needsLabel ? `${roleLabel} · ${entry.title}` : roleLabel || entry.title;
    if (entry.reconstructed && !entry.timestamp) return name + ' · Time unavailable';
    if (!entry.reconstructed && (entry.correlationUnknown || entry.title.startsWith('Provider ')
      || entry.title.startsWith('Raw ') || entry.title === 'Response not retained')) {
      return name + ` · Raw #${entry.sequence}`
        + (entry.requestSequence !== undefined ? ` · Request #${entry.requestSequence}` : '');
    }
    return name;
  };
  if (!initialLoadComplete) return <main className="session-log-page session-conversation-page"><div className="workspace-state project-opening-state session-opening-state" role="status" aria-live="polite"><p className="intro">Opening session…</p></div></main>;
  return <main className="session-log-page session-conversation-page">
    {!session && <div className="workspace-state project-opening-state session-opening-state" role="alert"><p className="error">Session unavailable. The transcript could not be loaded.</p></div>}
    <section className="session-transcript-conversation" aria-label="Transcript">
      <ol id="session-transcript-history" ref={list} className="session-log-events session-transcript-events"
        aria-label="Conversation history">
        {shownGroups.map(group => <li key={group.key} className={"session-transcript-turn" + (group.entries.some(entry => entry.brainstormMode === true && (entry.role === "investigator" || entry.role === "skeptic")) ? " is-brainstorm-turn" : "")}>
          <h3 className="session-transcript-turn-heading">
            <span>{group.label}{strategySuffix(group)}{group.latestTimestamp && <> · <time dateTime={group.latestTimestamp}>{formatTimestamp(group.latestTimestamp)}</time></>}</span>
            {group.key === activeTurnKey && <a
              className="research-running-indicator-frame session-transcript-current-turn"
              href={`/project?${new URLSearchParams({ path, reveal_session: sessionId })}`}
              aria-label="Show session in project" data-tooltip="Show session in project"
              onClick={event => {
                if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                event.preventDefault();
                window.history.pushState(null, '', event.currentTarget.href);
                window.dispatchEvent(new PopStateEvent('popstate'));
              }}>
              <span className="research-running-indicator"/>
            </a>}
          </h3>
          <ol className="session-transcript-turn-entries">
            {group.entries.map(entry => {
              const expanded = expandedEntries[entry.id] ?? transcriptDefaultExpanded(entry);
              const name = entryName(entry);
              const asMarkdown = markdownEntries.has(entry.id);
              const supervisor = entry.role === 'supervisor' ? supervisorDisplay(entry.text) : null;
              const formatted = formattedEntries[entry.id]?.source === entry.text ? formattedEntries[entry.id].body : entry.text;
              const formattedSupervisor = supervisor?.scores ? supervisorDisplay(formatted) : null;
              // A converter may rephrase the rating block; fall back to the saved
              // observation so a formatted view never repeats scores as prose.
              const visibleText = supervisor?.scores
                ? formattedSupervisor?.scores ? formattedSupervisor.body : supervisor.body
                : formatted;
              return <li key={entry.id} data-transcript-entry={entry.id}
                className={'session-transcript-entry chat-history-entry chat-history-' + entry.role}>
                <div className="session-transcript-entry-heading">
                  {entry.pending
                    ? <span className="chat-disclosure-button session-transcript-pending-heading">
                        <svg aria-hidden="true" className="disclosure-chevron" viewBox="0 0 12 12">
                          <path d="m4 2 4 4-4 4"/>
                        </svg>
                        <strong>{name}</strong>
                      </span>
                    : <button type="button" className="chat-disclosure-button" aria-expanded={expanded}
                        aria-controls={'transcript-entry-' + entry.id}
                        onClick={() => setExpandedEntries(current => ({ ...current, [entry.id]: !expanded }))}>
                        <svg aria-hidden="true" className={'disclosure-chevron' + (expanded ? ' is-expanded' : '')} viewBox="0 0 12 12">
                          <path d="m4 2 4 4-4 4"/>
                        </svg>
                        <strong>{name}</strong>
                      </button>}
                  {entry.pending && <small className="session-transcript-pending">Awaiting response…</small>}
                  {!entry.pending && <button type="button" className={'session-transcript-entry-markdown' + (asMarkdown ? ' is-active' : '')}
                    aria-label={asMarkdown ? `Show ${name} as plain text` : `Render ${name} as Markdown`}
                    aria-pressed={asMarkdown}
                    data-tooltip={asMarkdown ? 'Show plain text' : 'Render as Markdown'}
                    onClick={() => toggleEntryMarkdown(entry)}>
                    <svg className="markdown-logo" aria-hidden="true" viewBox="20 25 140 78">
                      <path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z"/>
                      <path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z"/>
                    </svg>
                  </button>}
                  {!entry.pending && <CopyTranscriptEntryButton title={name} text={entry.text}/>}
                </div>
                {supervisor?.scores && <small className="session-transcript-supervisor-scores">
                  Objective alignment {supervisor.scores.alignment}{supervisor.scores.originality !== undefined && <> · Originality {supervisor.scores.originality}</>} · Substantive advancement {supervisor.scores.advancement} · Evidence &amp; validation {supervisor.scores.evidence} · Research health {supervisor.scores.health}
                </small>}
                {!entry.pending && <div id={'transcript-entry-' + entry.id} hidden={!expanded}>
                  {expanded && (asMarkdown
                    ? <div className="session-transcript-markdown"><RenderedMarkdown body={formatTranscriptMarkdown(visibleText)} collapsibleSections/></div>
                    : <pre className="session-transcript-plain">{supervisor?.body ?? entry.text}</pre>)}
                </div>}
              </li>;
            })}
          </ol>
        </li>)}
      </ol>
      {remainingTurns > 0 && <div className="session-transcript-pagination">
        <button type="button" className="text-view-link" onClick={() => setVisibleTurnCount(current => current + 20)}>
          Show more turns
        </button>
      </div>}
    </section>
  </main>;
}
