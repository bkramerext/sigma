import { useEffect, useRef, useState } from 'react';
import DialogDismissButton from './DialogDismissButton';

type Status = { paired: boolean; online: boolean; ready: boolean; account_label: string; selected_personal: boolean };
type TestResult = { status: string; response: string; model: string };

async function copyToClipboard(value: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return true;
    }
  } catch {
    // Clipboard writes can be blocked after asynchronous pairing requests.
    // The explicit Copy button below provides another user gesture.
  }
  const fallback = document.createElement('textarea');
  fallback.value = value;
  fallback.readOnly = true;
  fallback.style.position = 'fixed';
  fallback.style.left = '-10000px';
  document.body.appendChild(fallback);
  fallback.select();
  try {
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    fallback.remove();
  }
}


async function jsonResponse<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...options });
  if (!response.ok) throw new Error('Companion request failed. Check the Personal connection and retry.');
  return await response.json() as T;
}

export default function PersonalCompanionLab({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [code, setCode] = useState('');
  const [copyStatus, setCopyStatus] = useState('');
  const [commandCopied, setCommandCopied] = useState(false);
  // Developer-only local reproduction; the eventual signed app needs no terminal.
  const command = code
    ? `uv run sigma-personal-companion --server ${window.location.origin} --code '${code}' --choose-account`
    : '';
  const [prompt, setPrompt] = useState('Explain in one sentence why a personal companion can keep ChatGPT credentials off a hosted research server.');
  const [result, setResult] = useState<TestResult | null>(null);
  const [jobId, setJobId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal();
    if (!open && dialog.current?.open) dialog.current.close();
  }, [open]);
  useEffect(() => {
    if (!open) return;
    let active = true;
    const update = async () => {
      try {
        const state = await jsonResponse<Status>('/api/personal-companion/status');
        if (active) setStatus(state);
        if (jobId) {
          const job = await jsonResponse<TestResult>('/api/personal-companion/test/' + encodeURIComponent(jobId));
          if (active && (job.status === 'completed' || job.status === 'failed')) {
            setResult(job);
            setJobId('');
          }
        }
      } catch { if (active) setStatus(null); }
    };
    void update();
    const interval = window.setInterval(() => void update(), 2000);
    return () => { active = false; window.clearInterval(interval); };
  }, [open, jobId]);

  async function pair() {
    setBusy(true); setError(''); setCode(''); setResult(null);
    setCopyStatus(''); setCommandCopied(false);
    try {
      const value = await jsonResponse<{ code: string }>('/api/personal-companion/pair', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}'
      });
      setCode(value.code);
      const copied = await copyToClipboard(value.code);
      setCopyStatus(copied
        ? 'Pairing code copied to clipboard.'
        : 'Automatic copying was blocked. Use Copy pairing code below.');
    } catch { setError('Could not create a pairing code. Choose Personal ChatGPT and sign in to SIGMA first.'); }
    finally { setBusy(false); }
  }
  async function copyCode() {
    const copied = await copyToClipboard(code);
    setCopyStatus(copied ? 'Pairing code copied to clipboard.' : 'Select the code above to copy it manually.');
  }
  async function copyCommand() {
    const copied = await copyToClipboard(command);
    setCommandCopied(copied);
    if (!copied) setCopyStatus('Select the command below to copy it manually.');
  }
  async function test() {
    setBusy(true); setError(''); setResult(null);
    try {
      const value = await jsonResponse<{ job_id: string }>('/api/personal-companion/test', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      setJobId(value.job_id);
    } catch { setError('The companion is not ready or a test is already running.'); }
    finally { setBusy(false); }
  }
  return <dialog ref={dialog} className="google-account-dialog hosted-personal-chatgpt-dialog"
    aria-labelledby="personal-companion-lab-heading" onClose={onClose}>
    <div className="privacy-notice-heading">
      <h2 id="personal-companion-lab-heading">Connect Personal ChatGPT</h2>
      <DialogDismissButton label="Close Personal ChatGPT connection" onClick={onClose}/>
    </div>
    <p>This is a prototype of the hosted connection. ChatGPT sign-in happens inside the separate SIGMA Companion, using OpenAI's account chooser. SIGMA never receives your ChatGPT access token.</p>
    <p><strong>Developer prototype only.</strong> There is no published SIGMA Companion app to install yet. When released, users will download a signed app and connect without Git, Python, or a terminal.</p>
    <p><strong>1.</strong> Create a short-lived pairing code. SIGMA tries to copy it automatically.</p>
    <button type="button" className="connection-text-action" onClick={() => void pair()} disabled={busy}>Create pairing code</button>
    {code && <>
      <p>Pairing code (expires after three minutes):</p>
      <input aria-label="Personal companion pairing code" readOnly value={code} onFocus={event => event.currentTarget.select()}/>
      <button type="button" className="connection-text-action" onClick={() => void copyCode()}>Copy pairing code</button>
      <p role="status">{copyStatus}</p>
      <p><strong>2.</strong> For this local test only, open a second terminal in your SIGMA checkout and run:</p>
      <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}><code>{command}</code></pre>
      <button type="button" className="connection-text-action" onClick={() => void copyCommand()}>Copy terminal command</button>
      {commandCopied && <p role="status">Terminal command copied to clipboard.</p>}
    </>}
    <p><strong>3.</strong> The companion opens OpenAI's account chooser. Choose your ChatGPT account and keep the companion running while testing Personal requests.</p>
    <p role="status">{status?.ready
      ? 'Companion connected: ' + (status.account_label || 'ChatGPT account')
      : status?.online ? 'Companion paired; waiting for eligible ChatGPT authorization.'
      : status?.paired ? 'Companion offline. Personal requests cannot be dispatched.'
      : 'No Personal companion connected.'}</p>
    {status?.ready && <>
      <label htmlFor="personal-companion-test-prompt">Test prompt</label>
      <textarea id="personal-companion-test-prompt" value={prompt} rows={2}
        maxLength={4000} onChange={event => setPrompt(event.target.value)}/>
      <button type="button" className="connection-text-action"
        disabled={busy || !!jobId || !prompt.trim()} onClick={() => void test()}>
        Send one test turn
      </button>
    </>}
    {jobId && <p role="status">A Personal ChatGPT test turn was dispatched. Waiting for the Companion.</p>}
    {result && <p role="status">{result.status === 'completed'
      ? 'Response (' + result.model + '): ' + result.response
      : 'The model attempt did not complete. No automatic retry was made.'}</p>}
    {error && <p role="alert">{error}</p>}
  </dialog>;
}
