"""Deterministic human-readable reports generated from project export snapshots."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import tempfile
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
    for label, key in (("Research problem", "problem"), ("Project ID", "id")):
        lines += [f"{label}: {_value(project.get(key))}", ""]
    research_type_labels = {
        "biology": "Biology",
        "chemistry": "Chemistry",
        "computer_science": "Computer Science",
        "economics": "Economics",
        "engineering": "Engineering",
        "law": "Law",
        "mathematical": "Mathematics",
        "military": "Military",
        "philosophy": "Philosophy",
        "physics": "Physics",
        "religion": "Religion",
        "default": "Other",
    }
    mode = project.get("investigation_type")
    mode_label = research_type_labels.get(mode, mode) if isinstance(mode, str) else mode
    lines += [f"Research type: {_value(mode_label)}", ""]
    difficulty_labels = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}
    difficulty = project.get("difficulty")
    if isinstance(difficulty, str):
        lines += [f"Difficulty: {difficulty_labels.get(difficulty, 'Unavailable')}", ""]

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
        outcome_raw = session.get("outcome")
        outcome = cast(dict[str, Any], outcome_raw) if isinstance(outcome_raw, dict) else {}
        lines += [
            f"Session #{number}",
            f"Execution status: {_value(session.get('status'))}",
            f"Outcome: {_value(outcome.get('label') or outcome.get('assessment'))}",
            f"Strategy: {_value(session.get('strategy_title'))}",
            f"Started: {_value(session.get('started_at') or session.get('created_at'))}",
            "",
        ]
        if outcome.get("summary"):
            lines += [f"Outcome summary: {_value(outcome.get('summary'))}", ""]
        if _items(outcome.get("caveats")):
            lines += ["Outcome caveats:"]
            lines += [f"- {item}" for item in _items(outcome.get("caveats"))]
            lines.append("")
        metrics_raw = outcome.get("metrics")
        metrics = cast(dict[str, Any], metrics_raw) if isinstance(metrics_raw, dict) else {}
        operational = _rows(metrics.get("operational"))
        research_quality = _rows(metrics.get("research_quality"))
        if operational or research_quality:
            lines += ["Outcome metrics", "~~~~~~~~~~~~~~~"]
            for heading, items in (
                ("Operational metrics", operational),
                ("Research-quality metrics", research_quality),
            ):
                if not items:
                    continue
                lines += [heading, "~" * len(heading)]
                for item in items:
                    lines.append(f"{_value(item.get('label'))}: {_value(item.get('value'))}")
                lines.append("")
        solution_review = outcome
        solution_review = solution_review.get("solution_review")
        review = solution_review
        if isinstance(review, dict):
            lines += [
                f"Claim scope: {_value(review.get('claim_scope', 'not recorded'))}",
                f"Solution claim: {_value(review.get('claim'))}",
                f"Argument: {_value(review.get('argument_summary'))}",
                f"Skeptic response: {_value(review.get('skeptic_response'))}",
                f"Assumptions reviewed: {'; '.join(_items(review.get('assumptions'))) or 'Not recorded'}",
                f"Proof obligations considered: {'; '.join(_items(review.get('proof_obligations'))) or 'Not recorded'}",
                f"Still open: {'; '.join(_items(review.get('open_obligations'))) or 'None recorded'}",
                f"Solution evidence references: {'; '.join(_items(review.get('basis_artifact_ids'))) or 'Not recorded'}",
                f"Unresolved objections: {'; '.join(_items(review.get('unresolved_objections'))) or 'None recorded'}",
                f"Resolved review notes: {'; '.join(_items(review.get('resolved_objections'))) or 'None recorded'}",
                "",
            ]
            lines += [
                f"Skeptic objection: {item}" for item in _items(review.get("skeptic_objections"))
            ]
            if _items(review.get("skeptic_objections")):
                lines.append("")
            if review.get("verification_status", "unknown") != "unknown":
                lines.insert(-1, f"Verification status: {_value(review['verification_status'])}")
            argument_steps = _rows(review.get("argument_steps"))
            if argument_steps:
                lines += ["Reviewed reasoning", "~~~~~~~~~~~~~~~~~"]
                for step in argument_steps:
                    lines += [
                        f"Step {step.get('number', '?')}: {_value(step.get('title'))}",
                        f"Epistemic status: {_value(step.get('epistemic_status'))}",
                        _value(step.get("argument")),
                        f"Research artifact: {_value(step.get('research_artifact_id'))}",
                        f"Source artifacts: {'; '.join(_items(step.get('basis_artifact_ids'))) or 'Current research artifact'}",
                    ]
                    step_review = step.get("review")
                    if isinstance(step_review, dict):
                        lines += [
                            f"Skeptic disposition: {_value(step_review.get('disposition'))}",
                            f"Skeptic rationale: {_value(step_review.get('rationale'))}",
                        ]
                    lines.append("")
            for finding in _rows(review.get("strategy_findings")):
                if len(_rows(review.get("strategy_findings"))) <= 1:
                    break
                lines += [
                    f"Strategy finding: {_value(finding.get('strategy_title'))} · {_value(finding.get('status'))}",
                    f"Claim: {_value(finding.get('claim'))}",
                    f"Source artifact: {_value(finding.get('research_artifact_id'))}",
                ]
                for step in _rows(finding.get("reasoning_steps")):
                    lines += [
                        f"Step {step.get('number', '?')}: {_value(step.get('title'))} ({_value(step.get('epistemic_status'))})",
                        _value(step.get("argument")),
                    ]
                    step_review = step.get("review")
                    if isinstance(step_review, dict):
                        lines.append(
                            f"Skeptic review: {_value(step_review.get('disposition'))} · {_value(step_review.get('rationale'))}"
                        )
                        if step_review.get("objection"):
                            lines.append(f"Objection: {_value(step_review.get('objection'))}")
                for label, key in (
                    ("Objection", "objections"),
                    ("Open obligation", "open_obligations"),
                ):
                    lines += [f"{label}: {item}" for item in _items(finding.get(key))]
                lines.append("")
        assessments = _rows(session.get("strategy_assessments"))
        if assessments:
            lines += ["Strategy Assessments", "--------------------"]
            labels = {
                "contributed_to_solution": "Contributed to solution",
                "productive": "Productive",
                "unproductive": "Unproductive",
                "not_used": "Not used",
                "disabled": "Disabled",
                "unknown": "Unknown (historical evidence unavailable)",
            }
            for item in assessments:
                label = labels.get(str(item.get("assessment")), "Unknown")
                refs = "; ".join(_items(item.get("basis_artifact_ids"))) or "No artifact references"
                lines.append(
                    f"{_value(item.get('strategy_title'))} · {label}: {_value(item.get('rationale'))} [Evidence: {refs}]"
                )
            lines.append("")
        artifacts = _rows(session.get("artifacts"))
        if not artifacts:
            lines += ["No completed research artifact is recorded.", ""]
        for index, artifact in enumerate(artifacts, 1):
            skeptic = artifact.get("skeptic_output")
            skeptic = skeptic if isinstance(skeptic, dict) else {}
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
            for disposition in _rows(skeptic.get("obligation_reviews")):
                lines.append(
                    "Obligation disposition: "
                    f"{_value(disposition.get('status'))} · {_value(disposition.get('obligation_id'))} · "
                    f"{_value(disposition.get('rationale'))} · evidence: "
                    f"{'; '.join(_items(disposition.get('basis_artifact_ids')) + _items(disposition.get('basis_step_ids'))) or 'none recorded'} · model-reported, unverified"
                )
            if _rows(skeptic.get("obligation_reviews")):
                lines.append("")
        steps_with_context = [
            step
            for step in _rows(session.get("steps"))
            if isinstance(step.get("context_manifest"), dict)
        ]
        if steps_with_context:
            lines += ["Agent context selection", "~~~~~~~~~~~~~~~~~~~~~~~"]
            lines.append(
                "Context extracts are deterministic, untrusted summaries; omitted evidence remains in the original session records."
            )
            for step in steps_with_context:
                manifest = step["context_manifest"]
                lines.append(
                    f"Step {_value(step.get('id'))} · {_value(step.get('role'))}: "
                    f"{_value(manifest.get('selected_count'))} selected, "
                    f"{_value(manifest.get('omitted_count'))} current-session artifacts omitted, "
                    f"{_value(manifest.get('assembled_context_bytes'))} UTF-8 bytes"
                )
                obligation_counts = manifest.get("obligation_disposition_counts")
                if isinstance(obligation_counts, dict):
                    lines.append(
                        "Obligation ledger dispositions: "
                        + ", ".join(
                            f"{state} {_value(obligation_counts.get(state, 0))}"
                            for state in (
                                "unresolved",
                                "addressed",
                                "superseded",
                                "retracted",
                                "unknown",
                            )
                        )
                    )
                omitted_obligations = manifest.get("omitted_obligations")
                if isinstance(omitted_obligations, dict) and omitted_obligations.get("count"):
                    lines.append(
                        f"Omitted obligations: {_value(omitted_obligations.get('count'))}; "
                        f"IDs: {_value(omitted_obligations.get('obligation_ids'))}; "
                        f"{_value(omitted_obligations.get('reason'))}"
                    )
                for source in _rows(manifest.get("sources")):
                    lines.append(
                        f"- {_value(source.get('status'))} {_value(source.get('category'))}: "
                        f"{_value(source.get('source_ids', source.get('source_id')))} · {_value(source.get('reason'))}"
                    )
                omitted_prior = manifest.get("omitted_prior_session_findings")
                if isinstance(omitted_prior, dict) and omitted_prior.get("count"):
                    lines.append(
                        f"- Omitted prior-session findings: {_value(omitted_prior.get('count'))}; "
                        f"source pointers: {_value(omitted_prior.get('source_ids'))}; "
                        f"{_value(omitted_prior.get('reason'))}"
                    )
                omitted_failures = manifest.get("omitted_prior_failures")
                if isinstance(omitted_failures, dict) and omitted_failures.get("count"):
                    lines.append(
                        f"- Omitted operational failures: {_value(omitted_failures.get('count'))}; "
                        f"attempt pointers: {_value(omitted_failures.get('attempt_ids'))}; "
                        f"{_value(omitted_failures.get('reason'))}"
                    )
            lines.append("")
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


_HEADING_MARK = re.compile(r"^(=+|-+|~+)$")
_INLINE_MATH = re.compile(r"(\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$|(?<!\\)\$[^$\n]+\$)")


def _html_math_text(source: str) -> str:
    value = source
    for latex, symbol in (
        (r"\cdot", "·"),
        (r"\times", "×"),
        (r"\leq", "≤"),
        (r"\le", "≤"),
        (r"\geq", "≥"),
        (r"\ge", "≥"),
        (r"\neq", "≠"),
        (r"\infty", "∞"),
        (r"\pi", "π"),
        (r"\alpha", "α"),
        (r"\beta", "β"),
        (r"\gamma", "γ"),
    ):
        value = value.replace(latex, symbol)
    value = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"\1⁄\2", value)
    value = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"√(\1)", value)
    return value


def _html_inline(text: str) -> str:
    """Escape report content and retain only a small safe Markdown subset."""
    parts = re.split(
        r"(`[^`\n]+`|\*\*[^*\n]+\*\*|\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$|(?<!\\)\$[^$\n]+\$)", text
    )
    result: list[str] = []
    for part in parts:
        if part.startswith("`") and part.endswith("`"):
            result.append(f"<code>{html.escape(part[1:-1])}</code>")
        elif part.startswith("**") and part.endswith("**"):
            result.append(f"<strong>{html.escape(part[2:-2])}</strong>")
        elif _INLINE_MATH.fullmatch(part):
            display = part.startswith(("$$", r"\["))
            body = part[2:-2] if part.startswith(("$$", r"\(", r"\[")) else part[1:-1]
            display_attr = ' display="block"' if display else ""
            result.append(
                f'<math class="report-math"{display_attr}><mrow><mtext>{html.escape(_html_math_text(body))}</mtext></mrow></math>'
            )
        else:
            result.append(html.escape(part))
    return "".join(result)


def _html_document(data: dict[str, Any], lines: list[str]) -> str:
    project_raw = data.get("project")
    project = cast(dict[str, Any], project_raw) if isinstance(project_raw, dict) else {}
    title = str(project.get("title") or "Research report")
    blocks: list[str] = []
    index = 2
    list_items: list[str] = []
    section_open = False
    session_open = False
    session_header_open = False
    session_facts: list[tuple[str, str]] = []

    def flush_list() -> None:
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{item}</li>" for item in list_items) + "</ul>")
            list_items.clear()

    def flush_session_header() -> None:
        nonlocal session_header_open
        if not session_header_open:
            return
        facts: list[str] = []
        for label, value in session_facts:
            fact_class = ""
            if label == "Execution status":
                normalized = value.casefold()
                fact_class = (
                    " report-status-ended"
                    if normalized in {"ended", "completed"}
                    else " report-status-active"
                    if normalized in {"running", "queued", "paused"}
                    else ""
                )
            elif label == "Outcome":
                normalized = value.casefold()
                fact_class = (
                    " report-outcome-positive"
                    if normalized.startswith(("positive", "successful"))
                    else " report-outcome-negative"
                    if normalized.startswith(("negative", "failed"))
                    else " report-outcome-mixed"
                    if normalized.startswith("mixed")
                    else ""
                )
            wide_class = " report-session-fact-wide" if label == "Strategy" else ""
            facts.append(
                f'<div class="report-session-fact{wide_class}"><dt>{html.escape(label)}</dt>'
                f'<dd class="report-session-value{fact_class}">{_html_inline(value)}</dd></div>'
            )
        if facts:
            blocks.append('<dl class="report-session-meta">' + "".join(facts) + "</dl>")
        blocks.append("</header>")
        session_facts.clear()
        session_header_open = False

    def close_session() -> None:
        nonlocal session_open
        if session_open:
            flush_session_header()
            blocks.append("</article>")
            session_open = False

    while index < len(lines):
        line = lines[index].strip()
        if not line:
            flush_list()
            index += 1
            continue
        if index + 1 < len(lines) and _HEADING_MARK.fullmatch(lines[index + 1].strip()):
            flush_list()
            flush_session_header()
            level = {"=": 1, "-": 2, "~": 3}[lines[index + 1].strip()[0]]
            if line in {"Strategy Assessments", "Outcome metrics"}:
                level = 4
            elif line in {"Operational metrics", "Research-quality metrics"}:
                level = 5
            if not (level == 1 and line == title):
                if level == 2:
                    close_session()
                    if section_open:
                        blocks.append("</section>")
                    blocks.append('<section class="report-section">')
                    section_open = True
                heading_class = "report-subheading" if level == 4 else "report-heading"
                blocks.append(f'<h{level} class="{heading_class}">{_html_inline(line)}</h{level}>')
            index += 2
            if line in {"Operational metrics", "Research-quality metrics"}:
                metric_rows: list[tuple[str, str]] = []
                while index < len(lines) and lines[index].strip():
                    label, separator, value = lines[index].partition(": ")
                    if separator:
                        metric_rows.append((label, value))
                    index += 1
                if metric_rows:
                    blocks.append(
                        '<dl class="report-outcome-metrics">'
                        + "".join(
                            f"<div><dt>{_html_inline(label)}</dt><dd>{_html_inline(value)}</dd></div>"
                            for label, value in metric_rows
                        )
                        + "</dl>"
                    )
            if line == "Strategy Assessments":
                rows: list[tuple[str, str, str, str]] = []
                while index < len(lines) and lines[index].strip():
                    row = re.match(
                        r"(.+?) · ([^:]+): (.*?) \[Evidence: (.*?)\]$", lines[index].strip()
                    )
                    if row:
                        groups = row.groups()
                        if len(groups) == 4:
                            rows.append((groups[0], groups[1], groups[2], groups[3]))
                    index += 1
                if rows:
                    cells = "".join(
                        "<tr>"
                        + "".join(f"<td>{_html_inline(value)}</td>" for value in row)
                        + "</tr>"
                        for row in rows
                    )
                    blocks.append(
                        '<div class="table-scroll"><table class="report-assessment-table"><colgroup><col><col><col><col></colgroup><thead><tr><th>Strategy</th><th>Assessment</th><th>Rationale</th><th>Evidence</th></tr></thead><tbody>'
                        + cells
                        + "</tbody></table></div>"
                    )
            continue
        if re.match(r"^Session #\S+", line):
            flush_list()
            close_session()
            blocks.append('<article class="report-session">')
            session_open = True
            session_header_open = True
            blocks.append('<header class="report-session-header">')
            blocks.append(f'<h3 class="report-record-heading">{_html_inline(line)}</h3>')
            index += 1
            continue
        if session_header_open:
            label, separator, value = line.partition(": ")
            if separator and label in {"Execution status", "Outcome", "Strategy", "Started"}:
                session_facts.append((label, value))
                index += 1
                continue
            flush_session_header()
        if re.match(r"^Artifact \d+ ·", line):
            flush_list()
            blocks.append(f'<h4 class="report-artifact-heading">{_html_inline(line)}</h4>')
            index += 1
            continue
        if re.match(r"^Run \S+", line):
            flush_list()
            close_session()
            blocks.append(f'<h3 class="report-record-heading">{_html_inline(line)}</h3>')
            index += 1
            continue
        bullet = re.match(r"^(?:[-*]|\d+[.)])\s+(.+)$", line)
        if bullet:
            list_items.append(_html_inline(bullet.group(1)))
            index += 1
            continue
        flush_list()
        label, separator, value = line.partition(": ")
        if separator and len(label) < 60 and re.fullmatch(r"[\w ·#-]+", label):
            paragraph_class = "report-note" if label == "Interpretation" else "report-field"
            blocks.append(
                f'<p class="{paragraph_class}"><strong>{html.escape(label)}:</strong> '
                f"{_html_inline(value)}</p>"
            )
        else:
            blocks.append(f'<p class="report-paragraph">{_html_inline(line)}</p>')
        index += 1
    flush_list()
    close_session()
    if section_open:
        blocks.append("</section>")
    body = "\n".join(blocks)
    css = """
      *{box-sizing:border-box}
      :root{color-scheme:light;--ink:#23313b;--muted:#65737d;--navy:#0b1b29;--blue:#24485e;--copper:#b77943;--line:#dbe2e5;--paper:#fff;--canvas:#edf1f2}
      body{margin:0;background:var(--canvas);color:var(--ink);font:16px/1.72 Georgia,"Iowan Old Style","Palatino Linotype",serif}
      .report{width:min(960px,calc(100% - 40px));margin:42px auto;background:var(--paper);border:1px solid #d6dfe2;border-radius:12px;box-shadow:0 18px 60px #18304018;overflow:hidden}
      .report-header{position:relative;padding:52px 68px 46px;background:linear-gradient(125deg,#0a1927,#183348 72%,#24475c);border-bottom:4px solid var(--copper);color:#f7f2ea}
      .report-header:after{position:absolute;right:68px;bottom:22px;width:76px;height:1px;background:linear-gradient(90deg,transparent,#d7a36d);content:""}
      .report-kicker{margin:0 0 16px;color:#e3b37d;font:600 11px/1.4 system-ui,sans-serif;letter-spacing:.2em;text-transform:uppercase}
      h1{max-width:760px;margin:0;color:#fff8ee;font:400 clamp(2rem,4vw,3rem)/1.12 Georgia,"Iowan Old Style",serif;letter-spacing:-.025em;overflow-wrap:anywhere}
      .report-subtitle{margin:18px 0 0;color:#bfd0d9;font:13px/1.5 system-ui,sans-serif;letter-spacing:.04em}
      .report-content{padding:12px 68px 64px}
      .report-section{padding:24px 0 12px;border-bottom:1px solid var(--line)}
      .report-section:last-child{border-bottom:0}
      .report-heading{color:var(--navy);font-family:Georgia,"Iowan Old Style",serif;font-weight:400;line-height:1.25}
      h2.report-heading{margin:0 0 22px;padding:0 0 13px;border-bottom:1px solid var(--line);font-size:1.65rem;letter-spacing:-.015em}
      h2.report-heading:before{display:block;width:34px;height:3px;margin:0 0 13px;background:var(--copper);content:""}
      h3.report-heading,.report-record-heading{margin:28px 0 10px;color:var(--blue);font:600 1.08rem/1.4 system-ui,sans-serif;overflow-wrap:anywhere}
      h3.report-heading{padding-bottom:8px;border-bottom:1px solid #e7ecee}
      .report-session{margin:26px 0 34px;padding:0 22px 20px;border:1px solid var(--line);border-radius:10px;background:linear-gradient(180deg,#fbfcfc,#fff);box-shadow:0 3px 12px #18304008}
      .report-session-header{display:block;margin:0 -22px 20px;padding:16px 20px 17px;border-bottom:1px solid var(--line);border-left:3px solid var(--copper);border-radius:9px 9px 0 0;background:#f4f6f6}
      .report-session .report-record-heading{margin:0 0 14px;color:var(--navy);font:600 1.18rem/1.3 system-ui,sans-serif;overflow-wrap:anywhere}
      .report-session-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px 24px;margin:0}
      .report-outcome-metrics{margin:8px 0 18px;font:13px/1.5 system-ui,sans-serif}
      .report-outcome-metrics div{margin:8px 0;overflow-wrap:anywhere}
      .report-outcome-metrics dt{color:var(--muted);font-weight:600}
      .report-outcome-metrics dd{margin:2px 0 0}
      .report-session-fact{min-width:0}
      .report-session-fact-wide{grid-column:1/-1}
      .report-session-fact dt{margin:0 0 3px;color:var(--muted);font:700 10px/1.4 system-ui,sans-serif;letter-spacing:.09em;text-transform:uppercase}
      .report-session-value{margin:0;color:var(--ink);font:500 13px/1.5 system-ui,sans-serif;overflow-wrap:anywhere}
      .report-session-value.report-status-ended{color:#426d5a}
      .report-session-value.report-status-active{color:#825b28}
      .report-session-value.report-outcome-positive{color:#286447;font-weight:700}
      .report-session-value.report-outcome-negative{color:#9b403c;font-weight:700}
      .report-session-value.report-outcome-mixed{color:#825b28;font-weight:700}
      .report-subheading{margin:25px 0 9px;padding-top:14px;border-top:1px solid #e7ecee;color:#775532;font:700 .74rem/1.4 system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase}
      .report-artifact-heading{margin:28px 0 8px;padding-top:12px;border-top:1px solid var(--line);color:var(--blue);font:600 .95rem/1.45 system-ui,sans-serif;overflow-wrap:anywhere}
      .report-paragraph,.report-field{margin:10px 0;overflow-wrap:anywhere}
      .report-field strong{display:inline-block;margin-right:.35em;color:#5b4937;font:700 .76em/1.5 system-ui,sans-serif;letter-spacing:.06em}
      .report-note{margin:0 0 24px;padding:14px 18px;border-left:3px solid #6d94a5;background:#f1f6f7;color:#455762;font:13px/1.6 system-ui,sans-serif}
      p{orphans:3;widows:3}
      ul{margin:10px 0 18px;padding-left:1.4em}
      li{margin:.4em 0;padding-left:.2em}
      li::marker{color:var(--copper)}
      code{padding:.12em .35em;border:1px solid #e2e7e9;border-radius:4px;background:#f4f6f6;color:#274052;font: .88em/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}
      .report-math{color:#183a50;font:italic 1.06em Georgia,serif;white-space:normal}
      .table-scroll{max-width:100%;margin:18px 0 24px;overflow-x:auto;border:1px solid var(--line);border-radius:7px}
      table{width:100%;border-collapse:collapse;font:13px/1.55 system-ui,sans-serif}
      .report-assessment-table{min-width:680px;table-layout:fixed}
      .report-assessment-table col:nth-child(1){width:17%}
      .report-assessment-table col:nth-child(2){width:15%}
      .report-assessment-table col:nth-child(3){width:44%}
      .report-assessment-table col:nth-child(4){width:24%}
      th,td{text-align:left;vertical-align:top;padding:11px 13px;border-bottom:1px solid var(--line);overflow-wrap:anywhere}
      th{background:var(--navy);color:#f1c58d;font-size:11px;letter-spacing:.07em;text-transform:uppercase}
      tbody tr:nth-child(even){background:#f6f8f8}
      tbody tr:last-child td{border-bottom:0}
      @media(max-width:640px){.report{width:100%;margin:0;border:0;border-radius:0;box-shadow:none}.report-header{padding:36px 25px 32px}.report-header:after{right:25px}.report-content{padding:8px 25px 40px}.report-section{padding-top:20px}.report-session{padding:0 16px 14px}.report-session-header{margin-inline:-16px;padding-inline:16px}.report-session-meta{gap:10px 14px}.report-session-fact-wide{grid-column:1/-1}h2.report-heading{font-size:1.45rem}}
      @media print{body{background:#fff;color:#111;font-size:10.5pt}.report{width:auto;margin:0;border:0;border-radius:0;box-shadow:none;overflow:visible}.report-header{padding:0 0 20pt;background:#fff;color:#111;border-bottom:2pt solid #a76d3d;print-color-adjust:exact;-webkit-print-color-adjust:exact}.report-header:after{display:none}.report-kicker{color:#76502f}.report-header h1{color:#111;font-size:25pt}.report-subtitle{color:#555}.report-content{padding:0}.report-section{padding:18pt 0 8pt;break-inside:auto}.report-session{break-inside:auto;border-color:#aaa;background:#fff}.report-heading,.report-record-heading,.report-subheading,.report-artifact-heading{break-after:avoid}.report-note,.report-record-heading,th{print-color-adjust:exact;-webkit-print-color-adjust:exact}.table-scroll{overflow:visible;border:0}table{font-size:9pt}th{background:#e8edf0;color:#162d3b}.report-record-heading{break-after:avoid}}
    """
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'
        f"{html.escape(title, quote=True)} — Research Report</title><style>{css}</style></head><body>"
        '<main class="report"><header class="report-header"><p class="report-kicker">SIGMA · Research report</p>'
        f'<h1>{html.escape(title)}</h1><p class="report-subtitle">Project record and research evidence</p></header>'
        f'<div class="report-content">{body}</div></main></body></html>\n'
    )


def _latex_inline(text: str) -> str:
    """Escape prose; preserve only a bounded set of commands inside math spans."""
    commands = {
        "frac",
        "sqrt",
        "mathrm",
        "mathbf",
        "mathbb",
        "infty",
        "cdot",
        "times",
        "le",
        "leq",
        "ge",
        "geq",
        "neq",
        "approx",
        "sum",
        "prod",
        "int",
        "alpha",
        "beta",
        "gamma",
        "Delta",
        "theta",
        "pi",
        "forall",
        "exists",
        "in",
        "notin",
        "left",
        "right",
    }
    out: list[str] = []
    cursor = 0
    for match in _INLINE_MATH.finditer(text):
        out.append(_latex(text[cursor : match.start()]))
        token = match.group(0)
        display = token.startswith(("$$", r"\["))
        body = (
            token[2:-2]
            if token.startswith("$$")
            else token[2:-2]
            if token.startswith((r"\(", r"\["))
            else token[1:-1]
        )
        safe = re.sub(
            r"\\([A-Za-z]+)",
            lambda cmd: (
                cmd.group(0)
                if cmd.group(1) in commands
                else r"\textbackslash{}" + _latex(cmd.group(1))
            ),
            body,
        )
        safe = safe.replace("%", r"\%").replace("&", r"\&").replace("#", r"\#")
        out.append((r"\[" + safe + r"\]") if display else ("$" + safe + "$"))
        cursor = match.end()
    out.append(_latex(text[cursor:]))
    return "".join(out)


def _latex_document(data: dict[str, Any], lines: list[str]) -> str:
    project_raw = data.get("project")
    project = cast(dict[str, Any], project_raw) if isinstance(project_raw, dict) else {}
    title = str(project.get("title") or "Research report")
    output = [
        "% Generated by SIGMA; compile with Tectonic or another TeX engine.",
        r"\documentclass[11pt]{article}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{amsmath,amssymb,booktabs,longtable}",
        r"\usepackage{array}",
        r"\usepackage{enumitem}",
        r"\setlist{nosep,leftmargin=*}",
        r"\usepackage{microtype}",
        r"\usepackage{titlesec}",
        r"\usepackage{xcolor}",
        r"\definecolor{blue}{HTML}{24485E}",
        r"\titleformat{\section}{\Large\bfseries\sffamily\color{blue}}{\thesection}{0.8em}{}",
        r"\titleformat{\subsection}{\large\bfseries\sffamily}{\thesubsection}{0.7em}{}",
        r"\titleformat{\subsubsection}{\normalsize\bfseries\sffamily\color{blue}}{\thesubsubsection}{0.6em}{}",
        r"\setlength{\parskip}{0.55em}",
        r"\setlength{\parindent}{0pt}",
        r"\title{" + _latex(title) + r"}",
        r"\author{SIGMA Research Record}",
        r"\date{\today}",
        r"\begin{document}",
        r"\maketitle",
        r"\begin{quote}\small In the future we plan on using AI to produce a typical academic paper based on the results of the research.\end{quote}",
    ]
    index = 2
    items: list[str] = []
    session_metadata_open = False

    def flush_list() -> None:
        if items:
            output.append(r"\begin{itemize}")
            output.extend(r"\item " + item for item in items)
            output.append(r"\end{itemize}")
            items.clear()

    while index < len(lines):
        line = lines[index].strip()
        if not line:
            flush_list()
            index += 1
            continue
        if re.match(r"^Session #\S+", line):
            flush_list()
            if session_metadata_open:
                output.append(r"\end{description}")
            output.append(r"\subsection{" + _latex_inline(line) + "}")
            output.append(
                r"\begin{description}[style=nextline,font=\normalfont\bfseries,leftmargin=0pt,labelsep=0pt]"
            )
            session_metadata_open = True
            index += 1
            continue
        if session_metadata_open:
            label, separator, value = line.partition(": ")
            if separator and label in {"Execution status", "Outcome", "Strategy", "Started"}:
                output.append(r"\item[" + _latex(label) + "] " + _latex_inline(value))
                index += 1
                continue
            output.append(r"\end{description}")
            session_metadata_open = False
        if re.match(r"^Artifact \d+ ·", line):
            flush_list()
            output.append(r"\paragraph{" + _latex_inline(line) + "}")
            index += 1
            continue
        if index + 1 < len(lines) and _HEADING_MARK.fullmatch(lines[index + 1].strip()):
            flush_list()
            marker = lines[index + 1].strip()[0]
            command = {"=": r"\section", "-": r"\section", "~": r"\subsection"}[marker]
            if line == "Strategy Assessments":
                output.append(r"\subsubsection*{Strategy assessments}")
            elif not (marker == "=" and line == title):
                output.append(command + "{" + _latex_inline(line) + "}")
            index += 2
            if line == "Strategy Assessments":
                rows: list[tuple[str, str, str, str]] = []
                while index < len(lines) and lines[index].strip():
                    row = re.match(
                        r"(.+?) · ([^:]+): (.*?) \[Evidence: (.*?)\]$", lines[index].strip()
                    )
                    if row:
                        groups = row.groups()
                        if len(groups) == 4:
                            rows.append((groups[0], groups[1], groups[2], groups[3]))
                    index += 1
                if rows:
                    output.extend(
                        [
                            r"\begin{longtable}{>{\raggedright\arraybackslash}p{.16\linewidth}>{\raggedright\arraybackslash}p{.15\linewidth}>{\raggedright\arraybackslash}p{.40\linewidth}>{\raggedright\arraybackslash}p{.17\linewidth}}",
                            r"\toprule Strategy & Assessment & Rationale & Evidence " + r"\\",
                            r"\midrule\endhead",
                        ]
                    )
                    for row in rows:
                        output.append(" & ".join(_latex_inline(value) for value in row) + r" \\")
                    output.extend([r"\bottomrule", r"\end{longtable}"])
            continue
        bullet = re.match(r"^(?:[-*]|\d+[.)])\s+(.+)$", line)
        if bullet:
            items.append(_latex_inline(bullet.group(1)))
            index += 1
            continue
        flush_list()
        label, separator, value = line.partition(": ")
        if separator and len(label) < 60 and re.fullmatch(r"[\w ·#-]+", label):
            output.append(r"\textbf{" + _latex(label + ":") + "} " + _latex_inline(value) + r"\par")
        else:
            output.append(_latex_inline(line) + r"\par")
        index += 1
    flush_list()
    if session_metadata_open:
        output.append(r"\end{description}")
    output.append(r"\end{document}")
    return "\n".join(output) + "\n"


def _compile_pdf(tex: str) -> bytes:
    executable = shutil.which(os.environ.get("SIGMA_TECTONIC", "tectonic"))
    if not executable:
        raise RuntimeError(
            "PDF export requires Tectonic. Install Tectonic and retry; no file was downloaded."
        )
    with tempfile.TemporaryDirectory(prefix="sigma-report-") as directory:
        if len(tex.encode("utf-8")) > 2_000_000:
            raise RuntimeError(
                "Research report is too large to typeset (2 MB limit). No file was downloaded."
            )
        source = os.path.join(directory, "report.tex")
        with open(source, "w", encoding="utf-8") as file:
            file.write(tex)
        state_dir = os.environ.get(
            "SIGMA_STATE_DIR", os.path.join(os.path.expanduser("~"), ".sigma")
        )
        cache_dir = os.path.join(state_dir, "tectonic-cache")
        os.makedirs(cache_dir, mode=0o700, exist_ok=True)
        environment = {
            "PATH": os.path.dirname(executable),
            "HOME": os.path.expanduser("~"),
            "XDG_CACHE_HOME": cache_dir,
            "TECTONIC_UNTRUSTED_MODE": "1",
            "LANG": "C.UTF-8",
        }
        try:
            result = subprocess.run(
                [executable, "--untrusted", "--outdir", directory, source],
                cwd=directory,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=45,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "PDF compilation exceeded 45 seconds. No file was downloaded."
            ) from exc
        pdf_path = os.path.join(directory, "report.pdf")
        if result.returncode != 0 or not os.path.isfile(pdf_path):
            detail = result.stdout.decode("utf-8", "replace")[-1200:]
            raise RuntimeError(
                "Tectonic could not compile this report. No PDF was downloaded. " + detail
            )
        with open(pdf_path, "rb") as file:
            pdf = file.read(20_000_001)
        if not pdf.startswith(b"%PDF-") or len(pdf) > 20_000_000:
            raise RuntimeError(
                "PDF compiler output was invalid or exceeded 20 MB. No file was downloaded."
            )
        return pdf


def render_report(data: dict[str, Any], output_format: str) -> tuple[str | bytes, str]:
    """Return UTF-8 report text and MIME type; unknown optional fields are ignored."""
    if output_format not in {"txt", "html", "tex", "pdf"}:
        raise ValueError("Report format must be txt, html or pdf")
    lines = _report_lines(data)
    body = "\n".join(lines).rstrip() + "\n"
    if output_format == "txt":
        return body, "text/plain; charset=utf-8"
    if output_format == "html":
        return _html_document(data, lines), "text/html; charset=utf-8"
    tex = _latex_document(data, lines)
    if output_format == "tex":
        return tex, "application/x-tex; charset=utf-8"
    return _compile_pdf(tex), "application/pdf"
