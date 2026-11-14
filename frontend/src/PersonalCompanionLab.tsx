import { useEffect, useRef, useState } from 'react';
import DialogDismissButton from './DialogDismissButton';

type Status = { paired: boolean; online: boolean; ready: boolean; account_label: string; selected_personal: boolean };
type TestResult = { status: string; response: string; model: string };

async function jsonResponse<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...options });
  if (!response.ok) throw new Error('Companion request failed. Check the Personal connection and retry.');
  return await response.json() as T;
}

export default function PersonalCompanionLab({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [code, setCode] = useState('');
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
    try {
      const value = await jsonResponse<{ code: string }>('/api/personal-companion/pair', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}'
      });
      setCode(value.code);
    } catch { setError('Could not create a pairing code. Choose Personal ChatGPT and sign in to SIGMA first.'); }
    finally { setBusy(false); }
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
    <p><strong>1.</strong> Install and open the standalone SIGMA Companion from a published release. No repository checkout is required. Prototype builds are available to developers; a signed installer is not yet released.</p>
    <p><strong>2.</strong> Create a pairing code and enter it in the Companion, along with this SIGMA address: <code>{window.location.origin}</code></p>
    <button type="button" className="connection-text-action" onClick={() => void pair()} disabled={busy}>Create pairing code</button>
    {code && <p role="status">Pairing code (expires after three minutes): <code>{code}</code></p>}
    <p><strong>3.</strong> Complete the OpenAI account chooser in the Companion. Keep it running while Personal research requests are active.</p>
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
