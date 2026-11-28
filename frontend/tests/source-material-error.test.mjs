import assert from 'node:assert/strict';
import test from 'node:test';
import { sourceMaterialOverflowCopy, collectSourceMaterialWarnings } from '../src/source-material-error.ts';

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

test('source warnings are announced individually and only once across polls', () => {
  const seen = new Map();
  const event = (sequence, message) => ({ sequence, kind: 'source_material.source_failed', message });
  const session = events => ({ id: 's1', events });
  assert.deepEqual(collectSourceMaterialWarnings([session([event(2, 'old (http_403)')])], seen, true), []);
  const events = [event(2, 'old (http_403)'), event(5, 'first (http_403)'), event(6, 'second (timeout)')];
  const warnings = collectSourceMaterialWarnings([session(events)], seen);
  assert.equal(warnings.length, 2);
  assert.match(warnings[0], /first \(http_403\)/);
  assert.match(warnings[1], /second \(timeout\)/);
  assert.match(warnings[1], /Source Material.*Resume/);
  assert.deepEqual(collectSourceMaterialWarnings([session(events)], seen), []);
  assert.deepEqual(collectSourceMaterialWarnings([session(events.slice(0, 1))], seen), []);
  assert.equal(collectSourceMaterialWarnings([session([...events, event(9, 'first (http_403)')])], seen).length, 1);
});

test('a new session may fail before its first poll; historical stopped sessions do not replay', () => {
  const seen = new Map();
  collectSourceMaterialWarnings([], seen, true);
  const events = [{ sequence: 1, kind: 'source_material.source_failed', message: 'failed link' }];
  assert.equal(collectSourceMaterialWarnings([{ id: 'new', events }], seen).length, 1);
  assert.deepEqual(collectSourceMaterialWarnings([{ id: 'new', events }], seen), []);
});
