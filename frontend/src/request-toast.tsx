import { useSyncExternalStore } from 'react';
import './request-toast.css';
import { RequestToastStore } from './request-toast-store.js';

const toastStore = new RequestToastStore();

export function reportRequestFailure(message: string) {
  toastStore.add(message);
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
  const maxDetailLength = 600;
  let detail: string | null = null;
  try {
    const body = await response.clone().text();
    if (body) {
      try { detail = describeError(JSON.parse(body)); }
      catch { detail = body.slice(0, 300).trim(); }
    }
  } catch { /* Failure to read the body must not interfere with the caller. */ }
  const status = `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}`;
  if (detail && detail.length > maxDetailLength) {
    return `${status}: The server returned an unusually long error response. SIGMA shortened it; review the session status for details.`;
  }
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
      const requestPath = new URL(url, window.location.href).pathname;
      const expectedSignedOutCheck = response.status === 401 && requestPath === '/api/ai/connection' &&
        (await response.clone().json().catch(() => null) as { error?: unknown } | null)?.error === 'Authentication required.';
      if (isApi && !response.ok && !expectedSignedOutCheck) reportRequestFailure(await responseError(response));
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
  const failures = useSyncExternalStore(toastStore.subscribe, toastStore.getSnapshot, toastStore.getSnapshot);
  return <div className="request-toast-stack" aria-label="Request errors">
    {failures.map(failure => <div className="request-toast-item" data-phase={failure.phase} key={failure.id}>
      <div className="request-toast-item-inner">
        <div className="request-toast" data-phase={failure.phase} role="alert">
          <div className="request-toast-content"><strong>Request Failed</strong><p>{failure.message}</p></div>
          <button type="button" aria-label="Dismiss request error" onClick={() => toastStore.dismiss(failure.id)}>Dismiss</button>
        </div>
      </div>
    </div>)}
  </div>;
}
