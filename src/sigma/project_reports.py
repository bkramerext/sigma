"""Deterministic human-readable reports generated from project export snapshots."""

from __future__ import annotations

import html
import json
from typing import Any, cast


def _value(value: Any) -> str:
    if value is None:
        return "Not recorded"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = str(value).strip()
    return text if text else "Not recorded"


def _items(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _rows(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, (list, tuple))
        else []
    )


def _report_lines(data: dict[str, Any]) -> list[str]:
    project_raw = data.get("project")
    project = cast(dict[str, Any], project_raw) if isinstance(project_raw, dict) else {}
    title = _value(project.get("title"))
    lines = [title, "=" * max(3, min(len(title), 72)), "", "Project", "-------"]
    lines += [
        "Interpretation: Agent-generated findings are provisional unless explicitly verified; reviewer agreement is not proof.",
        "",
    ]
    for label, key in (
        ("Research problem", "problem"),
        ("Project ID", "id"),
        ("Research mode", "investigation_type"),
    ):
        lines += [f"{label}: {_value(project.get(key))}", ""]

    lines += ["Strategies", "----------"]
    strategies = _rows(project.get("strategies"))
    active_order = project.get("active_order")
    if not isinstance(active_order, (list, tuple)):
        active_order = []
    ordered = {identifier: index for index, identifier in enumerate(active_order)}
    strategies = sorted(
        strategies,
        key=lambda item: (ordered.get(item.get("id"), len(ordered)), item.get("created_at", "")),
    )
    if not strategies:
        lines += ["No strategies are recorded.", ""]
    for strategy in strategies:
        lines += [
            f"{strategy.get('title') or 'Untitled strategy'} ({'removed' if strategy.get('removed_at') else 'saved'})",
            "~" * max(3, min(len(strategy.get("title") or "Strategy"), 72)),
            _value(strategy.get("approach")),
            "",
        ]

    lines += ["Research sessions", "-----------------"]
    sessions = _rows(data.get("research_sessions"))
    if not sessions:
        lines += ["No research sessions are recorded.", ""]
    for session in sessions:
        number = session.get("session_number", "?")
        lines += [
            f"Session #{number}",
            f"Execution status: {_value(session.get('status'))}",
            f"Outcome: {_value(session.get('outcome'))}",
            f"Strategy: {_value(session.get('strategy_title'))}",
            f"Started: {_value(session.get('started_at') or session.get('created_at'))}",
            "",
        ]
        artifacts = _rows(session.get("artifacts"))
        if not artifacts:
            lines += ["No completed research artifact is recorded.", ""]
        for index, artifact in enumerate(artifacts, 1):
            lines += [
                f"Artifact {index} · {_value(artifact.get('note'))}",
                f"Claim: {_value(artifact.get('claim') or artifact.get('claim_or_question'))}",
                f"Method: {_value(artifact.get('method'))}",
                f"Assumptions: {'; '.join(_items(artifact.get('assumptions'))) or 'Not recorded'}",
                f"Evidence status: {_value(artifact.get('evidence_status'))}",
                f"Skeptic response: {_value(artifact.get('skeptic_response'))}",
                f"Objections: {'; '.join(_items(artifact.get('objections'))) or 'None recorded'}",
                f"Decision: {_value(artifact.get('coordinator_decision'))}",
                f"Open obligations: {'; '.join(_items(artifact.get('open_obligations'))) or 'None recorded'}",
                f"Next question: {_value(artifact.get('next_question'))}",
                "",
            ]
        if session.get("terminal_reason"):
            lines += [f"Terminal reason: {_value(session.get('terminal_reason'))}", ""]

    lines += ["Agentic runs", "------------"]
    runs = _rows(data.get("agentic_runs"))
    if not runs:
        lines += ["No agentic runs are recorded.", ""]
    for run in runs:
        terminal_raw = run.get("terminal")
        terminal = cast(dict[str, Any], terminal_raw) if isinstance(terminal_raw, dict) else {}
        lines += [
            f"Run {run.get('run_id', '')}",
            f"Execution status: {_value(terminal.get('status'))}",
            f"Started: {_value(run.get('started_at'))}",
            f"Summary: {_value(terminal.get('summary'))}",
            "",
        ]
        for step in _rows(run.get("steps")):
            output_raw = step.get("output")
            output = cast(dict[str, Any], output_raw) if isinstance(output_raw, dict) else {}
            lines += [
                f"Step {step.get('index', '?')} · {_value(step.get('role'))} · {_value(step.get('status'))}"
            ]
            for key in (
                "title",
                "approach",
                "mechanism",
                "evidence_boundary",
                "public_summary",
                "mechanism_comparison",
                "missing_obligations",
            ):
                if output.get(key):
                    lines.append(f"{key.replace('_', ' ').capitalize()}: {_value(output[key])}")
            for objection in _items(output.get("objections")):
                lines.append(f"Objection: {objection}")
            lines.append("")
        for decision in _rows(run.get("history")):
            lines += [
                f"Decision: {_value(decision.get('outcome'))} · {_value(decision.get('summary'))}",
                "",
            ]
    return lines


def _latex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def render_report(data: dict[str, Any], output_format: str) -> tuple[str, str]:
    """Return UTF-8 report text and MIME type; unknown optional fields are ignored."""
    if output_format not in {"txt", "html", "tex"}:
        raise ValueError("Report format must be txt, html or tex")
    lines = _report_lines(data)
    body = "\n".join(lines).rstrip() + "\n"
    if output_format == "txt":
        return body, "text/plain; charset=utf-8"
    if output_format == "html":
        title = html.escape(
            str((data.get("project") or {}).get("title") or "Research report"), quote=True
        )
        escaped = html.escape(body, quote=True)
        return (
            f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} — Research Report</title><style>body{{max-width:900px;margin:3rem auto;padding:0 1.25rem;font:16px/1.6 system-ui,sans-serif;color:#17212b}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}}</style></head><body><pre>{escaped}</pre></body></html>\n',
            "text/html; charset=utf-8",
        )
    escaped_lines = [_latex(line) for line in lines]
    tex_body = "\n".join(r"\par" if not line else line + r"\par" for line in escaped_lines)
    tex = (
        "% !TEX program = xelatex\n\\documentclass[11pt]{article}\n\\usepackage{fontspec}\n"
        "\\usepackage{textcomp}\n\\usepackage[margin=1in]{geometry}\n"
        "\\setlength{\\parskip}{0.5em}\n\\begin{document}\n" + tex_body + "\n\\end{document}\n"
    )
    return tex, "application/x-tex; charset=utf-8"
