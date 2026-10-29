export default function SessionLogButton({ sessionId, sessionNumber, path }: {
  sessionId: string;
  sessionNumber: number;
  path: string;
}) {
  const query = new URLSearchParams({ session_log: sessionId, path });
  return <a
    className="text-view-link session-log-open-link"
    aria-label={`Open Session ${sessionNumber} log`}
    title={`Open Session ${sessionNumber} log in a new tab`}
    href={`/?${query}`}
    target="_blank"
    rel="noopener noreferrer"
  >Log</a>;
}
