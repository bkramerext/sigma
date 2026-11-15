import { openReusableTab } from './reusable-tabs';

export default function SessionLogButton({ sessionId, sessionNumber, path }: {
  sessionId: string;
  sessionNumber: number;
  path: string;
}) {
  const query = new URLSearchParams({ session_log: sessionId, path });
  return <a
    className="text-view-link text-view-icon workspace-icon-button session-log-open-link"
    aria-label={`View Session ${sessionNumber} log`}
    data-tooltip="View session log"
    href={`/?${query}`}
    onClick={event => openReusableTab(event, `sigma-log:${path}:${sessionId}`)}
    target="_blank"
    rel="noopener noreferrer"
  ><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M13 6h8M13 12h8M13 18h8M3 6h1M8 6h1M3 12h1M8 12h1M3 18h1M8 18h1"/></svg></a>;
}
