/** The saved score is authoritative; run progress may briefly lag persistence.
 * This module never initiates scoring or provider calls.
 */
export type ScoringRun = {
  paper_id?: string | null;
  status?: string | null;
  progress?: { stage?: string | null } | null;
};

export type AutomaticScorePhase = 'scoring' | 'finishing' | null;

function runScorePhase(run: ScoringRun): AutomaticScorePhase {
  if (!run.paper_id || run.status !== 'active') return null;
  switch (run.progress?.stage) {
    case 'scoring':
      return 'scoring';
    case 'score_failed':
    case 'finishing':
      return 'finishing';
    default:
      return null;
  }
}

export function automaticScorePhase(runs: readonly ScoringRun[], paperId: string): AutomaticScorePhase {
  let phase: AutomaticScorePhase = null;
  for (const run of runs) {
    if (run.paper_id !== paperId) continue;
    const current = runScorePhase(run);
    if (current === 'scoring') return 'scoring';
    if (current === 'finishing') phase = 'finishing';
  }
  return phase;
}

/** A previous score evaluation was actually active, not merely PDF checking. */
export function activeScoringPaperIds(runs: readonly ScoringRun[]): Set<string> {
  return new Set(runs.filter(run => run.paper_id && runScorePhase(run) === 'scoring')
    .map(run => run.paper_id as string));
}

/** Refresh only metadata when a previously observed Score ends; no provider
 * request is warranted. Finishing starts after the score has been persisted.
 */
export function completedScoringPaperIds(
  previouslyScoring: ReadonlySet<string>,
  runs: readonly ScoringRun[],
): string[] {
  return [...new Set(runs.filter(run => {
    if (!run.paper_id || !previouslyScoring.has(run.paper_id)) return false;
    const stage = run.progress?.stage;
    return run.status === 'complete' || stage === 'finishing' ||
      stage === 'score_failed' || stage === 'complete';
  }).map(run => run.paper_id as string))];
}

export type SavedPaperScoreDisplay = {
  label: string;
  busy: boolean;
  status: 'active' | 'complete' | 'interrupted';
  stage: 'scoring' | 'complete' | 'score_failed';
};

export function savedPaperScoreDisplay(
  scoreTotal: number | null | undefined,
  manualRescoreInFlight: boolean,
  autoPhase: AutomaticScorePhase,
): SavedPaperScoreDisplay {
  if (manualRescoreInFlight)
    return { label: 'Scoring…', busy: true, status: 'active', stage: 'scoring' };
  // The durable score wins over stale progress from the original generator.
  if (scoreTotal !== null && scoreTotal !== undefined)
    return { label: `Score ${scoreTotal}/100`, busy: false, status: 'complete', stage: 'complete' };
  if (autoPhase === 'scoring')
    return { label: 'Scoring…', busy: true, status: 'active', stage: 'scoring' };
  if (autoPhase === 'finishing')
    return { label: 'Finalizing…', busy: true, status: 'active', stage: 'scoring' };
  return { label: 'Score', busy: false, status: 'interrupted', stage: 'score_failed' };
}
