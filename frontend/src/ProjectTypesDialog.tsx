import { useEffect, useLayoutEffect, useMemo, useRef, useState, type MutableRefObject, type ReactNode } from 'react';
import './project-types.css';
import DialogDismissButton from './DialogDismissButton';

function ReferenceActionIcon({ kind }: { kind: 'checked' | 'unchecked' | 'edit' | 'remove' }) {
  return <svg className="pt-reference-action-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {kind === 'checked' || kind === 'unchecked' ? <>
      <rect x="4" y="4" width="16" height="16" rx="2"/>
      {kind === 'checked' && <path d="m8 12 3 3 5-6" strokeWidth="2.3"/>}
    </> : kind === 'edit' ? <>
      <path d="M12 20H4a1 1 0 0 1-1-1v-7"/>
      <path d="m8 16 9.7-9.7 3 3L11 19l-4 1zM16.7 7.3l2-2a2.1 2.1 0 0 1 3 3l-1 1"/>
    </> : <path d="M5 5 19 19M19 5 5 19"/>}
  </svg>;
}

export type ProjectTypeRecord = {
  id: string;
  name: string;
  scope: string;
  based_on?: string | null;
  user_defined: boolean;
  icon: { kind: string; key?: string; data_uri?: string; view_box?: string; elements?: Array<{ tag: string; attrs?: Record<string, string | number>; text?: string; children?: Array<{ tag: string; attrs?: Record<string, string | number>; text?: string; children?: never }> }> };
  research_standards_references: Reference[];
  publication_standards_references: Reference[];
  origin?: string | null;
  behavior?: Record<string, boolean>;
};

export type ProjectTypesSaveState = { dirty: boolean; valid: boolean; busy: boolean };
type Props = {
  onClose: () => void;
  renderIcon: (item: ProjectTypeRecord) => ReactNode;
  initialOpenTypeId?: string | null;
  embedded?: boolean;
  onSaveStateChange?: (state: ProjectTypesSaveState) => void;
  saveHandleRef?: MutableRefObject<(() => Promise<boolean>) | null>;
};
type Reference = { name: string; url: string };
type ReferenceField = 'research_standards_references' | 'publication_standards_references';
type ReferenceFields = Pick<ProjectTypeRecord, ReferenceField>;
type ReferencePreferences = Record<string, Partial<Record<ReferenceField, string[]>>>;
type DomainStatus = 'valid' | 'invalid' | 'unverified';
type TitleResult = { title: string | null; status: DomainStatus };
const titleCache = new Map<string, TitleResult>();
const blank = (icon: ProjectTypeRecord['icon']): ProjectTypeRecord => ({ id: crypto.randomUUID(), name: '', scope: '', user_defined: true, icon: structuredClone(icon), research_standards_references: [], publication_standards_references: [] });
const handledErrorHeaders = { 'X-Sigma-Error-Handled': 'true' };
// Mirror the server's URL canonicalization so switches on newly edited custom
// references persist under the normalized URL saved with the project type.
function preferenceUrl(raw: string): string {
  try {
    const parsed = new URL(raw.trim());
    if (!['http:', 'https:'].includes(parsed.protocol)) return raw.trim();
    return `${parsed.protocol}//${parsed.host}${parsed.pathname || '/'}${parsed.search}`;
  } catch { return raw.trim(); }
}
// Store the complete URL, but let people type a normal website address.
// When editing, preserve the original protocol invisibly; new links use HTTPS.
function editableReferenceUrl(value: string): string {
  return value.replace(/^https?:\/\//i, '');
}
function completeReferenceUrl(value: string, previous = ''): string {
  if (!value.trim()) return '';
  if (/^https?:\/\//i.test(value)) return value;
  if (value.includes('://') || /^[a-z][a-z\d+.-]*:(?!\d)/i.test(value)) return value;
  const protocol = previous.toLowerCase().startsWith('http://') ? 'http://' : 'https://';
  return protocol + value;
}
// Bad domain syntax is rejected immediately; DNS checks also catch domains
// that look plausible (such as badbadbad.bad) but do not actually resolve.
function referenceUrlError(value: string): string | null {
  const candidate = value.trim();
  if (!candidate) return null;
  if (value.length > 2048) return 'URL must be at most 2,048 characters.';
  if (!/^https?:\/\//i.test(candidate)) return 'Enter a website address, such as example.org.';
  try {
    const parsed = new URL(candidate);
    const host = parsed.hostname;
    const domain = /^(?:[a-z\d](?:[a-z\d-]{0,61}[a-z\d])?\.)+[a-z\d](?:[a-z\d-]{0,61}[a-z\d])?$/i;
    if (!['http:', 'https:'].includes(parsed.protocol) || !domain.test(host) || parsed.username || parsed.password) {
      return 'Enter a valid public website address, such as example.org.';
    }
    if (parsed.port && (Number(parsed.port) < 1 || Number(parsed.port) > 65535)) {
      return 'Enter a valid port number.';
    }
  } catch {
    return 'Enter a valid public website address, such as example.org.';
  }
  return null;
}

function ReferenceLink({ reference, onResolved, onChecked }: { reference: Reference; onResolved?: (name: string) => void; onChecked?: (status: DomainStatus) => void }) {
  const candidate = reference.url.trim();
  const knownName = reference.name.trim() || candidate;
  const [resolvedTitle, setResolvedTitle] = useState<string | null>(() => titleCache.get(candidate)?.title ?? null);
  useEffect(() => {
    if (!candidate || referenceUrlError(candidate) || knownName !== candidate) {
      setResolvedTitle(null);
      return;
    }
    if (titleCache.has(candidate)) {
      const cached = titleCache.get(candidate)!;
      setResolvedTitle(cached.title);
      onChecked?.(cached.status);
      if (cached.title) onResolved?.(cached.title);
      return;
    }
    setResolvedTitle(null);
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void fetch(`/api/reference-title?url=${encodeURIComponent(candidate)}`, { signal: controller.signal, headers: handledErrorHeaders })
        .then(response => response.ok ? response.json() : Promise.reject())
        .then((data: { title: string | null; domain_status?: string }) => {
          const title = typeof data.title === 'string' && data.title.trim() ? data.title.trim() : null;
          const status: DomainStatus = data.domain_status === 'invalid' ? 'invalid'
            : data.domain_status === 'valid' ? 'valid' : 'unverified';
          titleCache.set(candidate, { title, status });
          if (!controller.signal.aborted) {
            setResolvedTitle(title);
            onChecked?.(status);
            if (title) onResolved?.(title);
          }
        }).catch(() => {
          if (!controller.signal.aborted) {
            titleCache.set(candidate, { title: null, status: 'unverified' });
            setResolvedTitle(null);
            onChecked?.('unverified');
          }
        });
    }, 350);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [candidate, knownName]);
  if (!candidate || referenceUrlError(candidate)) return null;
  return <div className="pt-reference-link">
    <a href={candidate} target="_blank" rel="noopener noreferrer">{knownName === candidate ? resolvedTitle || candidate : knownName}</a>
  </div>;
}

function BasedOnPicker({ value, options, renderIcon, onChoose }: {
  value: string | null | undefined;
  options: ProjectTypeRecord[];
  renderIcon: Props['renderIcon'];
  onChoose: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const optionsRef = useRef<HTMLDivElement>(null);
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
  // The options must escape both the scrollable Project Types body and the
  // modal dialog's clipped border. A native popover renders in the top layer.
  useLayoutEffect(() => {
    if (!expanded || !trigger.current || !optionsRef.current) return;
    const anchor = trigger.current;
    const popup = optionsRef.current;
    popup.showPopover();
    const position = () => {
      const rect = anchor.getBoundingClientRect();
      const availableBelow = Math.max(0, window.innerHeight - rect.bottom - 12);
      const availableAbove = Math.max(0, rect.top - 12);
      const desiredHeight = Math.min(256, popup.scrollHeight + 2);
      const above = availableBelow < desiredHeight && availableAbove > availableBelow;
      const height = Math.max(32, Math.min(256, above ? availableAbove : availableBelow));
      const width = Math.min(rect.width, window.innerWidth - 16);
      popup.style.width = `${width}px`;
      popup.style.maxHeight = `${height}px`;
      popup.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - width - 8))}px`;
      popup.style.top = `${above ? Math.max(8, rect.top - Math.min(desiredHeight, height) - 4) : rect.bottom + 4}px`;
    };
    position();
    window.addEventListener('resize', position);
    window.addEventListener('scroll', position, true);
    return () => {
      window.removeEventListener('resize', position);
      window.removeEventListener('scroll', position, true);
      if (popup.matches(':popover-open')) popup.hidePopover();
    };
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
    {expanded && <div ref={optionsRef} className="research-type-options" popover="manual" role="listbox" aria-label="Based on"
      onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); setExpanded(false); trigger.current?.focus(); } }}>
      <button type="button" role="option" aria-selected={!value} onClick={() => { onChoose(''); setExpanded(false); trigger.current?.focus(); }}>None</button>
      {options.map(option => <button key={option.id} type="button" role="option" aria-selected={value === option.id}
        onClick={() => { onChoose(option.id); setExpanded(false); trigger.current?.focus(); }}>
        {renderIcon(option)}<span>{option.name}</span>
      </button>)}
    </div>}
  </div>;
}

export default function ProjectTypesDialog({ onClose, renderIcon, initialOpenTypeId = null, embedded = false, onSaveStateChange, saveHandleRef }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const embeddedRoot = useRef<HTMLDivElement>(null);
  const explicitlyClosing = useRef(false);
  const first = useRef<HTMLButtonElement>(null);
  const initialCustomIds = useRef<string[]>([]);
  const [savedDrafts, setSavedDrafts] = useState<ProjectTypeRecord[] | null>(null);
  const initialCustomNames = useRef<Map<string, string>>(new Map());
  const returnFocus = useRef<HTMLElement | null>(document.activeElement instanceof HTMLElement ? document.activeElement : null);
  const [builtins, setBuiltins] = useState<ProjectTypeRecord[]>([]);
  const [drafts, setDrafts] = useState<ProjectTypeRecord[]>([]);
  const [commonReferences, setCommonReferences] = useState<ReferenceFields | null>(null);
  const [commonCustomReferences, setCommonCustomReferences] = useState<ReferenceFields>({
    research_standards_references: [], publication_standards_references: [],
  });
  const [savedCommonCustomReferences, setSavedCommonCustomReferences] = useState<ReferenceFields | null>(null);
  const [builtinCustomReferences, setBuiltinCustomReferences] = useState<Record<string, Partial<ReferenceFields>>>({});
  const [savedBuiltinCustomReferences, setSavedBuiltinCustomReferences] = useState<Record<string, Partial<ReferenceFields>> | null>(null);
  const [referencePreferences, setReferencePreferences] = useState<ReferencePreferences>({});
  const [savedReferencePreferences, setSavedReferencePreferences] = useState<ReferencePreferences | null>(null);
  const [placeholderIcon, setPlaceholderIcon] = useState<ProjectTypeRecord['icon'] | null>(null);
  const [addingId, setAddingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState('');
  const [error, setError] = useState('');
  const [open, setOpen] = useState<string | null>(initialOpenTypeId);
  const [editingReferences, setEditingReferences] = useState<Set<string>>(() => new Set());
  // null marks a newly inserted row; existing edits retain their original
  // title and URL so an empty/escaped edit can be cancelled without data loss.
  const referenceEditOrigins = useRef<Map<string, Reference | null>>(new Map());
  const [urlValidation, setUrlValidation] = useState<Record<string, DomainStatus>>({});

  function close() {
    explicitlyClosing.current = true;
    if (dialog.current?.open) dialog.current.close();
    onClose();
    requestAnimationFrame(() => { if (returnFocus.current?.isConnected) returnFocus.current.focus(); });
  }
  useEffect(() => {
    const element = dialog.current;
    if (!element || embedded) return;
    if (!element.open) element.showModal();
    first.current?.focus();
    // Capture Escape before the browser's native dialog close behavior,
    // without swallowing inline editor key handlers.
    const preserveModal = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && element.open && !explicitlyClosing.current) {
        const target = event.target;
        if (target instanceof HTMLElement && target.closest('input, textarea, [role="combobox"], [role="listbox"]')) return;
        event.preventDefault();
        if (!busy) close();
      }
    };
    document.addEventListener('keydown', preserveModal, true);
    return () => document.removeEventListener('keydown', preserveModal, true);
  }, []);
  async function load() {
    const response = await fetch('/api/project-types', { cache: 'no-store', headers: handledErrorHeaders });
    if (!response.ok) throw new Error('Project types could not be loaded.');
    const data = await response.json() as {
      project_types: ProjectTypeRecord[];
      icons: { placeholder: ProjectTypeRecord['icon'] };
      revision: string;
      common_references: ReferenceFields;
      common_custom_references?: ReferenceFields;
      builtin_custom_references?: Record<string, Partial<ReferenceFields>>;
      reference_preferences: ReferencePreferences;
    };
    setCommonReferences(data.common_references);
    const commonCustom = data.common_custom_references ?? {
      research_standards_references: [], publication_standards_references: [],
    };
    setCommonCustomReferences(commonCustom);
    setSavedCommonCustomReferences(structuredClone(commonCustom));
    const builtinsCustom = data.builtin_custom_references ?? {};
    setBuiltinCustomReferences(builtinsCustom);
    setSavedBuiltinCustomReferences(structuredClone(builtinsCustom));
    setReferencePreferences(data.reference_preferences ?? {});
    setSavedReferencePreferences(structuredClone(data.reference_preferences ?? {}));
    setBuiltins(data.project_types.filter(item => !item.user_defined));
    const savedCustomTypes = data.project_types.filter(item => item.user_defined);
    setSavedDrafts(structuredClone(savedCustomTypes));
    setDrafts(savedCustomTypes);
    setPlaceholderIcon(data.icons.placeholder);
    initialCustomIds.current = data.project_types.filter(item => item.user_defined).map(item => item.id);
    initialCustomNames.current = new Map(data.project_types.filter(item => item.user_defined).map(item => [item.id, item.name]));
    setRevision(data.revision);
  }
  useEffect(() => { void load().catch(cause => setError(cause instanceof Error ? cause.message : String(cause))); }, []);
  useEffect(() => {
    if (!initialOpenTypeId || !revision) return;
    const frame = requestAnimationFrame(() => dialog.current
      ?.querySelector<HTMLElement>(`[data-project-type-id="${CSS.escape(initialOpenTypeId)}"]`)
      ?.scrollIntoView({ block: 'center', behavior: 'auto' }));
    return () => cancelAnimationFrame(frame);
  }, [initialOpenTypeId, revision]);
  // Opening a late row must bring its newly expanded contents into the scroll viewport.
  useEffect(() => {
    if (!embedded || !open) return;
    const frame = requestAnimationFrame(() => {
      const container = embeddedRoot.current?.querySelector<HTMLElement>('.project-types-body');
      const card = Array.from(container?.querySelectorAll<HTMLElement>('[data-project-type-id]') ?? [])
        .find(node => node.dataset.projectTypeId === open);
      if (container && card) {
        const viewport = container.getBoundingClientRect();
        const bounds = card.getBoundingClientRect();
        if (bounds.bottom > viewport.bottom || bounds.top < viewport.top) {
          container.scrollTop += bounds.top - viewport.top - 8;
        }
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [embedded, open]);
  const sortedBuiltins = useMemo(() => [...builtins].sort((a, b) => a.name.localeCompare(b.name)), [builtins]);
  const sortedDrafts = useMemo(() => [...drafts].sort((a, b) => a.name.localeCompare(b.name)), [drafts]);
  function edit(id: string, patch: Partial<ProjectTypeRecord>) {
    setError('');
    setDrafts(previous => previous.map(item => item.id === id ? { ...item, ...patch } : item));
    // A changed or removed URL must not leave an invalid disabled-reference
    // preference behind when the custom type is saved.
    for (const field of ['research_standards_references', 'publication_standards_references'] as const) {
      if (!patch[field]) continue;
      const urls = new Set(patch[field].map(ref => preferenceUrl(ref.url)));
      setReferencePreferences(previous => {
        const kept = (previous[id]?.[field] ?? []).filter(url => urls.has(url));
        if (kept.length === (previous[id]?.[field] ?? []).length) return previous;
        const owner = { ...previous[id], [field]: kept };
        if (kept.length === 0) delete owner[field];
        const next = { ...previous, [id]: owner };
        if (!Object.keys(owner).length) delete next[id];
        return next;
      });
    }
  }
  function editCommonReferences(field: ReferenceField, references: Reference[]) {
    setError('');
    setCommonCustomReferences(previous => ({ ...previous, [field]: references }));
    const allowed = new Set([
      ...(commonReferences?.[field] ?? []).map(ref => preferenceUrl(ref.url)),
      ...references.map(ref => preferenceUrl(ref.url)),
    ]);
    setReferencePreferences(previous => {
      const current = previous.common?.[field] ?? [];
      const kept = current.filter(url => allowed.has(url));
      if (kept.length === current.length) return previous;
      const fields: Partial<Record<ReferenceField, string[]>> = { ...previous.common, [field]: kept };
      if (!kept.length) delete fields[field];
      const next: ReferencePreferences = { ...previous, common: fields };
      if (!Object.keys(fields).length) delete next.common;
      return next;
    });
  }
  function editBuiltinReferences(owner: string, field: ReferenceField, references: Reference[]) {
    setError('');
    setBuiltinCustomReferences(previous => {
      const ownerFields = { ...previous[owner], [field]: references };
      if (!references.length) delete ownerFields[field];
      const next = { ...previous };
      if (Object.keys(ownerFields).length) next[owner] = ownerFields;
      else delete next[owner];
      return next;
    });
    const base = builtins.find(item => item.id === owner);
    const allowed = new Set([
      ...(base?.[field] ?? []).map(ref => preferenceUrl(ref.url)),
      ...references.map(ref => preferenceUrl(ref.url)),
    ]);
    setReferencePreferences(previous => {
      const kept = (previous[owner]?.[field] ?? []).filter(url => allowed.has(url));
      if (kept.length === (previous[owner]?.[field] ?? []).length) return previous;
      const fields: Partial<Record<ReferenceField, string[]>> = { ...previous[owner], [field]: kept };
      if (!kept.length) delete fields[field];
      const next: ReferencePreferences = { ...previous, [owner]: fields };
      if (!Object.keys(fields).length) delete next[owner];
      return next;
    });
  }
  function referenceDisabled(owner: string, field: ReferenceField, url: string): boolean {
    return referencePreferences[owner]?.[field]?.includes(preferenceUrl(url)) ?? false;
  }
  function toggleReference(owner: string, field: ReferenceField, url: string) {
    setError('');
    setReferencePreferences(previous => {
      const urls = previous[owner]?.[field] ?? [];
      const canonicalUrl = preferenceUrl(url);
      const updated = urls.includes(canonicalUrl)
        ? urls.filter(candidate => candidate !== canonicalUrl)
        : [...urls, canonicalUrl].sort((left, right) => left.localeCompare(right));
      const fields: Partial<Record<ReferenceField, string[]>> = { ...previous[owner] };
      if (updated.length) fields[field] = updated;
      else delete fields[field];
      const next = { ...previous, [owner]: fields };
      if (!Object.keys(fields).length) delete next[owner];
      return next;
    });
  }
  function referenceToggle(owner: string, field: ReferenceField, reference: Reference) {
    if (!reference.url.trim() || referenceUrlError(reference.url)) return null;
    const disabled = referenceDisabled(owner, field, reference.url);
    const action = disabled ? 'Enable' : 'Disable';
    const label = field === 'research_standards_references' ? 'research' : 'publication';
    return <button type="button" className="pt-reference-toggle" aria-pressed={!disabled}
      aria-label={`${action} ${label} reference ${reference.name || reference.url} for ${owner === 'common' ? 'all project types' : owner}`}
      disabled={busy} data-tooltip={`${action} reference`} onClick={() => toggleReference(owner, field, reference.url)}><ReferenceActionIcon kind={disabled ? 'unchecked' : 'checked'}/></button>;
  }
  const isDuplicateName = (item: ProjectTypeRecord) => {
    const normalized = item.name.normalize("NFKC").trim().toLocaleLowerCase();
    return !!normalized && [...builtins, ...drafts].some(other => other.id !== item.id && other.name.normalize("NFKC").trim().toLocaleLowerCase() === normalized);
  };
  function add() {
    if (!placeholderIcon) return;
    setError('');
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
      const item: ProjectTypeRecord = byId.get(current)!;
      chain.push(item);
      current = item.based_on;
    }
    const icon = chain.find(item => item.icon.kind === 'data' || item.icon.key !== 'placeholder')?.icon;
    const research = chain.flatMap(item => item.research_standards_references).filter((ref, index, refs) => refs.findIndex(other => other.url === ref.url) === index);
    const publication = chain.flatMap(item => item.publication_standards_references).filter((ref, index, refs) => refs.findIndex(other => other.url === ref.url) === index);
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
    setError('');
    setDrafts(previous => previous.filter(candidate => candidate.id !== id));
    setReferencePreferences(previous => {
      if (!previous[id]) return previous;
      const next = { ...previous };
      delete next[id];
      return next;
    });
    setAddingId(previous => previous === id ? null : previous);
    setOpen(previous => previous === id ? null : previous);
  }
  async function save(): Promise<boolean> {
    if (!hasChanges || invalidDraft || busy) return false;
    setBusy(true); setError('');
    try {
      // Validate changed domains, even when Save is clicked before the title
      // lookup has finished. A definite NXDOMAIN is rejected; transient DNS
      // outages must not destroy a valid user-created reference.
      const allUrls = (types: ProjectTypeRecord[], common: ReferenceFields | null,
        builtins: Record<string, Partial<ReferenceFields>> | null): string[] => [
        ...types.flatMap(type => [
          ...type.research_standards_references, ...type.publication_standards_references,
        ].map(ref => ref.url)),
        ...(common ? [...common.research_standards_references, ...common.publication_standards_references].map(ref => ref.url) : []),
        ...Object.values(builtins ?? {}).flatMap(fields => [
          ...(fields.research_standards_references ?? []), ...(fields.publication_standards_references ?? []),
        ].map(ref => ref.url)),
      ];
      const previousUrls = new Set(allUrls(savedDrafts ?? [], savedCommonCustomReferences, savedBuiltinCustomReferences));
      const newUrls = new Set(allUrls(drafts, commonCustomReferences, builtinCustomReferences)
        .filter(url => url.trim() && !previousUrls.has(url)));
      for (const url of newUrls) {
        const cached = titleCache.get(url)?.status ?? urlValidation[url];
        if (cached === 'invalid') throw new Error(`Website could not be found: ${editableReferenceUrl(url)}. Check the address.`);
        if (cached === 'valid') continue;
        try {
          const check = await fetch(`/api/reference-title?url=${encodeURIComponent(url)}`, { headers: handledErrorHeaders });
          if (!check.ok) continue;
          const metadata = await check.json() as { domain_status?: DomainStatus; title?: string | null };
          if (metadata.domain_status === 'invalid') {
            setUrlValidation(previous => ({ ...previous, [url]: 'invalid' }));
            throw new Error(`Website could not be found: ${editableReferenceUrl(url)}. Check the address.`);
          }
          if (metadata.domain_status === 'valid') {
            titleCache.set(url, { status: 'valid', title: metadata.title || null });
            setUrlValidation(previous => ({ ...previous, [url]: 'valid' }));
          }
        } catch (cause) {
          if (cause instanceof Error && cause.message.startsWith('Website could not be found:')) throw cause;
          // A network or DNS outage is not proof that the URL is invalid.
        }
      }
      const removed = initialCustomIds.current.filter(id => !drafts.some(draft => draft.id === id));
      const confirmedRemovals: Record<string, number> = {};
      for (const id of removed) {
        const usageResponse = await fetch(`/api/project-types/${encodeURIComponent(id)}/usage`, { cache: 'no-store', headers: handledErrorHeaders });
        const usage = await usageResponse.json() as { project_count: number };
        if (!usageResponse.ok) throw new Error('Could not check which projects use a removed type.');
        confirmedRemovals[id] = usage.project_count;
        if (usage.project_count && !window.confirm(`Remove “${initialCustomNames.current.get(id) ?? 'this project type'}”? ${usage.project_count} project${usage.project_count === 1 ? '' : 's'} use this type. They will keep their saved type settings and show a missing-type warning.`)) return false;
      }
      const response = await fetch('/api/project-types', { method: 'PUT', headers: { 'Content-Type': 'application/json', ...handledErrorHeaders }, body: JSON.stringify({ project_types: drafts, reference_preferences: referencePreferences, common_custom_references: commonCustomReferences, builtin_custom_references: builtinCustomReferences, expected_revision: revision, confirmed_removals: confirmedRemovals }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? 'Project types could not be saved. Reload and review any changed types or project usage.');
      // Round-trip the saved catalog before closing. Both the Home entry point
      // and the Project Settings shortcut must use the same persisted switches.
      const verifiedResponse = await fetch('/api/project-types', { cache: 'no-store', headers: handledErrorHeaders });
      if (!verifiedResponse.ok) throw new Error('Saved reference settings could not be verified. Reload and review your choices.');
      const verified = await verifiedResponse.json() as { reference_preferences?: ReferencePreferences };
      const signature = (choices: ReferencePreferences) => JSON.stringify(Object.entries(choices)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([owner, fields]) => [owner, Object.entries(fields)
          .filter(([, urls]) => !!urls?.length)
          .sort(([left], [right]) => left.localeCompare(right))
          .map(([field, urls]) => [field, [...urls].sort()])])
        .filter(([, fields]) => (fields as unknown[]).length > 0));
      if (signature(verified.reference_preferences ?? {}) !== signature(referencePreferences)) {
        throw new Error('Reference Enable/Disable changes were not retained. The dialog remains open so you can retry.');
      }
      await load();
      window.dispatchEvent(new Event('sigma-project-types-updated'));
      setAddingId(null);
      if (!embedded) close();
      return true;
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); return false; }
    finally { setBusy(false); }
  }
  const referenceAddButton = (owner: string, field: ReferenceField, references: Reference[], readonly = false, immutableCount = 0) => {
    const pending = references.some((reference, index) => index >= immutableCount &&
      (!reference.url.trim() || (editingReferences.has(`${owner}:${field}:${index}`) &&
        referenceEditOrigins.current.get(`${owner}:${field}:${index}`) === null)));
    if (readonly || references.length - immutableCount >= 100 || pending) return null;
    return <button type="button" className="pt-new-action pt-reference-add" aria-label="New reference"
      data-tooltip="New reference" disabled={busy} onClick={() => {
        const newKey = `${owner}:${field}:${references.length}`;
        referenceEditOrigins.current.set(newKey, null);
        setEditingReferences(previous => new Set(previous).add(newKey));
        const next = [...references, { name: '', url: '' }];
        if (owner === 'common') editCommonReferences(field, next.slice(immutableCount));
        else if (builtins.some(item => item.id === owner)) editBuiltinReferences(owner, field, next.slice(immutableCount));
        else edit(owner, { [field]: next });
      }}><span className="pt-circled-plus" aria-hidden="true">+</span></button>;
  };
  const listEditor = (owner: string, field: ReferenceField, references: Reference[], readonly: boolean, immutableCount = 0) => {
    const label = field === 'research_standards_references' ? 'Research' : 'Publication';
    const update = (next: Reference[]) => {
      if (owner === 'common') editCommonReferences(field, next.slice(immutableCount));
      else if (builtins.some(item => item.id === owner)) editBuiltinReferences(owner, field, next.slice(immutableCount));
      else edit(owner, { [field]: next });
    };
    const setAt = (index: number, typed: string) => update(references.map((reference, i) => {
      const url = completeReferenceUrl(typed, reference.url);
      return i === index ? { name: url, url } : reference;
    }));
    if (readonly && references.length === 0) return null;
    return <table className="pt-reference-table"><tbody>
      {references.map((reference, index) => {
        const isBuiltIn = readonly || index < immutableCount;
        const urlError = !isBuiltIn && (
          referenceUrlError(reference.url)
          || (urlValidation[reference.url] === 'invalid' ? 'Website could not be found. Check the address.' : null)
        );
        const duplicate = !isBuiltIn && !!reference.url.trim() &&
          references.some((other, i) => i !== index && preferenceUrl(other.url) === preferenceUrl(reference.url));
        const errorId = `pt-reference-error-${owner}-${field}-${index}`;
        const rowKey = `${owner}:${field}:${index}`;
        const editing = !isBuiltIn && (editingReferences.has(rowKey) || !reference.url.trim());
        const setResolved = (name: string) => {
          if (owner === 'common') setCommonCustomReferences(previous => ({
            ...previous, [field]: previous[field].map((current, i) => (
              i + immutableCount === index && current.url === reference.url && (!current.name || current.name === current.url)
                ? { ...current, name } : current
            )),
          }));
          else if (builtins.some(item => item.id === owner)) setBuiltinCustomReferences(previous => ({
            ...previous,
            [owner]: {
              ...previous[owner],
              [field]: (previous[owner]?.[field] ?? []).map((current, i) => (
                i + immutableCount === index && current.url === reference.url && (!current.name || current.name === current.url)
                  ? { ...current, name } : current
              )),
            },
          }));
          else setDrafts(previous => previous.map(draft => draft.id !== owner ? draft : {
            ...draft, [field]: draft[field].map((current, i) => (
              i === index && current.url === reference.url && (!current.name || current.name === current.url)
                ? { ...current, name } : current
            )),
          }));
        };
        const stopEditing = () => {
          referenceEditOrigins.current.delete(rowKey);
          setEditingReferences(previous => {
            const next = new Set(previous);
            next.delete(rowKey);
            return next;
          });
        };
        const cancelEditing = () => {
          const original = referenceEditOrigins.current.get(rowKey);
          stopEditing();
          if (original) {
            // Clearing an existing URL restores it, then exposes Remove.
            update(references.map((current, i) => i === index ? original : current));
          } else {
            // Leaving a new, empty URL cancels its insertion completely.
            update(references.filter((_, i) => i !== index));
          }
        };
        const finishEditing = () => {
          if (!reference.url.trim()) { cancelEditing(); return; }
          if (urlError || duplicate) return;
          stopEditing();
        };
        return <tr key={rowKey}><td><div className="pt-reference-entry">
          <div className={referenceDisabled(owner, field, reference.url) ? 'pt-reference-field pt-reference-disabled' : 'pt-reference-field'}>
            {editing ? <input aria-label={`${label} reference URL ${index + 1}`} type="text" inputMode="url"
              placeholder="example.org/guide" value={editableReferenceUrl(reference.url)}
              aria-invalid={!!urlError || duplicate} aria-describedby={urlError || duplicate ? errorId : undefined}
              autoFocus={editingReferences.has(rowKey)}
              onChange={event => {
                setEditingReferences(previous => new Set(previous).add(rowKey));
                setAt(index, event.target.value);
              }}
              onKeyDown={event => {
                if (event.key === 'Enter') { event.preventDefault(); finishEditing(); }
                if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); finishEditing(); }
              }}
              onBlur={finishEditing}/>
              : <ReferenceLink reference={reference} onResolved={isBuiltIn ? undefined : setResolved}
                  onChecked={isBuiltIn ? undefined : status => setUrlValidation(previous =>
                    previous[reference.url] === status ? previous : { ...previous, [reference.url]: status })}/>}
            {urlError && <span className="pt-validation-error" id={errorId} role="alert">{urlError}</span>}
            {duplicate && <span className="pt-validation-error" id={errorId} role="alert">Duplicate reference URL</span>}
          </div>
          {!editing && referenceToggle(owner, field, reference)}
          {!isBuiltIn && !editing && <>
            <button type="button" disabled={busy} onClick={() => {
              referenceEditOrigins.current.set(rowKey, reference);
              setEditingReferences(previous => new Set(previous).add(rowKey));
            }} aria-label="Edit reference" data-tooltip="Edit reference"><ReferenceActionIcon kind="edit"/></button>
            <button type="button" disabled={busy} onClick={() => {
              referenceEditOrigins.current.delete(rowKey);
              setEditingReferences(previous => { const next = new Set(previous); next.delete(rowKey); return next; });
              update(references.filter((_, i) => i !== index));
            }} aria-label="Remove reference" data-tooltip="Remove reference"><ReferenceActionIcon kind="remove"/></button>
          </>}
        </div></td></tr>;
      })}
    </tbody></table>;
  };
  const card = (item: ProjectTypeRecord, readonly: boolean) => <details className="project-type-card" data-project-type-id={item.id} key={item.id} open={open === item.id}>
    <summary onClick={event => { event.preventDefault(); setOpen(previous => previous === item.id ? null : item.id); }}>
      <span className="project-type-card-icon">{renderEffectiveIcon(item)}</span><strong>{item.name || 'New project type'}</strong>
      {!readonly && initialCustomIds.current.includes(item.id) && <button type="button" className="project-type-remove" disabled={busy} aria-label={`Remove project type ${item.name}`} onClick={event => { event.preventDefault(); event.stopPropagation(); removeDraft(item.id); }}>Remove</button>}
      <small>{readonly ? 'Built-in' : 'Custom'}</small>
    </summary>
    <div className="project-type-card-body">
      <label>Name<input value={item.name} disabled={readonly} aria-invalid={!readonly && isDuplicateName(item)} aria-describedby={!readonly && isDuplicateName(item) ? `duplicate-type-${item.id}` : undefined} onChange={event => edit(item.id, { name: event.target.value })}/>{!readonly && isDuplicateName(item) && <span className="pt-validation-error" id={`duplicate-type-${item.id}`} role="alert">Duplicate project type name</span>}</label>
      <label>Scope<input value={item.scope} disabled={readonly} onChange={event => edit(item.id, { scope: event.target.value })}/></label>
      {!readonly && <label>Based on<BasedOnPicker value={item.based_on} options={[...sortedBuiltins, ...sortedDrafts.filter(option => option.id !== item.id)]} renderIcon={renderEffectiveIcon} onChoose={id => id ? basedOn(item.id, id) : edit(item.id, { based_on: null })}/></label>}
      <section><div className="pt-reference-heading"><h3>Research standards references</h3>{referenceAddButton(item.id, 'research_standards_references', [...item.research_standards_references, ...(readonly ? builtinCustomReferences[item.id]?.research_standards_references ?? [] : [])], false, readonly ? item.research_standards_references.length : 0)}</div>{listEditor(item.id, 'research_standards_references', [
        ...item.research_standards_references, ...(readonly ? builtinCustomReferences[item.id]?.research_standards_references ?? [] : []),
      ], false, readonly ? item.research_standards_references.length : 0)}</section>
      <section><div className="pt-reference-heading"><h3>Publication standards references</h3>{referenceAddButton(item.id, 'publication_standards_references', [...item.publication_standards_references, ...(readonly ? builtinCustomReferences[item.id]?.publication_standards_references ?? [] : [])], false, readonly ? item.publication_standards_references.length : 0)}</div>{listEditor(item.id, 'publication_standards_references', [
        ...item.publication_standards_references, ...(readonly ? builtinCustomReferences[item.id]?.publication_standards_references ?? [] : []),
      ], false, readonly ? item.publication_standards_references.length : 0)}</section>
    </div>
  </details>;
  const hasChanges = savedDrafts !== null && (JSON.stringify(drafts) !== JSON.stringify(savedDrafts)
    || JSON.stringify(referencePreferences) !== JSON.stringify(savedReferencePreferences)
    || JSON.stringify(commonCustomReferences) !== JSON.stringify(savedCommonCustomReferences)
    || JSON.stringify(builtinCustomReferences) !== JSON.stringify(savedBuiltinCustomReferences));
  const pendingNewReference = Array.from(editingReferences)
    .some(key => referenceEditOrigins.current.get(key) === null);
  const invalidBuiltinReferences = Object.entries(builtinCustomReferences).some(([owner, fields]) => {
    const base = builtins.find(item => item.id === owner);
    if (!base) return true;
    return (['research_standards_references', 'publication_standards_references'] as const).some(field => {
      const references = fields[field] ?? [];
      const urls = [...base[field], ...references].map(ref => preferenceUrl(ref.url)).filter(Boolean);
      return references.length > 100 || new Set(urls).size !== urls.length ||
        references.some(reference => !!referenceUrlError(reference.url) || urlValidation[reference.url] === 'invalid');
    });
  });
  const invalidDraft = pendingNewReference || invalidBuiltinReferences || Object.entries(commonCustomReferences).some(([field, references]) => {
    const urls = [...(commonReferences?.[field as ReferenceField] ?? []), ...references].map(ref => preferenceUrl(ref.url));
    return references.length > 100 || new Set(urls.filter(Boolean)).size !== urls.filter(Boolean).length ||
      references.some(reference => !!referenceUrlError(reference.url) || urlValidation[reference.url] === 'invalid');
  }) || drafts.some(item =>
    isDuplicateName(item) || !item.name.trim() || !item.scope.trim() ||
    (item.icon.kind !== 'data' && item.icon.kind !== 'builtin') ||
    item.research_standards_references.length > 100 || item.publication_standards_references.length > 100 ||
    [...item.research_standards_references, ...item.publication_standards_references].some(ref =>
      !!referenceUrlError(ref.url) || urlValidation[ref.url] === 'invalid')
  );
  // Expose the existing validation and save operation to the unified Settings header.
  useEffect(() => {
    if (!saveHandleRef) return;
    saveHandleRef.current = save;
    return () => { saveHandleRef.current = null; };
  });
  useEffect(() => {
    onSaveStateChange?.({ dirty: hasChanges, valid: !invalidDraft && !!revision, busy });
  }, [hasChanges, invalidDraft, revision, busy, onSaveStateChange]);
  const content = <>
    {!embedded && <header><h2 id="project-types-title">Project Types</h2><div className="project-types-header-actions"><button type="button" disabled={busy || !revision || !hasChanges || invalidDraft} onClick={() => void save()}>{busy ? 'Saving…' : 'Save'}</button><DialogDismissButton ref={first} label="Close Project Types" disabled={busy} onClick={close}/></div></header>}
    {error && <p role="alert" className="pt-dialog-error">{error}</p>}
    <div className="project-types-body">
      <p className="pt-usage-notice">Reference materials incur higher ChatGPT usage.</p>
      <section><div className="project-types-section-heading"><h3>User-defined project types</h3>{addingId ? <DialogDismissButton label="Cancel adding project type" disabled={busy} onClick={() => removeDraft(addingId)}/> : <button type="button" className="pt-new-action" disabled={busy || !placeholderIcon} onClick={add} aria-label="New project type" data-tooltip="New project type"><span className="pt-circled-plus" aria-hidden="true">+</span></button>}</div>{sortedDrafts.map(item => card(item, false))}</section>
      <section><div className="project-types-section-heading"><h3>Built-in project types</h3><span>(curated defaults protected)</span></div>{sortedBuiltins.map(item => card(item, true))}</section>
      <section className="pt-common-references">
        <div className="pt-reference-heading"><h4>Research standards references for all project types</h4>{referenceAddButton('common', 'research_standards_references', [...(commonReferences?.research_standards_references ?? []), ...commonCustomReferences.research_standards_references], false, commonReferences?.research_standards_references.length ?? 0)}</div>
        {listEditor('common', 'research_standards_references', [
          ...(commonReferences?.research_standards_references ?? []),
          ...commonCustomReferences.research_standards_references,
        ], false, commonReferences?.research_standards_references.length ?? 0)}
        <div className="pt-reference-heading"><h4>Publication standards references for all project types</h4>{referenceAddButton('common', 'publication_standards_references', [...(commonReferences?.publication_standards_references ?? []), ...commonCustomReferences.publication_standards_references], false, commonReferences?.publication_standards_references.length ?? 0)}</div>
        {listEditor('common', 'publication_standards_references', [
          ...(commonReferences?.publication_standards_references ?? []),
          ...commonCustomReferences.publication_standards_references,
        ], false, commonReferences?.publication_standards_references.length ?? 0)}
      </section>
    </div>
  </>;
  if (embedded) return <div ref={embeddedRoot} className="project-types-dialog project-types-embedded" aria-label="Project Types settings">{content}</div>;
  return <dialog ref={dialog} className="project-types-dialog" aria-labelledby="project-types-title"
    onCancel={event => { event.preventDefault(); if (!busy) close(); }}
    onClose={() => {
      // Some browsers can still dispatch a native close despite a cancelled
      // Escape. Only Close/Save may dismiss this dialog. Restore modal status
      // rather than leaving its content laid out inside Home.
      if (!explicitlyClosing.current && dialog.current?.isConnected && !dialog.current.open) {
        dialog.current.showModal();
      }
    }}
    onKeyDown={event => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); if (!busy) close(); }
    }}
    onKeyDownCapture={event => {
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
    {content}
  </dialog>;
}
