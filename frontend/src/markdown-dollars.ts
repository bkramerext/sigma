/** Escape literal currency dollars without stealing delimiters from math. */
export function escapeUnmatchedInlineDollars(segment: string): string {
  const positions: number[] = [];
  for (let index = 0; index < segment.length; index++) {
    if (segment[index] !== '$') continue;
    let slashes = 0;
    for (let prior = index - 1; prior >= 0 && segment[prior] === '\\'; prior--) slashes++;
    if (slashes % 2) continue;
    if (segment[index + 1] === '$') { index++; continue; }
    if (segment[index - 1] === '$') continue;
    positions.push(index);
  }

  const unmatched = new Set<number>();
  const isCurrency = (position: number): boolean => {
    if (segment[position + 1] === '$' || !/^\d/u.test(segment[position + 1] ?? '')) return false;
    const amount = segment.slice(position + 1).match(/^\d+(?:,\d{3})*(?:\.\d{1,2})?/u)?.[0];
    if (!amount) return false;
    const remaining = segment.slice(position + 1 + amount.length);
    const next = remaining.trimStart()[0] ?? '';
    // "$1+n(n+1)/2$" and "$1 + n$" are math, not the price "$1".
    // A closing '$' also denotes math, including the simple formula "$1$".
    if (next && '+-*/^=<>$({[\\−×÷'.includes(next)) return false;
    const afterAmount = remaining[0] ?? '';
    return !/[\d\w./\\^]/u.test(afterAmount);
  };
  const mathPositions = positions.filter(position => {
    if (!isCurrency(position)) return true;
    unmatched.add(position);
    return false;
  });
  for (let index = 0; index < mathPositions.length; index += 2) {
    const open = mathPositions[index];
    const close = mathPositions[index + 1];
    if (close === undefined) unmatched.add(open);
  }
  // Indexes above are UTF-16 offsets. Do not spread by Unicode code point here.
  return segment.split('').map((character, index) => unmatched.has(index) ? '\\' + character : character).join('');
}
