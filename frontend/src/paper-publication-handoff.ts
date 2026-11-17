/** Keep a durable paper's transition visible while its saved metadata catches up.
 *
 * The PDF is published before automatic Score begins. A progress poll may see
 * its paper_id while the browser still holds an older saved-paper listing.
 * Hiding the run solely because paper_id exists creates an empty gap.
 */
export type PaperRunPublication = {
  paper_id?: string | null;
  status?: string | null;
  progress?: { stage?: string | null } | null;
};
type PaperListingItem = { paper_id: string };

/** Publishing the PDF is not the end of the paper-generation job. The AI Score
 * step still runs *after* the published record becomes listable. While that
 * original job is active, its generating card owns the Score and Finish steps.
 * A saved-paper card that says "Scoring…" at this point would falsely suggest
 * that a second scoring operation started.
 */
export function publishedRunStillFinishing(
  run: PaperRunPublication | null | undefined,
): boolean {
  return Boolean(run?.paper_id && (run.status === 'active' || run.status === 'queued'));
}

/** A published run is still the same generation operation. Do not label
 * its finishing/publishing time as a second AI scoring evaluation.
 */
export function publishedRunActivityLabel(run: PaperRunPublication): 'Scoring' | 'Finishing' | 'Preparing' {
  if (run.progress?.stage === 'scoring') return 'Scoring';
  if (['finishing', 'score_failed', 'complete'].includes(run.progress?.stage ?? '')) return 'Finishing';
  return 'Preparing';
}

/** Keep the saved row preloaded, but do not show it until Score + Finish ended.
 * An explicit terminal generation SSE receipt is authoritative even when the
 * progress poll still has a stale active run snapshot.
 */
export function savedPaperAwaitingGenerationFinish(
  paperId: string,
  runs: ReadonlyArray<PaperRunPublication>,
  terminalSsePaperId: string | null = null,
): boolean {
  if (paperId === terminalSsePaperId) return false;
  return runs.some(run => run.paper_id === paperId && publishedRunStillFinishing(run));
}

/** Do not retire the generating paper merely because its PDF exists.
 * The first score is not yet available in its canonical paper metadata.
 */
export function publishedRunReadyForHandoff(
  run: PaperRunPublication | null | undefined,
  papers: ReadonlyArray<PaperListingItem>,
  terminalSsePaperId: string | null = null,
): boolean {
  if (typeof run?.paper_id !== 'string' || !run.paper_id ||
      !papers.some(paper => paper.paper_id === run.paper_id)) return false;
  return run.paper_id === terminalSsePaperId || !publishedRunStillFinishing(run);
}

export function publicationAwaitingLibrary(
  run: PaperRunPublication | null | undefined,
  papers: ReadonlyArray<PaperListingItem>,
): boolean {
  return typeof run?.paper_id === 'string' &&
    run.paper_id.length > 0 &&
    !papers.some(paper => paper.paper_id === run.paper_id);
}

export function unlistedPublicationIds(
  runs: ReadonlyArray<PaperRunPublication>,
  papers: ReadonlyArray<PaperListingItem>,
  hidden: ReadonlySet<string> = new Set<string>(),
): string[] {
  const listed = new Set(papers.map(paper => paper.paper_id));
  const missing = new Set<string>();
  for (const run of runs) {
    const paperId = run.paper_id;
    if (typeof paperId === 'string' && paperId && !listed.has(paperId) && !hidden.has(paperId)) {
      missing.add(paperId);
    }
  }
  return [...missing].sort();
}
