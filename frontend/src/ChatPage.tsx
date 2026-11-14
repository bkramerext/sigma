import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import './chat-page.css';

type Speaker = 'human' | 'ai_1' | 'ai_2';
type ChatMessage = { speaker: Speaker; text: string };
type ChatConfig = {
  available: boolean;
  mode: string;
  status: string;
  message: string;
  binding: string;
  model: string;
  reasoning_effort: 'low' | 'medium' | 'high' | 'xhigh';
  max_messages: number;
  max_message_characters: number;
};

const labels: Record<Speaker, string> = { human: 'Human', ai_1: 'AI #1', ai_2: 'AI #2' };
const MAX_LOCAL_MESSAGES = 500;
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : 'Chat could not continue.';

export default function ChatPage({ onHome }: { onHome: () => void }) {
  const [config, setConfig] = useState<ChatConfig | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [running, setRunning] = useState(false);
  const [speaker, setSpeaker] = useState<Speaker | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [conversationId, setConversationId] = useState(() => crypto.randomUUID());
  const messagesRef = useRef<ChatMessage[]>([]);
  const runningRef = useRef(false);
  const runId = useRef(0);
  const abort = useRef<AbortController | null>(null);

  const refreshConfig = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await fetch('/api/chat/config', { cache: 'no-store', signal });
      const value = await response.json() as ChatConfig;
      if (!response.ok) throw new Error((value as unknown as { error?: string }).error ?? 'Chat settings are unavailable.');
      setConfig(value);
      setError('');
    } catch (cause) {
      if (!signal?.aborted) setError(errorText(cause));
    }
  }, []);

  useEffect(() => {
    document.title = 'Chat · SIGMA';
    const controller = new AbortController();
    void refreshConfig(controller.signal);
    const onFocus = () => { void refreshConfig(); };
    window.addEventListener('focus', onFocus);
    return () => {
      window.removeEventListener('focus', onFocus);
      controller.abort();
      runId.current += 1;
      abort.current?.abort();
    };
  }, [refreshConfig]);

  const addMessage = useCallback((message: ChatMessage) => {
    const next = [...messagesRef.current, message].slice(-MAX_LOCAL_MESSAGES);
    messagesRef.current = next;
    setMessages(next);
  }, []);

  function editLatestAgent(speaker: 'ai_1' | 'ai_2', text: string) {
    const next = [...messagesRef.current];
    let index = -1;
    for (let cursor = next.length - 1; cursor >= 0; cursor -= 1) {
      if (next[cursor].speaker === speaker) { index = cursor; break; }
    }
    if (index >= 0) {
      if (!text.trim()) next.splice(index, 1);
      else next[index] = { ...next[index], text };
    } else if (text.trim()) {
      next.push({ speaker, text });
    }
    messagesRef.current = next;
    setMessages(next);
  }

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
        messages: history.slice(-settings.max_messages),
        model: settings.model,
        reasoning_effort: settings.reasoning_effort,
      }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => null) as { error?: string; detail?: string } | null;
      throw new Error(detail?.error ?? detail?.detail ?? `AI request failed (${response.status}).`);
    }
    if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) {
      throw new Error('The chat server returned an invalid response.');
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
    throw new Error('The chat ended before the AI completed its turn.');
  }

  async function runConversation(id: number, settings: ChatConfig) {
    let nextSpeaker: 'ai_1' | 'ai_2' = 'ai_1';
    try {
      while (runningRef.current && id === runId.current) {
        const who: 'ai_1' | 'ai_2' = nextSpeaker;
        const controller = new AbortController();
        abort.current = controller;
        setSpeaker(who);
        const result = await requestTurn(who, messagesRef.current, controller, settings);
        if (!runningRef.current || id !== runId.current) return;
        addMessage({ speaker: who, text: result });
        nextSpeaker = who === 'ai_1' ? 'ai_2' : 'ai_1';
        setSpeaker(nextSpeaker);
        await new Promise(resolve => window.setTimeout(resolve, 500));
      }
    } catch (cause) {
      if (id === runId.current && runningRef.current) {
        setError(errorText(cause));
        setNotice('The AI exchange stopped. Review your selected account before retrying.');
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
    if (!text || !config?.available || text.length > config.max_message_characters) return;
    addMessage({ speaker: 'human', text });
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

  function clearConversation() {
    if (runningRef.current) return;
    messagesRef.current = [];
    setMessages([]);
    setConversationId(crypto.randomUUID());
    setError('');
    setNotice('');
  }

  const latest = (who: 'ai_1' | 'ai_2') => [...messages].reverse().find(message => message.speaker === who)?.text ?? '';
  const canSend = !!config?.available && !error.startsWith('The chat contains too many messages')
    && !!draft.trim() && draft.trim().length <= (config?.max_message_characters ?? 0);

  return <main className="chat-page">
    <header className="chat-page-header">
      <button type="button" className="chat-home-link" onClick={onHome}>← SIGMA Home</button>
      <div><p className="chat-eyebrow">Open conversation</p><h1>Two AI chat</h1></div>
      <p className="chat-description">Send a message to AI #1. AI #1 and AI #2 will alternate until you stop them.</p>
    </header>
    <section className="chat-boxes" aria-label="Conversation participants">
      <form className="chat-box chat-human" onSubmit={sendHuman}>
        <label htmlFor="chat-human-message">Human</label>
        <div className="chat-human-entry">
          <textarea id="chat-human-message" value={draft} onChange={event => setDraft(event.target.value)}
            placeholder="Write a message to AI #1…" maxLength={config?.max_message_characters ?? 8000}
            onKeyDown={event => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') event.currentTarget.form?.requestSubmit(); }}/>
          <button type="submit" className="chat-send" disabled={!canSend}>Send</button>
        </div>
        <small>{draft.length}/{config?.max_message_characters ?? 8000} characters</small>
      </form>
      <div className={`chat-box chat-agent${speaker === 'ai_1' ? ' is-speaking' : ''}`}>
        <label htmlFor="chat-ai-1">AI #1{speaker === 'ai_1' ? ' · responding' : ''}</label>
        <textarea id="chat-ai-1" value={latest('ai_1')} onChange={event => editLatestAgent('ai_1', event.target.value)} placeholder="AI #1’s reply will appear here." aria-label="AI #1 latest reply; editable"/>
      </div>
      <div className={`chat-box chat-agent${speaker === 'ai_2' ? ' is-speaking' : ''}`}>
        <label htmlFor="chat-ai-2">AI #2{speaker === 'ai_2' ? ' · responding' : ''}</label>
        <textarea id="chat-ai-2" value={latest('ai_2')} onChange={event => editLatestAgent('ai_2', event.target.value)} placeholder="AI #2’s reply will appear here." aria-label="AI #2 latest reply; editable"/>
      </div>
    </section>
    {!!messages.length && <ol className="chat-history" aria-label="Conversation history">
      {messages.map((message, index) => <li key={`${message.speaker}-${index}`} className={`chat-history-${message.speaker}`}>
        <strong>{labels[message.speaker]}</strong><p>{message.text}</p>
      </li>)}
    </ol>}
    <div className="chat-controls">
      {running
        ? <button type="button" className="chat-stop" onClick={stopConversation}>Stop exchange</button>
        : <button type="button" className="chat-clear" disabled={!messages.length} onClick={clearConversation}>Clear conversation</button>}
      <span role="status" aria-live="polite">{running ? `${labels[speaker ?? 'ai_1']} is responding…` : notice}</span>
    </div>
    {config && !config.available && <p className="chat-error" role="status">{config.message || 'Connect an AI account to start chatting.'}</p>}
    {error && <p className="chat-error" role="alert">{error}</p>}
    <p className="chat-privacy-note">Conversation text stays in this browser session and is sent to the selected AI provider for each turn. It is not saved as a SIGMA project.</p>
  </main>;
}
