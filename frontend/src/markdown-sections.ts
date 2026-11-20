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
    // Empty headings remain ordinary headings rather than inert disclosures.
    const content = nodes.slice(i + 1, end);
    if (content.every(node => node.type === 'text' && !(node.value ?? '').trim())) {
      result.push(heading);
    } else {
      const title = element('span', 'markdown-section-title', heading.children ?? []);
      title.properties = { ...title.properties, role: 'heading', 'aria-level': level };
      result.push(element('details', 'markdown-collapsible-section', [
        element('summary', 'markdown-section-summary', [
          element('span', 'markdown-section-chevron', []),
          title,
        ]),
        element('div', 'markdown-section-body', collapseSections(content)),
      ]));
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
