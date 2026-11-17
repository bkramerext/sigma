import assert from 'node:assert/strict';
import test from 'node:test';
import { paperGenerationFailureNotice } from '../src/paper-generation-error.ts';

test('PDF compilation failure has no provider-warning suffix', () => {
  const message = 'PDF compilation failed (unclassified Tectonic error (exit 1) near TeX line 63). The paper draft is preserved; use Resume to retry without rewriting it.';
  assert.equal(paperGenerationFailureNotice(message, {
    disconnected: false, requestDispatched: true, providerCallsAttempted: 5,
  }), message);
});

test('safe visual fallback failure also stays specific to local PDF work', () => {
  const message = 'The safe visual fallback could not compile; the authored TeX remains available.';
  assert.equal(paperGenerationFailureNotice(message, {
    disconnected: false, requestDispatched: true, providerCallsAttempted: 2,
  }), message);
});

test('uncertain provider failures still retain their existing guidance', () => {
  const value = paperGenerationFailureNotice('ChatGPT response failed.', {
    disconnected: false, requestDispatched: true, providerCallsAttempted: 1,
  });
  assert.match(value, /Check My Work versions and your provider usage/);
});

test('transport disconnect still reports uncertainty', () => {
  const value = paperGenerationFailureNotice('Transport ended.', {
    disconnected: true, requestDispatched: true,
  });
  assert.match(value, /^Connection interrupted/);
});
