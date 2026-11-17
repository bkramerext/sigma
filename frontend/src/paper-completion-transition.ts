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
  busy = false,
  progressStatus: string | null = null,
  publishedFinished = false,
): boolean {
  if (selectedRunId) return true;
  // An older local run can have a durable progress sidecar but no cloud
  // reservation. Keep that bar visible, including after browser reload.
  // After publication, never mistake a stale busy flag or checkpoint for a
  // newly starting, unnumbered Paper.
  if (busy || publishedFinished || progressStatus === 'complete') return false;
  return Boolean(continuationAvailable || checkpointMismatch || restartableCheckpoint ||
    restartReady || ['active', 'queued', 'interrupted', 'failed', 'cancelled'].includes(progressStatus ?? ''));
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

/** Do not redirect a just-finished Paper into a different abandoned run. */
export function shouldAutoSelectUnfinishedPaper(
  currentRunId: string | null,
  newPaperRequested: boolean,
  eligibleRunCount: number,
  justPublished: boolean,
): boolean {
  return !currentRunId && !newPaperRequested && eligibleRunCount > 0 && !justPublished;
}
