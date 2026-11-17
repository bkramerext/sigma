/** Single rendering boundary for generating → published Paper transitions. */

type NumberedRun = { number?: number | null };
type ReservedNumber = { runId: string; number: number };
type RemovableRun = {
  status: string;
  paper_id?: string | null;
  can_remove?: boolean;
  can_control?: boolean;
};

export function displayedPaperNumber(
  selectedRun: NumberedRun | null | undefined,
  reserved: ReservedNumber | null,
  selectedRunId: string | null,
): number | null {
  return selectedRun?.number ?? (reserved?.runId === selectedRunId ? reserved.number : null);
}

export function hasActualDraftIdentity(
  selectedRunId: string | null,
  continuationAvailable: boolean,
  checkpointMismatch: boolean,
  restartableCheckpoint: boolean,
  restartReady: boolean,
): boolean {
  return Boolean(selectedRunId || continuationAvailable || checkpointMismatch ||
    restartableCheckpoint || restartReady);
}

export function shouldShowPaperLoading(
  loading: boolean,
  savedCount: number,
  runningCount: number,
  newPaperRequested: boolean,
): boolean {
  return loading && savedCount === 0 && runningCount === 0 && !newPaperRequested;
}

export function canRemoveDisplayedPaperRun(run: RemovableRun): boolean {
  if (!run.can_remove) return false;
  // A published run has its own authenticated PDF deletion route and cannot
  // be removed as an unfinished checkpoint while automatic scoring is active.
  if (run.paper_id) return run.status === 'complete';
  return Boolean(run.can_control || !['active', 'queued'].includes(run.status));
}
