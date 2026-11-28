import { useRef, useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import DialogDismissButton from './DialogDismissButton';
import SigmaSelect from './SigmaSelect';
import './session-settings.css';

export type SupervisorMode = 'none' | 'light' | 'heavy';
export type SessionSettings = {
  name: string;
  supervisor_mode: SupervisorMode;
  unlimited_turns: boolean;
  brainstorm_mode: boolean;
  turn_limit: number;
};

export function defaultSessionSettings(limits?: { research_rounds: number; turns_per_round: number } | null): SessionSettings {
  return {
    name: '',
    supervisor_mode: 'none',
    unlimited_turns: false,
    brainstorm_mode: false,
    turn_limit: limits ? limits.research_rounds * limits.turns_per_round : 20,
  };
}

/** Save valid edits as they are made; the X also flushes the last pending change. */
export default function SessionSettingsDialog({ settings, mode, onClose, onApply }: {
  settings: SessionSettings;
  mode: 'start' | 'edit';
  onClose: (next: SessionSettings) => void;
  onApply: (next: SessionSettings) => void | Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState<SessionSettings>({ ...settings });
  const [turns, setTurns] = useState(String(settings.turn_limit));
  const initialSettings = useRef(JSON.stringify({ ...settings, name: settings.name.trim() }));
  const lastSubmitted = useRef(initialSettings.current);
  const onApplyRef = useRef(onApply);
  onApplyRef.current = onApply;
  const closing = useRef(false);
  const latest = useRef(draft);
  latest.current = draft;

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    element.showModal();
    return () => { if (element.open) element.close(); };
  }, []);

  useEffect(() => {
    const next = { ...draft, name: draft.name.trim() };
    const serialized = JSON.stringify(next);
    if (serialized === lastSubmitted.current) return;
    const timer = window.setTimeout(() => {
      lastSubmitted.current = serialized;
      onApplyRef.current(next);
    }, mode === 'edit' ? 500 : 150);
    return () => window.clearTimeout(timer);
  }, [draft, mode]);

  const close = async () => {
    if (closing.current) return;
    closing.current = true;
    try {
      const next = { ...latest.current, name: latest.current.name.trim() };
      const serialized = JSON.stringify(next);
      // Queue the final snapshot behind earlier auto-saves, and wait before
      // exposing Resume; it must not run using stale Session settings.
      if (serialized !== lastSubmitted.current ||
        (mode === 'edit' && serialized !== initialSettings.current)) {
        lastSubmitted.current = serialized;
        await onApplyRef.current(next);
      }
      onClose(next);
    } finally {
      closing.current = false;
    }
  };
  const minAllowedTurns = 1;
  const updateTurns = (value: string) => {
    setTurns(value);
    const parsed = Number(value);
    if (value.trim() && Number.isInteger(parsed) && parsed >= minAllowedTurns && parsed <= 1200)
      setDraft(current => ({ ...current, turn_limit: parsed }));
  };
  // Session pages hide the underlying Project panes. Mount the modal in the
  // document top layer, not inside a display:none Session pane.
  return createPortal(<dialog ref={dialog} className="project-settings-dialog session-settings-dialog"
    aria-labelledby="session-settings-title" onCancel={event => { event.preventDefault(); void close(); }}>
    <form onSubmit={event => event.preventDefault()}>
      <header className="settings-header session-settings-header">
        <h2 id="session-settings-title">Session Settings</h2>
        <DialogDismissButton label="Close Session Settings" onClick={() => { void close(); }}/>
      </header>
      <div className="session-settings-body">
        <label className="session-settings-field" htmlFor="session-settings-name">
          <span>Session name (optional)</span>
          <input id="session-settings-name" type="text" maxLength={200} value={draft.name}
            onChange={event => setDraft(current => ({ ...current, name: event.target.value }))}/>
        </label>
        <div className="session-settings-turn-row">
          <label className="session-settings-field session-settings-turn-limit" htmlFor="session-settings-turns">
            <span>Turns</span>
            <input id="session-settings-turns" type="number" min={minAllowedTurns} max={1200} step={1}
              disabled={draft.unlimited_turns} value={turns}
              onChange={event => updateTurns(event.target.value)}
              onBlur={() => setTurns(String(draft.turn_limit))}/>
          </label>
          <label className="session-settings-check session-settings-unlimited">
            <input type="checkbox" checked={draft.unlimited_turns}
              onChange={event => setDraft(current => ({ ...current, unlimited_turns: event.target.checked }))}/>
            Unlimited
          </label>
        </div>
        <div className="session-settings-field session-settings-supervisor">
          <label htmlFor="session-settings-supervisor">Steering level</label>
          <SigmaSelect id="session-settings-supervisor" ariaLabel="Steering level"
            value={draft.supervisor_mode}
            options={[{ value: 'none', label: 'None' }, { value: 'light', label: 'Light' }, { value: 'heavy', label: 'Heavy' }]}
            onChange={value => setDraft(current => ({ ...current, supervisor_mode: value as SupervisorMode }))}/>
          <small className="session-settings-supervisor-help">The Supervisor always observes. None offers no nudges; Light gently prompts clarity; Heavy watches more actively for drift and repetition. Neither directs the research.</small>
        </div>
        <label className="session-settings-check session-settings-brainstorm">
          <span><input type="checkbox" checked={draft.brainstorm_mode}
            onChange={event => setDraft(current => ({ ...current, brainstorm_mode: event.target.checked }))}/>
            Brainstorm mode</span>
          <small>Two investigators instead of an investigator/skeptic pair.</small>
        </label>
      </div>
    </form>
  </dialog>, document.body);
}
