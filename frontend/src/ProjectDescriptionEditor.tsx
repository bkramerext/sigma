import { useEffect, useRef, useState, type FormEvent } from 'react';
import RenderedMarkdown from './RenderedMarkdown';
import './project-settings.css';
import './project-description.css';

export type ProjectDescriptionDraft = {
  title: string;
  problem: string;
  desired_outcomes: string;
  paper_requirements: string;
};

type ProjectDescriptionView = { path: string; project: ProjectDescriptionDraft };
type EvidenceRow = { id: string; kind?: 'file' | 'link'; filename?: string; url?: string; pages?: number; can_remove?: boolean };
function EvidencePlusIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M7 12h10"/></svg>;
}
function EvidenceClipIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="m20 11.5-8.5 8.5a5.5 5.5 0 0 1-7.8-7.8L13 3a3.7 3.7 0 0 1 5.3 5.3l-9.3 9.3a1.9 1.9 0 0 1-2.7-2.7L14.7 6.5"/></svg>;
}
function EvidenceRemoveIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>;
}
function SuppliedEvidence({ path, expanded, onToggle }: { path: string; expanded: boolean; onToggle: () => void }) {
  const [rows, setRows] = useState<EvidenceRow[]>([]);
  const [adding, setAdding] = useState(false);
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const uploadInput = useRef<HTMLInputElement>(null);
  const linkInput = useRef<HTMLInputElement>(null);
  const saving = useRef(false);
  async function reload() {
    const response = await fetch(`/api/projects/evidence?${new URLSearchParams({ path })}`, {
      headers: { 'X-Sigma-Error-Handled': 'true' },
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail ?? 'Could not load evidence.');
    setRows(result.files as EvidenceRow[]);
  }
  useEffect(() => { void reload().catch(cause => setError(String(cause))); }, [path]);
  useEffect(() => { if (adding) linkInput.current?.focus(); }, [adding]);
  async function addLink() {
    if (saving.current) return;
    const value = url.trim();
    if (!value) { setAdding(false); return; }
    saving.current = true; setBusy(true); setError('');
    try {
      const normalized = /^https?:\/\//i.test(value) ? value : `https://${value}`;
      const response = await fetch('/api/projects/evidence/link', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
        body: JSON.stringify({ path, url: normalized }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? 'Could not add link.');
      await reload(); setAdding(false); setUrl('');
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { saving.current = false; setBusy(false); }
  }
  async function attach(file: File) {
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/projects/evidence?${new URLSearchParams({ path, filename: file.name })}`, {
        method: 'POST', body: file, headers: { 'Content-Type': 'application/pdf', 'X-Sigma-Error-Handled': 'true' },
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? 'Could not attach file.');
      await reload();
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); if (uploadInput.current) uploadInput.current.value = ''; }
  }
  async function remove(id: string) {
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/projects/evidence/${id}?${new URLSearchParams({ path })}`, {
        method: 'DELETE', headers: { 'X-Sigma-Error-Handled': 'true' },
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? 'Could not remove evidence.');
      await reload();
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }
  return <section className="sigma-description-field sigma-supplied-evidence">
    <div className="sigma-evidence-heading"><h4><button type="button" className="workspace-section-disclosure sigma-subsection-toggle" data-tooltip={`${expanded ? 'Collapse' : 'Expand'} Source Material`} aria-expanded={expanded} aria-controls="sigma-supplied-evidence-content" onClick={onToggle}><EvidenceChevron expanded={expanded}/>Source Material</button></h4><div className="sigma-evidence-actions">
      <button type="button" className="text-view-link sigma-heading-icon-action" aria-label="Add link" data-tooltip="Add link" disabled={busy || adding || rows.length >= 20} onClick={() => setAdding(true)}><EvidencePlusIcon/></button>
      <button type="button" className="text-view-link sigma-heading-icon-action" aria-label="Attach a file" data-tooltip="Attach a file" disabled={busy || rows.length >= 20} onClick={() => uploadInput.current?.click()}><EvidenceClipIcon/></button>
    </div></div>
    <input ref={uploadInput} type="file" accept=".pdf,application/pdf" hidden onChange={event => { const file = event.target.files?.[0]; if (file) void attach(file); }}/>
    <div id="sigma-supplied-evidence-content" hidden={!expanded}>
    <p className="settings-hint">Attached documents and linked sources are read when research starts. Their contents are treated as true premises for this project, with source attribution preserved.</p>
    {rows.map(entry => <div className="sigma-evidence-row" key={entry.id}>
      {entry.kind === 'link'
        ? <a href={entry.url} target="_blank" rel="noopener noreferrer">{entry.url}</a>
        : <a href={`/api/projects/evidence/${entry.id}/pdf?${new URLSearchParams({ path })}`} target="_blank" rel="noopener noreferrer">Attached: {entry.filename}</a>}
      {entry.can_remove !== false && <button type="button" className="text-view-link sigma-evidence-remove" aria-label={`Remove ${entry.filename ?? entry.url}`} data-tooltip="Remove evidence" disabled={busy} onClick={() => void remove(entry.id)}><EvidenceRemoveIcon/></button>}
    </div>)}
    {adding && <input ref={linkInput} className="sigma-evidence-link-input" aria-label="Evidence link" placeholder="Paste a URL" value={url} disabled={busy}
      onChange={event => setUrl(event.target.value)}
      onBlur={() => void addLink()}
      onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); void addLink(); } if (event.key === 'Escape') { setAdding(false); setUrl(''); } }}/>}
    {error && <p className="error" role="alert">{error}</p>}
    </div>
  </section>;
}


function EvidenceChevron({ expanded }: { expanded: boolean }) {
  return <svg aria-hidden="true" className={`disclosure-chevron${expanded ? ' is-expanded' : ''}`} viewBox="0 0 12 12"><path d="m4 2 4 4-4 4"/></svg>;
}

const definitions = [
  { key: 'problem', title: 'Research Subject', help: 'What are we investigating?', rows: 3 },
  { key: 'desired_outcomes', title: 'Desired Outcomes', help: 'What insights or advances are we hoping for?', rows: 4 },
  { key: 'paper_requirements', title: 'Paper Requirements', help: 'What should the finished publication contain?', rows: 4 },
] as const;

export default function ProjectDescriptionEditor({
  view, editing, busy, onBusyChange, onDirtyChange, onExitMode, onSave,
}: {
  view: ProjectDescriptionView;
  editing: boolean;
  busy: boolean;
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
  const [expandedFields, setExpandedFields] = useState<Record<string, boolean>>(() => {
    const entries = ['problem', 'desired_outcomes', 'paper_requirements', 'supplied_evidence'];
    return Object.fromEntries(entries.map(key => {
      const previous = window.localStorage.getItem(`sigma.projectSubsection:${view.path}:${key}`);
      return [key, previous === null ? true : previous === 'true'];
    }));
  });
  const toggleField = (key: string) => {
    setExpandedFields(previous => {
      const next = !(previous[key] ?? true);
      window.localStorage.setItem(`sigma.projectSubsection:${view.path}:${key}`, String(next));
      return { ...previous, [key]: next };
    });
  };
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
    if (editing) { titleInput.current?.focus(); titleInput.current?.select(); }
  }, [editing]);

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
      <h4><button type="button" className="workspace-section-disclosure sigma-subsection-toggle" aria-expanded={expandedFields[field.key] ?? true} aria-controls={`sigma-project-subsection-${field.key}`} data-tooltip={`${expandedFields[field.key] ? 'Collapse' : 'Expand'} ${field.title}`} onClick={() => toggleField(field.key)}><EvidenceChevron expanded={expandedFields[field.key] ?? true}/>{field.title}</button></h4>
      <div id={`sigma-project-subsection-${field.key}`} hidden={!(expandedFields[field.key] ?? true)}>
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
      </div>
    </section>)}
    <SuppliedEvidence path={view.path} expanded={expandedFields.supplied_evidence ?? true} onToggle={() => toggleField('supplied_evidence')}/>
  </div>;

  return     <div className="sigma-description-editor">
    {editing ? <form id="sigma-project-description-form" onSubmit={save}>
      <div className="project-pane-title-line is-renaming sigma-description-title-row">
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
        <span id="project-markdown-slot" className="project-markdown-slot"/>
        <span id="project-markdown-slot-copy" className="project-copy-slot"/>
      </div>
      {fields}
    </>}
  </div>;
}
