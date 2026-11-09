import { createElement, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import DialogDismissButton from './DialogDismissButton';
import ProjectTypesDialog, { type ProjectTypeRecord, type ProjectTypesSaveState } from './ProjectTypesDialog';
import RenderedMarkdown from './RenderedMarkdown';
import SigmaSelect from './SigmaSelect';
import './global-settings.css';

type Tab = 'types' | 'limits' | 'preferences' | 'ethos';
type DurationUnit = 'minutes' | 'hours' | 'days' | 'unlimited';
const unitMinutes: Record<Exclude<DurationUnit, 'unlimited'>, number> = { minutes: 1, hours: 60, days: 1440 };
type LimitSettings = {
  research_rounds: number;
  turns_per_round: number;
  scheduler_version: number;
  model_calls: number;
  session_duration_minutes: number | null;
  output_tokens_per_call: number;
  maximum_estimated_cost_usd: number | null;
  maximum_input_tokens_per_session: number | null;
  max_concurrent_sessions: number | string;
};
type ResearchConfig = {
  limits: LimitSettings;
  ai_model: string;
  reasoning_effort: string;
  show_advanced_outcome_details: boolean;
};
type EthosConfig = { markdown: string; is_override: boolean; version: string; sha256: string };
type Preference = { allow_unattended_background_execution: boolean; expand_one_project_section_at_a_time: boolean; progress_email: boolean };
const tabs: { id: Tab; title: string }[] = [
  { id: 'types', title: 'Project Types' },
  { id: 'limits', title: 'Limits' },
  { id: 'preferences', title: 'Preferences' },
  { id: 'ethos', title: 'Research Ethos' },
];
const headers = { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' };
const settingsTabStorageKey = 'sigma-settings-current-tab';
function initialSettingsTab(): Tab {
  try {
    const saved = window.sessionStorage.getItem(settingsTabStorageKey);
    const matching = tabs.find(item => item.id === saved);
    return matching?.id ?? 'types';
  } catch {
    return 'types';
  }
}

async function readJson(url: string): Promise<any> {
  const response = await fetch(url, { cache: 'no-store', headers: { 'X-Sigma-Error-Handled': 'true' } });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail ?? result.error ?? 'Settings could not be loaded');
  return result;
}
async function putJson(url: string, payload: unknown): Promise<any> {
  const response = await fetch(url, { method: 'PUT', headers, body: JSON.stringify(payload) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail ?? result.error ?? 'Settings could not be saved');
  return result;
}
const textValue = (value: number | null | undefined) => value == null ? '' : String(value);

/** Render persisted project-type icon definitions exactly as New Project does. */
function ProjectTypeIcon({ item }: { item: ProjectTypeRecord }) {
  if (item.icon.kind === 'data' && item.icon.data_uri) {
    return <img className="research-type-icon research-type-icon-custom" src={item.icon.data_uri} alt=""/>;
  }
  if (item.icon.kind !== 'builtin' || !Array.isArray(item.icon.elements)) return null;
  type IconNode = NonNullable<ProjectTypeRecord['icon']['elements']>[number];
  const render = (node: IconNode, key: string): ReactNode => {
    if (!['path', 'circle', 'ellipse', 'text', 'g'].includes(node.tag)) return null;
    const content = node.text ?? node.children?.map((child, index) => render(child, key + '-' + index));
    return createElement(node.tag, { key, ...(node.attrs ?? {}) }, content);
  };
  return <svg className="research-type-icon" viewBox={item.icon.view_box ?? '0 0 24 24'}
    aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6"
    strokeLinecap="round" strokeLinejoin="round">
    {item.icon.elements.map((node, index) => render(node, item.id + '-' + index))}
  </svg>;
}

export default function GlobalSettingsDialog({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState<Tab>(initialSettingsTab);
  const [config, setConfig] = useState<ResearchConfig | null>(null);
  const [durationUnit, setDurationUnit] = useState<DurationUnit>('minutes');
  const [prefs, setPrefs] = useState<Preference>({
    allow_unattended_background_execution: false,
    expand_one_project_section_at_a_time: false,
    progress_email: false,
  });
  const [progressAvailable, setProgressAvailable] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [ethos, setEthos] = useState<EthosConfig | null>(null);
  const [ethosDraft, setEthosDraft] = useState('');
  const [ethosEditing, setEthosEditing] = useState(false);
  const [ethosBusy, setEthosBusy] = useState(false);
  const [ethosError, setEthosError] = useState('');
  const [ethosCopied, setEthosCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [typesSaveState, setTypesSaveState] = useState<ProjectTypesSaveState>({ dirty: false, valid: false, busy: false });
  const typesSaveRef = useRef<(() => Promise<boolean>) | null>(null);
  const savedSnapshot = useRef<string | null>(null);
  // Keep only the selected tab across dialog closes/reopens (and refreshes).
  // Unsaved Settings fields remain local drafts and are discarded on Close.
  useEffect(() => {
    try { window.sessionStorage.setItem(settingsTabStorageKey, tab); } catch { /* Storage may be disabled. */ }
  }, [tab]);
  const onTypesSaveStateChange = useCallback((next: ProjectTypesSaveState) => {
    setTypesSaveState(previous =>
      previous.dirty === next.dirty && previous.valid === next.valid && previous.busy === next.busy ? previous : next);
  }, []);
  useEffect(() => {
    dialog.current?.showModal();
    // Native cancel must be prevented before any parent Escape handling.
    const preventCancel = (event: Event) => { event.preventDefault(); event.stopPropagation(); };
    const element = dialog.current;
    element?.addEventListener("cancel", preventCancel);
    const controller = new AbortController();
    void Promise.all([
      readJson('/api/user-preferences/research-settings'),
      readJson('/api/user-preferences/unattended-execution'),
      readJson('/api/user-preferences/section-layout'),
      readJson('/api/user-preferences/progress-email').catch(() => ({ enabled: false, available: false })),
    ]).then(([research, unattended, layout, progress]) => {
      if (controller.signal.aborted) return;
      setConfig(research as ResearchConfig);
      const minutes = (research as ResearchConfig).limits.session_duration_minutes;
      setDurationUnit(minutes === null ? 'unlimited'
        : minutes % 1440 === 0 ? 'days' : minutes % 60 === 0 ? 'hours' : 'minutes');
      setPrefs({
        allow_unattended_background_execution: !!unattended.allow_unattended_background_execution,
        expand_one_project_section_at_a_time: !!layout.expand_one_project_section_at_a_time,
        progress_email: !!progress.enabled,
      });
      setProgressAvailable(!!progress.available);
      savedSnapshot.current = JSON.stringify({ config: research, prefs: {
        allow_unattended_background_execution: !!unattended.allow_unattended_background_execution,
        expand_one_project_section_at_a_time: !!layout.expand_one_project_section_at_a_time,
        progress_email: !!progress.enabled,
      } });
      setLoaded(true);
    }).catch(cause => { if (!controller.signal.aborted) setError(String(cause)); });
    // Ethos is optional to the other tabs. Its read failure must not make
    // unrelated model/limits/preferences unavailable.
    void readJson('/api/user-preferences/research-ethos')
      .then((value: EthosConfig) => {
        if (controller.signal.aborted) return;
        setEthos(value);
        setEthosDraft(value.markdown);
        setEthosError('');
      })
      .catch(cause => { if (!controller.signal.aborted) setEthosError(String(cause)); });
    return () => { controller.abort(); element?.removeEventListener("cancel", preventCancel); };
  }, []);
  const setLimit = (key: keyof LimitSettings, value: number | string | null) => {
    setSaved(false);
    setConfig(current => current ? { ...current, limits: { ...current.limits, [key]: value } } : current);
  };
  const setResearch = (patch: Partial<ResearchConfig>) => {
    setSaved(false);
    setConfig(current => current ? { ...current, ...patch } : current);
  };
  const setPref = (patch: Partial<Preference>) => { setSaved(false); setPrefs(current => ({ ...current, ...patch })); };
  const hasOtherChanges = loaded && !!config && savedSnapshot.current !== JSON.stringify({ config, prefs });
  const hasChanges = typesSaveState.dirty || hasOtherChanges;
  const validLimits = !!config && (['research_rounds', 'turns_per_round', 'output_tokens_per_call', 'max_concurrent_sessions'] as const)
    .every(field => Number.isInteger(Number(config.limits[field])) && Number(config.limits[field]) >= 1 && String(config.limits[field]).trim() !== '')
    && (['session_duration_minutes', 'maximum_input_tokens_per_session'] as const)
      .every(field => config.limits[field] == null || (Number.isFinite(Number(config.limits[field])) && Number(config.limits[field]) > 0 && String(config.limits[field]).trim() !== ''))
    && (config.limits.maximum_estimated_cost_usd == null ||
      (Number.isFinite(Number(config.limits.maximum_estimated_cost_usd)) && Number(config.limits.maximum_estimated_cost_usd) > 0 &&
      String(config.limits.maximum_estimated_cost_usd).trim() !== ''));
  // Project Types can be saved independently if another preferences endpoint
  // is unavailable: never strand changes behind an unrelated Settings fetch.
  const canSave = hasChanges && !busy && !typesSaveState.busy && !ethosBusy &&
    (!typesSaveState.dirty || typesSaveState.valid) &&
    (!hasOtherChanges || (loaded && validLimits));
  async function save() {
    if (!canSave) return;
    setBusy(true); setError(''); setSaved(false);
    const completed: string[] = [];
    try {
      if (typesSaveState.dirty) {
        const didSave = await typesSaveRef.current?.();
        if (!didSave) return;
        completed.push('Project Types');
      }
      if (!hasOtherChanges) {
        setSaved(true);
        return;
      }
      if (!config) return;
    const limits = { ...config.limits };
    const whole = ['research_rounds', 'turns_per_round', 'output_tokens_per_call', 'max_concurrent_sessions'] as const;
    for (const field of whole) {
      const value = Number(limits[field]);
      if (!Number.isInteger(value) || value < 1) { setError('Enter positive whole numbers for research limits.'); setTab('limits'); return; }
      (limits as any)[field] = value;
    }
    limits.scheduler_version = 2;
    limits.model_calls = limits.research_rounds * limits.turns_per_round * 2;
    for (const field of ['session_duration_minutes', 'maximum_input_tokens_per_session'] as const) {
      const raw = limits[field] as number | string | null;
      (limits as any)[field] = raw === '' || raw === null ? null : Number(raw);
    }
    const cost = limits.maximum_estimated_cost_usd as number | string | null;
    limits.maximum_estimated_cost_usd = cost === '' || cost == null ? null : Number(cost);
      const next = await putJson('/api/user-preferences/research-settings', {
        limits, ai_model: config.ai_model, reasoning_effort: config.reasoning_effort,
        show_advanced_outcome_details: config.show_advanced_outcome_details,
      });
      setConfig(next);
      completed.push('Limits and Outcome preference');
      await putJson('/api/user-preferences/unattended-execution', {
        allow_unattended_background_execution: prefs.allow_unattended_background_execution,
      });
      completed.push('Unattended execution');
      await putJson('/api/user-preferences/section-layout', {
        expand_one_project_section_at_a_time: prefs.expand_one_project_section_at_a_time,
      });
      completed.push('Section layout');
      if (progressAvailable) {
        await putJson('/api/user-preferences/progress-email', { enabled: prefs.progress_email });
        completed.push('Progress email');
      }
      window.dispatchEvent(new CustomEvent('sigma-section-layout-preference-changed', {
        detail: prefs.expand_one_project_section_at_a_time,
      }));
      savedSnapshot.current = JSON.stringify({ config: next, prefs });
      setSaved(true);
      window.dispatchEvent(new Event('sigma-global-settings-saved'));
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : String(cause);
      // Never claim atomicity across independent settings endpoints. The
      // unsaved edits stay on screen, and retry replays idempotent PUTs.
      setError(completed.length
        ? message + '. Partially saved: ' + completed.join(', ') + '. Other edits remain unsaved; retry Save to finish.'
        : message);
    }
    finally { setBusy(false); }
  }
  async function reloadEthos() {
    setEthosBusy(true); setEthosError('');
    try {
      const next = await readJson('/api/user-preferences/research-ethos') as EthosConfig;
      setEthos(next);
      setEthosDraft(next.markdown);
    } catch (cause) { setEthosError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setEthosBusy(false); }
  }
  async function recoverEthos() {
    if (!window.confirm('This preserves an invalid Research Ethos override in a private backup, then restores the built-in Ethos. Continue?')) return;
    setEthosBusy(true); setEthosError('');
    try {
      const response = await fetch('/api/user-preferences/research-ethos/recover', {
        method: 'POST', headers,
      });
      const next = await response.json();
      if (!response.ok) throw new Error(next.detail ?? next.error ?? 'Research Ethos recovery failed');
      setEthos(next as EthosConfig);
      setEthosDraft((next as EthosConfig).markdown);
    } catch (cause) { setEthosError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setEthosBusy(false); }
  }
  async function saveEthos(markdown: string | null) {
    if (ethosBusy) return;
    setEthosBusy(true); setEthosError('');
    try {
      const next = await putJson('/api/user-preferences/research-ethos', { markdown }) as EthosConfig;
      setEthos(next);
      setEthosDraft(next.markdown);
      setEthosEditing(false);
    } catch (cause) {
      setEthosError(cause instanceof Error ? cause.message : String(cause));
    } finally { setEthosBusy(false); }
  }
  const changeTab = (next: Tab) => { setTab(next); setError(''); };
  // Closing discards all unpersisted draft settings and embedded project types
  // by unmounting this dialog. Only explicit Save sends their PUT requests.
  const cancelAndClose = () => { if (!busy && !typesSaveState.busy && !ethosBusy) onClose(); };
  async function copyEthos() {
    if (!ethos || ethosEditing) return;
    try {
      await navigator.clipboard.writeText(ethos.markdown);
      setEthosCopied(true);
      setEthosError('');
    } catch {
      setEthosError('Could not copy Research Ethos. Check clipboard permissions and try again.');
    }
  }
  return <dialog ref={dialog} className={`project-settings-dialog sigma-global-settings sigma-global-settings--${tab}`} aria-labelledby="sigma-global-settings-title"
    onCancel={event => { event.preventDefault(); event.stopPropagation(); cancelAndClose(); }}
    onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); cancelAndClose(); } }}>
    <div className="sigma-global-settings-content">
      <header className="settings-header">
        <h2 id="sigma-global-settings-title">Settings</h2>
        <div className="settings-actions">
          <button type="button" disabled={!canSave} onClick={() => void save()}>{busy || typesSaveState.busy ? 'Saving…' : 'Save'}</button>
          <DialogDismissButton label="Close Settings" disabled={busy || typesSaveState.busy || ethosBusy} onClick={cancelAndClose}/>
        </div>
      </header>
      <nav className="settings-tabs" role="tablist" aria-label="Settings">
        {tabs.map(item => <button type="button" key={item.id} role="tab" aria-selected={tab === item.id}
          onClick={() => changeTab(item.id)}>{item.title}</button>)}

      </nav>
      <section role="tabpanel" hidden={tab !== 'types'}>
        <ProjectTypesDialog embedded onClose={() => {}} onSaveStateChange={onTypesSaveStateChange} saveHandleRef={typesSaveRef} renderIcon={(item: ProjectTypeRecord) => <ProjectTypeIcon item={item}/>} />
      </section>
      {tab !== 'types' && <div className="settings-body">
        {!loaded && !error && <p role="status">Loading your settings…</p>}
        {config && tab === 'limits' && <fieldset disabled={busy} className="sigma-global-limits">
          <div className="sigma-global-limit-row">
            <div className="sigma-global-limit-field">
              <label htmlFor="sigma-global-concurrent">Max concurrent sessions</label>
              <input id="sigma-global-concurrent" type="number" min={1} max={4} value={config.limits.max_concurrent_sessions}
                onChange={e => setLimit('max_concurrent_sessions', e.target.value)}/>
            </div>
            <div className="sigma-global-limit-field">
              <label htmlFor="sigma-global-rounds">Research rounds</label>
              <input id="sigma-global-rounds" type="number" min={1} max={60} value={config.limits.research_rounds}
                onChange={e => setLimit('research_rounds', e.target.value)}/>
            </div>
            <div className="sigma-global-limit-field">
              <label htmlFor="sigma-global-turns">Turns per round</label>
              <input id="sigma-global-turns" type="number" min={1} max={20} value={config.limits.turns_per_round}
                onChange={e => setLimit('turns_per_round', e.target.value)}/>
            </div>
          </div>
          <div className="sigma-limit-calculation settings-hint" aria-live="polite">
            <div>{config.limits.research_rounds || 0} rounds × {config.limits.turns_per_round || 0} turns × 2 agents (Investigator + Skeptic) = <strong>{Number(config.limits.research_rounds || 0) * Number(config.limits.turns_per_round || 0) * 2} calls per strategy</strong>.</div>
            <div>For 3 enabled strategies: 3 × {Number(config.limits.research_rounds || 0) * Number(config.limits.turns_per_round || 0) * 2} = <strong>{3 * Number(config.limits.research_rounds || 0) * Number(config.limits.turns_per_round || 0) * 2} total calls</strong>.</div>
          </div>
          <div className="sigma-global-limit-row sigma-global-limit-row--ceilings">
            <div className="sigma-global-limit-field">
              <label htmlFor="sigma-global-duration">Max session duration</label>
              <div className="sigma-global-duration-controls">
                <input id="sigma-global-duration" type="number" min={1}
                  max={durationUnit === 'unlimited' ? undefined : Math.floor(10080 / unitMinutes[durationUnit])}
                  readOnly={durationUnit === 'unlimited'}
                  value={durationUnit === 'unlimited' ? '' : String(Number(config.limits.session_duration_minutes || 0) / unitMinutes[durationUnit])}
                  onChange={e => setLimit('session_duration_minutes',
                    e.target.value === '' ? '' : Number(e.target.value) * unitMinutes[durationUnit as Exclude<DurationUnit, 'unlimited'>])}/>
                <SigmaSelect className="sigma-duration-unit-select" ariaLabel="Maximum session duration unit"
                  value={durationUnit} options={[
                    { value: 'minutes', label: 'Minutes' }, { value: 'hours', label: 'Hours' },
                    { value: 'days', label: 'Days' }, { value: 'unlimited', label: 'Unlimited' },
                  ]} onChange={value => {
                    const next = value as DurationUnit;
                    setDurationUnit(next);
                    if (next === 'unlimited') setLimit('session_duration_minutes', null);
                    else if (durationUnit === 'unlimited') setLimit('session_duration_minutes', unitMinutes[next]);
                  }}/>
              </div>
              <p className="settings-hint sigma-duration-help"><span>1 minute to 7 days, or Unlimited.</span><span>Call and usage limits still apply.</span></p>
            </div>
            <div className="sigma-global-limit-field">
              <label htmlFor="sigma-global-input">Max input tokens per session</label>
              <input id="sigma-global-input" type="number" min={4096} max={1000000} placeholder="Unlimited"
                value={textValue(config.limits.maximum_input_tokens_per_session)}
                onChange={e => setLimit('maximum_input_tokens_per_session', e.target.value)}/>
            </div>
            <div className="sigma-global-limit-field">
              <label htmlFor="sigma-global-cost">Max estimated cost (USD)</label>
              <input id="sigma-global-cost" type="number" min={0.01} max={100} step={0.01} placeholder="Unlimited"
                value={textValue(config.limits.maximum_estimated_cost_usd)}
                onChange={e => setLimit('maximum_estimated_cost_usd', e.target.value)}/>
            </div>
          </div>
          <p className="settings-hint sigma-global-limit-footer">Limits apply to new sessions across all your projects. Existing session history is unchanged.</p>
        </fieldset>}
        {config && tab === 'preferences' && <fieldset disabled={busy}>
          <label className="project-preference-checkbox"><input type="checkbox" checked={config.show_advanced_outcome_details}
            onChange={e => setResearch({ show_advanced_outcome_details: e.target.checked })}/>Show advanced Outcome details</label>
          <label className="project-preference-checkbox"><input type="checkbox"
            checked={prefs.expand_one_project_section_at_a_time}
            onChange={e => setPref({ expand_one_project_section_at_a_time: e.target.checked })}/>Expand one project section at a time</label>
          <label className="project-preference-checkbox"><input type="checkbox" checked={prefs.progress_email}
            disabled={!progressAvailable && !prefs.progress_email}
            onChange={e => setPref({ progress_email: e.target.checked })}/>Notify me by email on progress</label>
          <label className="project-preference-checkbox"><input type="checkbox"
            checked={prefs.allow_unattended_background_execution}
            onChange={e => setPref({ allow_unattended_background_execution: e.target.checked })}/>Allow unattended background execution</label>
          <p className="settings-hint">Unattended execution may incur provider usage.</p>
        </fieldset>}
        {tab === 'ethos' && !ethos && <section className="sigma-research-ethos" aria-label="Research Ethos unavailable">
          <p role="status">Research Ethos could not be loaded. Other Settings remain available.</p>
          {ethosError && <p role="alert" className="error">{ethosError}</p>}
          <div className="sigma-ethos-actions">
            <button type="button" disabled={ethosBusy} onClick={() => void reloadEthos()}>Retry</button>
            <button type="button" disabled={ethosBusy} onClick={() => void recoverEthos()}>Recover invalid override</button>
          </div>
          <p className="settings-hint">Recovery is refused for a valid or unsafe file. An invalid override is archived privately, not deleted.</p>
        </section>}
        {tab === 'ethos' && ethos && <section className="sigma-research-ethos" aria-label="Research Ethos">
          <p className="settings-hint">Research Ethos means general principles governing how agents investigate, reason, challenge assumptions, and report findings. It is not a project topic or a publication requirement. Each new run freezes the current Ethos.</p>
          <div className="sigma-ethos-section-heading">
            <h3>Research Ethos</h3>
            <div className="sigma-ethos-inline-controls">
        {tab === 'ethos' && ethos && (ethosEditing ? <span className="sigma-ethos-tab-actions">
          <button type="button" className="sigma-ethos-tab-text-action"
            disabled={ethosBusy || !ethosDraft.trim() || ethosDraft === ethos.markdown}
            onClick={() => void saveEthos(ethosDraft)}>{ethosBusy ? 'Saving…' : 'Save'}</button>
          <button type="button" className="sigma-ethos-tab-text-action" disabled={ethosBusy}
            onClick={() => { setEthosDraft(ethos.markdown); setEthosEditing(false); setEthosError(''); }}>Cancel</button>
        </span> : <><button type="button" className="sigma-ethos-pencil" aria-label="Edit research ethos"
          data-tooltip="Edit research ethos" disabled={ethosBusy}
          onClick={() => { setEthosDraft(ethos.markdown); setEthosEditing(true); setEthosCopied(false); setEthosError(''); }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m4 16 0 4 4 0L20 8l-4-4L4 16zM14 6l4 4"/></svg>
        </button>
        <button type="button" className="sigma-ethos-copy" disabled={ethosBusy}
          aria-label={ethosCopied ? 'Copied Research Ethos' : 'Copy Research Ethos'}
          data-tooltip={ethosCopied ? 'Copied' : 'Copy Research Ethos'}
          onClick={() => void copyEthos()}>
          {ethosCopied
            ? <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 4 4L19 6"/></svg>
            : <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>}
        </button></>)}
            </div>
          </div>
          {ethosEditing ? <>
            <label htmlFor="sigma-ethos-edit">Research Ethos Markdown</label>
            <textarea id="sigma-ethos-edit" rows={16} maxLength={16000} disabled={ethosBusy}
              value={ethosDraft} onChange={event => setEthosDraft(event.target.value)}/>

          </> : <>
            <div className="sigma-ethos-rendered"><RenderedMarkdown body={ethos.markdown}/></div>
            {ethos.is_override && <div className="sigma-ethos-actions">
              <button type="button" className="text-view-link" disabled={ethosBusy}
                onClick={() => { if (window.confirm('Restore the built-in Research Ethos for future research and paper runs?')) void saveEthos(null); }}>Restore Default</button>
            </div>}
          </>}
          {ethosError && <p role="alert" className="error">{ethosError}</p>}
        </section>}
        {error && <p role="alert" className="error">{error}</p>}
        {saved && <p role="status" className="settings-hint">Settings saved.</p>}
      </div>}
    </div>
  </dialog>;
}
