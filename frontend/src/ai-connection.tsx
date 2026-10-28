import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import './ai-connection.css';

export type ConnectionInfo = { mode: 'chatgpt' | 'api_key' | 'unknown'; status: string; label: string; guidance: string; checked_at: string | null; ttl_seconds: number; account_label?: string; active_account?: string; accounts: { id: string; label: string }[]; welcome_pending?: boolean };
type SignInOptions = { newAccount?: boolean; accountId?: string; enablePlan?: boolean; sponsor?: boolean; signal?: AbortSignal };
type AIState = { info: ConnectionInfo | null; checking: boolean; initialLoading: boolean; backgroundRefreshing: boolean; healthError: boolean; connecting: boolean; transitioning: boolean; error: string; handoff: string; welcome: boolean; dismissWelcome: () => void; refresh: (source?: 'initial' | 'background' | 'manual') => Promise<ConnectionInfo>; signIn: (options?: SignInOptions) => Promise<boolean>; cancelSignIn: () => void; selectMode: (mode: 'chatgpt' | 'api_key', accountId?: string) => Promise<void>; disconnect: () => Promise<boolean> };
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
  return () => {
    setProviderActivity(key, false);
    window.dispatchEvent(new Event('sigma-sponsored-budget-refresh'));
  };
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
  let data: { error?: string; detail?: string };
  try { data = await response.json() as typeof data; }
  catch { data = {}; }
  if (!response.ok) throw new Error(data.error ?? data.detail ?? 'AI account change failed');
  return data as T;
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
          window.dispatchEvent(new Event('sigma-cloud-auth-refresh'));
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
      const data = await aiPost<{ id: string; authorization_url: string }>(options.sponsor ? 'sponsor-auth/begin' : 'auth/begin', { account_id: options.accountId, enable_plan: !!options.enablePlan, retry_attempt_id: !options.newAccount && retryAttempt.current?.accountId === options.accountId ? retryAttempt.current?.id : undefined }, controller.signal);
      attempt.id = data.id;
      const url = new URL(data.authorization_url, window.location.origin);
      if (url.origin !== window.location.origin || url.pathname !== `/api/ai/auth/open/${data.id}` || url.search || url.hash) throw new Error('Unsafe sign-in handoff rejected.');
      if (!popup) setHandoff(url.href);
      if (popup) popup.location.replace(url.href);
      const deadline = Date.now() + 305000;
      let popupClosedDeadline: number | null = null;
      while (!controller.signal.aborted && Date.now() < deadline) {
        const response = await fetch(`/api/ai/auth/attempt/${encodeURIComponent(data.id)}`, { signal: controller.signal });
        const state = await response.json(); if (!response.ok) throw new Error(state.error ?? 'Sign-in session lost. Retry.');
        if (state.status !== 'connecting') {
          await refresh('background');
          if (state.status === 'connected') { retryAttempt.current = null; return true; }
          retryAttempt.current = state.retryable ? { id: data.id, accountId: options.accountId } : null;
          setError(state.message); return false;
        }
        if (popup?.closed) {
          popupClosedDeadline ??= Date.now() + 10000;
          if (Date.now() >= popupClosedDeadline) {
            setError('ChatGPT sign-in was closed before SIGMA confirmed the connection. Retry sign-in.');
            controller.abort(); return false;
          }
        }
        await new Promise<void>(resolve => { const done = () => { clearTimeout(timer); controller.signal.removeEventListener('abort', done); resolve(); }; const timer = window.setTimeout(done, popupClosedDeadline === null ? 500 : 250); controller.signal.addEventListener('abort', done, { once: true }); });
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
  async function disconnect() { invalidateChecks(); const selectedGeneration = generation.current; transitioningRef.current = true; setTransitioning(true); cancelSignIn(); setError(''); try { await aiPost<{ message: string; remote_revocation_confirmed: boolean }>('disconnect'); setInfo(current => current ? { ...current, status: 'disconnected', label: 'Connect to ChatGPT', account_label: undefined, active_account: undefined, checked_at: new Date().toISOString() } : current); await refresh('background'); return true; } catch (error) { if (selectedGeneration === generation.current) setError(message(error)); return false; } finally { if (selectedGeneration === generation.current) { transitioningRef.current = false; setTransitioning(false); } } }
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
export function ConnectionStatus({ projectHeader = false, cloudFunding, zeroAllowanceAction }: { projectHeader?: boolean; zeroAllowanceAction?: ReactNode; cloudFunding?: { target: 'local' | 'hosted'; authenticationEnabled: boolean; googleAccount: string | null; budget: { allowance_usd: number; estimated_usage_usd: number; held_usd: number; remaining_usd: number; unknown_provider_attempts: number } | null; loading: boolean; error: string | null; authorized: boolean; sponsorshipEligible?: boolean; sponsorshipUnlimited?: boolean; provider: { status: string; guidance: string } | null; providerLoading: boolean; providerError: string | null; retryProvider: () => Promise<void>; selectedConnection?: 'personal' | 'sponsored'; selectConnection?: (mode: 'personal' | 'sponsored') => Promise<void>; connectionError?: string | null; selectingConnection?: boolean; forcedSponsored?: boolean; simulatedSponsored?: boolean; disconnectMockSponsored?: () => Promise<void> } } = {}) {
  const ai = useAI();
  const [allowanceTipOpen, setAllowanceTipOpen] = useState(false);
  const providerActive = useProviderActivity();
  const status = ai.connecting ? 'connecting' : ai.initialLoading ? 'checking' : ai.healthError ? 'stale' : ai.info?.status ?? 'unknown';
  const dotActive = !projectHeader && status === 'connected' && providerActive;
  const hosted = cloudFunding?.target === 'hosted';
  const simulatedSponsored = !!cloudFunding?.simulatedSponsored;
  const hostedPillLabel = 'Sponsored ChatGPT';
  const sponsoredSelected = cloudFunding?.selectedConnection === 'sponsored';
  const adminSponsored = sponsoredSelected && !!cloudFunding?.sponsorshipUnlimited;
  const sponsoredPill = !!hosted || (!!cloudFunding?.authorized && !!cloudFunding.sponsorshipEligible && sponsoredSelected);
  const localSponsorNeedsReconnect = cloudFunding?.target === 'local'
    && !simulatedSponsored
    && !!cloudFunding.authorized
    && !!cloudFunding.sponsorshipEligible
    && sponsoredSelected
    && ai.info?.mode === 'chatgpt'
    && ['reauth_required', 'disconnected', 'unauthorized', 'plan_not_permitted'].includes(ai.info.status);
  const googleRequired = !!cloudFunding?.authenticationEnabled && !cloudFunding.authorized;
  // Keep the ChatGPT credential intact while Google is signed out, but present
  // the pill as unavailable until an authorized Google session returns.
  const hostedConnected = hosted && sponsoredSelected && cloudFunding?.provider?.status === 'connected';
  const forcedSponsored = !!cloudFunding?.forcedSponsored && !!cloudFunding?.authorized;
  const connected = (hosted ? hostedConnected : simulatedSponsored
    ? sponsoredPill && sponsoredSelected && cloudFunding?.provider?.status === 'connected'
    : status === 'connected') && !googleRequired;
  const disabled = (!hosted && (ai.connecting || ai.transitioning)) || googleRequired || !!cloudFunding?.selectingConnection;
  const dotStatus = simulatedSponsored
    ? (connected ? 'connected' : 'disconnected')
    : projectHeader ? (connected ? 'connected' : 'disconnected') : hosted ? (connected ? 'connected' : 'disconnected') : status;
  const visibleLabel = sponsoredPill
    ? (hosted || simulatedSponsored) && (cloudFunding?.selectingConnection || cloudFunding?.providerLoading)
      ? 'Connecting to SIGMA-sponsored API…'
      : hostedPillLabel
    : connected ? 'ChatGPT connected' : ai.connecting ? 'Connecting to ChatGPT…' : 'Connect to ChatGPT';
  const connectionTooltip = connected && !sponsoredPill
    ? `${ai.info?.account_label ? `ChatGPT connected as ${ai.info.account_label}. ` : 'ChatGPT is connected. '}Click to return to sponsorship.`
    : undefined;
  const allowanceDescription = !cloudFunding?.authorized
    ? 'Sign in to view sponsorship.'
    : !sponsoredSelected
      ? 'Personal ChatGPT selected. Sponsored allowance is not being used.'
    : cloudFunding.error
      ? 'Sponsored allowance unavailable; research may be blocked.'
    : adminSponsored
      ? 'Admin sponsorship: Unlimited individual allowance. Global spending limit applies.'
    : cloudFunding.loading
      ? 'Loading sponsored allowance…'
      : cloudFunding.error
        ? 'Sponsored allowance unavailable.'
        : cloudFunding.budget
          ? `Sponsored allowance: $${cloudFunding.budget.remaining_usd.toFixed(2)} remaining of $${cloudFunding.budget.allowance_usd.toFixed(2)}.`
          : sponsoredSelected ? 'Sponsored allowance unavailable.' : 'Sponsorship not selected.';
  const sponsorTooltip = `${localSponsorNeedsReconnect ? 'Click to reconnect SIGMA-sponsored ChatGPT. Sign in as zetacontinuation@gmail.com. ' : forcedSponsored ? 'Sponsored mode is required for this account. ' : !hosted && !simulatedSponsored && sponsoredSelected ? 'Click to switch to your own ChatGPT account. ' : ''}${allowanceDescription}`;
  const sponsoredAccessibleLabel = `${hostedPillLabel}${forcedSponsored ? '; sponsored mode is required' : ''}${connected ? '; connected' : ''}`;
  const allowanceText = !sponsoredSelected
    ? 'Personal'
    : cloudFunding?.error
      ? 'Allowance unavailable'
    : adminSponsored
      ? 'Unlimited'
    : cloudFunding?.budget
      ? `${cloudFunding.budget.remaining_usd.toFixed(2)}`
    : cloudFunding?.loading ? 'Allowance loading' : 'Allowance details';
  async function connect() {
    if (ai.connecting || ai.transitioning) return;
    try {
      if (hosted) {
        if (forcedSponsored && sponsoredSelected) return;
        await cloudFunding?.selectConnection?.('sponsored');
        return;
      }
      if (localSponsorNeedsReconnect) {
        if (await ai.signIn({ sponsor: true })) await ai.refresh('manual');
        return;
      }
      if (cloudFunding?.authorized && cloudFunding.sponsorshipEligible) {
        if (forcedSponsored && sponsoredSelected) return;
        if (sponsoredSelected) {
          const personalConnected = await ai.signIn({ newAccount: true });
          if (personalConnected) await cloudFunding.selectConnection?.('personal');
        } else {
          const connected = await ai.signIn({
            accountId: ai.info?.active_account,
            newAccount: false,
            enablePlan: ai.info?.status === 'plan_not_permitted',
          });
          if (connected) await cloudFunding.selectConnection?.('personal');
        }
        await ai.refresh('manual');
        return;
      }
      const newLocalMemberAccount = !!cloudFunding?.authenticationEnabled
        && !!cloudFunding.authorized
        && !cloudFunding.sponsorshipEligible;
      await ai.signIn({
        accountId: newLocalMemberAccount ? undefined : ai.info?.active_account,
        newAccount: newLocalMemberAccount,
        enablePlan: ai.info?.status === 'plan_not_permitted',
      });
    } catch {
      // The connection error is shown beside the pill by the AI provider state.
    }
  }
  if (sponsoredPill && !adminSponsored && cloudFunding?.budget && cloudFunding.budget.remaining_usd <= 0) {
    return zeroAllowanceAction ?? null;
  }
  return <details className={`api-connection${projectHeader ? ' project-chatgpt-signin' : ''}`} open={!!ai.error || !!cloudFunding?.connectionError || (!sponsoredPill && (ai.connecting || !!ai.handoff))}>
    <summary className={sponsoredPill ? 'has-sponsored-allowance' : undefined} aria-label={sponsoredPill ? sponsoredAccessibleLabel : visibleLabel} data-tooltip={connectionTooltip} aria-disabled={disabled || (forcedSponsored && sponsoredSelected) || (connected && hosted)} onClick={event => { event.preventDefault(); if (disabled || (connected && hosted) || (forcedSponsored && sponsoredSelected)) return; if (simulatedSponsored && sponsoredSelected) void cloudFunding?.disconnectMockSponsored?.().catch(() => undefined); else if (connected && !sponsoredPill && cloudFunding?.sponsorshipEligible && !sponsoredSelected) void (async () => { if (await ai.disconnect()) await cloudFunding.selectConnection?.('sponsored'); })(); else if (connected && !sponsoredPill) void ai.disconnect(); else void connect(); }}>
      <span className={`connection-dot connection-${dotStatus}${dotActive ? ' connection-active' : ''}`} aria-hidden="true"/>
      {sponsoredPill ? <><span role="status">{visibleLabel}</span><button type="button" className="sponsored-allowance-trigger" aria-label="Sponsored allowance details" aria-describedby="sponsored-allowance-tooltip" aria-expanded={allowanceTipOpen} data-tooltip-disabled onClick={event => { event.stopPropagation(); event.preventDefault(); if (localSponsorNeedsReconnect) void connect(); else setAllowanceTipOpen(open => !open); }} onKeyDown={event => event.stopPropagation()}><span className="sponsored-allowance-inline">{allowanceText}</span><span id="sponsored-allowance-tooltip" className="sponsored-allowance-tooltip" role="tooltip">{sponsorTooltip}</span></button></> : <span role="status">{visibleLabel}</span>}
    </summary>
    {ai.connecting && !sponsoredPill && <p className="connection-pill-message" role="status">Complete sign-in in the browser. {ai.handoff && <a href={ai.handoff} target="_blank" rel="noreferrer">Open ChatGPT sign-in</a>}</p>}
    {ai.error && <p className="connection-pill-message" role="alert">{ai.error}</p>}
    {cloudFunding?.connectionError && <p className="connection-pill-message" role="alert">{cloudFunding.connectionError}</p>}
  </details>;
}
