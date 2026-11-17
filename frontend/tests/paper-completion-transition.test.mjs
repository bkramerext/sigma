import assert from 'node:assert/strict';
import test from 'node:test';
import {
  displayedPaperNumber,
  hasActualDraftIdentity,
  shouldShowPaperLoading,
  canRemoveDisplayedPaperRun,
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
