import { useState } from 'react';

export type ProjectDiagnostic = {
  id: string;
  timestamp: string;
  stage: string;
  code: string;
  message: string;
  correlation_id: string | null;
  session_id: string | null;
};

export default function ProjectDiagnosticsPanel({ path, diagnostics, status }: {
  path: string;
  diagnostics: ProjectDiagnostic[];
  status: string;
}) {
  const [copyStatus, setCopyStatus] = useState('');
  const downloadUrl = `/api/projects/diagnostics/download?${new URLSearchParams({ path })}`;
  const copy = async () => {
    try {
      // Copy and Download consume exactly the same complete server export.
      const response = await fetch(downloadUrl, { credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) throw new Error('Unable to fetch the diagnostic export');
      await navigator.clipboard.writeText(await response.text());
      setCopyStatus('Project diagnostic export copied.');
    } catch {
      setCopyStatus('Project diagnostic export could not be copied.');
    }
  };
  return <section aria-label="Diagnostics" className="project-diagnostics-panel">
    <details className="outcome-subsection project-diagnostics-disclosure">
      <summary>
        <svg aria-hidden="true" className="disclosure-chevron" viewBox="0 0 12 12"><path d="m4 2 4 4-4 4"/></svg>
        <span>Diagnostics ({diagnostics.length})</span>
      </summary>
      <div className="project-diagnostics-content">
        <p>Includes errors before Session 1 exists. Sanitized readable export; not the full raw provider-wire audit log.</p>
        <div className="project-diagnostics-actions">
          <button type="button" className="text-view-link" aria-label="Copy project diagnostics" onClick={() => void copy()}>Copy</button>
          <a className="text-view-link" href={downloadUrl} aria-label="Download project diagnostics">Download</a>
        </div>
        <ol>{diagnostics.map(item => <li key={item.id}>
          <time>{item.timestamp}</time> · {item.stage} · {item.code}: {item.message}
          <small> Event {item.id}{item.session_id ? ` · Session ${item.session_id}` : ' · pre-session'}</small>
        </li>)}</ol>
        {status && <p role="status">{status}</p>}
        {copyStatus && <p role="status">{copyStatus}</p>}
      </div>
    </details>
  </section>;
}
