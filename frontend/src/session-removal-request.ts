/** Shared deletion transport used by ResearchWorkspace and browser acceptance. */
export async function removeResearchSession(path: string, sessionId: string, expectedUpdatedAt: string): Promise<{ session_number: number }> {
  const response = await fetch(`/api/projects/research-sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json', 'X-Sigma-Error-Handled': 'true' },
    body: JSON.stringify({ path, expected_updated_at: expectedUpdatedAt }),
  });
  const result = await response.json() as { error?: string; session_number: number };
  if (!response.ok) throw new Error(result.error ?? 'Session removal failed');
  return result;
}
