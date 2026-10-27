export const REQUEST_TOAST_LIFETIME_MS = 60_000;
export const REQUEST_TOAST_EXIT_MS = 960;

export class RequestToastStore {
  constructor({
    setTimer = globalThis.setTimeout.bind(globalThis),
    clearTimer = globalThis.clearTimeout.bind(globalThis),
    prefersReducedMotion = () => globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
    maxVisible = 5,
  } = {}) {
    this.setTimer = setTimer;
    this.clearTimer = clearTimer;
    this.prefersReducedMotion = prefersReducedMotion;
    this.maxVisible = maxVisible;
    this.nextId = 0;
    this.failures = [];
    this.listeners = new Set();
    this.timers = new Map();
    this.subscribe = listener => {
      this.listeners.add(listener);
      return () => this.listeners.delete(listener);
    };
    this.getSnapshot = () => this.failures;
  }

  add(message) {
    const failure = { id: ++this.nextId, message, phase: 'visible' };
    const overflow = this.failures.slice(0, Math.max(0, this.failures.length + 1 - this.maxVisible));
    for (const old of overflow) this.clearTimers(old.id);
    this.failures = [...this.failures.slice(overflow.length), failure];
    this.notify();
    this.timers.set(failure.id, {
      expiry: this.setTimer(() => this.dismiss(failure.id), REQUEST_TOAST_LIFETIME_MS),
      exit: null,
    });
    return failure;
  }

  dismiss(id) {
    const failure = this.failures.find(item => item.id === id);
    if (!failure || failure.phase === 'exiting') return;
    const timers = this.timers.get(id);
    if (timers?.expiry !== null && timers?.expiry !== undefined) {
      this.clearTimer(timers.expiry);
      timers.expiry = null;
    }
    if (this.prefersReducedMotion()) {
      this.remove(id);
      return;
    }
    this.failures = this.failures.map(item => item.id === id ? { ...item, phase: 'exiting' } : item);
    this.notify();
    if (timers) {
      timers.exit = this.setTimer(() => this.remove(id), REQUEST_TOAST_EXIT_MS);
    }
  }

  remove(id) {
    if (!this.failures.some(item => item.id === id)) return;
    this.clearTimers(id);
    this.failures = this.failures.filter(item => item.id !== id);
    this.notify();
  }

  dispose() {
    for (const id of this.timers.keys()) this.clearTimers(id);
    this.failures = [];
    this.notify();
  }

  clearTimers(id) {
    const timers = this.timers.get(id);
    if (!timers) return;
    if (timers.expiry !== null) this.clearTimer(timers.expiry);
    if (timers.exit !== null) this.clearTimer(timers.exit);
    this.timers.delete(id);
  }

  notify() {
    for (const listener of this.listeners) listener();
  }
}
