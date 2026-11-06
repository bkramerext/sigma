/**
 * One presentation policy for research, papers, Markdown conversion, and the
 * global request toast. Keep raw provider details in saved logs/diagnostics.
 */
let sponsoredConnection = false;

export function setSponsoredUsageConnection(sponsored: boolean): void {
  sponsoredConnection = sponsored;
}

export function currentSponsoredUsageConnection(): boolean {
  return sponsoredConnection;
}

export function isProviderUsageLimit(message: string): boolean {
  return /subscription_sharing_usage_limit_exceeded|(?:ChatGPT|(?:AI )?provider|OpenAI)[^\n]{0,90}(?:account|app|shared)?\s*usage limit\s*(?:reached|exceeded)|(?:provider|ChatGPT) allowance (?:is )?(?:exhausted|depleted)/i.test(message);
}

export function providerUsageLimitCopy(sponsored = sponsoredConnection, chatgpt = true): {
  title: string; description: string; next: string;
} {
  if (sponsored) return {
    title: 'Sponsored ChatGPT usage limit reached',
    description: 'The sponsored ChatGPT account has run out of allowance. Your saved work is intact.',
    next: 'Try again in a few hours.',
  };
  if (chatgpt) return {
    title: 'ChatGPT usage limit reached',
    description: 'Your saved work is intact. Check ChatGPT → Settings → Usage to see when your allowance resets.',
    next: 'Try again when usage is available.',
  };
  return {
    title: 'AI provider usage limit reached',
    description: 'The AI provider has reached its allowance. Your saved work is intact.',
    next: 'Check your provider usage and retry when allowance is available.',
  };
}

export function friendlyProviderUsageError(message: string, sponsored = sponsoredConnection): string {
  if (!isProviderUsageLimit(message)) return message;
  const copy = providerUsageLimitCopy(sponsored);
  return `${copy.title}. ${copy.description} ${copy.next}`;
}

export function isSponsoredChatGPTUnavailable(message: string): boolean {
  return /(?:SIGMA[- ]sponsored|sponsored) ChatGPT (?:is )?temporarily unavailable/i.test(message);
}

export function providerInterruptionCopy(
  message: string, sponsored = sponsoredConnection,
): { title: string; description: string; next: string } | null {
  if (isProviderUsageLimit(message)) return providerUsageLimitCopy(sponsored);
  if (isSponsoredChatGPTUnavailable(message)) return {
    title: 'Sponsored ChatGPT unavailable',
    description: 'The sponsored ChatGPT connection is temporarily unavailable. Saved work is unchanged.',
    next: 'Try again in a few hours.',
  };
  return null;
}

export function friendlyProviderError(message: string, sponsored = sponsoredConnection): string {
  const copy = providerInterruptionCopy(message, sponsored);
  return copy ? `${copy.description} ${copy.next}` : message;
}
