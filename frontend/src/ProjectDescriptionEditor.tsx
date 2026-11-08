import { useEffect, useRef, useState, type FormEvent } from 'react';
import RenderedMarkdown from './RenderedMarkdown';
import './project-description.css';

export type ProjectDescriptionDraft = {
  title: string;
  problem: string;
  desired_outcomes: string;
  paper_requirements: string;
};

type ProjectDescriptionView = { project: ProjectDescriptionDraft };

const definitions = [
  { key: 'problem', title: 'Research Subject', help: 'What are we investigating?', rows: 3 },
  { key: 'desired_outcomes', title: 'Desired Outcomes', help: 'What insights or advances are we hoping for?', rows: 4 },
  { key: 'paper_requirements', title: 'Paper Requirements', help: 'What should the finished publication contain?', rows: 4 },
] as const;

export default function ProjectDescriptionEditor({
  view, disabled, onEnterMode, onExitMode, onSave,
}: {
  view: ProjectDescriptionView;
  disabled: boolean;
  onEnterMode: () => boolean;
  onExitMode: () => void;
  onSave: (draft: ProjectDescriptionDraft) => Promise<void>;
}) {
  const original = (): ProjectDescriptionDraft => ({
    title: view.project.title,
    problem: view.project.problem,
    desired_outcomes: view.project.desired_outcomes ?? '',
    paper_requirements: view.project.paper_requirements ?? '',
  });
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(original);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const trigger = useRef<HTMLButtonElement>(null);
  const titleInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!editing) setDraft(original());
  }, [editing, view.project.title, view.project.problem,
      view.project.desired_outcomes, view.project.paper_requirements]);
  useEffect(() => {
    if (editing) { titleInput.current?.focus(); titleInput.current?.select(); }
  }, [editing]);

  async function save(event?: FormEvent) {
    event?.preventDefault();
    if (busy) return;
    if (!draft.title.trim() || !draft.problem.trim()) {
      setError('Project title and Research Subject are required.');
      return;
    }
    setBusy(true); setError('');
    try {
      await onSave(draft);
      setEditing(false);
      onExitMode();
      requestAnimationFrame(() => trigger.current?.focus());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally { setBusy(false); }
  }

  const fields = <div className="sigma-description-fields">
    {definitions.map(field => <section key={field.key} className="sigma-description-field">
      <h4>{field.title}</h4>
      <p className="settings-hint">{field.help}</p>
      {editing ? <textarea
        aria-label={field.title} required={field.key === 'problem'}
        rows={field.rows} maxLength={20000} disabled={busy}
        value={draft[field.key]}
        onChange={event => setDraft(old => ({ ...old, [field.key]: event.target.value }))}
      /> : <div className="sigma-description-rendered">
        {(view.project[field.key] ?? '').trim()
          ? <RenderedMarkdown body={view.project[field.key]}/>
          : <p className="settings-hint">Not specified.</p>}
      </div>}
    </section>)}
  </div>;

  return <div className="sigma-description-editor">
    {editing ? <form onSubmit={save} onKeyDownCapture={event => {
      if (event.key !== 'Escape' || event.nativeEvent.isComposing) return;
      // Escape commits the entire project description, not the browser's
      // enclosing dialog/panel shortcut. Failed validation keeps editing open.
      event.preventDefault();
      event.stopPropagation();
      void save();
    }}>
      <div className="project-pane-title-line is-renaming">
        <label className="sr-only" htmlFor="project-pane-title-input">Project title</label>
        <input id="project-pane-title-input" ref={titleInput} required
          aria-label="Project title" value={draft.title} maxLength={200} disabled={busy}
          onChange={event => setDraft(old => ({ ...old, title: event.target.value }))}/>
      </div>
      {fields}

      {error && <p className="error" role="alert">{error}</p>}
    </form> : <>
      <div className="project-pane-title-line">
        <h3 className="current-project">{view.project.title}</h3>
        <button ref={trigger} type="button" disabled={disabled}
          aria-label={'Edit project title and description: ' + view.project.title}
          data-tooltip="Edit text and description"
          className="text-view-link text-view-icon workspace-icon-button project-title-pencil"
          onClick={() => { if (onEnterMode()) { setDraft(original()); setEditing(true); } }}>
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
            <path d="m15 5 4 4M4 20l4.5-1 11-11a2.83 2.83 0 0 0-4-4l-11 11L4 20Z"/>
          </svg>
        </button>
        <span id="project-markdown-slot" className="project-markdown-slot"/>
        <span id="project-markdown-slot-copy" className="project-copy-slot"/>
      </div>
      {fields}
    </>}
  </div>;
}
