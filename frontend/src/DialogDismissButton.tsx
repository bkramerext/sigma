import { forwardRef, type ComponentProps } from 'react';

/** Visual dialog dismissal only; callers retain their original close/cancel semantics. */
type Props = Omit<ComponentProps<'button'>, 'children' | 'title'> & { label?: string };
const DialogDismissButton = forwardRef<HTMLButtonElement, Props>(function DialogDismissButton(
  { label = 'Close dialog', className = '', ...props }, ref,
) {
  return <button {...props} ref={ref} type="button" className={`sigma-dialog-dismiss ${className}`.trim()}
    aria-label={label}>
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
      strokeWidth="4" strokeLinecap="round" aria-hidden="true"><path d="M8 8 16 16M16 8 8 16"/></svg>
  </button>;
});
export default DialogDismissButton;
