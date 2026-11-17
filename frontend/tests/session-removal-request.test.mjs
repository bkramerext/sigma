import assert from 'node:assert/strict';
import test from 'node:test';
import { removeResearchSession } from '../src/session-removal-request.ts';

const sessionId = 'b65ca881-02e0-4071-8997-6d20fbd7a043';
const path = 'shared/project.json';
const result = (status, body) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
});

test('Session 17 deletion silently retries a stale revision then succeeds', async () => {
  const savedFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (_url, init) => {
    calls.push(init);
    if (calls.length === 1) return result(409, { error: 'Session changed; refresh its status before removing it' });
    if (calls.length === 2) return result(200, { id: sessionId, updated_at: 'new-rev', status: 'stopped', session_number: 17 });
    return result(200, { removed: true, id: sessionId, session_number: 17 });
  };
  try {
    const deleted = await removeResearchSession(path, sessionId, 'old-rev', 17);
    assert.equal(deleted.session_number, 17);
    assert.equal(deleted.removed, true);
    assert.equal(calls.length, 3);
    assert.equal(new Headers(calls[0].headers).get('X-Sigma-Error-Handled'), 'true');
    assert.equal(JSON.parse(calls[2].body).expected_updated_at, 'new-rev');
  } finally { globalThis.fetch = savedFetch; }
});

test('a lost delete response is recognized as successful if the record is gone', async () => {
  const savedFetch = globalThis.fetch;
  let count = 0;
  globalThis.fetch = async (_url, init) => {
    count++;
    if (init?.method === 'DELETE') throw new TypeError('Failed to fetch');
    return result(404, { error: 'Research session not found' });
  };
  try {
    const deleted = await removeResearchSession(path, sessionId, 'old-rev', 17);
    assert.equal(deleted.session_number, 17);
    assert.equal(deleted.removed, true);
    assert.equal(count, 2);
  } finally { globalThis.fetch = savedFetch; }
});

test('a still-releasing terminal worker is retried without an error toast', async () => {
  const savedFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async (_url, init) => {
    calls++;
    if (calls === 1) return result(409, { error: 'Session execution is still releasing resources; its record was retained' });
    if (calls === 2) return result(200, { id: sessionId, updated_at: 'rev-2', status: 'stopped', session_number: 17 });
    return result(200, { removed: true, id: sessionId, session_number: 17 });
  };
  try {
    assert.equal((await removeResearchSession(path, sessionId, 'rev-1', 17)).removed, true);
    assert.equal(calls, 3);
  } finally { globalThis.fetch = savedFetch; }
});

test('authorization errors and newly running sessions are never retried as deletions', async () => {
  const savedFetch = globalThis.fetch;
  globalThis.fetch = async () => result(403, { error: 'Only the creator may remove unfinished work.' });
  try {
    await assert.rejects(() => removeResearchSession(path, sessionId, 'rev-1', 17), /Only the creator/);
  } finally { globalThis.fetch = savedFetch; }

  let calls = 0;
  globalThis.fetch = async (_url, init) => {
    calls++;
    if (init?.method === 'DELETE') return result(409, { error: 'Session changed; refresh its status before removing it' });
    return result(200, { id: sessionId, updated_at: 'rev-2', status: 'running', session_number: 17 });
  };
  try {
    await assert.rejects(() => removeResearchSession(path, sessionId, 'rev-1', 17), /active/);
    assert.equal(calls, 2);
  } finally { globalThis.fetch = savedFetch; }
});
