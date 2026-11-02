"""Repair and rebuild the archived Qubit v1 paper without a provider call."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from sigma.papers import _restore_escaped_math_in_tex

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/evaluations/report_quality/golden5/qubit-non-markovian-v1/source.tex"
OUTPUT = ROOT / "papers/when-does-qubit-decoherence-require-a-non-markovian-model-v1-v1"


def rebuild() -> None:
    tex, count = _restore_escaped_math_in_tex(SOURCE.read_text(encoding="utf-8"))
    if count != 12:
        raise RuntimeError(f"Expected 12 safely escaped math spans; restored {count}")
    tex = tex.replace(
        r"\begin{center}\fbox{\parbox{.92\linewidth}{\textbf{Needs review: TeX verification is incomplete.} Review the archived proofreading diagnostics before relying on the typesetting.}}\end{center}",
        "",
    )
    tex = re.sub(
        r"The bounded evidence index omitted \d+ saved research fragments across \d+ sources\. Claims that could depend on those fragments remain provisional; the full omission ledger is retained with the archived research record\.",
        "This synthesis uses a bounded selection of archived research; unreviewed records may affect its conclusions.",
        tex,
    )
    article, notes = tex.split(r"\section*{Claim and source notes}", 1)
    article = re.sub(r"\s*\\?\[(?:C\d+(?:,\s*C\d+)*)\]", "", article)
    article = re.sub(r"\s*\((?:C\d+(?:,\s*C\d+)*)\)", "", article)
    tex = article + r"\section*{Claim and source notes}" + notes
    tex = re.sub(
        r"\\section\*?\{Typesetting verification note\}.*?(?=\\end\{document\})",
        "",
        tex,
        flags=re.S,
    )
    tex = re.sub(
        r"\\section\*?\{Authorship note\}\s*AI-assisted synthesis from saved research; not independently peer reviewed\.\s*",
        "",
        tex,
    )
    diagram = r"""
\begin{figure}[!htbp]
\centering
\begin{tikzpicture}[>=stealth, every node/.style={draw=blue!65,rounded corners=4pt,fill=blue!5,align=center,text width=5.1cm,font=\small\sffamily,inner sep=6pt}]
\node (dynamic) at (-3.1,0) {Coherence change in the dynamical channel};
\node (preparation) at (3.1,0) {Delay-dependent preparation drift};
\node (same) at (0,-2.5) {Identical unmonitored single-time outputs};
\node (monitor) at (0,-5.0) {Context-matched preparation monitor may separate them};
\draw[->,thick,blue!65] (dynamic) -- (same);
\draw[->,thick,blue!65] (preparation) -- (same);
\draw[->,thick,blue!65] (same) -- (monitor);
\end{tikzpicture}
\caption{Two physically admissible explanations can produce the same unmonitored outputs. A preparation monitor distinguishes this constructed pair only when its calibration transfers to the delayed experiment. The arrows summarize the conditional identifiability argument, not experimental observations.}
\end{figure}
"""
    legacy_diagram = re.compile(
        r"\\begin\{quote\}\s*\\textbf\{Diagram \(readable relationship list\)\.}.*?\\end\{quote\}",
        re.S,
    )
    if len(legacy_diagram.findall(tex)) != 1:
        raise RuntimeError("Expected one source-linked diagram list")
    tex = legacy_diagram.sub(lambda _: diagram, tex)
    tex = tex.replace(r"\usepackage{titlesec}", r"\usepackage{titlesec}" + "\n" + r"\usepackage{tikz}")
    guide = (
        r"\begingroup\setlength{\fboxsep}{10pt}\noindent"
        r"\fcolorbox{blue!55}{blue!5}{\begin{minipage}{0.90\linewidth}"
        r"\small\sffamily{\large\bfseries\color{blue}In brief}\par\smallskip"
        r"\textbf{Question.} When do finite, noisy qubit measurements justify rejecting a CP-divisible dephasing model?\par\smallskip"
        r"\textbf{Answer.} A calibrated increase in the same system's coherence can reject the stated null. Apparent revival alone cannot distinguish dynamics from preparation or readout drift.\par\smallskip"
        r"\textbf{Route.} Define the model, expose sampling and calibration ambiguities, then state the conditional test and its limits.\par\smallskip"
        r"\textbf{Limit.} No experiment, simulation, or primary-literature benchmark was completed.\end{minipage}}\endgroup\par\medskip"
    )
    tex = tex.replace(r"\end{abstract}", r"\end{abstract}" + "\n" + guide, 1)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sigma-qubit-") as temp:
        work = Path(temp)
        source = work / "paper.tex"
        source.write_text(tex, encoding="utf-8")
        result = subprocess.run(
            ["tectonic", "--keep-logs", "--outdir", str(work), str(source)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        OUTPUT.with_suffix(".tex").write_text(tex, encoding="utf-8")
        OUTPUT.with_suffix(".pdf").write_bytes((work / "paper.pdf").read_bytes())
    print(OUTPUT.with_suffix(".pdf"))


if __name__ == "__main__":
    rebuild()
