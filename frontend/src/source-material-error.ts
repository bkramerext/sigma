/** User-facing guidance for SIGMA's extracted Source Material size guard.
 * These are saved backend counts, not estimates from filenames or model tokens.
 */
type SourceMaterialEvent = { kind?: string; message?: string };

export function sourceMaterialOverflowCopy(
  savedMessage: string,
  events: readonly SourceMaterialEvent[] = [],
  strategyReasons: readonly string[] = [],
): { cause: string; next: string } {
  // Some older sessions retain the precise backend failure only in an event
  // after subsequent Resume activity replaces the top-level display message.
  const candidates = [
    savedMessage,
    ...strategyReasons,
    ...events.filter(event => event.kind === 'source_material.compilation.blocked')
      .map(event => event.message || ''),
  ];
  let measurement = '';
  for (const candidate of candidates) {
    const match = /Source Material contains\s*([\d,]+)\s*extracted characters;\s*the session supports at most\s*([\d,]+)/i.exec(candidate);
    if (!match) continue;
    const extracted = Number(match[1].replaceAll(',', ''));
    const limit = Number(match[2].replaceAll(',', ''));
    if (!Number.isSafeInteger(extracted) || !Number.isSafeInteger(limit) || limit <= 0) continue;
    const excess = Math.max(0, extracted - limit);
    measurement = `SIGMA extracted ${extracted.toLocaleString('en-US')} characters from the selected documents and links. The limit is ${limit.toLocaleString('en-US')} characters (${excess.toLocaleString('en-US')} over).`;
    break;
  }
  if (!measurement) measurement = 'The selected documents and links exceed SIGMA’s extracted-text limit.';
  return {
    cause: `Too much Source Material. ${measurement} This is SIGMA’s source-size limit, not the selected model’s context window. Saved project material and research are preserved.`,
    next: 'Open this project’s Source Material list and disable or remove unneeded files and links, or replace long documents with shorter excerpts. Then click Resume. Before the first Investigator/Skeptic call, SIGMA will reload the current enabled sources and recheck the limit. Saved findings and any prior provider usage remain preserved.',
  };
}

/** Only failures in the current retrieval attempt belong in the session.
 * Derive from durable events so polling never duplicates notices and a
 * reopened session still explains its current failures.
 */
export function currentSourceMaterialWarnings(
  events: readonly (SourceMaterialEvent & { sequence?: number })[],
): { sequence: number; message: string }[] {
  const warnings = new Map<number, string>();
  const ordered = [...events].sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0));
  for (const event of ordered) {
    if (event.kind === 'resumed' || event.kind === 'source_material.selection_refreshed'
      || event.kind === 'source_material.compilation.completed') {
      warnings.clear();
      continue;
    }
    if (event.kind === 'source_material.source_failed' && typeof event.sequence === 'number'
      && Number.isSafeInteger(event.sequence) && typeof event.message === 'string' && event.message.trim()) {
      warnings.set(event.sequence, event.message);
    }
  }
  return [...warnings].map(([sequence, message]) => ({ sequence, message }));
}
