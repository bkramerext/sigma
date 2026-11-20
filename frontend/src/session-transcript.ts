/** Readable view of the existing Session log, not a second authoritative record. */
export type TranscriptRole = 'investigator' | 'skeptic' | 'human' | 'supervisor' | 'other';
export type TranscriptEvent = {
  seq: number; timestamp: string; type: string; request_id?: string;
  role?: string; round?: number; strategy_id?: string; step_id?: string;
  event_kind?: string; message?: string; response?: unknown; provider_error?: unknown;
  request?: unknown; brainstorm_mode?: boolean; status?: string; [key: string]: unknown;
};
/** Session wire roles remain unchanged; Brainstorm only changes the displayed title. */
export function transcriptRoleLabel(role: TranscriptRole, brainstormMode: boolean): string {
  if (role === 'investigator') return 'Investigator';
  if (role === 'skeptic') return brainstormMode ? 'Investigator' : 'Skeptic';
  if (role === 'supervisor') return 'Supervisor';
  if (role === 'human') return 'Human';
  return '';
}

export type TranscriptIntervention = {
  id: string; text: string; kind: string; submitted_at: string;
  target_strategy_ids?: string[]; target_roles?: string[];
};
export type TranscriptEntry = {
  id: string; timestamp: string; role: TranscriptRole; title: string;
  text: string; round?: number; strategyId?: string; sequence: number;
  request?: unknown; response?: unknown; pending?: boolean; brainstormMode?: boolean;
};
/** Strip the scored metadata from the rendered assessment while retaining the
 * saved text unmodified for Copy and Download. Old four-score reviews continue
 * to display correctly when Originality was not yet recorded. */
export type SupervisorScores = {
  alignment: string; originality?: string; advancement: string; evidence: string; health: string;
};
export function supervisorDisplay(text: string): { body: string; scores?: SupervisorScores } {
  const pattern = /\r?\n\r?\nObjective alignment:\s*(\d+(?:\.\d+)?)\/10(?:\.0)?\r?\n(?:Originality:\s*(\d+(?:\.\d+)?)\/10(?:\.0)?\r?\n)?Substantive advancement:\s*(\d+(?:\.\d+)?)\/10(?:\.0)?\r?\nEvidence & validation:\s*(\d+(?:\.\d+)?)\/10(?:\.0)?\r?\nResearch health:\s*(\d+(?:\.\d+)?)\/10(?:\.0)?(?=\s|$)/;
  const match = pattern.exec(text);
  if (!match) return { body: text };
  return {
    body: text.slice(0, match.index) + text.slice(match.index + match[0].length),
    scores: {
      alignment: match[1], ...(match[2] === undefined ? {} : { originality: match[2] }),
      advancement: match[3], evidence: match[4], health: match[5],
    },
  };
}

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
/** Presentation-only: fence nested JSON and inline-code artifact IDs. */
export function formatTranscriptMarkdown(markdown: string): string {
  const lines = markdown.split('\n');
  const result: string[] = [];
  let fence: string | null = null;
  const guid = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const boundary = line.match(/^\s*(```+|~{3,})/);
    if (boundary) {
      if (fence === null) fence = boundary[1][0];
      else if (fence === boundary[1][0]) fence = null;
      result.push(line); continue;
    }
    if (fence !== null) { result.push(line); continue; }
    if (/^\s*[\[{]\s*$/.test(line)) {
      let candidate = '';
      let end = i;
      for (; end < Math.min(lines.length, i + 500); end++) {
        candidate += (end === i ? '' : '\n') + lines[end];
        if (!/^\s*[\]}]\s*$/.test(lines[end])) continue;
        try {
          const parsed: unknown = JSON.parse(candidate);
          if (parsed !== null && typeof parsed === 'object') break;
        } catch { /* Incomplete JSON: continue searching. */ }
      }
      if (end < lines.length && end < i + 500) {
        result.push('```json', ...lines.slice(i, end + 1), '```');
        i = end; continue;
      }
    }
    // Protect existing inline code and keep GUIDs in prose unchanged.
    result.push(line.split(/(`+[^`]*`+)/g).map(part =>
      part.startsWith('`') ? part : part.replace(guid, id => '`' + id + '`')
    ).join(''));
  }
  return result.join('\n');
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
/** Dispatch-time configuration is authoritative. Historical requests predate the
 * explicit mode field, but retain the exact prompt sent to the provider. */
function brainstormAtDispatch(event: TranscriptEvent | undefined): boolean {
  if (!event) return false;
  if (typeof event.brainstorm_mode === 'boolean') return event.brainstorm_mode;
  // Legacy provider requests have no mode flag; detect the exact established
  // instructions marker instead of using today's mutable Session settings.
  return event.request !== undefined &&
    JSON.stringify(event.request).includes('BRAINSTORM MODE: You and your peer are two co-investigators.');
}
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
        brainstormMode: brainstormAtDispatch(request ?? event),
      });
      continue;
    }
    if (event.type === 'provider_request') {
      entries.push({
        id: 'pending-' + (event.request_id ?? event.seq), timestamp: event.timestamp,
        role: roleOf(event.role), title: 'Provider request', text: 'Awaiting response…',
        round: event.round, strategyId: event.strategy_id, sequence: event.seq,
        request: event.request, pending: true,
        brainstormMode: brainstormAtDispatch(event),
      });
      continue;
    }
    // Lifecycle/validation/step events are audit metadata, not agent replies.
    // They often carry investigator/skeptic roles and previously appeared as
    // repeated AI #1 / AI #2 cards within the same turn.
    // Keep the actual Supervisor assessment, not its completion status event.
    if (event.type === 'session_event' && event.event_kind === 'supervisor.review'
      && roleOf(event.role) === 'supervisor') {
      entries.push({
        id: 'event-' + event.seq, timestamp: event.timestamp,
        role: 'supervisor', title: 'Supervisor',
        text: String(event.message ?? ''), round: event.round,
        strategyId: event.strategy_id, sequence: event.seq,
      });
    }
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
  // A turn has one accepted reply per agent. Retry/failed attempts remain in
  // the complete saved log, while the reading view prefers the last successful
  // response (or the last interrupted attempt if no reply completed).
  const bySlot = new Map<string, TranscriptEntry>();
  const unpaired: TranscriptEntry[] = [];
  for (const entry of entries) {
    if (!['investigator', 'skeptic'].includes(entry.role)
      || !entry.strategyId || !entry.round || entry.round < 1) {
      unpaired.push(entry);
      continue;
    }
    const slot = `${entry.strategyId}:${entry.round}:${entry.role}`;
    const earlier = bySlot.get(slot);
    const successful = (value: TranscriptEntry) =>
      value.id.startsWith('response-') && value.title !== 'Provider failure';
    if (!earlier || (successful(entry) && !successful(earlier))
      || (successful(entry) === successful(earlier) && entry.sequence > earlier.sequence))
      bySlot.set(slot, entry);
  }
  return [...unpaired, ...bySlot.values()].sort((left, right) =>
    left.timestamp.localeCompare(right.timestamp)
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

/** Paginate by the actual turn number, keeping all concurrent strategies for
 * a turn on the same page. Non-turn entries each occupy one pagination slot. */
export function paginateTranscriptTurns(groups: TranscriptTurnGroup[], limit: number): {
  shownGroups: TranscriptTurnGroup[]; remainingTurns: number;
} {
  const key = (group: TranscriptTurnGroup): string => {
    const number = group.entries.find(entry =>
      typeof entry.round === 'number' && Number.isInteger(entry.round) && entry.round > 0)?.round;
    return number === undefined ? `event:${group.key}` : `turn:${number}`;
  };
  const keys = [...new Set(groups.map(key))];
  const shown = new Set(keys.slice(0, limit));
  return { shownGroups: groups.filter(group => shown.has(key(group))),
    remainingTurns: keys.length - shown.size };
}

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
  return [...groups.values()].sort((a, b) => {
    // Newest turn first; within each turn, display strategies in ascending
    // order rather than ordering concurrent work by completion timestamp.
    const aTurn = a.entries.find(entry => entry.round)?.round;
    const bTurn = b.entries.find(entry => entry.round)?.round;
    if (aTurn !== undefined && bTurn !== undefined && aTurn !== bTurn)
      return bTurn - aTurn;
    const aStrategy = a.entries.find(entry => entry.strategyId)?.strategyId;
    const bStrategy = b.entries.find(entry => entry.strategyId)?.strategyId;
    if (aTurn !== undefined && bTurn !== undefined && aStrategy && bStrategy && aStrategy !== bStrategy)
      return aStrategy.localeCompare(bStrategy, undefined, { numeric: true });
    return b.latestTimestamp.localeCompare(a.latestTimestamp) || b.key.localeCompare(a.key);
  });
}
