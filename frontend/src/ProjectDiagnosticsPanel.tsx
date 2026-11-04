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
  return <section aria-label="Project diagnostics" className="project-diagnostics-panel">
    <details>
      <summary>Project diagnostics ({diagnostics.length})</summary>
      <p>Includes errors before Session #1 exists. Sanitized readable export; not the full raw provider-wire audit log.</p>
      <button type="button" aria-label="Copy project diagnostics" onClick={() => void copy()}>Copy diagnostics</button>
      <a href={downloadUrl} aria-label="Download project diagnostics">Download diagnostics</a>
      <ol>{diagnostics.map(item => <li key={item.id}>
        <time>{item.timestamp}</time> · {item.stage} · {item.code}: {item.message}
        <small> Event {item.id}{item.session_id ? ` · Session ${item.session_id}` : ' · pre-session'}</small>
      </li>)}</ol>
    </details>
    {status && <p role="status">{status}</p>}
    {copyStatus && <p role="status">{copyStatus}</p>}
  </section>;
}
