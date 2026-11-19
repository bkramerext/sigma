import { useRef, useState, useEffect, type FormEvent } from 'react';
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
    turn_limit: (limits?.research_rounds ?? 3) * (limits?.turns_per_round ?? 3),
  };
}

export default function SessionSettingsDialog({ settings, mode, minTurns = 0, onCancel, onApply }: {
  settings: SessionSettings;
  mode: 'start' | 'edit';
  minTurns?: number;
  onCancel: () => void;
  onApply: (next: SessionSettings) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState<SessionSettings>({ ...settings });
  const [turns, setTurns] = useState(String(settings.turn_limit));
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    element.showModal();
    return () => { if (element.open) element.close(); };
  }, []);
  const parsedTurns = Number(turns);
  const valid = (draft.unlimited_turns || (Number.isInteger(parsedTurns)
    && parsedTurns >= Math.max(1, minTurns) && parsedTurns <= 1200))
    && draft.name.length <= 200;
  const commit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!valid) return;
    onApply({ ...draft, turn_limit: draft.unlimited_turns
      ? Math.max(1, minTurns, Number.isInteger(parsedTurns) ? parsedTurns : 1)
      : parsedTurns, name: draft.name.trim() });
  };
  return <dialog ref={dialog} className="project-settings-dialog session-settings-dialog" aria-labelledby="session-settings-title"
    onCancel={event => { event.preventDefault(); onCancel(); }}>
    <form onSubmit={commit}>
      <header className="session-settings-header"><h2 id="session-settings-title">Session Settings</h2></header>
      <div className="session-settings-body">
        <label className="session-settings-field" htmlFor="session-settings-name">
          <span>Session name (optional)</span>
          <input id="session-settings-name" type="text" maxLength={200} value={draft.name}
            onChange={event => setDraft(current => ({ ...current, name: event.target.value }))}/>
        </label>
        <div className="session-settings-turn-row">
          <label className="session-settings-field session-settings-turn-limit" htmlFor="session-settings-turns">
            <span>Turns</span>
            <input id="session-settings-turns" type="number" min={Math.max(1, minTurns)} max={1200} step={1}
              disabled={draft.unlimited_turns} value={turns}
              onChange={event => setTurns(event.target.value)}/>
          </label>
          <label className="session-settings-check session-settings-unlimited">
            <input type="checkbox" checked={draft.unlimited_turns}
              onChange={event => setDraft(current => ({ ...current, unlimited_turns: event.target.checked }))}/>
            Unlimited turns
          </label>
        </div>
        <div className="session-settings-field session-settings-supervisor">
          <label htmlFor="session-settings-supervisor">Supervisor mode</label>
          <SigmaSelect id="session-settings-supervisor" ariaLabel="Supervisor mode"
            value={draft.supervisor_mode}
            options={[{ value: 'none', label: 'None' }, { value: 'light', label: 'Light' }, { value: 'heavy', label: 'Heavy' }]}
            onChange={value => setDraft(current => ({ ...current, supervisor_mode: value as SupervisorMode }))}/>
        </div>
        <label className="session-settings-check session-settings-brainstorm">
          <span><input type="checkbox" checked={draft.brainstorm_mode}
            onChange={event => setDraft(current => ({ ...current, brainstorm_mode: event.target.checked }))}/>
            Brainstorm mode</span>
          <small>Two investigators instead of an investigator/skeptic pair.</small>
        </label>
      </div>
      <footer>
        <button type="button" className="session-settings-cancel" onClick={onCancel}>Cancel</button>
        <button type="submit" className="session-settings-apply" disabled={!valid}>{mode === 'start' ? 'Save' : 'Save'}</button>
      </footer>
    </form>
  </dialog>;
}
