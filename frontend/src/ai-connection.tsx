import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import './ai-connection.css';

export type ConnectionInfo = { mode: 'chatgpt' | 'api_key' | 'unknown'; status: string; label: string; guidance: string; checked_at: string | null; ttl_seconds: number; account_label?: string; active_account?: string; accounts: { id: string; label: string }[]; welcome_pending?: boolean };
type SignInOptions = { newAccount?: boolean; accountId?: string; enablePlan?: boolean; signal?: AbortSignal };
type AIState = { info: ConnectionInfo | null; checking: boolean; connecting: boolean; error: string; handoff: string; welcome: boolean; dismissWelcome: () => void; refresh: () => Promise<ConnectionInfo>; signIn: (options?: SignInOptions) => Promise<boolean>; cancelSignIn: () => void; selectMode: (mode: 'chatgpt' | 'api_key', accountId?: string) => Promise<void>; disconnect: () => Promise<void> };
const Context = createContext<AIState | null>(null);
export function useAI() { const value = useContext(Context); if (!value) throw new Error('AI connection context missing'); return value; }
const message = (error: unknown) => error instanceof Error ? error.message : 'Could not reach the local server.';
export async function aiPost<T>(route: string, body: object = {}, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/ai/${route}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal });
  const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'AI account change failed'); return data;
}
export function AIProvider({ children }: { children: ReactNode }) {
  const [info, setInfo] = useState<ConnectionInfo | null>(null);
  const [checking, setChecking] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState('');
  const [handoff, setHandoff] = useState('');
  const [welcome, setWelcome] = useState(false);
  const welcomed = useRef(false);
  const retryAttempt = useRef<{ id: string; accountId?: string } | null>(null);
  const pending = useRef<{ controller: AbortController; id?: string } | null>(null);
  const check = useRef<Promise<ConnectionInfo> | null>(null);
  const refresh = useCallback((): Promise<ConnectionInfo> => {
    if (check.current) return check.current;
    setChecking(true);
    const promise = (async () => {
      try { const response = await fetch('/api/ai/connection?refresh=true'); if (!response.ok) throw new Error('Could not read AI connection'); const data: ConnectionInfo = await response.json(); setInfo(data); return data; }
      finally { setChecking(false); check.current = null; }
    })(); check.current = promise; return promise;
  }, []);
  useEffect(() => { void refresh().catch(error => setError(message(error))); return () => pending.current?.controller.abort(); }, [refresh]);
  useEffect(() => {
    if (info?.welcome_pending && !welcomed.current) {
      welcomed.current = true; setWelcome(true);
      // Record presentation, not a required approval. Closing/restarting never repeats it.
      void aiPost('welcome').catch(() => setError('Could not remember the welcome dismissal; retry connection later.'));
    }
  }, [info]);
  async function signIn(options: SignInOptions = {}): Promise<boolean> {
    if (pending.current) { setError('A ChatGPT sign-in is already pending. Complete or cancel it.'); return false; }
    const controller = new AbortController(); const attempt = { controller, id: undefined as string | undefined }; pending.current = attempt;
    const abort = () => controller.abort(); options.signal?.addEventListener('abort', abort, { once: true });
    if (options.signal?.aborted) controller.abort();
    // Open on the user's click; never open provider pages on application startup.
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const fallbackFocus = trigger?.closest(".api-connection")?.querySelector<HTMLDetailsElement>("summary");
    const popup = controller.signal.aborted ? null : window.open('about:blank', '_blank'); if (popup) popup.opener = null;
    setConnecting(true); setError('');
    try {
      const data = await aiPost<{ id: string; authorization_url: string }>('auth/begin', { account_id: options.accountId, enable_plan: !!options.enablePlan, retry_attempt_id: !options.newAccount && retryAttempt.current?.accountId === options.accountId ? retryAttempt.current?.id : undefined }, controller.signal);
      attempt.id = data.id;
      const url = new URL(data.authorization_url, window.location.origin);
      if (url.origin !== window.location.origin || url.pathname !== `/api/ai/auth/open/${data.id}` || url.search || url.hash) throw new Error('Unsafe sign-in handoff rejected.');
      if (!popup) setHandoff(url.href);
      if (popup) popup.location.replace(url.href);
      const deadline = Date.now() + 305000;
      while (!controller.signal.aborted && Date.now() < deadline) {
        const response = await fetch(`/api/ai/auth/attempt/${encodeURIComponent(data.id)}`, { signal: controller.signal });
        const state = await response.json(); if (!response.ok) throw new Error(state.error ?? 'Sign-in session lost. Retry.');
        if (state.status !== 'connecting') {
          await refresh();
          if (state.status === 'connected') { retryAttempt.current = null; return true; }
          retryAttempt.current = state.retryable ? { id: data.id, accountId: options.accountId } : null;
          setError(state.message); return false;
        }
        await new Promise<void>(resolve => { const done = () => { clearTimeout(timer); controller.signal.removeEventListener('abort', done); resolve(); }; const timer = window.setTimeout(done, 500); controller.signal.addEventListener('abort', done, { once: true }); });
      }
      return false;
    } catch (error) { if (!controller.signal.aborted) setError(message(error)); return false; }
    finally {
      if (attempt.id && controller.signal.aborted) await aiPost(`auth/cancel/${encodeURIComponent(attempt.id)}`).catch(() => {});
      popup?.close();
      if (trigger?.isConnected) trigger.focus(); else if (fallbackFocus?.isConnected) fallbackFocus.focus();
      options.signal?.removeEventListener('abort', abort);
      pending.current = null; setConnecting(false); setHandoff('');
    }
  }
  function cancelSignIn() { pending.current?.controller.abort(); }
  async function selectMode(mode: 'chatgpt' | 'api_key', accountId?: string) { cancelSignIn(); setError(''); try { setInfo(await aiPost<ConnectionInfo>('mode', { mode, account_id: accountId })); } catch (error) { setError(message(error)); } }
  async function disconnect() { cancelSignIn(); setError(''); try { const result = await aiPost<{ message: string; remote_revocation_confirmed: boolean }>('disconnect'); if (!result.remote_revocation_confirmed) setError(result.message); await refresh(); } catch (error) { setError(message(error)); } }
  const value = { info, checking, connecting, error, handoff, welcome, dismissWelcome: () => setWelcome(false), refresh, signIn, cancelSignIn, selectMode, disconnect };
  return <Context.Provider value={value}>{children}{welcome && !document.querySelector('dialog[open]') && <div className="plan-welcome-toast"><PlanWelcome/></div>}</Context.Provider>;
}
export function ManageUsage() { return <a href="https://chatgpt.com/settings/usage" target="_blank" rel="noreferrer">Manage usage</a>; }
export function PlanWelcome() { const ai = useAI(); return ai.welcome ? <aside className="plan-welcome" aria-label="ChatGPT plan welcome"><strong>You're using your ChatGPT plan</strong><p>Eligible requests use your plan allowance or credits, subject to plan, app and workspace limits.</p><ManageUsage/> <button type="button" onClick={ai.dismissWelcome}>Got it</button></aside> : null; }
export function ConnectAction({ signal }: { signal?: AbortSignal }) {
  const ai = useAI();
  return <div className="ai-connect-actions">
    <button type="button" className="chatgpt-sign-in" disabled={ai.connecting} onClick={() => void ai.signIn({ accountId: ai.info?.active_account, enablePlan: ai.info?.status === 'plan_not_permitted', signal })}><img src="/chatgpt-logo-black.svg" alt="" width="20" height="20"/>Continue with ChatGPT</button>
    {ai.connecting && <><p role="status">Connecting… Complete sign-in in the browser.</p>{ai.handoff && <a href={ai.handoff} target="_blank" rel="noreferrer">Open sign-in browser</a>}<button type="button" onClick={ai.cancelSignIn}>Cancel sign-in</button></>}
  </div>;
}
export function ConnectionStatus() {
  const ai = useAI(); const disclosure = useRef<HTMLDetailsElement>(null);
  const [stale, setStale] = useState(false);
  useEffect(() => {
    function outside(event: PointerEvent) { if (event.target instanceof Node && disclosure.current && !disclosure.current.contains(event.target)) disclosure.current.open = false; }
    function escape(event: KeyboardEvent) { if (event.key === 'Escape' && disclosure.current?.open) { disclosure.current.open = false; disclosure.current.querySelector('summary')?.focus(); } }
    document.addEventListener('pointerdown', outside); document.addEventListener('keydown', escape); return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, []);
  useEffect(() => { setStale(false); if (!ai.info?.checked_at || ai.info.status !== 'connected') return; const timer = window.setTimeout(() => setStale(true), Math.max(0, Date.parse(ai.info.checked_at) + ai.info.ttl_seconds * 1000 - Date.now())); return () => clearTimeout(timer); }, [ai.info]);
  const status = ai.connecting ? 'connecting' : ai.checking ? 'checking' : stale ? 'stale' : ai.info?.status ?? 'unknown';
  const label = ai.connecting ? 'Connecting…' : ai.checking ? 'Checking AI…' : stale ? 'AI connection check expired' : ai.info?.label ?? 'Connect AI';
  return <details ref={disclosure} className="api-connection"><summary aria-label="AI connection settings"><span className={`connection-dot connection-${status}`} aria-hidden="true"/><span role="status">{label}</span></summary>
    <div className="connection-details">
      {ai.info?.account_label && <p className="account-label">{ai.info.account_label}</p>}
      <p>{ai.info?.mode === 'api_key' ? 'OpenAI API · billed separately' : ai.info?.active_account ? 'Using ChatGPT plan' : 'Connect your ChatGPT account'}</p>
      <p>{stale ? 'Retry to verify the current account connection.' : ai.info?.guidance ?? 'Manual research is always available.'}</p>
      {ai.info?.mode !== 'api_key' && <>{['disconnected', 'reauth_required', 'unauthorized', 'plan_not_permitted'].includes(ai.info?.status ?? 'disconnected') && <ConnectAction/>}{ai.info?.active_account && <><ManageUsage/><button type="button" disabled={ai.connecting} onClick={() => void ai.disconnect()}>Disconnect</button></>}</>}
      {!!ai.info?.accounts?.length && <label>Switch account<select aria-label="Switch ChatGPT account" value={ai.info.active_account ?? ''} onChange={event => void ai.selectMode('chatgpt', event.target.value)}>{ai.info.accounts.map(account => <option key={account.id} value={account.id}>{account.label}</option>)}</select></label>}
      {ai.info?.active_account && <button type="button" disabled={ai.connecting} onClick={() => void ai.signIn({ newAccount: true })}>Connect another account</button>}
      <button type="button" disabled={ai.checking || ai.connecting} onClick={() => void ai.refresh().catch(() => {})}>Retry connection</button>
      {ai.info?.mode === 'api_key' ? <button type="button" onClick={() => void ai.selectMode('chatgpt')}>Use ChatGPT plan</button> : <details className="advanced-ai"><summary>Use API key (advanced)</summary><p>Uses OPENAI_API_KEY from this checkout's .env or server environment. API usage is billed separately from your ChatGPT plan. No enable switch is needed.</p><button type="button" onClick={() => void ai.selectMode('api_key')}>Use API key · billed separately</button></details>}
      {ai.error && <p role="alert">{ai.error}</p>}
    </div>
  </details>;
}
