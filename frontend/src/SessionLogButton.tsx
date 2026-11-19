import { openReusableTab } from './reusable-tabs';

export default function SessionLogButton({ sessionId, sessionNumber, path }: {
  sessionId: string;
  sessionNumber: number;
  path: string;
}) {
  const query = new URLSearchParams({ session_log: sessionId, path });
  return <a
    className="text-view-link text-view-icon workspace-icon-button session-log-open-link"
    aria-label={`View Session ${sessionNumber} transcript`}
    data-tooltip="View session transcript"
    href={`/?${query}`}
    onClick={event => openReusableTab(event, `sigma-log:${path}:${sessionId}`)}
    target="_blank"
    rel="noopener noreferrer"
  ><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M14 2.5H6a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-11z"/>
    <path d="M14 2.5v6h6M8 13h8M8 17h6"/>
  </svg></a>;
}
