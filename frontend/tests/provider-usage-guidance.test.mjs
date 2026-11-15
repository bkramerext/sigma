import assert from 'node:assert/strict';
import test from 'node:test';

import {
  friendlyProviderError,
  openAIProjectSpendLimitCopy,
  providerInterruptionCopy,
  sponsoredProviderLabel,
} from '../src/provider-usage-guidance.ts';

test('hosted sponsored pill names the effective inference provider', () => {
  assert.equal(sponsoredProviderLabel('api_key'), 'Sponsored OpenAI API');
  assert.equal(sponsoredProviderLabel('chatgpt'), 'Sponsored ChatGPT');
  assert.equal(sponsoredProviderLabel(undefined), 'Sponsored inference');
});

test('project hard-cap responses give project-level recovery guidance', () => {
  const copy = providerInterruptionCopy('project_spend_limit_exceeded', true);
  assert.deepEqual(copy, openAIProjectSpendLimitCopy());
  assert.match(copy.title, /OpenAI API project/);
  assert.match(copy.description, /API-billed model request/);
  assert.match(copy.next, /optional reference compilation or later Investigator\/Skeptic/);
  assert.match(copy.next, /active sponsored provider/);
  assert.match(copy.next, /intentionally selected/);
  assert.match(copy.next, /authorized/);
  assert.match(
    friendlyProviderError('HTTP 429 project_spend_limit_exceeded', true),
    /SIGMA allowances cannot override it/,
  );
});
