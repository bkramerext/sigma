import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import './project-types.css';

export type ProjectTypeRecord = {
  id: string;
  name: string;
  scope: string;
  based_on?: string | null;
  user_defined: boolean;
  icon: { kind: string; key?: string; data_uri?: string; view_box?: string; elements?: Array<{ tag: string; attrs?: Record<string, string | number>; text?: string; children?: Array<{ tag: string; attrs?: Record<string, string | number>; text?: string; children?: never }> }> };
  research_standards_references: string[];
  publication_standards_references: string[];
  origin?: string | null;
  behavior?: Record<string, boolean>;
};

type Props = { onClose: () => void; renderIcon: (item: ProjectTypeRecord) => ReactNode };
const blank = (icon: ProjectTypeRecord['icon']): ProjectTypeRecord => ({ id: crypto.randomUUID(), name: '', scope: '', user_defined: true, icon: structuredClone(icon), research_standards_references: [], publication_standards_references: [] });

function BasedOnPicker({ value, options, renderIcon, onChoose }: {
  value: string | null | undefined;
  options: ProjectTypeRecord[];
  renderIcon: Props['renderIcon'];
  onChoose: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const selected = options.find(option => option.id === value);
  const widestName = options.reduce((longest, option) => option.name.length > longest.length ? option.name : longest, "None");
  useEffect(() => {
    if (!expanded) return;
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setExpanded(false);
    };
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [expanded]);
  return <div className="research-type-picker pt-based-on-picker" ref={root}>
    <span className="pt-picker-width-measure" aria-hidden="true"><span className="pt-picker-icon-space"/><span>{widestName}</span><span className="pt-picker-chevron-space"/></span>
    <button ref={trigger} type="button" role="combobox" aria-label="Based on project type" aria-expanded={expanded}
      aria-haspopup="listbox" onClick={() => setExpanded(open => !open)}
      onKeyDown={event => {
        if (event.key === 'Escape') { setExpanded(false); trigger.current?.focus(); }
        if (event.key === 'ArrowDown') { event.preventDefault(); setExpanded(true); }
      }}>
      {selected && renderIcon(selected)}<span>{selected?.name ?? 'None'}</span>
      <svg className="research-type-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="m2 4 4 4 4-4"/></svg>
    </button>
    {expanded && <div className="research-type-options" role="listbox" aria-label="Based on">
      <button type="button" role="option" aria-selected={!value} onClick={() => { onChoose(''); setExpanded(false); trigger.current?.focus(); }}>None</button>
      {options.map(option => <button key={option.id} type="button" role="option" aria-selected={value === option.id}
        onClick={() => { onChoose(option.id); setExpanded(false); trigger.current?.focus(); }}>
        {renderIcon(option)}<span>{option.name}</span>
      </button>)}
    </div>}
  </div>;
}

export default function ProjectTypesDialog({ onClose, renderIcon }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const first = useRef<HTMLButtonElement>(null);
  const initialCustomIds = useRef<string[]>([]);
  const initialDrafts = useRef('[]');
  const initialCustomNames = useRef<Map<string, string>>(new Map());
  const returnFocus = useRef<HTMLElement | null>(document.activeElement instanceof HTMLElement ? document.activeElement : null);
  const [builtins, setBuiltins] = useState<ProjectTypeRecord[]>([]);
  const [drafts, setDrafts] = useState<ProjectTypeRecord[]>([]);
  const [placeholderIcon, setPlaceholderIcon] = useState<ProjectTypeRecord['icon'] | null>(null);
  const [addingId, setAddingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState('');
  const [error, setError] = useState('');
  const [open, setOpen] = useState<string | null>(null);

  function close() {
    if (dialog.current?.open) dialog.current.close();
    onClose();
    requestAnimationFrame(() => { if (returnFocus.current?.isConnected) returnFocus.current.focus(); });
  }
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (!element.open) element.showModal();
    first.current?.focus();
  }, []);
  async function load() {
    const response = await fetch('/api/project-types', { cache: 'no-store' });
    if (!response.ok) throw new Error('Project types could not be loaded.');
    const data = await response.json() as { project_types: ProjectTypeRecord[]; icons: { placeholder: ProjectTypeRecord['icon'] }; revision: string };
    setBuiltins(data.project_types.filter(item => !item.user_defined));
    const savedCustomTypes = data.project_types.filter(item => item.user_defined);
    initialDrafts.current = JSON.stringify(savedCustomTypes);
    setDrafts(savedCustomTypes);
    setPlaceholderIcon(data.icons.placeholder);
    initialCustomIds.current = data.project_types.filter(item => item.user_defined).map(item => item.id);
    initialCustomNames.current = new Map(data.project_types.filter(item => item.user_defined).map(item => [item.id, item.name]));
    setRevision(data.revision);
  }
  useEffect(() => { void load().catch(cause => setError(cause instanceof Error ? cause.message : String(cause))); }, []);
  const sortedBuiltins = useMemo(() => [...builtins].sort((a, b) => a.name.localeCompare(b.name)), [builtins]);
  const sortedDrafts = useMemo(() => [...drafts].sort((a, b) => a.name.localeCompare(b.name)), [drafts]);
  function edit(id: string, patch: Partial<ProjectTypeRecord>) {
    setDrafts(previous => previous.map(item => item.id === id ? { ...item, ...patch } : item));
  }
  const isDuplicateName = (item: ProjectTypeRecord) => {
    const normalized = item.name.normalize("NFKC").trim().toLocaleLowerCase();
    return !!normalized && [...builtins, ...drafts].some(other => other.id !== item.id && other.name.normalize("NFKC").trim().toLocaleLowerCase() === normalized);
  };
  function add() {
    if (!placeholderIcon) return;
    const item = blank(placeholderIcon);
    setDrafts(previous => [...previous, item]);
    setOpen(item.id);
    setAddingId(item.id);
  }
  function inheritedMetadata(parentId: string) {
    const byId = new Map([...builtins, ...drafts].map(item => [item.id, item]));
    const visited = new Set<string>();
    const chain: ProjectTypeRecord[] = [];
    let current: string | null | undefined = parentId;
    while (current && !visited.has(current) && byId.has(current)) {
      visited.add(current);
      const item = byId.get(current)!;
      chain.push(item);
      current = item.based_on;
    }
    const icon = chain.find(item => item.icon.kind === 'data' || item.icon.key !== 'placeholder')?.icon;
    const research = chain.find(item => item.research_standards_references.length)?.research_standards_references ?? [];
    const publication = chain.find(item => item.publication_standards_references.length)?.publication_standards_references ?? [];
    return { icon: structuredClone(icon ?? placeholderIcon!), research_standards_references: [...research], publication_standards_references: [...publication] };
  }
  function basedOn(id: string, parentId: string) {
    const parent = [...builtins, ...drafts].find(item => item.id === parentId);
    if (!parent) return;
    const seen = new Set([id]);
    let next: string | null | undefined = parentId;
    while (next) {
      if (seen.has(next)) { setError('Project type ancestry cannot contain a cycle.'); return; }
      seen.add(next);
      next = [...builtins, ...drafts].find(item => item.id === next)?.based_on;
    }
    edit(id, { based_on: parent.id, scope: parent.scope, ...inheritedMetadata(parentId), origin: parent.id });
  }
  // The icon is display-only. Resolve its nearest non-placeholder ancestor
  // immediately, including unsaved draft parents, without any AI generation.
  function effectiveIcon(item: ProjectTypeRecord): ProjectTypeRecord['icon'] {
    const byId = new Map([...builtins, ...drafts].map(definition => [definition.id, definition]));
    const seen = new Set<string>();
    let current: ProjectTypeRecord | undefined = item;
    while (current && !seen.has(current.id)) {
      seen.add(current.id);
      if (current.icon.kind === 'data' || current.icon.key !== 'placeholder') return current.icon;
      current = current.based_on ? byId.get(current.based_on) : undefined;
    }
    return placeholderIcon ?? item.icon;
  }
  const renderEffectiveIcon = (item: ProjectTypeRecord): ReactNode =>
    renderIcon({ ...item, icon: effectiveIcon(item) });
  function removeDraft(id: string) {
    setDrafts(previous => previous.filter(candidate => candidate.id !== id));
    setAddingId(previous => previous === id ? null : previous);
    setOpen(previous => previous === id ? null : previous);
  }
  async function save(closeAfter = true) {
    if (JSON.stringify(drafts) === initialDrafts.current) { if (closeAfter) close(); return; }
    setBusy(true); setError('');
    try {
      const removed = initialCustomIds.current.filter(id => !drafts.some(draft => draft.id === id));
      const confirmedRemovals: Record<string, number> = {};
      for (const id of removed) {
        const usageResponse = await fetch(`/api/project-types/${encodeURIComponent(id)}/usage`, { cache: 'no-store' });
        const usage = await usageResponse.json() as { project_count: number };
        if (!usageResponse.ok) throw new Error('Could not check which projects use a removed type.');
        confirmedRemovals[id] = usage.project_count;
        if (usage.project_count && !window.confirm(`Remove “${initialCustomNames.current.get(id) ?? 'this project type'}”? ${usage.project_count} project${usage.project_count === 1 ? '' : 's'} use this type. They will keep their saved type settings and show a missing-type warning.`)) return;
      }
      const response = await fetch('/api/project-types', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_types: drafts, expected_revision: revision, confirmed_removals: confirmedRemovals }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? 'Project types could not be saved. Reload and review any changed types or project usage.');
      await load();
      window.dispatchEvent(new Event('sigma-project-types-updated'));
      setAddingId(null);
      if (closeAfter) close();
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }
  const listEditor = (item: ProjectTypeRecord, field: 'research_standards_references' | 'publication_standards_references', readonly: boolean) => {
    const urls = item[field];
    const label = field === 'research_standards_references' ? 'Research' : 'Publication';
    const setAt = (index: number, value: string) => edit(item.id, { [field]: urls.map((url, i) => i === index ? value : url) });
    if (readonly && urls.length === 0) return null;
    return <table className="pt-reference-table">
      <colgroup>{readonly ? <col/> : <><col/><col/></>}</colgroup>
      <tbody>
        {urls.map((url, index) => <tr key={index}>
          <td>{readonly ? <a href={url} target="_blank" rel="noreferrer">{url}</a> : <input aria-label={`${label} reference URL ${index + 1}`} type="url" value={url} onChange={event => setAt(index, event.target.value)}/>}</td>
          {!readonly && <td><button type="button" disabled={busy} onClick={() => edit(item.id, { [field]: urls.filter((_, i) => i !== index) })}>Remove</button></td>}
        </tr>)}
        {!readonly && <tr className="pt-reference-new-row"><td><button type="button" disabled={busy || urls.some(url => !url.trim())} onClick={() => edit(item.id, { [field]: [...urls, ''] })}>New</button></td><td/></tr>}
      </tbody>
    </table>;
  };
  const card = (item: ProjectTypeRecord, readonly: boolean) => <details className="project-type-card" key={item.id} open={open === item.id}>
    <div className="project-type-card-header">
      <summary onClick={event => { event.preventDefault(); setOpen(previous => previous === item.id ? null : item.id); }}><span className="project-type-card-icon">{renderEffectiveIcon(item)}</span><strong>{item.name || 'New project type'}</strong><small>{readonly ? 'Built-in' : 'Custom'}</small></summary>
      {!readonly && <button type="button" className="project-type-remove" disabled={busy} aria-label={`Remove project type ${item.name || 'new project type'}`} onClick={() => removeDraft(item.id)}>Remove</button>}
    </div>
    <div className="project-type-card-body">
      <label>Name<input value={item.name} disabled={readonly} aria-invalid={!readonly && isDuplicateName(item)} aria-describedby={!readonly && isDuplicateName(item) ? `duplicate-type-${item.id}` : undefined} onChange={event => edit(item.id, { name: event.target.value })}/>{!readonly && isDuplicateName(item) && <span className="pt-validation-error" id={`duplicate-type-${item.id}`} role="alert">Duplicate project type name</span>}</label>
      <label>Scope<input value={item.scope} disabled={readonly} onChange={event => edit(item.id, { scope: event.target.value })}/></label>
      {!readonly && <label>Based on<BasedOnPicker value={item.based_on} options={[...sortedBuiltins, ...sortedDrafts.filter(option => option.id !== item.id)]} renderIcon={renderEffectiveIcon} onChoose={id => id ? basedOn(item.id, id) : edit(item.id, { based_on: null })}/></label>}
      {(!readonly || item.research_standards_references.length > 0) && <section><h3>Research standards references</h3>{listEditor(item, 'research_standards_references', readonly)}</section>}
      {(!readonly || item.publication_standards_references.length > 0) && <section><h3>Publication standards references</h3>{listEditor(item, 'publication_standards_references', readonly)}</section>}
    </div>
  </details>;
  const hasChanges = JSON.stringify(drafts) !== initialDrafts.current;
  const invalidDraft = drafts.some(item => isDuplicateName(item) || !item.name.trim() || !item.scope.trim() || item.icon.kind !== 'data' && item.icon.kind !== 'builtin');
  return <dialog ref={dialog} className="project-types-dialog" aria-labelledby="project-types-title" onCancel={event => { event.preventDefault(); if (!busy) close(); }} onClick={event => { if (event.target === dialog.current && !busy) close(); }} onKeyDownCapture={event => {
    if (event.key !== 'Tab') return;
    const element = dialog.current;
    if (!element) return;
    const focusable = Array.from(element.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], summary, [tabindex]:not([tabindex="-1"])')).filter(candidate => candidate.getClientRects().length > 0);
    if (!focusable.length) { event.preventDefault(); element.focus(); return; }
    const activeIndex = focusable.indexOf(document.activeElement as HTMLElement);
    const nextIndex = event.shiftKey
      ? activeIndex <= 0 ? focusable.length - 1 : activeIndex - 1
      : activeIndex < 0 || activeIndex === focusable.length - 1 ? 0 : activeIndex + 1;
    event.preventDefault();
    focusable[nextIndex].focus();
  }}>
    <header><h2 id="project-types-title">Project Types</h2><div className="project-types-header-actions"><button type="button" disabled={busy || !revision || !hasChanges || invalidDraft} onClick={() => void save()}>{busy ? 'Saving…' : 'Save'}</button><button ref={first} type="button" disabled={busy} onClick={close}>Cancel</button></div></header>
    <div className="project-types-body">
      <section><div className="project-types-section-heading"><h3>User-defined project types</h3>{addingId ? <div><button type="button" disabled={busy || !drafts.find(d => d.id === addingId)?.name.trim() || !drafts.find(d => d.id === addingId)?.scope.trim() || !!drafts.find(d => d.id === addingId && isDuplicateName(d)) || invalidDraft} onClick={() => void save(false)}>Save</button><button type="button" disabled={busy} onClick={() => { setDrafts(previous => previous.filter(d => d.id !== addingId)); setAddingId(null); }}>Cancel</button></div> : <button type="button" disabled={busy || !placeholderIcon} onClick={add}>New</button>}</div>{sortedDrafts.map(item => card(item, false))}</section>
      <section><div className="project-types-section-heading"><h3>Built-in project types</h3><span>(cannot be modified)</span></div>{sortedBuiltins.map(item => card(item, true))}</section>
      {error && <p role="alert">{error}</p>}
    </div>
  </dialog>;
}
