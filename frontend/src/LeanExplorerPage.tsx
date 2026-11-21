import { lazy, Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import './lean-explorer.css';

const RenderedMarkdown = lazy(() => import('./RenderedMarkdown'));

type Speaker = 'human' | 'ai_1' | 'ai_2' | 'objective' | 'supervisor';
type TranscriptSpeaker = Speaker | 'supervisor_setting' | 'source';
type Target = 'ai_1' | 'ai_2' | 'both';
type ChatMessage = { speaker: TranscriptSpeaker; text: string; timestamp?: string; recipient?: Target; guidance?: string; score?: number; breakthrough?: boolean };
type SupervisorAssessment = {
  score: number;
  rubric: Record<'alignment' | 'originality' | 'advancement' | 'evidence' | 'momentum', number>;
  assessment: string;
  action: 'continue' | 'nudge' | 'redirect';
  recipient: Target | null;
  guidance: string;
  breakthrough_candidate: boolean;
  breakthrough_invalidated?: boolean;
};
type SavedTranscript = {
  conversation_id: string;
  transcript_name: string;
  transcript_path: string;
  messages: ChatMessage[];
  research_objective: string;
  next_speaker: 'ai_1' | 'ai_2';
  supervisor_enabled: boolean;
};
type ChatConfig = {
  available: boolean;
  mode: string;
  status: string;
  message: string;
  binding: string;
  model: string;
  models: { id: string; label: string; relative_cost: string; efforts: ChatConfig['reasoning_effort'][] }[];
  reasoning_effort: 'low' | 'medium' | 'high' | 'xhigh';
  max_messages: number;
};

const labels: Record<TranscriptSpeaker, string> = { human: 'Human', ai_1: 'AI #1', ai_2: 'AI #2', objective: 'Research Objective', supervisor: 'Supervisor', supervisor_setting: 'Supervisor setting', source: 'Sources' };
// Keep the complete transcript in memory; pagination only affects rendering.
const TRANSCRIPT_GROUPS_PER_PAGE = 20;

// Only errors returned *before* the server starts model inference are safe to
// retry automatically. A malformed/truncated generated response may already
// have consumed sponsored allowance.
class ExplorerPreflightUnavailable extends Error {}
type IndexedEntry = { message: ChatMessage; index: number };
type TranscriptGroup = { entries: IndexedEntry[] };

function groupTranscriptEntries(messages: ChatMessage[]): TranscriptGroup[] {
  const groups: TranscriptGroup[] = [];
  for (const [index, message] of messages.entries()) {
    if (message.speaker === 'supervisor_setting') continue;
    const last = groups[groups.length - 1];
    const lastSpeaker = last?.entries[last.entries.length - 1].message.speaker;
    if ((message.speaker === 'ai_2' && lastSpeaker === 'ai_1')
      || (message.speaker === 'supervisor' && lastSpeaker === 'ai_2')) {
      last.entries.push({ message, index });
    } else {
      groups.push({ entries: [{ message, index }] });
    }
  }
  return groups.reverse();
}

function entryTimestamp(timestamp?: string): string {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp : new Intl.DateTimeFormat(undefined, {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit',
  }).format(date);
}
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : 'Lean Explorer could not continue.';

// FastAPI validation failures contain structured issues. Do not stringify an
// array of objects into "[object Object]" and lose the actionable error.
function apiErrorMessage(value: unknown, fallback: string): string {
  if (!value || typeof value !== 'object') return fallback;
  const response = value as { detail?: unknown; error?: unknown };
  const detail = response.error ?? response.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (!Array.isArray(detail)) return fallback;
  const issues = detail.map((item: unknown) => {
    if (!item || typeof item !== 'object') return '';
    const issue = item as { loc?: unknown; msg?: unknown };
    const path = Array.isArray(issue.loc) ? issue.loc.map(String).join('.') : '';
    const message = typeof issue.msg === 'string' ? issue.msg : '';
    return path && message ? `${path}: ${message}` : message;
  }).filter(Boolean);
  return issues.length ? issues.join('; ') : fallback;
}

function CopyReplyButton({ name, text }: { name: string; text: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }
  return <button type="button" className="text-view-link text-view-icon workspace-icon-button text-copy-button chat-copy-button"
    aria-label={copied ? `Copied ${name} to clipboard` : `Copy ${name}`}
    data-tooltip={copied ? 'Copied' : `Copy ${name}`} disabled={!text} onClick={() => void copy()}>
    {copied
      ? <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 4 4L19 6"/></svg>
      : <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>}
  </button>;
}

function MarkdownReply({ body }: { body: string }) {
  return <div className="chat-markdown">
    <Suspense fallback={<p>{body}</p>}><RenderedMarkdown body={body}/></Suspense>
  </div>;
}

export default function LeanExplorerPage({ onClose }: { onClose: () => void }) {
  const [config, setConfig] = useState<ChatConfig | null>(null);
  const configRef = useRef<ChatConfig | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  // Only manual changes override the initial disclosure state for each entry.
  const [expandedEntries, setExpandedEntries] = useState<Record<number, boolean>>({});
  const [visibleGroupCount, setVisibleGroupCount] = useState(TRANSCRIPT_GROUPS_PER_PAGE);
  const [draft, setDraft] = useState('');
  type SourceChoice = { formal_path: string; include_guide: boolean; include_announcement: boolean };
  type SourcePreview = { kind: string; path: string; url: string; commit: string; sha256: string; text: string; complete: boolean; characters: number };
  const [sourcePath, setSourcePath] = useState('src/Statements.lean');
  const [includeGuide, setIncludeGuide] = useState(true);
  const [includeAnnouncement, setIncludeAnnouncement] = useState(true);
  const [sourcePreview, setSourcePreview] = useState<SourcePreview | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState('');
  const [activeTranscriptName, setActiveTranscriptName] = useState('');
  const sourceSettingsRef = useRef<SourceChoice>({ formal_path: 'src/Statements.lean', include_guide: true, include_announcement: true });
  const lastSourceSelectionRef = useRef('');
  const sourceManifestShaRef = useRef('');
  const [sourceRecordVersion, setSourceRecordVersion] = useState(0);
  async function loadSourcePreview(path: string) {
    setSourceLoading(true); setSourceError('');
    try {
      const q = new URLSearchParams({kind: 'formal', path});
      const response = await fetch('/api/explorelean/source?' + q, {cache: 'no-store', headers: {'X-Sigma-Error-Handled': 'true'}});
      const data = await response.json() as SourcePreview & {detail?: string; error?: string};
      if (!response.ok) throw new Error(apiErrorMessage(data, 'The Lean source could not be retrieved.'));
      setSourcePreview(data);
    } catch (cause) {
      setSourcePreview(null); setSourceError(errorText(cause));
    } finally { setSourceLoading(false); }
  }
  useEffect(() => { void loadSourcePreview('src/Statements.lean'); }, []);
  function updateSourcePath(value: string) {
    sourceSettingsRef.current = {...sourceSettingsRef.current, formal_path: value};
    setSourcePath(value);
  }
  function updateIncludeGuide(value: boolean) {
    sourceSettingsRef.current = {...sourceSettingsRef.current, include_guide: value};
    setIncludeGuide(value);
  }
  function updateIncludeAnnouncement(value: boolean) {
    sourceSettingsRef.current = {...sourceSettingsRef.current, include_announcement: value};
    setIncludeAnnouncement(value);
  }
  const [researchObjective, setResearchObjective] = useState('Develop a rigorous, human-readable exposition of Alpöge’s Riemann Hypothesis proof, checking every mathematical bridge against the pinned Lean source.');
  const researchObjectiveRef = useRef('Develop a rigorous, human-readable exposition of Alpöge’s Riemann Hypothesis proof, checking every mathematical bridge against the pinned Lean source.');
  const recordedObjectiveRef = useRef('');
  const [supervisorEnabled, setSupervisorEnabled] = useState(false);
  const supervisorEnabledRef = useRef(false);
  const [progressScore, setProgressScore] = useState<number | null>(null);
  const breakthroughLatched = useRef(false);
  const [running, setRunning] = useState(false);
  const [turnElapsedSeconds, setTurnElapsedSeconds] = useState(0);
  const [turnTimedOut, setTurnTimedOut] = useState(false);
  const [failedTurn, setFailedTurn] = useState<'ai_1' | 'ai_2' | null>(null);
  const [speaker, setSpeaker] = useState<Speaker | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [conversationId, setConversationId] = useState('');
  const [transcriptPath, setTranscriptPath] = useState('');
  const [savedTranscripts, setSavedTranscripts] = useState<{ name: string }[]>([]);
  const [selectedTranscript, setSelectedTranscript] = useState('');
  const [restoringTranscript, setRestoringTranscript] = useState(false);
  const messagesRef = useRef<ChatMessage[]>([]);
  const runningRef = useRef(false);
  const runId = useRef(0);
  const abort = useRef<AbortController | null>(null);
  const turnStartedAtRef = useRef<number | null>(null);
  const transcriptWrites = useRef<Promise<void>>(Promise.resolve());
  // If the provider completed but saving the response failed, Retry must
  // save that exact response rather than generate and bill for a duplicate.
  const pendingReplyRef = useRef<ChatMessage | null>(null);
  const pendingHumanRef = useRef<ChatMessage | null>(null);
  const skipNextSupervisorAssessmentRef = useRef(false);

  useEffect(() => { configRef.current = config; }, [config]);

  // Model/Thinking is a shared, persisted setting across Home, Project and
  // Lean Explorer. Read it immediately before every new inference request, not
  // once when the alternating conversation starts.
  async function currentTurnSettings(): Promise<ChatConfig> {
    // Read the live connection for every inference, rather than retaining a
    // connection that was selected before this conversation (or even one turn)
    // began. Changing accounts is not a conversation-state change.
    const [connectionResponse, preferencesResponse] = await Promise.all([
      fetch('/api/explorelean/config', {
        cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' },
      }),
      fetch('/api/user-preferences/research-settings', {
        cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' },
      }),
    ]);
    if (!connectionResponse.ok) throw new Error('Could not read the selected AI connection. Retry this turn.');
    const current = await connectionResponse.json() as ChatConfig;
    configRef.current = current;
    setConfig(current);
    if (!current.available) throw new Error(current.message || 'Connect an AI account before continuing.');
    if (!preferencesResponse.ok) throw new Error('Could not load the current Model/Thinking selection. Retry the turn.');
    const preferences = await preferencesResponse.json() as { ai_model?: string; reasoning_effort?: string };
    // The new connection may offer a different model catalog. Keep explicit
    // user-selected settings if available; otherwise use that connection's
    // verified default. This does not switch the funding/connection mode.
    const choice = current.models.find(item => item.id === preferences.ai_model)
      ?? current.models.find(item => item.id === current.model);
    if (!choice) throw new Error('The selected AI connection has no available Lean Explorer model.');
    const effort = choice.efforts.includes(preferences.reasoning_effort as ChatConfig['reasoning_effort'])
      ? preferences.reasoning_effort as ChatConfig['reasoning_effort']
      : choice.efforts.includes(current.reasoning_effort)
        ? current.reasoning_effort
        : choice.efforts[0];
    if (!effort) throw new Error('The selected AI connection has no available Thinking setting.');
    return { ...current, model: choice.id, reasoning_effort: effort };
  }

  const refreshTranscripts = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch('/api/explorelean/transcripts', { cache: 'no-store', signal });
    if (!response.ok) throw new Error('Could not list saved Lean Explorer transcripts.');
    if (!signal?.aborted) setSavedTranscripts(await response.json() as { name: string }[]);
  }, []);

  const refreshConfig = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await fetch('/api/explorelean/config', {
        cache: 'no-store', signal, headers: { 'X-Sigma-Error-Handled': 'true' },
      });
      const value = await response.json() as ChatConfig;
      if (!response.ok) throw new Error((value as unknown as { error?: string }).error ?? 'Lean Explorer settings are unavailable.');
      setConfig(previous => {
        if (!previous) return value;
        const retainedModel = value.models.some(item => item.id === previous.model)
          ? previous.model : value.model;
        const selected = value.models.find(item => item.id === retainedModel);
        const effort = selected?.efforts.includes(previous.reasoning_effort)
          ? previous.reasoning_effort
          : value.reasoning_effort;
        return { ...value, model: retainedModel, reasoning_effort: effort };
      });
      setError('');
    } catch (cause) {
      if (!signal?.aborted) setError(errorText(cause));
    }
  }, []);

  const openTranscript = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch('/api/explorelean/session', {
      method: 'POST', cache: 'no-store', signal,
    });
    const value = await response.json() as {
      conversation_id?: string; transcript_path?: string; error?: string; detail?: string;
    };
    if (!response.ok || !value.conversation_id || !value.transcript_path) {
      throw new Error(value.error ?? value.detail ?? 'The Lean Explorer transcript could not be opened.');
    }
    if (!signal?.aborted) {
      transcriptWrites.current = Promise.resolve();
      setActiveTranscriptName((value as { transcript_name?: string }).transcript_name ?? '');
      recordedObjectiveRef.current = '';
      setConversationId(value.conversation_id);
      setTranscriptPath(value.transcript_path);
    }
    return value.conversation_id;
  }, []);

  function appendTranscriptMessage(id: string, message: ChatMessage): Promise<void> {
    const write = transcriptWrites.current.catch(() => undefined).then(async () => {
      const response = await fetch('/api/explorelean/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store',
        // Persist only the API schema fields. The UI-only score, breakthrough
        // and timestamp metadata must not be sent: extra="forbid" rejects them.
        body: JSON.stringify({
          conversation_id: id, speaker: message.speaker, text: message.text,
          ...(message.recipient ? { recipient: message.recipient } : {}),
          ...(message.guidance ? { guidance: message.guidance } : {}),
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null) as unknown;
        throw new Error(apiErrorMessage(detail, 'The Lean Explorer transcript could not be updated.'));
      }
    });
    transcriptWrites.current = write;
    return write;
  }

  async function ensureSourcesAttached(id: string) {
    const selection = sourceSettingsRef.current;
    const key = JSON.stringify(selection);
    if (key === lastSourceSelectionRef.current && sourceManifestShaRef.current) return;
    const response = await fetch('/api/explorelean/attach', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
      body: JSON.stringify({conversation_id: id, ...selection}),
    });
    const data = await response.json() as { source_manifest_sha256?: string; record?: string; detail?: string; error?: string };
    if (!response.ok || !data.source_manifest_sha256 || !data.record)
      throw new Error(apiErrorMessage(data, 'The selected Lean sources could not be attached.'));
    sourceManifestShaRef.current = data.source_manifest_sha256;
    lastSourceSelectionRef.current = key;
    setSourceRecordVersion(previous => previous + 1);
    addMessage({speaker: 'source', text: data.record});
  }

  function recordResearchObjective(id: string) {
    const value = researchObjectiveRef.current.trim();
    if (!id || value === recordedObjectiveRef.current) return;
    recordedObjectiveRef.current = value;
    const message: ChatMessage = { speaker: 'objective', text: value || '(cleared)' };
    addMessage(message);
    void appendTranscriptMessage(id, message).catch(cause => setError(errorText(cause)));
  }

  useEffect(() => {
    document.title = 'Lean Explorer · SIGMA';
    const controller = new AbortController();
    void refreshConfig(controller.signal);
    void refreshTranscripts(controller.signal).catch(cause => {
      if (!controller.signal.aborted) setError(errorText(cause));
    });
    void openTranscript(controller.signal).catch(cause => {
      if (!controller.signal.aborted) setError(errorText(cause));
    });
    const onFocus = () => { void refreshConfig(); };
    window.addEventListener('focus', onFocus);
    return () => {
      window.removeEventListener('focus', onFocus);
      controller.abort();
      runId.current += 1;
      abort.current?.abort();
    };
  }, [openTranscript, refreshConfig, refreshTranscripts]);

  useEffect(() => {
    if (!running || turnStartedAtRef.current === null) return;
    const update = () => {
      if (turnStartedAtRef.current !== null) {
        setTurnElapsedSeconds(Math.floor((Date.now() - turnStartedAtRef.current) / 1000));
      }
    };
    update();
    const interval = window.setInterval(update, 1000);
    return () => window.clearInterval(interval);
  }, [running, speaker]);

  const addMessage = useCallback((message: ChatMessage) => {
    // Keep all history visible, including early Supervisor assessments.
    // Inference requests are separately bounded by settings.max_messages.
    const next = [...messagesRef.current, { ...message, timestamp: message.timestamp ?? new Date().toISOString() }];
    messagesRef.current = next;
    setMessages(next);
  }, []);

  async function requestTurn(who: 'ai_1' | 'ai_2', history: ChatMessage[], controller: AbortController, settings: ChatConfig, sessionId = conversationId): Promise<string> {
    const response = await fetch('/api/explorelean/turn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
      cache: 'no-store',
      signal: controller.signal,
      body: JSON.stringify({
        conversation_id: sessionId,
        speaker: who,
        ...sourceSettingsRef.current,
        source_manifest_sha256: sourceManifestShaRef.current,
        messages: history.filter(item => item.speaker !== 'objective' && item.speaker !== 'supervisor_setting' && item.speaker !== 'source'
          && !(item.speaker === 'supervisor' && item.text.startsWith('Supervisor assessment unavailable:'))).slice(-settings.max_messages).map(({speaker, text, recipient, guidance}) => ({speaker, text, recipient, guidance})),
        model: settings.model,
        reasoning_effort: settings.reasoning_effort,
        research_objective: researchObjectiveRef.current,
      }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => null) as { error?: string; detail?: string } | null;
      const message = detail?.error ?? detail?.detail ?? `AI request failed (${response.status}).`;
      // This endpoint returns 503 before dispatching any model request. Don't
      // automatically retry rate/quota exhaustion or authorization failures.
      if (response.status === 503 &&
          !/limit|quota|allowance|exhaust|reauth|authorization|permission|not connected/i.test(message)) {
        throw new ExplorerPreflightUnavailable(message);
      }
      throw new Error(message);
    }
    if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) {
      throw new Error('The Lean Explorer server returned an invalid response.');
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const frames = buffer.split('\n\n');
      buffer = frames.pop() ?? '';
      for (const frame of frames) {
        const line = frame.split('\n').find(row => row.startsWith('data: '));
        if (!line) continue;
        const event = JSON.parse(line.slice(6)) as { type: string; text?: string; error?: string };
        if (event.type === 'error') throw new Error(event.error ?? 'AI turn failed.');
        if (event.type === 'complete' && event.text) return event.text;
      }
      if (done) break;
    }
    throw new Error('The Lean Explorer exchange ended before the AI completed its turn.');
  }

  async function assessPair(id: number, sessionId = conversationId) {
    if (!supervisorEnabledRef.current || !researchObjectiveRef.current.trim()) return;
    const settings = await currentTurnSettings();
    const controller = new AbortController();
    abort.current = controller;
    const response = await fetch('/api/explorelean/supervisor', {
      method: 'POST', cache: 'no-store', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
      body: JSON.stringify({
        conversation_id: sessionId,         messages: messagesRef.current.filter(item => item.speaker !== 'objective' && item.speaker !== 'supervisor_setting' && item.speaker !== 'source'
          && !(item.speaker === 'supervisor' && item.text.startsWith('Supervisor assessment unavailable:')))
          .slice(-settings.max_messages).map(({speaker, text, recipient, guidance}) => ({speaker, text, recipient, guidance})),
        model: settings.model, reasoning_effort: settings.reasoning_effort,
        research_objective: researchObjectiveRef.current,
        milestone_latched: breakthroughLatched.current,
      }),
    });
    const assessment = await response.json() as SupervisorAssessment;
    if (!response.ok) throw new Error(apiErrorMessage(assessment, 'Supervisor assessment failed.'));
    if (typeof assessment.score !== 'number' || !Number.isFinite(assessment.score) ||
        typeof assessment.assessment !== 'string' || !assessment.assessment) {
      throw new Error('The supervisor returned an invalid assessment.');
    }
    if (!runningRef.current || id !== runId.current || !supervisorEnabledRef.current) return;
    if (assessment.breakthrough_invalidated) breakthroughLatched.current = false;
    if (assessment.breakthrough_candidate) breakthroughLatched.current = true;
    const score = breakthroughLatched.current ? 10 : assessment.score;
    const guidance = assessment.guidance?.trim() ?? '';
    const recipient = assessment.recipient;
    const summary = assessment.rubric ? Object.entries(assessment.rubric).map(([name, points]) =>
      `${name}: ${Number(points).toFixed(1)}`).join(' · ') : '';
    const text = [
      `Research progress: ${score.toFixed(1)} / 10.0`,
      assessment.breakthrough_candidate ? 'POTENTIAL BREAKTHROUGH DETECTED — independent validation required.'
        : assessment.breakthrough_invalidated ? 'Previous breakthrough candidate invalidated; normal scoring resumed.'
          : breakthroughLatched.current ? 'Breakthrough candidate remains under validation.' : '',
      summary ? `Rubric — ${summary}` : '',
      assessment.assessment,
      assessment.action !== 'continue' && recipient && guidance
        ? `To ${recipient === 'both' ? 'AI #1 and AI #2' : labels[recipient]}: ${guidance}`
        : 'No intervention.',
    ].filter(Boolean).join('\n\n');
    const entry: ChatMessage = { speaker: 'supervisor', text, score,
      breakthrough: breakthroughLatched.current,
      ...(assessment.action !== 'continue' && recipient && guidance ? { recipient, guidance } : {}),
    };
    // The transcript is authoritative: do not display an assessment as
    // recorded until its durable append has completed.
    await appendTranscriptMessage(sessionId, entry);
    addMessage(entry);
    setProgressScore(score);
  }

  async function runConversation(id: number, initialSpeaker: 'ai_1' | 'ai_2' = 'ai_1', sessionId = conversationId) {
    let nextSpeaker: 'ai_1' | 'ai_2' = initialSpeaker;
    try {
      while (runningRef.current && id === runId.current) {
        recordResearchObjective(sessionId);
        // A previous transcript write error must not permanently poison Retry.
        await transcriptWrites.current.catch(() => undefined);
        if (!runningRef.current || id !== runId.current) return;
        await ensureSourcesAttached(sessionId);
        if (!runningRef.current || id !== runId.current) return;
        if (pendingHumanRef.current) {
          await appendTranscriptMessage(sessionId, pendingHumanRef.current);
          pendingHumanRef.current = null;
        }
        const who: 'ai_1' | 'ai_2' = nextSpeaker;
        const controller = new AbortController();
        abort.current = controller;
        turnStartedAtRef.current = Date.now();
        setTurnElapsedSeconds(0);
        setTurnTimedOut(false);
        setSpeaker(who);
        // Snapshot the selected model/thinking on each new provider request.
        // If a response was generated but its transcript write failed, resume
        // that write instead of making another potentially billable request.
        if (!pendingReplyRef.current) {
          const settings = await currentTurnSettings();
          let result = '';
          for (let attempt = 0; attempt < 3; attempt += 1) {
            try {
              result = await requestTurn(who, messagesRef.current, controller, settings, sessionId);
              break;
            } catch (cause) {
              const detail = errorText(cause);
              const safeToRetry = cause instanceof ExplorerPreflightUnavailable;
              if (!safeToRetry || attempt === 2 || !runningRef.current || id !== runId.current || controller.signal.aborted) {
                throw new Error(safeToRetry && attempt === 2
                  ? `The connection check was unavailable after 3 automatic attempts. Saved research is intact. (${detail})`
                  : detail);
              }
              // Retry only a rejected preflight. A successful 200/SSE stream
              // may have incurred a provider charge even if decoding failed.
              await new Promise(resolve => window.setTimeout(resolve, 350 * (attempt + 1)));
              if (!runningRef.current || id !== runId.current || controller.signal.aborted) return;
            }
          }
          if (!runningRef.current || id !== runId.current) return;
          const reply: ChatMessage = { speaker: who, text: result };
          pendingReplyRef.current = reply;
          addMessage(reply);
        }
        const reply = pendingReplyRef.current;
        if (!reply || reply.speaker !== who) throw new Error('The pending AI reply does not match the retry turn.');
        await appendTranscriptMessage(sessionId, reply);
        pendingReplyRef.current = null;
        turnStartedAtRef.current = null;
        setTurnElapsedSeconds(0);
        nextSpeaker = who === 'ai_1' ? 'ai_2' : 'ai_1';
        if (who === 'ai_2' && supervisorEnabledRef.current && !skipNextSupervisorAssessmentRef.current) {
          try { await assessPair(id, sessionId); }
          catch (cause) {
            if (runningRef.current && id === runId.current && supervisorEnabledRef.current) {
              const detail = errorText(cause);
              // Supervisor failures belong in the permanent record too. Never
              // silently omit an assessment or interrupt the two researchers.
              const failure: ChatMessage = {
                speaker: 'supervisor',
                text: `Supervisor assessment unavailable: ${detail}`,
              };
              // A failed write of a completed assessment must be handled by
              // the same durable transcript queue, not hidden by a toast.
              try {
                await appendTranscriptMessage(sessionId, failure);
                addMessage(failure);
                setNotice('Supervisor assessment failed and was recorded; the AIs are continuing.');
              } catch (writeCause) {
                setError(`Supervisor assessment could not be recorded: ${errorText(writeCause)}`);
              }
            }
          }
        }
        if (who === 'ai_2') skipNextSupervisorAssessmentRef.current = false;
        setSpeaker(nextSpeaker);
        await new Promise(resolve => window.setTimeout(resolve, 500));
      }
    } catch (cause) {
      if (id === runId.current && runningRef.current) {
        const message = errorText(cause);
        const timedOut = /timed out|timeout/i.test(message);
        setTurnTimedOut(timedOut);
        setFailedTurn(nextSpeaker);
        setError(message);
        setNotice(timedOut ? 'Timed out. Retry the failed turn when ready.' : 'The exchange stopped. Retry the failed turn when ready.');
      }
    } finally {
      if (id === runId.current) {
        abort.current = null;
        turnStartedAtRef.current = null;
        runningRef.current = false;
        setRunning(false);
        setSpeaker(null);
      }
    }
  }

  async function resumeTranscript(name: string) {
    if (!name || runningRef.current || restoringTranscript) return;
    setRestoringTranscript(true);
    setError('');
    setNotice('');
    try {
      const response = await fetch(`/api/explorelean/transcripts/${encodeURIComponent(name)}`, { cache: 'no-store' });
      if (!response.ok) throw new Error('The selected transcript could not be restored.');
      const saved = await response.json() as SavedTranscript;
      if (runningRef.current) return;
      // The existing conversation ID and file are reused. No historical entries
      // are re-appended and the first new provider request follows the last AI.
      runId.current += 1;
      abort.current?.abort();
      pendingReplyRef.current = null;
      pendingHumanRef.current = null;
      skipNextSupervisorAssessmentRef.current = false;
      transcriptWrites.current = Promise.resolve();
      const restored = saved.messages;
      const sourceEntry = [...restored].reverse().find(item => item.speaker === 'source');
      if (sourceEntry) {
        try {
          const savedSource = JSON.parse(sourceEntry.text) as {
            formal_path?: string; include_guide?: boolean; include_announcement?: boolean;
            source_manifest_sha256?: string;
          };
          if (typeof savedSource.formal_path === 'string'
              && typeof savedSource.include_guide === 'boolean'
              && typeof savedSource.include_announcement === 'boolean'
              && /^[0-9a-f]{64}$/.test(savedSource.source_manifest_sha256 ?? '')) {
            const selection: SourceChoice = {
              formal_path: savedSource.formal_path,
              include_guide: savedSource.include_guide,
              include_announcement: savedSource.include_announcement,
            };
            sourceSettingsRef.current = selection;
            setSourcePath(selection.formal_path);
            setIncludeGuide(selection.include_guide);
            setIncludeAnnouncement(selection.include_announcement);
            lastSourceSelectionRef.current = JSON.stringify(selection);
            sourceManifestShaRef.current = savedSource.source_manifest_sha256!;
            void loadSourcePreview(selection.formal_path);
          }
        } catch { /* The source manifest is independently validated on dispatch. */ }
      } else {
        lastSourceSelectionRef.current = '';
        sourceManifestShaRef.current = '';
      }
      messagesRef.current = restored;
      setMessages(restored);
      setExpandedEntries({});
      setVisibleGroupCount(TRANSCRIPT_GROUPS_PER_PAGE);
      setConversationId(saved.conversation_id);
      setTranscriptPath(saved.transcript_path);
      setActiveTranscriptName(saved.transcript_name);
      recordedObjectiveRef.current = saved.research_objective;
      researchObjectiveRef.current = saved.research_objective;
      setResearchObjective(saved.research_objective);
      supervisorEnabledRef.current = saved.supervisor_enabled;
      setSupervisorEnabled(saved.supervisor_enabled);
      const latestSupervisor = [...restored].reverse().find(item => item.speaker === 'supervisor');
      const score = latestSupervisor?.text.match(/Research progress:\s*(\d+(?:\.\d+)?)\s*\/\s*10\.0/);
      const restoredScore = score ? Number(score[1]) : null;
      setProgressScore(restoredScore);
      breakthroughLatched.current = !!latestSupervisor?.text.includes('Breakthrough candidate remains under validation.')
        || !!latestSupervisor?.text.includes('POTENTIAL BREAKTHROUGH DETECTED');
      setSelectedTranscript(name);
      setDraft('');
      setFailedTurn(null);
      setTurnTimedOut(false);
      setTurnElapsedSeconds(0);
      // Do not charge for a new inference if there is no actual conversation
      // to continue; restore it for a Human kickoff instead.
      if (!restored.some(item => item.speaker === 'human' || item.speaker === 'ai_1' || item.speaker === 'ai_2')) {
        setNotice('Transcript restored. Enter a Human message to begin.');
        return;
      }
      runId.current += 1;
      runningRef.current = true;
      setRunning(true);
      setNotice('Transcript restored; continuing the exchange.');
      void runConversation(runId.current, saved.next_speaker, saved.conversation_id);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setRestoringTranscript(false);
    }
  }

  function changeSupervisor(enabled: boolean) {
    supervisorEnabledRef.current = enabled;
    setSupervisorEnabled(enabled);
    // Changing the supervisor never stops or restarts the current AI turn.
    // Persist the setting independently of AI-visible history, in order.
    if (conversationId) {
      void appendTranscriptMessage(conversationId, {
        speaker: 'supervisor_setting',
        text: enabled ? 'enabled' : 'disabled',
      }).catch(cause => setError(errorText(cause)));
    }
  }

  function sendHuman(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !config?.available || !conversationId) return;
    const message = { speaker: 'human', text } as const;
    recordResearchObjective(conversationId);
    addMessage(message);
    void appendTranscriptMessage(conversationId, message).catch(cause => {
      if (runningRef.current) {
        runId.current += 1;
        runningRef.current = false;
        abort.current?.abort();
        setRunning(false);
        setSpeaker(null);
      }
      pendingHumanRef.current = message;
      setFailedTurn('ai_1');
      setNotice('The exchange stopped. Retry to save the Human message and continue.');
      setError(errorText(cause));
    });
    setDraft('');
    setError('');
    setNotice('');
    setTurnTimedOut(false);
    // A Human intervention during an active turn must not discard a
    // completed reply that still needs to be written to the transcript.
    if (runningRef.current) return;
    const resumeSpeaker = failedTurn ?? 'ai_1';
    if (!pendingReplyRef.current) pendingHumanRef.current = null;
    runId.current += 1;
    runningRef.current = true;
    setRunning(true);
    void runConversation(runId.current, resumeSpeaker);
  }

  function retryConversation() {
    if (runningRef.current || !failedTurn || !conversationId) return;
    const who = failedTurn;
    setError('');
    setNotice('');
    setTurnTimedOut(false);
    setFailedTurn(null);
    runId.current += 1;
    runningRef.current = true;
    setRunning(true);
    void runConversation(runId.current, who);
  }

  function skipFailedTurn() {
    if (!failedTurn || runningRef.current || !conversationId || pendingReplyRef.current) return;
    const next = failedTurn === 'ai_1' ? 'ai_2' : 'ai_1';
    skipNextSupervisorAssessmentRef.current = failedTurn === 'ai_1';
    setFailedTurn(null);
    setError('');
    setTurnTimedOut(false);
    setNotice(`Skipped the failed ${labels[failedTurn]} turn; ${labels[next]} is continuing.`);
    runId.current += 1;
    runningRef.current = true;
    setRunning(true);
    void runConversation(runId.current, next);
  }

  function stopConversation() {
    if (!runningRef.current) return;
    runId.current += 1;
    runningRef.current = false;
    abort.current?.abort();
    abort.current = null;
    turnStartedAtRef.current = null;
    setTurnTimedOut(false);
    setFailedTurn(null);
    pendingReplyRef.current = null;
    pendingHumanRef.current = null;
    skipNextSupervisorAssessmentRef.current = false;
    setRunning(false);
    setSpeaker(null);
    setNotice('Stopped. A provider request in progress may have completed and used account allowance.');
  }

  async function clearConversation() {
    if (runningRef.current) return;
    messagesRef.current = [];
    setMessages([]);
    setExpandedEntries({});
    setVisibleGroupCount(TRANSCRIPT_GROUPS_PER_PAGE);
    setConversationId('');
    setTranscriptPath('');
    setActiveTranscriptName('');
    setSelectedTranscript('');
    lastSourceSelectionRef.current = '';
    sourceManifestShaRef.current = '';
    transcriptWrites.current = Promise.resolve();
    recordedObjectiveRef.current = '';
    researchObjectiveRef.current = '';
    setResearchObjective('');
    breakthroughLatched.current = false;
    setProgressScore(null);
    setError('');
    setNotice('');
    setTurnTimedOut(false);
    setFailedTurn(null);
    pendingReplyRef.current = null;
    pendingHumanRef.current = null;
    skipNextSupervisorAssessmentRef.current = false;
    try {
      await openTranscript();
      await refreshTranscripts();
    } catch (cause) {
      setError(errorText(cause));
    }
  }

  const timeoutMinutesRemaining = Math.max(1, Math.ceil((600 - turnElapsedSeconds) / 60));
  const timeoutStatus = running && turnElapsedSeconds >= 300
    ? (turnElapsedSeconds >= 600 ? 'Timed out' : `Timing out in ${timeoutMinutesRemaining} minute${timeoutMinutesRemaining === 1 ? '' : 's'}`)
    : turnTimedOut ? 'Timed out' : '';

  const latest = (who: 'ai_1' | 'ai_2') => [...messages].reverse().find(message => message.speaker === who)?.text ?? '';
  const isEntryExpanded = (message: ChatMessage, index: number) =>
    expandedEntries[index] ?? (message.speaker !== 'ai_1' && message.speaker !== 'ai_2');
  const resetTranscriptExpansion = () => {
    // Restore the canonical state; individual disclosure choices remain free
    // until the user explicitly resets them again.
    setExpandedEntries({});
  };
  const transcriptGroups = groupTranscriptEntries(messages);
  const shownGroups = transcriptGroups.slice(0, visibleGroupCount);
  const hiddenGroups = transcriptGroups.length - shownGroups.length;
  const canSend = !!config?.available && !!conversationId
    && !error.startsWith('The chat contains too many messages') && !!draft.trim();

  return <>
  <main className="chat-page">
    <div className="leanx-page-tools">
      <span>Formal proof exploration · Interactive research workspace</span>
      <button type="button" className="leanx-close-button" aria-label="Close Lean Explorer" onClick={onClose}>×</button>
    </div>
    <div className="chat-transcript-picker">
      <label htmlFor="chat-saved-transcript">Continue transcript:</label>
      <select id="chat-saved-transcript" value={selectedTranscript}
        disabled={running || restoringTranscript || !conversationId}
        onChange={event => {
          if (!event.target.value) setSelectedTranscript('');
          else void resumeTranscript(event.target.value);
        }}>
        <option value="">Choose saved transcript…</option>
        {savedTranscripts.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}
      </select>
      {activeTranscriptName && <a className="leanx-export-link" href={`/api/explorelean/transcripts/${encodeURIComponent(activeTranscriptName)}/download`}>Download transcript</a>}
    </div>
    <p className="chat-privacy-note">Lean Explorer transcript file: <code>{transcriptPath || 'opening…'}</code></p>
    {config && !config.available && <p className="chat-error" role="status">{config.message || 'Connect an AI account to start brainstorming.'}</p>}
    {error && <p className="chat-error" role="alert">{error}</p>}
    <section className="leanx-real-sources" aria-label="Lean Explorer source inputs">
      <div className="leanx-real-source-header">
        <h2>Inputs</h2>
        <span>Pinned formal source + supplementary literature</span>
      </div>
      <div className="leanx-real-source-form">
        <label htmlFor="leanx-formal-path">A. Official Lean proof · <a href="https://github.com/CocoSgt/riemann-hypothesis-lean/tree/7cbf7a0c32fca1badf05931879a37c3f8a2b03b4" target="_blank" rel="noreferrer">Mirror 7cbf7a0</a></label>
        <div className="leanx-real-source-path-row">
          <input id="leanx-formal-path" value={sourcePath} disabled={running || restoringTranscript}
            spellCheck={false} onChange={event => updateSourcePath(event.target.value)}
            aria-label="Lean file path within pinned mirror" />
          <button type="button" disabled={sourceLoading || running} onClick={() => void loadSourcePreview(sourceSettingsRef.current.formal_path)}>
            {sourceLoading ? 'Loading…' : 'Read file'}
          </button>
        </div>
        <p className="leanx-source-note">Enter a real <code>src/… .lean</code> path. The server fetches and hashes source bytes; imports are not followed automatically yet.</p>
      </div>
      <div className="leanx-real-source-form">
        <div className="leanx-source-group-title">B. Supplementary sources</div>
        <label className="leanx-source-checkbox"><input type="checkbox" checked={includeGuide} disabled={running || restoringTranscript}
          onChange={event => updateIncludeGuide(event.target.checked)}/>
          <span>Proof guide (<a href="https://github.com/nasqret/riemann-rev/blob/main/guide/proof-guide.pdf" target="_blank" rel="noreferrer">riemann-rev PDF</a>; text from pinned TeX)</span>
        </label>
        <label className="leanx-source-checkbox"><input type="checkbox" checked={includeAnnouncement} disabled={running || restoringTranscript}
          onChange={event => updateIncludeAnnouncement(event.target.checked)}/>
          <span>Alpöge announcement (<a href="https://alpo.ge/remark.pdf" target="_blank" rel="noreferrer">remark.pdf</a>)</span>
        </label>
        <p className="leanx-source-note">Selected sources are fetched and supplied as bounded, marked excerpts to each AI turn. A source manifest and hashes are saved in the transcript.</p>
      </div>
      {sourceError && <p role="alert" className="chat-error leanx-source-error">{sourceError}</p>}
      {sourcePreview && <details className="leanx-source-preview">
        <summary>Source preview: {sourcePreview.path} · SHA256 {sourcePreview.sha256.slice(0,12)}… {sourcePreview.complete ? '' : '· incomplete excerpt'}</summary>
        <p><a href={sourcePreview.url} target="_blank" rel="noreferrer">Pinned source URL</a> · {sourcePreview.commit} · {sourcePreview.characters} characters</p>
        <pre>{sourcePreview.text}</pre>
      </details>}
      <div className="leanx-source-state" role="status">Source manifest: {sourceManifestShaRef.current ? sourceManifestShaRef.current.slice(0, 12) + '… (saved)' : 'will be saved when the exchange starts'}{sourceRecordVersion > 0 ? '' : ''}</div>
    </section>
    <section className="chat-repeated-prompt" aria-label="Research objective">
      <div className="chat-field-heading">
        <label htmlFor="chat-research-objective" data-tooltip="Shared with both AIs and the optional supervisor; changes apply on the next turn.">Research Objective:</label>
        <CopyReplyButton name="Research Objective" text={researchObjective}/>
      </div>
      <textarea id="chat-research-objective" rows={2} value={researchObjective}
        onBlur={() => recordResearchObjective(conversationId)}
        onChange={event => { researchObjectiveRef.current = event.target.value; setResearchObjective(event.target.value); }}
        placeholder="What finding or research goal should the two AIs pursue?"/>
    </section>
    <section className="chat-supervisor-option" aria-label="Lean Explorer supervisor">
      <label><input type="checkbox" checked={supervisorEnabled}
        disabled={restoringTranscript}
        onChange={event => changeSupervisor(event.target.checked)}/>
        Enable Supervisor</label>
      <p>A third AI reviews progress after each AI pair, recording a brief assessment and offering occasional
         gentle process-only guidance, without contributing research ideas.</p>
    </section>
    {supervisorEnabled && progressScore !== null && <p className="chat-progress-status" aria-live="polite">
      Research progress: <strong>{progressScore.toFixed(1)} / 10.0</strong>
      {breakthroughLatched.current ? ' · Potential breakthrough — independent validation needed' : ''}
    </p>}
    <form id="explorelean-human-form" className="chat-human-form" onSubmit={sendHuman}>
      <div className="chat-field-heading">
        <label htmlFor="chat-human-message">Human:</label>
        <CopyReplyButton name="Human" text={draft}/>
      </div>
      <textarea id="chat-human-message" aria-label="Human" rows={2} value={draft}
        onChange={event => setDraft(event.target.value)}
        placeholder="Write a message to AI #1…"
        onKeyDown={event => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') event.currentTarget.form?.requestSubmit(); }}/>
    </form>
    <div className="chat-controls" role="region" aria-label="Lean Explorer exchange controls">
      <button type="submit" form="explorelean-human-form" className="chat-send" disabled={!canSend}>Send</button>
      {failedTurn && !running && <button type="button" className="chat-retry" aria-label={`Retry ${labels[failedTurn]}`} data-tooltip={`Retry the interrupted ${labels[failedTurn]} turn`} disabled={!conversationId} onClick={retryConversation}>Retry</button>}
      {failedTurn && !running && <button type="button" className="chat-skip" data-tooltip={`Skip the failed ${labels[failedTurn]} turn and continue with the other AI`} disabled={!conversationId || !!pendingReplyRef.current} onClick={skipFailedTurn}>Skip turn</button>}
      <button type="button" className="chat-stop" disabled={!running} onClick={stopConversation}>Stop exchange</button>
      <button type="button" className="chat-clear" disabled={running || restoringTranscript || !messages.length} onClick={clearConversation}>Clear</button>
      <span role="status" aria-live="polite">{running ? `${labels[speaker ?? 'ai_1']} is responding…` : notice}</span>
      {timeoutStatus && <span className="chat-timeout-status" role="timer" aria-label="Lean Explorer turn time limit">{timeoutStatus}</span>}
    </div>
    <section className="chat-boxes" aria-label="AI responses">
      {(['ai_1', 'ai_2'] as const).map(who => <section key={who}
        className={`chat-box chat-agent${speaker === who ? ' is-speaking' : ''}`}
        aria-label={`${labels[who]} latest reply`}>
        <div className="chat-reply-heading"><h2>{labels[who]}{speaker === who ? ' · responding' : ''}</h2><CopyReplyButton name={labels[who]} text={latest(who)}/></div>
        {latest(who)
          ? <MarkdownReply body={latest(who)}/>
          : <p className="chat-agent-placeholder">{labels[who]}’s reply will appear here.</p>}
      </section>)}
    </section>
    {!!messages.length && <section className="chat-transcript" aria-label="Transcript">
      <h2 className="chat-transcript-heading">
        <button type="button" className="chat-disclosure-button"
          aria-controls="chat-transcript-history" onClick={resetTranscriptExpansion}
          data-tooltip="Restore default transcript expansion">
          <svg aria-hidden="true" className="disclosure-chevron is-expanded" viewBox="0 0 12 12"><path d="m4 2 4 4-4 4"/></svg>
          Transcript
        </button>
      </h2>
      <ol id="chat-transcript-history" className="chat-history" aria-label="Conversation history">
        {shownGroups.map(group => <li key={group.entries[0].index} className="chat-transcript-group">
          <ol className="chat-transcript-group-entries">
            {group.entries.map(({ message, index }) => {
              const expanded = isEntryExpanded(message, index);
              return <li key={index} className={`chat-history-entry chat-history-${message.speaker}`}>
                <div className="chat-reply-heading">
                  <button type="button" className="chat-disclosure-button" aria-expanded={expanded}
                    aria-controls={`chat-transcript-entry-${index}`}
                    onClick={() => setExpandedEntries(previous => ({ ...previous, [index]: !expanded }))}>
                    <svg aria-hidden="true" className={`disclosure-chevron${expanded ? ' is-expanded' : ''}`} viewBox="0 0 12 12"><path d="m4 2 4 4-4 4"/></svg>
                    <strong>{labels[message.speaker]}</strong>
                  </button>
                  <CopyReplyButton name={labels[message.speaker]} text={message.text}/>
                  {message.timestamp && <time className="chat-entry-timestamp" dateTime={message.timestamp}>
                    {entryTimestamp(message.timestamp)}
                  </time>}
                </div>
                <div id={`chat-transcript-entry-${index}`} hidden={!expanded}>
                  {message.speaker === 'supervisor' && message.recipient && <p className="chat-supervisor-meta">
                    Process guidance to {message.recipient === 'both' ? 'both AIs' : labels[message.recipient]}
                  </p>}
                  {expanded && <MarkdownReply body={message.text}/>}
                </div>
              </li>;
            })}
          </ol>
        </li>)}
      </ol>
      {hiddenGroups > 0 && <div className="chat-history-pagination" role="status">
        <p>Showing the latest {shownGroups.length} of {transcriptGroups.length} exchanges.
          {hiddenGroups} earlier {hiddenGroups === 1 ? 'exchange is' : 'exchanges are'} hidden from this view,
          but the complete record remains in the transcript file.</p>
        <button type="button" onClick={() => setVisibleGroupCount(previous => previous + TRANSCRIPT_GROUPS_PER_PAGE)}>
          Show {Math.min(hiddenGroups, TRANSCRIPT_GROUPS_PER_PAGE)} earlier
        </button>
      </div>}
    </section>}
  </main>
  </>;
}
