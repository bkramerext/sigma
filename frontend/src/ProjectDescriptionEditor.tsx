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
  view, editing, busy, canEditTitle = true, onBusyChange, onDirtyChange, onExitMode, onSave,
}: {
  view: ProjectDescriptionView;
  editing: boolean;
  busy: boolean;
  canEditTitle?: boolean;
  onBusyChange: (busy: boolean) => void;
  onDirtyChange: (dirty: boolean) => void;
  onExitMode: () => void;
  onSave: (draft: ProjectDescriptionDraft) => Promise<void>;
}) {
  const original = (): ProjectDescriptionDraft => ({
    title: view.project.title,
    problem: view.project.problem,
    desired_outcomes: view.project.desired_outcomes ?? '',
    paper_requirements: view.project.paper_requirements ?? '',
  });
  const [draft, setDraft] = useState(original);
  const [error, setError] = useState('');
  const titleInput = useRef<HTMLInputElement>(null);
  const dirty = draft.title !== view.project.title
    || draft.problem !== view.project.problem
    || draft.desired_outcomes !== (view.project.desired_outcomes ?? '')
    || draft.paper_requirements !== (view.project.paper_requirements ?? '');
  useEffect(() => {
    onDirtyChange(editing && dirty);
  }, [editing, dirty, onDirtyChange]);
  useEffect(() => {
    if (!editing) { setDraft(original()); setError(''); }
  }, [editing, view.project.title, view.project.problem,
      view.project.desired_outcomes, view.project.paper_requirements]);
  useEffect(() => {
    if (editing && canEditTitle) { titleInput.current?.focus(); titleInput.current?.select(); }
  }, [editing, canEditTitle]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || !dirty) return;
    if (!draft.title.trim() || !draft.problem.trim()) {
      setError('Project title and Research Subject are required.');
      return;
    }
    onBusyChange(true); setError('');
    try {
      await onSave(draft);
      onExitMode();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally { onBusyChange(false); }
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

  return     <div className="sigma-description-editor">
    {editing ? <form id="sigma-project-description-form" onSubmit={save}>
      <div className="project-pane-title-line is-renaming sigma-description-title-row">
        {canEditTitle ? <>
          <label className="sr-only" htmlFor="project-pane-title-input">Project title</label>
          <input id="project-pane-title-input" ref={titleInput} required
            aria-label="Project title" value={draft.title} maxLength={200} disabled={busy}
            onChange={event => setDraft(old => ({ ...old, title: event.target.value }))}/>
        </> : <h3 className="current-project">{view.project.title}</h3>}
      </div>
      {fields}
      {error && <p className="error" role="alert">{error}</p>}
    </form> : <>
      <div className="project-pane-title-line">
        <h3 className="current-project">{view.project.title}</h3>
        <span id="project-markdown-slot" className="project-markdown-slot"/>
        <span id="project-markdown-slot-copy" className="project-copy-slot"/>
      </div>
      {fields}
    </>}
  </div>;
}
