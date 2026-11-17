/** Keep a durable paper's transition visible while its saved metadata catches up.
 *
 * The PDF is published before automatic Score begins. A progress poll may see
 * its paper_id while the browser still holds an older saved-paper listing.
 * Hiding the run solely because paper_id exists creates an empty gap.
 */
type PaperRunPublication = { paper_id?: string | null };
type PaperListingItem = { paper_id: string };

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
