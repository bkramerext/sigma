import { lazy, Suspense, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import './lean-explorer.css';

const RenderedMarkdown = lazy(() => import('./RenderedMarkdown'));
const DEFAULT_PATH = 'src/Statements.lean';
const DEFAULT_LOCAL_DIRECTORY = '~/lean_alpoge';
const THINKING_STEPS = [
  {name: 'Load sources', question: 'Which formal and supplementary sources can be inspected directly?'},
  {name: 'Choose a section', question: 'What is a coherent mathematical part of the argument?'},
  {name: 'Select Lean evidence', question: 'Which exact declarations belong in this investigation, across files?'},
  {name: 'Investigate', question: 'What do these declarations establish, and what connections remain unverified?'},
  {name: 'Shape the exposition', question: 'How should we explain the ideas and prerequisites to a human reader?'},
  {name: 'Prepare paper', question: 'Is the selected evidence sufficient to hand to SIGMA’s full paper generator?'},
] as const;
type ProofSection = {
  id: string; title: string; question: string; purpose: string;
  guide_section: number; guide_url: string; status: string; declaration_hints: string[];
};
type ProofMap = {
  title: string; status: string; warning: string;
  derived_from: {url: string; revision: string; title: string};
  sections: ProofSection[];
  connections: {from: string; to: string; why: string; status: string}[];
};
type SourceMode = 'mirror' | 'local';
type LocalSource = {mode: 'local'; directory: string; root_id: string; file_count: number; default_module?: string};
type LocalStatus = {configured: boolean; source: LocalSource | null};
type LocalFiles = {
  root_id: string; directory: string; total_files: number; total_matches: number;
  offset: number; limit: number; files: string[];
};
type LocalEvent = {
  type: string; stage?: string; label?: string; error?: string;
  scanned_directories?: number; found_files?: number; current_directory?: string;
  source?: LocalSource & {sample: string[]};
};

type LeanDecl = { kind: string; name: string; line: number };
type FileIndex = {
  path: string; commit: string; sha256: string; url: string;
  declarations: LeanDecl[]; total: number; truncated: boolean;
  imports: {line: number; text: string}[]; index_type: string;
};
type Declaration = {
  path: string; name: string; kind: string; commit: string; url: string; sha256: string;
  start_line: number; end_line: number; complete: boolean; excerpt: string;
};
type ScopedDeclaration = Declaration & {
  selection_origin?: string; relevance_score?: number; selection_reasons?: string[];
};
type Citation = {kind: string; path: string; commit: string; url: string; sha256: string; complete: boolean};
type Entry = {id: string; mode: string; text: string; created_at: string; source: Declaration; supplementary_sources?: Citation[]; interpretation_status: string};
type DiscoveryInfo = {
  index_type: string; scanned_files: number; total_files: number; complete: boolean;
  unreadable_files: number; matching_declarations: number; selected: number;
  warning: string;
};
type Dossier = {
  id: string; title: string; updated_at: string; entries: Entry[];
  scope?: ScopedDeclaration[]; discovery?: DiscoveryInfo;
  paper_project?: {path: string; project_id: string} | null;
  source_mode: SourceMode; section_id?: string; section_title?: string; section_focus?: string;
};
type DossierItem = {
  id: string; title: string; entry_count: number; updated_at: string;
  source_mode: SourceMode; section_id?: string; section_title?: string; section_focus?: string;
  formal_commit?: string; scope_count?: number;
  paper_project?: {path: string; project_id: string} | null;
};
type AIConfig = {available: boolean; message: string; model: string; reasoning_effort: string; models: {id: string; label: string; efforts: string[]}[]};
type Activity = {id: number; time: string; label: string; state: 'ok'|'working'|'error'|'note'};
type Stage = {
  type: string; stage?: string; label?: string; error?: string; text?: string;
  saved?: boolean; save_error?: string; sources?: Citation[];
  scanned?: number; total?: number; matches?: number; path?: string;
  dossier?: Dossier;
  discovery?: {scanned_files: number; total_files: number; matching_declarations: number; complete: boolean; candidates: unknown[]};
};

function explainError(err: unknown): string {return err instanceof Error ? err.message : String(err);}
async function requestJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {cache: 'no-store', ...init, headers: {'X-Sigma-Error-Handled': 'true', ...(init?.headers || {})}});
  const data = await response.json().catch(() => null) as (T & {detail?: unknown; error?: string}) | null;
  if (!response.ok) {
    const reason = data?.error || (typeof data?.detail === 'string' ? data.detail : '') || `Request failed (${response.status})`;
    throw new Error(reason);
  }
  if (!data) throw new Error('The server returned no result.');
  return data;
}
const postJSON = <T,>(url: string, body?: unknown) => requestJSON<T>(url, {method: 'POST', ...(body !== undefined ? {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {})});

function SourceLink({href, children}: {href: string; children: ReactNode}) {
  return href.startsWith('https://')
    ? <a href={href} target="_blank" rel="noreferrer">{children}<span aria-hidden="true"> ↗</span></a>
    : <span>{children}</span>;
}
function Timestamp({value}: {value: string}) {
  const date = new Date(value);
  return <time dateTime={value}>{Number.isNaN(date.getTime()) ? value : date.toLocaleString()}</time>;
}

export default function LeanExplorerPage() {
  const [path, setPath] = useState(DEFAULT_PATH);
  const [formalInput, setFormalInput] = useState(DEFAULT_PATH);
  const [sourceMode, setSourceMode] = useState<SourceMode>('local');
  const [activeFileMode, setActiveFileMode] = useState<SourceMode>('mirror');
  const [localDirectory, setLocalDirectory] = useState(DEFAULT_LOCAL_DIRECTORY);
  const [localSource, setLocalSource] = useState<LocalSource | null>(null);
  const [localFiles, setLocalFiles] = useState<LocalFiles | null>(null);
  const [moduleFilter, setModuleFilter] = useState('');
  const [proofMap, setProofMap] = useState<ProofMap | null>(null);
  const [sectionId, setSectionId] = useState('');
  const currentSection = proofMap?.sections.find(item => item.id === sectionId);
  const sectionName = currentSection?.title ?? 'Choose a mathematical section';
  const [sectionPrompt, setSectionPrompt] = useState('');
  const [moduleLoading, setModuleLoading] = useState(false);
  const [localIndexing, setLocalIndexing] = useState(false);
  const [scanCount, setScanCount] = useState({dirs: 0, files: 0, path: ''});
  const indexAbortRef = useRef<AbortController | null>(null);
  const [includeGuide, setIncludeGuide] = useState(true);
  const [includeAnnouncement, setIncludeAnnouncement] = useState(true);
  const [file, setFile] = useState<FileIndex | null>(null);
  const [selectedName, setSelectedName] = useState('');
  const [selected, setSelected] = useState<Declaration | null>(null);
  const [filter, setFilter] = useState('');
  const [loadingFile, setLoadingFile] = useState(false);
  const [loadingDeclaration, setLoadingDeclaration] = useState(false);
  const [config, setConfig] = useState<AIConfig | null>(null);
  const [model, setModel] = useState('');
  const [effort, setEffort] = useState('medium');
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState('Idle');
  const [elapsed, setElapsed] = useState(0);
  const [, setAnalysis] = useState('');
  const [markdownDraft, setMarkdownDraft] = useState('');
  const [savedMarkdown, setSavedMarkdown] = useState('');
  const [savingMarkdown, setSavingMarkdown] = useState(false);
  const [analysisSources, setAnalysisSources] = useState<Citation[]>([]);
  const [error, setError] = useState('');
  const [activity, setActivity] = useState<Activity[]>([]);
  const [dossierList, setDossierList] = useState<DossierItem[]>([]);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [note, setNote] = useState('');
  const [savingNote, setSavingNote] = useState(false);
  const [scopeBusy, setScopeBusy] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const discoveryAbortRef = useRef<AbortController | null>(null);
  const [handoffBusy, setHandoffBusy] = useState(false);
  const [showInputs, setShowInputs] = useState(false);
  const [showBrowser, setShowBrowser] = useState(false);
  const [showDossier, setShowDossier] = useState(false);
  const [showActivity, setShowActivity] = useState(false);
  const [objective, setObjective] = useState('Explain the selected Lean declarations, their mathematical meaning, and unresolved connections in a rigorous human-readable exposition.');
  const abortRef = useRef<AbortController | null>(null);
  const busyRef = useRef(false);
  const activitySeq = useRef(0);

  const log = useCallback((label: string, state: Activity['state']='note') => {
    setActivity(existing => [
      {id: ++activitySeq.current, time: new Date().toISOString(), label, state},
      ...existing,
    ].slice(0, 100));
  }, []);
  const refreshDossiers = useCallback(async () => {
    const all = await requestJSON<DossierItem[]>('/api/explorelean/dossiers');
    setDossierList(all);
  }, []);
  const loadDossier = useCallback(async (id: string) => {
    const data = await requestJSON<Dossier>('/api/explorelean/dossiers/' + encodeURIComponent(id));
    setDossier(data); setNote('');
  }, []);
  const loadFile = useCallback(async (filename: string, mode: SourceMode) => {
    setLoadingFile(true); setError(''); setStage('Reading formal source');
    log('Retrieving and scanning ' + filename, 'working');
    try {
      const data = await requestJSON<FileIndex>('/api/explorelean/declarations?' + new URLSearchParams({path: filename, source_mode: mode}));
      setFile(data); setPath(filename); setFormalInput(filename); setActiveFileMode(mode);
      setSelectedName(current => data.declarations.some(d => d.name === current) ? current : (data.declarations[0]?.name ?? ''));
      setStage('Formal source loaded');
      log(`Scanned ${data.total} candidate declarations in ${data.path}; source ${data.commit.slice(0, 22)}`, 'ok');
    } catch (cause) {
      setError(explainError(cause)); setStage('Source unavailable');
      log('Source load failed: ' + explainError(cause), 'error');
    } finally {setLoadingFile(false);}
  }, [log]);

  const loadModules = useCallback(async (query = '', offset = 0): Promise<LocalFiles> => {
    setModuleLoading(true);
    try {
      const data = await requestJSON<LocalFiles>('/api/explorelean/local-files?' + new URLSearchParams({
        query, offset: String(offset), limit: '100',
      }));
      setLocalFiles(data);
      return data;
    } finally {setModuleLoading(false);}
  }, []);

  function chooseSection(id: string) {
    const section = proofMap?.sections.find(item => item.id === id);
    if (!section || running) return;
    setSectionId(id); setSectionPrompt(section.question);
    setDossier(null); setNote('');
    setMarkdownDraft(''); setSavedMarkdown(''); setAnalysis(''); setAnalysisSources([]);
    log('Selected mathematical proof section: ' + section.title, 'ok');
  }

  function updateSourceMode(mode: SourceMode) {
    if (mode === sourceMode || running || localIndexing) return;
    setSourceMode(mode); setFile(null); setSelected(null); setSelectedName('');
    setAnalysis(''); setAnalysisSources([]); setDossier(null);
    if (mode === 'mirror') void loadFile(DEFAULT_PATH, 'mirror');
    else if (localSource) {
      void loadModules().then(result => {
        if (result.files.length) void loadFile(localSource.default_module || result.files[0], 'local');
      }).catch(cause => setError(explainError(cause)));
    }
  }

  async function indexLocalDirectory(): Promise<LocalSource | null> {
    if (localIndexing || running || !localDirectory.trim()) return null;
    setLocalIndexing(true); setScanCount({dirs: 0, files: 0, path: ''});
    setStage('Scanning local directory'); setError('');
    const controller = new AbortController(); indexAbortRef.current = controller;
    log('Scanning local Lean directory: ' + localDirectory.trim(), 'working');
    try {
      const response = await fetch('/api/explorelean/local-index', {
        method: 'POST', cache: 'no-store', signal: controller.signal,
        headers: {'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true'},
        body: JSON.stringify({directory: localDirectory.trim()}),
      });
      if (!response.ok) {
        const failure = await response.json().catch(() => null) as {detail?: string} | null;
        throw new Error(failure?.detail || `Directory indexing failed (${response.status})`);
      }
      if (!response.body) throw new Error('No directory scan events were received.');
      const reader = response.body.getReader(); const decoder = new TextDecoder();
      let buffer = ''; let complete: LocalSource | null = null;
      while (true) {
        const {done, value} = await reader.read();
        buffer += decoder.decode(value ?? new Uint8Array(), {stream: !done});
        const frames = buffer.split('\n\n'); buffer = frames.pop() ?? '';
        for (const frame of frames) {
          const line = frame.split('\n').find(row => row.startsWith('data: '));
          if (!line) continue;
          const event = JSON.parse(line.slice(6)) as LocalEvent;
          if (event.type === 'progress') {
            setScanCount({
              dirs: event.scanned_directories ?? 0,
              files: event.found_files ?? 0,
              path: event.current_directory ?? '',
            });
          } else if (event.type === 'error') {
            throw new Error(event.error || 'The local directory could not be indexed.');
          } else if (event.type === 'complete' && event.source) {
            complete = event.source;
          }
        }
        if (done) break;
      }
      if (!complete) throw new Error('The directory scan ended without a completed index.');
      setLocalSource(complete); setLocalDirectory(complete.directory);
      setSourceMode('local'); setFile(null); setDossier(null);
      const listed = await loadModules();
      if (listed.files.length) await loadFile(complete.default_module || listed.files[0], 'local');
      setShowInputs(false);
      setStage('Local Lean tree indexed');
      log(`Indexed ${complete.file_count.toLocaleString()} Lean files from local directory`, 'ok');
      return complete;
    } catch (cause) {
      if (controller.signal.aborted) {setStage('Directory scan stopped'); log('Directory scan stopped', 'note');}
      else {setError(explainError(cause)); setStage('Directory scan failed'); log(explainError(cause), 'error');}
      return null;
    } finally {setLocalIndexing(false); indexAbortRef.current = null;}
  }

  useEffect(() => {
    const oldTitle = document.title;
    document.title = 'Lean Explorer · SIGMA';
    void (async () => {
      try {
        const status = await requestJSON<LocalStatus>('/api/explorelean/local-status');
        if (status.configured && status.source) {
          setLocalSource(status.source);
          setLocalDirectory(status.source.directory);
          setSourceMode('local');
          const listed = await loadModules();
          if (listed.files.length) await loadFile(status.source.default_module || listed.files[0], 'local');
        } else {
          setShowInputs(true);
          setStage('Local directory ready to index');
          log('Select Index directory for ~/lean_alpoge to read the formalization', 'note');
        }
      } catch {
        setSourceMode('mirror');
        await loadFile(DEFAULT_PATH, 'mirror');
      }
    })();
    void refreshDossiers().catch(cause => setError(explainError(cause)));
    void requestJSON<ProofMap>('/api/explorelean/proof-map')
      .then(result => setProofMap(result))
      .catch(cause => setError(explainError(cause)));
    let cancelled = false;
    async function readModel() {
      try {
        const [account, preference] = await Promise.all([
          requestJSON<AIConfig>('/api/chat/config'),
          requestJSON<{ai_model?: string; reasoning_effort?: string}>('/api/user-preferences/research-settings').catch(() => ({ai_model: undefined, reasoning_effort: undefined})),
        ]);
        if (cancelled) return;
        setConfig(account);
        const choice = account.models.find(item => item.id === preference.ai_model)
          ?? account.models.find(item => item.id === account.model)
          ?? account.models[0];
        if (choice) {
          setModel(choice.id);
          setEffort(choice.efforts.includes(preference.reasoning_effort ?? '') ? preference.reasoning_effort! : choice.efforts.includes('medium') ? 'medium' : choice.efforts[0]);
        }
      } catch (cause) {if (!cancelled) setError(explainError(cause));}
    }
    void readModel();
    return () => {
      cancelled = true; abortRef.current?.abort();
      indexAbortRef.current?.abort(); discoveryAbortRef.current?.abort();
      document.title = oldTitle;
    };
  }, [loadFile, loadModules, refreshDossiers]);

  useEffect(() => {
    if (proofMap?.sections.length && !proofMap.sections.some(item => item.id === sectionId)) {
      setSectionId(proofMap.sections[0].id);
      setSectionPrompt(proofMap.sections[0].question);
    }
  }, [proofMap, sectionId]);

  // Resume the existing dossier for a mathematical section, regardless of
  // which source file is currently open. Switching sections never mixes notes.
  useEffect(() => {
    const match = dossierList.find(item =>
      item.section_id === sectionId && item.source_mode === sourceMode
      && (sourceMode !== 'local' || item.formal_commit === 'local:' + localSource?.root_id)
    );
    if (!match) {
      setDossier(null);
      return;
    }
    let active = true;
    void requestJSON<Dossier>('/api/explorelean/dossiers/' + encodeURIComponent(match.id))
      .then(result => {if (active) setDossier(result);})
      .catch(cause => {if (active) setError(explainError(cause));});
    return () => {active = false;};
  }, [dossierList, sectionId, sourceMode, localSource?.root_id]);

  useEffect(() => {
    if (!file || !selectedName) {setSelected(null); return;}
    let cancelled = false;
    setLoadingDeclaration(true); setSelected(null);
    void requestJSON<Declaration>('/api/explorelean/declaration?' + new URLSearchParams({path: file.path, name: selectedName, source_mode: activeFileMode}))
      .then(result => {if (!cancelled) setSelected(result);})
      .catch(cause => {if (!cancelled) setError(explainError(cause));})
      .finally(() => {if (!cancelled) setLoadingDeclaration(false);});
    return () => {cancelled = true;};
  }, [file, selectedName, activeFileMode]);

  useEffect(() => {
    if (!running) return;
    const started = Date.now(); setElapsed(0);
    const interval = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(interval);
  }, [running]);

  async function selectDossier(value: string) {
    if (!value) {setDossier(null); return;}
    setError('');
    try {
      const record = await requestJSON<Dossier>('/api/explorelean/dossiers/' + encodeURIComponent(value));
      if ((record.source_mode || 'mirror') !== sourceMode || record.section_id !== sectionId)
        throw new Error('This dossier belongs to a different mathematical proof section.');
      setDossier(record); setNote('');
    } catch (cause) {setError(explainError(cause));}
  }
  async function ensureDossier(): Promise<string> {
    if (dossier && dossier.source_mode === sourceMode && dossier.section_id === sectionId)
      return dossier.id;
    const existing = dossierList.find(item =>
      item.section_id === sectionId && item.source_mode === sourceMode
      && (sourceMode !== 'local' || item.formal_commit === 'local:' + localSource?.root_id)
    );
    if (existing) {
      await loadDossier(existing.id);
      return existing.id;
    }
    const created = await postJSON<Dossier>('/api/explorelean/dossiers', {
      source_mode: sourceMode, section_id: sectionId,
      section_title: sectionName, section_focus: sectionPrompt,
    });
    setDossier(created); await refreshDossiers(); log('Created new expository dossier', 'ok');
    return created.id;
  }
  async function createDossier() {
    try {
      setError('');
      const created = await postJSON<Dossier>('/api/explorelean/dossiers', {
        source_mode: sourceMode, section_id: sectionId,
        section_title: sectionName, section_focus: sectionPrompt,
      });
      setDossier(created); await refreshDossiers();
      log('Created new expository dossier', 'ok');
    } catch (cause) {setError(explainError(cause));}
  }
  async function updateScope(add: boolean, item: {path: string; name: string}) {
    if (scopeBusy || running) return;
    setScopeBusy(true); setError('');
    try {
      const id = await ensureDossier();
      const result = await requestJSON<Dossier>(
        '/api/explorelean/dossiers/' + encodeURIComponent(id) + '/scope',
        {
          method: add ? 'POST' : 'DELETE',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            formal_path: item.path, declaration: item.name, source_mode: sourceMode,
          }),
        },
      );
      setDossier(result);
      await refreshDossiers();
      log((add ? 'Added ' : 'Removed ') + item.name + (add ? ' to ' : ' from ') + sectionName, 'ok');
    } catch (cause) {setError(explainError(cause));}
    finally {setScopeBusy(false);}
  }

  async function preparePaperProject() {
    if (!dossier || !(dossier.scope?.length) || handoffBusy || running) return;
    if (markdownDraft.trim() !== savedMarkdown && markdownDraft.trim()) {
      setError('Save the revised expository Markdown before preparing the paper.');
      return;
    }
    setHandoffBusy(true); setError('');
    try {
      const project = await postJSON<{path: string; project_id: string}>(
        '/api/explorelean/dossiers/' + encodeURIComponent(dossier.id) + '/paper-project',
        {source_mode: sourceMode},
      );
      setDossier(current => current ? {...current, paper_project: project} : current);
      await refreshDossiers();
      log('Prepared SIGMA project and preserved selected Lean evidence for paper generation', 'ok');
      window.location.assign('/project?' + new URLSearchParams({path: project.path}));
    } catch (cause) {
      setError(explainError(cause));
    } finally {setHandoffBusy(false);}
  }

  async function exploreSection() {
    if (!localDirectory.trim() || !sectionId || sourceMode !== 'local' || discovering
      || running || localIndexing || scopeBusy || !!dossier?.paper_project) return;
    if (markdownDraft.trim() && markdownDraft.trim() !== savedMarkdown) {
      setError('Save or discard your current Markdown edits before a new exploration.');
      return;
    }
    setDiscovering(true); setError(''); setStage('Discovering Lean evidence');
    const controller = new AbortController(); discoveryAbortRef.current = controller;
    try {
      if (!localSource) {
        const indexed = await indexLocalDirectory();
        if (!indexed) return;
      }
      const dossierId = await ensureDossier();
      const response = await fetch('/api/explorelean/discover', {
        method: 'POST', signal: controller.signal, cache: 'no-store',
        headers: {'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true'},
        body: JSON.stringify({source_mode: 'local', section_id: sectionId, dossier_id: dossierId}),
      });
      if (!response.ok) {
        const failure = await response.json().catch(() => null) as {detail?: string} | null;
        throw new Error(failure?.detail || 'Lean discovery failed (' + response.status + ')');
      }
      if (!response.body) throw new Error('The discovery stream is missing.');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = ''; let completed = false;
      while (true) {
        const {done, value} = await reader.read();
        buffer += decoder.decode(value ?? new Uint8Array(), {stream: !done});
        const frames = buffer.split('\n\n'); buffer = frames.pop() ?? '';
        for (const frame of frames) {
          const line = frame.split('\n').find(row => row.startsWith('data: '));
          if (!line) continue;
          const event = JSON.parse(line.slice(6)) as Stage;
          if (event.type === 'stage') {
            setStage(event.label || 'Working');
          } else if (event.type === 'progress') {
            setStage('Scanned ' + (event.scanned ?? 0).toLocaleString() + ' / '
              + (event.total ?? 0).toLocaleString() + ' Lean files; '
              + (event.matches ?? 0).toLocaleString() + ' candidate matches');
          } else if (event.type === 'error') {
            throw new Error(event.error || 'Lean evidence discovery failed.');
          } else if (event.type === 'complete' && event.dossier && event.discovery) {
            completed = true;
            setDossier(event.dossier);
            await refreshDossiers();
            const info = event.discovery;
            log('Scanned ' + info.scanned_files.toLocaleString() + ' Lean files; '
              + info.matching_declarations.toLocaleString() + ' lexical matches; '
              + (event.dossier.scope?.length ?? 0) + ' selected evidence declarations', 'ok');
            if (!info.complete)
              log('Discovery is partial: the repository exceeds this pass limit.', 'note');
            if (event.dossier.scope?.length) {
              const hasNewEvidence =
                (event.dossier.scope?.length ?? 0) > (dossier?.scope?.length ?? 0);
              if (config?.available && model &&
                  (hasNewEvidence || !event.dossier.entries.some(item => item.mode === 'explain'))) {
                setStage('Lean candidates selected; investigating');
                await analyzeSelected(event.dossier);
              } else {
                setStage('Evidence collected; section dossier ready for review');
              }
            } else {
              setStage('No matching declarations found; expand discovery criteria');
            }
          }
        }
        if (done) break;
      }
      if (!completed) throw new Error('Discovery ended without a completed result.');
    } catch (cause) {
      if (controller.signal.aborted) {
        setStage('Stopped'); log('Discovery stopped; prior evidence remains saved.', 'note');
      } else {
        setError(explainError(cause)); setStage('Discovery failed');
      }
    } finally {
      discoveryAbortRef.current = null; setDiscovering(false);
    }
  }

  async function analyzeSelected(override?: Dossier) {
    const analysisDossier = override ?? dossier;
    if (!analysisDossier?.scope?.length || !config?.available || !model || busyRef.current || !proofMap) return;
    busyRef.current = true; setError(''); setAnalysis(''); setAnalysisSources([]);
    setRunning(true); setStage('Preparing analysis');
    const controller = new AbortController(); abortRef.current = controller;
    try {
      const dossierId = analysisDossier.id;
      log('Requested analysis of ' + analysisDossier.scope.length + ' selected Lean declarations', 'working');
      const response = await fetch('/api/explorelean/analyze', {
        method: 'POST', cache: 'no-store', signal: controller.signal,
        headers: {'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true'},
        body: JSON.stringify({
          formal_path: analysisDossier.scope[0].path, declaration: analysisDossier.scope[0].name, source_mode: sourceMode,
          include_guide: includeGuide, include_announcement: includeAnnouncement,
          model, reasoning_effort: effort,
          objective: (objective + '\n\nProvisional mathematical proof section: ' + sectionName
            + '\nExpository question: ' + sectionPrompt
            + '\nFind evidence for the relevance of this declaration to the section; '
            + 'do not assume a dependency merely because it was selected.').slice(0, 6000),
          dossier_id: dossierId,
        }),
      });
      if (!response.ok) {
        const failure = await response.json().catch(() => null) as {detail?: string; error?: string} | null;
        throw new Error(failure?.detail || failure?.error || `Analysis failed (${response.status})`);
      }
      if (!response.body) throw new Error('No exploration progress stream was received.');
      const reader = response.body.getReader();
      const decoder = new TextDecoder(); let buffer = ''; let completed = false;
      while (true) {
        const {done, value} = await reader.read();
        buffer += decoder.decode(value ?? new Uint8Array(), {stream: !done});
        const frames = buffer.split('\n\n'); buffer = frames.pop() ?? '';
        for (const frame of frames) {
          const line = frame.split('\n').find(row => row.startsWith('data: '));
          if (!line) continue;
          const event = JSON.parse(line.slice(6)) as Stage;
          if (event.type === 'stage') {
            setStage(event.label || event.stage || 'Working');
            log(event.label || event.stage || 'Working', 'working');
          } else if (event.type === 'error') {
            throw new Error(event.error || 'Exploration failed.');
          } else if (event.type === 'complete') {
            completed = true;
            setAnalysis(event.text || '');
            setMarkdownDraft(event.text || '');
            setSavedMarkdown(event.saved ? (event.text || '') : '');
            setAnalysisSources(event.sources || []);
            setStage(event.saved ? 'Explanation saved' : 'Explanation ready · not saved');
            log(event.saved ? 'Explanation saved to dossier' : 'Explanation returned without durable save', event.saved ? 'ok' : 'error');
            if (event.save_error) setError(event.save_error);
            if (event.saved) {await loadDossier(dossierId); await refreshDossiers();}
          }
        }
        if (done) break;
      }
      if (!completed) throw new Error('The exploration ended without a completed explanation.');
    } catch (cause) {
      if (controller.signal.aborted) {
        setStage('Stopped'); log('Stopped by user. Earlier dossier entries remain saved.', 'note');
      } else {
        const message = explainError(cause);
        setError(message);
        setStage('Investigation failed — discovered evidence is saved');
        log('Investigation failed: ' + message, 'error');
      }
    } finally {setRunning(false); abortRef.current = null; busyRef.current = false;}
  }
  function stopAnalysis() {
    abortRef.current?.abort();
    discoveryAbortRef.current?.abort();
    indexAbortRef.current?.abort();
  }
  async function saveMarkdown() {
    // The Markdown belongs to the selected *section*, not necessarily the
    // declaration currently visible in the source editor.
    const anchor = dossier?.scope?.[0];
    if (!anchor || !markdownDraft.trim() || savingMarkdown || running
      || markdownDraft.trim() === savedMarkdown) return;
    setSavingMarkdown(true); setError('');
    try {
      const id = await ensureDossier();
      await postJSON('/api/explorelean/dossiers/' + encodeURIComponent(id) + '/notes', {
        formal_path: anchor.path,
        declaration: anchor.name,
        source_mode: sourceMode,
        text: markdownDraft.trim(),
      });
      setSavedMarkdown(markdownDraft.trim());
      await loadDossier(id); await refreshDossiers();
      log('Saved revised expository Markdown', 'ok');
    } catch (cause) {
      setError(explainError(cause));
    } finally {setSavingMarkdown(false);}
  }
  async function saveNote() {
    if (!selected || !dossier?.scope?.some(item =>
      item.path === selected.path && item.name === selected.name)
      || !note.trim() || savingNote) return;
    setSavingNote(true); setError('');
    try {
      const id = await ensureDossier();
      await postJSON('/api/explorelean/dossiers/' + encodeURIComponent(id) + '/notes', {
        formal_path: selected.path, declaration: selected.name, source_mode: sourceMode, text: note.trim(),
      });
      await loadDossier(id); await refreshDossiers();
      log('Saved note for ' + selected.name, 'ok');
    } catch (cause) {setError(explainError(cause));}
    finally {setSavingNote(false);}
  }

  const filtered = file?.declarations.filter(item =>
    item.name.toLowerCase().includes(filter.trim().toLowerCase())) ?? [];
  const scope = dossier?.scope ?? [];
  const selectedInScope = !!selected && scope.some(item =>
    item.path === selected.path && item.name === selected.name);
  const hasExplanation = !!dossier?.entries.some(item => item.mode === 'explain');
  const ready = scope.length > 0 && !loadingFile && !loadingDeclaration && !running
    && !discovering && !localIndexing && !scopeBusy
    && !!config?.available && !!model && !!proofMap;
  const selectedEntries = dossier?.entries.filter(item =>
    item.source.name === selectedName && item.source.path === file?.path) ?? [];
  const matchedDossiers = dossierList.filter(item =>
    (item.source_mode || 'mirror') === sourceMode && item.section_id === sectionId
    && (sourceMode !== 'local' || (item.formal_commit || '') === 'local:' + localSource?.root_id)
  );
  const stageCompletion = [
    sourceMode === 'local' ? !!localSource : !!file,
    !!proofMap && !!currentSection,
    scope.length > 0,
    hasExplanation,
    !!dossier?.entries.length,
    !!dossier?.paper_project,
  ];
  const activeStep = stageCompletion.findIndex(complete => !complete);
  const currentThought = THINKING_STEPS[activeStep >= 0 ? activeStep : THINKING_STEPS.length - 1];

  return <main className="chat-page leanx-ui">
    <section className="leanx-workflow" aria-label="Lean Explorer workflow">
      <div className="leanx-workflow-title">
        <strong>Exploring {sectionName}</strong>
        {(running || discovering || localIndexing) &&
          <span className="research-running-indicator" aria-label="Lean exploration in progress"/>}
      </div>
      <ol className="leanx-paper-steps">
        {THINKING_STEPS.map((item, index) =>
          <li key={item.name} className={stageCompletion[index] ? 'is-past' :
            index === activeStep ? (running || discovering || localIndexing ? 'is-active' : 'is-current') : 'is-upcoming'}>
            <span className="leanx-stage-marker" aria-hidden="true">{stageCompletion[index] ? '✓' : '○'}</span>
            <strong>{item.name}</strong>
          </li>
        )}
      </ol>
      <p className="leanx-thinking-prompt"><strong>Consider:</strong> {currentThought.question}</p>
      <div className="leanx-workflow-status" role="status">
        {localIndexing
          ? `Indexing: ${scanCount.files.toLocaleString()} Lean files in ${scanCount.dirs.toLocaleString()} directories`
          : running ? `${stage} · ${Math.floor(elapsed / 60)}m ${String(elapsed % 60).padStart(2, '0')}s` : stage}
      </div>
      {error && <div className="leanx-workflow-error" role="alert">
        <span>{error}</span>
        {!!dossier?.scope?.length && !running && !discovering && !!config?.available && !!model &&
          <button type="button" onClick={() => void analyzeSelected()}>Retry investigation</button>}
      </div>}
    </section>



    <section className="leanx-section-selection" aria-label="Select a mathematical proof section">
      <div className="leanx-section-selection-line">
        <label htmlFor="leanx-selected-section">Research section</label>
        <select id="leanx-selected-section" value={sectionId} disabled={running || scopeBusy || handoffBusy}
          onChange={event => chooseSection(event.target.value)}>
          {proofMap?.sections.map((item, index) =>
            <option key={item.id} value={item.id}>
              {index + 1}. {item.title}
            </option>
          )}
        </select>
        <span className="leanx-section-provenance">
          {proofMap?.status === 'interpretive_not_lean_verified'
            ? 'Provisional source-informed sections · formal dependencies not established'
            : 'Section classification derived from supplied sources'}
        </span>
        {proofMap && <SourceLink href={proofMap.derived_from.url}>Source guide</SourceLink>}
      </div>
      <p><strong>Question:</strong> {sectionPrompt}</p>
      {currentSection && <p className="leanx-section-purpose">{currentSection.purpose}</p>}
    </section>

    <section className="leanx-evidence-scope" aria-label="Selected Lean evidence for this section">
      <div className="leanx-scope-heading">
        <strong>Lean evidence scope · {scope.length} declaration{scope.length === 1 ? '' : 's'}</strong>
        <div className="leanx-scope-actions">
          <button type="button" className="leanx-primary-action"
            disabled={!localDirectory.trim() || sourceMode !== 'local' || !proofMap || !sectionId
              || discovering || running || localIndexing || scopeBusy || !!dossier?.paper_project}
            onClick={() => void exploreSection()}>
            {discovering ? 'Exploring…'
              : dossier?.discovery && !dossier.discovery.complete
                ? 'Continue scanning Lean files' : 'Explore section'}
          </button>
          {(discovering || running) && <button type="button" onClick={stopAnalysis}>Stop</button>}
          <button type="button" onClick={() => setShowBrowser(true)}>Find Lean evidence manually</button>
        </div>
      </div>
      {selected && <div className="leanx-scope-candidate">
        <span>Current declaration: <code>{selected.name}</code> · {selected.path}</span>
        {selectedInScope ? <span>Included in this section</span> :
          <button type="button" disabled={scopeBusy || running || !!dossier?.paper_project}
            onClick={() => void updateScope(true, {path: selected.path, name: selected.name})}>
            {scopeBusy ? 'Saving…' : 'Include in section'}
          </button>}
      </div>}
      {dossier?.discovery && <p className="leanx-discovery-summary">
        Automatic lexical discovery scanned {dossier.discovery.scanned_files.toLocaleString()} of
        {' '}{dossier.discovery.total_files.toLocaleString()} indexed Lean files, with
        {' '}{dossier.discovery.matching_declarations.toLocaleString()} possible matches.
        {dossier.discovery.unreadable_files > 0 &&
          ' Unreadable files: ' + dossier.discovery.unreadable_files.toLocaleString() + '.'}
        {!dossier.discovery.complete && ' Scan incomplete; Continue scanning Lean files resumes from the saved checkpoint.'}
        {' '}Matches are candidates, not verified mathematical dependencies.
      </p>}
      {scope.length > 0 ? <ul className="leanx-scope-list">
        {scope.map(item => <li key={item.path + ':' + item.name}>
          <span title={item.selection_reasons?.join(' · ')}>
            <strong>{item.name}</strong>
            <small>{item.path}</small>
            {item.selection_origin === 'automatic_lexical_candidate' &&
              <small> · Suggested (lexical score {item.relevance_score})</small>}
          </span>
          <button type="button" disabled={scopeBusy || running || !!dossier?.paper_project}
            aria-label={'Remove ' + item.name + ' from section'}
            onClick={() => void updateScope(false, item)}>Remove</button>
        </li>)}
      </ul> :
        <p className="leanx-scope-empty">
          Click Explore section to search the indexed Lean root and automatically collect
          candidate declarations. You can refine the selection afterward if needed.
        </p>}
    </section>

    <div className="leanx-compact-controls">
      <nav className="leanx-tool-tabs" aria-label="Explorer tools">
        <button type="button" aria-expanded={showInputs} onClick={() => setShowInputs(!showInputs)}>
          Source · {sourceMode === 'local' ? (localSource ? 'Local Lean tree' : '~/lean_alpoge') : 'GitHub mirror'}
        </button>
        <button type="button" aria-expanded={showBrowser} onClick={() => setShowBrowser(!showBrowser)}>
          Find Lean evidence
        </button>
        <button type="button" aria-expanded={showDossier} onClick={() => setShowDossier(!showDossier)}>
          Section dossier · {dossier?.entries.length ?? 0} entries
        </button>
      </nav>
      {showInputs && <div className="leanx-tool-body">
    <section className="leanx-section" aria-label="Proof and supplementary inputs">
      <div className="leanx-section-heading"><h2>Inputs</h2><span>Formal proof tree + supplementary literature</span></div>
      <div className="leanx-formal-input">
        <label htmlFor="leanx-source-mode">A. Official Lean proof · source location</label>
        <select id="leanx-source-mode" className="leanx-mode-select" value={sourceMode} disabled={running || localIndexing}
          onChange={event => updateSourceMode(event.target.value as SourceMode)}>
          <option value="local">Local directory</option>
          <option value="mirror">Pinned GitHub mirror</option>
        </select>
        {sourceMode === 'local' ? <>
          <p className="leanx-local-hint">Enter the absolute path of the extracted Lean folder on the same Mac running SIGMA. No browser upload is needed.</p>
          <div className="leanx-input-row">
            <input id="leanx-local-directory" spellCheck={false} aria-label="Local Lean directory" placeholder="~/rh-lean/lean"
              value={localDirectory} disabled={running || localIndexing} onChange={event => setLocalDirectory(event.target.value)}
              onKeyDown={event => {if (event.key === 'Enter') void indexLocalDirectory();}}/>
            <button type="button" disabled={running || localIndexing || !localDirectory.trim()} onClick={() => void indexLocalDirectory()}>
              {localIndexing ? 'Scanning…' : localSource ? 'Rescan directory' : 'Index directory'}
            </button>
            {localIndexing && <button type="button" onClick={() => indexAbortRef.current?.abort()}>Stop</button>}
          </div>
          {localIndexing && <div className="leanx-local-progress" role="status">
            {scanCount.dirs.toLocaleString()} directories scanned · {scanCount.files.toLocaleString()} Lean files found
            {scanCount.path && <span> · {scanCount.path}</span>}
          </div>}
          {localSource && <p className="leanx-local-hint">{localSource.file_count.toLocaleString()} Lean modules indexed from <code>{localSource.directory}</code>. Files are read lazily; local working copies are mutable.</p>}
        </> : <div className="leanx-mirror-controls">
          <p className="leanx-local-hint">Pinned mirror: <SourceLink href="https://github.com/CocoSgt/riemann-hypothesis-lean">CocoSgt/riemann-hypothesis-lean</SourceLink></p>
          <div className="leanx-input-row">
            <input id="leanx-input-path" spellCheck={false} aria-label="Lean module path on pinned GitHub mirror"
              value={formalInput} disabled={running || loadingFile} onChange={event => setFormalInput(event.target.value)}
              onKeyDown={event => {if (event.key === 'Enter') void loadFile(formalInput.trim(), 'mirror');}}/>
            <button type="button" disabled={running || loadingFile || !formalInput.trim()} onClick={() => void loadFile(formalInput.trim(), 'mirror')}>{loadingFile ? 'Reading…' : 'Open file'}</button>
          </div>
        </div>}
        {file && <div className="leanx-source-line">
          <span>Source <code>{file.commit.slice(0, 24)}</code></span>
          <span>File SHA256 <code>{file.sha256.slice(0, 12)}…</code></span>
          <span>{file.total} candidate declarations in current file</span>
          <span>Lexical scan · Not kernel checked</span>
          {file.url && <SourceLink href={file.url}>View source</SourceLink>}
        </div>}
      </div>
      <div className="leanx-supplement">
        <strong>B. Supplementary literature</strong>
        <label><input type="checkbox" checked={includeGuide} disabled={running} onChange={event => setIncludeGuide(event.target.checked)}/>
          <span><SourceLink href="https://github.com/nasqret/riemann-rev/blob/main/guide/proof-guide.pdf">riemann-rev proof guide</SourceLink> · pinned TeX excerpt used for analysis</span>
        </label>
        <label><input type="checkbox" checked={includeAnnouncement} disabled={running} onChange={event => setIncludeAnnouncement(event.target.checked)}/>
          <span><SourceLink href="https://alpo.ge/remark.pdf">Alpöge's announcement</SourceLink> · original PDF</span>
        </label>
      </div>
    </section>
      </div>}
      {showBrowser && <div className="leanx-tool-body leanx-browser-tool">
        <p className="leanx-tree-disclaimer">Search real Lean files and declarations across the source tree. Directory names are not mathematical proof sections.</p>
      <aside className="leanx-pane leanx-declarations" aria-label="Lean source evidence browser">
        {sourceMode === 'local' && <div className="leanx-module-navigator">
          <div className="leanx-pane-title"><h2>Lean files</h2><span>{localFiles?.total_matches.toLocaleString() ?? '—'} matches</span></div>
          <div className="leanx-module-search">
            <input type="search" placeholder="Find files across directory…" aria-label="Find Lean files"
              value={moduleFilter} disabled={!localSource || moduleLoading || localIndexing}
              onChange={event => setModuleFilter(event.target.value)}
              onKeyDown={event => {if (event.key === 'Enter') void loadModules(moduleFilter).catch(cause => setError(explainError(cause)));}}/>
            <button type="button" disabled={!localSource || moduleLoading || localIndexing}
              onClick={() => void loadModules(moduleFilter).catch(cause => setError(explainError(cause)))}>Find</button>
          </div>
          <div className="leanx-module-list">
            {localFiles?.files.map(filename => <button type="button" key={filename}
              className={filename === path && activeFileMode === 'local' ? 'is-selected' : ''}
              onClick={() => {void loadFile(filename, 'local'); setShowBrowser(false);}}>{filename}</button>)}
            {!localFiles?.files.length && <p className="leanx-empty">Index a directory to browse its Lean files.</p>}
          </div>
          {localFiles && <div className="leanx-module-pager">
            <button type="button" disabled={moduleLoading || localFiles.offset === 0}
              onClick={() => void loadModules(moduleFilter, Math.max(0, localFiles.offset - 100)).catch(cause => setError(explainError(cause)))}>Previous</button>
            <span>{localFiles.total_matches ? localFiles.offset + 1 : 0}–{Math.min(localFiles.offset + localFiles.files.length, localFiles.total_matches)} of {localFiles.total_matches.toLocaleString()}</span>
            <button type="button" disabled={moduleLoading || localFiles.offset + localFiles.files.length >= localFiles.total_matches}
              onClick={() => void loadModules(moduleFilter, localFiles.offset + 100).catch(cause => setError(explainError(cause)))}>Next</button>
          </div>}
        </div>}
        <div className="leanx-pane-title"><h2>Declarations</h2><span>{file?.total ?? '—'} in current file</span></div>
        <input type="search" placeholder="Filter declarations…" aria-label="Filter declarations" value={filter} onChange={event => setFilter(event.target.value)}/>
        <div className="leanx-declaration-list">
          {filtered.map(item => <button key={item.name + ':' + item.line} type="button"
            className={item.name === selectedName ? 'is-selected' : ''}
            onClick={() => {
              setSelectedName(item.name); setAnalysis(''); setAnalysisSources([]);
              setMarkdownDraft(''); setSavedMarkdown(''); setShowBrowser(false);
            }}>
            <span className="leanx-declaration-kind">{item.kind}</span>
            <span className="leanx-declaration-name">{item.name}</span>
            <span className="leanx-declaration-line">:{item.line}</span>
          </button>)}
          {!loadingFile && !filtered.length && <p className="leanx-empty">No matching declarations in this file.</p>}
        </div>
        {file && <div className="leanx-pane-footer">
          {file.truncated ? 'List truncated to first candidates. ' : ''}
          Imports and declaration names are scanned lexically. Formal dependencies are not indexed yet.
        </div>}
      </aside>
      </div>}
      {showDossier && <div className="leanx-tool-body leanx-dossier-tool">
        <section className="leanx-pane leanx-dossier-pane">
          <div className="leanx-pane-title"><h2>Expository dossier</h2><span>{dossier?.entries.length ?? 0} entries</span></div>
          <label htmlFor="leanx-dossier-select">Working dossier</label>
          <div className="leanx-dossier-select-row">
            <select id="leanx-dossier-select" value={dossier?.id ?? ''} disabled={running} onChange={event => void selectDossier(event.target.value)}>
              <option value="">Choose dossier…</option>
              {matchedDossiers.map(item => <option key={item.id} value={item.id}>{item.title} ({item.entry_count})</option>)}
            </select>
            <button type="button" disabled={running} onClick={() => void createDossier()}>New</button>
          </div>
          {dossier && <>
            <a className="leanx-download-link" href={'/api/explorelean/dossiers/' + encodeURIComponent(dossier.id) + '/markdown'}>Download dossier (Markdown)</a>
            <div className="leanx-dossier-entries">
              {dossier.entries.slice().reverse().slice(0, 12).map(item => <button key={item.id} type="button"
                onClick={() => {
                  if (item.source.path !== path) {
                    setFormalInput(item.source.path); void loadFile(item.source.path, sourceMode);
                  }
                  setSelectedName(item.source.name); setAnalysis(item.text);
                  setMarkdownDraft(item.text); setSavedMarkdown(item.text);
                  setAnalysisSources(item.supplementary_sources || []);
                }}>
                <span>{item.source.name}</span><small>{item.mode} · <Timestamp value={item.created_at}/></small>
              </button>)}
              {!dossier.entries.length && <p className="leanx-empty">Explanations are saved here automatically after completion.</p>}
            </div>
          </>}

        </section>
      </div>}
    </div>

    <div className="leanx-activity-toggle">
      <button type="button" aria-expanded={showActivity} onClick={() => setShowActivity(!showActivity)}>Activity history</button>
    </div>
    {showActivity && <div className="leanx-activity-expanded">
        <section className="leanx-pane leanx-progress-pane" aria-live="polite">
          <div className="leanx-pane-title">
            <h2>Live activity</h2>
            {(running || discovering || localIndexing) &&
              <span className="research-running-indicator" aria-label="Lean exploration in progress"/>}
          </div>
          <div className="leanx-stage">{stage}</div>
          {localIndexing && <p className="leanx-running-time">{scanCount.dirs.toLocaleString()} directories · {scanCount.files.toLocaleString()} Lean files discovered</p>}
          {running && <p className="leanx-running-time">Elapsed: {Math.floor(elapsed / 60)}m {String(elapsed % 60).padStart(2, '0')}s</p>}
          <ol className="leanx-activity-log">
            {activity.map(item => <li key={item.id} className={'leanx-state-' + item.state}>
              <span className="leanx-activity-icon" aria-hidden="true">{item.state === 'ok' ? '✓' : item.state === 'error' ? '!' : '•'}</span>
              <div><span>{item.label}</span><small><Timestamp value={item.time}/></small></div>
            </li>)}
            {!activity.length && <li className="leanx-muted-activity">No operations yet.</li>}
          </ol>
        </section>
    </div>}

    <div className="leanx-primary-reading">
      <div className="leanx-reading-column">
        <section className="leanx-pane leanx-source-code">
          <div className="leanx-pane-title">
            <h2>{selected?.name ?? (loadingDeclaration ? 'Reading declaration…' : 'Lean source')}</h2>
            {selected && (selected.url ? <SourceLink href={selected.url + '#L' + selected.start_line}>Lines {selected.start_line}–{selected.end_line}</SourceLink> : <span>Lines {selected.start_line}–{selected.end_line}</span>)}
          </div>
          {selected ? <>
            <textarea className="leanx-lean-source-editor" aria-label="Lean source text" readOnly spellCheck={false}
              value={selected.excerpt}/>
            <div className="leanx-pane-footer">Actual Lean source · {selected.complete ? 'To next declaration boundary' : 'Partial excerpt'} · Not a Lean kernel check</div>
          </> : <p className="leanx-empty">Select a declaration using Find Lean evidence to inspect its source.</p>}
        </section>

        <section className="leanx-pane leanx-analysis-pane">
          <div className="leanx-pane-title"><h2>Mathematical interpretation</h2><span>AI commentary · Not formally verified</span></div>
          <details className="leanx-objective-details">
            <summary>Expository objective</summary>
            <textarea id="leanx-objective" aria-label="Expository objective" rows={3} value={objective} disabled={running} onChange={event => setObjective(event.target.value)}/>
          </details>
          <div className="leanx-operation-controls">
            <button type="button" className="leanx-primary-action" disabled={!ready || !objective.trim()} onClick={() => void analyzeSelected()}>
              {running ? 'Investigating…' : 'Investigate selected Lean evidence (' + scope.length + ')'}
            </button>
            <button type="button" disabled={!running} onClick={stopAnalysis}>Stop</button>
            <span>{config ? (config.available ? `${config.models.find(item => item.id === model)?.label ?? model} · ${effort}` : config.message) : 'Reading selected AI connection…'}</span>
          </div>
          <p className="leanx-map-provenance">
            Investigation uses the selected {scope.length} Lean declarations.
            Automatically discovered candidates and mathematical connections are hypotheses, not verified Lean dependencies.
          </p>
          <div className="leanx-markdown-editor">
            <div className="leanx-markdown-toolbar">
              <label htmlFor="leanx-markdown">Expository Markdown</label>
              <button type="button" disabled={!scope.length || !markdownDraft.trim() ||
                markdownDraft.trim() === savedMarkdown || savingMarkdown || running}
                onClick={() => void saveMarkdown()}>
                {savingMarkdown ? 'Saving…' : 'Save Markdown'}
              </button>
            </div>
            <textarea id="leanx-markdown" value={markdownDraft} disabled={!scope.length || running || savingMarkdown}
              onChange={event => setMarkdownDraft(event.target.value)}
              placeholder="The mathematical explanation goes here. Edit its Markdown, refine the ideas, then save it to this section's dossier."/>
            {!!markdownDraft && markdownDraft.trim() !== savedMarkdown && <small>Unsaved edits</small>}
            {!!markdownDraft && <details className="leanx-markdown-preview">
              <summary>Preview rendered Markdown</summary>
              <div className="leanx-explanation">
                <Suspense fallback={<p>Rendering Markdown…</p>}>
                  <RenderedMarkdown body={markdownDraft}/>
                </Suspense>
              </div>
            </details>}
          </div>
          {!!analysisSources.length && <details className="leanx-evidence-detail">
            <summary>Evidence used in this explanation ({analysisSources.length})</summary>
            {analysisSources.map(item => <p key={item.kind + item.path}>
              {item.kind}: <SourceLink href={item.url}>{item.path}</SourceLink>
              <span> · {item.commit.slice(0, 12)} · SHA256 {item.sha256.slice(0, 12)}…</span>
            </p>)}
          </details>}
          {!!selectedEntries.length && <div className="leanx-existing">Saved entries for this declaration: {selectedEntries.length}</div>}
        </section>
        <section className="leanx-pane leanx-notes-pane">
          <div className="leanx-pane-title">
            <h2>Expository notes</h2><span>Editable Markdown · Current section</span>
          </div>
          <textarea aria-label="Expository notes" value={note} rows={7}
            disabled={!selectedInScope || savingNote || running}
            onChange={event => setNote(event.target.value)}
            placeholder="What is surprising here? Which assumptions need explanation? What questions should the next research session pursue?"/>
          <div className="leanx-notes-action">
            <button type="button" disabled={!selectedInScope || !note.trim() || savingNote || running}
              onClick={() => void saveNote()}>{savingNote ? 'Saving…' : 'Save note to section dossier'}</button>
          </div>
        </section>
      </div>
    </div>

    <section className="leanx-paper-stage" aria-label="Generate a section paper">
      <div className="leanx-pane-title">
        <h2>Generate expository paper</h2>
        <span>Using SIGMA's existing paper-generation pipeline</span>
      </div>
      <p>
        This section can become its own SIGMA project, carrying the selected Lean statements,
        source hashes, and saved explanatory notes. Review its publication settings there,
        then generate, validate, score, and download a PDF.
      </p>
      <div className="leanx-paper-actions">
        <button type="button" disabled={handoffBusy || running || scopeBusy || !dossier?.scope?.length}
          onClick={() => void preparePaperProject()}>
          {handoffBusy ? 'Preparing…' : dossier?.paper_project ? 'Open section paper project' : 'Prepare paper in SIGMA'}
        </button>
        {dossier?.paper_project && <span>Project prepared · scope frozen for this paper</span>}
      </div>
    </section>

    <p className="leanx-boundary">
      Current scope contains source-backed candidates; automatic mathematical section inference, elaborated theorem
      dependencies, and Lean kernel checking remain future capabilities. Paper generation uses SIGMA's
      project pipeline and retains these evidence limitations.
    </p>
  </main>;
}
