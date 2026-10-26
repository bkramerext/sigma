import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
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
  for (let index = 0; index < 4; index += 1) store.add(`new ${index}`);
  assert.equal(store.getSnapshot().length, 4);
  assert.equal(clock.timers.size, 4);
  store.dispose();
  assert.equal(store.getSnapshot().length, 0);
  assert.equal(clock.timers.size, 0);
});

test('exit phase slides down, stack gap collapses, and reduced-motion CSS disables motion', async () => {
  const css = await readFile(new URL('./request-toast.css', import.meta.url), 'utf8');
  assert.match(css, /\.request-toast\[data-phase="exiting"\][^{]*\{[^}]*translateY\(calc\(100% \+ 10px\)\)/s);
  assert.match(css, /\.request-toast-item\[data-phase="exiting"\][^{]*\{[^}]*grid-template-rows:\s*0fr/s);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
});
