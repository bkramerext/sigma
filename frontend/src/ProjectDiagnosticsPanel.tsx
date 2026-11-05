export type ProjectDiagnostic = {
  id: string;
  timestamp: string;
  stage: string;
  code: string;
  message: string;
  correlation_id: string | null;
  session_id: string | null;
};

export default function ProjectDiagnosticsPanel({ diagnostics, status }: {
  diagnostics: ProjectDiagnostic[];
  status: string;
}) {
  return <section aria-label="Diagnostics" className="project-diagnostics-panel">
    <details className="outcome-subsection project-diagnostics-disclosure">
      <summary>
        <svg aria-hidden="true" className="disclosure-chevron" viewBox="0 0 12 12"><path d="m4 2 4 4-4 4"/></svg>
        <span>Diagnostics ({diagnostics.length})</span>
      </summary>
      <div className="project-diagnostics-content">
        <ol>{diagnostics.map(item => <li key={item.id}>
          <time>{item.timestamp}</time> · {item.stage} · {item.code}: {item.message}
          <small> Event {item.id}{item.session_id ? ` · Session ${item.session_id}` : ' · pre-session'}</small>
        </li>)}</ol>
        {status && <p role="status">{status}</p>}
      </div>
    </details>
  </section>;
}
