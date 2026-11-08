import { useCallback, useEffect, useRef, useState } from 'react';
import DialogDismissButton from './DialogDismissButton';
import ProjectTypesDialog, { type ProjectTypeRecord, type ProjectTypesSaveState } from './ProjectTypesDialog';
import RenderedMarkdown from './RenderedMarkdown';
import './global-settings.css';

type Tab = 'types' | 'research' | 'limits' | 'preferences' | 'ethos';
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
type CatalogModel = { id: string; label: string; efforts: string[]; relative_cost: string };
type EthosConfig = { markdown: string; is_override: boolean; version: string; sha256: string };
type Preference = { allow_unattended_background_execution: boolean; expand_one_project_section_at_a_time: boolean; progress_email: boolean };
const modelCost = (value: string) => /^\${1,3}$/.test(value) ? value.length : Number.POSITIVE_INFINITY;
const tabs: { id: Tab; title: string }[] = [
  { id: 'types', title: 'Project Types' },
  { id: 'research', title: 'Model' },
  { id: 'limits', title: 'Limits' },
  { id: 'preferences', title: 'Preferences' },
  { id: 'ethos', title: 'Research Ethos' },
];
const headers = { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' };

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

export default function GlobalSettingsDialog({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState<Tab>('types');
  const [config, setConfig] = useState<ResearchConfig | null>(null);
  const [models, setModels] = useState<CatalogModel[]>([]);
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
  const [restoreDefault, setRestoreDefault] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [typesSaveState, setTypesSaveState] = useState<ProjectTypesSaveState>({ dirty: false, valid: false, busy: false });
  const typesSaveRef = useRef<(() => Promise<boolean>) | null>(null);
  const savedSnapshot = useRef<string | null>(null);
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
      readJson('/api/ai/models').catch(() => ({ models: [] })),
      readJson('/api/user-preferences/research-ethos'),
    ]).then(([research, unattended, layout, progress, catalog, ethosData]) => {
      if (controller.signal.aborted) return;
      setConfig(research as ResearchConfig);
      setEthos(ethosData as EthosConfig);
      setEthosDraft((ethosData as EthosConfig).markdown);
      const minutes = (research as ResearchConfig).limits.session_duration_minutes;
      setDurationUnit(minutes === null ? 'unlimited'
        : minutes % 1440 === 0 ? 'days' : minutes % 60 === 0 ? 'hours' : 'minutes');
      setPrefs({
        allow_unattended_background_execution: !!unattended.allow_unattended_background_execution,
        expand_one_project_section_at_a_time: !!layout.expand_one_project_section_at_a_time,
        progress_email: !!progress.enabled,
      });
      setProgressAvailable(!!progress.available);
      setModels(catalog.models ?? []);
      savedSnapshot.current = JSON.stringify({ config: research, prefs: {
        allow_unattended_background_execution: !!unattended.allow_unattended_background_execution,
        expand_one_project_section_at_a_time: !!layout.expand_one_project_section_at_a_time,
        progress_email: !!progress.enabled,
      } });
      setLoaded(true);
    }).catch(cause => { if (!controller.signal.aborted) setError(String(cause)); });
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
  const ethosDirty = !!ethos && (restoreDefault ? ethos.is_override : ethosDraft !== ethos.markdown);
  const hasChanges = typesSaveState.dirty || hasOtherChanges || ethosDirty;
  const validLimits = !!config && (['research_rounds', 'turns_per_round', 'output_tokens_per_call', 'max_concurrent_sessions'] as const)
    .every(field => Number.isInteger(Number(config.limits[field])) && Number(config.limits[field]) >= 1 && String(config.limits[field]).trim() !== '')
    && (['session_duration_minutes', 'maximum_input_tokens_per_session'] as const)
      .every(field => config.limits[field] == null || (Number.isFinite(Number(config.limits[field])) && Number(config.limits[field]) > 0 && String(config.limits[field]).trim() !== ''))
    && (config.limits.maximum_estimated_cost_usd == null ||
      (Number.isFinite(Number(config.limits.maximum_estimated_cost_usd)) && Number(config.limits.maximum_estimated_cost_usd) > 0 &&
      String(config.limits.maximum_estimated_cost_usd).trim() !== ''));
  // Project Types can be saved independently if another preferences endpoint
  // is unavailable: never strand changes behind an unrelated Settings fetch.
  const canSave = hasChanges && !busy && !typesSaveState.busy &&
    (!typesSaveState.dirty || typesSaveState.valid) &&
    (!hasOtherChanges || (loaded && validLimits)) &&
    (!ethosDirty || restoreDefault || !!ethosDraft.trim());
  async function save() {
    if (!canSave) return;
    setBusy(true); setError(''); setSaved(false);
    try {
      if (typesSaveState.dirty) {
        const didSave = await typesSaveRef.current?.();
        if (!didSave) return;
      }
      if (hasOtherChanges) {
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
      await putJson('/api/user-preferences/unattended-execution', {
        allow_unattended_background_execution: prefs.allow_unattended_background_execution,
      });
      await putJson('/api/user-preferences/section-layout', {
        expand_one_project_section_at_a_time: prefs.expand_one_project_section_at_a_time,
      });
      if (progressAvailable) {
        await putJson('/api/user-preferences/progress-email', { enabled: prefs.progress_email });
      }
      window.dispatchEvent(new CustomEvent('sigma-section-layout-preference-changed', {
        detail: prefs.expand_one_project_section_at_a_time,
      }));
      savedSnapshot.current = JSON.stringify({ config: next, prefs });
      }
      if (ethosDirty) {
        const next = await putJson('/api/user-preferences/research-ethos', {
          markdown: restoreDefault ? null : ethosDraft,
        }) as EthosConfig;
        setEthos(next);
        setEthosDraft(next.markdown);
        setRestoreDefault(false);
        setEthosEditing(false);
      }
      setSaved(true);
      window.dispatchEvent(new Event('sigma-global-settings-saved'));
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }
  const model = models.find(item => item.id === config?.ai_model);
  const changeTab = (next: Tab) => { setTab(next); setError(''); };
  return <dialog ref={dialog} className={`project-settings-dialog sigma-global-settings sigma-global-settings--${tab}`} aria-labelledby="sigma-global-settings-title"
    onCancel={event => { event.preventDefault(); event.stopPropagation(); }}
    onKeyDownCapture={event => { if (event.key === "Escape") event.preventDefault(); }}>
    <div className="sigma-global-settings-content">
      <header className="settings-header">
        <h2 id="sigma-global-settings-title">Settings</h2>
        <div className="settings-actions">
          <button type="button" disabled={!canSave} onClick={() => void save()}>{busy || typesSaveState.busy ? 'Saving…' : 'Save'}</button>
          <DialogDismissButton label="Close Settings" disabled={busy} onClick={onClose}/>
        </div>
      </header>
      <nav className="settings-tabs" role="tablist" aria-label="Settings">
        {tabs.map(item => <button type="button" key={item.id} role="tab" aria-selected={tab === item.id}
          onClick={() => changeTab(item.id)}>{item.title}</button>)}
        <button type="button" className="sigma-ethos-pencil text-view-link text-view-icon workspace-icon-button"
          aria-label="Edit Research Ethos" data-tooltip="Edit Research Ethos"
          disabled={!ethos || busy} onClick={() => { setTab('ethos'); setEthosEditing(true); }}>
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
            <path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/>
          </svg>
        </button>
      </nav>
      <section role="tabpanel" hidden={tab !== 'types'}>
        <ProjectTypesDialog embedded onClose={() => {}} onSaveStateChange={onTypesSaveStateChange} saveHandleRef={typesSaveRef} renderIcon={(item: ProjectTypeRecord) =>
          item.icon.kind === 'data' && item.icon.data_uri ? <img src={item.icon.data_uri} alt=""/> :
          <span className="sigma-settings-type-icon" aria-hidden="true">◈</span>}/>
      </section>
      {tab !== 'types' && <div className="settings-body">
        {!loaded && !error && <p role="status">Loading your settings…</p>}
        {config && tab === 'research' && <fieldset disabled={busy}>
          <label htmlFor="sigma-global-model">Model</label>
          <select id="sigma-global-model" className="sigma-model-select" value={config.ai_model} onChange={event => {
            const selected = models.find(m => m.id === event.target.value);
            setResearch({ ai_model: event.target.value,
              reasoning_effort: selected?.efforts.includes(config.reasoning_effort)
                ? config.reasoning_effort : selected?.efforts[0] ?? config.reasoning_effort });
          }}>
            {!model && <option value={config.ai_model}>{config.ai_model}</option>}
            {[...models].sort((a, b) => modelCost(a.relative_cost) - modelCost(b.relative_cost) || a.label.localeCompare(b.label)).map(item =>
              <option key={item.id} value={item.id}>{item.label} · {item.relative_cost}</option>)}
          </select>
          <label htmlFor="sigma-global-effort">Thinking level</label>
          <select id="sigma-global-effort" className="sigma-effort-select" value={config.reasoning_effort}
            onChange={event => setResearch({ reasoning_effort: event.target.value })}>
            {(model?.efforts ?? [config.reasoning_effort]).map(effort =>
              <option key={effort} value={effort}>{effort.charAt(0).toUpperCase() + effort.slice(1)}</option>)}
          </select>
          <p className="settings-hint">Applies to future research and AI proposals in every project. Active sessions retain their saved configuration.</p>
        </fieldset>}
        {config && tab === 'limits' && <fieldset disabled={busy} className="sigma-global-limits">
          <label htmlFor="sigma-global-concurrent">Maximum concurrent sessions per project</label>
          <input id="sigma-global-concurrent" type="number" min={1} max={4} value={config.limits.max_concurrent_sessions}
            onChange={e => setLimit('max_concurrent_sessions', e.target.value)}/>
          <label htmlFor="sigma-global-rounds">Research rounds</label>
          <input id="sigma-global-rounds" type="number" min={1} max={60} value={config.limits.research_rounds}
            onChange={e => setLimit('research_rounds', e.target.value)}/>
          <label htmlFor="sigma-global-turns">Turns per round</label>
          <input id="sigma-global-turns" type="number" min={1} max={20} value={config.limits.turns_per_round}
            onChange={e => setLimit('turns_per_round', e.target.value)}/>
          <p className="settings-hint">Maximum agent calls per strategy: {Number(config.limits.research_rounds || 0) * Number(config.limits.turns_per_round || 0) * 2} (Investigator + Skeptic per turn).</p>
          <label htmlFor="sigma-global-duration">Maximum session duration</label>
          <div className="sigma-global-duration-controls">
            <input id="sigma-global-duration" type="number" min={1}
              max={durationUnit === 'unlimited' ? undefined : Math.floor(10080 / unitMinutes[durationUnit])}
              readOnly={durationUnit === 'unlimited'}
              value={durationUnit === 'unlimited' ? '' : String(Number(config.limits.session_duration_minutes || 0) / unitMinutes[durationUnit])}
              onChange={e => setLimit('session_duration_minutes',
                e.target.value === '' ? '' : Number(e.target.value) * unitMinutes[durationUnit as Exclude<DurationUnit, 'unlimited'>])}/>
            <select aria-label="Maximum session duration unit" value={durationUnit}
              onChange={e => {
                const next = e.target.value as DurationUnit;
                setDurationUnit(next);
                if (next === 'unlimited') setLimit('session_duration_minutes', null);
                else if (durationUnit === 'unlimited') setLimit('session_duration_minutes', unitMinutes[next]);
              }}>
              <option value="minutes">Minutes</option>
              <option value="hours">Hours</option>
              <option value="days">Days</option>
              <option value="unlimited">Unlimited</option>
            </select>
          </div>
          <p className="settings-hint">1 minute to 7 days, or Unlimited. Call and usage limits still apply.</p>
          <label htmlFor="sigma-global-input">Maximum input tokens per session</label>
          <input id="sigma-global-input" type="number" min={4096} max={1000000} placeholder="Unlimited"
            value={textValue(config.limits.maximum_input_tokens_per_session)}
            onChange={e => setLimit('maximum_input_tokens_per_session', e.target.value)}/>
          <label htmlFor="sigma-global-cost">Maximum estimated session cost (USD)</label>
          <input id="sigma-global-cost" type="number" min={0.01} max={100} step={0.01} placeholder="Unlimited"
            value={textValue(config.limits.maximum_estimated_cost_usd)}
            onChange={e => setLimit('maximum_estimated_cost_usd', e.target.value)}/>
          <p className="settings-hint">Limits apply to new sessions across all your projects. Existing session history is unchanged.</p>
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
        {tab === 'ethos' && ethos && <section className="sigma-research-ethos" aria-label="Research Ethos">
          <p className="settings-hint">Research Ethos means general principles governing how agents investigate, reason, challenge assumptions, and report findings. It is not a project topic or a publication requirement. Each new run freezes the current Ethos.</p>
          {ethosEditing ? <>
            <label htmlFor="sigma-ethos-edit">Research Ethos Markdown</label>
            <textarea id="sigma-ethos-edit" rows={16} maxLength={16000} disabled={busy}
              value={ethosDraft} onChange={event => { setEthosDraft(event.target.value); setRestoreDefault(false); setSaved(false); }}/>
          </> : <>
            <div className="sigma-ethos-rendered"><RenderedMarkdown body={ethos.markdown}/></div>
            {ethos.is_override && <button type="button" className="text-view-link sigma-ethos-restore"
              disabled={busy} onClick={() => {
                if (window.confirm('Restore the built-in Research Ethos when Settings is saved?')) {
                  setRestoreDefault(true); setEthosEditing(false); setEthosError(''); setSaved(false);
                }
              }}>Restore Default</button>}
            {restoreDefault && <p className="settings-hint">Built-in Research Ethos will be restored when you Save Settings.</p>}
          </>}
        </section>}
        {error && <p role="alert" className="error">{error}</p>}
        {saved && <p role="status" className="settings-hint">Settings saved.</p>}
      </div>}
    </div>
  </dialog>;
}
