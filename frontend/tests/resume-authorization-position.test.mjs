import assert from 'node:assert/strict';
import test from 'node:test';
import { resumeAuthorizationAnchor, resumeAuthorizationPosition } from '../src/resume-authorization-position.ts';

test('Resume confirmation stays by the clicked Play location even after Play unmounts', () => {
  // Captured before clicking Play. The real element is no longer in the DOM
  // when asynchronous recovery preflight asks for additional authorization.
  const originalPlay = { top: 225, bottom: 249, right: 730 };
  const detachedPlay = {
    isConnected: false,
    getBoundingClientRect: () => ({ top: 0, bottom: 0, right: 0 }),
  };
  const bounds = resumeAuthorizationAnchor(detachedPlay, originalPlay);
  assert.deepEqual(bounds, originalPlay);
  const position = resumeAuthorizationPosition(bounds,
    { width: 320, height: 120 }, { width: 1440, height: 900 });
  assert.deepEqual(position, { top: 257, left: 738 });
  assert.notDeepEqual(position, { top: 12, left: 12 });
});

test('Resume confirmation remains in viewport near a bottom-right Play button', () => {
  const position = resumeAuthorizationPosition(
    { top: 720, bottom: 744, right: 1130 },
    { width: 320, height: 160 },
    { width: 1200, height: 800 },
  );
  assert.deepEqual(position, { top: 552, left: 868 });
});

test('connected Play tracks its current location instead of stale bounds', () => {
  const live = { top: 350, bottom: 374, right: 610 };
  assert.deepEqual(resumeAuthorizationAnchor(
    { isConnected: true, getBoundingClientRect: () => live },
    { top: 250, bottom: 274, right: 610 },
  ), live);
});
