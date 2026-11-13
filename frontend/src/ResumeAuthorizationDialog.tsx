import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import DialogDismissButton from './DialogDismissButton';
import './resume-authorization.css';

export type ResumeAuthorization = {
  kind: 'attempts' | 'duration';
  count: number;
  sessionNumber: number;
};

const EDGE = 12;
const GAP = 8;

function anchoredPosition(anchor: HTMLElement, panel: HTMLElement): { top: number; left: number } {
  const rect = anchor.getBoundingClientRect();
  const width = panel.offsetWidth;
  const height = panel.offsetHeight;
  const availableBelow = window.innerHeight - rect.bottom - GAP - EDGE;
  const availableAbove = rect.top - GAP - EDGE;
  const openBelow = availableBelow >= height || availableBelow >= availableAbove;
  const preferredTop = openBelow ? rect.bottom + GAP : rect.top - GAP - height;
  const top = Math.max(EDGE, Math.min(preferredTop, window.innerHeight - height - EDGE));
  // Prefer the right side of Play, but keep the entire popup in the viewport.
  const left = Math.max(EDGE, Math.min(rect.right + GAP, window.innerWidth - width - EDGE));
  return { top, left };
}

/** Nonmodal confirmation matches SIGMA's anchored remove confirmations. */
export default function ResumeAuthorizationDialog({ request, anchor, onAuthorize, onCancel }: {
  request: ResumeAuthorization | null;
  anchor: HTMLButtonElement | null;
  onAuthorize: () => void;
  onCancel: () => void;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);
  const cancelAction = useRef(onCancel);
  cancelAction.current = onCancel;
  const [position, setPosition] = useState({ top: 0, left: 0, ready: false });

  useLayoutEffect(() => {
    if (!request || !anchor || !panel.current) return;
    const update = () => {
      if (!panel.current) return;
      setPosition({ ...anchoredPosition(anchor, panel.current), ready: true });
    };
    update();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [request, anchor]);

  useEffect(() => {
    if (!request) return;
    cancelButton.current?.focus({ preventScroll: true });
    const onPointerDown = (event: PointerEvent) => {
      if (panel.current && !panel.current.contains(event.target as Node)) cancelAction.current();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        cancelAction.current();
      }
    };
    document.addEventListener('pointerdown', onPointerDown, true);
    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown, true);
      document.removeEventListener('keydown', onKeyDown, true);
      if (anchor?.isConnected && !anchor.disabled) anchor.focus({ preventScroll: true });
    };
  }, [request, anchor]);

  if (!request) return null;
  return createPortal(
    <div ref={panel} className="resume-authorization-popover" role="dialog"
      aria-labelledby="resume-authorization-title" aria-describedby="resume-authorization-message"
      style={{ top: position.top, left: position.left, visibility: position.ready ? 'visible' : 'hidden' }}>
      <h3 id="resume-authorization-title">Resume Session {request.sessionNumber}</h3>
      <div id="resume-authorization-message">
        {request.kind === 'attempts' ? <>
          <p>Authorize {request.count} additional provider attempt{request.count === 1 ? '' : 's'} (may use more allowance)?</p>
        </> : <>
          <p>Authorize up to {request.count} more minutes of research?</p>
        </>}
      </div>
      <div className="resume-authorization-actions">
        <button type="button" onClick={onAuthorize}>Confirm</button>
        <DialogDismissButton ref={cancelButton} label="Cancel session resumption" onClick={onCancel}/>
      </div>
    </div>,
    document.body,
  );
}
