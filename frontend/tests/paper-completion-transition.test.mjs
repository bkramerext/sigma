import assert from 'node:assert/strict';
import test from 'node:test';
import {
  displayedPaperNumber,
  hasActualDraftIdentity,
  shouldShowPaperLoading,
  canRemoveDisplayedPaperRun,
  shouldAutoSelectUnfinishedPaper,
  orderPaperRunsDescending,
} from '../src/paper-completion-transition.ts';

test('Paper 15 keeps its reserved identity while progress and publication metadata change', () => {
  const runId = 'reserved-paper-15';
  const reserved = { runId, number: 15 };

  // The authoritative reservation is present during Finish.
  assert.equal(displayedPaperNumber({ number: 15 }, reserved, runId), 15);

  // A sidecar temporarily omits the run while the final SSE event arrives.
  assert.equal(displayedPaperNumber(null, reserved, runId), 15);
  assert.equal(hasActualDraftIdentity(runId, false, false, false, false), true);

  // Saved Paper 15 has replaced the run; the generation request may still
  // resolve asynchronously but it must not materialize a new unnumbered card.
  assert.equal(hasActualDraftIdentity(null, false, false, false, false), false);
  assert.equal(displayedPaperNumber(null, reserved, null), null);
});

test('paper-run cards stay newest-first before metadata is available', () => {
  const runs = [1, 2, 3, 5, 7].map(number => ({ number, run_id: `run-${number}` }));
  const ordered = orderPaperRunsDescending(runs);
  assert.deepEqual(ordered.map(run => run.number), [7, 5, 3, 2, 1]);
  assert.deepEqual(runs.map(run => run.number), [1, 2, 3, 5, 7], 'input is not mutated');
  assert.deepEqual(orderPaperRunsDescending([...ordered, { number: 8, run_id: 'new' }])
    .map(run => run.number), [8, 7, 5, 3, 2, 1]);
});

test('background completion never shows a Loading papers interstitial', () => {
  assert.equal(shouldShowPaperLoading(true, 14, 1, true), false);
  assert.equal(shouldShowPaperLoading(true, 15, 0, false), false);
  assert.equal(shouldShowPaperLoading(true, 0, 1, false), false);
  assert.equal(shouldShowPaperLoading(true, 0, 0, true), false);
  assert.equal(shouldShowPaperLoading(true, 0, 0, false), true);
  assert.equal(shouldShowPaperLoading(false, 0, 0, false), false);
});

test('the four terminal unpublished papers expose authorized X controls', () => {
  for (const status of ['interrupted', 'cancelled', 'failed', 'complete']) {
    assert.equal(canRemoveDisplayedPaperRun({
      status, paper_id: null, can_remove: true, can_control: false,
    }), true, status);
  }
});

test('published fallback row uses saved-PDF removal only after scoring completes', () => {
  assert.equal(canRemoveDisplayedPaperRun({
    status: 'active', paper_id: 'published-id', can_remove: true, can_control: true,
  }), false);
  assert.equal(canRemoveDisplayedPaperRun({
    status: 'complete', paper_id: 'published-id', can_remove: true, can_control: false,
  }), true);
  assert.equal(canRemoveDisplayedPaperRun({
    status: 'failed', paper_id: 'published-id', can_remove: true, can_control: false,
  }), false);
});

test('no X is shown to an unauthorized viewer; active creator can still Stop first', () => {
  assert.equal(canRemoveDisplayedPaperRun({
    status: 'interrupted', can_remove: false, can_control: false,
  }), false);
  assert.equal(canRemoveDisplayedPaperRun({
    status: 'active', can_remove: true, can_control: false,
  }), false);
  assert.equal(canRemoveDisplayedPaperRun({
    status: 'active', can_remove: true, can_control: true,
  }), true);
});

test('legacy active progress stays visible without a cloud reservation', () => {
  assert.equal(hasActualDraftIdentity(null, false, false, false, false, false, 'active'), true);
  assert.equal(hasActualDraftIdentity(null, false, false, false, false, false, 'interrupted'), true);
});

test('finished Paper never becomes unnumbered due to stale busy or restart state', () => {
  assert.equal(hasActualDraftIdentity(null, true, true, true, true, true, 'active', true), false);
  assert.equal(hasActualDraftIdentity(null, true, true, true, true, false, 'complete', false), false);
  assert.equal(hasActualDraftIdentity(null, true, true, true, true, false, 'active', true), false);
});

test('a just-finished Paper 15 does not jump to one of four old unfinished Papers', () => {
  assert.equal(shouldAutoSelectUnfinishedPaper(null, false, 4, true), false);
  assert.equal(shouldAutoSelectUnfinishedPaper(null, false, 4, false), true);
  assert.equal(shouldAutoSelectUnfinishedPaper('paper-15-run', false, 4, false), false);
  assert.equal(shouldAutoSelectUnfinishedPaper(null, true, 4, false), false);
});
