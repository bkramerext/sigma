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

test('nested headings remain nested; headings without content are removed', () => {
  const tree = { type: 'root', children: [
    node('h2', 'Main'),
    node('p', 'Introduction'),
    node('h3', 'Details'),
    node('pre', 'JSON content'),
    node('h2', 'Another'),
  ] };
  collapsibleMarkdownSections()(tree);
  assert.equal(tree.children.length, 1);
  assert.equal(tree.children[0].children[1].children[0].tagName, 'p');
  assert.equal(tree.children[0].children[1].children[1].tagName, 'details');
  assert.equal(tree.children[0].children[1].children[1].children[1].children[0].tagName, 'pre');
});

test('content before first heading and standalone code remain unchanged', () => {
  const paragraph = node('p', 'Preamble');
  const code = node('pre', 'standalone');
  const tree = { type: 'root', children: [paragraph, code] };
  collapsibleMarkdownSections()(tree);
  assert.deepEqual(tree.children, [paragraph, code]);
});

test('Claim stays visible; null, blank and empty-valued sections disappear', () => {
  const tree = { type: 'root', children: [
    node('h4', 'Claim'),
    node('p', 'The main result remains readable.'),
    node('h4', 'Method'),
    node('p', 'A derivation follows.'),
    node('h4', 'Python code'),
    node('p', 'null'),
    node('h4', 'Sage code'),
    { type: 'element', tagName: 'pre', children: [node('code', 'null')] },
    node('h4', 'Prior session failure attempt ids'),
    node('h4', 'Empty collection'),
    node('p', '[]'),
    node('h4', 'Evidence status'),
    node('p', 'Unverified'),
  ] };
  collapsibleMarkdownSections()(tree);
  assert.deepEqual(tree.children.map(section => section.tagName), ['h4', 'p', 'details', 'details']);
  assert.equal(tree.children[0].children[0].value, 'Claim');
  assert.equal(tree.children[1].children[0].value, 'The main result remains readable.');
  assert.equal(tree.children[2].children[0].children[1].children[0].value, 'Method');
  assert.equal(tree.children[3].children[0].children[1].children[0].value, 'Evidence status');
  assert.equal(tree.children[2].properties.open, undefined);
});

test('genuine code including null checks is preserved', () => {
  const tree = { type: 'root', children: [
    node('h4', 'Python code'),
    { type: 'element', tagName: 'pre', children: [node('code', 'if value is None:\\n    print(value)')] },
  ] };
  collapsibleMarkdownSections()(tree);
  assert.equal(tree.children.length, 1);
  assert.equal(tree.children[0].children[1].children[0].tagName, 'pre');
});
