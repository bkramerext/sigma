/**
 * One presentation policy for research, papers, Markdown conversion, and the
 * global request toast. Keep raw provider details in saved logs/diagnostics.
 */
let sponsoredConnection = false;

export type SponsoredInferenceProvider = 'chatgpt' | 'api_key';

export function sponsoredProviderLabel(provider: SponsoredInferenceProvider | undefined): string {
  if (provider === 'api_key') return 'Sponsored OpenAI API';
  if (provider === 'chatgpt') return 'Sponsored ChatGPT';
  return 'Sponsored inference';
}

export function openAIProjectSpendLimitCopy(): {
  title: string; description: string; next: string;
} {
  return {
    title: 'OpenAI API project spending limit reached',
    description: 'OpenAI rejected an API-billed model request with project_spend_limit_exceeded (HTTP 429). This is the provider project hard limit; SIGMA allowances cannot override it. Saved research is intact.',
    next: 'The rejected request may have occurred during optional reference compilation or later Investigator/Skeptic work. Check the active sponsored provider and fix its routing before resuming. If API-key billing is intentionally selected, an authorized project owner can review Organization settings → the project used by SIGMA → Limits. Do not raise or disable a provider limit unless that billing change is authorized.',
  };
}

export function isOpenAIProjectSpendLimit(message: string): boolean {
  return /project_spend_limit_exceeded|provider_spend_limit_exceeded|insufficient_quota|billing_hard_limit_reached|billing_not_active/.test(message);
}

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
  if (isOpenAIProjectSpendLimit(message)) return openAIProjectSpendLimitCopy();
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
