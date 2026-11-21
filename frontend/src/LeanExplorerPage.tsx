import { useEffect } from 'react';
import './lean-explorer.css';

/**
 * UI-only concept for exploring a pinned Lean development.
 * Nothing on this page fetches, indexes, elaborates, checks, or saves proof data.
 */
const MIRROR = 'https://github.com/CocoSgt/riemann-hypothesis-lean';
const STATEMENT = `def RiemannZetaZerosOnLine : Prop :=
  ∀ s : ℂ, riemannZeta s = 0 →
    (¬∃ n : ℕ, s = -2 * ((n : ℂ) + 1)) →
    s ≠ 1 →
    s.re = 1 / 2`;

function Step({ number, title, detail }: { number: string; title: string; detail: string }) {
  return <div className="leanx-step">
    <span className="leanx-step-number">{number}</span>
    <span><strong>{title}</strong><small>{detail}</small></span>
  </div>;
}

export default function LeanExplorerPage({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const prior = document.title;
    document.title = 'Lean Explorer · SIGMA';
    return () => { document.title = prior; };
  }, []);

  return <div className="leanx-root">
    <header className="leanx-header">
      <a className="leanx-brand" href="/" onClick={event => {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        onClose();
      }} aria-label="SIGMA Home">
        <img src="/sigma-workspace-logo.png" alt="SIGMA" />
      </a>
      <span className="leanx-header-divider" aria-hidden="true" />
      <span className="leanx-header-title">Lean Explorer</span>
      <span className="leanx-header-spacer" />
      <span className="leanx-draft-pill">UI concept</span>
      <button type="button" className="leanx-close" aria-label="Close Lean Explorer" title="Close Lean Explorer" onClick={onClose}>×</button>
    </header>

    <div className="leanx-scroll">
      <div className="leanx-content">
        <div className="leanx-heading">
          <div>
            <div className="leanx-overline">Formal proof exploration</div>
            <h1>From Lean to understanding</h1>
            <p>Explore an authoritative formal proof alongside mathematical literature, then shape a human-readable exposition for SIGMA.</p>
          </div>
          <span className="leanx-nodata">Preview only · No proof index loaded</span>
        </div>

        <div className="leanx-source-strip">
          <div className="leanx-source-symbol" aria-hidden="true">λ</div>
          <div className="leanx-source-name">
            <strong>Riemann Hypothesis · Alpöge / Claude Lean proof</strong>
            <a href={MIRROR} target="_blank" rel="noreferrer">CocoSgt/riemann-hypothesis-lean ↗</a>
          </div>
          <div className="leanx-source-meta"><span>Source</span><strong>GitHub mirror</strong></div>
          <div className="leanx-source-meta"><span>Commit</span><strong>Not pinned</strong></div>
          <div className="leanx-source-meta"><span>Index</span><strong>Not built</strong></div>
        </div>

        <div className="leanx-columns">
          <aside className="leanx-left" aria-label="Proof navigation mockup">
            <section className="leanx-panel leanx-nav-panel">
              <div className="leanx-panel-heading">
                <h2>Proof navigator</h2>
                <span className="leanx-subtle">Planned</span>
              </div>
              <div className="leanx-search-placeholder" aria-label="Declaration search not implemented">
                <span aria-hidden="true">⌕</span> Search declarations
              </div>
              <div className="leanx-rail-heading">Selected formal statement</div>
              <div className="leanx-selected-node">
                <span className="leanx-node-dot" aria-hidden="true" />
                <span>RiemannZetaZerosOnLine</span>
              </div>
              <div className="leanx-rail-heading">Dependencies</div>
              <div className="leanx-rail-empty">
                <span className="leanx-branch-mark" aria-hidden="true">└─</span>
                Awaiting Lean index
              </div>
              <p className="leanx-rail-note">The actual dependency graph will come from Lean declarations, never an AI-generated outline.</p>
            </section>
            <section className="leanx-panel leanx-nav-panel">
              <div className="leanx-panel-heading"><h2>Expository outline</h2><span className="leanx-subtle">Draft</span></div>
              <div className="leanx-outline-row"><span>01</span> Central mathematical idea</div>
              <div className="leanx-outline-row"><span>02</span> Main constructions</div>
              <div className="leanx-outline-row"><span>03</span> Quantitative estimates</div>
              <div className="leanx-outline-row"><span>04</span> Passage to RH</div>
              <p className="leanx-rail-note">Illustrative chapter topics. These are not claimed Lean dependency edges.</p>
            </section>
          </aside>

          <div className="leanx-center">
            <section className="leanx-panel leanx-statement">
              <div className="leanx-panel-heading">
                <h2>Selected declaration</h2>
                <span className="leanx-file-label">Statements.lean</span>
              </div>
              <div className="leanx-code"><pre><code>{STATEMENT}</code></pre></div>
              <div className="leanx-code-footer">
                <span>Source excerpt · Not locally checked</span>
                <a href={MIRROR + '/blob/main/src/Statements.lean'} target="_blank" rel="noreferrer">View source ↗</a>
              </div>
            </section>

            <section className="leanx-panel leanx-interpretation">
              <div className="leanx-panel-heading"><h2>Mathematical reading</h2><span className="leanx-subtle">Preview text</span></div>
              <p>Every nontrivial zero of the Riemann zeta function lies on the critical line <span className="leanx-math">Re(s) = ½</span>.</p>
              <div className="leanx-evidence-note"><strong>Interpretation is not verification.</strong> The future Explorer will pair each explanation with precise definitions and theorem dependencies from a pinned Lean environment.</div>
            </section>

            <section className="leanx-panel leanx-dependency">
              <div className="leanx-panel-heading"><h2>Formal dependency view</h2><span className="leanx-subtle">Planned</span></div>
              <div className="leanx-graph-empty">
                <div className="leanx-graph-glyph" aria-hidden="true"><span /><span /><span /></div>
                <strong>Dependency graph will appear here</strong>
                <p>Imports, declarations, direct and transitive dependencies, and source locations will be derived from Lean—not inferred from supplementary papers.</p>
              </div>
            </section>
          </div>

          <aside className="leanx-right" aria-label="Proof source and output mockup">
            <section className="leanx-panel leanx-reference-panel">
              <div className="leanx-panel-heading"><h2>Source material</h2></div>
              <div className="leanx-reference">
                <span className="leanx-source-type">A · Formal</span>
                <strong>Official proof (mirror)</strong>
                <a href={MIRROR} target="_blank" rel="noreferrer">Browse repository ↗</a>
              </div>
              <div className="leanx-reference">
                <span className="leanx-source-type">B · Supplementary</span>
                <strong>Alpöge's announcement</strong>
                <a href="https://alpo.ge/remark.pdf" target="_blank" rel="noreferrer">remark.pdf ↗</a>
              </div>
              <div className="leanx-reference">
                <span className="leanx-source-type">B · Supplementary</span>
                <strong>Allahyar · From theta lifts to zeta zeros</strong>
                <span className="leanx-muted">Manuscript to attach</span>
              </div>
            </section>

            <section className="leanx-panel leanx-dossier-panel">
              <div className="leanx-panel-heading"><h2>Expository dossier</h2><span className="leanx-subtle">Planned</span></div>
              <p className="leanx-small-copy">A durable record of mathematical interpretations, formal references, unresolved gaps, and candidate explanations.</p>
              <div className="leanx-dossier-placeholder">
                <span>Statements explained</span><strong>—</strong>
                <span>Proof mappings</span><strong>—</strong>
                <span>Open obligations</span><strong>—</strong>
              </div>
              <div className="leanx-planned-action" aria-disabled="true">Create dossier <span>Coming later</span></div>
            </section>

            <section className="leanx-panel leanx-handoff">
              <div className="leanx-panel-heading"><h2>From exploration to paper</h2></div>
              <Step number="1" title="Explore" detail="Read declarations and source evidence" />
              <Step number="2" title="Research" detail="Develop and critique expository strategies" />
              <Step number="3" title="Publish" detail="Generate a traceable SIGMA paper" />
              <div className="leanx-planned-action" aria-disabled="true">Send to SIGMA research <span>Coming later</span></div>
            </section>
          </aside>
        </div>
        <p className="leanx-footer">Conceptual interface only. No Lean execution, repository indexing, AI analysis, source ingestion, or paper handoff is implemented.</p>
      </div>
    </div>
  </div>;
}
