import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import './sigma-select.css';

type Option = { value: string; label: string };
type Props = { id?: string; ariaLabel: string; value: string; options: Option[]; onChange: (value: string) => void; disabled?: boolean; className?: string };

/** Dark copper dropdown shared across SIGMA, including clipped dialogs. */
export default function SigmaSelect({ id, ariaLabel, value, options, onChange, disabled = false, className = '' }: Props) {
  const listId = 'sigma-pick-options-' + useId().replace(/:/g, '');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const items = useRef<(HTMLButtonElement | null)[]>([]);
  const [rectStyle, setRectStyle] = useState({ top: -10000, left: -10000, width: 0, maxHeight: 256 });
  const selectedIndex = Math.max(0, options.findIndex(item => item.value === value));
  const selected = options.find(item => item.value === value);
  useEffect(() => { if (disabled) setOpen(false); }, [disabled]);
  useEffect(() => { if (open) items.current[active]?.focus(); }, [open, active]);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!root.current?.contains(target) && !popup.current?.contains(target)) setOpen(false);
    };
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  useLayoutEffect(() => {
    if (!open || !popup.current) return;
    const menu = popup.current;
    menu.showPopover();
    const position = () => {
      const rect = trigger.current?.getBoundingClientRect();
      if (!rect) return;
      const below = Math.max(0, window.innerHeight - rect.bottom - 12);
      const above = Math.max(0, rect.top - 12);
      const desired = Math.min(256, options.length * 35 + 10);
      const useAbove = below < desired && above > below;
      const height = Math.max(32, Math.min(desired, useAbove ? above : below));
      const width = Math.min(rect.width, window.innerWidth - 16);
      setRectStyle({
        top: useAbove ? Math.max(8, rect.top - height - 4) : rect.bottom + 4,
        left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)),
        width, maxHeight: height,
      });
    };
    position();
    window.addEventListener('resize', position);
    window.addEventListener('scroll', position, true);
    return () => {
      window.removeEventListener('resize', position);
      window.removeEventListener('scroll', position, true);
      if (menu.matches(':popover-open')) menu.hidePopover();
    };
  }, [open, options.length]);
  const choose = (next: string) => {
    onChange(next); setOpen(false);
    requestAnimationFrame(() => trigger.current?.focus());
  };
  const move = (next: number) => { if (options.length) setActive((next + options.length) % options.length); };
  return <div ref={root} className={'sigma-select ' + className}>
    <button id={id} ref={trigger} type="button" className="sigma-select-trigger" role="combobox"
      aria-label={ariaLabel} aria-haspopup="listbox" aria-expanded={open} aria-controls={listId}
      disabled={disabled} onClick={() => { setActive(selectedIndex); setOpen(current => !current); }}
      onKeyDown={event => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault(); setActive(event.key === 'ArrowDown' ? selectedIndex : options.length - 1); setOpen(true);
        } else if (event.key === 'Escape' && open) {
          event.preventDefault(); event.stopPropagation(); setOpen(false);
        }
      }}>
      <span>{selected?.label ?? value}</span>
      <svg className="sigma-select-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="m2 4 4 4 4-4"/></svg>
    </button>
    {open && <div ref={popup} popover="manual" style={rectStyle} className="sigma-select-options" id={listId} role="listbox" aria-label={ariaLabel}>
      {options.map((item, index) => <button key={item.value} ref={element => { items.current[index] = element; }}
        type="button" role="option" aria-selected={item.value === value}
        tabIndex={active === index ? 0 : -1} onFocus={() => setActive(index)}
        onClick={() => choose(item.value)} onKeyDown={event => {
          if (event.key === 'ArrowDown') { event.preventDefault(); move(index + 1); }
          else if (event.key === 'ArrowUp') { event.preventDefault(); move(index - 1); }
          else if (event.key === 'Home') { event.preventDefault(); move(0); }
          else if (event.key === 'End') { event.preventDefault(); move(options.length - 1); }
          else if (event.key === 'Escape') {
            event.preventDefault(); event.stopPropagation(); setOpen(false); trigger.current?.focus();
          } else if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault(); choose(item.value);
          }
        }}><span>{item.label}</span></button>)}
    </div>}
  </div>;
}
