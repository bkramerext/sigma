import { lazy, Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { createPortal } from 'react-dom';
import { ModelThinkingPillButton } from './GlobalModelPill';
import { modelDisplayLabel } from './model-display';
import './chat-page.css';

const RenderedMarkdown = lazy(() => import('./RenderedMarkdown'));

type Speaker = 'human' | 'ai_1' | 'ai_2' | 'repeated';
type ChatMessage = { speaker: Speaker; text: string };
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

const labels: Record<Speaker, string> = { human: 'Human', ai_1: 'AI #1', ai_2: 'AI #2', repeated: 'Repeated instruction' };
const thinkingLabels: Record<ChatConfig['reasoning_effort'], string> = {
  low: 'Low', medium: 'Medium', high: 'High', xhigh: 'Extra high',
};
const MAX_LOCAL_MESSAGES = 500;
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : 'Brainstorm could not continue.';

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

export default function ChatPage() {
  const [config, setConfig] = useState<ChatConfig | null>(null);
  const configRef = useRef<ChatConfig | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [repeatedText, setRepeatedText] = useState('');
  const repeatedTextRef = useRef('');
  const recordedRepeatedRef = useRef('');
  const [running, setRunning] = useState(false);
  const [turnElapsedSeconds, setTurnElapsedSeconds] = useState(0);
  const [turnTimedOut, setTurnTimedOut] = useState(false);
  const [failedTurn, setFailedTurn] = useState<'ai_1' | 'ai_2' | null>(null);
  const [speaker, setSpeaker] = useState<Speaker | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [conversationId, setConversationId] = useState('');
  const [transcriptPath, setTranscriptPath] = useState('');
  const [headerControlsTarget, setHeaderControlsTarget] = useState<HTMLElement | null>(null);
  const [modelCycleRevision, setModelCycleRevision] = useState(0);
  const [thinkingCycleRevision, setThinkingCycleRevision] = useState(0);
  const messagesRef = useRef<ChatMessage[]>([]);
  const runningRef = useRef(false);
  const runId = useRef(0);
  const abort = useRef<AbortController | null>(null);
  const turnStartedAtRef = useRef<number | null>(null);
  const transcriptWrites = useRef<Promise<void>>(Promise.resolve());
  // If the provider completed but saving the response failed, Retry must
  // save that exact response rather than generate and bill for a duplicate.
  const pendingReplyRef = useRef<ChatMessage | null>(null);

  useEffect(() => { configRef.current = config; }, [config]);

  const refreshConfig = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await fetch('/api/chat/config', { cache: 'no-store', signal });
      const value = await response.json() as ChatConfig;
      if (!response.ok) throw new Error((value as unknown as { error?: string }).error ?? 'Brainstorm settings are unavailable.');
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

  function cycleModel() {
    if (!config) return;
    const available = config.models;
    const index = available.findIndex(item => item.id === config.model);
    const next = available[(index + 1 + available.length) % available.length];
    if (!next) return;
    const updated = { ...config, model: next.id,
      reasoning_effort: next.efforts.includes(config.reasoning_effort) ? config.reasoning_effort : next.efforts[0] };
    configRef.current = updated;
    setConfig(updated);
    setModelCycleRevision(revision => revision + 1);
  }

  function cycleThinking() {
    if (!config) return;
    const efforts = config.models.find(item => item.id === config.model)?.efforts ?? [];
    const index = efforts.indexOf(config.reasoning_effort);
    const next = efforts[(index + 1 + efforts.length) % efforts.length];
    if (next) {
      const updated = { ...config, reasoning_effort: next };
      configRef.current = updated;
      setConfig(updated);
      setThinkingCycleRevision(revision => revision + 1);
    }
  }

  const openTranscript = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch('/api/chat/session', {
      method: 'POST', cache: 'no-store', signal,
    });
    const value = await response.json() as {
      conversation_id?: string; transcript_path?: string; error?: string; detail?: string;
    };
    if (!response.ok || !value.conversation_id || !value.transcript_path) {
      throw new Error(value.error ?? value.detail ?? 'The Brainstorm transcript could not be opened.');
    }
    if (!signal?.aborted) {
      transcriptWrites.current = Promise.resolve();
      recordedRepeatedRef.current = '';
      setConversationId(value.conversation_id);
      setTranscriptPath(value.transcript_path);
    }
    return value.conversation_id;
  }, []);

  function appendTranscriptMessage(id: string, message: ChatMessage): Promise<void> {
    const write = transcriptWrites.current.catch(() => undefined).then(async () => {
      const response = await fetch('/api/chat/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store',
        body: JSON.stringify({ conversation_id: id, ...message }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null) as { detail?: string; error?: string } | null;
        throw new Error(detail?.error ?? detail?.detail ?? 'The Brainstorm transcript could not be updated.');
      }
    });
    transcriptWrites.current = write;
    return write;
  }

  function recordRepeatedInstruction(id: string) {
    const value = repeatedTextRef.current.trim();
    if (!id || value === recordedRepeatedRef.current) return;
    recordedRepeatedRef.current = value;
    const message: ChatMessage = { speaker: 'repeated', text: value || '(cleared)' };
    addMessage(message);
    void appendTranscriptMessage(id, message).catch(cause => setError(errorText(cause)));
  }

  useEffect(() => {
    document.title = 'Brainstorm · SIGMA';
    setHeaderControlsTarget(document.querySelector<HTMLElement>('.chat-site-header .chat-header-center-slot'));
    const controller = new AbortController();
    void refreshConfig(controller.signal);
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
  }, [openTranscript, refreshConfig]);

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
    const next = [...messagesRef.current, message].slice(-MAX_LOCAL_MESSAGES);
    messagesRef.current = next;
    setMessages(next);
  }, []);

  async function requestTurn(who: 'ai_1' | 'ai_2', history: ChatMessage[], controller: AbortController, settings: ChatConfig): Promise<string> {
    const response = await fetch('/api/chat/turn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
      signal: controller.signal,
      body: JSON.stringify({
        conversation_id: conversationId,
        expected_binding: settings.binding,
        speaker: who,
        messages: history.filter(item => item.speaker !== 'repeated').slice(-settings.max_messages),
        model: settings.model,
        reasoning_effort: settings.reasoning_effort,
        repeated_text: repeatedTextRef.current,
      }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => null) as { error?: string; detail?: string } | null;
      throw new Error(detail?.error ?? detail?.detail ?? `AI request failed (${response.status}).`);
    }
    if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) {
      throw new Error('The Brainstorm server returned an invalid response.');
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
    throw new Error('The Brainstorm exchange ended before the AI completed its turn.');
  }

  async function runConversation(id: number, initialSpeaker: 'ai_1' | 'ai_2' = 'ai_1') {
    let nextSpeaker: 'ai_1' | 'ai_2' = initialSpeaker;
    try {
      while (runningRef.current && id === runId.current) {
        recordRepeatedInstruction(conversationId);
        // A previous transcript write error must not permanently poison Retry.
        await transcriptWrites.current.catch(() => undefined);
        if (!runningRef.current || id !== runId.current) return;
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
          const settings = configRef.current;
          if (!settings?.available) throw new Error('The selected AI account is unavailable.');
          const result = await requestTurn(who, messagesRef.current, controller, settings);
          if (!runningRef.current || id !== runId.current) return;
          const reply: ChatMessage = { speaker: who, text: result };
          pendingReplyRef.current = reply;
          addMessage(reply);
        }
        const reply = pendingReplyRef.current;
        if (!reply || reply.speaker !== who) throw new Error('The pending AI reply does not match the retry turn.');
        await appendTranscriptMessage(conversationId, reply);
        pendingReplyRef.current = null;
        turnStartedAtRef.current = null;
        setTurnElapsedSeconds(0);
        nextSpeaker = who === 'ai_1' ? 'ai_2' : 'ai_1';
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

  function sendHuman(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !config?.available || !conversationId) return;
    const message = { speaker: 'human', text } as const;
    recordRepeatedInstruction(conversationId);
    addMessage(message);
    void appendTranscriptMessage(conversationId, message).catch(cause => {
      if (runningRef.current) {
        runId.current += 1;
        runningRef.current = false;
        abort.current?.abort();
        setRunning(false);
        setSpeaker(null);
      }
      setError(errorText(cause));
    });
    setDraft('');
    setError('');
    setNotice('');
    setTurnTimedOut(false);
    setFailedTurn(null);
    pendingReplyRef.current = null;
    if (runningRef.current) return;
    runId.current += 1;
    runningRef.current = true;
    setRunning(true);
    void runConversation(runId.current);
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
    setRunning(false);
    setSpeaker(null);
    setNotice('Stopped. A provider request in progress may have completed and used account allowance.');
  }

  async function clearConversation() {
    if (runningRef.current) return;
    messagesRef.current = [];
    setMessages([]);
    setConversationId('');
    setTranscriptPath('');
    transcriptWrites.current = Promise.resolve();
    recordedRepeatedRef.current = '';
    setError('');
    setNotice('');
    setTurnTimedOut(false);
    setFailedTurn(null);
    pendingReplyRef.current = null;
    try {
      await openTranscript();
    } catch (cause) {
      setError(errorText(cause));
    }
  }

  const timeoutMinutesRemaining = Math.max(1, Math.ceil((600 - turnElapsedSeconds) / 60));
  const timeoutStatus = running && turnElapsedSeconds >= 300
    ? (turnElapsedSeconds >= 600 ? 'Timed out' : `Timing out in ${timeoutMinutesRemaining} minute${timeoutMinutesRemaining === 1 ? '' : 's'}`)
    : turnTimedOut ? 'Timed out' : '';

  const latest = (who: 'ai_1' | 'ai_2') => [...messages].reverse().find(message => message.speaker === who)?.text ?? '';
  const modelControlHint = !config
    ? error || 'Brainstorm settings are loading.'
    : !config.available
      ? config.message || 'Connect an AI account to enable model selection.'
      : `${config.model} · ${config.models.find(item => item.id === config.model)?.label ?? 'Selected model'}. Click to cycle through models; changes apply on the next AI turn.`;
  const thinkingControlHint = !config
    ? error || 'Brainstorm settings are loading.'
    : !config.available
      ? config.message || 'Connect an AI account to enable Thinking selection.'
      : `Thinking is ${thinkingLabels[config.reasoning_effort]}. Click to cycle through supported levels; changes apply on the next AI turn.`;
  const canSend = !!config?.available && !!conversationId
    && !error.startsWith('The chat contains too many messages') && !!draft.trim();

  const selectedModel = config?.models.find(item => item.id === config.model);
  const displayedModel = selectedModel ? modelDisplayLabel(selectedModel) : config?.model ?? 'Loading';
  const displayedThinking = thinkingLabels[config?.reasoning_effort ?? 'low'];
  const selectionDisabled = !config?.available || !config.models.length;
  const modelThinkingControls = <div className="sigma-header-model-column chat-header-model-controls" aria-label="Brainstorm model and thinking controls">
    <span className="global-model-pill-position">
      <ModelThinkingPillButton label={displayedModel} thinkingLabel={`Thinking · ${displayedThinking}`}
        tooltip={`${modelControlHint} ${thinkingControlHint} Click the upper half to cycle models; click the lower half to cycle thinking levels.`}
        disabled={selectionDisabled}
        modelCycleRevision={modelCycleRevision} thinkingCycleRevision={thinkingCycleRevision}
        onCycleModel={cycleModel} onCycleThinking={cycleThinking}/>
    </span>
  </div>;

  return <>
  {headerControlsTarget && createPortal(modelThinkingControls, headerControlsTarget)}
  <main className="chat-page">
    <header className="chat-page-header">
      <div className="chat-title-group"><p className="chat-eyebrow">Open conversation</p><h1>Brainstorm</h1></div>
      <p className="chat-description">Send a message to AI #1. AI #1 and AI #2 will alternate until you stop them.</p>
    </header>
    <p className="chat-privacy-note">Transcript file: <code>{transcriptPath || 'opening…'}</code></p>
    {config && !config.available && <p className="chat-error" role="status">{config.message || 'Connect an AI account to start brainstorming.'}</p>}
    {error && <p className="chat-error" role="alert">{error}</p>}
    <section className="chat-repeated-prompt" aria-label="Repeated text">
      <div className="chat-field-heading">
        <label htmlFor="chat-repeated-text" data-tooltip="Prepended to every AI request; changes apply on the next turn.">Repeated:</label>
      </div>
      <textarea id="chat-repeated-text" rows={2} value={repeatedText}
        onBlur={() => recordRepeatedInstruction(conversationId)}
        onChange={event => { repeatedTextRef.current = event.target.value; setRepeatedText(event.target.value); }}
        placeholder="Optional text prepended to every AI turn…"/>
    </section>
    <form id="brainstorm-human-form" className="chat-human-form" onSubmit={sendHuman}>
      <div className="chat-field-heading">
        <label htmlFor="chat-human-message">Human:</label>
      </div>
      <textarea id="chat-human-message" aria-label="Human" rows={2} value={draft}
        onChange={event => setDraft(event.target.value)}
        placeholder="Write a message to AI #1…"
        onKeyDown={event => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') event.currentTarget.form?.requestSubmit(); }}/>
    </form>
    <div className="chat-controls" role="region" aria-label="Brainstorm exchange controls">
      <button type="submit" form="brainstorm-human-form" className="chat-send" disabled={!canSend}>Send</button>
      {failedTurn && !running && <button type="button" className="chat-retry" disabled={!conversationId} onClick={retryConversation}>Retry {labels[failedTurn]}</button>}
      <button type="button" className="chat-stop" disabled={!running} onClick={stopConversation}>Stop exchange</button>
      <button type="button" className="chat-clear" disabled={running || !messages.length} onClick={clearConversation}>Clear</button>
      <span role="status" aria-live="polite">{running ? `${labels[speaker ?? 'ai_1']} is responding…` : notice}</span>
      {timeoutStatus && <span className="chat-timeout-status" role="timer" aria-label="Brainstorm turn time limit">{timeoutStatus}</span>}
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
    {!!messages.length && <ol className="chat-history" aria-label="Conversation history">
      {messages.map((message, index) => <li key={`${message.speaker}-${index}`} className={`chat-history-${message.speaker}`}>
        <div className="chat-reply-heading"><strong>{labels[message.speaker]}</strong><CopyReplyButton name={labels[message.speaker]} text={message.text}/></div><MarkdownReply body={message.text}/>
      </li>)}
    </ol>}
  </main>
  </>;
}
