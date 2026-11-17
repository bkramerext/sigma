/** Session deletion transport; stale state and in-flight teardown are retried
 * without emitting a global Request Failed toast. Never retry an auth error. */
type SessionRemovalResponse = { session_number: number; id?: string; removed?: boolean };
type SessionSnapshot = { id: string; updated_at: string; status: string; session_number: number };
const retryable = (message: string) =>
  /Session changed; refresh its status|Session execution is still releasing resources/.test(message);

const readBody = async (response: Response): Promise<Record<string, unknown>> => {
  try { return await response.json() as Record<string, unknown>; }
  catch { return {}; }
};
const messageFrom = (body: Record<string, unknown>, fallback: string) =>
  typeof body.error === 'string' && body.error ? body.error : fallback;

export async function removeResearchSession(
  path: string, sessionId: string, expectedUpdatedAt: string,
  sessionNumber = 0,
): Promise<SessionRemovalResponse> {
  const query = new URLSearchParams({ path });
  const target = `/api/projects/research-sessions/${encodeURIComponent(sessionId)}`;
  const safeHeaders = { 'X-Sigma-Error-Handled': 'true' };
  let expected = expectedUpdatedAt;
  let knownNumber = sessionNumber;
  for (let attempt = 0; attempt < 5; attempt++) {
    let retry = false;
    try {
      const response = await fetch(target, {
        method: 'DELETE',
        headers: { ...safeHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, expected_updated_at: expected }),
      });
      const body = await readBody(response);
      if (response.ok) {
        return { session_number: Number(body.session_number) || knownNumber, id: sessionId, removed: true };
      }
      const message = messageFrom(body, 'Session removal failed.');
      if (!retryable(message) && response.status !== 404) throw new Error(message);
      retry = retryable(message);
    } catch (error) {
      // Network loss after the server committed deletion is ambiguous.
      // A read-only state check decides whether deletion has already won.
      if (error instanceof Error && error.message !== 'Failed to fetch'
          && error.message !== 'NetworkError when attempting to fetch resource.'
          && !retryable(error.message)) throw error;
      retry = true;
    }

    const stateResponse = await fetch(`${target}?${query}`, {
      cache: 'no-store', headers: safeHeaders,
    });
    if (stateResponse.status === 404) {
      return { session_number: knownNumber, id: sessionId, removed: true };
    }
    if (!stateResponse.ok) throw new Error('Could not confirm the session removal state.');
    const snapshot = await readBody(stateResponse) as Partial<SessionSnapshot>;
    if (snapshot.id !== sessionId || typeof snapshot.updated_at !== 'string') {
      throw new Error('Session removal state is inconsistent.');
    }
    if (snapshot.status === 'running' || snapshot.status === 'queued') {
      throw new Error('The session is active; stop it before removing it.');
    }
    if (!retry) break;
    expected = snapshot.updated_at;
    if (typeof snapshot.session_number === 'number') knownNumber = snapshot.session_number;
    if (attempt < 4) await new Promise<void>(resolve => setTimeout(resolve, 180 * (attempt + 1)));
  }
  throw new Error('Could not complete session removal after reconciling its saved state.');
}
