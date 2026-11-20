import assert from 'node:assert/strict';
import test from 'node:test';
import { projectTranscript, groupTranscriptTurns, transcriptDefaultExpanded, readableTranscriptResponse, transcriptCategories, convertibleTranscriptEntry, supervisorDisplay, transcriptRoleLabel, paginateTranscriptTurns } from '../src/session-transcript.ts';

test('Supervisor ratings become one metadata line without changing saved or copied text', () => {
  const saved = [
    'The reasoning remains conditional; independent verification is needed.',
    '',
    'Objective alignment: 2.0/10.0',
    'Substantive advancement: 2.5/10.0',
    'Evidence & validation: 5.0/10.0',
    'Research health: 8.0/10.0',
  ].join('\n');
  const result = supervisorDisplay(saved);
  assert.equal(result.body, 'The reasoning remains conditional; independent verification is needed.');
  assert.deepEqual(result.scores, { alignment: '2.0', advancement: '2.5', evidence: '5.0', health: '8.0' });
  const entries = projectTranscript([
    { seq: 1, timestamp: '2026-11-20T06:25:47Z', type: 'session_event', event_kind: 'supervisor.review',
      role: 'supervisor', strategy_id: 'x', round: 1, message: saved },
  ]);
  assert.equal(entries[0].text, saved);
  assert.deepEqual(supervisorDisplay('Historical Supervisor note without scores'),
    { body: 'Historical Supervisor note without scores' });
  const withCandidate = supervisorDisplay(saved + ' Unverified breakthrough candidate: needs checking.');
  assert.equal(withCandidate.body, result.body + ' Unverified breakthrough candidate: needs checking.');
  assert.deepEqual(withCandidate.scores, result.scores);
});

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

test('Brainstorm-style transcript starts with only Supervisor expanded', () => {
  for (const role of ['investigator', 'skeptic', 'human', 'other'])
    assert.equal(transcriptDefaultExpanded({ role }), false);
  assert.equal(transcriptDefaultExpanded({ role: 'supervisor' }), true);
});

test('Supervisor groups after its paired agents and the newest exchange displays first', () => {
  const entries = projectTranscript([
    { seq: 1, timestamp: '2026-11-18T01:00:01Z', type: 'provider_request', request_id: 'a1', role: 'investigator', round: 1, strategy_id: 'x' },
    { seq: 2, timestamp: '2026-11-18T01:00:02Z', type: 'provider_response', request_id: 'a1', response: { output_text: 'AI one reply' } },
    { seq: 3, timestamp: '2026-11-18T01:00:03Z', type: 'provider_request', request_id: 'a2', role: 'skeptic', round: 1, strategy_id: 'x' },
    { seq: 4, timestamp: '2026-11-18T01:00:04Z', type: 'provider_response', request_id: 'a2', response: { output_text: 'AI two reply' } },
    { seq: 5, timestamp: '2026-11-18T01:00:05Z', type: 'session_event', event_kind: 'supervisor.review', role: 'supervisor', round: 1, strategy_id: 'x', message: 'Process-only assessment' },
    { seq: 6, timestamp: '2026-11-18T01:00:06Z', type: 'provider_request', request_id: 'b1', role: 'investigator', round: 2, strategy_id: 'x' },
    { seq: 7, timestamp: '2026-11-18T01:00:07Z', type: 'provider_response', request_id: 'b1', response: { output_text: 'Next exchange' } },
  ]);
  const groups = groupTranscriptTurns(entries);
  assert.deepEqual(groups.map(group => group.key), ['x:2', 'x:1']);
  assert.deepEqual(groups[1].entries.map(entry => entry.role), ['investigator', 'skeptic', 'supervisor']);
  assert.deepEqual(groups[1].entries.map(entry => entry.text), ['AI one reply', 'AI two reply', 'Process-only assessment']);
});

test('reading view keeps one accepted reply per turn and omits audit chatter', () => {
  const entries = projectTranscript([
    { seq: 1, timestamp: '2026-11-18T01:00:01Z', type: 'provider_request', request_id: 'first', role: 'investigator', round: 1, strategy_id: 'x' },
    { seq: 2, timestamp: '2026-11-18T01:00:02Z', type: 'provider_failure', request_id: 'first', provider_error: 'transient failure' },
    { seq: 3, timestamp: '2026-11-18T01:00:03Z', type: 'session_event', role: 'investigator', event_kind: 'call.started', round: 1, message: 'Call started' },
    { seq: 4, timestamp: '2026-11-18T01:00:04Z', type: 'provider_request', request_id: 'retry', role: 'investigator', round: 1, strategy_id: 'x' },
    { seq: 5, timestamp: '2026-11-18T01:00:05Z', type: 'provider_response', request_id: 'retry', response: { output_text: 'Substantive AI one result' } },
    { seq: 6, timestamp: '2026-11-18T01:00:06Z', type: 'session_event', role: 'investigator', event_kind: 'call.completed', round: 1, message: 'Call accepted' },
    { seq: 7, timestamp: '2026-11-18T01:00:07Z', type: 'provider_request', request_id: 'peer', role: 'skeptic', round: 1, strategy_id: 'x' },
    { seq: 8, timestamp: '2026-11-18T01:00:08Z', type: 'provider_response', request_id: 'peer', response: { output_text: 'Substantive AI two result' } },
    { seq: 9, timestamp: '2026-11-18T01:00:09Z', type: 'session_event', role: 'supervisor', event_kind: 'supervisor.completed', round: 1, message: 'Supervisor completed' },
    { seq: 10, timestamp: '2026-11-18T01:00:10Z', type: 'session_event', role: 'supervisor', event_kind: 'supervisor.review', round: 1, strategy_id: 'x', message: 'Process check' },
  ]);
  assert.deepEqual(entries.map(entry => entry.text), [
    'Substantive AI one result', 'Substantive AI two result', 'Process check',
  ]);
  const turns = groupTranscriptTurns(entries);
  assert.deepEqual(turns.map(group => group.label), ['Turn 1']);
  assert.deepEqual(turns[0].entries.map(entry => entry.role), [
    'investigator', 'skeptic', 'supervisor',
  ]);
});


test('strategy groups display in ascending order despite concurrent completion timestamps', () => {
  const entries = [
    { id: 's2', timestamp: '2026-11-20T06:23:17Z', role: 'skeptic', round: 1, strategyId: 'strategy-2', sequence: 1 },
    { id: 's3', timestamp: '2026-11-20T06:23:17Z', role: 'skeptic', round: 1, strategyId: 'strategy-3', sequence: 2 },
    { id: 's1-turn2', timestamp: '2026-11-20T06:23:18Z', role: 'investigator', round: 2, strategyId: 'strategy-1', sequence: 3 },
    { id: 's1-turn1', timestamp: '2026-11-20T06:23:16Z', role: 'skeptic', round: 1, strategyId: 'strategy-1', sequence: 4 },
  ];
  assert.deepEqual(groupTranscriptTurns(entries).map(group => group.key), [
    'strategy-1:2', 'strategy-1:1', 'strategy-2:1', 'strategy-3:1',
  ]);
});

test('Transcript uses paired role labels and Brainstorm displays two Investigators', () => {
  assert.equal(transcriptRoleLabel('investigator', false), 'Investigator');
  assert.equal(transcriptRoleLabel('skeptic', false), 'Skeptic');
  assert.equal(transcriptRoleLabel('investigator', true), 'Investigator');
  assert.equal(transcriptRoleLabel('skeptic', true), 'Investigator');
  assert.equal(transcriptRoleLabel('supervisor', true), 'Supervisor');
  assert.equal(transcriptRoleLabel('human', false), 'Human');
});

test('Supervisor originality displays when present and legacy four-score reviews remain valid', () => {
  const saved = [
    'The agents are exploring fresh possibilities.',
    '',
    'Objective alignment: 4.0/10.0',
    'Originality: 6.5/10.0',
    'Substantive advancement: 2.5/10.0',
    'Evidence & validation: 3.0/10.0',
    'Research health: 7.0/10.0',
  ].join('\n');
  assert.deepEqual(supervisorDisplay(saved), {
    body: 'The agents are exploring fresh possibilities.',
    scores: { alignment: '4.0', originality: '6.5', advancement: '2.5', evidence: '3.0', health: '7.0' },
  });
});

test('Transcript pagination reveals twenty turn numbers at a time without splitting strategies', () => {
  const groups = [];
  for (let turn = 45; turn >= 1; turn--) {
    for (const strategy of ['a', 'b', 'c']) {
      groups.push({
        key: `${strategy}:${turn}`, label: `Turn ${turn}`, latestTimestamp: '',
        entries: [{ id: `${strategy}:${turn}`, role: 'investigator', round: turn, strategyId: strategy, timestamp: '', sequence: 1, text: '' }],
      });
    }
  }
  const initial = paginateTranscriptTurns(groups, 20);
  assert.equal(initial.shownGroups.length, 60);
  assert.equal(initial.remainingTurns, 25);
  assert.deepEqual([...new Set(initial.shownGroups.map(group => group.entries[0].round))],
    Array.from({ length: 20 }, (_, index) => 45 - index));
  const second = paginateTranscriptTurns(groups, 40);
  assert.equal(second.shownGroups.length, 120);
  assert.equal(second.remainingTurns, 5);
  const last = paginateTranscriptTurns(groups, 60);
  assert.equal(last.shownGroups.length, 135);
  assert.equal(last.remainingTurns, 0);
});

test('Transcript role labels retain the mode at each historical provider dispatch', () => {
  const ordinary = { instructions: 'Regular paired research instructions.' };
  const brainstorm = { instructions: 'BRAINSTORM MODE: You and your peer are two co-investigators. Independently explore.' };
  const entries = projectTranscript([
    { seq: 1, type: 'provider_request', request_id: 'old', role: 'skeptic', round: 3,
      strategy_id: 's', timestamp: '2026-11-20T01:00:00Z', request: ordinary },
    { seq: 2, type: 'provider_response', request_id: 'old', timestamp: '2026-11-20T01:00:02Z',
      response: { output_text: 'Earlier ordinary mode answer' } },
    { seq: 3, type: 'provider_request', request_id: 'new', role: 'skeptic', round: 4,
      strategy_id: 's', timestamp: '2026-11-20T01:00:03Z', request: brainstorm },
    { seq: 4, type: 'provider_response', request_id: 'new', timestamp: '2026-11-20T01:00:04Z',
      response: { output_text: 'Later brainstorm mode answer' } },
    { seq: 5, type: 'provider_request', request_id: 'pending', role: 'skeptic', round: 5,
      strategy_id: 's', timestamp: '2026-11-20T01:00:05Z', brainstorm_mode: false, request: brainstorm },
  ]);
  assert.deepEqual(entries.map(entry => [entry.round, transcriptRoleLabel(entry.role, entry.brainstormMode === true)]),
    [[3, 'Skeptic'], [4, 'Investigator'], [5, 'Skeptic']]);
});
