import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

type MarkdownNode = {
  type: string;
  value?: string;
  children?: MarkdownNode[];
  url?: string;
  data?: Record<string, unknown>;
};

const unicodeMathCommands: Record<string, string> = {
  α: '\\alpha', β: '\\beta', γ: '\\gamma', δ: '\\delta', ε: '\\epsilon', ζ: '\\zeta',
  η: '\\eta', θ: '\\theta', ι: '\\iota', κ: '\\kappa', λ: '\\lambda', μ: '\\mu',
  ν: '\\nu', ξ: '\\xi', π: '\\pi', ρ: '\\rho', σ: '\\sigma', τ: '\\tau',
  φ: '\\phi', χ: '\\chi', ψ: '\\psi', ω: '\\omega',
  Α: 'A', Β: 'B', Γ: '\\Gamma', Δ: '\\Delta', Θ: '\\Theta', Λ: '\\Lambda',
  Ξ: '\\Xi', Π: '\\Pi', Σ: '\\Sigma', Φ: '\\Phi', Ψ: '\\Psi', Ω: '\\Omega',
  '−': '-', '≠': '\\ne', '≤': '\\le', '≥': '\\ge', '≈': '\\approx',
  '∞': '\\infty', '∫': '\\int', '∑': '\\sum', '√': '\\sqrt',
  '±': '\\pm', '×': '\\times', '÷': '\\div',
};

function isTechnicalIdentifier(value: string): boolean {
  return /^[A-Z][A-Z\d]*(?:_[A-Z\d]+)+$/.test(value)
    || /(?:^|\b)(?:[A-Z][A-Z\d]*_){2,}[A-Z\d]+\b/.test(value);
}

function mathSource(value: string): string {
  return value
    .replace(/√\s*\(([^()]+)\)/g, '\\sqrt{$1}')
    .replace(/√([\p{L}\d]+)/gu, '\\sqrt{$1}')
    .replace(/[α-ωΑ-Ω−≠≤≥≈∞∫∑√±×÷]/gu, symbol => unicodeMathCommands[symbol] ?? symbol)
    .replace(/²/g, '^{2}').replace(/³/g, '^{3}')
    .replace(/\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*\/\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)/gu, '\\frac{$1}{$2}')
    .replace(/\(([^()]+)\)\s*\/\s*\(([^()]+)\)/gu, '\\frac{$1}{$2}')
    .replace(/_\(([^()]+)\)/gu, '_{$1}')
    .replace(/([\p{L}\d)]+)\s*\/\s*([\p{L}\d(][^\s,;.!?)]*)/gu, (_match, numerator: string, denominator: string) => {
      const cleanDenominator = denominator.replace(/[.,;:!?]+$/u, '');
      return `\\frac{${numerator}}{${cleanDenominator}}`;
    });
}

type Candidate = { start: number; end: number; value: string; priority: number };

function candidates(text: string, structuralContext = ''): Candidate[] {
  const found: Candidate[] = [];
  const add = (regex: RegExp, priority: number, acceptable: (match: RegExpExecArray) => boolean) => {
    let match: RegExpExecArray | null;
    while ((match = regex.exec(text))) {
      if (acceptable(match)) found.push({ start: match.index, end: match.index + match[0].length, value: match[0], priority });
      if (!match[0].length) regex.lastIndex++;
    }
  };

  // Fractions are recognized only when their shape or surrounding words indicate
  // a quotient. This keeps dates, paths, URLs and version strings as prose.
  add(/\([^()\n]{1,60}\)\s*\/\s*\([^()\n]{1,60}\)|\([^()\n]{1,60}\)\s*\/\s*(?:\d+|[a-zA-Zα-ωΑ-Ω])|(?:\d+|[a-zA-Zα-ωΑ-Ω])\s*\/\s*\([^()\n]{1,60}\)/gu, 4, () => true);
  add(/\b\d{1,3}\s*\/\s*\d{1,3}\b/gu, 3, match => {
    const before = text.slice(Math.max(0, match.index - 65), match.index).toLowerCase();
    const after = text.slice(match.index + match[0].length, match.index + match[0].length + 28).toLowerCase();
    if (/(?:https?:|file:|\b(?:v|version)\s*)$/u.test(before) || /^(?:\/|\d|\.\d)/u.test(after)) return false;
    if (/\b(?:probability|fraction|ratio|chance|likelihood|one half|half|quotient|divided by|over)\s+(?:is|of|equals|was|:)?\s*$/u.test(before)) return true;
    if (/\b(?:probability|fraction|ratio|likelihood)\b/u.test(structuralContext.toLowerCase())) return true;
    return false;
  });
  add(/\([a-zA-Zα-ωΑ-Ω\d+−*^²³\s]{1,50}\)\s*\/\s*\([a-zA-Zα-ωΑ-Ω\d+−*^²³\s]{1,50}\)/gu, 5, () => true);

  // A local equation is a mathematical span even when ordinary prose follows it.
  add(/\b(?:[a-zα-ω]|[A-Z])(?:_[a-zA-Zα-ωΑ-Ω\d{}+-]+)?(?:\([^()\s]{1,24}\))?\s*=\s*[\p{L}\p{N}²³√±−+*/^_{}()\[\]\-]+(?:\s*[=+−*/±]\s*[\p{L}\p{N}²³√±−+*/^_{}()\[\]\-]+)*/gu, 6, match => {
    const expression = match[0].trim().replace(/[.,;:!?]+$/u, '');
    const equalsAt = expression.indexOf('=');
    const right = expression.slice(equalsAt + 1).trim();
    if (!/[\p{L}\d]/u.test(right)) return false;
    const boundary = Math.max(text.lastIndexOf('.', match.index), text.lastIndexOf('!', match.index), text.lastIndexOf('?', match.index), text.lastIndexOf(';', match.index), 0);
    const precedingSentence = text.slice(Math.max(boundary, match.index - 100), match.index).toLowerCase();
    const hasMathematicalCue = /\b(?:equation|root|roots|sequence|term|variable|function|probability|fraction|ratio|solution|solve|formula|identity|satisf(?:y|ies)|denote|defined|obtain|substitute|calculate|compute|evaluate|algebraic|mathematical)\b/u.test(precedingSentence);
    const hasFormulaStructure = /[+−\-*/^_{}²³√±×÷<>≤≥≠≈∑∫]/u.test(right);
    if (!hasFormulaStructure && !hasMathematicalCue) return false;
    // Trim a natural-language continuation after a mathematical expression.
    const trimmed = expression.replace(/\s+(?:(?:relates|where|which|that|and|or|for|with|from|to|is|are|was|were|because|since|as|if|then)\b|[A-Z][a-z]+(?:['’]s)?\s+equation\b)[\s\S]*$/u, '').trim();
    if (trimmed.length < 3) return false;
    match[0] = trimmed;
    return true;
  });

  // Only single-letter, lower-case bases are plausible bare subscripts. The
  // surrounding semantic cue prevents identifiers such as file_state from
  // being reinterpreted merely because they contain an underscore.
  add(/\b[a-zα-ω]_(?:\{[a-zA-Zα-ωΑ-Ω\d,+-]+\}|\([a-zA-Zα-ωΑ-Ω\d,+-]+\)|[a-zA-Zα-ωΑ-Ω\d]+)\b/gu, 2, match => {
    const boundary = Math.max(text.lastIndexOf('.', match.index), text.lastIndexOf('!', match.index), text.lastIndexOf('?', match.index), text.lastIndexOf(';', match.index), 0);
    const before = text.slice(Math.max(boundary, match.index - 90), match.index).toLowerCase();
    const afterBoundary = [text.indexOf('.', match.index), text.indexOf('!', match.index), text.indexOf('?', match.index), text.indexOf(';', match.index)].filter(index => index >= 0);
    const afterEnd = Math.min(...(afterBoundary.length ? afterBoundary : [text.length]), match.index + match[0].length + 80);
    const after = text.slice(match.index + match[0].length, afterEnd).toLowerCase();
    if (isTechnicalIdentifier(match[0])) return false;
    return /\b(?:variable|sequence|term|value|index|coefficient|subscript|denote|let|define|where|of)\b/u.test(before)
      || /^\s*(?:=|\b(?:is|denotes|satisfies|equals|represents)\b)/u.test(after)
      || /[=+−*]/u.test(before.slice(-18));
  });

  // Select non-overlapping spans, preferring equation/context and structured
  // fractions over shorter matches.
  found.sort((a, b) => b.priority - a.priority || a.start - b.start || b.end - a.end);
  const selected: Candidate[] = [];
  for (const candidate of found) {
    if (selected.some(item => candidate.start < item.end && item.start < candidate.end)) continue;
    selected.push(candidate);
  }
  return selected.sort((a, b) => a.start - b.start);
}

function inlineMath(value: string): MarkdownNode {
  const source = mathSource(value);
  return {
    type: 'inlineMath',
    value: source,
    data: {
      hName: 'code',
      hProperties: { className: ['language-math', 'math-inline'] },
      hChildren: [{ type: 'text', value: source }],
    },
  };
}

function semanticMath(): (tree: MarkdownNode) => void {
  return tree => {
    const getText = (node: MarkdownNode): string => `${node.value ?? ''}${(node.children ?? []).map(getText).join(' ')}`;
    const visit = (node: MarkdownNode, parent?: MarkdownNode, ancestors: MarkdownNode[] = []) => {
      if (node.type === 'text' && typeof node.value === 'string' && parent) {
        const tableContext = ancestors.filter(item => item.type === 'table').map(getText).join(' ');
        const matches = candidates(node.value, tableContext);
        if (!matches.length) return;
        const replacement: MarkdownNode[] = [];
        let offset = 0;
        for (const match of matches) {
          if (match.start > offset) replacement.push({ type: 'text', value: node.value.slice(offset, match.start) });
          replacement.push(inlineMath(match.value));
          offset = match.end;
        }
        if (offset < node.value.length) replacement.push({ type: 'text', value: node.value.slice(offset) });
        const index = parent.children?.indexOf(node) ?? -1;
        if (index >= 0) parent.children?.splice(index, 1, ...replacement);
        return;
      }
      if (node.type === 'link' || node.type === 'linkReference' || node.type === 'image' || node.type === 'imageReference') return;
      for (const child of [...(node.children ?? [])]) visit(child, node, [...ancestors, node]);
    };
    visit(tree);
  };
}

/** Translate legacy TeX delimiters while leaving escaped and unmatched text alone. */
export function markdownWithMathDelimiters(body: string): string {
  const code = /(^|\n)([ \t]*)(`{3,}|~{3,})[^\n]*\n[\s\S]*?\n[ \t]*\3[^\n]*(?=\n|$)|(`+)[^`\n]*\4/g;
  const replaceOutsideCode = (source: string, pattern: RegExp, replacement: (match: RegExpExecArray) => string) => {
    const protectedRanges: Array<[number, number]> = [];
    let match: RegExpExecArray | null;
    while ((match = code.exec(source))) protectedRanges.push([match.index, match.index + match[0].length]);
    code.lastIndex = 0;
    const isProtected = (index: number) => protectedRanges.some(([start, end]) => index >= start && index < end);
    let result = '';
    let cursor = 0;
    while ((match = pattern.exec(source))) {
      if (isProtected(match.index)) continue;
      let slashCount = 0;
      for (let index = match.index - 1; index >= 0 && source[index] === '\\'; index--) slashCount++;
      if (slashCount % 2) continue;
      result += source.slice(cursor, match.index) + replacement(match);
      cursor = match.index + match[0].length;
    }
    pattern.lastIndex = 0;
    return cursor ? result + source.slice(cursor) : source;
  };
  let normalized = replaceOutsideCode(body, /(?<!\\)\\\[([\s\S]*?)(?<!\\)\\\]/g, item => `$$\n${item[1]}\n$$`);
  // Apply the inline legacy form only to complete, unescaped pairs.
  normalized = replaceOutsideCode(normalized, /(?<!\\)\\\(([^\n]*?)(?<!\\)\\\)/g, item => `$${item[1]}$`);

  // An unmatched dollar is prose (often currency). Escape it for the math parser
  // while preserving the displayed character and leave matched delimiters intact.
  const lines = normalized.split('\n');
  let inFence = false;
  let fenceCharacter = '';
  let match: RegExpExecArray | null;
  return lines.map(line => {
    const fenceMatch = line.match(/^\s*(`{3,}|~{3,})/u);
    if (fenceMatch) {
      if (!inFence) { inFence = true; fenceCharacter = fenceMatch[1][0]; }
      else if (fenceMatch[1][0] === fenceCharacter) inFence = false;
      return line;
    }
    if (inFence) return line;
    const escapeUnmatched = (segment: string) => {
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
      // Currency markers are literal individually, before pairing math markers.
      // This permits "$5 then $x+1$" and "$x+1$ costs $100" without allowing a
      // price to consume the opening/closing delimiter of a neighboring formula.
      const isCurrency = (position: number) => {
        if (segment[position + 1] === '$' || !/^\d/u.test(segment[position + 1] ?? '')) return false;
        const amount = segment.slice(position + 1).match(/^\d+(?:,\d{3})*(?:\.\d{1,2})?/u)?.[0];
        if (!amount) return false;
        const afterAmount = segment[position + 1 + amount.length] ?? '';
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
      return [...segment].map((character, index) => unmatched.has(index) ? `\\${character}` : character).join('');
    };
    const codeSpan = /(`+)[^`\n]*?\1/gu;
    let result = '';
    let cursor = 0;
    while ((match = codeSpan.exec(line))) {
      result += escapeUnmatched(line.slice(cursor, match.index)) + match[0];
      cursor = match.index + match[0].length;
    }
    return result + escapeUnmatched(line.slice(cursor));
  }).join('\n');
}

export default function RenderedMarkdown({ body }: { body: string }) {
  return <ReactMarkdown skipHtml remarkPlugins={[remarkGfm, remarkMath, semanticMath]}
    rehypePlugins={[[rehypeKatex, { trust: false, throwOnError: false }]]}
    urlTransform={url => url.startsWith('#') ? url : ''}
    components={{ img: () => null }}>{markdownWithMathDelimiters(body)}</ReactMarkdown>;
}
