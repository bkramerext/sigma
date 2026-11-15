export type RequestToastPhase = 'visible' | 'exiting';
export type RequestToast = { id: number; message: string; phase: RequestToastPhase };

export class RequestToastStore {
  constructor(options?: {
    setTimer?: (callback: () => void, delay: number) => ReturnType<typeof setTimeout>;
    clearTimer?: (timer: ReturnType<typeof setTimeout>) => void;
    prefersReducedMotion?: () => boolean;
    maxVisible?: number;
  });
  subscribe: (listener: () => void) => () => void;
  getSnapshot: () => RequestToast[];
  add: (message: string) => RequestToast;
  dismiss: (id: number) => void;
  remove: (id: number) => void;
  dispose: () => void;
}
