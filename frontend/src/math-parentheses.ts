/**
 * Size only balanced TeX parentheses that enclose a built-up fraction.
 * The input is mathematical TeX, not prose; all source characters are retained.
 * Existing \left/\right delimiters are left intact.
 */
export function sizeFractionParentheses(tex: string): string {
  const stack: number[] = [];
  const replacements = new Map<number, string>();
  for (let i = 0; i < tex.length; i++) {
    if (tex[i] === '\\') {
      // Skip escaped literal parentheses; TeX commands are otherwise scanned
      // normally so that \frac's arguments can contain grouped parentheses.
      if (tex[i + 1] === '(' || tex[i + 1] === ')') { i++; continue; }
    }
    if (tex[i] === '(') {
      stack.push(i);
    } else if (tex[i] === ')' && stack.length) {
      const start = stack.pop()!;
      const alreadySized = tex.slice(Math.max(0, start - 5), start) === '\\left'
        || tex.slice(Math.max(0, i - 6), i) === '\\right';
      if (alreadySized) continue;
      const inside = tex.slice(start + 1, i);
      if (/\\(?:dfrac|tfrac|cfrac|frac)\b/.test(inside)) {
        replacements.set(start, '\\left(');
        replacements.set(i, '\\right)');
      }
    }
  }
  return Array.from(tex, (character, i) => replacements.get(i) ?? character).join('');
}
