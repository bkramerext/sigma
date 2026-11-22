import { useEffect } from 'react';
import './publication-page.css';

const repo = 'https://github.com/bkramerext/unpacking-alpoges-proof';
const pdf = `${repo}/raw/refs/heads/main/paper/Unpacking_Alpoges_Proof_Of_the_Riemann_Hypothesis_v1.1-review.pdf`;
const tex = `${repo}/raw/refs/heads/main/source/Unpacking_Alpoges_Proof_Of_the_Riemann_Hypothesis_v1.1-review.tex`;

function PublicArtworkHeader() {
  return <header className="sigma-public-header">
    <a href="/" aria-label="SIGMA home" className="sigma-public-brand"><img src="/sigma-project-header.png" alt="SIGMA" /></a>
  </header>;
}

export function AlpogePublicationPage() {
  useEffect(() => { document.title = "Unpacking Alpöge's Proof of the Riemann Hypothesis · SIGMA"; }, []);
  return <main className="home-page sigma-public-page">
    <div className="home-atmosphere" aria-hidden="true"/>
    <PublicArtworkHeader/>
    <article className="sigma-public-panel" aria-labelledby="publication-title">
      <p className="sigma-public-kicker">Research exposition · v1.1-review</p>
      <h1 id="publication-title">Unpacking Alpöge's Proof of the Riemann Hypothesis</h1>
      <p className="sigma-public-author">Brian Kramer · 21 November 2026</p>
      <p className="sigma-public-summary">A 137-page guided reconstruction of the mathematical argument associated with Levent Alpöge's formalized proof. Presented for independent mathematical scrutiny, not as an independent certification of correctness.</p>
      <h2>Download the manuscript</h2>
      <div className="sigma-public-downloads" aria-label="Manuscript downloads">
        <a href={pdf} className="sigma-public-download">Download PDF <span aria-hidden="true">↗</span></a>
        <a href={tex} className="sigma-public-download">Download TeX source <span aria-hidden="true">↗</span></a>
      </div>
      <p className="sigma-public-note">Written primarily by ChatGPT under Brian Kramer's direction, review, and editorial guidance.</p>
      <p className="sigma-public-references"><a href="https://zenodo.org/records/24433694">Zenodo publication record</a><span aria-hidden="true"> · </span><a href={repo}>Complete source and figures on GitHub</a></p>
      <p className="sigma-public-feedback">Feedback and corrections: <a href="mailto:zetacontinuation@gmail.com">zetacontinuation@gmail.com</a></p>
    </article>
  </main>;
}

export function PublicNotFoundPage() {
  useEffect(() => { document.title = 'Page not found · SIGMA'; }, []);
  return <main className="home-page sigma-public-page sigma-not-found-page">
    <div className="home-atmosphere" aria-hidden="true"/>
    <section className="sigma-public-panel" aria-labelledby="not-found-title">
      <h1 id="not-found-title">Page not found</h1>
      <p>The requested page does not exist.</p>
      <a href="/" className="sigma-public-home-link">Return Home</a>
    </section>
  </main>;
}
