import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import './project-types.css';

export type ProjectTypeRecord = {
  id: string;
  name: string;
  scope: string;
  description: string;
  based_on?: string | null;
  user_defined: boolean;
  icon: { kind: string; key?: string; data_uri?: string; view_box?: string; elements?: Array<{ tag: string; attrs?: Record<string, string | number>; text?: string; children?: Array<{ tag: string; attrs?: Record<string, string | number>; text?: string; children?: never }> }> };
  research_standards_references: string[];
  publication_standards_references: string[];
  origin?: string | null;
  behavior?: Record<string, boolean>;
};

type Props = { onClose: () => void; renderIcon: (item: ProjectTypeRecord) => ReactNode };
const blank = (): ProjectTypeRecord => ({ id: crypto.randomUUID(), name: '', scope: '', description: '', user_defined: true, icon: { kind: 'pending' }, research_standards_references: [], publication_standards_references: [] });

export default function ProjectTypesDialog({ onClose, renderIcon }: Props) {
  const [builtins, setBuiltins] = useState<ProjectTypeRecord[]>([]);
  const [drafts, setDrafts] = useState<ProjectTypeRecord[]>([]);
  const [showBuiltins, setShowBuiltins] = useState(true);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState('');
  const [generating, setGenerating] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [open, setOpen] = useState<string | null>(null);

  async function load() {
    const response = await fetch('/api/project-types', { cache: 'no-store' });
    if (!response.ok) throw new Error('Project types could not be loaded.');
    const data = await response.json() as { project_types: ProjectTypeRecord[]; revision: string };
    setBuiltins(data.project_types.filter(item => !item.user_defined));
    setDrafts(data.project_types.filter(item => item.user_defined));
    setRevision(data.revision);
  }
  useEffect(() => { void load().catch(cause => setError(cause instanceof Error ? cause.message : String(cause))); }, []);
  const sortedBuiltins = useMemo(() => [...builtins].sort((a, b) => a.name.localeCompare(b.name)), [builtins]);
  const sortedDrafts = useMemo(() => [...drafts].sort((a, b) => a.name.localeCompare(b.name)), [drafts]);
  function edit(id: string, patch: Partial<ProjectTypeRecord>) {
    setDrafts(previous => previous.map(item => item.id === id ? { ...item, ...patch } : item));
  }
  function add() {
    const item = blank();
    setDrafts(previous => [...previous, item]);
    setOpen(item.id);
  }
  function basedOn(id: string, parentId: string) {
    const parent = [...builtins, ...drafts].find(item => item.id === parentId);
    if (!parent) return;
    edit(id, { based_on: parent.id, description: parent.description, scope: parent.scope, icon: structuredClone(parent.icon), research_standards_references: [...parent.research_standards_references], publication_standards_references: [...parent.publication_standards_references], origin: parent.id });
  }
  async function save() {
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/project-types', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_types: drafts, expected_revision: revision }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? 'Project types could not be saved.');
      await load();
      window.dispatchEvent(new Event('sigma-project-types-updated'));
      onClose();
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }
  async function remove(item: ProjectTypeRecord) {
    setBusy(true); setError('');
    try {
      const usageResponse = await fetch(`/api/project-types/${encodeURIComponent(item.id)}/usage`);
      const { project_count: count } = await usageResponse.json() as { project_count: number };
      const confirmed = window.confirm(count ? `Remove “${item.name}”? ${count} project${count === 1 ? '' : 's'} will keep their saved type settings and show a missing-type warning.` : `Remove “${item.name}”?`);
      if (!confirmed) return;
      const response = await fetch(`/api/project-types/${encodeURIComponent(item.id)}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm: true, expected_project_count: count, expected_revision: revision }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? 'Type could not be removed.');
      await load();
      window.dispatchEvent(new Event('sigma-project-types-updated'));
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }
  async function createIcon(item: ProjectTypeRecord) {
    if (!item.name.trim() || !item.scope.trim()) return;
    if (!window.confirm('Generate this icon with OpenAI image generation? This uses the currently selected API-key billing mode and may incur separate API charges.')) return;
    setGenerating(item.id); setError('');
    try {
      const response = await fetch('/api/project-types/icon', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: item.name, scope: item.scope, description: item.description }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? 'Icon generation failed. Your current icon was kept.');
      edit(item.id, { icon: data.icon });
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setGenerating(null); }
  }
  const listEditor = (item: ProjectTypeRecord, field: 'research_standards_references' | 'publication_standards_references', readonly: boolean) => {
    const urls = item[field];
    const setAt = (index: number, value: string) => edit(item.id, { [field]: urls.map((url, i) => i === index ? value : url) });
    return <table className="pt-reference-table"><colgroup><col/><col/></colgroup><thead><tr><th>URL</th><th>Action</th></tr></thead><tbody>
      {urls.map((url, index) => <tr key={`${index}:${url}`}><td>{readonly ? <a href={url} target="_blank" rel="noreferrer">{url}</a> : <input aria-label={`${field === 'research_standards_references' ? 'Research' : 'Publication'} reference URL ${index + 1}`} type="url" value={url} onChange={event => setAt(index, event.target.value)}/>}</td><td>{!readonly && <button type="button" onClick={() => edit(item.id, { [field]: urls.filter((_, i) => i !== index) })}>Remove</button>}</td></tr>)}
      {!readonly && <tr><td><input aria-label={`New ${field === 'research_standards_references' ? 'research' : 'publication'} reference URL`} type="url" placeholder="https://" value="" readOnly/></td><td><button type="button" onClick={() => edit(item.id, { [field]: [...urls, ''] })}>New</button></td></tr>}
    </tbody></table>;
  };
  const card = (item: ProjectTypeRecord, readonly: boolean) => <details className="project-type-card" key={item.id} open={open === item.id} onToggle={event => { if (event.currentTarget.open) setOpen(item.id); }}>
    <summary><span className="project-type-card-icon">{renderIcon(item)}</span><strong>{item.name || 'New project type'}</strong><small>{readonly ? 'Built-in' : 'Custom'}</small></summary>
    <div className="project-type-card-body">
      <label>Name<input value={item.name} disabled={readonly} onChange={event => edit(item.id, { name: event.target.value })}/></label>
      <label>Scope<input value={item.scope} disabled={readonly} onChange={event => edit(item.id, { scope: event.target.value })}/></label>
      <label>Description<textarea value={item.description} disabled={readonly} onChange={event => edit(item.id, { description: event.target.value })}/></label>
      {!readonly && <label>Based on<select value={item.based_on ?? ''} onChange={event => event.target.value ? basedOn(item.id, event.target.value) : edit(item.id, { based_on: null })}><option value="">None</option>{[...sortedBuiltins, ...sortedDrafts.filter(option => option.id !== item.id)].map(option => <option key={option.id} value={option.id}>{option.name}</option>)}</select></label>}
      <section><h3>Icon</h3><div className="project-type-icon-edit"><span>{renderIcon(item)}</span>{!readonly && <><button type="button" disabled={!item.name.trim() || !item.scope.trim() || generating !== null} onClick={() => void createIcon(item)}>{generating === item.id ? 'Creating icon…' : item.icon.kind === 'data' ? 'Recreate icon' : 'Create icon'}</button>{item.icon.kind !== 'data' && <small>Generate an icon from the name and scope to enable Save.</small>}</>}</div></section>
      <section><h3>Research standards references</h3>{listEditor(item, 'research_standards_references', readonly)}</section>
      <section><h3>Publication standards references</h3>{listEditor(item, 'publication_standards_references', readonly)}</section>
      {!readonly && <div className="project-type-card-actions"><button type="button" disabled={busy} onClick={() => void remove(item)}>Remove</button></div>}
    </div>
  </details>;
  return createPortal(<div className="project-types-scrim" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onClose(); }}>
    <section className="project-types-dialog" role="dialog" aria-modal="true" aria-labelledby="project-types-title">
      <header><h2 id="project-types-title">Project Types</h2><div><button type="button" disabled={busy} onClick={onClose}>Cancel</button><button type="button" disabled={busy || drafts.some(item => !item.name.trim() || !item.scope.trim() || item.icon.kind !== 'data' && item.icon.kind !== 'builtin') || drafts.some(item => !item.research_standards_references.every(Boolean) || !item.publication_standards_references.every(Boolean))} onClick={() => void save()}>{busy ? 'Saving…' : 'Save'}</button></div></header>
      <div className="project-types-body"><label className="project-types-checkbox"><input type="checkbox" checked={showBuiltins} onChange={event => setShowBuiltins(event.target.checked)}/>Show built-in project types</label>
        {showBuiltins && <section><h3>Built-in project types</h3>{sortedBuiltins.map(item => card(item, true))}</section>}
        <section><h3>User-defined project types</h3>{sortedDrafts.map(item => card(item, false))}<button type="button" className="project-types-add" disabled={busy} onClick={add}>Add project type</button></section>
        {error && <p role="alert">{error}</p>}
      </div>
    </section>
  </div>, document.body);
}
