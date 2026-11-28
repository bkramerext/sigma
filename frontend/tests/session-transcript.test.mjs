import assert from 'node:assert/strict';
import test from 'node:test';
import { projectTranscript, groupTranscriptTurns, transcriptDefaultExpanded, readableTranscriptResponse, transcriptCategories, convertibleTranscriptEntry, supervisorDisplay, transcriptRoleLabel, paginateTranscriptTurns, formatTranscriptMarkdown } from '../src/session-transcript.ts';

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

test('reading view retains failed attempts and omits non-response audit chatter', () => {
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
    'transient failure', 'Substantive AI one result', 'Substantive AI two result', 'Process check',
  ]);
  const turns = groupTranscriptTurns(entries);
  assert.deepEqual(turns.map(group => group.label), ['Turn 1']);
  assert.deepEqual(turns[0].entries.map(entry => entry.role), [
    'investigator', 'investigator', 'skeptic', 'supervisor',
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

test('Transcript uses paired role labels and Brainstorm displays Co-investigators', () => {
  assert.equal(transcriptRoleLabel('investigator', false), 'Investigator');
  assert.equal(transcriptRoleLabel('skeptic', false), 'Skeptic');
  assert.equal(transcriptRoleLabel('investigator', true), 'Co-investigator');
  assert.equal(transcriptRoleLabel('skeptic', true), 'Co-investigator');
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
    [[3, 'Skeptic'], [4, 'Co-investigator'], [5, 'Skeptic']]);
});

test('Markdown presentation fences nested JSON and formats artifact GUIDs', () => {
  const id = 'ebcaaf1f-f6d7-4d3e-9082-1fd352d5bf98';
  const body = ['#### Reasoning steps', '', '[', '  {', '    "title": "Definitions",',
    '    "basis_artifact_ids": ["' + id + '"]', '  }', ']', '',
    '- Original artifact ' + id + ' is unavailable.',
    '- Already formatted `' + id + '` remains.',
  ].join('\n');
  const output = formatTranscriptMarkdown(body);
  assert.ok(output.includes('```json\n[\n  {'));
  assert.ok(output.includes(']\n```\n'));
  assert.ok(output.includes('- Original artifact `' + id + '` is unavailable.'));
  assert.ok(output.includes('Already formatted `' + id + '` remains.'));
  assert.equal(formatTranscriptMarkdown(output), output);
});

test('accepted saved results survive missing raw history, with no false pending or invented times', () => {
  const events = [
    { seq: 1, timestamp: '2026-11-18T01:00:01Z', type: 'provider_request', request_id: 'a', role: 'investigator', round: 1, strategy_id: 'x', step_id: 'step-a' },
    { seq: 2, timestamp: '2026-11-18T01:00:02Z', type: 'retention_limit', message: 'Raw history limit reached' },
  ];
  const before = JSON.stringify(events);
  const saved = [
    { step_id: 'step-a', role: 'investigator', round: 1, strategy_id: 'x', status: 'completed',
      started_at: '2026-11-18T01:00:01Z', finished_at: '2026-11-18T01:00:03Z', text: 'Saved investigator result' },
    { step_id: 'step-b', role: 'skeptic', round: 1, strategy_id: 'x', status: 'completed', text: 'Saved critique' },
    { step_id: 'step-c', role: 'supervisor', round: 1, strategy_id: 'x', status: 'completed',
      finished_at: '2026-11-18T01:00:05Z', text: 'Saved process review' },
  ];
  const entries = projectTranscript(events, [], saved, 'completed');
  assert.equal(JSON.stringify(events), before);
  assert.equal(entries.filter(entry => entry.reconstructed).length, 3);
  assert.ok(entries.every(entry => !entry.pending && !convertibleTranscriptEntry(entry)));
  assert.equal(entries.find(entry => entry.id === 'saved-step-b').timestamp, '');
  assert.equal(entries.find(entry => entry.id === 'saved-step-a').timestamp, saved[0].finished_at);
  assert.ok(entries.some(entry => entry.historyNotice && entry.text === 'Raw history limit reached'));
  assert.equal(groupTranscriptTurns(entries).find(group => group.key === 'x:1').entries.length, 3);
});

test('raw response and subsequent validation failure are retained separately from accepted retry', () => {
  const events = [
    { seq: 1, timestamp: '2026-11-18T01:00:01Z', type: 'provider_request', request_id: 'a', role: 'investigator', round: 1, strategy_id: 'x', step_id: 'step-a' },
    { seq: 2, timestamp: '2026-11-18T01:00:02Z', type: 'provider_response', request_id: 'a', response: { output_text: 'A long raw result that subsequently fails schema validation.' } },
    { seq: 3, timestamp: '2026-11-18T01:00:03Z', type: 'provider_failure', request_id: 'a', message: 'Schema validation failed' },
    { seq: 4, timestamp: '2026-11-18T01:00:04Z', type: 'provider_request', request_id: 'b', role: 'investigator', round: 1, strategy_id: 'x', step_id: 'step-b' },
    { seq: 5, timestamp: '2026-11-18T01:00:05Z', type: 'provider_response', request_id: 'b', response: { output_text: 'A substantive accepted research result with a full explanation.' } },
  ];
  const saved = [
    { step_id: 'step-a', role: 'investigator', round: 1, strategy_id: 'x', status: 'failed', failure_kind: 'response_invalid' },
    { step_id: 'step-b', role: 'investigator', round: 1, strategy_id: 'x', status: 'completed',
      request_id: 'b', text: 'A substantive accepted research result with a full explanation.' },
  ];
  const entries = projectTranscript(events, [], saved, 'completed');
  assert.deepEqual(entries.map(entry => entry.title), [
    'Provider response with recorded failure', 'Provider failure', 'Accepted response',
    'Reconstructed from saved state',
  ]);
  assert.equal(new Set(entries.map(entry => entry.id)).size, 4);
  assert.deepEqual(entries.filter(convertibleTranscriptEntry).map(entry => entry.id), ['response-b']);
  assert.deepEqual(entries.filter(entry => !entry.reconstructed).map(entry => entry.sequence), [2, 3, 5]);
  assert.match(entries.find(entry => entry.reconstructed).text, /response_invalid/);
});

test('orphan terminal attribution, interruption, and concurrent strategies reconcile by exact ID', () => {
  const events = [
    { seq: 1, timestamp: '2026-11-18T01:00:01Z', type: 'provider_request', request_id: 'a', role: 'investigator', round: 1, strategy_id: 'x', step_id: 'interrupted' },
    { seq: 2, timestamp: '2026-11-18T01:00:02Z', type: 'provider_response', request_id: 'b', role: 'investigator', round: 1, strategy_id: 'y', step_id: 'accepted-y', response: { output_text: 'Accepted Y result' } },
    { seq: 3, timestamp: '2026-11-18T01:00:03Z', type: 'provider_response', request_id: 'c', role: 'investigator', round: 1, strategy_id: 'x', step_id: 'accepted-y', response: { output_text: 'Conflicting strategy attribution' } },
    { seq: 4, timestamp: '2026-11-18T01:00:04Z', type: 'provider_request', request_id: 'd', role: 'skeptic', round: 1, strategy_id: 'y', step_id: 'running-y' },
  ];
  const saved = [
    { step_id: 'interrupted', role: 'investigator', round: 1, strategy_id: 'x', status: 'interrupted',
      finished_at: '2026-11-18T01:00:02Z', interruption_reason: 'backend_restart' },
    { step_id: 'accepted-y', role: 'investigator', round: 1, strategy_id: 'y', status: 'completed', request_id: 'b', text: 'Accepted Y result' },
    { step_id: 'running-y', role: 'skeptic', round: 1, strategy_id: 'y', status: 'running', request_id: 'd' },
  ];
  const entries = projectTranscript(events, [], saved, 'running');
  assert.equal(entries.find(entry => entry.id === 'saved-interrupted').pending, undefined);
  assert.match(entries.find(entry => entry.id === 'saved-interrupted').text, /interrupted/);
  assert.equal(entries.find(entry => entry.id === 'response-b').strategyId, 'y');
  assert.equal(entries.find(entry => entry.id === 'raw-response-c-3').title, 'Raw response (acceptance unverified)');
  assert.equal(entries.find(entry => entry.id === 'raw-response-c-3').correlationUnknown, true);
  assert.ok(groupTranscriptTurns(entries).find(group => group.label.startsWith('Uncertain attribution')
    && group.entries.some(entry => entry.id === 'raw-response-c-3')));
  assert.equal(entries.find(entry => entry.id === 'pending-d').pending, true);
  assert.equal(entries.filter(entry => entry.pending).length, 1);
  assert.equal(projectTranscript(events, [], saved, 'paused').filter(entry => entry.pending).length, 0);
});

test('multiple raw responses sharing an attempt remain separate and cannot establish acceptance', () => {
  const events = [
    { seq: 1, timestamp: '2026-11-18T01:00:01Z', type: 'provider_request', request_id: 'a', role: 'investigator', round: 1, strategy_id: 'x', step_id: 'step-a' },
    { seq: 2, timestamp: '2026-11-18T01:00:02Z', type: 'provider_response', request_id: 'a', response: { output_text: 'First retained response' } },
    { seq: 3, timestamp: '2026-11-18T01:00:03Z', type: 'provider_response', request_id: 'a', response: { output_text: 'Second retained response' } },
  ];
  const entries = projectTranscript(events, [], [{ step_id: 'step-a', role: 'investigator', status: 'completed',
    round: 1, strategy_id: 'x', text: 'Persisted accepted result' }], 'completed');
  assert.equal(entries.length, 3);
  assert.equal(new Set(entries.map(entry => entry.id)).size, 3);
  assert.equal(entries.filter(entry => entry.reconstructed).length, 1);
  assert.ok(entries.every(entry => !convertibleTranscriptEntry(entry)));
});

test('raw execution chronology is independent of grouped presentation for four turns and three strategies', () => {
  let seq = 0;
  const events = [];
  const saved = [];
  const time = n => new Date(Date.UTC(2026, 0, 1, 0, 0, n)).toISOString();
  for (let round = 1; round <= 4; round++) {
    for (const role of ['investigator', 'skeptic', 'supervisor']) {
      for (const strategy_id of ['a', 'b', 'c']) {
        const step_id = `${strategy_id}-${round}-${role}`;
        const started_at = time(++seq);
        if (role !== 'supervisor')
          events.push({ seq, timestamp: started_at, type: 'provider_request', request_id: step_id,
            step_id, role, round, strategy_id });
        const finished_at = time(++seq);
        if (role === 'supervisor')
          events.push({ seq, timestamp: finished_at, type: 'session_event', event_kind: 'supervisor.review',
            step_id, role, round, strategy_id, message: step_id });
        else
          events.push({ seq, timestamp: finished_at, type: 'provider_response', request_id: step_id,
            step_id, role, round, strategy_id, response: { output_text: step_id } });
        saved.push({ step_id, request_id: role === 'supervisor' ? undefined : step_id,
          role, strategy_id, round, status: 'completed', started_at, finished_at, text: step_id });
      }
    }
  }
  // Assert chronological evidence independently of grouping, before simulating
  // a retention gap. This fixture is synthetic, not a claim about ONP execution.
  for (const strategy of ['a', 'b', 'c']) for (let turn = 1; turn <= 4; turn++) {
    const pair = saved.filter(s => s.strategy_id === strategy && s.round === turn);
    assert.ok(pair[0].finished_at < pair[1].started_at);
    assert.ok(pair[1].finished_at < pair[2].started_at);
  }
  const retained = events.slice(0, 17);
  const entries = projectTranscript(retained, [], saved, 'completed');
  assert.equal(entries.filter(e => (e.role === 'investigator' || e.role === 'skeptic')
    && (e.reconstructed || e.title === 'Accepted response')).length, 24);
  assert.equal(entries.filter(e => e.role === 'supervisor').length, 12);
  assert.ok(entries.every(e => !e.pending));
  const groups = groupTranscriptTurns(entries);
  assert.equal(groups.length, 12);
  for (const group of groups) assert.equal(group.entries.filter(e =>
    e.reconstructed || e.title === 'Accepted response' || e.role === 'supervisor').length, 3);
});

test('contradictory or absent attempt identity and mismatching content never replace saved acceptance', () => {
  const stamp = '2026-01-01T00:00:00Z';
  const step = { step_id: 's', request_id: 'accepted', role: 'investigator', strategy_id: 'x',
    round: 1, status: 'completed', text: 'Authoritative saved completion' };
  const event = { seq: 1, timestamp: stamp, type: 'provider_response', request_id: 'older',
    step_id: 's', role: 'investigator', strategy_id: 'x', round: 1, response: { output_text: 'Old raw reply' } };
  for (const [raw, saved] of [
    [event, step],
    [{ ...event, request_id: 'accepted' }, step],
    [{ ...event, request_id: undefined }, step],
    [event, { ...step, request_id: undefined }],
  ]) {
    const rows = projectTranscript([raw], [], [saved], 'completed');
    assert.equal(rows.length, 2);
    assert.equal(rows.find(row => row.reconstructed).text, step.text);
    assert.equal(rows.find(row => !row.reconstructed).text, 'Old raw reply');
    assert.ok(rows.every(row => !convertibleTranscriptEntry(row)));
  }
  const duplicate = projectTranscript([event], [], [step, { ...step, text: 'Another saved result' }], 'completed');
  assert.equal(duplicate.filter(row => row.reconstructed).length, 2);
  assert.ok(duplicate.every(row => row.correlationUnknown));
});

test('unanswered raw attempts remain distinct while running, paused and resumed', () => {
  const stamp = '2026-01-01T00:00:00Z';
  const common = { timestamp: stamp, type: 'provider_request', step_id: 's', role: 'skeptic', round: 1, strategy_id: 'x' };
  const events = [{ ...common, seq: 1, request_id: 'old' }, { ...common, seq: 2, request_id: 'new' }];
  const step = { step_id: 's', request_id: 'new', role: 'skeptic', round: 1, strategy_id: 'x', status: 'running' };
  const running = projectTranscript(events, [], [step], 'running');
  assert.equal(running.filter(row => row.pending).length, 1);
  assert.equal(running.find(row => row.pending).id, 'pending-new');
  assert.equal(running.find(row => row.id === 'pending-old').correlationUnknown, true);
  for (const status of ['paused', 'ended']) {
    const rows = projectTranscript(events, [], [{ ...step, status: 'interrupted', interruption_reason: 'backend_restart' }], status);
    assert.equal(rows.length, 3);
    assert.ok(rows.every(row => !row.pending));
    assert.match(rows.find(row => row.reconstructed).text, /backend_restart/);
  }
  const duplicate = projectTranscript([...events, { ...events[1], seq: 3 }], [], [step], 'running');
  assert.ok(duplicate.every(row => !row.pending));
});

test('mismatching Supervisor review cannot replace saved assessment; duplicate raw review remains ambiguous', () => {
  const step = { step_id: 's', role: 'supervisor', strategy_id: 'x', round: 1, status: 'completed', text: 'Saved assessment' };
  const event = { seq: 1, timestamp: '2026-01-01T00:00:00Z', type: 'session_event', event_kind: 'supervisor.review',
    step_id: 's', role: 'supervisor', strategy_id: 'x', round: 1, message: 'Wrong assessment' };
  const rows = projectTranscript([event], [], [step], 'completed');
  assert.equal(rows.find(row => row.reconstructed).text, step.text);
  assert.equal(rows.find(row => !row.reconstructed).title, 'Raw review (acceptance unverified)');
  const same = { ...event, message: step.text };
  const duplicate = projectTranscript([same, { ...same, seq: 2 }], [], [step], 'completed');
  assert.equal(duplicate.length, 3);
  assert.ok(duplicate.every(row => !convertibleTranscriptEntry(row)));
});

test('long history keeps indexed exact attempts and does not lose accepted results', () => {
  const saved = Array.from({ length: 1200 }, (_, i) => ({
    step_id: 'step-' + i, request_id: 'request-' + i, role: 'investigator',
    strategy_id: 'strategy-' + i % 3, round: 1 + Math.floor(i / 3), status: 'completed',
    text: 'Bounded synthetic content '.repeat(200) + i,
  }));
  const events = saved.map((step, i) => ({
    seq: i + 1, type: 'provider_response', timestamp: '2026-01-01T00:00:00Z',
    request_id: step.request_id, response: { output_text: step.text },
  }));
  const rows = projectTranscript(events, [], saved, 'completed');
  assert.equal(rows.length, saved.length);
  assert.ok(rows.every(row => row.title === 'Accepted response'));
});

test('mixed structured response content remains complete, including historical raw JSON text', () => {
  const data = { mixed: ['visible', { nested: 'retained' }] };
  const raw = JSON.stringify(data);
  const rendered = readableTranscriptResponse({ output_text: raw });
  assert.equal(readableTranscriptResponse(raw), rendered);
  assert.match(rendered, /visible/);
  assert.match(rendered, /retained/);
  const step = { step_id: 'step', request_id: 'request', role: 'investigator',
    strategy_id: 'x', round: 1, status: 'completed', text: rendered };
  const rows = projectTranscript([{ seq: 1, type: 'provider_response', timestamp: '',
    step_id: 'step', request_id: 'request', response: { output_text: raw } }], [], [step], 'completed');
  assert.equal(rows.length, 1);
  assert.equal(rows[0].title, 'Accepted response');
});

test('live admission without request binding is qualified, never definitely pending or missing', () => {
  const event = { seq: 1, timestamp: '2026-01-01T00:00:01Z', type: 'provider_request',
    step_id: 's', request_id: 'new', role: 'investigator', strategy_id: 'x', round: 1 };
  const saved = { step_id: 's', role: 'investigator', strategy_id: 'x', round: 1, status: 'running' };
  const rows = projectTranscript([event], [], [saved], 'running');
  assert.equal(rows.find(r => r.id === 'pending-new').title, 'Provider request (possibly active; attempt unconfirmed)');
  assert.ok(rows.every(r => !r.pending && !convertibleTranscriptEntry(r)));
  assert.equal(rows.filter(r => r.reconstructed).length, 1);
  const multiple = projectTranscript([event, { ...event, seq: 2, request_id: 'older' }], [], [saved], 'running');
  assert.equal(multiple.filter(r => r.title.includes('attempt ambiguous')).length, 2);
  assert.ok(multiple.every(r => !r.pending));
  for (const status of ['paused', 'completed']) {
    const terminal = projectTranscript([event], [], [{ ...saved, status: 'interrupted' }], status);
    assert.equal(terminal.find(r => r.id === 'pending-new').title, 'Response not retained');
  }
  const contradictory = projectTranscript([event], [], [saved,
    { ...saved, step_id: 'other', request_id: 'new' }], 'running');
  assert.equal(contradictory.find(r => r.id === 'pending-new').title, 'Response not retained');
  const completed = projectTranscript([event, { ...event, seq: 2, type: 'provider_response',
    response: { output_text: 'saved result' } }], [], [{ ...saved, status: 'completed',
    request_id: 'new', text: 'saved result' }], 'completed');
  assert.deepEqual(completed.map(r => r.title), ['Accepted response']);
});

test('Supervisor historical fallback cannot override explicit request identity', () => {
  const saved = { step_id: 's', role: 'supervisor', strategy_id: 'x', round: 1,
    status: 'completed', text: 'Saved review with enough text for formatting.' };
  const event = { seq: 1, timestamp: '', type: 'session_event', event_kind: 'supervisor.review',
    role: 'supervisor', strategy_id: 'x', round: 1, message: saved.text };
  assert.equal(projectTranscript([event], [], [saved], 'completed').length, 1);
  for (const raw of [{ ...event, request_id: 'wrong' },
    { ...event, request_id: 'wrong', step_id: 's' }]) {
    const rows = projectTranscript([raw], [], [saved], 'completed');
    assert.equal(rows.length, 2);
    assert.ok(rows.every(r => !convertibleTranscriptEntry(r)));
  }
});
