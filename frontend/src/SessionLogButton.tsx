export default function SessionLogButton({ sessionId, sessionNumber, path, indicator = false }: {
  sessionId: string;
  sessionNumber: number;
  path: string;
  indicator?: boolean;
}) {
  const query = new URLSearchParams({ session_log: sessionId, path });
  const url = `/session?${query}`;
  return <a
    className={indicator ? "session-status-navigation-indicator" : "text-view-link text-view-icon workspace-icon-button session-log-open-link"}
    aria-label={`Open Session ${sessionNumber} page`}
    data-tooltip={indicator ? "Open running session" : "Open session"}
    href={url}
    onClick={event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      window.history.pushState(null, "", url);
      window.dispatchEvent(new PopStateEvent("popstate"));
    }}
  >{indicator ? <span className="research-running-indicator" aria-hidden="true"/> : <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M13 3.5H6a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-7"/><path d="M14 3.5h6.5V10M20.5 3.5l-9 9"/></svg>}</a>;
}
