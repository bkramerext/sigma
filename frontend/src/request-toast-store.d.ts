export type RequestToastPhase = 'visible' | 'exiting';
export type RequestToastSeverity = 'error' | 'warning';
export type RequestToast = { id: number; message: string; phase: RequestToastPhase; severity: RequestToastSeverity };

export class RequestToastStore {
  constructor(options?: {
    setTimer?: (callback: () => void, delay: number) => ReturnType<typeof setTimeout>;
    clearTimer?: (timer: ReturnType<typeof setTimeout>) => void;
    prefersReducedMotion?: () => boolean;
    maxVisible?: number;
  });
  subscribe: (listener: () => void) => () => void;
  getSnapshot: () => RequestToast[];
  add: (message: string, severity?: RequestToastSeverity) => RequestToast;
  dismiss: (id: number) => void;
  remove: (id: number) => void;
  dispose: () => void;
}
