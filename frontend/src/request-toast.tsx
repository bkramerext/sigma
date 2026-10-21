import { useEffect, useState } from 'react';
import './request-toast.css';

type Failure = { id: number; message: string };
const listeners = new Set<(failure: Failure) => void>();
let nextId = 0;

export function reportRequestFailure(message: string) {
  const failure = { id: ++nextId, message };
  listeners.forEach(listener => listener(failure));
}

function describeError(body: unknown): string | null {
  if (typeof body === 'string') return body.trim() || null;
  if (!body || typeof body !== 'object') return null;
  const fields = body as Record<string, unknown>;
  for (const key of ['error', 'detail', 'message']) {
    const value = fields[key];
    if (typeof value === 'string' && value.trim()) return value;
    if (Array.isArray(value) && value.length) {
      const descriptions = value.map(item => typeof item === 'string' ? item : (item && typeof item === 'object' && 'msg' in item ? String(item.msg) : '')).filter(Boolean);
      if (descriptions.length) return descriptions.join('; ');
    }
  }
  return null;
}

async function responseError(response: Response): Promise<string> {
  let detail: string | null = null;
  try {
    const body = await response.clone().text();
    if (body) {
      try { detail = describeError(JSON.parse(body)); }
      catch { detail = body.slice(0, 300).trim(); }
    }
  } catch { /* Failure to read the body must not interfere with the caller. */ }
  const status = `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}`;
  return detail ? `${status}: ${detail}` : status;
}

/**
 * Centralized error reporting for the local API.
 * Preserve fetch semantics: callers still receive responses and rejections
 * so existing loading/error handling can restore the right view.
 */
export function installRequestErrorToasts() {
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const isApi = new URL(url, window.location.href).pathname.startsWith('/api/');
    try {
      const response = await originalFetch(input, init);
      if (isApi && !response.ok) reportRequestFailure(await responseError(response));
      return response;
    } catch (error) {
      const aborted = init?.signal?.aborted || (input instanceof Request && input.signal.aborted)
        || (error instanceof DOMException && error.name === 'AbortError');
      if (isApi && !aborted) {
        reportRequestFailure(error instanceof Error ? error.message : 'Network request failed');
      }
      throw error;
    }
  };
}

export function RequestErrorToasts() {
  const [failures, setFailures] = useState<Failure[]>([]);
  useEffect(() => {
    const receive = (failure: Failure) => setFailures(current => [...current, failure].slice(-4));
    listeners.add(receive);
    return () => { listeners.delete(receive); };
  }, []);
  return <div className="request-toast-stack" aria-label="Request errors">
    {failures.map(failure => <div className="request-toast" role="alert" key={failure.id}>
      <div className="request-toast-content"><strong>Request Failed</strong><p>{failure.message}</p></div>
      <button type="button" aria-label="Dismiss request error" onClick={() => setFailures(current => current.filter(item => item.id !== failure.id))}>Dismiss</button>
    </div>)}
  </div>;
}
