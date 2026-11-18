import { useRef, useState, useEffect, type FormEvent } from 'react';
import { ScrollingLabel } from './GlobalModelPill';
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
  const [cycleRevision, setCycleRevision] = useState(0);
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    element.showModal();
    return () => { if (element.open) element.close(); };
  }, []);
  const choices: SupervisorMode[] = ['none', 'light', 'heavy'];
  const nextMode = choices[(choices.indexOf(draft.supervisor_mode) + 1) % choices.length];
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
      <h2 id="session-settings-title">{mode === 'start' ? 'Session Settings' : 'Session Settings'}</h2>
      <label className="session-settings-field" htmlFor="session-settings-name">
        <span>Session name (optional)</span>
        <input id="session-settings-name" type="text" maxLength={200} value={draft.name}
          onChange={event => setDraft(current => ({ ...current, name: event.target.value }))}/>
      </label>
      <label className="session-settings-field" htmlFor="session-settings-turns">
        <span>Turns</span>
        <input id="session-settings-turns" type="number" min={Math.max(1, minTurns)} max={1200} step={1}
          disabled={draft.unlimited_turns} value={turns}
          onChange={event => setTurns(event.target.value)}/>
      </label>
      <div className="session-settings-supervisor">
        <span>Supervisor mode</span>
        <button type="button" className="global-model-pill session-settings-supervisor-pill"
          aria-label={'Supervisor mode ' + draft.supervisor_mode + '. Click to cycle.'}
          data-tooltip="Cycle supervisor mode: None, Light, Heavy"
          onClick={() => {
            setDraft(current => ({ ...current, supervisor_mode: nextMode }));
            setCycleRevision(current => current + 1);
          }}>
          <ScrollingLabel value={'Supervisor · ' + draft.supervisor_mode.charAt(0).toUpperCase() + draft.supervisor_mode.slice(1)}
            direction="forward" userCycleRevision={cycleRevision} className="global-model-pill-primary"/>
          <span className="session-settings-supervisor-measure" aria-hidden="true">Supervisor · Heavy</span>
        </button>
      </div>
      <label className="session-settings-check">
        <input type="checkbox" checked={draft.unlimited_turns}
          onChange={event => setDraft(current => ({ ...current, unlimited_turns: event.target.checked }))}/>
        Unlimited turns
      </label>
      <label className="session-settings-check session-settings-brainstorm">
        <span><input type="checkbox" checked={draft.brainstorm_mode}
          onChange={event => setDraft(current => ({ ...current, brainstorm_mode: event.target.checked }))}/>
          Brainstorm mode</span>
        <small>Two investigators instead of an investigator/skeptic pair.</small>
      </label>
      <footer>
        <button type="button" className="session-settings-cancel" onClick={onCancel}>Cancel</button>
        <button type="submit" className="session-settings-apply" disabled={!valid}>Save</button>
      </footer>
    </form>
  </dialog>;
}
