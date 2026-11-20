/**
 * Group rendered Markdown headings with their following content.
 * This is a presentation-only rehype transform. The Markdown source,
 * math nodes, pre/code nodes, and copied/exported transcripts are untouched.
 */
export type SectionNode = {
  type: string;
  tagName?: string;
  properties?: Record<string, unknown>;
  children?: SectionNode[];
  value?: string;
};

function headingLevel(node: SectionNode): number | null {
  if (node.type !== 'element') return null;
  const match = /^h([1-6])$/.exec(node.tagName ?? '');
  return match ? Number(match[1]) : null;
}

function element(tagName: string, className: string, children: SectionNode[]): SectionNode {
  return { type: 'element', tagName, properties: { className: [className] }, children };
}

/** Text-only placeholder blocks are not useful research content. */
function nodeText(node: SectionNode): string {
  if (node.type === 'text' || node.type === 'raw') return node.value ?? '';
  return (node.children ?? []).map(nodeText).join('');
}

function emptyBlock(node: SectionNode): boolean {
  if (node.type === 'text') return !node.value?.trim();
  if (node.type !== 'element') return false;
  // Never hide an actual fenced code block just because its code happens to
  // contain the word "null" in a larger program.
  if (node.tagName === 'pre') {
    const code = node.children?.find(child => child.tagName === 'code');
    const value = nodeText(code ?? node).trim();
    return !value || /^(?:null|none|undefined|\[\]|\{\})$/i.test(value);
  }
  if (node.tagName === 'p' || node.tagName === 'code') {
    const value = nodeText(node).trim();
    return !value || /^(?:null|none|undefined|\[\]|\{\})$/i.test(value);
  }
  if (node.tagName === 'ul' || node.tagName === 'ol') return !(node.children ?? []).some(child => child.tagName === 'li' && !emptyBlock(child));
  if (node.tagName === 'li') return !(node.children ?? []).some(child => !emptyBlock(child));
  return false;
}

function collapseSections(nodes: SectionNode[]): SectionNode[] {
  const result: SectionNode[] = [];
  for (let i = 0; i < nodes.length;) {
    const heading = nodes[i];
    const level = headingLevel(heading);
    if (level === null) {
      result.push(heading);
      i++;
      continue;
    }
    let end = i + 1;
    while (end < nodes.length) {
      const nextLevel = headingLevel(nodes[end]);
      if (nextLevel !== null && nextLevel <= level) break;
      end++;
    }
    const content = collapseSections(nodes.slice(i + 1, end));
    const useful = content.filter(node => !emptyBlock(node));
    // Blank, null, or empty-array fields are omitted from the display.
    // Preserve hierarchy if a heading contains useful nested sections.
    if (useful.length) {
      const headingText = nodeText(heading).trim().toLowerCase();
      if (headingText === 'claim') {
        // Claim is the lead narrative, not an optional detail.
        result.push(heading, ...useful);
      } else {
        const title = element('span', 'markdown-section-title', heading.children ?? []);
        title.properties = { ...title.properties, role: 'heading', 'aria-level': level };
        result.push(element('details', 'markdown-collapsible-section', [
          element('summary', 'markdown-section-summary', [
            element('span', 'markdown-section-chevron', []),
            title,
          ]),
          element('div', 'markdown-section-body', useful),
        ]));
      }
    }
    i = end;
  }
  return result;
}

/** Rehype plugin: headings are collapsed initially, with nested levels retained. */
export function collapsibleMarkdownSections(): (tree: SectionNode) => void {
  return tree => {
    if (tree.children) tree.children = collapseSections(tree.children);
  };
}
