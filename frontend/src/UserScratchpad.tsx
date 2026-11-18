import { useState } from 'react';
import RenderedMarkdown from './RenderedMarkdown';
import './user-scratchpad.css';

export type ScratchpadEntry = { id: string; text: string };

export default function ProjectScratchpad({ entries, onChange, disabled }: {
  entries: ScratchpadEntry[];
  onChange: (entries: ScratchpadEntry[]) => void;
  disabled?: boolean;
}) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [markdown, setMarkdown] = useState<Record<string, boolean>>({});
  const [copied, setCopied] = useState<string | null>(null);
  const changeText = (id: string, text: string) =>
    onChange(entries.map(entry => entry.id === id ? { ...entry, text } : entry));
  const add = () => {
    if (entries.length >= 100) return;
    const id = crypto.randomUUID().replaceAll('-', '');
    onChange([...entries, { id, text: '' }]);
    setCollapsed(previous => ({ ...previous, [id]: false }));
  };
  const copy = async (entry: ScratchpadEntry) => {
    try {
      await navigator.clipboard.writeText(entry.text);
      setCopied(entry.id);
    } catch {
      setCopied(null);
    }
  };
  return <div className="project-scratchpad">
    <div className="project-scratchpad-heading">
      <h3>Scratchpad</h3>
      <button type="button" className="pt-new-action"
        disabled={disabled || entries.length >= 100} aria-label="Add scratchpad entry"
        data-tooltip="Add scratchpad entry" onClick={add}>
        <svg className="sigma-action-glyph" aria-hidden="true" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="9"/><path d="M12 7.5v9M7.5 12h9"/>
        </svg>
      </button>
    </div>
    <div className="project-scratchpad-entries">
      {entries.map((entry, index) => {
        const isCollapsed = collapsed[entry.id] ?? false;
        const isMarkdown = markdown[entry.id] ?? false;
        return <section className="project-scratchpad-entry" key={entry.id}>
          <div className="project-scratchpad-entry-heading">
            <button type="button" className="strategy-row-disclosure"
              aria-expanded={!isCollapsed} aria-controls={`scratchpad-${entry.id}`}
              onClick={() => setCollapsed(previous => ({ ...previous, [entry.id]: !isCollapsed }))}>
              <svg aria-hidden="true" className={`disclosure-chevron${isCollapsed ? '' : ' is-expanded'}`}
                viewBox="0 0 12 12"><path d="m4 2 4 4-4 4"/></svg>
              <span>Note {index + 1}</span>
            </button>
            <div className="project-scratchpad-actions">
              <button type="button" className={`sigma-render-toggle sigma-unified-markdown workspace-icon-button${isMarkdown ? ' sigma-render-active' : ''}`}
                aria-label={isMarkdown ? 'Show plain text' : 'Render as Markdown'}
                aria-pressed={isMarkdown} data-tooltip={isMarkdown ? 'Show plain text' : 'Render as Markdown'}
                onClick={() => setMarkdown(previous => ({ ...previous, [entry.id]: !isMarkdown }))}>
                <svg aria-hidden="true" className="markdown-logo" viewBox="20 25 160 78" fill="none"
                  xmlns="http://www.w3.org/2000/svg"><path d="M20 92V30h20l20 25 20-25h20v62H80V59L60 84 40 59v33H20Z"
                    fill="currentColor"/><path d="M120 30v38h-18l28 28 28-28h-18V30h-20Z" fill="currentColor"/></svg>
              </button>
              <button type="button" className="text-view-link text-view-icon workspace-icon-button text-copy-button"
                aria-label={`Copy scratchpad note ${index + 1}`} data-tooltip={copied === entry.id ? 'Copied' : 'Copy note'}
                onClick={() => void copy(entry)}>
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="8" y="8" width="12" height="13" rx="2"/>
                  <path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>
                </svg>
              </button>
              <button type="button" className="text-view-link text-view-icon workspace-icon-button project-scratchpad-remove"
                aria-label={`Remove scratchpad note ${index + 1}`} data-tooltip="Remove note"
                disabled={disabled} onClick={() => onChange(entries.filter(item => item.id !== entry.id))}>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
                  strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M8 8 16 16M16 8 8 16"/>
                </svg>
              </button>
            </div>
          </div>
          <div id={`scratchpad-${entry.id}`} hidden={isCollapsed}>
            {isMarkdown
              ? <div className="project-scratchpad-markdown"><RenderedMarkdown body={entry.text}/></div>
              : <textarea aria-label={`Scratchpad note ${index + 1}`} rows={5} maxLength={50000}
                  value={entry.text} disabled={disabled}
                  onChange={event => changeText(entry.id, event.target.value)}/>}
          </div>
        </section>;
      })}
    </div>
  </div>;
}
