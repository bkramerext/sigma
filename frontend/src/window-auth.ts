/** Give each top-level SIGMA browser window its own authenticated cookie. */
const WINDOW_KEY = 'sigma.auth.window';
const existing = (() => {
  try { return window.sessionStorage.getItem(WINDOW_KEY); } catch { return null; }
})();
const windowId = existing && /^[a-f0-9]{32}$/.test(existing) ? existing : (() => {
  const value = crypto.randomUUID().replaceAll('-', '');
  try { window.sessionStorage.setItem(WINDOW_KEY, value); } catch { return ''; }
  return value;
})();

export function windowAuthUrl(path: string): string {
  if (!windowId) return path;
  const url = new URL(path, window.location.origin);
  if (url.origin !== window.location.origin || !url.pathname.startsWith('/api/')) return path;
  url.searchParams.set(url.pathname === '/api/cloud-auth/login' ? 'window_id' : 'sigma_window', windowId);
  return url.pathname + url.search + url.hash;
}

if (windowId) {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const target = new URL(input instanceof Request ? input.url : String(input), window.location.href);
    if (target.origin !== window.location.origin) return nativeFetch(input, init);
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
