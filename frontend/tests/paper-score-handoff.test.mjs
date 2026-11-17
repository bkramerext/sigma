import assert from 'node:assert/strict';
import test from 'node:test';
import { activeScoringPaperIds, automaticScorePhase, completedScoringPaperIds, savedPaperScoreDisplay } from '../src/paper-score-handoff.ts';

test('stored score wins over stale Score, Finishing, and even failed run progress', () => {
  for (const stage of ['scoring', 'finishing', 'score_failed', 'pdf_check']) {
    const runs = [{ paper_id: 'paper-22', status: 'active', progress: { stage } }];
    const displayed = savedPaperScoreDisplay(83, false, automaticScorePhase(runs, 'paper-22'));
    assert.equal(displayed.label, 'Score 83/100');
    assert.equal(displayed.busy, false);
    assert.equal(displayed.stage, 'complete');
  }
});

test('finishing is not shown as a second Scoring operation', () => {
  const active = [{ paper_id: 'paper-22', status: 'active', progress: { stage: 'scoring' } }];
  const finishing = [{ paper_id: 'paper-22', status: 'active', progress: { stage: 'finishing' } }];
  assert.equal(savedPaperScoreDisplay(null, false, automaticScorePhase(active, 'paper-22')).label, 'Scoring…');
  assert.deepEqual(savedPaperScoreDisplay(null, false, automaticScorePhase(finishing, 'paper-22')), {
    label: 'Finalizing…', busy: true, status: 'active', stage: 'finishing',
  });
  assert.equal(savedPaperScoreDisplay(null, false, automaticScorePhase([{
    paper_id: 'paper-22', status: 'active', progress: { stage: 'pdf_check' },
  }], 'paper-22')).label, 'Score');
});

test('only an explicit Rescore overrides an already persisted result', () => {
  assert.equal(savedPaperScoreDisplay(71, false, null).label, 'Score 71/100');
  assert.equal(savedPaperScoreDisplay(71, true, null).label, 'Scoring…');
});

test('refresh score metadata at Score -> Finishing rather than waiting for run completion', () => {
  const scoring = [{ paper_id: 'paper-22', status: 'active', progress: { stage: 'scoring' } }];
  const previous = activeScoringPaperIds(scoring);
  assert.deepEqual(completedScoringPaperIds(previous, [{
    paper_id: 'paper-22', status: 'active', progress: { stage: 'finishing' },
  }]), ['paper-22']);
  assert.deepEqual(completedScoringPaperIds(previous, [{
    paper_id: 'paper-22', status: 'complete', progress: { stage: 'complete' },
  }]), ['paper-22']);
  assert.deepEqual(completedScoringPaperIds(previous, scoring), []);
  assert.deepEqual(completedScoringPaperIds(activeScoringPaperIds([]), [{
    paper_id: 'paper-22', status: 'complete', progress: { stage: 'complete' },
  }]), []);
});
