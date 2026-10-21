import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

export default function RenderedMarkdown({ body }: { body: string }) {
  return <ReactMarkdown skipHtml remarkPlugins={[remarkMath]}
    rehypePlugins={[[rehypeKatex, { trust: false, throwOnError: false }]]}
    urlTransform={url => url.startsWith('#') ? url : ''}
    components={{ img: () => null }}>{body}</ReactMarkdown>;
}
