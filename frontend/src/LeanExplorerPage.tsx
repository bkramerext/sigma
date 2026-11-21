import { lazy, Suspense, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import './lean-explorer.css';

const RenderedMarkdown = lazy(() => import('./RenderedMarkdown'));
const DEFAULT_PATH = 'src/Statements.lean';

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
type Citation = {kind: string; path: string; commit: string; url: string; sha256: string; complete: boolean};
type Entry = {id: string; mode: string; text: string; created_at: string; source: Declaration; supplementary_sources?: Citation[]; interpretation_status: string};
type Dossier = {id: string; title: string; updated_at: string; entries: Entry[]};
type DossierItem = {id: string; title: string; entry_count: number; updated_at: string};
type AIConfig = {available: boolean; message: string; model: string; reasoning_effort: string; models: {id: string; label: string; efforts: string[]}[]};
type Activity = {id: number; time: string; label: string; state: 'ok'|'working'|'error'|'note'};
type Stage = {type: string; stage?: string; label?: string; error?: string; text?: string; saved?: boolean; save_error?: string; sources?: Citation[]};

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
  return <a href={href} target="_blank" rel="noreferrer">{children}<span aria-hidden="true"> ↗</span></a>;
}
function Timestamp({value}: {value: string}) {
  const date = new Date(value);
  return <time dateTime={value}>{Number.isNaN(date.getTime()) ? value : date.toLocaleString()}</time>;
}

export default function LeanExplorerPage({onClose}: {onClose: () => void}) {
  const [path, setPath] = useState(DEFAULT_PATH);
  const [formalInput, setFormalInput] = useState(DEFAULT_PATH);
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
  const [analysis, setAnalysis] = useState('');
  const [analysisSources, setAnalysisSources] = useState<Citation[]>([]);
  const [error, setError] = useState('');
  const [activity, setActivity] = useState<Activity[]>([]);
  const [dossierList, setDossierList] = useState<DossierItem[]>([]);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [note, setNote] = useState('');
  const [savingNote, setSavingNote] = useState(false);
  const [objective, setObjective] = useState('Explain this declaration precisely and identify its role in a rigorous human-readable reconstruction of Alpöge’s Riemann Hypothesis proof.');
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
  const loadFile = useCallback(async (filename: string) => {
    setLoadingFile(true); setError(''); setStage('Reading formal source');
    log('Retrieving and scanning ' + filename, 'working');
    try {
      const data = await requestJSON<FileIndex>('/api/explorelean/declarations?' + new URLSearchParams({path: filename}));
      setFile(data); setPath(filename); setFormalInput(filename);
      setSelectedName(current => data.declarations.some(d => d.name === current) ? current : (data.declarations[0]?.name ?? ''));
      setStage('Formal source loaded');
      log(`Scanned ${data.total} candidate declarations in ${data.path}; commit ${data.commit.slice(0, 10)}`, 'ok');
    } catch (cause) {
      setError(explainError(cause)); setStage('Source unavailable');
      log('Source load failed: ' + explainError(cause), 'error');
    } finally {setLoadingFile(false);}
  }, [log]);

  useEffect(() => {
    const oldTitle = document.title;
    document.title = 'Lean Explorer · SIGMA';
    void loadFile(DEFAULT_PATH);
    void refreshDossiers().catch(cause => setError(explainError(cause)));
    let cancelled = false;
    async function readModel() {
      try {
        const [account, preference] = await Promise.all([
          requestJSON<AIConfig>('/api/chat/config'),
          requestJSON<{ai_model?: string; reasoning_effort?: string}>('/api/user-preferences/research-settings').catch(() => ({})),
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
    return () => {cancelled = true; abortRef.current?.abort(); document.title = oldTitle;};
  }, [loadFile, refreshDossiers]);

  useEffect(() => {
    if (!file || !selectedName) {setSelected(null); return;}
    let cancelled = false;
    setLoadingDeclaration(true); setSelected(null);
    void requestJSON<Declaration>('/api/explorelean/declaration?' + new URLSearchParams({path: file.path, name: selectedName}))
      .then(result => {if (!cancelled) setSelected(result);})
      .catch(cause => {if (!cancelled) setError(explainError(cause));})
      .finally(() => {if (!cancelled) setLoadingDeclaration(false);});
    return () => {cancelled = true;};
  }, [file, selectedName]);

  useEffect(() => {
    if (!running) return;
    const started = Date.now(); setElapsed(0);
    const interval = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(interval);
  }, [running]);

  async function selectDossier(value: string) {
    if (!value) {setDossier(null); return;}
    setError('');
    try {await loadDossier(value);} catch (cause) {setError(explainError(cause));}
  }
  async function ensureDossier(): Promise<string> {
    if (dossier) return dossier.id;
    const created = await postJSON<Dossier>('/api/explorelean/dossiers');
    setDossier(created); await refreshDossiers(); log('Created new expository dossier', 'ok');
    return created.id;
  }
  async function createDossier() {
    try {
      setError('');
      const created = await postJSON<Dossier>('/api/explorelean/dossiers');
      setDossier(created); await refreshDossiers();
      log('Created new expository dossier', 'ok');
    } catch (cause) {setError(explainError(cause));}
  }
  async function analyzeSelected() {
    if (!selected || !config?.available || !model || busyRef.current) return;
    busyRef.current = true; setError(''); setAnalysis(''); setAnalysisSources([]);
    setRunning(true); setStage('Preparing analysis');
    const controller = new AbortController(); abortRef.current = controller;
    try {
      const dossierId = await ensureDossier();
      log('Requested explanation of ' + selected.name, 'working');
      const response = await fetch('/api/explorelean/analyze', {
        method: 'POST', cache: 'no-store', signal: controller.signal,
        headers: {'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true'},
        body: JSON.stringify({
          formal_path: selected.path, declaration: selected.name,
          include_guide: includeGuide, include_announcement: includeAnnouncement,
          model, reasoning_effort: effort, objective, dossier_id: dossierId,
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
            completed = true; setAnalysis(event.text || ''); setAnalysisSources(event.sources || []);
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
        const message = explainError(cause); setError(message); setStage('Failed');
        log('Exploration failed: ' + message, 'error');
      }
    } finally {setRunning(false); abortRef.current = null; busyRef.current = false;}
  }
  function stopAnalysis() {abortRef.current?.abort();}
  async function saveNote() {
    if (!selected || !note.trim() || savingNote) return;
    setSavingNote(true); setError('');
    try {
      const id = await ensureDossier();
      await postJSON('/api/explorelean/dossiers/' + encodeURIComponent(id) + '/notes', {
        formal_path: selected.path, declaration: selected.name, text: note.trim(),
      });
      await loadDossier(id); await refreshDossiers();
      log('Saved note for ' + selected.name, 'ok');
    } catch (cause) {setError(explainError(cause));}
    finally {setSavingNote(false);}
  }

  const filtered = file?.declarations.filter(item => item.name.toLowerCase().includes(filter.trim().toLowerCase())) ?? [];
  const ready = !!selected && !loadingFile && !loadingDeclaration && !running && !!config?.available && !!model;
  const selectedEntries = dossier?.entries.filter(item => item.source.name === selectedName && item.source.path === file?.path) ?? [];

  return <main className="chat-page leanx-ui">
    <div className="leanx-page-row">
      <div>
        <p className="chat-eyebrow">Pinned formal proof · Source-driven exploration</p>
        <p className="leanx-description">Select an actual Lean declaration, inspect its source, explain it against the literature, and accumulate a cited expository dossier.</p>
      </div>
      <button className="leanx-close-button" type="button" aria-label="Close Lean Explorer" data-tooltip="Close Lean Explorer" onClick={onClose}>×</button>
    </div>

    <section className="leanx-section" aria-label="Proof and supplementary inputs">
      <div className="leanx-section-heading"><h2>Inputs</h2><span>Actual sources</span></div>
      <div className="leanx-formal-input">
        <label htmlFor="leanx-input-path">A. Official proof · <SourceLink href="https://github.com/CocoSgt/riemann-hypothesis-lean">CocoSgt mirror</SourceLink></label>
        <div className="leanx-input-row">
          <input id="leanx-input-path" spellCheck={false} value={formalInput} disabled={running || loadingFile} onChange={event => setFormalInput(event.target.value)}
            onKeyDown={event => {if (event.key === 'Enter') void loadFile(formalInput.trim());}}/>
          <button type="button" disabled={running || loadingFile || !formalInput.trim()} onClick={() => void loadFile(formalInput.trim())}>{loadingFile ? 'Reading…' : 'Open file'}</button>
        </div>
        {file && <div className="leanx-source-line">
          <span>Commit <code>{file.commit.slice(0, 12)}</code></span>
          <span>SHA256 <code>{file.sha256.slice(0, 12)}…</code></span>
          <span>{file.total} candidate declarations</span>
          <span>Lexical scan · Not kernel checked</span>
          <SourceLink href={file.url}>Source</SourceLink>
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

    <div className="leanx-workspace-grid">
      <aside className="leanx-pane leanx-declarations" aria-label="Lean declaration selector">
        <div className="leanx-pane-title"><h2>Declarations</h2><span>{file?.total ?? '—'} in this file</span></div>
        <input type="search" placeholder="Filter declarations…" aria-label="Filter declarations" value={filter} onChange={event => setFilter(event.target.value)}/>
        <div className="leanx-declaration-list">
          {filtered.map(item => <button key={item.name + ':' + item.line} type="button"
            className={item.name === selectedName ? 'is-selected' : ''}
            onClick={() => {setSelectedName(item.name); setAnalysis(''); setAnalysisSources([]);}}>
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

      <div className="leanx-reading-column">
        <section className="leanx-pane leanx-source-code">
          <div className="leanx-pane-title">
            <h2>{selected?.name ?? (loadingDeclaration ? 'Reading declaration…' : 'Lean source')}</h2>
            {selected && <SourceLink href={selected.url + '#L' + selected.start_line}>Lines {selected.start_line}–{selected.end_line}</SourceLink>}
          </div>
          {selected ? <>
            <pre><code>{selected.excerpt}</code></pre>
            <div className="leanx-pane-footer">Actual source · {selected.complete ? 'Excerpt through next declaration boundary' : 'Partial excerpt (length limit)'} · Not an elaborated statement or proof check</div>
          </> : <p className="leanx-empty">Select a declaration to inspect its actual source.</p>}
        </section>

        <section className="leanx-pane leanx-analysis-pane">
          <div className="leanx-pane-title"><h2>Mathematical interpretation</h2><span>AI commentary · Not formally verified</span></div>
          <label className="leanx-objective-label" htmlFor="leanx-objective">Expository objective</label>
          <textarea id="leanx-objective" rows={2} value={objective} disabled={running} onChange={event => setObjective(event.target.value)}/>
          <div className="leanx-operation-controls">
            <button type="button" className="leanx-primary-action" disabled={!ready || !objective.trim()} onClick={() => void analyzeSelected()}>
              {running ? 'Exploring…' : 'Explain selected declaration'}
            </button>
            <button type="button" disabled={!running} onClick={stopAnalysis}>Stop</button>
            <span>{config ? (config.available ? `${config.models.find(item => item.id === model)?.label ?? model} · ${effort}` : config.message) : 'Reading selected AI connection…'}</span>
          </div>
          {analysis ? <div className="leanx-explanation"><Suspense fallback={<p>{analysis}</p>}><RenderedMarkdown body={analysis}/></Suspense></div> :
            <p className="leanx-empty">Explanation will appear here, grounded in the selected declaration and chosen supplementary excerpts.</p>}
          {!!analysisSources.length && <details className="leanx-evidence-detail">
            <summary>Evidence used in this explanation ({analysisSources.length})</summary>
            {analysisSources.map(item => <p key={item.kind + item.path}>
              {item.kind}: <SourceLink href={item.url}>{item.path}</SourceLink>
              <span> · {item.commit.slice(0, 12)} · SHA256 {item.sha256.slice(0, 12)}…</span>
            </p>)}
          </details>}
          {!!selectedEntries.length && <div className="leanx-existing">Saved entries for this declaration: {selectedEntries.length}</div>}
        </section>
      </div>

      <aside className="leanx-progress-column">
        <section className="leanx-pane leanx-progress-pane" aria-live="polite">
          <div className="leanx-pane-title">
            <h2>Live activity</h2>
            <span className={running ? 'leanx-live-dot is-active' : 'leanx-live-dot'} aria-label={running ? 'Active' : 'Idle'}/>
          </div>
          <div className="leanx-stage">{stage}</div>
          {running && <p className="leanx-running-time">Elapsed: {Math.floor(elapsed / 60)}m {String(elapsed % 60).padStart(2, '0')}s</p>}
          <ol className="leanx-activity-log">
            {activity.map(item => <li key={item.id} className={'leanx-state-' + item.state}>
              <span className="leanx-activity-icon" aria-hidden="true">{item.state === 'ok' ? '✓' : item.state === 'error' ? '!' : '•'}</span>
              <div><span>{item.label}</span><small><Timestamp value={item.time}/></small></div>
            </li>)}
            {!activity.length && <li className="leanx-muted-activity">No operations yet.</li>}
          </ol>
        </section>
        <section className="leanx-pane leanx-dossier-pane">
          <div className="leanx-pane-title"><h2>Expository dossier</h2><span>{dossier?.entries.length ?? 0} entries</span></div>
          <label htmlFor="leanx-dossier-select">Working dossier</label>
          <div className="leanx-dossier-select-row">
            <select id="leanx-dossier-select" value={dossier?.id ?? ''} disabled={running} onChange={event => void selectDossier(event.target.value)}>
              <option value="">Choose dossier…</option>
              {dossierList.map(item => <option key={item.id} value={item.id}>{item.title} ({item.entry_count})</option>)}
            </select>
            <button type="button" disabled={running} onClick={() => void createDossier()}>New</button>
          </div>
          {dossier && <>
            <a className="leanx-download-link" href={'/api/explorelean/dossiers/' + encodeURIComponent(dossier.id) + '/markdown'}>Download dossier (Markdown)</a>
            <div className="leanx-dossier-entries">
              {dossier.entries.slice().reverse().slice(0, 12).map(item => <button key={item.id} type="button"
                onClick={() => {
                  if (item.source.path !== path) {
                    setFormalInput(item.source.path); void loadFile(item.source.path);
                  }
                  setSelectedName(item.source.name); setAnalysis(item.text);
                  setAnalysisSources(item.supplementary_sources || []);
                }}>
                <span>{item.source.name}</span><small>{item.mode} · <Timestamp value={item.created_at}/></small>
              </button>)}
              {!dossier.entries.length && <p className="leanx-empty">Explanations are saved here automatically after completion.</p>}
            </div>
          </>}
          <label htmlFor="leanx-note">Note on selected declaration</label>
          <textarea id="leanx-note" value={note} rows={3} disabled={!selected || savingNote || running} onChange={event => setNote(event.target.value)}
            placeholder="Record an interpretation, question, or open obligation…"/>
          <button type="button" disabled={!selected || !note.trim() || savingNote || running} onClick={() => void saveNote()}>
            {savingNote ? 'Saving…' : 'Save note'}
          </button>
        </section>
      </aside>
    </div>

    {error && <p className="chat-error leanx-error" role="alert">{error}</p>}
    <p className="leanx-boundary">Current capability: pinned-source retrieval, single-file declaration scanning, source-grounded AI explanations, durable dossiers and Markdown export. Full import/dependency indexing, Lean elaboration, verification and SIGMA paper handoff are not yet implemented.</p>
  </main>;
}
