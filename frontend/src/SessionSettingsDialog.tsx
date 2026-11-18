import { useRef, useState, useEffect, type FormEvent } from 'react';
import { ScrollingLabel } from './GlobalModelPill';
import './session-settings.css';

export type SupervisorMode = 'none' | 'light' | 'heavy';
export type SessionSettings = {
  name: string;
  supervisor_mode: SupervisorMode;
  single_round_unlimited_turns: boolean;
  brainstorm_mode: boolean;
  session_score: boolean;
  research_rounds: number;
  turns_per_round: number;
};

export function defaultSessionSettings(limits?: { research_rounds: number; turns_per_round: number } | null): SessionSettings {
  return {
    name: '',
    supervisor_mode: 'none',
    single_round_unlimited_turns: false,
    brainstorm_mode: false,
    session_score: false,
    research_rounds: limits?.research_rounds ?? 3,
    turns_per_round: limits?.turns_per_round ?? 3,
  };
}

export default function SessionSettingsDialog({ settings, mode, onCancel, onApply }: {
  settings: SessionSettings;
  mode: 'start' | 'edit';
  onCancel: () => void;
  onApply: (next: SessionSettings) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState<SessionSettings>({ ...settings });
  const [rounds, setRounds] = useState(String(settings.research_rounds));
  const [turns, setTurns] = useState(String(settings.turns_per_round));
  const [cycleRevision, setCycleRevision] = useState(0);
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    element.showModal();
    return () => { if (element.open) element.close(); };
  }, []);
  const choices: SupervisorMode[] = ['none', 'light', 'heavy'];
  const nextMode = choices[(choices.indexOf(draft.supervisor_mode) + 1) % choices.length];
  const parsedRounds = Number(rounds);
  const parsedTurns = Number(turns);
  const valid = Number.isInteger(parsedRounds) && parsedRounds >= 1 && parsedRounds <= 60
    && Number.isInteger(parsedTurns) && parsedTurns >= 1 && parsedTurns <= 20
    && parsedRounds * parsedTurns <= 1200 && draft.name.length <= 200;
  const commit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!valid) return;
    onApply({
      ...draft,
      research_rounds: draft.single_round_unlimited_turns ? 1 : parsedRounds,
      turns_per_round: parsedTurns,
      name: draft.name.trim(),
    });
  };
  return <dialog ref={dialog} className="session-settings-dialog" aria-labelledby="session-settings-title"
    onCancel={event => { event.preventDefault(); onCancel(); }}>
    <form onSubmit={commit}>
      <h2 id="session-settings-title">Session settings</h2>
      <label className="session-settings-field" htmlFor="session-settings-name">
        <span>Session name (optional)</span>
        <input id="session-settings-name" type="text" maxLength={200} value={draft.name}
          onChange={event => setDraft(current => ({ ...current, name: event.target.value }))}/>
      </label>
      <div className="session-settings-limits">
        <label className="session-settings-field" htmlFor="session-settings-rounds">
          <span>Research rounds</span>
          <input id="session-settings-rounds" type="number" min={1} max={60} step={1}
            disabled={draft.single_round_unlimited_turns} value={draft.single_round_unlimited_turns ? '1' : rounds}
            onChange={event => setRounds(event.target.value)}/>
        </label>
        <label className="session-settings-field" htmlFor="session-settings-turns">
          <span>Turns per round</span>
          <input id="session-settings-turns" type="number" min={1} max={20} step={1}
            disabled={draft.single_round_unlimited_turns} value={turns}
            onChange={event => setTurns(event.target.value)}/>
        </label>
      </div>
      <div className="session-settings-supervisor">
        <span>Supervisor mode</span>
        <button type="button" className="global-model-pill session-settings-supervisor-pill"
          aria-label={'Supervisor mode ' + draft.supervisor_mode + '. Click to cycle.'}
          data-tooltip={'Cycle supervisor mode: None, Light, Heavy'}
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
        <input type="checkbox" checked={draft.single_round_unlimited_turns}
          onChange={event => setDraft(current => ({ ...current, single_round_unlimited_turns: event.target.checked }))}/>
        Single round, unlimited turns
      </label>
      <label className="session-settings-check session-settings-brainstorm">
        <span><input type="checkbox" checked={draft.brainstorm_mode}
          onChange={event => setDraft(current => ({ ...current, brainstorm_mode: event.target.checked }))}/>
          Brainstorm mode</span>
        <small>Two investigators instead of an investigator/skeptic pair.</small>
      </label>
      <footer>
        <button type="button" className="session-settings-cancel" onClick={onCancel}>Cancel</button>
        <button type="submit" className="session-settings-apply" disabled={!valid}>{mode === 'start' ? 'Start session' : 'Save'}</button>
      </footer>
    </form>
  </dialog>;
}
