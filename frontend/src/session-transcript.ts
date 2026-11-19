/** Readable view of the existing Session log, not a second authoritative record. */
export type TranscriptRole = 'investigator' | 'skeptic' | 'human' | 'supervisor' | 'other';
export type TranscriptEvent = {
  seq: number; timestamp: string; type: string; request_id?: string;
  role?: string; round?: number; strategy_id?: string; step_id?: string;
  event_kind?: string; message?: string; response?: unknown; provider_error?: unknown;
  request?: unknown; status?: string; [key: string]: unknown;
};
export type TranscriptIntervention = {
  id: string; text: string; kind: string; submitted_at: string;
  target_strategy_ids?: string[]; target_roles?: string[];
};
export type TranscriptEntry = {
  id: string; timestamp: string; role: TranscriptRole; title: string;
  text: string; round?: number; strategyId?: string; sequence: number;
  request?: unknown; response?: unknown; pending?: boolean;
};
function responseText(value: unknown): string {
  if (typeof value === 'string') {
    try {
      const parsed: unknown = JSON.parse(value);
      if (parsed && typeof parsed === 'object') return responseText(parsed);
    } catch { /* Provider-authored text is not necessarily JSON. */ }
    return value;
  }
  if (Array.isArray(value)) return value.map(responseText).filter(Boolean).join('\n\n');
  if (!value || typeof value !== 'object') return '';
  const obj = value as Record<string, unknown>;
  if (Array.isArray(obj.output)) {
    const parts = obj.output.flatMap(item => {
      if (!item || typeof item !== 'object') return [];
      const contents = (item as Record<string, unknown>).content;
      return Array.isArray(contents)
        ? contents.filter(x => x && typeof x === 'object' && typeof (x as Record<string, unknown>).text === 'string')
          .map(x => String((x as Record<string, unknown>).text))
        : [];
    });
    if (parts.length) return parts.join('\n\n');
  }
  if (typeof obj.output_text === 'string') return obj.output_text;
  if (Array.isArray(obj.choices)) {
    const parts = obj.choices.map(choice => {
      if (!choice || typeof choice !== 'object') return '';
      const c = choice as Record<string, unknown>;
      const message = c.message ?? c.delta;
      return message && typeof message === 'object'
        ? String((message as Record<string, unknown>).content ?? '') : '';
    }).filter(Boolean);
    if (parts.length) return parts.join('\n\n');
  }
  if (typeof obj.content === 'string') return obj.content;
  return '';
}
export function readableTranscriptResponse(value: unknown): string {
  const raw = responseText(value);
  if (!raw) return '';
  let parsed: unknown;
  try { parsed = JSON.parse(raw); } catch { return raw; }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return raw;
  return Object.entries(parsed as Record<string, unknown>).map(([key, value]) => {
    const label = key.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
    const body = typeof value === 'string' ? value
      : Array.isArray(value) && value.every(x => typeof x === 'string' || typeof x === 'number')
        ? value.map(x => '- ' + String(x)).join('\n')
        : typeof value === 'object' && value !== null
          ? JSON.stringify(value, null, 2)
          : String(value);
    return '#### ' + label + '\n\n' + body;
  }).join('\n\n');
}
function roleOf(value: unknown): TranscriptRole {
  const role = typeof value === 'string' ? value.toLowerCase() : '';
  return role === 'investigator' || role === 'skeptic' || role === 'supervisor' ? role : 'other';
}
export const transcriptCategories: { value: TranscriptRole; label: string }[] = [
  { value: 'investigator', label: 'Investigator' },
  { value: 'skeptic', label: 'Skeptic' },
  { value: 'human', label: 'Human' },
  { value: 'supervisor', label: 'Supervisor' },
  { value: 'other', label: 'Other' },
];
export function projectTranscript(events: TranscriptEvent[], interventions: TranscriptIntervention[] = []): TranscriptEntry[] {
  const requests = new Map<string, TranscriptEvent>();
  const responses = new Map<string, TranscriptEvent>();
  for (const event of events) {
    if (event.type === 'provider_request' && event.request_id) requests.set(event.request_id, event);
    if ((event.type === 'provider_response' || event.type === 'provider_failure') && event.request_id)
      responses.set(event.request_id, event);
  }
  const entries: TranscriptEntry[] = [];
  for (const event of events) {
    if (event.type === 'provider_request' && event.request_id && responses.has(event.request_id)) continue;
    if (event.type === 'provider_response' || event.type === 'provider_failure') {
      const request = event.request_id ? requests.get(event.request_id) : undefined;
      const role = roleOf(request?.role ?? event.role);
      const text = event.type === 'provider_failure'
        ? String(event.provider_error ?? event.message ?? 'Provider call failed.')
        : readableTranscriptResponse(event.response);
      entries.push({
        id: 'response-' + (event.request_id ?? event.seq), timestamp: event.timestamp, role,
        title: event.type === 'provider_failure' ? 'Provider failure' : (role === 'other' ? 'Provider response' : role[0].toUpperCase() + role.slice(1)),
        text: text || 'The response text was not retained in this historical log.',
        round: request?.round ?? event.round, strategyId: request?.strategy_id ?? event.strategy_id,
        sequence: event.seq, request: request?.request, response: event.response,
      });
      continue;
    }
    if (event.type === 'provider_request') {
      entries.push({
        id: 'pending-' + (event.request_id ?? event.seq), timestamp: event.timestamp,
        role: roleOf(event.role), title: 'Provider request', text: 'Awaiting response…',
        round: event.round, strategyId: event.strategy_id, sequence: event.seq,
        request: event.request, pending: true,
      });
      continue;
    }
    // Display the complete human text from the saved Session, not this short event.
    if (event.type === 'session_event' && event.event_kind === 'intervention.accepted') continue;
    entries.push({
      id: 'event-' + event.seq, timestamp: event.timestamp,
      role: roleOf(event.role), title: String(event.event_kind ?? event.type).replaceAll('_', ' '),
      text: String(event.message ?? event.status ?? ''), round: event.round,
      strategyId: event.strategy_id, sequence: event.seq,
    });
  }
  interventions.forEach((intervention, index) => {
    if (!intervention.id || !intervention.submitted_at) return;
    entries.push({
      id: 'human-' + intervention.id, timestamp: intervention.submitted_at, role: 'human',
      title: 'Human · ' + intervention.kind, text: intervention.text,
      sequence: events.length + index + 1,
      strategyId: intervention.target_strategy_ids?.length === 1 ? intervention.target_strategy_ids[0] : undefined,
    });
  });
  return entries.sort((left, right) => left.timestamp.localeCompare(right.timestamp)
    || left.sequence - right.sequence || left.id.localeCompare(right.id));
}

/** Only accepted saved research or supervisor text should incur AI formatting calls. */
export function convertibleTranscriptEntry(entry: TranscriptEntry): boolean {
  return !entry.pending &&
    entry.title !== 'Provider failure' &&
    entry.text.length >= 40 && entry.text.length <= 20000 &&
    (entry.id.startsWith('response-') || (entry.role === 'supervisor' && entry.id.startsWith('event-'))) &&
    entry.text !== 'The response text was not retained in this historical log.';
}

/** Brainstorm's canonical disclosure state: only Supervisor guidance starts open. */
export function transcriptDefaultExpanded(entry: Pick<TranscriptEntry, 'role'>): boolean {
  return entry.role === 'supervisor';
}

export type TranscriptTurnGroup = {
  key: string; label: string; latestTimestamp: string; entries: TranscriptEntry[];
};

/** Group flat, durable paired-slot events by turn and show newest turns first.
 * Concurrent strategies retain their own turn identities; within a turn the
 * Investigator and Skeptic messages remain chronologically ordered.
 */
export function groupTranscriptTurns(entries: TranscriptEntry[]): TranscriptTurnGroup[] {
  const groups = new Map<string, TranscriptTurnGroup>();
  // Only attach a Human entry to a prior turn when its explicitly targeted
  // strategy identifies that turn. Never infer an arbitrary concurrent branch.
  const latestTurnByStrategy = new Map<string, string>();
  for (const entry of [...entries].sort((a, b) => a.timestamp.localeCompare(b.timestamp)
    || a.sequence - b.sequence)) {
    const hasTurn = typeof entry.round === 'number' && entry.round > 0;
    const turnKey = hasTurn ? `${entry.strategyId ?? 'session'}:${entry.round}` : null;
    const humanTurn = entry.role === 'human' && entry.strategyId
      ? latestTurnByStrategy.get(entry.strategyId) : undefined;
    const key = turnKey ?? humanTurn ?? `event:${entry.id}`;
    if (turnKey && entry.strategyId) latestTurnByStrategy.set(entry.strategyId, turnKey);
    const label = turnKey ? `Turn ${entry.round}`
      : humanTurn ? groups.get(humanTurn)?.label ?? 'Human' 
      : entry.role === 'human' ? 'Human' : 'Session activity';
    const existing = groups.get(key);
    if (existing) {
      existing.entries.push(entry);
      if (entry.timestamp > existing.latestTimestamp) existing.latestTimestamp = entry.timestamp;
    } else {
      groups.set(key, { key, label, latestTimestamp: entry.timestamp, entries: [entry] });
    }
  }
  return [...groups.values()].sort((a, b) => b.latestTimestamp.localeCompare(a.latestTimestamp)
    || b.key.localeCompare(a.key));
}
