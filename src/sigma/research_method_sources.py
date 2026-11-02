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
# Advisory only: do not truncate inherited or user-specified references.
RECOMMENDED_SOURCE_COUNT = 3
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


# Source information below enriches *known* URLs, but never chooses references.
# Selection comes exclusively from the unified Project Types data model.
BY_URL = {row["url"]: row for row in CATALOG}
BY_URL["https://github.com/acmsigsoft/EmpiricalStandards/blob/master/docs/standards/EngineeringResearch.md"] = {
    "id": "acm-engineering-method",
    "title": "ACM SIGSOFT — Engineering Research",
    "notes": "For software engineering distinguish conceptual designs, analytical results, tested implementations, and independently measured outcomes. Check the task, correctness oracle, and limitations.",
}
CATALOG_VERSION = "project-type-methods-v1"


def _canonical_url(url: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url)
    host = (parts.hostname or "").casefold()
    if parts.port and (parts.scheme.lower(), parts.port) not in {
        ("https", 443), ("http", 80)
    }:
        host += f":{parts.port}"
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", parts.query, ""))


def _effective_sources(project_type_id: str) -> tuple[list[dict[str, str]], str | None]:
    """Collect common + root-to-leaf Project Types references without truncation.

    Missing parents/cycles are bounded. Custom types are allowed; no keyword
    classifier can override an explicitly persisted project type.
    """
    from sigma.project_types import (
        builtin_types,
        common_research_references,
        custom_types,
    )

    definitions = {t.id: t for t in [*builtin_types(), *custom_types()]}
    chain = []
    visited: set[str] = set()
    cursor: str | None = project_type_id
    while cursor and cursor not in visited:
        visited.add(cursor)
        item = definitions.get(cursor)
        if item is None:
            break
        chain.append(item)
        cursor = item.based_on
    chain.reverse()

    seen: set[str] = set()
    sources: list[dict[str, str]] = []

    def add(url: str, tier: str, owner_id: str, owner_name: str) -> None:
        canonical = _canonical_url(url)
        if canonical in seen:
            return
        seen.add(canonical)
        known = BY_URL.get(url) or BY_URL.get(canonical)
        from urllib.parse import urlsplit

        title = known["title"] if known else (
            f"{owner_name} — {urlsplit(canonical).hostname or 'Research method'}"
        )
        notes = known["notes"] if known else (
            "Project-type reference provided by the user or catalog; its contents "
            "have not been independently inspected here. Consult the reference "
            "before attributing a prescribed method to it, and state uncertainty."
        )
        row = {
            "id": known["id"] if known else "project-type-" + hashlib.sha256(
                canonical.encode("utf-8")
            ).hexdigest()[:16],
            "tier": tier,
            "title": title,
            "url": canonical,
            "notes": notes,
            "project_type_id": owner_id,
        }
        if tier == "branch":
            row["branch"] = owner_id
        sources.append(row)

    for url in common_research_references():
        add(url, "general", "common", "Common scientific methods")
    for index, item in enumerate(chain):
        tier = "discipline" if index == 0 else "branch"
        for url in item.research_standards_references:
            add(url, tier, item.id, item.name)
    return sources, (chain[-1].id if len(chain) > 1 else None)


def select_method_sources(
    mode: str,
    title: str,
    problem: str,
    strategies: Iterable[str],
    prior_sessions: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Freeze the complete inherited reference set at session creation.

    The legacy signature is retained for callers; title/problem/strategies do
    *not* guess a methodology branch. A changed project-type reference set is
    applied on the next session, never retroactively to saved sessions.
    """
    _ = (title, problem, strategies)
    if not isinstance(mode, str):
        mode = "default"
    sources, branch = _effective_sources(mode)
    selection_key = hashlib.sha256(json.dumps(
        [{"url": row["url"], "tier": row["tier"], "type": row["project_type_id"]}
         for row in sources],
        sort_keys=True,
    ).encode("utf-8")).hexdigest()
    old_sessions = sorted(
        (item for item in prior_sessions if isinstance(item, Mapping)),
        key=lambda item: (str(item.get("created_at") or ""), str(item.get("id") or "")),
        reverse=True,
    )
    status = "selected" if sources else "unavailable"
    source_session_id = None
    for previous in old_sessions:
        old = previous.get("research_method_sources")
        if not isinstance(old, Mapping) or old.get("selection_key") != selection_key:
            continue
        old_sources = old.get("sources")
        if not isinstance(old_sources, list) or len(old_sources) != len(sources):
            continue
        if not all(
            isinstance(row, dict)
            and row.get("url") == current["url"]
            and isinstance(row.get("notes"), str)
            and isinstance(row.get("title"), str)
            for row, current in zip(old_sources, sources)
        ):
            continue
        # Preserve previously supplied exact descriptions when URLs/ancestry
        # remain unchanged; annotations can be edited without mutating history.
        sources = [dict(row) for row in old_sources]
        status = "reused"
        source_session_id = str(previous.get("id") or "")
        break
    advisory = (
        f"{len(sources)} research-method references are configured. Three or fewer "
        "is recommended for focus; all selected references will still be supplied."
        if len(sources) > RECOMMENDED_SOURCE_COUNT
        else None
    )
    return {
        "version": CATALOG_VERSION,
        "status": status,
        "mode": mode,
        "branch": branch,
        "sources": sources,
        "source_session_id": source_session_id,
        "selection_key": selection_key,
        "advisory": advisory,
        "selection_reason": (
            "Resolved common and inherited Project Types research references; "
            "all references are retained, with three as a nonbinding recommendation."
        ),
    }


def methodology_digest(selection: Mapping[str, Any]) -> str:
    payload = json.dumps(
        selection.get("sources", []), sort_keys=True, ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
