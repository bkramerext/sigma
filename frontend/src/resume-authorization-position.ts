/** Position a Resume authorization near the Play button that initiated it.
 * Accept a snapshot because the pending-resume UI unmounts that button.
 */
export type ResumeAnchorBounds = Readonly<{ top: number; bottom: number; right: number }>;

export function resumeAuthorizationPosition(
  anchor: ResumeAnchorBounds,
  panel: Readonly<{ width: number; height: number }>,
  viewport: Readonly<{ width: number; height: number }>,
): { top: number; left: number } {
  const EDGE = 12;
  const GAP = 8;
  const availableBelow = viewport.height - anchor.bottom - GAP - EDGE;
  const availableAbove = anchor.top - GAP - EDGE;
  const openBelow = availableBelow >= panel.height || availableBelow >= availableAbove;
  const preferredTop = openBelow ? anchor.bottom + GAP : anchor.top - GAP - panel.height;
  const top = Math.max(EDGE, Math.min(preferredTop, viewport.height - panel.height - EDGE));
  const left = Math.max(EDGE, Math.min(anchor.right + GAP, viewport.width - panel.width - EDGE));
  return { top, left };
}
