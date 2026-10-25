import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

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

function bareMathToken(token: string): string | null {
  if (/^\*{1,2}[^*]+\*{1,2}$|^_{1,2}[^_]+_{1,2}$/u.test(token)) return null;
  if (/^\[[^\]]+\]\([^)]+\)$/u.test(token) || /^https?:\/\//iu.test(token)) return null;
  const trailing = token.match(/[.,;:!?]+$/u)?.[0] ?? '';
  const expression = trailing ? token.slice(0, -trailing.length) : token;
  const hasOperand = /[\p{L}\d]/u.test(expression);
  const hasExplicitMathOperator = /[=<>≤≥≠≈∫∑√±×÷+*−]/u.test(expression);
  const hasSimpleFraction = /(?:\d+|[\p{Script=Greek}A-Za-z])\/(?:\([^()]+\)|\[[^\[\]]+\]|\d+|[\p{Script=Greek}A-Za-z])/u.test(expression);
  const hasCompactPowerOrIndex = /^[\p{Script=Greek}A-Za-z](?:\([^()\s]+\))?[\^_](?:\{?[+\-]?(?:\d+|\p{Script=Greek}|[A-Za-z])\}?)$/u.test(expression);
  const hasMathOperator = hasExplicitMathOperator || hasSimpleFraction || hasCompactPowerOrIndex;
  if (!hasOperand || !hasMathOperator || expression.length > 180) return null;
  const normalized = expression
    .replace(/[α-ωΑ-Ω−≠≤≥≈∞∫∑√±×÷]/gu, symbol => unicodeMathCommands[symbol] ?? symbol)
    .replace(/\{([A-Za-z])\}/g, (_match, symbol: string) => `\\{${symbol}\\}`)
    .replace(/(\d+|[\p{Script=Greek}A-Za-z])\/(\([^()]+\)|\[[^\[\]]+\]|\d+|[\p{Script=Greek}A-Za-z])/gu, '\\frac{$1}{$2}');
  return `$${normalized}$${trailing}`;
}

function renderBareMathTokens(line: string): string {
  if (/[$`\\]/u.test(line) || /<\/?[A-Za-z][^>]*>/u.test(line) || /^\s*[#>*+\-|]/u.test(line)) return line;
  return line.split(/(\s+)/u).map(part => {
    if (!part || /^\s+$/u.test(part)) return part;
    return bareMathToken(part) ?? part;
  }).join('');
}

/**
 * Older saved conclusions use the LaTeX delimiters accepted by many editors.
 * remark-math uses dollar delimiters, so translate only those explicit
 * delimiters. Empty math blocks are omitted from the rendered view; the
 * source-mode toggle continues to show the stored text unchanged.
 */
export function markdownWithMathDelimiters(body: string): string {
  const withLegacyDelimiters = body
    .replace(/\\\[([\s\S]*?)\\\]/g, (_match, expression: string) => `$$\n${expression}\n$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_match, expression: string) => `$${expression}$`)
    .replace(/^[ \t]*\$\$[ \t]*\r?\n[ \t]*\$\$[ \t]*(?:\r?\n|$)/gm, '')
    .replace(/\$[ \t]+\$/g, '');
  return withLegacyDelimiters.split('\n').map(line => {
    line = renderBareMathTokens(line);
    const mayContainMarkdownCodeOrMath = /[`$\\]/u.test(line);
    if (!mayContainMarkdownCodeOrMath && !/^\s*[#>*+\-|]/u.test(line)) {
      line = line.replace(
        /(^|[^\p{L}\p{N}])([\p{Script=Greek}A-Za-z](?:\([^()\s]+\))?)\s*([\^_]\s*\{?[+\-]?(?:\d+|[\p{Script=Greek}A-Za-z])\}?)(?=$|[^\p{L}\p{N}])/gu,
        (_match, prefix: string, base: string, power: string) => `${prefix}$${base}${power.replace(/\s+/g, '')}$`,
      );
    }
    const expression = line.trim();
    const compactFormula = expression.length > 0 && expression.length <= 240
      && !/\s|[`$\\]/u.test(expression)
      && (/[\p{Script=Greek}∫∑√≤≥≠≈∞±×÷^_]/u.test(expression)
        || (/[=<>≤≥≠]/u.test(expression) && /[\d()[\]]/u.test(expression)))
      && /[=+*/^_∫∑√≤≥≠≈]/u.test(expression);
    if (!compactFormula || /^[#>*+\-|]/u.test(expression)) return line;
    const start = line.indexOf(expression);
    const mathExpression = expression.replace(/\{([a-zA-Z])\}/g, (_match, symbol: string) => `\\{${symbol}\\}`);
    return `${line.slice(0, start)}$${mathExpression}$${line.slice(start + expression.length)}`;
  }).join('\n');
}

export default function RenderedMarkdown({ body }: { body: string }) {
  return <ReactMarkdown skipHtml remarkPlugins={[remarkMath]}
    rehypePlugins={[[rehypeKatex, { trust: false, throwOnError: false }]]}
    urlTransform={url => url.startsWith('#') ? url : ''}
    components={{ img: () => null }}>{markdownWithMathDelimiters(body)}</ReactMarkdown>;
}
