import assert from 'node:assert/strict';
import test from 'node:test';
import { sessionValidationDetail } from '../src/session-validation-diagnostics.ts';

test('saved invalid role response reveals its precise persisted validator reason', () => {
  const steps = [
    { status: 'completed', strategy_id: 'a', failure_kind: null },
    { status: 'failed', strategy_id: 'a', failure_kind: 'response_invalid' },
  ];
  const branches = [{ strategy_id: 'a', status: 'failed', reason: 'Skeptic obligation_reviews cited evidence not selected into its context' }];
  assert.equal(sessionValidationDetail(steps, branches), branches[0].reason);
});

test('old validation failure does not contaminate a later connection failure', () => {
  const steps = [
    { status: 'failed', strategy_id: 'a', failure_kind: 'response_invalid' },
    { status: 'failed', strategy_id: 'a', failure_kind: 'transport_interrupted' },
  ];
  assert.equal(sessionValidationDetail(steps, [
    { strategy_id: 'a', status: 'failed', reason: 'Old validation failure' },
  ]), null);
});

test('validation detail requires the matching failed strategy', () => {
  const steps = [{ status: 'failed', strategy_id: 'a', failure_kind: 'response_invalid' }];
  const branches = [
    { strategy_id: 'b', status: 'failed', reason: 'Unrelated failure' },
    { strategy_id: 'a', status: 'failed', reason: 'reasoning_steps.basis_artifact_ids not supplied' },
  ];
  assert.equal(sessionValidationDetail(steps, branches), branches[1].reason);
  assert.equal(sessionValidationDetail(steps, branches.slice(0, 1)), null);
});

test('per-attempt validation message takes precedence over stale branch text', () => {
  const steps = [{ status: 'failed', strategy_id: 'a', failure_kind: 'response_invalid', failure_message: 'Schema: field claim (missing)' }];
  assert.equal(sessionValidationDetail(steps, [
    { strategy_id: 'a', status: 'failed', reason: 'Old context error' },
  ]), 'Schema: field claim (missing)');
});
