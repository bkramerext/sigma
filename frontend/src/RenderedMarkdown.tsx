import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

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
    const expression = line.trim();
    const compactFormula = expression.length > 0 && expression.length <= 240
      && !/\s|[`$\\]/u.test(expression)
      && /[\p{Script=Greek}∫∑√≤≥≠≈∞±×÷^_]/u.test(expression)
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
