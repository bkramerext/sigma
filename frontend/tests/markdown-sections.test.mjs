import assert from 'node:assert/strict';
import test from 'node:test';
import { collapsibleMarkdownSections } from '../src/markdown-sections.ts';

const node = (tagName, text) => ({
  type: 'element', tagName, children: [{ type: 'text', value: text }],
});
const classOf = element => element.properties?.className?.[0];

test('section headings own their content, including fenced JSON, with no separate code disclosure', () => {
  const tree = { type: 'root', children: [
    node('h4', 'Reasoning steps'),
    { type: 'element', tagName: 'pre', children: [node('code', '[{"title":"Example"}]')] },
    node('h4', 'Claim is conditional'),
    node('p', 'true'),
    node('h4', 'Assumptions'),
    node('ul', 'The premises'),
  ] };
  collapsibleMarkdownSections()(tree);
  assert.equal(tree.children.length, 3);
  assert.ok(tree.children.every(section => section.tagName === 'details'));
  const [reasoning, conditional, assumptions] = tree.children;
  assert.equal(classOf(reasoning), 'markdown-collapsible-section');
  assert.equal(reasoning.properties.open, undefined);
  assert.equal(reasoning.children[0].tagName, 'summary');
  assert.equal(reasoning.children[0].children[1].children[0].value, 'Reasoning steps');
  assert.equal(reasoning.children[1].children[0].tagName, 'pre');
  assert.equal(conditional.children[0].children[1].children[0].value, 'Claim is conditional');
  assert.equal(conditional.children[1].children[0].tagName, 'p');
  assert.equal(assumptions.children[1].children[0].tagName, 'ul');
});

test('nested headings remain nested; headings without content are not wrapped', () => {
  const tree = { type: 'root', children: [
    node('h2', 'Main'),
    node('p', 'Introduction'),
    node('h3', 'Details'),
    node('pre', 'JSON content'),
    node('h2', 'Another'),
  ] };
  collapsibleMarkdownSections()(tree);
  assert.equal(tree.children.length, 2);
  assert.equal(tree.children[0].children[1].children[0].tagName, 'p');
  assert.equal(tree.children[0].children[1].children[1].tagName, 'details');
  assert.equal(tree.children[0].children[1].children[1].children[1].children[0].tagName, 'pre');
  assert.equal(tree.children[1].tagName, 'h2');
});

test('content before first heading and standalone code remain unchanged', () => {
  const paragraph = node('p', 'Preamble');
  const code = node('pre', 'standalone');
  const tree = { type: 'root', children: [paragraph, code] };
  collapsibleMarkdownSections()(tree);
  assert.deepEqual(tree.children, [paragraph, code]);
});
