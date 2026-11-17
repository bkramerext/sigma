import assert from 'node:assert/strict';
import test from 'node:test';
import { publicationAwaitingLibrary, unlistedPublicationIds } from '../src/paper-publication-handoff.ts';

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

  // Once the saved PDF appears, retire the run in that same React render.
  assert.equal(publicationAwaitingLibrary(run, [saved]), false);
  assert.deepEqual(unlistedPublicationIds([run], [saved]), []);
});

test('refresh retry survives stale listings and a completed scoring sidecar', () => {
  const finished = { ...run, status: 'complete' };
  assert.equal(publicationAwaitingLibrary(finished, []), true);
  assert.deepEqual(unlistedPublicationIds([finished], []), ['published-7']);
  assert.equal(publicationAwaitingLibrary(finished, [saved]), false);
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
