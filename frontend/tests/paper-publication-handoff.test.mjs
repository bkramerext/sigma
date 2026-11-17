import assert from 'node:assert/strict';
import test from 'node:test';
import { publicationAwaitingLibrary, publishedRunActivityLabel, publishedRunReadyForHandoff, publishedRunStillFinishing, savedPaperAwaitingGenerationFinish, unlistedPublicationIds } from '../src/paper-publication-handoff.ts';

const run = { run_id: 'run-7', status: 'active', paper_id: 'published-7' };
const saved = { paper_id: 'published-7' };

test('publication before automatic scoring completes never leaves both cards absent', () => {
  const beforePDF = { ...run, paper_id: null };
  assert.equal(publicationAwaitingLibrary(beforePDF, []), false);
  // The normal active draft is still visible before the first published PDF.
  assert.equal(beforePDF.status, 'active');

  // The reserved run now has a durable PDF ID, but metadata has not arrived:
  // keep the run card and trigger a lightweight library refresh.
  assert.equal(publicationAwaitingLibrary(run, []), true);
  assert.deepEqual(unlistedPublicationIds([run], []), ['published-7']);

  // Previously the saved PDF immediately replaced the original Score bar,
  // creating the appearance of a second scoring operation. The run must
  // remain visible while the original automatic evaluation is in flight.
  assert.equal(publicationAwaitingLibrary(run, [saved]), false);
  assert.equal(publishedRunStillFinishing(run), true);
  assert.equal(publishedRunReadyForHandoff(run, [saved]), false);
  assert.equal(savedPaperAwaitingGenerationFinish(saved.paper_id, [run]), true);
  assert.deepEqual(unlistedPublicationIds([run], [saved]), []);
});

test('refresh retry survives stale listings and a completed scoring sidecar', () => {
  const finished = { ...run, status: 'complete' };
  assert.equal(publicationAwaitingLibrary(finished, []), true);
  assert.deepEqual(unlistedPublicationIds([finished], []), ['published-7']);
  assert.equal(publicationAwaitingLibrary(finished, [saved]), false);
  assert.equal(publishedRunReadyForHandoff(finished, [saved]), true);
  assert.equal(savedPaperAwaitingGenerationFinish(saved.paper_id, [finished]), false);
});

test('multiple collaborators only wait for unpublished metadata', () => {
  const second = { run_id: 'run-8', status: 'active', paper_id: 'published-8' };
  assert.deepEqual(unlistedPublicationIds([run, second, run], [saved]), ['published-8']);
  assert.deepEqual(unlistedPublicationIds([run, second], [], new Set(['published-8'])), ['published-7']);
});

test('ordinary unfinished and deleted papers do not trigger new listing requests', () => {
  assert.deepEqual(unlistedPublicationIds([
    { paper_id: null }, {}, { paper_id: '' }, { paper_id: 'removed' },
  ], [], new Set(['removed'])), []);
  assert.equal(publicationAwaitingLibrary(null, []), false);
});


test('the pipeline Score and Finish always remain in the same generating card', () => {
  const paperId = 'paper-22';
  const saved = { paper_id: paperId, score: null };
  for (const stage of ['pdf_check', 'scoring', 'score_failed', 'finishing']) {
    const active = { run_id: 'run-22', status: 'active', paper_id: paperId, progress: { stage } };
    const runCard = publishedRunStillFinishing(active);
    const savedCard = !savedPaperAwaitingGenerationFinish(paperId, [active]);
    assert.equal(runCard, true, stage);
    assert.equal(savedCard, false, stage);
    assert.equal(Number(runCard) + Number(savedCard), 1, `duplicate or missing card at ${stage}`);
    assert.equal(publishedRunReadyForHandoff(active, [saved]), false, stage);
  }

  // A saved score can arrive while Finish is still active, but the UI must
  // not show a second "Scoring..." after the Score milestone has completed.
  const finishing = { run_id: 'run-22', status: 'active', paper_id: paperId,
    progress: { stage: 'finishing' } };
  assert.equal(publishedRunActivityLabel(finishing), 'Finishing');
  assert.equal(publishedRunActivityLabel({
    ...finishing, progress: { stage: 'scoring' },
  }), 'Scoring');

  const completed = { ...finishing, status: 'complete', progress: { stage: 'complete' } };
  assert.equal(publishedRunReadyForHandoff(completed, [saved]), true);
  assert.equal(savedPaperAwaitingGenerationFinish(paperId, [completed]), false);
});

test('terminal SSE receipt permits immediate transition despite a stale active progress poll', () => {
  const active = { run_id: 'run-23', status: 'active', paper_id: 'paper-23' };
  const saved = { paper_id: 'paper-23', score: { total: 82 } };
  assert.equal(publishedRunReadyForHandoff(active, [saved]), false);
  assert.equal(publishedRunReadyForHandoff(active, [saved], 'paper-23'), true);
  assert.equal(savedPaperAwaitingGenerationFinish('paper-23', [active], 'paper-23'), false);
  // A short-lived handoff pointer can be cleared after the first refresh,
  // while the polling sidecar still says active. The durable terminal receipt
  // must continue suppressing that stale status on every subsequent render.
  for (let poll = 0; poll < 4; poll++) {
    assert.equal(savedPaperAwaitingGenerationFinish('paper-23', [active], 'paper-23'), false);
    assert.equal(publishedRunReadyForHandoff(active, [saved], 'paper-23'), true);
  }
  assert.equal(publishedRunReadyForHandoff(active, [], 'paper-23'), false,
    'keep the numbered generating card until the saved metadata is available');
});

test('only the still-running paper is hidden from the saved library', () => {
  const first = { run_id: 'a', paper_id: 'paper-a', status: 'active' };
  const other = { run_id: 'b', paper_id: 'paper-b', status: 'complete' };
  const savedIds = ['paper-a', 'paper-b', 'paper-c'];
  assert.deepEqual(savedIds.filter(id =>
    !savedPaperAwaitingGenerationFinish(id, [first, other])), ['paper-b', 'paper-c']);
  assert.equal(publishedRunReadyForHandoff(other, [{ paper_id: 'paper-b' }]), true);
  assert.equal(publishedRunReadyForHandoff(first, [{ paper_id: 'paper-a' }]), false);
});

test('interruptions do not hide already published PDFs or lose resumability', () => {
  for (const status of ['cancelled', 'failed', 'interrupted']) {
    const run = { paper_id: 'paper-21', status };
    assert.equal(publishedRunStillFinishing(run), false);
    assert.equal(savedPaperAwaitingGenerationFinish('paper-21', [run]), false);
    assert.equal(publishedRunReadyForHandoff(run, [{ paper_id: 'paper-21' }]), true);
  }
});
