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
  // Older API fixtures omit this field and retain the prior ChatGPT label.
  assert.equal(sponsoredProviderLabel(undefined), 'Sponsored ChatGPT');
});

test('project hard-cap responses give project-level recovery guidance', () => {
  const copy = providerInterruptionCopy('project_spend_limit_exceeded', true);
  assert.deepEqual(copy, openAIProjectSpendLimitCopy());
  assert.match(copy.title, /OpenAI API project/);
  assert.match(copy.next, /Monthly spend limit/);
  assert.match(copy.next, /Enforce a hard limit/);
  assert.match(copy.next, /authorized/);
  assert.doesNotMatch(copy.next, /few hours/);
  assert.match(
    friendlyProviderError('HTTP 429 project_spend_limit_exceeded', true),
    /SIGMA usage allowances do not override the API project hard limit/,
  );
});
