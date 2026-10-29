export default function SessionLogButton({ sessionId, sessionNumber, path }: {
  sessionId: string;
  sessionNumber: number;
  path: string;
}) {
  return <button
    type="button"
    className="text-view-link session-remove-link"
    aria-label={`Open Session ${sessionNumber} log`}
    title={`Open Session ${sessionNumber} log in a new window`}
    onClick={() => {
      const query = new URLSearchParams({ session_log: sessionId, path });
      window.open(`/?${query}`, '_blank', 'noopener');
    }}
  >Log</button>;
}
