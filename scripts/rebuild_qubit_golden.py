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
    tex = re.sub(r"\s*\\?\[(?:C\d+(?:,\s*C\d+)*)\]", "", tex)
    tex = re.sub(
        r"\\section\*?\{Typesetting verification note\}.*?(?=\\end\{document\})",
        "",
        tex,
        flags=re.S,
    )
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
