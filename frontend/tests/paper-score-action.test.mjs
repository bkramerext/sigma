import assert from 'node:assert/strict';
import test from 'node:test';
import { activatePaperScoreStep } from '../src/paper-score-action.ts';

test('a completed Scored step opens its saved score instead of rescoring', () => {
  const calls = [];
  activatePaperScoreStep(true, () => calls.push('view'), () => calls.push('score'));
  assert.deepEqual(calls, ['view']);
});

test('a paper without a saved score retries through the cache-safe scoring path', () => {
  const calls = [];
  activatePaperScoreStep(false, () => calls.push('view'), () => calls.push('score'));
  assert.deepEqual(calls, ['score']);
});
