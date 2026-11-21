"""Provisional mathematical proof map for the Alpöge RH exposition.

Sections are ordered in conceptual prerequisite-to-conclusion flow. Every edge
is an interpretation of the supplementary proof guide, NOT a
machine-extracted dependency. IDs are stable dossier section identifiers.
"""

from __future__ import annotations

from sigma import lean_explorer
from sigma.projects import ProjectError

GUIDE_URL = (
    "https://github.com/nasqret/riemann-rev/blob/"
    + lean_explorer.GUIDE_SHA
    + "/guide/proof-guide.tex"
)

_SECTIONS = [
    {
        "id": "automorphic-foundation",
        "title": "Automorphic and Galois-theoretic foundations",
        "question": "Which representation-theoretic inputs make the theta and cohomological arguments possible?",
        "purpose": "Trace the automorphic/Galois inputs and the assumptions used by the later constructions.",
        "guide_section": 7,
        "guide_lines": [597, 635],
        "declaration_hints": [],
    },
    {
        "id": "iwasawa-windows",
        "title": "Iwasawa theory and cohomological windows",
        "question": "What is the cost of divisibility, and why can that cost be controlled on whole windows?",
        "purpose": "Explain cohomological losses, Iwasawa-theoretic bounds, exceptional twists, and interval avoidance.",
        "guide_section": 6,
        "guide_lines": [546, 594],
        "declaration_hints": ["VWinAt"],
    },
    {
        "id": "theta-slopes",
        "title": "Theta-lift chains, divisibility and slopes",
        "question": "How can repeated theta lifts mimic Stepanov multiplicity and create a square-root estimate?",
        "purpose": "Connect local divisibility, integral theta lifts, archimedean periods, and Bost's slope inequality.",
        "guide_section": 4,
        "guide_lines": [349, 473],
        "declaration_hints": ["TopG"],
    },
    {
        "id": "character-averaging",
        "title": "Character averaging and arithmetic hosts",
        "question": "How can a bound for many characters become the positive estimate we actually need?",
        "purpose": "Explain Fourier averaging, auxiliary primes, positive weights, thick sets, and uniform windows.",
        "guide_section": 5,
        "guide_lines": [476, 543],
        "declaration_hints": [],
    },
    {
        "id": "prime-statistics",
        "title": "Prime sums and Mellin transforms",
        "question": "Which prime statistic exposes a zeta zero as a pole, and why this normalization?",
        "purpose": "Define smoothed von Mangoldt sums, their centering, and Mellin transforms.",
        "guide_section": 2,
        "guide_lines": [254, 281],
        "declaration_hints": [],
    },
    {
        "id": "localized-landau",
        "title": "Localized Landau zero exclusion",
        "question": "Why do one-sided estimates on distant windows rule out off-line zeros?",
        "purpose": "Reconstruct the positive-family residues, high-derivative localization, and order of quantifiers.",
        "guide_section": 3,
        "guide_lines": [284, 346],
        "declaration_hints": [],
    },
    {
        "id": "reflection",
        "title": "Reflection and the final conclusion",
        "question": "Why is exclusion of zeros to the right of the critical line sufficient?",
        "purpose": "Explain the transition from a zero-free right half-plane to RH and Dirichlet GRH.",
        "guide_section": 1,
        "guide_lines": [233, 251],
        "declaration_hints": ["RiemannHypothesis", "RiemannZetaZerosOnLine"],
    },

]

# Arrows describe a proposed *mathematical flow*, not formal proof-term references.
_CONNECTIONS = [
    {
        "from": "automorphic-foundation",
        "to": "iwasawa-windows",
        "why": "Arithmetic representation inputs support cohomological controls.",
    },
    {
        "from": "automorphic-foundation",
        "to": "theta-slopes",
        "why": "Automorphic and period inputs underpin the theta-lift construction.",
    },
    {
        "from": "iwasawa-windows",
        "to": "theta-slopes",
        "why": "Cohomological estimates control divisibility losses.",
    },
    {
        "from": "theta-slopes",
        "to": "character-averaging",
        "why": "The chain yields estimates that require character selection and averaging.",
    },
    {
        "from": "character-averaging",
        "to": "localized-landau",
        "why": "A positive-family window bound supplies the analytic hypothesis.",
    },
    {
        "from": "prime-statistics",
        "to": "localized-landau",
        "why": "Mellin poles and their residues detect zeros.",
    },
    {
        "from": "localized-landau",
        "to": "reflection",
        "why": "Right-half-plane zero exclusion and the functional equation imply the final result.",
    },
]


def section(identifier: str) -> dict:
    if not isinstance(identifier, str):
        raise ProjectError("Invalid mathematical section identifier.")
    for entry in _SECTIONS:
        if entry["id"] == identifier:
            return dict(entry)
    raise ProjectError("Select an existing mathematical section in the provisional proof map.")


def catalog() -> dict:
    return {
        "title": "A provisional mathematical map of Alpöge's announced RH argument",
        "status": "interpretive_not_lean_verified",
        "derived_from": {
            "title": "The proof of the Riemann hypothesis announced by L. Alpöge: a guide to its architecture",
            "repository": lean_explorer.GUIDE,
            "revision": lean_explorer.GUIDE_SHA,
            "url": GUIDE_URL,
        },
        "primary_formal_source": {
            "repository": lean_explorer.MIRROR,
            "revision": lean_explorer.MIRROR_SHA,
        },
        "warning": (
            "The sections and their connections are provisional mathematical "
            "interpretations, not Lean-derived theorem dependency edges. "
            "The formal dependency graph has not yet been extracted."
        ),
        "sections": [
            {
                **item,
                "status": "unverified_guide_interpretation",
                "guide_url": GUIDE_URL + "#L" + str(item["guide_lines"][0]),
            }
            for item in _SECTIONS
        ],
        "connections": [
            {**edge, "status": "interpretive_not_machine_verified"} for edge in _CONNECTIONS
        ],
    }
