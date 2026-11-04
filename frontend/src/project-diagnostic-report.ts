// Shared browser transport: never claim a diagnostic was saved unless the
// server confirms it. The original UI-visible message is authoritative.
export type DiagnosticReport = {
  recorded: boolean;
  correlationId: string;
  status: string;
};

export async function reportProjectDiagnostic(
  path: string,
  message: string,
  stage: string,
  correlationId: string,
): Promise<DiagnosticReport> {
  try {
    const response = await fetch('/api/projects/diagnostics', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path, stage, code: 'browser_request_failed', message, correlation_id: correlationId,
      }),
    });
    if (!response.ok) throw new Error('diagnostic storage unavailable');
    const result = await response.json() as { recorded?: boolean; diagnostic?: { message?: string; correlation_id?: string } };
    if (!result.recorded || !result.diagnostic) throw new Error('diagnostic not recorded');
    // Redaction can change the message: the report is still the canonical
    // sanitized record, but do not falsely claim that raw UI text was stored.
    return {
      recorded: true,
      correlationId,
      status: 'Error recorded in Project diagnostics.',
    };
  } catch {
    return {
      recorded: false,
      correlationId,
      status: `Error not recorded (offline or logging unavailable). Correlation ID: ${correlationId}.`,
    };
  }
}
