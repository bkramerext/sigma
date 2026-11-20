import assert from 'node:assert/strict';
import test from 'node:test';
import { sizeFractionParentheses } from '../src/math-parentheses.ts';

test('balanced parentheses grow around built-up fractions, not plain terms', () => {
  assert.equal(sizeFractionParentheses(String.raw`\log(\frac{1}{R})`),
    String.raw`\log\left(\frac{1}{R}\right)`);
  assert.equal(sizeFractionParentheses(String.raw`f_R(x)=R^{(-\frac{1}{2})}u(\frac{x}{R})`),
    String.raw`f_R(x)=R^{\left(-\frac{1}{2}\right)}u\left(\frac{x}{R}\right)`);
  assert.equal(sizeFractionParentheses(String.raw`\lambda_k(R)+O(R)`),
    String.raw`\lambda_k(R)+O(R)`);
});
test('preserve existing sized parentheses and unmatched/escaped delimiters', () => {
  const alreadySized = String.raw`\left(\frac{1}{R}\right)`;
  assert.equal(sizeFractionParentheses(alreadySized), alreadySized);
  assert.equal(sizeFractionParentheses(sizeFractionParentheses(String.raw`(\frac{1}{R})`)),
    String.raw`\left(\frac{1}{R}\right)`);
  assert.equal(sizeFractionParentheses(String.raw`\(\frac{1}{R}\)`),
    String.raw`\(\frac{1}{R}\)`);
  assert.equal(sizeFractionParentheses(String.raw`(\frac{1}{R}`),
    String.raw`(\frac{1}{R}`);
});
