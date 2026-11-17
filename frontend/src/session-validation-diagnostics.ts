/**
 * Existing persisted sessions already contain the branch-local validation
 * exception, even though the aggregated termination label is only
 * "response_invalid". Surface the latest relevant reason, not a stale error
 * from an earlier rejected turn or a different strategy.
 */
export type FailedResearchStep = {
  status?: string;
  failure_kind?: string | null;
  strategy_id?: string | null;
  failure_message?: string | null;
};
export type FailedResearchBranch = {
  strategy_id: string;
  status: string;
  reason?: string | null;
};

export function sessionValidationDetail(
  steps: readonly FailedResearchStep[],
  branches: readonly FailedResearchBranch[],
): string | null {
  const lastFailure = [...steps].reverse().find(step => step.status === 'failed');
  if (lastFailure?.failure_kind !== 'response_invalid') return null;
  const reason = branches.find(branch =>
    branch.strategy_id === lastFailure.strategy_id
    && branch.status === 'failed'
    && typeof branch.reason === 'string'
    && branch.reason.trim().length > 0,
  )?.reason;
  const detail = lastFailure.failure_message?.trim() || reason?.trim();
  return detail ? detail.slice(0, 900) : null;
}
