import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import './global-model-pill.css';

type ModelChoice = {
  id: string;
  label: string;
  efforts: string[];
  relative_cost: string;
  availability?: string;
};
type ResearchSettings = {
  limits: Record<string, unknown>;
  ai_model: string;
  reasoning_effort: string;
  show_advanced_outcome_details: boolean;
};
const costTier = (s: string) => /^\${1,3}$/.test(s) ? s.length : Number.POSITIVE_INFINITY;
const effortOrder = ['low', 'medium', 'high', 'xhigh'];
const modelName = (m: ModelChoice | undefined, fallback: string) => m?.label.split(' · ')[0] ?? fallback;
function suitableEffort(model: ModelChoice, current: string): string | null {
  if (!model.efforts?.length) return null;
  if (model.efforts.includes(current)) return current;
  const index = effortOrder.indexOf(current);
  return [...model.efforts].sort((a, b) =>
    Math.abs(effortOrder.indexOf(a) - index) - Math.abs(effortOrder.indexOf(b) - index)
    || effortOrder.indexOf(a) - effortOrder.indexOf(b))[0];
}

/** Slide only the changed label, preserving the pill's measured width. */
function ScrollingLabel({ value, direction, className }: {
  value: string;
  direction: 'forward' | 'reverse';
  className: string;
}) {
  const previous = useRef(value);
  const sequence = useRef(0);
  const [slide, setSlide] = useState<{ from: string; to: string; sequence: number } | null>(null);
  useEffect(() => {
    if (previous.current === value) return;
    const from = previous.current;
    previous.current = value;
    sequence.current += 1;
    setSlide({ from, to: value, sequence: sequence.current });
  }, [value]);
  const active = slide?.to === value ? slide : null;
  return <span className={`${className} global-model-pill-slide-viewport`}>
    {active ? <span key={active.sequence} className={`global-model-pill-slide-pair global-model-pill-slide-${direction}`} aria-hidden="true">
      <span className="global-model-pill-slide-out">{active.from}</span>
      <span className="global-model-pill-slide-in">{active.to}</span>
    </span> : <span className="global-model-pill-slide-static">{value}</span>}
  </span>;
}

/** Restores the historic model cycle pill, now persisted as a per-user default. */
export default function GlobalModelPill({ enabled = true }: { enabled?: boolean }) {
  const [settings, setSettings] = useState<ResearchSettings | null>(null);
  const [models, setModels] = useState<ModelChoice[]>([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pending, setPending] = useState<ModelChoice | null>(null);
  const [popup, setPopup] = useState({ left: 8, top: 8 });
  const trigger = useRef<HTMLButtonElement>(null);
  const confirm = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!enabled) { setReady(true); return; }
    let alive = true;
    const refresh = () => {
      void Promise.all([
        fetch('/api/user-preferences/research-settings', { headers: { 'X-Sigma-Error-Handled': 'true' }, cache: 'no-store' }),
        fetch('/api/ai/models', { headers: { 'X-Sigma-Error-Handled': 'true' }, cache: 'no-store' }),
      ]).then(async ([configResponse, catalogResponse]) => {
        if (!configResponse.ok) throw new Error('Sign in to view or change the default model.');
        const config = await configResponse.json() as ResearchSettings;
        const catalog = catalogResponse.ok ? await catalogResponse.json() as { models?: ModelChoice[] } : { models: [] };
        if (alive) { setSettings(config); setModels(Array.isArray(catalog.models) ? catalog.models : []); setError(''); }
      }).catch((cause: unknown) => {
        if (alive) setError(cause instanceof Error ? cause.message : String(cause));
      }).finally(() => { if (alive) setReady(true); });
    };
    refresh();
    window.addEventListener('sigma-global-settings-saved', refresh);
    return () => { alive = false; window.removeEventListener('sigma-global-settings-saved', refresh); };
  }, [enabled]);
  useEffect(() => {
    if (!pending) return;
    const position = () => {
      const bounds = trigger.current?.getBoundingClientRect();
      if (!bounds) return;
      const width = Math.min(320, window.innerWidth - 16);
      const height = 150;
      setPopup({
        left: Math.max(8, Math.min(bounds.left, window.innerWidth - width - 8)),
        top: bounds.bottom + height + 8 < window.innerHeight ? bounds.bottom + 8 : Math.max(8, bounds.top - height - 8),
      });
    };
    position();
    confirm.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setPending(null); trigger.current?.focus(); }
    };
    window.addEventListener('resize', position);
    window.addEventListener('scroll', position, true);
    document.addEventListener('keydown', keydown, true);
    return () => {
      window.removeEventListener('resize', position);
      window.removeEventListener('scroll', position, true);
      document.removeEventListener('keydown', keydown, true);
    };
  }, [pending]);
  const selected = models.find(m => m.id === settings?.ai_model);
  const choices = models.filter(m => m.availability !== 'unavailable' && m.efforts?.length)
    .sort((a, b) => costTier(a.relative_cost) - costTier(b.relative_cost) || a.label.localeCompare(b.label));
  const selectedIndex = choices.findIndex(m => m.id === settings?.ai_model);
  const next = choices.length > 1 ? choices[(selectedIndex - 1 + choices.length) % choices.length]
    : choices.length === 1 && selectedIndex < 0 ? choices[0] : undefined;
  const nextEffort = next && settings ? suitableEffort(next, settings.reasoning_effort) : null;
  const supportedEfforts = selected?.efforts.filter(effort => effortOrder.includes(effort))
    .sort((a, b) => effortOrder.indexOf(a) - effortOrder.indexOf(b)) ?? [];
  const thinkingIndex = supportedEfforts.indexOf(settings?.reasoning_effort ?? '');
  const nextThinking = supportedEfforts.length > 1
    ? supportedEfforts[(thinkingIndex + 1) % supportedEfforts.length] : null;
  const selectedName = modelName(selected, settings?.ai_model ?? 'Unavailable');
  const label = !enabled ? 'Sign in' : settings ? selectedName + (selected?.relative_cost ? ' ' + selected.relative_cost : '') : 'Unavailable';
  const thinkingLabel = settings?.reasoning_effort
    ? 'Thinking · ' + (settings.reasoning_effort === 'xhigh' ? 'Extra High'
      : settings.reasoning_effort.charAt(0).toUpperCase() + settings.reasoning_effort.slice(1))
    : null;
  const notice = nextEffort && settings && nextEffort !== settings.reasoning_effort
    ? ' Switching to ' + modelName(next, '') + ' also changes Thinking to ' + nextEffort + '.' : '';
  const tooltip = !enabled ? 'Sign in to view your default research model.' : settings
    ? 'The selected default model is ' + selectedName + '. Relative published API token cost: ' +
      (selected?.relative_cost ?? 'unknown') + '. Applies to future research and proposals across projects. ' +
      (thinkingLabel ? ' ' + thinkingLabel + '.' : '') +
      ' Click the upper half to cycle models; click the lower half to cycle thinking levels.' + notice
    : error || 'Checking your model selection.';
  async function save(choice: ModelChoice, requestedEffort?: string) {
    if (!settings || busy) return;
    const effort = requestedEffort ?? suitableEffort(choice, settings.reasoning_effort);
    if (!effort) return;
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/user-preferences/research-settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
        body: JSON.stringify({
          limits: settings.limits, ai_model: choice.id, reasoning_effort: effort,
          show_advanced_outcome_details: settings.show_advanced_outcome_details,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? result.error ?? 'Model could not be changed.');
      setSettings(result as ResearchSettings);
      window.dispatchEvent(new Event('sigma-global-settings-saved'));
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }
  function cycle() {
    if (!next || !settings || !nextEffort) return;
    if (selected && costTier(next.relative_cost) > costTier(selected.relative_cost)) setPending(next);
    else void save(next);
  }
  function cycleThinking() {
    if (!selected || !nextThinking || !settings) return;
    void save(selected, nextThinking);
  }
  const dismiss = () => { setPending(null); trigger.current?.focus(); };
  return <span className="global-model-pill-position">
    <button ref={trigger} type="button" className="global-model-pill"
      aria-label={'Model ' + label + (thinkingLabel ? ', ' + thinkingLabel : '')}
      title={tooltip} data-tooltip={tooltip}
      disabled={!enabled || !ready || busy || !!pending || !settings || (!next && !nextThinking)}
      onClick={event => {
        const rect = event.currentTarget.getBoundingClientRect();
        if (event.clientY >= rect.top + rect.height / 2) cycleThinking();
        else cycle();
      }}
      onKeyDown={event => {
        if (event.key === 'ArrowDown') { event.preventDefault(); cycleThinking(); }
      }}>
      <span className="global-model-pill-current">
        <ScrollingLabel className="global-model-pill-primary" value={`Model · ${label}`} direction="forward"/>
        {thinkingLabel && <ScrollingLabel className="global-model-pill-secondary" value={thinkingLabel} direction="forward"/>}
      </span>
      {choices.map(choice => <span key={choice.id} className="global-model-pill-measure" aria-hidden="true">
        Model · {modelName(choice, choice.id)}{choice.relative_cost ? ' ' + choice.relative_cost : ''}
      </span>)}
    </button>
    {settings && error && <span className="global-model-error" role="alert">{error}</span>}
    {pending && createPortal(<div className="project-model-confirm-popover global-model-confirm-popover"
      role="group" aria-label={'Confirm switch to ' + modelName(pending, pending.id)} style={popup}>
      <p><strong>Switch to {modelName(pending, pending.id)}?</strong> Its published API token cost tier
        ({pending.relative_cost}) is higher than the current tier ({selected?.relative_cost ?? 'unknown'}).
        Continue with this user-wide default?</p>
      <div className="project-model-confirm-actions">
        <button ref={confirm} type="button" onClick={() => { const choice = pending; dismiss(); void save(choice); }}>Confirm</button>
        <button type="button" onClick={dismiss}>Cancel</button>
      </div>
    </div>, document.body)}
  </span>;
}
