"""Pre-investigation selection of readable research-method references.

This module contains short, independently authored *method notes* derived from
publicly readable HTML chapters, not scraped or model-invented quotations.
Selections are from an explicitly vetted catalog: no provider request, third-
party fetch, network credentials, or website availability can block research.
A source is not primary evidence about the subject under investigation.

The selection is re-evaluated when the project question/branch changes; for
compatible later sessions the most recent vetted selection is reused.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

CATALOG_VERSION = "methodology-catalog-v1"
MAX_SOURCES = 3
# IDs and notes have been individually source-checked against readable HTML.
# "notes" are concise method implications written by the SIGMA coordinator.
CATALOG: tuple[dict[str, str], ...] = (
    {
        "id": "nasem-scientific-methods",
        "tier": "general",
        "title": "NASEM — Scientific Methods and Knowledge, chapter 2",
        "url": "https://www.nationalacademies.org/read/25303/chapter/5",
        "notes": "Specify the question, explicit assumptions, observation and inference standard. Distinguish discovery from independent confirmation; state uncertainty and corrections. Reproducible calculation is not independent replication.",
    },
    {
        "id": "tao-solving-mathematical-problems",
        "tier": "discipline",
        "mode": "mathematical",
        "title": "Terence Tao — Solving Mathematical Problems",
        "url": "https://terrytao.wordpress.com/career-advice/solving-mathematical-problems/",
        "notes": "Explore meaningful special cases and modified assumptions, then seek a proof with explicit hypotheses. Partial progress is useful; understanding the mechanism matters beyond obtaining a candidate answer.",
    },
    {
        "id": "nasem-physical-models",
        "tier": "discipline",
        "mode": "physics",
        "title": "NASEM — Assessing Reliability of Complex Models, Summary",
        "url": "https://www.nationalacademies.org/read/13395/chapter/2",
        "notes": "Identify physical quantity of interest; separate numerical verification, model-to-observation validation and uncertainty quantification. A mathematically consistent model does not itself demonstrate physical reality.",
    },
    {
        "id": "nc3rs-experimental-design",
        "tier": "discipline",
        "mode": "biology",
        "title": "NC3Rs — Experimental Design",
        "url": "https://eda.nc3rs.org.uk/experimental-design",
        "notes": "For proposed biological experiments identify intervention, independent and nuisance variables, experimental unit, allocation, controls, masking and outcome measurement. Do not turn proposed tests into performed results.",
    },
    {
        "id": "acm-software-research",
        "tier": "discipline",
        "mode": "computer_science",
        "title": "ACM SIGSOFT — Empirical Standards",
        "url": "https://www2.sigsoft.org/EmpiricalStandards/docs/standards",
        "notes": "Match method to engineering question; distinguish conceptual design, mathematical assertion and actual tested implementation. Define evaluated task and evidence collection, limitations and appropriate comparators.",
    },
    {
        "id": "nasa-systems-handbook",
        "tier": "discipline",
        "mode": "engineering",
        "title": "NASA Systems Engineering Handbook — 6.8 Decision Analysis",
        "url": "https://www.nasa.gov/reference/6-8-decision-analysis/",
        "notes": "Compare feasible alternatives against a common requirement and measurable acceptance criterion. Separate proposed design, analytical bound, implementation feasibility, risks and residual uncertainty.",
    },
    {
        "id": "nist-experimental-selection",
        "tier": "discipline",
        "mode": "economics",
        "title": "NIST/SEMATECH — Selecting an Experimental Design",
        "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri33.htm",
        "notes": "Choose a comparative, screening or response-surface design according to the actual inference objective. State denominators, important factors and uncertainty before interpreting effects.",
    },
    {
        "id": "stanford-abduction",
        "tier": "discipline",
        "mode": "default",
        "title": "Stanford Encyclopedia — Abduction",
        "url": "https://plato.stanford.edu/entries/abduction/",
        "notes": "Inference to the best available explanation is not deductive proof. Develop serious alternatives and specify what observation would discriminate them.",
    },
    {
        "id": "applied-combinatorics",
        "tier": "branch",
        "branch": "combinatorics",
        "mode": "mathematical",
        "title": "Oscar Levin — Generating Functions (open HTML textbook)",
        "url": "https://discrete.openmathbooks.org/dmoi4/sec_addtops-genfun.html",
        "notes": "For finite counting use a bijection, generating function or recurrence only when its interpretation is derived. Verify initial conditions, weighted identities and exact finite cases; distinguish computationally fitted identities from global proof.",
    },
    {
        "id": "tong-einstein-equations",
        "tier": "branch",
        "branch": "relativity",
        "mode": "physics",
        "title": "David Tong — General Relativity, §4 Einstein Equations",
        "url": "https://davidtong.org/teaching/general-relativity/grhtml/S4.html",
        "notes": "In a spacetime metric project distinguish a prescribed geometry from a stress-energy source satisfying field equations. Track signature, coordinate choices, causal structure, conservation, and assumptions behind physical matter interpretations.",
    },
    {
        "id": "nc3rs-experimental-unit",
        "tier": "branch",
        "branch": "animal-regeneration",
        "mode": "biology",
        "title": "NC3Rs — Experimental Unit",
        "url": "https://eda.nc3rs.org.uk/experimental-design-unit",
        "notes": "In animal regeneration work define whether the independent unit is an animal, tissue or pooled sample, and check pairing and repeated measures. Distinguish wound-age from time-after-intervention and assay timing.",
    },
    {
        "id": "acm-engineering-method",
        "tier": "branch",
        "branch": "ai-reliability",
        "mode": "computer_science",
        "title": "ACM SIGSOFT — Engineering Research",
        "url": "https://www2.sigsoft.org/EmpiricalStandards/docs/standards",
        "notes": "For AI-agent reliability specify external ground-truth oracle, fault and retry model, observation horizon and task sampling. A proposed reliability test is not an executed benchmark; acceptance by an evaluator is not necessarily correctness.",
    },
    {
        "id": "nasa-federation-decisions",
        "tier": "branch",
        "branch": "federation",
        "mode": "computer_science",
        "title": "NASA — 6.8 Decision Analysis",
        "url": "https://www.nasa.gov/reference/6-8-decision-analysis/",
        "notes": "When designing federated computing systems compare feasible local, gateway, approved external and federation alternatives against common authorized tasks. Apply cost-benefit, sensitivity, constraints, and decision thresholds; report unknown source policies and implementation limits.",
    },
    {
        "id": "nist-comparative-design",
        "tier": "branch",
        "branch": "federation",
        "mode": "engineering",
        "title": "NIST/SEMATECH — Comparative Design",
        "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri33.htm",
        "notes": "For federation or system routing compare plausible authorized alternatives on the same parent-task success and cost unit. Include failure/partition assumptions, subgroup fairness, and an explicit result that would reverse the decision.",
    },
)

BY_ID = {row["id"]: row for row in CATALOG}
# Only identify problem branch to select a *method reference*, never treat
# branch-keyword matches as verified scientific facts or pre-solved results.
BRANCH_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("mathematical", "combinatorics", re.compile(
        r"\b(subsets?|combinatoric\w*|counting|generating function|recurrence|modulo|fibonacci|graph enumerat\w*)\b", re.I
    )),
    ("physics", "relativity", re.compile(
        r"\b(warp|spacetime|metric|relativit\w*|einstein|superluminal|ftl|stress.energy)\b", re.I
    )),
    ("biology", "animal-regeneration", re.compile(
        r"\b(tadpole\w*|xenopus|regenerat\w*|wound|tail|erk|animal)\b", re.I
    )),
    ("computer_science", "federation", re.compile(
        r"\b(federat\w*|sovereign\w*|gateway|campus|revocation|quota|routing)\b", re.I
    )),
    ("computer_science", "ai-reliability", re.compile(
        r"\b(agent\w*|retr(?:y|ies)|external effect|reliab\w*|checkpoint|acknowledg\w*)\b", re.I
    )),
    ("engineering", "federation", re.compile(
        r"\b(federat\w*|sovereign\w*|gateway|campus|revocation|quota|routing)\b", re.I
    )),
)


def _usable(row: Mapping[str, Any]) -> bool:
    """Never select a broken/unreadable or metadata-only catalog record."""
    return (
        isinstance(row.get("id"), str)
        and isinstance(row.get("title"), str) and len(row["title"]) >= 10
        and isinstance(row.get("url"), str) and row["url"].startswith("https://")
        and isinstance(row.get("notes"), str) and len(row["notes"]) >= 50
        and len(row["notes"]) <= 900
    )


def _branch(mode: str, title: str, text: str) -> str | None:
    """Prefer the project's declared topic over incidental method keywords."""
    ranked: list[tuple[int, int, str]] = []
    for order, (kind, specialty, expression) in enumerate(BRANCH_PATTERNS):
        if kind != mode:
            continue
        # Count distinct topical evidence, heavily weighting project title.
        # E.g. an AI agent reliability study mentioning a gateway as an
        # implementation detail must not become a federation methods study.
        title_hits = len({m.group().casefold() for m in expression.finditer(title)})
        context_hits = len({m.group().casefold() for m in expression.finditer(text)})
        if title_hits or context_hits:
            ranked.append((12 * title_hits + context_hits, -order, specialty))
    return max(ranked)[2] if ranked else None


def _source(row: Mapping[str, str]) -> dict[str, str]:
    # Keep the actual usable methodological note with its source, not just URL.
    return {key: row[key] for key in ("id", "tier", "title", "url", "notes")} | (
        {"branch": row["branch"]} if row.get("branch") else {}
    )


def _complete(ids: list[str], mode: str, branch: str | None) -> bool:
    if not 2 <= len(ids) <= MAX_SOURCES or len(set(ids)) != len(ids):
        return False
    rows = [BY_ID.get(i) for i in ids]
    if any(row is None or not _usable(row) for row in rows):
        return False
    assert all(row is not None for row in rows)
    levels = {r["tier"] for r in rows}
    if not {"general", "discipline"} <= levels:
        return False
    if any(
        (r["tier"] == "discipline" and r.get("mode") not in {mode, "default"})
        or (r["tier"] == "branch" and (r.get("mode") != mode or r.get("branch") != branch))
        for r in rows
    ):
        return False
    if branch and any(
        row["tier"] == "branch" and row.get("branch") == branch and _usable(row)
        for row in CATALOG
    ):
        return "branch" in levels
    return True


def select_method_sources(
    mode: str,
    title: str,
    problem: str,
    strategies: Iterable[str],
    prior_sessions: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return a frozen, bounded, content-bearing selection for a *new* session.

    Last selection is reused if still usable and covers current mode+branch.
    Failed/incomplete catalog records are skipped; research never blocks.
    No external internet calls or provider billing happen in this preflight.
    """
    if not isinstance(mode, str):
        mode = "default"
    search_text = " ".join([problem, *list(strategies)])[:40_000]
    branch = _branch(mode, title, search_text)
    prior = sorted(
        (s for s in prior_sessions if isinstance(s, Mapping)),
        key=lambda s: (str(s.get("created_at") or ""), str(s.get("id") or "")),
        reverse=True,
    )
    for previous in prior:
        old = previous.get("research_method_sources")
        if not isinstance(old, Mapping) or old.get("mode") != mode or old.get("branch") != branch:
            continue
        source_rows = old.get("sources")
        if not isinstance(source_rows, list):
            continue
        ids = [s.get("id") for s in source_rows if isinstance(s, Mapping)]
        if not all(isinstance(i, str) for i in ids) or not _complete(ids, mode, branch):
            continue
        # Retain the previous *readable content*, not only source IDs:
        # later catalog copy edits must not silently change a controlled
        # multi-session research comparison. Reject unsafe/empty old rows.
        if not all(_usable(row) and row.get("tier") == BY_ID[row["id"]]["tier"]
                   for row in source_rows):
            continue
        rows = [dict(row) for row in source_rows]
        return {
            "version": CATALOG_VERSION,
            "status": "reused",
            "mode": mode,
            "branch": branch,
            "sources": rows,
            "source_session_id": previous.get("id"),
            "selection_reason": "Previous session source set remains usable and covers shared, project-type and applicable specialty methods.",
        }

    rows = [r for r in CATALOG if _usable(r)]
    selected = []
    general = next((r for r in rows if r.get("tier") == "general"), None)
    discipline = next((r for r in rows if r.get("tier") == "discipline" and r.get("mode") == mode), None)
    if discipline is None:
        discipline = next((r for r in rows if r.get("id") == "stanford-abduction"), None)
    specialty = next((r for r in rows if r.get("tier") == "branch" and r.get("branch") == branch and r.get("mode") == mode), None)
    for row in (general, discipline, specialty):
        if row and row["id"] not in {item["id"] for item in selected}:
            selected.append(_source(row))
    if len(selected) < 2:  # Safe fallback if future catalog entries become unusable.
        for row in rows:
            if row.get("tier") == "discipline" and row["id"] not in {i["id"] for i in selected}:
                selected.append(_source(row))
                break
    return {
        "version": CATALOG_VERSION,
        "status": "selected" if len(selected) >= 2 else "partial",
        "mode": mode,
        "branch": branch,
        "sources": selected[:MAX_SOURCES],
        "source_session_id": None,
        "selection_reason": "Chosen from readable coordinator-vetted method notes for this project type and detected specialty; optional unavailable candidates are skipped.",
    }


def methodology_digest(selection: Mapping[str, Any]) -> str:
    payload = json.dumps(selection.get("sources", []), sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
