#!/usr/bin/env python3
"""Reproduce URL-induced TeX overfull boxes with raw, url, and xurl rendering.

This is a local TeX fixture, NOT a recompilation of the SIGMA manuscript.
No provider/network access. Requires pdflatex and installed url/xurl packages.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

URL_A = "https://mindrouter.ai/documentation.html"
URL_B = "https://ai4ra.uidaho.edu/wp-content/uploads/2026/04/Sheneman_MindRouter_PEARC26_Short_Paper.pdf"
BODY = ("The supplied characterization of MindRouter provides the campus-gateway starting point. "
        "It attributes protocol translation across OpenAI, Ollama and Anthropic clients "
        "and Ollama/vLLM backends, WDRR fair-share scheduling, per-user quotas, audit "
        "logging and GPU telemetry to the published gateway. The starting references "
        "are the documentation at {a} and the PEARC short paper at {b}.")
OVERFULL = re.compile(r"Overfull \\hbox \(([0-9.]+)pt too wide\)")


def render(mode: str) -> str:
    if mode == "raw":
        a, b = URL_A, URL_B.replace("_", r"\_")
        package = ""
    elif mode in ("url_both", "xurl_both"):
        a, b = rf"\url{{{URL_A}}}", rf"\url{{{URL_B}}}"
        package = "\\usepackage{" + ("url" if mode == "url_both" else "xurl") + "}\n"
    else:
        raise ValueError(mode)
    return ("\\documentclass{article}\n\\usepackage[T1]{fontenc}\n" + package +
            "\\begin{document}\n" + BODY.format(a=a, b=b) +
            "\n\\end{document}\n")


def main() -> None:
    if not shutil.which("pdflatex"):
        raise SystemExit("pdflatex not installed; no A/B result produced")
    results = {}
    with tempfile.TemporaryDirectory() as d:
        directory = Path(d)
        for mode in ("raw", "url_both", "xurl_both"):
            (directory / f"{mode}.tex").write_text(render(mode), encoding="utf-8")
            p = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                                f"{mode}.tex"], cwd=directory, capture_output=True, text=True,
                               timeout=30, check=False)
            log = directory / f"{mode}.log"
            widths = [float(x) for x in OVERFULL.findall(log.read_text(errors="replace"))] if log.exists() else []
            results[mode] = {"exit_code": p.returncode, "overfull_pt": widths,
                             "max_overfull_pt": max(widths, default=0.0)}
    print(json.dumps({"scope": "isolated URL rendering fixture, not SIGMA paper validation",
                      "results": results}, indent=2))
    if any(r["exit_code"] for r in results.values()):
        raise SystemExit("one or more fixture compilations failed")


if __name__ == "__main__":
    main()
