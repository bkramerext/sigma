/** Give each top-level SIGMA browser window its own authenticated cookie. */
const WINDOW_KEY = 'sigma.auth.window';
const existing = (() => {
  try { return window.sessionStorage.getItem(WINDOW_KEY); } catch { return null; }
})();
// window.open() can clone sessionStorage into a new top-level window. Detect
// the copied identity and assign a new one before issuing any API requests.
const copiedFromOpener = (() => {
  if (!existing || !window.opener) return false;
  try { return window.opener.sessionStorage.getItem(WINDOW_KEY) === existing; }
  catch { return false; }
})();
const windowId = existing && /^[a-f0-9]{32}$/.test(existing) && !copiedFromOpener ? existing : (() => {
  const value = crypto.randomUUID().replaceAll('-', '');
  try {
    window.sessionStorage.setItem(WINDOW_KEY, value);
    if (copiedFromOpener) window.sessionStorage.removeItem('sigma.auth.windowScoped');
  } catch { return ''; }
  return value;
})();

// Legacy sessions must keep working on upgrade. Window-scoped mode starts on
// the first Google sign-in from this window and survives its OAuth redirect.
const ACTIVE_KEY = 'sigma.auth.windowScoped';
let windowScoped = (() => {
  try { return window.sessionStorage.getItem(ACTIVE_KEY) === 'yes'; } catch { return false; }
})();
function activateWindowSession() {
  try { window.sessionStorage.setItem(ACTIVE_KEY, 'yes'); } catch { /* legacy fallback */ }
  windowScoped = true;
}

// The first request from a new window clones the most recently authenticated
// browser-profile cookie into a separate HttpOnly per-window session. Once
// scoped, subsequent Google logins in other windows cannot change this one.
let adoption: Promise<void> | null = null;
export function adoptLatestWindowSignIn(): Promise<void> {
  if (!windowId || windowScoped) return Promise.resolve();
  if (!adoption) adoption = (async () => {
    try {
      const response = await window.fetch('/api/cloud-auth/window/adopt', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-Sigma-Window': windowId, 'X-Sigma-Error-Handled': 'true' },
      });
      if (!response.ok) return;
      const result = await response.json() as { scoped?: boolean };
      if (result.scoped) activateWindowSession();
    } catch { /* An unavailable auth service keeps its normal sign-in UI. */ }
  })();
  return adoption;
}

export function windowAuthUrl(path: string): string {
  if (!windowId) return path;
  const url = new URL(path, window.location.origin);
  if (url.origin !== window.location.origin || !url.pathname.startsWith('/api/')) return path;
  if (url.pathname === '/api/cloud-auth/login') activateWindowSession();
  if (!windowScoped) return path;
  url.searchParams.set(url.pathname === '/api/cloud-auth/login' ? 'window_id' : 'sigma_window', windowId);
  return url.pathname + url.search + url.hash;
}

if (windowId) {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const target = new URL(input instanceof Request ? input.url : String(input), window.location.href);
    if (!windowScoped || target.origin !== window.location.origin || !target.pathname.startsWith('/api/')) return nativeFetch(input, init);
    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    if (init?.headers) new Headers(init.headers).forEach((value, name) => headers.set(name, value));
    headers.set('X-Sigma-Window', windowId);
    return nativeFetch(input, { ...init, headers });
  };
  document.addEventListener('click', event => {
    if (!(event.target instanceof Element)) return;
    const link = event.target.closest<HTMLAnchorElement>('a[href]');
    if (!link) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin === window.location.origin && url.pathname.startsWith('/api/')) {
      link.href = windowAuthUrl(link.href);
    }
  }, true);
}
