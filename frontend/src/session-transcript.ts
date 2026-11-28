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
  if (role === 'investigator') return brainstormMode ? 'Co-investigator' : 'Investigator';
  if (role === 'skeptic') return brainstormMode ? 'Co-investigator' : 'Skeptic';
  if (role === 'supervisor') return 'Supervisor';
  if (role === 'human') return 'Human';
  return '';
}

export type TranscriptIntervention = {
  id: string; text: string; kind: string; submitted_at: string;
  target_strategy_ids?: string[]; target_roles?: string[];
};
/** A read-only projection of the existing persisted step/review, not a raw event. */
export type TranscriptSavedStep = {
  step_id: string; role: string; status: string; strategy_id?: string; round?: number;
  request_id?: string; started_at?: string; finished_at?: string; text?: string;
  content_digest?: string | null;
  attempt_status?: string; failure_kind?: string; interruption_reason?: string;
  incomplete_reason?: string; reason?: string; partial_text?: string; brainstorm_mode?: boolean;
};
/** Disposable server evidence, separate from retained raw events. */
export type TranscriptResponseEvidence = Record<string, { text: string; content_digest: string | null; conversion_digest?: string | null }>;
export type TranscriptEntry = {
  id: string; timestamp: string; role: TranscriptRole; title: string;
  text: string; round?: number; strategyId?: string; sequence: number;
  request?: unknown; response?: unknown; pending?: boolean; brainstormMode?: boolean;
  reconstructed?: boolean; historyNotice?: boolean; correlationUnknown?: boolean;
  claimedAttribution?: string; requestTimestamp?: string; requestSequence?: number;
  conversionDigest?: string;
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
      if (parsed && typeof parsed === 'object') return responseText(parsed) || value;
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
function savedStepMessage(step: TranscriptSavedStep): string {
  if (step.status === 'completed') return step.text || 'Saved completion has no retained response text.';
  const details = [step.attempt_status, step.failure_kind, step.interruption_reason,
    step.incomplete_reason, step.reason].filter(Boolean);
  return `Saved step status: ${step.status}.` + (details.length ? ' ' + details.join('; ') + '.' : '')
    + (step.partial_text ? '\n\nSaved partial output (not accepted):\n\n' + step.partial_text : '');
}

/** Missing timestamps are not chronological evidence; place them last. */
function transcriptOrder(left: TranscriptEntry, right: TranscriptEntry): number {
  return Number(!left.timestamp) - Number(!right.timestamp)
    || left.timestamp.localeCompare(right.timestamp)
    || left.sequence - right.sequence || left.id.localeCompare(right.id);
}

function consistentAttribution(left: TranscriptEvent, right: TranscriptEvent): boolean {
  return (['step_id', 'role', 'strategy_id', 'round'] as const).every(field =>
    left[field] == null || right[field] == null || left[field] === right[field]);
}

function claimedAttribution(event: TranscriptEvent, request?: TranscriptEvent): string {
  const describe = (row: TranscriptEvent) => [
    row.strategy_id ? 'strategy ' + row.strategy_id : '',
    row.round != null ? 'turn ' + row.round : '',
    row.step_id ? 'step ' + row.step_id : '',
    row.request_id ? 'request ' + row.request_id : '',
  ].filter(Boolean).join(', ');
  const own = describe(event);
  const paired = request ? describe(request) : '';
  return [own, paired && paired !== own ? 'request claims ' + paired : ''].filter(Boolean).join('; ');
}

function reviewKey(strategy: string | undefined, turn: number | undefined, message: string): string {
  return JSON.stringify([strategy ?? null, turn ?? null, message]);
}

/** Keep raw attempts and authoritative saved results distinct. A logical step
 * ID alone cannot prove which provider invocation produced accepted content. */
export function projectTranscript(
  events: TranscriptEvent[], interventions: TranscriptIntervention[] = [],
  savedSteps?: TranscriptSavedStep[], sessionStatus?: string,
  responseEvidence?: TranscriptResponseEvidence,
): TranscriptEntry[] {
  const requests = new Map<string, TranscriptEvent>();
  const ambiguousRequests = new Set<string>();
  const failedRequests = new Set<string>();
  const responseCounts = new Map<string, number>();
  const terminalCounts = new Map<string, number>();
  const sequenceCounts = new Map<number, number>();
  for (const event of events) {
    sequenceCounts.set(event.seq, (sequenceCounts.get(event.seq) ?? 0) + 1);
    if (event.request_id && ['provider_response', 'provider_failure'].includes(event.type))
      terminalCounts.set(event.request_id, (terminalCounts.get(event.request_id) ?? 0) + 1);
    if (event.type === 'provider_request' && event.request_id) {
      if (requests.has(event.request_id)) ambiguousRequests.add(event.request_id);
      requests.set(event.request_id, event);
    }
    if (event.request_id && event.type === 'provider_failure') failedRequests.add(event.request_id);
    if (event.request_id && event.type === 'provider_response')
      responseCounts.set(event.request_id, (responseCounts.get(event.request_id) ?? 0) + 1);
  }
  for (const id of ambiguousRequests) requests.delete(id);
  const requestFor = (event: TranscriptEvent) =>
    event.request_id ? requests.get(event.request_id) : undefined;
  const responded = new Set<string>();
  const contradictoryRequests = new Set<string>();
  for (const event of events) {
    if (!event.request_id || !['provider_response', 'provider_failure'].includes(event.type)) continue;
    const request = requestFor(event);
    if (request) {
      if (consistentAttribution(event, request) && request.seq < event.seq) responded.add(event.request_id);
      else contradictoryRequests.add(event.request_id);
    }
  }
  for (const id of contradictoryRequests) responded.delete(id);

  const savedById = new Map<string, TranscriptSavedStep>();
  const savedByRequest = new Map<string, TranscriptSavedStep>();
  const ambiguousSteps = new Set<string>();
  const ambiguousSavedRequests = new Set<string>();
  const savedReviews = new Map<string, TranscriptSavedStep[]>();
  for (const step of savedSteps ?? []) {
    if (savedById.has(step.step_id)) ambiguousSteps.add(step.step_id);
    savedById.set(step.step_id, step);
    if (step.request_id) {
      if (savedByRequest.has(step.request_id)) ambiguousSavedRequests.add(step.request_id);
      savedByRequest.set(step.request_id, step);
    }
    if (step.role === 'supervisor' && step.status === 'completed' && step.text) {
      const key = reviewKey(step.strategy_id, step.round, step.text);
      const matches = savedReviews.get(key) ?? [];
      matches.push(step);
      savedReviews.set(key, matches);
    }
  }
  for (const id of ambiguousSteps) savedById.delete(id);
  for (const id of ambiguousSavedRequests) savedByRequest.delete(id);
  const correlate = (event: TranscriptEvent): TranscriptSavedStep | undefined => {
    const request = requestFor(event);
    if (request && !consistentAttribution(event, request)) return undefined;
    if (event.request_id && contradictoryRequests.has(event.request_id)) return undefined;
    const ids = new Set([event.step_id, request?.step_id].filter(
      (id): id is string => typeof id === 'string' && !!id));
    if (ids.size > 1 || (event.request_id && ambiguousRequests.has(event.request_id))) return undefined;
    const step = ids.size === 1 ? savedById.get([...ids][0])
      : event.request_id ? savedByRequest.get(event.request_id) : undefined;
    if (!step || ambiguousSteps.has(step.step_id)) return undefined;
    if (event.request_id && (ambiguousSavedRequests.has(event.request_id)
      || (savedByRequest.has(event.request_id) && savedByRequest.get(event.request_id) !== step))) return undefined;
    if (step.request_id && (ambiguousSavedRequests.has(step.request_id)
      || (event.request_id && step.request_id !== event.request_id))) return undefined;
    for (const field of ['role', 'strategy_id', 'round'] as const) {
      if (step[field] !== undefined && [event, request].some(row =>
        row !== undefined && row[field] != null && row[field] !== step[field])) return undefined;
    }
    return step;
  };
  const isBound = (event: TranscriptEvent, step: TranscriptSavedStep | undefined) =>
    !!step?.request_id && event.request_id === step.request_id;
  // Admission identifies the durable running step, not the raw request ID
  // allocated later inside the provider call. Never claim a definite binding.
  const active = sessionStatus === 'running' || sessionStatus === 'queued';
  const possibleAttempts = new Map<string, number>();
  if (active) for (const event of events) {
    if (event.type !== 'provider_request' || !event.request_id || responded.has(event.request_id)
      || failedRequests.has(event.request_id) || responseCounts.has(event.request_id)) continue;
    const step = correlate(event);
    if (step?.status === 'running' && !step.request_id && event.step_id === step.step_id)
      possibleAttempts.set(step.step_id, (possibleAttempts.get(step.step_id) ?? 0) + 1);
  }
  const reviewsByEvent = new Map<TranscriptEvent, TranscriptSavedStep>();
  const reviewCounts = new Map<TranscriptSavedStep, number>();
  for (const event of events) {
    if (event.type !== 'session_event' || event.event_kind !== 'supervisor.review'
      || roleOf(event.role) !== 'supervisor') continue;
    const message = String(event.message ?? '');
    let review = correlate(event);
    if (!review && !event.step_id && !event.request_id) {
      const matches = savedReviews.get(reviewKey(event.strategy_id, event.round, message)) ?? [];
      if (matches.length === 1 && !ambiguousSteps.has(matches[0].step_id)) review = matches[0];
    }
    if (review?.role === 'supervisor' && review.status === 'completed'
      && (!event.request_id || isBound(event, review)) && !!message && review.text === message) {
      reviewsByEvent.set(event, review);
      reviewCounts.set(review, (reviewCounts.get(review) ?? 0) + 1);
    }
  }

  const entries: TranscriptEntry[] = [];
  const represented = new Set<TranscriptSavedStep>();
  for (const event of events) {
    const step = correlate(event);
    const bound = isBound(event, step);
    if (event.type === 'provider_request' && event.request_id && responded.has(event.request_id)
      && !ambiguousRequests.has(event.request_id)) continue;
    if (event.type === 'provider_response' || event.type === 'provider_failure') {
      const request = requestFor(event);
      const role = roleOf(event.role ?? request?.role ?? step?.role);
      const failure = event.type === 'provider_failure';
      const evidence = responseEvidence?.[String(event.seq)];
      const rawText = failure
        ? String(event.provider_error ?? event.message ?? 'Provider call failed.')
        : evidence?.text ?? readableTranscriptResponse(event.response);
      const ambiguous = !!event.request_id && ((responseCounts.get(event.request_id) ?? 0) > 1
        || ambiguousRequests.has(event.request_id) || contradictoryRequests.has(event.request_id));
      const recordedFailure = !!event.request_id && failedRequests.has(event.request_id);
      const contentMatches = step?.content_digest !== undefined || responseEvidence !== undefined
        ? !!evidence?.content_digest && evidence.content_digest === step?.content_digest
        : step?.text === rawText;
      const accepted = !failure && !!step && step.status === 'completed' && bound
        && !ambiguous && !recordedFailure && !!rawText && contentMatches;
      if (step && accepted) represented.add(step);
      // A failure event is not the saved terminal status or its reason. Keep
      // both, and never overwrite raw text with a normalized saved result.
      const convertible = !failure && !ambiguous && !recordedFailure && !!event.request_id
        && (savedSteps === undefined || accepted);
      const id = failure ? `failure-${event.request_id ?? 'unknown'}-${event.seq}`
        : convertible ? `response-${event.request_id}`
          : `raw-response-${event.request_id ?? 'unknown'}-${event.seq}`;
      const title = failure ? 'Provider failure'
        : recordedFailure ? 'Provider response with recorded failure'
          : ambiguous ? 'Provider response with ambiguous correlation'
            : accepted ? 'Accepted response'
              : savedSteps !== undefined ? 'Raw response (acceptance unverified)'
                : role === 'other' ? 'Provider response' : role[0].toUpperCase() + role.slice(1);
      const unknown = savedSteps !== undefined && !bound;
      entries.push({
        id, timestamp: event.timestamp, role, title,
        text: rawText || 'The response text was not retained in this historical log.',
        round: event.round ?? request?.round ?? step?.round,
        strategyId: event.strategy_id ?? request?.strategy_id ?? step?.strategy_id,
        sequence: event.seq, request: request?.request, response: event.response,
        requestTimestamp: request && !contradictoryRequests.has(event.request_id ?? '') ? request.timestamp : undefined,
        requestSequence: request && !contradictoryRequests.has(event.request_id ?? '') ? request.seq : undefined,
        conversionDigest: accepted && (role === 'investigator' || role === 'skeptic')
          && sequenceCounts.get(event.seq) === 1 ? evidence?.conversion_digest ?? undefined : undefined,
        brainstormMode: request || typeof event.brainstorm_mode === 'boolean'
          ? brainstormAtDispatch(request ?? event) : step?.brainstorm_mode === true,
        correlationUnknown: unknown,
        claimedAttribution: unknown ? claimedAttribution(event, request) : undefined,
      });
      continue;
    }
    if (event.type === 'provider_request') {
      // Every unmatched raw request survives, even if its logical step ended.
      // Only a uniquely bound running attempt can be called pending.
      // A compatible unresolved request may be live, without that certainty.
      const terminalEvidence = !!event.request_id && terminalCounts.has(event.request_id);
      const pending = !terminalEvidence && (savedSteps === undefined || (!!step && bound && active && step.status === 'running'));
      if (step && pending) represented.add(step);
      const possible = step && event.request_id && !failedRequests.has(event.request_id)
        && !responseCounts.has(event.request_id) && event.step_id === step.step_id
        ? possibleAttempts.get(step.step_id) ?? 0 : 0;
      const title = pending ? 'Provider request'
        : terminalEvidence ? 'Provider request (contradictory terminal evidence)'
        : possible === 1 ? 'Provider request (possibly active; attempt unconfirmed)'
          : possible > 1 ? 'Provider request (active step; attempt ambiguous)' : 'Response not retained';
      const text = pending ? 'Awaiting response…'
        : terminalEvidence ? 'Terminal evidence exists; request identity or chronology is unverified.'
        : possible === 1 ? 'Saved step is running; this raw request may be in flight. Its attempt identity and outcome are unconfirmed.'
          : possible > 1 ? 'Saved step is running; multiple unresolved raw requests match. Which attempt is active and their outcomes are unconfirmed.'
            : 'Raw response unavailable; outcome unverified.';
      const unknown = savedSteps !== undefined && (!bound || terminalEvidence);
      entries.push({
        id: 'pending-' + (event.request_id && !ambiguousRequests.has(event.request_id)
          ? event.request_id : event.seq), timestamp: event.timestamp,
        role: roleOf(event.role ?? step?.role), title, text,
        round: event.round ?? step?.round, strategyId: event.strategy_id ?? step?.strategy_id,
        sequence: event.seq, request: event.request, pending,
        brainstormMode: brainstormAtDispatch(event),
        correlationUnknown: unknown,
        claimedAttribution: unknown ? claimedAttribution(event) : undefined,
      });
      continue;
    }
    if (event.type === 'retention_limit' || event.type === 'event_omitted') {
      entries.push({
        id: 'history-' + event.seq, timestamp: event.timestamp, role: 'other',
        title: 'Incomplete raw history', historyNotice: true, sequence: event.seq,
        text: String(event.message ?? event.reason ?? 'Some raw log events were not retained.'),
      });
      continue;
    }
    if (event.type === 'session_event' && event.event_kind === 'supervisor.review'
      && roleOf(event.role) === 'supervisor') {
      const review = reviewsByEvent.get(event);
      const accepted = !!review && reviewCounts.get(review) === 1;
      if (review && accepted) represented.add(review);
      const unknown = savedSteps !== undefined && !accepted;
      entries.push({
        id: (unknown ? 'raw-event-' : 'event-') + event.seq,
        timestamp: event.timestamp, role: 'supervisor',
        title: unknown ? 'Raw review (acceptance unverified)' : 'Supervisor',
        text: String(event.message ?? ''), round: event.round ?? review?.round,
        strategyId: event.strategy_id ?? review?.strategy_id, sequence: event.seq,
        correlationUnknown: unknown,
        claimedAttribution: unknown ? claimedAttribution(event) : undefined,
        conversionDigest: accepted && sequenceCounts.get(event.seq) === 1
          ? responseEvidence?.[String(event.seq)]?.conversion_digest ?? undefined : undefined,
      });
    }
  }
  (savedSteps ?? []).forEach((step, index) => {
    if (represented.has(step)) return;
    const role = roleOf(step.role);
    const duplicate = ambiguousSteps.has(step.step_id);
    entries.push({
      id: `saved-${step.step_id}${duplicate ? '-' + index : ''}`,
      timestamp: (step.status === 'running' ? step.started_at : step.finished_at) ?? '',
      role, title: 'Reconstructed from saved state' + (duplicate ? ' (duplicate step identity)' : ''),
      text: savedStepMessage(step), round: step.round, strategyId: step.strategy_id,
      sequence: 0, reconstructed: true, brainstormMode: step.brainstorm_mode,
      correlationUnknown: duplicate,
      claimedAttribution: duplicate ? [step.strategy_id, step.round, step.step_id].filter(Boolean).join(' · ') : undefined,
    });
  });
  interventions.forEach((intervention, index) => {
    if (!intervention.id || !intervention.submitted_at) return;
    entries.push({
      id: 'human-' + intervention.id, timestamp: intervention.submitted_at, role: 'human',
      title: 'Human · ' + intervention.kind, text: intervention.text,
      sequence: events.length + index + 1,
      strategyId: intervention.target_strategy_ids?.length === 1 ? intervention.target_strategy_ids[0] : undefined,
    });
  });
  // Historical events can omit their timestamps. Preserve unknown-time
  // semantics rather than fabricating a timestamp or sorting undefined.
  for (const entry of entries) {
    if (typeof entry.timestamp !== 'string') entry.timestamp = '';
  }
  return entries.sort(transcriptOrder);
}

/** Only accepted saved research or supervisor text should incur AI formatting calls. */
export function convertibleTranscriptEntry(entry: TranscriptEntry): boolean {
  return !entry.pending && !entry.reconstructed && !entry.correlationUnknown &&
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
      !entry.correlationUnknown && typeof entry.round === 'number' && Number.isInteger(entry.round) && entry.round > 0)?.round;
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
  for (const entry of [...entries].sort(transcriptOrder)) {
    const hasTurn = typeof entry.round === 'number' && entry.round > 0;
    const turnKey = hasTurn && !entry.correlationUnknown
      ? `${entry.strategyId ?? 'session'}:${entry.round}` : null;
    const humanTurn = entry.role === 'human' && entry.strategyId
      ? latestTurnByStrategy.get(entry.strategyId) : undefined;
    const key = turnKey ?? humanTurn ?? `event:${entry.id}`;
    if (turnKey && entry.strategyId) latestTurnByStrategy.set(entry.strategyId, turnKey);
    const label = entry.correlationUnknown
      ? 'Uncertain attribution' + (entry.claimedAttribution ? ' · Claimed ' + entry.claimedAttribution : '')
      : turnKey ? `Turn ${entry.round}`
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
    const aTurn = a.entries.find(entry => !entry.correlationUnknown && entry.round)?.round;
    const bTurn = b.entries.find(entry => !entry.correlationUnknown && entry.round)?.round;
    if (aTurn !== undefined && bTurn !== undefined && aTurn !== bTurn)
      return bTurn - aTurn;
    const aStrategy = a.entries.find(entry => entry.strategyId)?.strategyId;
    const bStrategy = b.entries.find(entry => entry.strategyId)?.strategyId;
    if (aTurn !== undefined && bTurn !== undefined && aStrategy && bStrategy && aStrategy !== bStrategy)
      return aStrategy.localeCompare(bStrategy, undefined, { numeric: true });
    return b.latestTimestamp.localeCompare(a.latestTimestamp) || b.key.localeCompare(a.key);
  });
}
