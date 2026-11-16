import assert from 'node:assert/strict';
import test from 'node:test';
import { escapeUnmatchedInlineDollars } from '../src/markdown-dollars.ts';

test('numeric-leading math in SIGMA maximum-regions Abstract remains math', () => {
  const abstract = String.raw`Abstract. How many connected regions can an arrangement of $n$ full straight lines produce in the Euclidean plane? The maximum is $1+n(n+1)/2$ for every nonnegative integer $n$. The upper bound follows by inserting lines one at a time: the $k$th line meets the preceding lines in at most $k-1$ distinct points, so it contributes at most $k$ new regions. A concrete family, $y=ix+i^2$ for $i=1,\ldots,n$, has no parallel pairs and no triple concurrence; each new line therefore realizes the full increment.`;
  assert.equal(escapeUnmatchedInlineDollars(abstract), abstract);
  assert.match(abstract, /\$1\+n\(n\+1\)\/2\$ for every nonnegative integer \$n\$/);
});

test('math with numeric first term, spaces, TeX and simple digits is not currency', () => {
  for (const formula of ['$1+n(n+1)/2$', '$1 + n(n+1)/2$', '$1$', '$1 = 2$', '$1 \\cdot n$', '$1−n$']) {
    assert.equal(escapeUnmatchedInlineDollars(formula), formula, formula);
  }
});

test('currency is escaped without consuming adjacent symbolic math', () => {
  assert.equal(escapeUnmatchedInlineDollars('$100 costs less than $n$'), '\\$100 costs less than $n$');
  assert.equal(escapeUnmatchedInlineDollars('$2.50 or $x+1$'), '\\$2.50 or $x+1$');
  assert.equal(escapeUnmatchedInlineDollars('$1,000'), '\\$1,000');
  assert.equal(escapeUnmatchedInlineDollars('Already \\$9 and $n$'), 'Already \\$9 and $n$');
});

test('math delimiters after Unicode use correct UTF-16 positions', () => {
  assert.equal(escapeUnmatchedInlineDollars('📐 $1+n(n+1)/2$'), '📐 $1+n(n+1)/2$');
  assert.equal(escapeUnmatchedInlineDollars('📐 $8 per unit'), '📐 \\$8 per unit');
});
