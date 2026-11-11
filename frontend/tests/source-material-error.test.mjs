import assert from 'node:assert/strict';
import test from 'node:test';
import { sourceMaterialOverflowCopy } from '../src/source-material-error.ts';

const exact = 'Source Material contains 279,835 extracted characters; the session supports at most 60,000. Split or shorten the supplied documents.';

test('excess Source Material is named with exact persisted counts and a concrete action', () => {
  const copy = sourceMaterialOverflowCopy(exact);
  assert.match(copy.cause, /Too much Source Material/);
  assert.match(copy.cause, /279,835/);
  assert.match(copy.cause, /60,000/);
  assert.match(copy.cause, /219,835 over/);
  assert.match(copy.cause, /not the selected model’s context window/);
  assert.match(copy.next, /Source Material list/);
  assert.match(copy.next, /disable or remove/);
  assert.match(copy.next, /start a new session/);
  assert.match(copy.next, /frozen sources/);
});

test('historical blocked event preserves sizes even after top-level message changes', () => {
  const copy = sourceMaterialOverflowCopy('Stopped after Resume', [
    { kind: 'source_material.compilation.blocked', message: exact },
  ]);
  assert.match(copy.cause, /279,835/);
  assert.match(copy.cause, /60,000/);
});

test('missing counts are not invented', () => {
  const copy = sourceMaterialOverflowCopy('Source material exceeds context limit');
  assert.match(copy.cause, /exceed SIGMA’s extracted-text limit/);
  assert.doesNotMatch(copy.cause, /\d+,\d+/);
});
