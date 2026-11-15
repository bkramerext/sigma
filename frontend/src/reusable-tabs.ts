import type { MouseEvent } from 'react';

/** Reuse a tab opened by this page while preserving the browser's modifier-click behavior. */
const openedTabs = new Map<string, Window>();

export function openReusableTab(event: MouseEvent<HTMLAnchorElement>, key: string): void {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  const existing = openedTabs.get(key);
  if (existing && !existing.closed) {
    existing.focus();
    return;
  }
  const tab = window.open(event.currentTarget.href, '_blank');
  if (!tab) {
    window.location.assign(event.currentTarget.href);
    return;
  }
  // Keep the target page independent from the initiating SIGMA workspace.
  try { tab.opener = null; } catch { /* PDF viewers may disallow opener access. */ }
  openedTabs.set(key, tab);
  tab.focus();
}
