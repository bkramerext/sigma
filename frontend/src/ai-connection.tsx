import { createContext, useCallback, useContext, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import './ai-connection.css';
import { windowAuthUrl } from './window-auth';
import { type SponsoredInferenceProvider } from './provider-usage-guidance';
import { reportRequestFailure } from './request-toast';
import DialogDismissButton from './DialogDismissButton';

export type ConnectionInfo = { mode: 'chatgpt' | 'api_key' | 'unknown'; status: string; label: string; guidance: string; checked_at: string | null; ttl_seconds: number; account_label?: string; active_account?: string; sponsor_account_selected?: boolean; accounts: { id: string; label: string }[]; welcome_pending?: boolean };
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
  // Report on failure transitions, not when a header remounts after navigation.
  useEffect(() => { if (error) reportRequestFailure(error); }, [error]);
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
      // Popup navigations have no X-Sigma-Window fetch header. Preserve the
      // initiating Google session in both the popup and blocked-popup link,
      // without forwarding the window selector to OpenAI.
      const handoffUrl = windowAuthUrl(url.pathname);
      if (!popup) setHandoff(handoffUrl);
      if (popup) popup.location.replace(handoffUrl);
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


const personalDiagnosticsEnabled = import.meta.env.VITE_SIGMA_PERSONAL_DIAGNOSTICS_ENABLED === 'true';

function PersonalBrowserDialog({ state, error, external = false, handoff, onClose, onRetry }: {
  state: 'closed' | 'preparing' | 'starting' | 'ready' | 'error';
  error: string;
  external?: boolean;
  handoff?: string;
  onClose: () => void;
  onRetry: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [diagnosticsStatus, setDiagnosticsStatus] = useState<'idle' | 'copied' | 'failed'>('idle');
  useEffect(() => { setDiagnosticsStatus('idle'); }, [state, error]);
  async function copyDiagnostics() {
    try {
      const response = await fetch(windowAuthUrl('/api/ai/personal-browser/diagnostics'), {
        credentials: 'same-origin', cache: 'no-store',
        headers: { 'X-Sigma-Error-Handled': 'true' },
      });
      if (!response.ok) throw new Error('Diagnostics unavailable');
      const report = await response.json() as { diagnostics?: string };
      if (!report.diagnostics) throw new Error('Missing diagnostic report');
      await navigator.clipboard.writeText(report.diagnostics);
      setDiagnosticsStatus('copied');
    } catch {
      setDiagnosticsStatus('failed');
    }
  }
  useEffect(() => {
    if (state === 'closed' || !dialog.current) return;
    if (!dialog.current.open) dialog.current.showModal();
    return () => { if (dialog.current?.open) dialog.current.close(); };
  }, [state === 'closed']);
  if (state === 'closed') return null;
  return <dialog ref={dialog} className={`google-account-dialog personal-chatgpt-connect-dialog${external ? ' is-external' : state !== 'error' ? ' is-viewing' : ''}`}
    aria-labelledby="personal-browser-heading"
    onCancel={event => { event.preventDefault(); onClose(); }}>
    <div className="privacy-notice-heading">
      <h2 id="personal-browser-heading">Connect to ChatGPT</h2>
      <DialogDismissButton label="Close ChatGPT connection" onClick={onClose}/>
    </div>
    {state === 'preparing' && !external && <p role="status">Preparing ChatGPT sign-in… This may take a little longer the first time.</p>}
    {state === 'starting' && <p role="status">{external
      ? 'Complete ChatGPT sign-in in the browser tab. This dialog closes after you connect.'
      : 'Opening ChatGPT sign-in…'}</p>}
    {external && handoff && state === 'starting' &&
      <a className="sigma-text-action" href={handoff} target="_blank" rel="noreferrer">
        Open sign-in tab
      </a>}
    {state === 'error' && <div className="personal-chatgpt-connection-error" role="alert">
      <p>{error || (external ? 'ChatGPT sign-in did not complete.' : 'The private browser could not be started.')}</p>
      <button className="sigma-text-action" type="button" onClick={onRetry}>Retry</button>
      {!external && personalDiagnosticsEnabled && <button className="sigma-text-action" type="button"
        onClick={() => void copyDiagnostics()}>Copy diagnostics</button>}
      {diagnosticsStatus === 'copied' && <span role="status">Diagnostics copied.</span>}
      {diagnosticsStatus === 'failed' && <span role="alert">
        Could not copy diagnostics. See the diagnostic file printed in the SIGMA terminal.
      </span>}
    </div>}
    {!external && state === 'ready' && <iframe
      className="personal-chatgpt-browser-frame"
      title="Private ChatGPT sign-in browser"
      src={windowAuthUrl('/api/ai/personal-browser/view')}/>}
  </dialog>;
}

function HostedPersonalChatGPTNotice({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!open || !dialog.current) return;
    if (!dialog.current.open) dialog.current.showModal();
    return () => { if (dialog.current?.open) dialog.current.close(); };
  }, [open]);
  if (!open) return null;
  return <dialog ref={dialog} className="google-account-dialog hosted-personal-chatgpt-dialog"
    aria-labelledby="hosted-personal-chatgpt-heading" onClose={onClose}>
    <div className="privacy-notice-heading">
      <h2 id="hosted-personal-chatgpt-heading">Oh, Darn.</h2>
      <DialogDismissButton label="Close Personal ChatGPT information" onClick={onClose}/>
    </div>
    <p>Unfortunately, Open AI doesn't let us connect using personal accounts while using a hosted application. Installing and running SIGMA locally allows this. But you can still use SIGMA now using the ChatGPT sponsor.</p>
  </dialog>;
}

function SponsorProvisioningDialog({ open, message, onClose }: {
  open: boolean; message: string; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!open || !dialog.current) return;
    if (!dialog.current.open) dialog.current.showModal();
    return () => { if (dialog.current?.open) dialog.current.close(); };
  }, [open]);
  if (!open) return null;
  return <dialog ref={dialog} className="google-account-dialog hosted-personal-chatgpt-dialog"
    aria-labelledby="sponsor-provisioning-heading" onCancel={event => { event.preventDefault(); onClose(); }}>
    <div className="privacy-notice-heading">
      <h2 id="sponsor-provisioning-heading">Sponsored ChatGPT</h2>
      <DialogDismissButton label="Close Sponsored ChatGPT information" onClick={onClose}/>
    </div>
    <p>{message}</p>
  </dialog>;
}

export function ConnectionStatus({ projectHeader = false, cloudFunding, zeroAllowanceAction }: { projectHeader?: boolean; zeroAllowanceAction?: ReactNode; cloudFunding?: { target: 'local' | 'hosted'; personalChatGPTNoticeEnabled?: boolean; personalChatGPTNoticePreview?: boolean; personalBrowserLabEnabled?: boolean; personalBrowserUiMode?: 'external' | 'container'; authenticationEnabled: boolean; googleAccount: string | null; budget: { allowance_usd: number; estimated_usage_usd: number; held_usd: number; remaining_usd: number | null; global_cap_exempt?: boolean; global_remaining_usd?: number; global_ceiling_usd?: number; global_spend_period?: 'cumulative' | 'calendar_month'; global_reset_at?: string | null; unknown_provider_attempts: number } | null; loading: boolean; error: string | null; authorized: boolean; sponsorshipEligible?: boolean; sponsorshipUnlimited?: boolean; provider: { provider?: SponsoredInferenceProvider; status: string; guidance: string } | null; providerLoading: boolean; providerError: string | null; retryProvider: () => Promise<void>; selectedConnection?: 'personal' | 'sponsored'; selectConnection?: (mode: 'personal' | 'sponsored') => Promise<void>; connectionError?: string | null; selectingConnection?: boolean; forcedSponsored?: boolean; simulatedSponsored?: boolean; disconnectMockSponsored?: () => Promise<void> } } = {}) {
  const ai = useAI();
  const [sponsorProvisioningHelpOpen, setSponsorProvisioningHelpOpen] = useState(false);
  const [personalHostedNoticeOpen, setPersonalHostedNoticeOpen] = useState(false);
  const openingContainerBrowser = useRef(false);
  const pendingPersonalStop = useRef<Promise<void> | null>(null);
  const browserLaunchSequence = useRef(0);
  const localSignInSequence = useRef(0);
  const localSignInOptions = useRef<SignInOptions>({});
  const dialogActive = useRef(false);
  const activatingPersonal = useRef(false);
  const restoringSponsored = useRef(false);
  // A deliberate Sponsored -> Personal click must finish a fresh OAuth
  // attempt. Existing saved credentials must not silently skip its chooser.
  const freshBrowserIntent = useRef(false);
  const freshBrowserStarted = useRef(false);
  const [personalDialogState, setPersonalDialogState] = useState<'closed' | 'preparing' | 'starting' | 'ready' | 'error'>('closed');
  const [personalDialogError, setPersonalDialogError] = useState('');
  const [testAccountOwner, setTestAccountOwner] = useState<string | null>(null);
  const [authorizedPreviewOwner, setAuthorizedPreviewOwner] = useState<string | null>(null);
  const pillTrigger = useRef<HTMLElement>(null);
  const disconnectPopup = useRef<HTMLDivElement>(null);
  const disconnectCancel = useRef<HTMLButtonElement>(null);
  const disconnectPromptId = useId();
  const [disconnectOpen, setDisconnectOpen] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [disconnectError, setDisconnectError] = useState('');
  const [restoringPersonal, setRestoringPersonal] = useState(false);
  const [disconnectPlacement, setDisconnectPlacement] = useState<{ left: number; top: number }>();
  const closeDisconnectPopup = useCallback(() => {
    setDisconnectOpen(false);
    setDisconnectError('');
    setDisconnectPlacement(undefined);
    window.requestAnimationFrame(() => pillTrigger.current?.focus());
  }, []);
  useLayoutEffect(() => {
    const anchor = pillTrigger.current;
    const popup = disconnectPopup.current;
    if (!disconnectOpen || !anchor || !popup) return;
    const place = () => {
      const rect = anchor.getBoundingClientRect();
      const { offsetWidth: width, offsetHeight: height } = popup;
      const left = Math.max(12, Math.min(rect.right - width, window.innerWidth - width - 12));
      const top = Math.max(12, Math.min(
        window.innerHeight - rect.bottom >= height + 18 ? rect.bottom + 6 : rect.top - height - 6,
        window.innerHeight - height - 12,
      ));
      setDisconnectPlacement({ left, top });
    };
    function escape(event: KeyboardEvent) {
      if (event.key !== 'Escape' || disconnecting) return;
      event.preventDefault();
      closeDisconnectPopup();
    }
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    document.addEventListener('keydown', escape);
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
      document.removeEventListener('keydown', escape);
    };
  }, [disconnectOpen, disconnecting, closeDisconnectPopup]);
  useEffect(() => {
    if (disconnectOpen && !disconnecting) disconnectCancel.current?.focus();
  }, [disconnectOpen, disconnecting]);
  const providerActive = useProviderActivity();
  const status = ai.connecting ? 'connecting' : ai.initialLoading ? 'checking' : ai.healthError ? 'stale' : ai.info?.status ?? 'unknown';
  const dotActive = !projectHeader && status === 'connected' && providerActive;
  const hosted = cloudFunding?.target === 'hosted';
  const simulatedSponsored = !!cloudFunding?.simulatedSponsored;
  // --prod previews the production-sponsored pill regardless of the user's
  // saved local connection. Presentation must not mutate credentials, mode or billing.
  const localHostedNoticePreview = !!cloudFunding?.authorized
    && !!cloudFunding.personalChatGPTNoticePreview
    && !!cloudFunding.personalChatGPTNoticeEnabled;
  // The launcher is authoritative: plain "sigma start" always opens a
  // separate, real ChatGPT browser tab. An inherited lab/worker flag alone
  // must never route this path through the embedded Docker browser.
  const containerBrowserLab = !!cloudFunding?.authorized && !!cloudFunding.personalBrowserLabEnabled
    && cloudFunding.personalBrowserUiMode === 'container';
  // The isolated Docker worker is shared by local preview and opt-in hosted
  // deployments. Never rely on target === 'local' as the authorization gate.
  const localLabAccount = containerBrowserLab ? cloudFunding?.googleAccount ?? null : null;
  const testConnected = localLabAccount !== null && testAccountOwner === localLabAccount;
  const previewAuthorized = localLabAccount !== null && authorizedPreviewOwner === localLabAccount;
  const selectConnection = cloudFunding?.selectConnection;
  const selectedConnection = cloudFunding?.selectedConnection;
  const selectingConnection = cloudFunding?.selectingConnection;
  const personalSelectionAllowed = !!cloudFunding && !cloudFunding.forcedSponsored;
  const refreshConnection = ai.refresh;
  // Reset the isolated preview only when its owner changes. Do not clear the
  // ordinary-local OAuth dialog every time it changes from closed to starting:
  // those state updates must not be coupled to the container-only status poll.
  useEffect(() => {
    if (localLabAccount) return;
    dialogActive.current = false;
    browserLaunchSequence.current += 1;
    freshBrowserIntent.current = false;
    freshBrowserStarted.current = false;
    setRestoringPersonal(false);
    setTestAccountOwner(null);
    setAuthorizedPreviewOwner(null);
    setPersonalDialogState('closed');
  }, [localLabAccount]);
  useEffect(() => {
    if (!localLabAccount) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function readStatus(path: string) {
      const response = await fetch(windowAuthUrl('/api/ai/personal-browser/' + path), {
        signal: controller.signal,
        headers: { 'X-Sigma-Error-Handled': 'true' },
      });
      return response.ok ? await response.json() : null;
    }
    async function check() {
      const [test, preview] = await Promise.allSettled([
        readStatus('test-account'),
        readStatus('preview-state'),
      ]);
      if (controller.signal.aborted) return;
      if (preview.status === 'fulfilled') {
        if (freshBrowserIntent.current && ['connecting', 'failed', 'ready'].includes(preview.value?.phase ?? ''))
          freshBrowserStarted.current = true;
        setAuthorizedPreviewOwner(preview.value?.phase === 'connected' ? localLabAccount : null);
      }
      if (test.status === 'fulfilled') {
        const verified = test.value?.verified === true;
        setTestAccountOwner(verified ? localLabAccount : null);
        if (verified) {
          setPersonalDialogState('closed');
          return;
        }
      }
      // A prior Personal selection is not a live connection. If its worker
      // cannot verify the account, restore the backed Sponsored mode instead
      // of displaying an inert "Connect to ChatGPT" pill at startup.
      // Never race an explicit sign-in or downgrade a verified account.
      if (test.status === 'fulfilled' && preview.status === 'fulfilled'
          && test.value?.verified !== true
          && preview.value?.phase !== 'connected'
          && selectedConnection === 'personal' && !!cloudFunding?.sponsorshipEligible
          && !dialogActive.current && personalDialogState === 'closed'
          && !selectingConnection && !restoringSponsored.current && selectConnection) {
        restoringSponsored.current = true;
        void selectConnection('sponsored').catch(() => {
          // Failures remain observable through the normal connection state.
        }).finally(() => { restoringSponsored.current = false; });
      }
      // A saved-session restoration is controlled by the verified fast path,
      // not by the background preview poll.
      if (!dialogActive.current || personalDialogState !== 'ready') return;
      if (preview.status === 'fulfilled' && preview.value?.phase === 'failed') {
        // An authorization error in the private worker must be a normal SIGMA
        // dialog error with Retry, not Chromium's raw HTTP error document.
        setPersonalDialogError('Could not open ChatGPT sign-in. Please retry.');
        setPersonalDialogState('error');
        return;
      }
      if (preview.status === 'fulfilled' && preview.value?.phase === 'connected'
          && (!freshBrowserIntent.current || freshBrowserStarted.current)
          && personalSelectionAllowed && !activatingPersonal.current) {
        if (selectingConnection) {
          timer = setTimeout(check, 750);
          return;
        }
        // OAuth completion alone is not proof of an eligible plan or model.
        // Keep Chromium open until the private worker verifies this account.
        const account = await readStatus('account').catch(() => null);
        if (controller.signal.aborted || !dialogActive.current) return;
        if (account?.status === 'verified') {
          activatingPersonal.current = true;
          const activationSequence = browserLaunchSequence.current;
          try {
            if (selectedConnection === 'sponsored') await selectConnection?.('personal');
            if (!dialogActive.current || activationSequence !== browserLaunchSequence.current) {
              // A click on X cancels the mode change. Keep any durable OAuth
              // credentials, but do not silently select Personal.
              if (selectedConnection === 'sponsored') {
                await selectConnection?.('sponsored');
                if (!dialogActive.current)
                  await stopContainerPersonalBrowser().catch(() => undefined);
              }
              return;
            }
            await refreshConnection('manual');
            if (dialogActive.current && activationSequence === browserLaunchSequence.current) {
              dialogActive.current = false;
              freshBrowserIntent.current = false;
              freshBrowserStarted.current = false;
              setPersonalDialogState('closed');
              // The shared worker continues model inference; release Chromium
              // and its X11/VNC helpers as soon as authorization succeeds.
              void stopContainerPersonalBrowser().catch(() => {
                console.warn('SIGMA: could not release the temporary ChatGPT browser.');
              });
            }
          } catch (cause) {
            if (dialogActive.current) {
              setPersonalDialogError(cause instanceof Error ? cause.message
                : 'SIGMA could not activate Personal ChatGPT.');
              setPersonalDialogState('error');
            } else if (selectedConnection === 'sponsored') {
              // The user closed the dialog while activation was completing.
              // Do not switch a cancelled connection behind their back.
              await selectConnection?.('sponsored').catch(() => undefined);
            }
          } finally {
            activatingPersonal.current = false;
          }
          return;
        }
      }
      timer = setTimeout(check, 750);
    }
    void check();
    return () => {
      controller.abort();
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [localLabAccount, personalDialogState, personalSelectionAllowed, refreshConnection,
    selectConnection, selectedConnection, selectingConnection, cloudFunding?.sponsorshipEligible]);
  const hostedNoticeClick = !!cloudFunding?.authorized
    && !!cloudFunding.personalChatGPTNoticeEnabled
    && (hosted || localHostedNoticePreview) && !containerBrowserLab;
  // A disconnected local --prod worker never displays a fourth pill state.
  // Show the available Sponsored mode while its persisted choice is reconciled.
  const localSponsoredDefault = !!localLabAccount && !!cloudFunding?.sponsorshipEligible
    && selectedConnection === 'personal' && !testConnected && !previewAuthorized;
  const sponsoredSelected = cloudFunding?.selectedConnection === 'sponsored'
    || localHostedNoticePreview || localSponsoredDefault;
  const hostedPersonalUnavailable = hosted && !!cloudFunding?.authorized
    && cloudFunding.selectedConnection === 'personal' && !cloudFunding.forcedSponsored
    && !containerBrowserLab;
  const sponsoredPresentation = sponsoredSelected || hostedPersonalUnavailable;
  const adminSponsored = sponsoredPresentation && !!cloudFunding?.sponsorshipUnlimited;
  const adminNeedsSponsorProvisioning = !!hosted && adminSponsored
    && (cloudFunding?.provider?.provider === 'api_key'
      || (cloudFunding?.provider?.provider === 'chatgpt'
        && cloudFunding.provider.status !== 'connected'));
  const sponsoredPill = !!cloudFunding?.authorized && (hostedNoticeClick || hostedPersonalUnavailable
    || (hosted ? sponsoredSelected : !!cloudFunding.sponsorshipEligible && sponsoredSelected));
  const googleRequired = !!cloudFunding?.authenticationEnabled && !cloudFunding.authorized;
  // Keep the ChatGPT credential intact while Google is signed out, but present
  // the pill as unavailable until an authorized Google session returns.
  const hostedConnected = hosted && sponsoredSelected && cloudFunding?.provider?.status === 'connected';
  const forcedSponsored = !!cloudFunding?.forcedSponsored && !!cloudFunding?.authorized;
  const connected = (hosted ? (sponsoredSelected ? hostedConnected : status === 'connected') : simulatedSponsored
    ? sponsoredPill && sponsoredSelected && cloudFunding?.provider?.status === 'connected'
    : status === 'connected') && !googleRequired;
  const disabled = (!hosted && !hostedNoticeClick && (ai.connecting || ai.transitioning)) || googleRequired || !!cloudFunding?.selectingConnection || disconnecting || restoringPersonal;
  const dotStatus = simulatedSponsored
    ? (connected ? 'connected' : 'disconnected')
    : projectHeader ? (connected ? 'connected' : 'disconnected') : hosted ? (connected ? 'connected' : 'disconnected') : status;
  // Connection pill text reflects only stable connection modes. Never turn the
  // pill into a startup, verification, or disconnect progress indicator.
  const visibleLabel = testConnected ? 'Connected to ChatGPT'
    : sponsoredPill ? 'ChatGPT Sponsored'
    : connected ? 'Connected to ChatGPT' : 'Connect to ChatGPT';
  const connectionTooltip = containerBrowserLab
    ? 'Click to attempt your Personal ChatGPT connection using a private container browser.'
    : (hostedNoticeClick || hostedPersonalUnavailable)
    ? cloudFunding?.personalChatGPTNoticeEnabled
      ? 'Click to learn why personal ChatGPT is unavailable in hosted SIGMA.'
      : 'Personal ChatGPT is unavailable in hosted SIGMA. Click to use SIGMA-sponsored ChatGPT instead.'
    : googleRequired
      ? 'Sign in with Google to use your configured ChatGPT connection. Your saved ChatGPT credentials are preserved.'
      : ai.connecting
        ? 'ChatGPT sign-in is in progress. Complete authorization in the browser to connect your personal account.'
        : cloudFunding?.selectingConnection
          ? 'Switching your ChatGPT connection. Your selected funding mode will apply to future AI requests.'
          : connected
            ? `${ai.info?.account_label ? `ChatGPT connected as ${ai.info.account_label}.` : 'Your personal ChatGPT account is connected.'} SIGMA uses this personal connection for AI requests. ${cloudFunding?.sponsorshipEligible && !hosted ? 'Click to disconnect and return to SIGMA sponsorship.' : hosted ? 'Hosted SIGMA does not support personal ChatGPT here.' : 'Click to disconnect this ChatGPT account.'}`
            : `Personal ChatGPT is not connected${ai.info?.status && !['unknown', 'unconfigured'].includes(ai.info.status) ? ` (${ai.info.status})` : ''}. Click to sign in with your own ChatGPT account to use your available model access. ${ai.info?.guidance ?? ''}`.trim();
  const globalRemaining = cloudFunding?.budget?.global_remaining_usd;
  const globalFundingExhausted = sponsoredSelected
    && !cloudFunding?.budget?.global_cap_exempt
    && typeof globalRemaining === 'number'
    && globalRemaining <= 0;
  const sponsorDetails = simulatedSponsored
    ? 'This Sponsored ChatGPT connection is simulated.'
    : globalFundingExhausted
      ? 'SIGMA has reached its sponsored spending limit.'
      : !cloudFunding?.authorized
        ? 'Sign in with Google to use Sponsored ChatGPT.'
        : adminSponsored || cloudFunding?.budget?.remaining_usd === null
          ? 'SIGMA covers ChatGPT requests. Your allowance is unlimited.'
          : typeof cloudFunding?.budget?.remaining_usd === 'number'
            ? `SIGMA covers ChatGPT requests. $${Math.max(0, cloudFunding.budget.remaining_usd).toFixed(2)} remaining.`
            : 'SIGMA covers ChatGPT requests.';
  const sponsorProvisioningGuidance = cloudFunding?.provider?.provider === 'api_key'
    ? 'Hosted inference is currently routed to Sponsored OpenAI API key billing. SIGMA does not fall back between providers. To use the designated ChatGPT sponsor, set SIGMA_CLOUD_INFERENCE_PROVIDER=chatgpt and provision the sponsor registration using the supported local sign-in and protected VM import flow.'
    : 'Hosted ChatGPT sponsor credentials are not connected. The production HTTPS callback is not a supported ChatGPT sign-in flow. Complete sign-in locally with the designated account, then securely import its protected registration on the VM; SIGMA validates the account and scopes and keeps the VM host ID.';
  const sponsoredAccessibleLabel = `ChatGPT Sponsored${forcedSponsored ? '; sponsored mode required' : ''}${connected && sponsoredSelected ? adminSponsored ? '; sponsor connected' : '; connected' : ''}`;
  const allowanceText = !sponsoredPresentation
    ? 'Personal'
    : adminSponsored
      ? 'Unlimited'
    : cloudFunding?.budget?.remaining_usd !== null && typeof cloudFunding?.budget?.remaining_usd === 'number'
      ? `Allocation: ${cloudFunding.budget.remaining_usd.toFixed(2)}`
    : 'Unlimited';
  async function stopContainerPersonalBrowser() {
    const response = await fetch(windowAuthUrl('/api/ai/personal-browser/stop'), {
      method: 'POST',
      headers: { 'X-Sigma-Error-Handled': 'true' },
    });
    if (!response.ok) throw new Error('Could not stop the private browser.');
  }

  async function closePersonalBrowserDialog() {
    dialogActive.current = false;
    browserLaunchSequence.current += 1;
    freshBrowserIntent.current = false;
    freshBrowserStarted.current = false;
    const activationPending = activatingPersonal.current;
    const wasReady = personalDialogState === 'ready' || personalDialogState === 'error';
    setPersonalDialogState('closed');
    setPersonalDialogError('');
    // Closing a completed connection must not stop its inference worker.
    // If activation is in flight, let it finish before touching the worker.
    // Image preparation and the Sponsored SIGMA application keep running.
    if (!wasReady || activationPending) return;
    try {
      await stopContainerPersonalBrowser();
    } catch (cause) {
      reportRequestFailure(cause instanceof Error ? cause.message : 'Could not stop the private browser.');
    }
  }

  async function finishContainerBrowserStart(sequence: number) {
    if (sequence !== browserLaunchSequence.current || !dialogActive.current) return;
    // Reuse an already validated worker account before exposing the GUI.
    // OAuth state alone cannot establish model permission or billing identity.
    try {
      const response = await fetch(windowAuthUrl('/api/ai/personal-browser/account'), {
        credentials: 'same-origin',
        headers: { 'X-Sigma-Error-Handled': 'true' },
        signal: AbortSignal.timeout(20000),
      });
      const account = response.ok ? await response.json() as { status?: string } : null;
      if (sequence !== browserLaunchSequence.current || !dialogActive.current) return;
      if (account?.status === 'verified' && personalSelectionAllowed
          && !freshBrowserIntent.current) {
        activatingPersonal.current = true;
        try {
          if (selectedConnection !== 'personal') await selectConnection?.('personal');
          if (sequence !== browserLaunchSequence.current || !dialogActive.current) return;
          await refreshConnection('manual');
          if (sequence !== browserLaunchSequence.current || !dialogActive.current) return;
          dialogActive.current = false;
          setPersonalDialogState('closed');
          void stopContainerPersonalBrowser().catch(() => {
            console.warn('SIGMA: could not release the temporary ChatGPT browser.');
          });
          return;
        } catch (cause) {
          if (sequence === browserLaunchSequence.current && dialogActive.current) {
            setPersonalDialogError(cause instanceof Error ? cause.message
              : 'Could not restore the saved ChatGPT connection.');
            setPersonalDialogState('error');
          }
          return;
        } finally {
          activatingPersonal.current = false;
          setRestoringPersonal(false);
        }
      }
    } catch {
      // A failed verification is not proof of authorization; show the real
      // sign-in viewer instead of silently selecting an unverified account.
    } finally {
      setRestoringPersonal(false);
    }
    if (sequence !== browserLaunchSequence.current || !dialogActive.current) return;
    // The shared worker reports "ready", not a stale "connected", until
    // Chromium initiates this fresh chooser. The callback can finish faster
    // than a polling interval; don't require observing "connecting" first.
    if (freshBrowserIntent.current) freshBrowserStarted.current = true;
    setPersonalDialogState('ready');
  }

  async function startContainerPersonalBrowser() {
    if (openingContainerBrowser.current || personalDialogState === 'ready'
        || personalDialogState === 'starting' || personalDialogState === 'preparing') return;
    if (testConnected) {
      try {
        await stopContainerPersonalBrowser();
        setTestAccountOwner(null);
      } catch (cause) {
        reportRequestFailure(cause instanceof Error ? cause.message : 'Could not close the test browser.');
      }
      return;
    }
    // The user remains in SIGMA. The iframe embeds SIGMA's authenticated VNC
    // viewer; OpenAI itself is never framed or deprived of its CSP protections.
    const sequence = ++browserLaunchSequence.current;
    freshBrowserIntent.current = selectedConnection === 'sponsored';
    freshBrowserStarted.current = false;
    const diagnosticAttempt = personalDiagnosticsEnabled
      ? crypto.randomUUID().replaceAll('-', '').slice(0, 12) : '';
    if (personalDiagnosticsEnabled) console.info('[SIGMA Personal] browser launch', diagnosticAttempt);
    dialogActive.current = true;
    openingContainerBrowser.current = true;
    setPersonalDialogError('');
    setRestoringPersonal(true);
    // Show the dialog immediately. The actual iframe remains deferred until
    // the isolated worker is ready; a saved account may close it automatically.
    setPersonalDialogState('starting');
    try {
      // A new cold connection must never race the preceding Docker stop.
      if (pendingPersonalStop.current) await pendingPersonalStop.current.catch(() => undefined);
      while (sequence === browserLaunchSequence.current && dialogActive.current) {
        const response = await fetch(windowAuthUrl('/api/ai/personal-browser/start'), {
          method: 'POST', credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-Sigma-Error-Handled': 'true',
            ...(personalDiagnosticsEnabled ? { 'X-Sigma-Personal-Attempt': diagnosticAttempt } : {}),
          },
          body: '{}',
        });
        if (personalDiagnosticsEnabled) console.info('[SIGMA Personal] start status', diagnosticAttempt, response.status);
        const data = await response.json().catch(() => ({})) as {
          browser_status?: string; detail?: string; error?: string;
        };
        if (sequence !== browserLaunchSequence.current || !dialogActive.current) {
          // A dismissed attempt may finish while the request is in flight.
          // Do not stop a worker concurrently being adopted as Personal.
          if (!activatingPersonal.current && !(selectedConnection === 'personal' && connected))
            void stopContainerPersonalBrowser().catch(() => {});
          return;
        }
        if (response.status === 202 && data.browser_status === 'preparing') {
          setPersonalDialogState('preparing');
          await new Promise<void>(resolve => window.setTimeout(resolve, 1500));
          continue;
        }
        if (!response.ok)
          throw new Error(data.detail ?? data.error ??
            `Private ChatGPT browser startup returned HTTP ${response.status}.`);
        if (data.browser_status === 'ready') {
          await finishContainerBrowserStart(sequence);
          return;
        }
        if (data.browser_status !== 'unavailable' && data.browser_status !== 'stopped')
          throw new Error('Private ChatGPT browser returned an unexpected startup status.');
        // Compose --wait can finish before Chromium, VNC and the private Unix
        // relays are all responsive. Poll status instead of declaring failure
        // from the first not-yet-ready response; do NOT POST start repeatedly.
        const deadline = Date.now() + 60_000;
        while (sequence === browserLaunchSequence.current && dialogActive.current
               && Date.now() < deadline) {
          await new Promise<void>(resolve => window.setTimeout(resolve, 2000));
          if (sequence !== browserLaunchSequence.current || !dialogActive.current) return;
          let statusResponse: Response;
          try {
            statusResponse = await fetch(windowAuthUrl('/api/ai/personal-browser/status'), {
              credentials: 'same-origin',
              headers: {
                'X-Sigma-Error-Handled': 'true',
                ...(personalDiagnosticsEnabled ? { 'X-Sigma-Personal-Attempt': diagnosticAttempt } : {}),
              },
              signal: AbortSignal.timeout(5000),
            });
          } catch {
            // A temporary network interruption during Chromium startup is
            // not an authorization failure. Retry inside the grace period.
            continue;
          }
          if (sequence !== browserLaunchSequence.current || !dialogActive.current) return;
          if (!statusResponse.ok) {
            if (personalDiagnosticsEnabled) console.info('[SIGMA Personal] poll status', diagnosticAttempt, statusResponse.status);
            continue;
          }
          const status = await statusResponse.json().catch(() => ({})) as {
            browser_status?: string;
          };
          if (status.browser_status === 'ready') {
            await finishContainerBrowserStart(sequence);
            return;
          }
        }
        if (sequence !== browserLaunchSequence.current || !dialogActive.current) return;
        throw new Error('Private ChatGPT browser is still unavailable after 60 seconds.');
      }
    } catch (cause) {
      if (sequence !== browserLaunchSequence.current || !dialogActive.current) return;
      setRestoringPersonal(false);
      const message = cause instanceof Error ? cause.message : 'Private browser unavailable.';
      if (personalDiagnosticsEnabled) console.info('[SIGMA Personal] launch failed', diagnosticAttempt, message);
      setPersonalDialogError(personalDiagnosticsEnabled
        ? `${message} (diagnostic attempt ${diagnosticAttempt})` : message);
      setPersonalDialogState('error');
    } finally {
      openingContainerBrowser.current = false;
    }
  }

  async function disconnectContainerConnection() {
    if (disconnecting) return;
    setDisconnectError('');
    setDisconnecting(true);
    try {
      const response = await fetch(windowAuthUrl('/api/ai/personal-browser/disconnect'), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
        body: '{}',
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({})) as { detail?: string; error?: string };
        throw new Error(detail.detail ?? detail.error ?? 'Could not disconnect Personal ChatGPT. Try again.');
      }
      const result = await response.json() as { disconnected?: boolean };
      if (result.disconnected !== true)
        throw new Error('SIGMA did not confirm that Personal ChatGPT was disconnected.');
      // The backend has committed local credential removal and the Sponsored
      // choice. Never leave the confirmation up after successful completion.
      setAuthorizedPreviewOwner(null);
      setTestAccountOwner(null);
      dialogActive.current = false;
      browserLaunchSequence.current += 1;
      setPersonalDialogState('closed');
      // Begin tearing down Chromium before the confirmation disappears, so a
      // new click can await this precise stop rather than race it.
      const stop = stopContainerPersonalBrowser();
      pendingPersonalStop.current = stop;
      closeDisconnectPopup();
      window.dispatchEvent(new Event('sigma-cloud-auth-refresh'));
      // The committed disconnect must not turn into a false failure because a
      // subsequent provider-status refresh happened to be unavailable.
      await ai.refresh('manual').catch(() => undefined);
      // Chromium's ephemeral browser login is discarded for the next chooser.
      // A Docker stop failure cannot undo the committed local disconnect.
      try {
        await stop.catch(() => {
          // Personal credentials are already cleared and Sponsored is active.
          // Cleanup is best-effort and not an actionable user failure.
          console.warn('SIGMA: private browser cleanup failed after disconnect.');
        });
      } finally {
        if (pendingPersonalStop.current === stop) pendingPersonalStop.current = null;
      }
    } catch (cause) {
      setDisconnectError(cause instanceof Error ? cause.message
        : 'Could not disconnect Personal ChatGPT. Try again.');
    } finally {
      setDisconnecting(false);
    }
  }

  async function selectContainerConnection() {
    if (localLabAccount && !testConnected && selectedConnection === 'personal' && (previewAuthorized || connected)) {
      setDisconnectOpen(true);
      return;
    }
    if (previewAuthorized && selectedConnection !== 'sponsored'
        && cloudFunding?.sponsorshipEligible && !cloudFunding.forcedSponsored) {
      try {
        await cloudFunding.selectConnection?.('personal');
        dialogActive.current = false;
        setPersonalDialogState('closed');
        await ai.refresh('manual');
      } catch {
        // The connection selector reports the error in the SIGMA window.
      }
      return;
    }
    await startContainerPersonalBrowser();
  }
  async function signInLocally(options: SignInOptions): Promise<boolean> {
    // Local OAuth uses the user's normal browser; keep the same SIGMA modal
    // shell as the isolated preview, never iframe the provider's login page.
    const sequence = ++localSignInSequence.current;
    localSignInOptions.current = options;
    setPersonalDialogError('');
    setPersonalDialogState('starting');
    try {
      const success = await ai.signIn(options);
      if (sequence !== localSignInSequence.current) return false;
      if (success) setPersonalDialogState('closed');
      else {
        setPersonalDialogError('ChatGPT sign-in was not completed.');
        setPersonalDialogState('error');
      }
      return success;
    } catch (cause) {
      if (sequence === localSignInSequence.current) {
        setPersonalDialogError(cause instanceof Error ? cause.message : 'ChatGPT sign-in failed.');
        setPersonalDialogState('error');
      }
      return false;
    }
  }
  function closeLocalPersonalDialog() {
    localSignInSequence.current += 1;
    ai.cancelSignIn();
    setPersonalDialogState('closed');
    setPersonalDialogError('');
  }
  async function connect() {
    if (ai.connecting || ai.transitioning) return;
    try {
      // A local container POC must NEVER fall back to Mac-local OAuth.
      if (containerBrowserLab) { await startContainerPersonalBrowser(); return; }
      if (hosted) {
        if (forcedSponsored && sponsoredSelected) return;
        if (adminNeedsSponsorProvisioning) {
          setSponsorProvisioningHelpOpen(true);
          return;
        }
        await cloudFunding?.selectConnection?.('sponsored');
        return;
      }
      if (cloudFunding?.authorized && cloudFunding.sponsorshipEligible) {
        if (forcedSponsored && sponsoredSelected) return;
        if (sponsoredSelected) {
          const personalConnected = await signInLocally({ newAccount: true });
          if (personalConnected) await cloudFunding.selectConnection?.('personal');
        } else {
          const connected = await signInLocally({
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
      await signInLocally({
        accountId: newLocalMemberAccount ? undefined : ai.info?.active_account,
        newAccount: newLocalMemberAccount,
        enablePlan: ai.info?.status === 'plan_not_permitted',
      });
    } catch {
      // The connection error is shown beside the pill by the AI provider state.
    }
  }
  const pillTooltip = containerBrowserLab && !sponsoredSelected && connected
    ? ai.info?.account_label
      ? `Connected to ChatGPT using personal account ${ai.info.account_label}.`
      : 'Connected to ChatGPT using your personal account.'
    : previewAuthorized && sponsoredSelected
      ? 'Click to use your ChatGPT plan for SIGMA requests.'
      : sponsoredPill ? undefined : connectionTooltip;
  const zeroAllowance = sponsoredPill && sponsoredSelected && !adminSponsored && typeof cloudFunding?.budget?.remaining_usd === 'number' && cloudFunding.budget.remaining_usd < 0.05;
  return <>
  <details className={`api-connection${projectHeader ? ' project-chatgpt-signin' : ''}`}>
    <summary ref={pillTrigger} className={sponsoredPill ? 'has-sponsored-allowance' : undefined} aria-label={sponsoredPill && !testConnected ? `${sponsoredAccessibleLabel}; ${allowanceText}` : visibleLabel} data-tooltip={sponsoredPill ? undefined : pillTooltip} aria-disabled={disabled} onClick={event => { event.preventDefault(); if (disabled) return; if (containerBrowserLab) { if (localLabAccount || sponsoredPill || cloudFunding?.selectedConnection !== 'personal') void selectContainerConnection(); else void cloudFunding?.selectConnection?.('sponsored').catch(() => undefined); return; } if (hostedNoticeClick) { setPersonalHostedNoticeOpen(true); return; } if ((connected && hosted && !adminNeedsSponsorProvisioning) || (forcedSponsored && sponsoredSelected)) return; if (simulatedSponsored && sponsoredSelected) void cloudFunding?.disconnectMockSponsored?.().catch(() => undefined); else if (connected && !sponsoredPill && cloudFunding?.sponsorshipEligible && !sponsoredSelected) void (async () => { if (await ai.disconnect()) { await cloudFunding.selectConnection?.('sponsored'); await ai.refresh('manual'); } })(); else if (connected && !sponsoredPill) void ai.disconnect(); else void connect(); }}>
      <span className={`connection-dot connection-${dotStatus}${dotActive ? ' connection-active' : ''}`} aria-hidden="true"/>
      {sponsoredPill && !testConnected ? <span className="connection-label-stack"><span role="status">{visibleLabel}</span><span className="sponsored-allowance-trigger"><span className="sponsored-allowance-inline">{allowanceText}</span><span className="sponsored-allowance-tooltip" role="tooltip">{sponsorDetails}</span></span></span> : <span role="status">{visibleLabel}</span>}
    </summary>
  </details>
  {localLabAccount && disconnectOpen && createPortal(
    <div ref={disconnectPopup} className="paper-step-restart-popup chatgpt-disconnect-popup"
      role="dialog" aria-modal="false" aria-labelledby={disconnectPromptId} aria-busy={disconnecting}
      style={disconnectPlacement ?? { left: 12, top: 12, visibility: 'hidden' }}>
      <p id={disconnectPromptId}>{ai.info?.account_label
        ? `Disconnect from personal ChatGPT account ${ai.info.account_label}?`
        : 'Disconnect from your personal ChatGPT account?'}</p>
      {disconnectError && <p role="alert">{disconnectError}</p>}
      <div className="session-remove-confirm-actions">
        {disconnecting ? <span role="status">Disconnecting…</span>
          : <button type="button" className="text-view-link"
              onClick={() => void disconnectContainerConnection()}>Confirm</button>}
        <button ref={disconnectCancel} type="button" className="text-view-link" disabled={disconnecting}
          onClick={closeDisconnectPopup}>Cancel</button>
      </div>
    </div>, document.body)}
  {createPortal(
    <PersonalBrowserDialog
      // Ordinary local sign-in already opens a real browser tab on click.
      // Never overlay the container-style dialog unless that popup was
      // blocked and we need to show the safe manual handoff link.
      state={!containerBrowserLab && !hosted && !ai.handoff ? 'closed' : personalDialogState}
      error={personalDialogError || (!containerBrowserLab ? ai.error : '')}
      external={!containerBrowserLab && !hosted}
      handoff={ai.handoff}
      onClose={() => {
        if (containerBrowserLab) void closePersonalBrowserDialog();
        else closeLocalPersonalDialog();
      }}
      onRetry={() => {
        if (containerBrowserLab) void startContainerPersonalBrowser();
        else void signInLocally(localSignInOptions.current);
      }}/>,
    document.body,
  )}
  <SponsorProvisioningDialog open={sponsorProvisioningHelpOpen} message={sponsorProvisioningGuidance}
    onClose={() => setSponsorProvisioningHelpOpen(false)}/>
  <HostedPersonalChatGPTNotice open={personalHostedNoticeOpen} onClose={() => {
    setPersonalHostedNoticeOpen(false);
    window.requestAnimationFrame(() => pillTrigger.current?.focus());
  }}/>
  {zeroAllowance && zeroAllowanceAction}
  </>;
}
