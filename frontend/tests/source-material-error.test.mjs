import assert from 'node:assert/strict';
import test from 'node:test';
import { sourceMaterialOverflowCopy, currentSourceMaterialWarnings } from '../src/source-material-error.ts';

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
  assert.match(copy.next, /click Resume/);
  assert.match(copy.next, /reload the current enabled sources/);
});

test('historical blocked event preserves sizes even after top-level message changes', () => {
  const copy = sourceMaterialOverflowCopy('Stopped after Resume', [
    { kind: 'source_material.compilation.blocked', message: exact },
  ]);
  assert.match(copy.cause, /279,835/);
  assert.match(copy.cause, /60,000/);
});

test('new larger limit is displayed from persisted backend measurements', () => {
  const copy = sourceMaterialOverflowCopy(
    'Source Material contains 450,010 extracted characters; the session supports at most 400,000.',
  );
  assert.match(copy.cause, /450,010/);
  assert.match(copy.cause, /400,000/);
  assert.match(copy.cause, /50,010 over/);
});

test('missing counts are not invented', () => {
  const copy = sourceMaterialOverflowCopy('Source material exceeds context limit');
  assert.match(copy.cause, /exceed SIGMA’s extracted-text limit/);
  assert.doesNotMatch(copy.cause, /\d+,\d+/);
});

test('source warnings are individual, session-local, and deduplicated by event sequence', () => {
  const failure = (sequence, message) => ({ sequence, kind: 'source_material.source_failed', message });
  const first = failure(2, 'first (http_403)');
  const second = failure(3, 'second (timeout)');
  const events = [second, first, first];
  assert.deepEqual(currentSourceMaterialWarnings(events), [
    { sequence: 2, message: first.message }, { sequence: 3, message: second.message },
  ]);
  assert.deepEqual(currentSourceMaterialWarnings(events), currentSourceMaterialWarnings(events));
  assert.deepEqual(currentSourceMaterialWarnings([]), []);
});

test('resume clears old notices and a new failure is independently dismissible', () => {
  const old = { sequence: 2, kind: 'source_material.source_failed', message: 'same link (http_403)' };
  const resumed = { sequence: 4, kind: 'resumed' };
  const retry = { ...old, sequence: 5 };
  assert.deepEqual(currentSourceMaterialWarnings([old, resumed]), []);
  assert.deepEqual(currentSourceMaterialWarnings([old, resumed, retry]), [
    { sequence: 5, message: retry.message },
  ]);
  assert.deepEqual(currentSourceMaterialWarnings([old, resumed, retry,
    { sequence: 6, kind: 'source_material.compilation.completed' }]), []);
  assert.deepEqual(currentSourceMaterialWarnings([old,
    { sequence: 3, kind: 'source_material.selection_refreshed' }]), []);
});
