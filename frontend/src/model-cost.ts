/** Reviewed published API token price tiers; unknown costs sort last. */
export function relativeModelCostRank(value: string | undefined): number {
  return value && /^\${1,3}$/.test(value) ? value.length : Number.POSITIVE_INFINITY;
}
