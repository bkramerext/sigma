import { useEffect, useRef, useState } from 'react';
import './style.css';
import RenderedMarkdown from './RenderedMarkdown';
import { projectTranscript, groupTranscriptTurns, convertibleTranscriptEntry, type TranscriptIntervention, type TranscriptEntry } from './session-transcript';
import './session-transcript.css';

type SessionLogEvent = { seq: number; timestamp: string; type: string; request_id?: string; role?: string; round?: number; strategy_id?: string; step_id?: string; status?: string; [key: string]: unknown };
type SessionState = { number: number; status: string; current_action?: string; termination_reason_code?: string; reason?: string; message?: string };
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
    data-tooltip={copied ? 'Copied' : `Copy ${title}`} disabled={!text} onClick={() => { void copy(); }}>
    {copied
      ? <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 4 4L19 6"/></svg>
      : <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>}
  </button>;
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
  const [projectId, setProjectId] = useState('');
  const [interventions, setInterventions] = useState<TranscriptIntervention[]>([]);
  const [expandedEntries, setExpandedEntries] = useState<Record<string, boolean>>({});
  const [renderMarkdown, setRenderMarkdown] = useState(false);
  const [seenMarkdownEntries, setSeenMarkdownEntries] = useState<Set<string>>(() => new Set());
  const [formattedEntries, setFormattedEntries] = useState<Record<string, { source: string; body: string }>>({});
  const formattedEntriesRef = useRef<Record<string, { source: string; body: string }>>({});
  const conversionQueue = useRef<TranscriptEntry[]>([]);
  const conversionQueued = useRef(new Set<string>());
  const conversionWorker = useRef(false);
  const conversionAbort = useRef<AbortController | null>(null);
  const markdownEnabled = useRef(false);
  const [markdownError, setMarkdownError] = useState('');
  const [error, setError] = useState('');
  const [copyError, setCopyError] = useState('');
  const [copyState, setCopyState] = useState<'idle' | 'copying' | 'copied'>('idle');
  const copyTimer = useRef<number | null>(null);
  const list = useRef<HTMLOListElement>(null);
  const [visibleGroupCount, setVisibleGroupCount] = useState(20);
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
        const data = await response.json() as { events: SessionLogEvent[]; cursor: number; short_name: string; project_title: string; project_id?: string; session: SessionState; interventions?: TranscriptIntervention[] };
        if (!alive) return;
        const fresh = data.events.filter(event => !seen.current.has(event.seq));
        fresh.forEach(event => seen.current.add(event.seq));
        if (fresh.length) setEvents(current => [...current, ...fresh]);
        cursor.current = Math.max(cursor.current, data.cursor);
        setShortName(data.short_name); setProjectTitle(data.project_title); if (data.project_id) setProjectId(data.project_id); setSession(data.session); setInterventions(data.interventions ?? []); setError('');
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
  // Queue formatting only after a transcript row has entered the scroll viewport.
  // A long historical transcript must not trigger hundreds of paid conversions
  // merely because the user enabled Markdown.
  useEffect(() => {
    if (!renderMarkdown || !list.current || typeof IntersectionObserver === 'undefined') return;
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
  }, [renderMarkdown, events, expandedEntries, visibleGroupCount]);

  // The existing Markdown action formats saved provider text with the same
  // metered converter as other SIGMA research blocks. The original transcript
  // and Copy/Download remain byte-for-byte unchanged. Only accepted, visible
  // transcript content is queued; never send arbitrary browser-authored text.
  useEffect(() => {
    if (!renderMarkdown || !projectId) return;
    const entries = projectTranscript(events, interventions).filter(entry =>
      seenMarkdownEntries.has(entry.id) &&
      entry.role !== 'other' &&
      (expandedEntries[entry.id] ?? !['investigator', 'skeptic'].includes(entry.role)) &&
      convertibleTranscriptEntry(entry));
    for (const entry of entries) {
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
            if (!controller.signal.aborted && markdownEnabled.current) {
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
  }, [renderMarkdown, events, interventions, projectId, path, sessionId, expandedEntries, seenMarkdownEntries]);

  const toggleMarkdown = () => {
    const next = !renderMarkdown;
    markdownEnabled.current = next;
    setRenderMarkdown(next);
    if (!next) {
      conversionAbort.current?.abort();
      conversionQueue.current = [];
      conversionQueued.current = new Set(Object.keys(formattedEntriesRef.current));
      setSeenMarkdownEntries(new Set());
      setMarkdownError('');
    }
  };
  useEffect(() => () => { conversionAbort.current?.abort(); }, []);
  const allGroups = groupTranscriptTurns(
    projectTranscript(events, interventions).filter(entry => entry.role !== 'other'),
  );
  const shownGroups = allGroups.slice(0, visibleGroupCount);
  const hiddenGroups = allGroups.length - shownGroups.length;
  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return Number.isNaN(date.getTime()) ? timestamp : new Intl.DateTimeFormat(undefined, {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit',
    }).format(date);
  };
  return <main className="session-log-page session-conversation-page">
    <header className="session-transcript-page-header">
      <h1>{projectTitle || shortName}, Session {session?.number ?? '…'} — Transcript</h1>
      <p>Research conversation · {session?.status ?? 'loading'}</p>
      <div className="session-log-toolbar session-transcript-toolbar" aria-label="Transcript actions">
        <button type="button"
          className={'session-log-toolbar-icon session-transcript-markdown-toggle' + (renderMarkdown ? ' is-active' : '')}
          aria-label={renderMarkdown ? 'Show plain transcript' : 'Render transcript as Markdown'}
          aria-pressed={renderMarkdown}
          data-tooltip={renderMarkdown ? 'Show plain text' : 'Render as Markdown'}
          onClick={toggleMarkdown}>
          <svg className="markdown-logo" aria-hidden="true" width="24" height="20" viewBox="20 25 160 78">
            <path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z"/>
            <path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z"/>
          </svg>
        </button>
        <button type="button" className="session-log-toolbar-icon text-copy-button"
          aria-label="Copy complete transcript" data-tooltip={copyState === 'copied' ? 'Copied' : 'Copy complete transcript'}
          disabled={copyState === 'copying'} onClick={() => { void copyLog(); }}>
          {copyState === 'copied'
            ? <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 4 4L19 6"/></svg>
            : <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>}
        </button>
        <a className="session-log-toolbar-icon session-log-download" href={downloadUrl}
          aria-label="Download complete transcript" data-tooltip="Download complete transcript">
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v3.5h13V13" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </a>
      </div>
    </header>
    {copyState === 'copied' && <p role="status" className="session-log-copy-status">Copied transcript to clipboard.</p>}
    {copyError && <p role="alert" className="session-log-copy-error">{copyError}</p>}
    {(error || markdownError) && <p role="alert">{error || markdownError}</p>}
    <section className="session-transcript-conversation" aria-label="Transcript">
      <h2>Transcript</h2>
      <ol ref={list} className="session-log-events session-transcript-events" aria-label="Conversation history">
        {shownGroups.map(group => <li key={group.key} className="session-transcript-turn">
          <ol className="session-transcript-turn-entries">
            {group.entries.map(entry => {
              const expanded = expandedEntries[entry.id] ?? !['investigator', 'skeptic'].includes(entry.role);
              return <li key={entry.id} data-transcript-entry={entry.id}
                className={'session-transcript-entry chat-history-entry chat-history-' + entry.role}>
                <div className="session-transcript-entry-heading">
                  <button type="button" className="chat-disclosure-button" aria-expanded={expanded}
                    aria-controls={'transcript-entry-' + entry.id}
                    onClick={() => setExpandedEntries(current => ({ ...current, [entry.id]: !expanded }))}>
                    <svg aria-hidden="true" className={'disclosure-chevron' + (expanded ? ' is-expanded' : '')} viewBox="0 0 12 12">
                      <path d="m4 2 4 4-4 4"/>
                    </svg>
                    <strong>{entry.title}</strong>
                  </button>
                  <CopyTranscriptEntryButton title={entry.title} text={entry.text}/>
                  <time dateTime={entry.timestamp}>{formatTimestamp(entry.timestamp)}</time>
                </div>
                <div id={'transcript-entry-' + entry.id} hidden={!expanded}>
                  {expanded && (renderMarkdown
                    ? <div className="session-transcript-markdown"><RenderedMarkdown body={formattedEntries[entry.id]?.source === entry.text ? formattedEntries[entry.id].body : entry.text}/></div>
                    : <pre className="session-transcript-plain">{entry.text}</pre>)}
                </div>
              </li>;
            })}
          </ol>
        </li>)}
      </ol>
      {hiddenGroups > 0 && <div className="session-transcript-pagination">
        <p>Showing the latest {shownGroups.length} of {allGroups.length} exchanges. The complete record remains available through Copy and Download.</p>
        <button type="button" onClick={() => setVisibleGroupCount(current => current + 20)}>
          Show {Math.min(hiddenGroups, 20)} earlier
        </button>
      </div>}
    </section>
  </main>;
}
