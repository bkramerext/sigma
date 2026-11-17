/** PDF compilation is local deterministic work. A failed TeX compiler must
 * never imply that another provider call or paid authoring might be needed.
 */
export function paperGenerationFailureNotice(
  message: string,
  options: { disconnected: boolean; requestDispatched: boolean; providerCallsAttempted?: number },
): string {
  const { disconnected, requestDispatched, providerCallsAttempted } = options;
  if (disconnected && requestDispatched)
    return 'Connection interrupted. This paper may still be generating; check its status before trying again.';
  if (/^(?:PDF compilation failed|The safe visual fallback could not compile|The compiled PDF failed its output validity check)/i.test(message))
    return message;
  if (requestDispatched && providerCallsAttempted === 0)
    return `${message} No provider request was made for this attempt. Paper versions and research evidence are unchanged; refresh the snapshot before retrying.`;
  if (requestDispatched)
    return `${message} Check My Work versions and your provider usage before generating again; a provider request may have completed or consumed allowance before the error.`;
  return message;
}
