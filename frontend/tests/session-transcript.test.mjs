import assert from 'node:assert/strict';
import test from 'node:test';
import { projectTranscript, groupTranscriptTurns, readableTranscriptResponse, transcriptCategories, convertibleTranscriptEntry } from '../src/session-transcript.ts';

test('response entries use completion order and retain full provider-authored output', () => {
  const entries = projectTranscript([
    { seq: 1, timestamp: '2026-11-18T01:00:00Z', type: 'provider_request', request_id: 'a', role: 'investigator', round: 1, strategy_id: 'x' },
    { seq: 2, timestamp: '2026-11-18T01:00:01Z', type: 'provider_request', request_id: 'b', role: 'skeptic', round: 1 },
    { seq: 3, timestamp: '2026-11-18T01:00:03Z', type: 'provider_response', request_id: 'b', response: { output_text: 'Challenge and counterexample' } },
    { seq: 4, timestamp: '2026-11-18T01:00:04Z', type: 'provider_response', request_id: 'a', response: { output: [{ content: [{ text: 'Long investigator response' }] }] } },
  ]);
  assert.equal(entries.length, 2);
  assert.deepEqual(entries.map(entry => entry.role), ['skeptic', 'investigator']);
  assert.equal(entries[1].text, 'Long investigator response');
  assert.equal(entries[1].strategyId, 'x');
});
test('human intervention shows full text without a duplicate status entry', () => {
  const entries = projectTranscript([
    { seq: 1, type: 'session_event', timestamp: '2026-11-18T01:00:00Z', event_kind: 'intervention.accepted', message: 'Human objection accepted' },
  ], [{ id: 'h1', text: 'Please test the boundary case.', kind: 'objection', submitted_at: '2026-11-18T01:00:00Z' }]);
  assert.equal(entries.length, 1);
  assert.equal(entries[0].role, 'human');
  assert.equal(entries[0].text, 'Please test the boundary case.');
});
test('raw JSON responses display readable headings without truncation', () => {
  const text = readableTranscriptResponse({ output_text: JSON.stringify({ claim: 'A'.repeat(10000), objections: ['B'] }) });
  assert.ok(text.includes('A'.repeat(10000)));
  assert.match(text, /#### Claim/);
  assert.match(text, /#### Objections/);
});
test('unanswered requests stay visible and filter categories are unique', () => {
  assert.equal(projectTranscript([{ seq: 1, timestamp: '2026-11-18T01:00:00Z', type: 'provider_request', request_id: 'x', role: 'investigator' }])[0].pending, true);
  assert.equal(new Set(transcriptCategories.map(item => item.value)).size, transcriptCategories.length);
});

test('concurrent Session turns group separately and newest completion appears first', () => {
  const entries = projectTranscript([
    { seq: 1, timestamp: '2026-11-18T01:00:00Z', type: 'provider_request', request_id: 'x1', role: 'investigator', round: 1, strategy_id: 'x' },
    { seq: 2, timestamp: '2026-11-18T01:00:01Z', type: 'provider_response', request_id: 'x1', response: { output_text: 'First x' } },
    { seq: 3, timestamp: '2026-11-18T01:00:02Z', type: 'provider_request', request_id: 'y1', role: 'investigator', round: 1, strategy_id: 'y' },
    { seq: 4, timestamp: '2026-11-18T01:00:03Z', type: 'provider_response', request_id: 'y1', response: { output_text: 'First y' } },
    { seq: 5, timestamp: '2026-11-18T01:00:04Z', type: 'provider_request', request_id: 'x2', role: 'skeptic', round: 1, strategy_id: 'x' },
    { seq: 6, timestamp: '2026-11-18T01:00:05Z', type: 'provider_response', request_id: 'x2', response: { output_text: 'Second x' } },
  ]);
  const groups = groupTranscriptTurns(entries);
  assert.deepEqual(groups.map(item => item.key), ['x:1', 'y:1']);
  assert.deepEqual(groups[0].entries.map(item => item.text), ['First x', 'Second x']);
  assert.equal(groups[0].label, 'Turn 1');
});

test('Human input attaches only to its explicit strategy and never to a concurrent peer', () => {
  const entries = projectTranscript([
    { seq: 1, timestamp: '2026-11-18T01:00:00Z', type: 'provider_request', request_id: 'x', role: 'investigator', round: 1, strategy_id: 'x' },
    { seq: 2, timestamp: '2026-11-18T01:00:01Z', type: 'provider_response', request_id: 'x', response: { output_text: 'X hypothesis' } },
    { seq: 3, timestamp: '2026-11-18T01:00:02Z', type: 'provider_request', request_id: 'y', role: 'investigator', round: 1, strategy_id: 'y' },
    { seq: 4, timestamp: '2026-11-18T01:00:03Z', type: 'provider_response', request_id: 'y', response: { output_text: 'Y hypothesis' } },
  ], [
    { id: 'targeted', kind: 'guidance', text: 'Examine X', submitted_at: '2026-11-18T01:00:04Z', target_strategy_ids: ['x'] },
    { id: 'untargeted', kind: 'guidance', text: 'For all', submitted_at: '2026-11-18T01:00:05Z', target_strategy_ids: ['x', 'y'] },
  ]);
  const groups = groupTranscriptTurns(entries);
  assert.ok(groups.find(group => group.key === 'x:1').entries.some(entry => entry.text === 'Examine X'));
  assert.ok(!groups.find(group => group.key === 'y:1').entries.some(entry => entry.text === 'Examine X'));
  assert.ok(groups.find(group => group.label === 'Human').entries.some(entry => entry.text === 'For all'));
});

test('Markdown conversion excludes provider failures and short or unavailable records', () => {
  const rows = projectTranscript([
    { seq: 1, timestamp: '2026-11-18T01:00:00Z', type: 'provider_request', request_id: 'ok', role: 'investigator', round: 1, strategy_id: 'x' },
    { seq: 2, timestamp: '2026-11-18T01:00:01Z', type: 'provider_response', request_id: 'ok', response: { output_text: 'A substantive accepted research result with a full explanation.' } },
    { seq: 3, timestamp: '2026-11-18T01:00:02Z', type: 'provider_request', request_id: 'bad', role: 'skeptic', round: 1, strategy_id: 'x' },
    { seq: 4, timestamp: '2026-11-18T01:00:03Z', type: 'provider_failure', request_id: 'bad', provider_error: 'Provider error: request failed after authentication.' },
    { seq: 5, timestamp: '2026-11-18T01:00:04Z', type: 'session_event', event_kind: 'supervisor.review', role: 'supervisor', message: 'The agents should make their assumptions clearer before drawing conclusions.' },
  ]);
  assert.deepEqual(rows.filter(convertibleTranscriptEntry).map(entry => entry.id), ['response-ok', 'event-5']);
});
