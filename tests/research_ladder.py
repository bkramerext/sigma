"""Validate the answer-free Riemann research ladder and its finite math fixtures."""

import json
import math
import tempfile
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from sigma import recents, samples

ROOT = Path(__file__).resolve().parents[1]
LADDER = (
    ("handshake-count-easy", "easy", 1),
    ("euler-product-primes", "medium", 2),
    ("alternating-zeta-boundary", "hard", 2),
    ("theta-functional-equation", "hard", 2),
    ("riemann-hypothesis-research", "hard", 3),
)


def finite_euler_products(primes: tuple[int, ...], cutoff: int) -> set[int]:
    """Enumerate integers represented by a finite geometric Euler product."""
    values = {1}
    for prime in primes:
        powers = []
        value = prime
        while value <= cutoff:
            powers.append(value)
            value *= prime
        values |= {
            existing * power
            for existing in tuple(values)
            for power in powers
            if existing * power <= cutoff
        }
    return values


def eta_pair_identity(power: int, pairs: int) -> bool:
    """Check the exact finite even/odd split using rational arithmetic."""
    alternating = sum(
        (Fraction((-1) ** (number - 1), number**power) for number in range(1, 2 * pairs + 1)),
        Fraction(),
    )
    harmonic_even = sum(
        (Fraction(1, number**power) for number in range(1, 2 * pairs + 1)), Fraction()
    )
    harmonic_half = sum((Fraction(1, number**power) for number in range(1, pairs + 1)), Fraction())
    return alternating == harmonic_even - Fraction(2, 2**power) * harmonic_half


def theta_partial(value: float, cutoff: int = 12) -> float:
    return sum(
        math.exp(-math.pi * number * number * value) for number in range(-cutoff, cutoff + 1)
    )


def main() -> None:
    catalog = {item["id"]: item for item in samples.sample_projects()["projects"]}
    with tempfile.TemporaryDirectory(prefix="sigma-rh-ladder-") as temporary:
        project_root = Path(temporary) / "projects"
        state_root = Path(temporary) / "state"
        project_root.mkdir(mode=0o700)
        state_root.mkdir(mode=0o700)
        with (
            patch.object(samples, "projects_root", lambda: project_root),
            patch.object(recents, "state_directory", lambda: state_root),
        ):
            for identifier, difficulty, strategy_count in LADDER:
                raw, entry = samples._load(identifier)
                assert entry.difficulty == difficulty
                assert entry.investigation_type == "mathematical"
                assert len(raw["strategies"]) == strategy_count
                assert catalog[identifier]["strategy_count"] == strategy_count
                assert len({strategy["id"] for strategy in raw["strategies"]}) == strategy_count
                for strategy in raw["strategies"]:
                    assert strategy["author_kind"] == "human"
                    assert len(strategy["approach"]) > 100
                if identifier == "handshake-count-easy":
                    supplied_text = json.dumps(
                        {"problem": raw["problem"], "strategies": raw["strategies"]},
                        ensure_ascii=False,
                    )
                    assert "n(n−1)/2" not in supplied_text
                    assert "binomial coefficient" not in supplied_text
                original_bytes = (ROOT / "samples" / identifier / "project.json").read_bytes()
                copy = samples.open_sample_project(identifier)
                assert copy.project.id != raw["id"]
                assert copy.project.title == entry.title + " v1"
                assert len(copy.project.strategies) == strategy_count
                assert (
                    ROOT / "samples" / identifier / "project.json"
                ).read_bytes() == original_bytes

    # Exact finite expansion of (1-p^-s)^-1 over P={2,3,5}.
    generated = finite_euler_products((2, 3, 5), 500)
    # Independently classify 5-smooth integers by removing every permitted prime.
    expected = set()
    for number in range(1, 501):
        remainder = number
        for prime in (2, 3, 5):
            while remainder % prime == 0:
                remainder //= prime
        if remainder == 1:
            expected.add(number)
    assert generated == expected

    for power in range(2, 9):
        for pairs in (1, 2, 7, 31, 64):
            assert eta_pair_identity(power, pairs)

    for value in (0.5, 0.75, 1.0, 2.0):
        transformed = value**-0.5 * theta_partial(1 / value)
        assert abs(theta_partial(value) - transformed) < 2e-14

    rh_problem = samples._load("riemann-hypothesis-research")[1].problem
    assert "no external-source" in rh_problem
    assert "never claim to have searched" in rh_problem
    assert "session execution_tools" in rh_problem
    assert "saved execution evidence" in rh_problem
    print(
        "PASS five staged sample projects, independent copies, exact finite Euler/eta identities, and theta-transform spot checks"
    )
    print(
        "NOTE finite computations validate examples only; they do not prove analytic continuation, the functional equation, or the Riemann Hypothesis"
    )


if __name__ == "__main__":
    main()
