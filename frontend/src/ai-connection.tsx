import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import './ai-connection.css';

export type ConnectionInfo = { mode: 'chatgpt' | 'api_key' | 'unknown'; status: string; label: string; guidance: string; checked_at: string | null; ttl_seconds: number; account_label?: string; active_account?: string; accounts: { id: string; label: string }[]; welcome_pending?: boolean };
type SignInOptions = { newAccount?: boolean; accountId?: string; enablePlan?: boolean; signal?: AbortSignal };
type AIState = { info: ConnectionInfo | null; checking: boolean; initialLoading: boolean; backgroundRefreshing: boolean; healthError: boolean; connecting: boolean; transitioning: boolean; error: string; handoff: string; welcome: boolean; dismissWelcome: () => void; refresh: (source?: 'initial' | 'background' | 'manual') => Promise<ConnectionInfo>; signIn: (options?: SignInOptions) => Promise<boolean>; cancelSignIn: () => void; selectMode: (mode: 'chatgpt' | 'api_key', accountId?: string) => Promise<void>; disconnect: () => Promise<void> };
const Context = createContext<AIState | null>(null);
const providerActivity = new Set<string>();
const providerActivityListeners = new Set<() => void>();
let providerActivitySequence = 0;
const researchActivityMonitors = new Set<string>();
function publishProviderActivity() { providerActivityListeners.forEach(listener => listener()); }
export function setProviderActivity(key: string, active: boolean) {
  const changed = active ? !providerActivity.has(key) : providerActivity.has(key);
  if (!changed) return;
  if (active) providerActivity.add(key); else providerActivity.delete(key);
  publishProviderActivity();
}
export function beginProviderRequest(label: string): () => void {
  const key = `request:${++providerActivitySequence}:${label}`;
  setProviderActivity(key, true);
  return () => setProviderActivity(key, false);
}
export function watchResearchProviderActivity(path: string, projectId: string): () => void {
  if (researchActivityMonitors.has(projectId)) return () => {};
  researchActivityMonitors.add(projectId);
  const activityKey = `research:${projectId}`;
  let stopped = false;
  const poll = async () => {
    if (stopped) return;
    try {
      const response = await fetch(`/api/projects/research-sessions?${new URLSearchParams({ path })}`);
      if (!response.ok) throw new Error('Research activity unavailable');
      const data = await response.json() as { sessions: { status: string; steps: { status: string }[] }[] };
      const activeSessions = data.sessions.filter(item => ['queued', 'running', 'paused'].includes(item.status));
      setProviderActivity(activityKey, activeSessions.some(item => item.steps.some(step => step.status === 'running')));
      if (!activeSessions.length) {
        stopped = true;
        researchActivityMonitors.delete(projectId);
        setProviderActivity(activityKey, false);
        return;
      }
    } catch {
      // Keep the last confirmed activity state and retry; a later connection-state
      // check turns off the green pulse while the local server is unavailable.
    }
    if (!stopped) window.setTimeout(() => void poll(), 900);
  };
  void poll();
  return () => {
    // Continue watching across client navigation until the backend confirms the
    // session has stopped or reached a terminal state.
  };
}
function useProviderActivity() {
  const [active, setActive] = useState(() => providerActivity.size > 0);
  useEffect(() => {
    const update = () => setActive(providerActivity.size > 0);
    providerActivityListeners.add(update);
    update();
    return () => { providerActivityListeners.delete(update); };
  }, []);
  return active;
}
export function useAI() { const value = useContext(Context); if (!value) throw new Error('AI connection context missing'); return value; }
const message = (error: unknown) => error instanceof Error ? error.message : 'Could not reach the local server.';
export async function aiPost<T>(route: string, body: object = {}, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/ai/${route}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal });
  const data = await response.json(); if (!response.ok) throw new Error(data.error ?? 'AI account change failed'); return data;
}
export function AIProvider({ children, unavailable = false }: { children: ReactNode; unavailable?: boolean }) {
  const [info, setInfo] = useState<ConnectionInfo | null>(null);
  const [checking, setChecking] = useState(true);
  const [initialLoading, setInitialLoading] = useState(true);
  const [backgroundRefreshing, setBackgroundRefreshing] = useState(false);
  const [healthError, setHealthError] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  const [error, setError] = useState('');
  const [handoff, setHandoff] = useState('');
  const [welcome, setWelcome] = useState(false);
  const welcomed = useRef(false);
  const retryAttempt = useRef<{ id: string; accountId?: string } | null>(null);
  const pending = useRef<{ controller: AbortController; id?: string } | null>(null);
  const check = useRef<{ promise: Promise<ConnectionInfo>; controller: AbortController; generation: number } | null>(null);
  const generation = useRef(0);
  const retryCount = useRef(0);
  const mounted = useRef(true);
  const transitioningRef = useRef(false);
  const refresh = useCallback((source: 'initial' | 'background' | 'manual' = 'manual'): Promise<ConnectionInfo> => {
    if (unavailable) {
      const guestInfo: ConnectionInfo = { mode: 'unknown', status: 'unconfigured', label: 'Unavailable in Guest mode', guidance: 'Sign in to connect a model.', checked_at: null, ttl_seconds: 0, accounts: [] };
      setInfo(guestInfo); setChecking(false); setInitialLoading(false); setHealthError(false);
      return Promise.resolve(guestInfo);
    }
    if (check.current?.generation === generation.current) return check.current.promise;
    const requestGeneration = generation.current;
    const controller = new AbortController();
    if (source === 'background') setBackgroundRefreshing(true);
    else { setChecking(true); if (source === 'initial') setInitialLoading(true); }
    const request = { promise: Promise.resolve(null as unknown as ConnectionInfo), controller, generation: requestGeneration };
    const promise = (async () => {
      try {
        const response = await fetch('/api/ai/connection?refresh=true', { signal: controller.signal });
        if (!response.ok) throw new Error('Could not read AI connection');
        const data: ConnectionInfo = await response.json();
        if (mounted.current && requestGeneration === generation.current) {
          setInfo(data);
          const failed = data.status === 'unavailable';
          setHealthError(failed);
          retryCount.current = failed ? retryCount.current + 1 : 0;
        }
        return data;
      } catch (error) {
        if (mounted.current && requestGeneration === generation.current && !controller.signal.aborted) {
          setHealthError(true);
          retryCount.current += 1;
        }
        throw error;
      } finally {
        if (mounted.current && requestGeneration === generation.current) {
          setChecking(false);
          setInitialLoading(false);
          setBackgroundRefreshing(false);
        }
        if (check.current === request) check.current = null;
      }
    })();
    request.promise = promise;
    check.current = request;
    return promise;
  }, [unavailable]);
  useEffect(() => {
    mounted.current = true;
    if (unavailable) {
      void refresh('initial');
      return () => { mounted.current = false; };
    }
    void refresh('initial').catch(() => {});
    return () => { mounted.current = false; check.current?.controller.abort(); pending.current?.controller.abort(); };
  }, [refresh, unavailable]);
  useEffect(() => {
    let timer = 0;
    const clear = () => { window.clearTimeout(timer); timer = 0; };
    const eligible = info && (info.status === 'connected' || info.status === 'unavailable') &&
      (info.mode === 'api_key' || (info.mode === 'chatgpt' && !!info.active_account));
    const schedule = () => {
      clear();
      if (document.visibilityState !== 'visible' || !eligible || connecting || transitioning) return;
      let delay: number;
      if (healthError || info.status === 'unavailable') {
        delay = Math.min(300, 30 * 2 ** Math.max(0, retryCount.current - 1)) * 1000;
      } else {
        const checked = info.checked_at ? Date.parse(info.checked_at) : NaN;
        const ttl = Number.isFinite(info.ttl_seconds) && info.ttl_seconds > 0 ? info.ttl_seconds : 60;
        const safeAge = Number.isFinite(checked) && checked <= Date.now() + 60_000 ? checked : Date.now();
        delay = Math.max(0, safeAge + Math.min(50, ttl * 0.8) * 1000 - Date.now());
      }
      timer = window.setTimeout(() => { timer = 0; if (!transitioningRef.current) void refresh('background').catch(() => {}); }, delay);
    };
    const visibility = () => {
      if (document.visibilityState !== 'visible') { clear(); return; }
      if (!eligible || connecting || transitioning || transitioningRef.current) return;
      const checked = info?.checked_at ? Date.parse(info.checked_at) : NaN;
      const ttl = info && Number.isFinite(info.ttl_seconds) && info.ttl_seconds > 0 ? info.ttl_seconds : 60;
      const due = healthError || info?.status === 'unavailable' || !Number.isFinite(checked) || checked > Date.now() + 60_000 || Date.now() >= checked + ttl * 1000;
      if (due) { clear(); void refresh('background').catch(() => {}); } else schedule();
    };
    const online = () => { if (document.visibilityState === 'visible' && healthError && !transitioningRef.current) { clear(); void refresh('background').catch(() => {}); } };
    schedule();
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('online', online);
    return () => { clear(); document.removeEventListener('visibilitychange', visibility); window.removeEventListener('online', online); };
  }, [info, healthError, connecting, transitioning, refresh]);
  useEffect(() => {
    if (info?.welcome_pending && !welcomed.current) {
      welcomed.current = true; setWelcome(true);
      // Record presentation, not a required approval. Closing/restarting never repeats it.
      void aiPost('welcome').catch(() => setError('Could not remember the welcome dismissal; retry connection later.'));
    }
  }, [info]);
  async function signIn(options: SignInOptions = {}): Promise<boolean> {
    if (pending.current) { setError('A ChatGPT sign-in is already pending. Complete or cancel it.'); return false; }
    invalidateChecks();
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
          await refresh('background');
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
  function invalidateChecks() { generation.current += 1; check.current?.controller.abort(); check.current = null; retryCount.current = 0; setHealthError(false); setChecking(false); setInitialLoading(false); setBackgroundRefreshing(false); }
  async function selectMode(mode: 'chatgpt' | 'api_key', accountId?: string) { invalidateChecks(); const selectedGeneration = generation.current; transitioningRef.current = true; setTransitioning(true); cancelSignIn(); setError(''); try { const next = await aiPost<ConnectionInfo>('mode', { mode, account_id: accountId }); if (selectedGeneration === generation.current) setInfo(next); } catch (error) { if (selectedGeneration === generation.current) setError(message(error)); } finally { if (selectedGeneration === generation.current) { transitioningRef.current = false; setTransitioning(false); } } }
  async function disconnect() { invalidateChecks(); const selectedGeneration = generation.current; transitioningRef.current = true; setTransitioning(true); cancelSignIn(); setError(''); try { const result = await aiPost<{ message: string; remote_revocation_confirmed: boolean }>('disconnect'); if (!result.remote_revocation_confirmed) setError(result.message); await refresh('background'); } catch (error) { setError(message(error)); } finally { if (selectedGeneration === generation.current) { transitioningRef.current = false; setTransitioning(false); } } }
  const value = { info, checking, initialLoading, backgroundRefreshing, healthError, connecting, transitioning, error, handoff, welcome, dismissWelcome: () => setWelcome(false), refresh, signIn, cancelSignIn, selectMode, disconnect };
  return <Context.Provider value={value}>{children}{welcome && !document.querySelector('dialog[open]') && <div className="plan-welcome-toast"><PlanWelcome/></div>}</Context.Provider>;
}
export function ManageUsage({ connectionAction = false }: { connectionAction?: boolean } = {}) { return <a className={connectionAction ? 'connection-text-action' : undefined} href="https://chatgpt.com/settings/usage" target="_blank" rel="noreferrer">Manage usage</a>; }
export function PlanWelcome() { const ai = useAI(); return ai.welcome ? <aside className="plan-welcome" aria-label="ChatGPT plan welcome"><strong>You're using your ChatGPT plan</strong><p>Eligible requests use your plan allowance or credits, subject to plan, app and workspace limits.</p><ManageUsage/> <button type="button" onClick={ai.dismissWelcome}>Got it</button></aside> : null; }
export function ConnectAction({ signal }: { signal?: AbortSignal }) {
  const ai = useAI();
  return <div className="ai-connect-actions">
    <button type="button" className="chatgpt-sign-in" disabled={ai.connecting} onClick={() => void ai.signIn({ accountId: ai.info?.active_account, enablePlan: ai.info?.status === 'plan_not_permitted', signal })}><img src="/chatgpt-logo-black.svg" alt="" width="20" height="20"/>Continue with ChatGPT</button>
    {ai.connecting && <><p role="status">Connecting… Complete sign-in in the browser.</p>{ai.handoff && <a href={ai.handoff} target="_blank" rel="noreferrer">Open sign-in browser</a>}<button type="button" className="connection-text-action" onClick={ai.cancelSignIn}>Cancel sign-in</button></>}
  </div>;
}
export function ConnectionStatus({ disabled = false, projectHeader = false, cloudFunding, googleAccount, onGoogleSignOut, guestAccount }: { disabled?: boolean; projectHeader?: boolean; cloudFunding?: { target: 'local' | 'hosted'; authenticationEnabled: boolean; budget: { allowance_usd: number; estimated_usage_usd: number; held_usd: number; remaining_usd: number; unknown_provider_attempts: number } | null; loading: boolean; error: string | null; authorized: boolean; provider: { status: string; guidance: string } | null; providerLoading: boolean; providerError: string | null; retryProvider: () => Promise<void>; selectedConnection?: 'personal' | 'sponsored'; selectConnection?: (mode: 'personal' | 'sponsored') => Promise<void>; connectionError?: string | null; selectingConnection?: boolean }; googleAccount?: { role: string; email: string } | null; onGoogleSignOut?: () => Promise<void>; guestAccount?: { ready: boolean; deniedEmail?: string | null; invitationControls?: ReactNode } } = {}) {
  const ai = useAI(); const disclosure = useRef<HTMLDetailsElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ top: number; right: number } | null>(null);
  const [accountError, setAccountError] = useState('');
  const providerActive = useProviderActivity();
  useEffect(() => {
    if (!guestAccount) return;
    const openSignIn = () => setOpen(true);
    window.addEventListener('sigma-open-google-signin', openSignIn);
    return () => window.removeEventListener('sigma-open-google-signin', openSignIn);
  }, [guestAccount]);
  useEffect(() => {
    if (!open) return;
    const place = () => {
      const trigger = disclosure.current?.querySelector('summary');
      const rect = trigger?.getBoundingClientRect();
      if (!rect || !panel.current) return;
      const panelRect = panel.current.getBoundingClientRect();
      const below = rect.bottom + 8 + panelRect.height <= window.innerHeight - 8;
      const preferredRight = Math.max(8, window.innerWidth - rect.right);
      const right = Math.min(preferredRight, Math.max(8, window.innerWidth - panelRect.width - 8));
      setPosition({ top: below ? rect.bottom + 8 : Math.max(8, rect.top - panelRect.height - 8), right });
    };
    const frame = requestAnimationFrame(() => {
      place();
      panel.current?.querySelector<HTMLElement>('button:not(:disabled), a, select, summary')?.focus();
    });
    window.addEventListener('resize', place); window.addEventListener('scroll', place, true);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); };
  }, [open]);
  useEffect(() => {
    function escape(event: KeyboardEvent) {
      if (event.key === 'Escape' && open) { event.preventDefault(); setOpen(false); requestAnimationFrame(() => disclosure.current?.querySelector('summary')?.focus()); }
      if (event.key !== 'Tab' || !open || !panel.current) return;
      const items = Array.from(panel.current.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], select:not(:disabled), summary, [tabindex="0"]')).filter(item => item.offsetParent !== null);
      if (!items.length) { event.preventDefault(); panel.current.focus(); return; }
      const first = items[0]; const last = items.at(-1)!;
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener('keydown', escape); return () => document.removeEventListener('keydown', escape);
  }, [open]);
  const status = ai.connecting ? 'connecting' : ai.initialLoading ? 'checking' : ai.healthError ? 'stale' : ai.info?.status ?? 'unknown';
  const label = ai.connecting ? 'Connecting…' : ai.initialLoading ? 'Checking AI…' : ai.healthError && ai.info?.status !== 'unavailable' ? 'AI status unavailable' : ai.info?.label ?? 'Connect AI';
  const serviceFunded = cloudFunding?.target === 'hosted';
  const localGoogleRequired = projectHeader && cloudFunding?.target === 'local' && cloudFunding.authenticationEnabled && !cloudFunding.authorized;
  const projectHeaderLabel = serviceFunded
    ? cloudFunding?.selectedConnection === 'sponsored' ? 'ChatGPT · SIGMA allowance' : 'ChatGPT · personal connection'
    : localGoogleRequired
      ? 'ChatGPT sign-in · Google sign-in required'
    : status === 'connected' && ai.info?.mode === 'chatgpt' && ai.info.active_account
    ? 'ChatGPT connected'
    : status === 'connected' && ai.info?.mode === 'api_key'
      ? 'OpenAI API connected'
      : `ChatGPT sign-in · ${label}`;
  const interactionDisabled = disabled || (localGoogleRequired && !guestAccount);
  const dotActive = !projectHeader && status === 'connected' && providerActive;
  const visibleLabel = projectHeader ? projectHeaderLabel : label;
  const roleLabel = googleAccount?.role === 'admin' ? 'Administrator' : 'Regular user';
  const modelLine = serviceFunded
    ? cloudFunding?.selectedConnection === 'personal' ? 'Personal ChatGPT · unavailable'
      : cloudFunding?.budget?.remaining_usd === 0 ? 'SIGMA-sponsored · allowance exhausted'
        : cloudFunding?.providerLoading ? 'Checking SIGMA-sponsored access…'
        : cloudFunding?.providerError ? 'SIGMA-sponsored check failed'
          : cloudFunding?.provider?.status === 'connected' ? 'SIGMA-sponsored'
            : cloudFunding?.provider?.status === 'unconfigured' ? 'SIGMA-sponsored · not configured'
              : cloudFunding?.provider?.status === 'unauthorized' ? 'SIGMA-sponsored · credential rejected'
                : cloudFunding?.provider ? 'SIGMA-sponsored · provider unavailable' : 'Checking SIGMA-sponsored access…'
    : ai.connecting || ai.initialLoading ? 'Checking personal model…'
      : ai.healthError || ai.info?.status === 'unavailable' ? 'Personal model check failed'
        : ai.info?.status === 'connected' ? 'Personal model connected'
          : ai.info?.status === 'unauthorized' || ai.info?.status === 'reauth_required' ? 'Personal model needs sign-in'
            : ai.info?.status === 'unconfigured' || ai.info?.status === 'disconnected' ? 'Personal model not configured'
              : ai.info?.label ?? 'Personal model status unavailable';
  return <details ref={disclosure} className={`api-connection${projectHeader ? ' project-chatgpt-signin' : ''}${googleAccount ? ' account-model-status' : ''}`} open={open} onToggle={event => setOpen(event.currentTarget.open)}><summary aria-label={guestAccount ? 'Guest, Explore only; open account settings' : googleAccount ? `${roleLabel}, ${modelLine}; open account and model settings` : projectHeader ? `${visibleLabel}; open AI connection settings` : 'AI connection settings'} data-tooltip-disabled={projectHeader ? '' : undefined} aria-haspopup="dialog" aria-expanded={open} aria-disabled={interactionDisabled} tabIndex={interactionDisabled ? -1 : 0} onClick={event => { if (interactionDisabled) event.preventDefault(); }}><span className={`connection-dot connection-${status}${dotActive ? ' connection-active' : ''}`} aria-hidden="true"/>{guestAccount ? <span className="account-model-lines"><span role="status">Guest</span><span>Explore only · no execution</span></span> : googleAccount ? <span className="account-model-lines"><span role="status">{roleLabel}</span><span>{modelLine}</span></span> : <span role="status">{visibleLabel}</span>}</summary>
    {open && createPortal(<>
    <div className="connection-backdrop" onPointerDown={event => { if (event.target === event.currentTarget) { event.preventDefault(); setOpen(false); requestAnimationFrame(() => disclosure.current?.querySelector('summary')?.focus()); } }}/>
    <div ref={panel} className="connection-details" role="dialog" aria-modal="true" aria-label={guestAccount || googleAccount ? "Account and model settings" : "AI connection settings"} tabIndex={-1} style={position ? { top: position.top, right: position.right } : undefined}>
      {guestAccount ? <section className="account-identity-state"><h2>Guest · Explore SIGMA</h2><p>Published research is available without signing in. A verified invitation is required for a private workspace and model access.</p>{guestAccount.deniedEmail && <p role="status">Access is not granted for {guestAccount.deniedEmail}.</p>}{guestAccount.invitationControls}{guestAccount.ready ? <a className="connection-text-action" href="/api/cloud-auth/login">Sign in with Google</a> : <p role="status">Google sign-in is not configured on this server.</p>}</section> : <>{googleAccount && <section className="account-identity-state"><h2>{roleLabel}</h2><p>{googleAccount.email}</p><p>Invitation access is verified by SIGMA for this Google account.</p>{onGoogleSignOut && <button type="button" className="connection-text-action" onClick={() => { setAccountError(''); void onGoogleSignOut().catch(cause => setAccountError(message(cause))); }}>Sign out of Google</button>}</section>}
      {!guestAccount && (serviceFunded ? <>
        <h2>Model access</h2>
        <p>Choose which connection SIGMA will use. The choice is saved for this Google account. SIGMA never switches funding paths automatically.</p>
        <section className="account-model-choice" aria-label="Personal ChatGPT connection">
          <p><strong>Connect your own ChatGPT account through OpenAI authentication.</strong></p>
          <button type="button" className="connection-text-action" aria-pressed={cloudFunding?.selectedConnection === 'personal'} disabled={cloudFunding?.selectingConnection || cloudFunding?.selectedConnection === 'personal'} onClick={() => void cloudFunding?.selectConnection?.('personal')}>{cloudFunding?.selectedConnection === 'personal' ? 'Personal connection selected' : 'Use personal connection'}</button>
          {cloudFunding?.selectedConnection === 'personal' && <p role="status">Hosted personal ChatGPT authentication is unavailable until an approved access path is established. No personal credential is transferred or used.</p>}
        </section>
        {cloudFunding?.authorized && cloudFunding.budget && cloudFunding.budget.remaining_usd > 0 && <button type="button" className="connection-text-action" aria-pressed={cloudFunding.selectedConnection === 'sponsored'} disabled={cloudFunding.selectingConnection || cloudFunding.selectedConnection === 'sponsored'} onClick={() => void cloudFunding?.selectConnection?.('sponsored')}>Or you can use your allowance that's on us.</button>}
        {cloudFunding?.selectedConnection === 'sponsored' && <section className="account-model-choice" aria-label="SIGMA-sponsored connection">
          <h3>SIGMA-sponsored ChatGPT</h3>
          <p>Inference uses SIGMA's designated sponsor connection and the allowance below. It does not use a personal ChatGPT credential.</p>
          {cloudFunding?.providerLoading && <p role="status">Checking sponsored provider authentication and model-catalog reachability. This check does not send a research prompt.</p>}
          {!cloudFunding?.providerLoading && cloudFunding?.provider?.status === 'connected' && <p role="status">The SIGMA-sponsored model connection is reachable. This does not guarantee a particular inference will complete.</p>}
          {!cloudFunding?.providerLoading && cloudFunding?.provider?.status === 'unconfigured' && <p role="status">SIGMA-sponsored model access is not configured. Contact the administrator. SIGMA will not switch to personal or separately billed credentials.</p>}
          {!cloudFunding?.providerLoading && cloudFunding?.provider?.status === 'unauthorized' && <p role="alert">The SIGMA-sponsored credential was rejected. Contact the administrator; SIGMA will not use a personal billing path.</p>}
          {(cloudFunding?.providerError || ['unavailable', 'invalid_response', 'forbidden', 'limited', 'disconnected', 'reauth_required', 'plan_not_permitted'].includes(cloudFunding?.provider?.status ?? '')) && <p role="alert">{cloudFunding?.providerError ?? cloudFunding?.provider?.guidance ?? 'The sponsored provider could not be reached.'} Retry the check. No research was run.</p>}
          <button type="button" className="connection-text-action" disabled={cloudFunding?.providerLoading} onClick={() => void cloudFunding?.retryProvider()}>{cloudFunding?.providerLoading ? 'Checking…' : 'Retry sponsored connection check'}</button>
          <p>SIGMA-sponsored inference · separate from a personal ChatGPT plan.</p>
        </section>}
        {cloudFunding?.authorized && <p className="cloud-chatgpt-allowance"><strong>ChatGPT allowance</strong>{cloudFunding.budget ? <span>{new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(cloudFunding.budget.remaining_usd)} remaining</span> : cloudFunding.loading ? <span>Loading…</span> : <span>{cloudFunding.error ?? 'Unavailable'}</span>}</p>}
        {cloudFunding?.authorized && cloudFunding.budget && <p className="cloud-chatgpt-usage">Estimated {new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(cloudFunding.budget.estimated_usage_usd)} · held {new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(cloudFunding.budget.held_usd)}{cloudFunding.budget.unknown_provider_attempts ? ` · ${cloudFunding.budget.unknown_provider_attempts} unknown-charge attempts` : ''}</p>}
        {cloudFunding?.connectionError && <p role="alert">{cloudFunding.connectionError}</p>}
        {cloudFunding?.error && <p role="status">{cloudFunding.error} Saved research remains available.</p>}
        {cloudFunding?.budget && cloudFunding.budget.remaining_usd <= 0 && <p role="status">This sponsored allowance is exhausted. Sponsored inference is disabled; switch to a personal connection or continue with saved research.</p>}
      </> : <>
        {googleAccount && <h2>Personal model connection</h2>}
        {ai.initialLoading && <p role="status">Checking the configured personal model connection. SIGMA checks provider authentication and reachability; it does not send a research prompt.</p>}
        {!ai.initialLoading && ai.info?.status === 'connected' && <p role="status">The configured personal model connection is reachable. No research was run.</p>}
        {!ai.initialLoading && ai.info?.status === 'unconfigured' && <p role="status">No personal model connection is configured. Connect your ChatGPT account or choose the separately billed API key option.</p>}
        {!ai.initialLoading && ai.info?.status === 'unauthorized' && <p role="status">The provider rejected the saved credential. Sign in again to restore this connection.</p>}
        {!ai.initialLoading && (ai.healthError || ai.info?.status === 'unavailable') && <p role="status">SIGMA could not reach the model provider. Retry the connection check; no research was run.</p>}
        {ai.info?.account_label && <p className="account-label">{ai.info.account_label}</p>}
        {(ai.info?.mode === 'api_key' || !ai.info?.active_account) && <p>{ai.info?.mode === 'api_key' ? 'OpenAI API · billed separately' : 'Connect your ChatGPT account'}</p>}
        <p>{ai.healthError && ai.info?.status !== 'unavailable' ? 'Connection status could not be refreshed. Retry when convenient.' : ai.info?.guidance ?? 'Manual research is always available.'}</p>
        {ai.info?.mode !== 'api_key' && <>{['disconnected', 'reauth_required', 'unauthorized', 'plan_not_permitted'].includes(ai.info?.status ?? 'disconnected') && <ConnectAction/>}{ai.info?.active_account && <div className="connection-usage-actions"><ManageUsage connectionAction/><button type="button" className="connection-text-action" disabled={ai.connecting || ai.transitioning} onClick={() => void ai.disconnect()}>Disconnect</button></div>}</>}
        {ai.info?.active_account && <button type="button" className="connection-text-action" disabled={ai.connecting || ai.transitioning} onClick={() => void ai.signIn({ newAccount: true })}>Connect another account</button>}
        <button type="button" className="connection-text-action" disabled={ai.checking || ai.connecting || ai.transitioning} onClick={() => void ai.refresh('manual').catch(() => {})}>{ai.checking ? 'Checking…' : 'Retry connection'}</button>
        {ai.info?.mode === 'api_key' ? <button type="button" className="connection-text-action" onClick={() => void ai.selectMode('chatgpt')}>Use ChatGPT plan</button> : <details className="advanced-ai"><summary>API key option</summary><p>Uses OPENAI_API_KEY from this checkout's .env or server environment. API usage is billed separately from your ChatGPT plan. No enable switch is needed.</p><button type="button" className="connection-text-action" onClick={() => void ai.selectMode('api_key')}>Separately billed API Key</button></details>}
      </>)}
      </>}
      {!guestAccount && ai.error && <p role="alert">{ai.error}</p>}
      {accountError && <p role="alert">{accountError}</p>}
    </div></>, document.body)}
  </details>;
}
