import { lazy, Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { createPortal } from 'react-dom';
import { ModelThinkingPillButton } from './GlobalModelPill';
import { modelDisplayLabel } from './model-display';
import './chat-page.css';

const RenderedMarkdown = lazy(() => import('./RenderedMarkdown'));

type Speaker = 'human' | 'ai_1' | 'ai_2' | 'supervisor';
type Participant = 'ai_1' | 'ai_2';
type ChatMessage = {
  speaker: Speaker;
  text: string;
  recipients?: Participant[];
  guidance?: string;
  score?: number;
  action?: 'continue' | 'nudge' | 'redirect';
  breakthrough_candidate?: boolean;
  breakthrough_invalidated?: boolean;
  milestone_latched?: boolean;
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

const labels: Record<Speaker, string> = { human: 'Human', ai_1: 'AI #1', ai_2: 'AI #2', supervisor: 'Supervisor' };
const thinkingLabels: Record<ChatConfig['reasoning_effort'], string> = {
  low: 'Low', medium: 'Medium', high: 'High', xhigh: 'Extra high',
};
const MAX_LOCAL_MESSAGES = 500;
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : 'Brainstorm could not continue.';

function promptHistory(messages: ChatMessage[], limit: number) {
  return messages.slice(-limit).map(({ speaker, text, recipients, guidance }) => ({
    speaker, text,
    ...(speaker === 'supervisor' ? { recipients: recipients ?? [], guidance: guidance ?? '' } : {}),
  }));
}

function MarkdownReply({ body }: { body: string }) {
  return <div className="chat-markdown">
    <Suspense fallback={<p>{body}</p>}><RenderedMarkdown body={body}/></Suspense>
  </div>;
}

export default function ChatPage() {
  const [config, setConfig] = useState<ChatConfig | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [researchObjective, setResearchObjective] = useState('');
  const researchObjectiveRef = useRef('');
  const recordedObjectiveRef = useRef('');
  const [supervisorEnabled, setSupervisorEnabled] = useState(false);
  const supervisorEnabledRef = useRef(false);
  const [progress, setProgress] = useState<number | null>(null);
  const milestoneLatchedRef = useRef(false);
  const [running, setRunning] = useState(false);
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
  const transcriptWrites = useRef<Promise<void>>(Promise.resolve());

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
    if (!config || running) return;
    const available = config.models;
    const index = available.findIndex(item => item.id === config.model);
    const next = available[(index + 1 + available.length) % available.length];
    if (!next) return;
    setConfig({ ...config, model: next.id,
      reasoning_effort: next.efforts.includes(config.reasoning_effort) ? config.reasoning_effort : next.efforts[0] });
    setModelCycleRevision(revision => revision + 1);
  }

  function cycleThinking() {
    if (!config || running) return;
    const efforts = config.models.find(item => item.id === config.model)?.efforts ?? [];
    const index = efforts.indexOf(config.reasoning_effort);
    const next = efforts[(index + 1 + efforts.length) % efforts.length];
    if (next) {
      setConfig({ ...config, reasoning_effort: next });
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
      setConversationId(value.conversation_id);
      setTranscriptPath(value.transcript_path);
    }
    return value.conversation_id;
  }, []);

  function appendTranscriptMessage(id: string, message: { speaker: 'human' | Participant | 'objective'; text: string }): Promise<void> {
    const write = transcriptWrites.current.then(async () => {
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
        messages: promptHistory(history, settings.max_messages),
        model: settings.model,
        reasoning_effort: settings.reasoning_effort,
        research_objective: researchObjectiveRef.current,
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

  async function requestSupervisorReview(history: ChatMessage[], settings: ChatConfig, controller: AbortController): Promise<ChatMessage> {
    const response = await fetch('/api/chat/supervise', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
      signal: controller.signal,
      body: JSON.stringify({
        conversation_id: conversationId,
        expected_binding: settings.binding,
        messages: promptHistory(history, settings.max_messages),
        model: settings.model,
        reasoning_effort: settings.reasoning_effort,
        research_objective: researchObjectiveRef.current,
        milestone_latched: milestoneLatchedRef.current,
      }),
    });
    const assessment = await response.json() as ChatMessage & { error?: string; detail?: string };
    if (!response.ok) throw new Error(assessment.error ?? assessment.detail ?? 'Supervisor assessment failed.');
    if (assessment.speaker !== 'supervisor' || typeof assessment.score !== 'number') {
      throw new Error('Supervisor returned an invalid assessment.');
    }
    return assessment;
  }

  async function runConversation(id: number, settings: ChatConfig) {
    let nextSpeaker: Participant = 'ai_1';
    let turnsSinceReview = 0;
    try {
      while (runningRef.current && id === runId.current) {
        await transcriptWrites.current;
        if (!runningRef.current || id !== runId.current) return;
        const who: 'ai_1' | 'ai_2' = nextSpeaker;
        const controller = new AbortController();
        abort.current = controller;
        setSpeaker(who);
        const result = await requestTurn(who, messagesRef.current, controller, settings);
        if (!runningRef.current || id !== runId.current) return;
        const reply = { speaker: who, text: result } as const;
        addMessage(reply);
        await appendTranscriptMessage(conversationId, reply);
        nextSpeaker = who === 'ai_1' ? 'ai_2' : 'ai_1';
        turnsSinceReview += 1;
        if (supervisorEnabledRef.current && turnsSinceReview >= 4) {
          turnsSinceReview = 0;
          const reviewController = new AbortController();
          abort.current = reviewController;
          setSpeaker('supervisor');
          try {
            const assessment = await requestSupervisorReview(messagesRef.current, settings, reviewController);
            if (!runningRef.current || id !== runId.current) return;
            // The supervisor endpoint already wrote this assessment into the transcript.
            addMessage(assessment);
            setProgress(assessment.score ?? null);
            milestoneLatchedRef.current = !!assessment.milestone_latched;
            setNotice('');
          } catch (cause) {
            if (!runningRef.current || id !== runId.current) return;
            // A metacognitive review failure must never stop the two participants.
            setNotice('Supervisor review unavailable; the exchange continues.');
            console.warn('Brainstorm supervisor review unavailable', cause);
          }
        }
        setSpeaker(nextSpeaker);
        await new Promise(resolve => window.setTimeout(resolve, 500));
      }
    } catch (cause) {
      if (id === runId.current && runningRef.current) {
        setError(errorText(cause));
        setNotice('The exchange stopped. Check the message above before starting again.');
      }
    } finally {
      if (id === runId.current) {
        abort.current = null;
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
    if (runningRef.current) return;
    runId.current += 1;
    runningRef.current = true;
    setRunning(true);
    void runConversation(runId.current, config);
  }

  function stopConversation() {
    if (!runningRef.current) return;
    runId.current += 1;
    runningRef.current = false;
    abort.current?.abort();
    abort.current = null;
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
    recordedObjectiveRef.current = '';
    milestoneLatchedRef.current = false;
    setProgress(null);
    setError('');
    setNotice('');
    try {
      await openTranscript();
    } catch (cause) {
      setError(errorText(cause));
    }
  }

  function recordResearchObjective() {
    const text = researchObjectiveRef.current.trim();
    if (!conversationId || text === recordedObjectiveRef.current) return;
    recordedObjectiveRef.current = text;
    void appendTranscriptMessage(conversationId, {
      speaker: 'objective', text: text || '(cleared)',
    }).catch(cause => setError(errorText(cause)));
  }

  const latest = (who: Participant) => [...messages].reverse().find(message => message.speaker === who)?.text ?? '';
  const modelControlHint = !config
    ? error || 'Brainstorm settings are loading.'
    : !config.available
      ? config.message || 'Connect an AI account to enable model selection.'
      : running
        ? 'Stop the exchange before changing the model.'
        : `${config.model} · ${config.models.find(item => item.id === config.model)?.label ?? 'Selected model'}. Click to cycle through models available to this account.`;
  const thinkingControlHint = !config
    ? error || 'Brainstorm settings are loading.'
    : !config.available
      ? config.message || 'Connect an AI account to enable Thinking selection.'
      : running
        ? 'Stop the exchange before changing the Thinking level.'
        : `Thinking is ${thinkingLabels[config.reasoning_effort]}. Click to cycle through levels supported by this model.`;
  const canSend = !!config?.available && !!conversationId
    && !error.startsWith('The chat contains too many messages') && !!draft.trim();

  const selectedModel = config?.models.find(item => item.id === config.model);
  const displayedModel = selectedModel ? modelDisplayLabel(selectedModel) : config?.model ?? 'Loading';
  const displayedThinking = thinkingLabels[config?.reasoning_effort ?? 'low'];
  const selectionDisabled = !config?.available || !config.models.length || running;
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
    <section className="chat-repeated-prompt" aria-label="Research objective">
      <div className="chat-field-heading">
        <label htmlFor="chat-research-objective">Research Objective:</label>
      </div>
      <textarea id="chat-research-objective" rows={2} value={researchObjective}
        onChange={event => { researchObjectiveRef.current = event.target.value; setResearchObjective(event.target.value); }}
        onBlur={recordResearchObjective}
        placeholder="What discovery or understanding should this research pursue?"/>
    </section>
    <section className="chat-supervisor-settings" aria-label="Supervisor settings">
      <label className="chat-supervisor-toggle">
        <input type="checkbox" checked={supervisorEnabled}
          onChange={event => { supervisorEnabledRef.current = event.target.checked; setSupervisorEnabled(event.target.checked); }}/>
        <span>Enable Supervisor</span>
      </label>
      <p>Optional metacognitive guidance: periodically assesses progress toward your Research Objective,
        gives gentle clarity and productivity nudges to AI #1, AI #2, or both when useful,
        and records each assessment and any direction in the transcript. It does not contribute research ideas.
        Reviews use additional AI requests.</p>
      {supervisorEnabled && <div className="chat-supervisor-progress" role="status" aria-live="polite">
        <span>Research Progress</span>
        <strong>{progress === null ? '—' : progress.toFixed(1)} / 10.0</strong>
        {milestoneLatchedRef.current && <span className="chat-supervisor-milestone">Potential breakthrough · verification required</span>}
      </div>}
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
      <button type="button" className="chat-stop" disabled={!running} onClick={stopConversation}>Stop exchange</button>
      <button type="button" className="chat-clear" disabled={running || !messages.length} onClick={clearConversation}>Clear</button>
      <span role="status" aria-live="polite">{running ? `${labels[speaker ?? 'ai_1']} is responding…` : notice}</span>
    </div>
    <section className="chat-boxes" aria-label="AI responses">
      {(['ai_1', 'ai_2'] as const).map(who => <section key={who}
        className={`chat-box chat-agent${speaker === who ? ' is-speaking' : ''}`}
        aria-label={`${labels[who]} latest reply`}>
        <h2>{labels[who]}{speaker === who ? ' · responding' : ''}</h2>
        {latest(who)
          ? <MarkdownReply body={latest(who)}/>
          : <p className="chat-agent-placeholder">{labels[who]}’s reply will appear here.</p>}
      </section>)}
    </section>
    {!!messages.length && <ol className="chat-history" aria-label="Conversation history">
      {messages.map((message, index) => <li key={`${message.speaker}-${index}`}
        className={`chat-history-${message.speaker}${message.speaker === 'supervisor' && message.milestone_latched ? ' is-breakthrough' : ''}`}>
        <strong>{labels[message.speaker]}</strong><MarkdownReply body={message.text}/>
      </li>)}
    </ol>}
  </main>
  </>;
}
