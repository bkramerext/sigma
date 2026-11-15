import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  MAX_REQUEST_TOAST_MESSAGE_LENGTH,
  REQUEST_TOAST_EXIT_MS,
  REQUEST_TOAST_LIFETIME_MS,
  RequestToastStore,
} from './request-toast-store.js';

class FakeClock {
  now = 0;
  nextId = 0;
  timers = new Map();

  setTimer = (callback, delay) => {
    const id = ++this.nextId;
    this.timers.set(id, { callback, at: this.now + delay });
    return id;
  };

  clearTimer = id => this.timers.delete(id);

  advance = milliseconds => {
    const end = this.now + milliseconds;
    while (true) {
      const next = [...this.timers.entries()]
        .filter(([, timer]) => timer.at <= end)
        .sort((left, right) => left[1].at - right[1].at || left[0] - right[0])[0];
      if (!next) break;
      const [id, timer] = next;
      this.timers.delete(id);
      this.now = timer.at;
      timer.callback();
    }
    this.now = end;
  };
}

function makeStore(clock, reducedMotion = false) {
  return new RequestToastStore({
    setTimer: clock.setTimer,
    clearTimer: clock.clearTimer,
    prefersReducedMotion: () => reducedMotion,
  });
}

test('expires exactly at 60 seconds, slides out, then cleans up', () => {
  const clock = new FakeClock();
  const store = makeStore(clock);
  const toast = store.add('first');
  clock.advance(REQUEST_TOAST_LIFETIME_MS - 1);
  assert.equal(store.getSnapshot()[0].phase, 'visible');
  clock.advance(1);
  assert.equal(store.getSnapshot()[0].phase, 'exiting');
  clock.advance(REQUEST_TOAST_EXIT_MS - 1);
  assert.equal(store.getSnapshot().length, 1);
  clock.advance(1);
  assert.equal(store.getSnapshot().length, 0);
  assert.equal(clock.timers.size, 0);
  store.dismiss(toast.id); // Late duplicate dismissals are harmless.
  assert.equal(store.getSnapshot().length, 0);
});

test('each toast keeps its own lifetime when other toasts arrive', () => {
  const clock = new FakeClock();
  const store = makeStore(clock);
  const first = store.add('first');
  clock.advance(30_000);
  const second = store.add('second');
  clock.advance(30_000);
  assert.equal(store.getSnapshot().find(item => item.id === first.id).phase, 'exiting');
  assert.equal(store.getSnapshot().find(item => item.id === second.id).phase, 'visible');
  clock.advance(REQUEST_TOAST_EXIT_MS);
  assert.deepEqual(store.getSnapshot().map(item => item.id), [second.id]);
  clock.advance(30_000 - REQUEST_TOAST_EXIT_MS);
  assert.equal(store.getSnapshot()[0].phase, 'exiting');
});

test('manual dismissal uses the exit lifecycle and clears the 60-second timer', () => {
  const clock = new FakeClock();
  const store = makeStore(clock);
  const toast = store.add('manual');
  store.dismiss(toast.id);
  assert.equal(store.getSnapshot()[0].phase, 'exiting');
  assert.equal(clock.timers.size, 1);
  clock.advance(REQUEST_TOAST_EXIT_MS);
  assert.equal(store.getSnapshot().length, 0);
  clock.advance(REQUEST_TOAST_LIFETIME_MS);
  assert.equal(store.getSnapshot().length, 0);
  assert.equal(clock.timers.size, 0);
});

test('simultaneous expirations remove each toast once and leave no timers', () => {
  const clock = new FakeClock();
  const store = makeStore(clock);
  for (let index = 0; index < 4; index += 1) store.add(`toast ${index}`);
  clock.advance(REQUEST_TOAST_LIFETIME_MS);
  assert.deepEqual(store.getSnapshot().map(item => item.phase), Array(4).fill('exiting'));
  clock.advance(REQUEST_TOAST_EXIT_MS);
  assert.equal(store.getSnapshot().length, 0);
  assert.equal(clock.timers.size, 0);
});

test('reduced motion expires immediately without scheduling an exit animation', () => {
  const clock = new FakeClock();
  const store = makeStore(clock, true);
  store.add('reduced motion');
  clock.advance(REQUEST_TOAST_LIFETIME_MS);
  assert.equal(store.getSnapshot().length, 0);
  assert.equal(clock.timers.size, 0);
});

test('dispose and burst eviction clear all timers', () => {
  const clock = new FakeClock();
  const store = makeStore(clock);
  store.add('oldest');
  for (let index = 0; index < 5; index += 1) store.add(`new ${index}`);
  assert.deepEqual(store.getSnapshot().map(item => item.message), ['new 0', 'new 1', 'new 2', 'new 3', 'new 4']);
  assert.equal(store.getSnapshot().length, 5);
  assert.equal(clock.timers.size, 5);
  store.dispose();
  assert.equal(store.getSnapshot().length, 0);
  assert.equal(clock.timers.size, 0);
});

test('adding a sixth toast immediately removes the oldest and keeps five visible', () => {
  const clock = new FakeClock();
  const store = makeStore(clock);
  const toasts = Array.from({ length: 6 }, (_, index) => store.add(`toast ${index}`));
  assert.deepEqual(store.getSnapshot().map(item => item.id), toasts.slice(1).map(item => item.id));
  assert.deepEqual(store.getSnapshot().map(item => item.message), [
    'toast 1', 'toast 2', 'toast 3', 'toast 4', 'toast 5',
  ]);
  assert.equal(clock.timers.size, 5);
  clock.advance(REQUEST_TOAST_LIFETIME_MS);
  clock.advance(REQUEST_TOAST_EXIT_MS);
  assert.equal(store.getSnapshot().length, 0);
  assert.equal(clock.timers.size, 0);
});

test('long error messages are shortened before they can fill the screen', () => {
  const clock = new FakeClock();
  const store = makeStore(clock);
  const toast = store.add('provider detail '.repeat(200));
  assert.equal(toast.message.length, MAX_REQUEST_TOAST_MESSAGE_LENGTH - 1);
  assert.ok(toast.message.endsWith('… [message shortened]'));
});

test('identical provider failures become one toast without resetting its lifetime', () => {
  const clock = new FakeClock();
  const store = makeStore(clock);
  const message = 'SIGMA-sponsored ChatGPT is temporarily unavailable. Please try again later. Saved research is unchanged.';
  const first = store.add(message);
  clock.advance(30_000);
  const duplicate = store.add(message);
  assert.equal(duplicate.id, first.id);
  assert.deepEqual(store.getSnapshot().map(item => item.id), [first.id]);
  assert.equal(clock.timers.size, 1);

  // Frequent identical polling errors do not keep the notification alive forever.
  clock.advance(29_999);
  store.add(message);
  clock.advance(1);
  assert.equal(store.getSnapshot()[0].phase, 'exiting');
  assert.equal(store.add(message).id, first.id);
  clock.advance(REQUEST_TOAST_EXIT_MS);
  assert.equal(store.getSnapshot().length, 0);
  const retry = store.add(message);
  assert.notEqual(retry.id, first.id);
  assert.equal(store.getSnapshot().length, 1);
});

test('HTTP envelopes and whitespace are coalesced with the same local error detail', () => {
  const clock = new FakeClock();
  const store = makeStore(clock);
  const detail = 'Billing is temporarily unavailable. Saved research is unchanged.';
  const fromGlobalFetch = store.add(`HTTP 503 Service Unavailable: ${detail}`);
  const fromLocalCatch = store.add(` Billing is temporarily unavailable.  Saved research is unchanged. `);
  assert.equal(fromLocalCatch.id, fromGlobalFetch.id);
  assert.equal(store.getSnapshot().length, 1);
  assert.equal(clock.timers.size, 1);

  const secondStore = makeStore(new FakeClock());
  secondStore.add(detail);
  secondStore.add(`HTTP 503: ${detail}`);
  assert.equal(secondStore.getSnapshot().length, 1);
});

test('different errors remain distinct and a new retry can report after dismissal', () => {
  const clock = new FakeClock();
  const store = makeStore(clock);
  const first = store.add('Provider is unavailable');
  const other = store.add('Payment method was rejected');
  assert.notEqual(first.id, other.id);
  assert.equal(store.getSnapshot().length, 2);

  store.dismiss(first.id);
  assert.equal(store.add('Provider is unavailable').id, first.id);
  clock.advance(REQUEST_TOAST_EXIT_MS);
  const retry = store.add('Provider is unavailable');
  assert.notEqual(retry.id, first.id);
  assert.deepEqual(store.getSnapshot().map(item => item.message), ['Payment method was rejected', 'Provider is unavailable']);
});

test('duplicate bursts do not evict unrelated errors or allocate extra timers', () => {
  const clock = new FakeClock();
  const store = makeStore(clock);
  for (let index = 0; index < 5; index += 1) store.add(`distinct error ${index}`);
  const firstIds = store.getSnapshot().map(item => item.id);
  for (let index = 0; index < 20; index += 1) store.add('distinct error 2');
  assert.deepEqual(store.getSnapshot().map(item => item.id), firstIds);
  assert.equal(clock.timers.size, 5);
});

test('exit phase slides down, stack gap collapses, and reduced-motion CSS disables motion', async () => {
  const css = await readFile(new URL('./request-toast.css', import.meta.url), 'utf8');
  assert.match(css, /\.request-toast\[data-phase="exiting"\][^{]*\{[^}]*translateY\(calc\(100% \+ 10px\)\)/s);
  assert.match(css, /\.request-toast-item\[data-phase="exiting"\][^{]*\{[^}]*grid-template-rows:\s*0fr/s);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /max-height:\s*min\(70vh,\s*560px\)/);
  assert.match(css, /max-height:\s*min\(60vh,\s*480px\)/);
});
