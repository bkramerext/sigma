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
type EvidenceRow = {
  id: string; kind?: 'file' | 'link'; filename?: string; url?: string;
  pages?: number; can_remove?: boolean; enabled?: boolean;
};

function EvidencePlusIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M7 12h10"/></svg>;
}

function EvidenceClipIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="m20 11.5-8.5 8.5a5.5 5.5 0 0 1-7.8-7.8L13 3a3.7 3.7 0 0 1 5.3 5.3l-9.3 9.3a1.9 1.9 0 0 1-2.7-2.7L14.7 6.5"/></svg>;
}

function EvidenceActionIcon({ kind }: { kind: 'enabled' | 'disabled' | 'edit' | 'remove' }) {
  return <svg aria-hidden="true" className="pt-reference-action-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    {kind === 'enabled' || kind === 'disabled' ? <>
      <rect x="4" y="4" width="16" height="16" rx="2"/>
      {kind === 'enabled' && <path d="m8 12 3 3 5-6" strokeWidth="2.3"/>}
    </> : kind === 'edit' ? <>
      <path d="M12 20H4a1 1 0 0 1-1-1v-7"/>
      <path d="m8 16 9.7-9.7 3 3L11 19l-4 1zM16.7 7.3l2-2a2.1 2.1 0 0 1 3 3l-1 1"/>
    </> : <path d="M8 8 16 16M16 8 8 16" strokeWidth="4"/>}
  </svg>;
}

function sourceUrl(value: string, previous = ''): string {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (trimmed.includes('://') || /^[a-z][a-z\d+.-]*:(?!\d)/i.test(trimmed)) return trimmed;
  return (previous.toLowerCase().startsWith('http://') ? 'http://' : 'https://') + trimmed;
}

function sourceUrlError(value: string): string | null {
  if (value.length > 2048) return 'URL must be at most 2,048 characters.';
  try {
    const parsed = new URL(value);
    const domain = /^(?:[a-z\d](?:[a-z\d-]{0,61}[a-z\d])?\.)+[a-z\d](?:[a-z\d-]{0,61}[a-z\d])?$/i;
    if (!['http:', 'https:'].includes(parsed.protocol) || !domain.test(parsed.hostname)
      || parsed.username || parsed.password) return 'Enter a valid public website address, such as example.org.';
    const standardPort = parsed.protocol === 'https:' ? '443' : '80';
    if (parsed.port && parsed.port !== standardPort) return 'Source Material URLs must use the standard HTTP or HTTPS port.';
    return null;
  } catch {
    return 'Enter a valid public website address, such as example.org.';
  }
}

function SourceMaterialLink({ url }: { url: string }) {
  const [title, setTitle] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setTitle(null);
    void fetch('/api/reference-title?url=' + encodeURIComponent(url), {
      signal: controller.signal, headers: { 'X-Sigma-Error-Handled': 'true' },
    }).then(response => response.ok ? response.json() : null)
      .then((result: { title?: string | null } | null) => {
        if (!controller.signal.aborted) setTitle(result?.title?.trim() || null);
      }).catch(() => {});
    return () => controller.abort();
  }, [url]);
  return <a className="sigma-evidence-link" href={url} target="_blank" rel="noopener noreferrer">{title || url}</a>;
}

function SuppliedEvidence({ path, expanded, onToggle, guest, collaborationRevision }: { path: string; expanded: boolean; onToggle: () => void; guest: boolean; collaborationRevision?: number }) {
  const [rows, setRows] = useState<EvidenceRow[]>([]);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const editingOriginalUrl = useRef<string | null>(null);
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const uploadInput = useRef<HTMLInputElement>(null);
  const linkInput = useRef<HTMLInputElement>(null);
  const saving = useRef(false);
  const cancelled = useRef(false);
  const currentPath = useRef(path);
  const currentGuest = useRef(guest);
  currentPath.current = path;
  currentGuest.current = guest;

  async function reload() {
    const response = await fetch('/api/projects/evidence?' + new URLSearchParams({ path }), {
      headers: { 'X-Sigma-Error-Handled': 'true' },
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error ?? result.detail ?? 'Could not load Source Material.');
    if (currentPath.current === path && !currentGuest.current) {
      const latest = result.files as EvidenceRow[];
      if (editingId) {
        const current = latest.find(row => row.id === editingId);
        if (!current || current.url !== editingOriginalUrl.current) {
          cancelled.current = true;
          setEditingId(null);
          editingOriginalUrl.current = null;
          setUrl('');
          setError('This Source Material changed in another window. Your edit was cancelled.');
        }
      }
      setRows(latest);
    }
  }

  useEffect(() => {
    setRows([]); setError(''); setAdding(false); setEditingId(null); setUrl('');
    if (!guest) void reload().catch(cause => setError(cause instanceof Error ? cause.message : String(cause)));
  }, [path, guest]);

  useEffect(() => { if (adding || editingId) linkInput.current?.focus(); }, [adding, editingId]);
  // Reload the collection on committed remote revisions. A draft for a
  // different item (or a new link) must not be cancelled.
  useEffect(() => {
    if (collaborationRevision === undefined || guest) return;
    void reload().catch(cause => setError(cause instanceof Error ? cause.message : String(cause)));
  }, [collaborationRevision, path, guest]);

  function cancelLink() {
    cancelled.current = true;
    setAdding(false); setEditingId(null); editingOriginalUrl.current = null; setUrl(''); setError('');
  }

  async function saveLink() {
    if (saving.current || cancelled.current) return;
    const old = editingId ? rows.find(row => row.id === editingId) : undefined;
    const candidate = sourceUrl(url, old?.url);
    if (!candidate) { cancelLink(); return; }
    const syntaxError = sourceUrlError(candidate);
    if (syntaxError) { setError(syntaxError); return; }
    if (rows.some(row => row.kind === 'link' && row.id !== editingId && row.url === candidate)) {
      setError('Duplicate Source Material URL.');
      return;
    }
    saving.current = true; setBusy(true); setError('');
    try {
      // The same DNS/domain-status service used by Research/Publication Standards.
      // An unverified lookup is transient; only definitive invalidity blocks saving.
      const lookup = await fetch('/api/reference-title?url=' + encodeURIComponent(candidate), {
        headers: { 'X-Sigma-Error-Handled': 'true' },
      });
      if (lookup.ok) {
        const metadata = await lookup.json() as { domain_status?: string };
        if (metadata.domain_status === 'invalid') throw new Error('Website could not be found. Check the address.');
      }
      const endpoint = editingId
        ? '/api/projects/evidence/' + encodeURIComponent(editingId) + '/link'
        : '/api/projects/evidence/link';
      const response = await fetch(endpoint, {
        method: editingId ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
        body: JSON.stringify({ path, url: candidate, ...(editingId ? { expected_url: old?.url } : {}) }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? result.detail ?? 'Could not save link.');
      await reload();
      setAdding(false); setEditingId(null); editingOriginalUrl.current = null; setUrl('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      saving.current = false; setBusy(false);
    }
  }

  async function attach(file: File) {
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/projects/evidence?' + new URLSearchParams({ path, filename: file.name }), {
        method: 'POST', body: file, headers: { 'Content-Type': 'application/pdf', 'X-Sigma-Error-Handled': 'true' },
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? result.detail ?? 'Could not attach file.');
      await reload();
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); if (uploadInput.current) uploadInput.current.value = ''; }
  }

  async function toggleEnabled(entry: EvidenceRow) {
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/projects/evidence/' + encodeURIComponent(entry.id) + '/enabled', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
        body: JSON.stringify({ path, enabled: entry.enabled === false }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? result.detail ?? 'Could not change Source Material state.');
      await reload();
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }

  async function remove(id: string) {
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/projects/evidence/' + encodeURIComponent(id) + '?' + new URLSearchParams({ path }), {
        method: 'DELETE', headers: { 'X-Sigma-Error-Handled': 'true' },
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? result.detail ?? 'Could not remove Source Material.');
      await reload();
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }

  function linkEditor() {
    return <input ref={linkInput} className="sigma-evidence-link-input" aria-label="Source Material link"
      aria-invalid={!!error} inputMode="url" type="text" placeholder="example.org/document"
      value={url} disabled={busy} onChange={event => { setUrl(event.target.value); setError(''); }}
      onBlur={() => { if (!cancelled.current) void saveLink(); }}
      onKeyDown={event => {
        if (event.key === 'Enter') { event.preventDefault(); void saveLink(); }
        if (event.key === 'Escape') { event.preventDefault(); cancelLink(); }
      }}/>;
  }

  return <section className="sigma-description-field sigma-supplied-evidence">
    <div className="sigma-evidence-heading"><h4><button type="button" className="workspace-section-disclosure sigma-subsection-toggle"
      data-tooltip={(expanded ? 'Collapse' : 'Expand') + ' Source Material'}
      aria-expanded={expanded} aria-controls="sigma-supplied-evidence-content" onClick={onToggle}>
      <EvidenceChevron expanded={expanded}/>Source Material
    </button></h4>{!guest && <div className="sigma-evidence-actions">
      <button type="button" className="text-view-link sigma-heading-icon-action" aria-label="Add link" data-tooltip="Add link"
        disabled={busy || rows.length >= 20}
        onClick={() => {
          if (!expanded) onToggle();
          cancelled.current = false;
          setError('');
          if (editingId) setEditingId(null);
          if (!adding) { setUrl(''); setAdding(true); }
          else linkInput.current?.focus();
        }}><EvidencePlusIcon/></button>
      <button type="button" className="text-view-link sigma-heading-icon-action" aria-label="Attach a file" data-tooltip="Attach a file"
        disabled={busy || rows.length >= 20} onClick={() => { if (!expanded) onToggle(); uploadInput.current?.click(); }}><EvidenceClipIcon/></button>
    </div>}</div>
    <input ref={uploadInput} type="file" accept=".pdf,application/pdf" hidden
      onChange={event => { const file = event.target.files?.[0]; if (file) void attach(file); }}/>
    <div id="sigma-supplied-evidence-content" hidden={!expanded}>
      <p className="settings-hint">Files and links SIGMA reads and accepts as true premises for this research. Unlike Research Standards, these define what is true—not how to investigate.</p>
      {rows.map(entry => <div className="sigma-evidence-row" key={entry.id}>
        <div className={'sigma-evidence-item' + (entry.enabled === false ? ' is-disabled' : '')}>
          {entry.kind === 'link'
            ? editingId === entry.id ? linkEditor() : <SourceMaterialLink url={entry.url || ''}/>
            : <a className="sigma-evidence-attachment" href={'/api/projects/evidence/' + encodeURIComponent(entry.id) + '/pdf?' + new URLSearchParams({ path })}
                target="_blank" rel="noopener noreferrer"><EvidenceClipIcon/><span>{entry.filename}</span></a>}
          {editingId === entry.id && error && <span className="sigma-evidence-url-error" role="alert">{error}</span>}
        </div>
        {!guest && editingId !== entry.id && <div className="sigma-evidence-row-actions">
          <button type="button" aria-pressed={entry.enabled !== false}
            aria-label={(entry.enabled === false ? 'Enable ' : 'Disable ') + (entry.filename || entry.url || 'Source Material')}
            data-tooltip={(entry.enabled === false ? 'Enable' : 'Disable') + ' Source Material'}
            disabled={busy} onClick={() => void toggleEnabled(entry)}>
            <EvidenceActionIcon kind={entry.enabled === false ? 'disabled' : 'enabled'}/>
          </button>
          {entry.kind === 'link' && <button type="button" aria-label="Edit Source Material link" data-tooltip="Edit link"
            disabled={busy} onClick={() => { cancelled.current = false; setError(''); setAdding(false); editingOriginalUrl.current = entry.url || ''; setEditingId(entry.id); setUrl(entry.url || ''); }}>
            <EvidenceActionIcon kind="edit"/>
          </button>}
          {entry.can_remove !== false && <button type="button" aria-label={'Remove ' + (entry.filename || entry.url)}
            data-tooltip="Remove Source Material" disabled={busy} onClick={() => void remove(entry.id)}>
            <EvidenceActionIcon kind="remove"/>
          </button>}
        </div>}
      </div>)}
      {adding && <div className="sigma-evidence-row sigma-evidence-adding">
        <div className="sigma-evidence-item">
          {linkEditor()}
          {error && <span className="sigma-evidence-url-error" role="alert">{error}</span>}
        </div>
      </div>}
      {error && !adding && !editingId && <p className="sigma-evidence-url-error" role="alert">{error}</p>}
    </div>
  </section>;
}

function EvidenceChevron({ expanded }: { expanded: boolean }) {
  return <svg aria-hidden="true" className={`disclosure-chevron${expanded ? ' is-expanded' : ''}`} viewBox="0 0 12 12"><path d="m4 2 4 4-4 4"/></svg>;
}

const definitions = [
  { key: 'problem', title: 'Research Problem', help: 'What are we investigating?', rows: 3 },
  { key: 'desired_outcomes', title: 'Desired Outcomes', help: 'What insights or advances are we hoping for?', rows: 4 },
  { key: 'paper_requirements', title: 'Paper Requirements', help: 'What should the finished publication contain?', rows: 4 },
] as const;

export default function ProjectDescriptionEditor({
  view, editing, busy, canEditTitle = true, onBusyChange, onDirtyChange, onExitMode, onSave, guest, collaborationRevision,
}: {
  view: ProjectDescriptionView;
  guest: boolean;
  editing: boolean;
  busy: boolean;
  canEditTitle?: boolean;
  collaborationRevision?: number;
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
    if (editing && canEditTitle) { titleInput.current?.focus(); titleInput.current?.select(); }
  }, [editing, canEditTitle]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || !dirty) return;
    if (!draft.title.trim() || !draft.problem.trim()) {
      setError('Project title and Research Problem are required.');
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
    <SuppliedEvidence path={view.path} guest={guest} collaborationRevision={collaborationRevision} expanded={expandedFields.supplied_evidence ?? true} onToggle={() => toggleField('supplied_evidence')}/>
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
