#!/usr/bin/env python3
"""Exact-arithmetic checks for selected conditional claims in SIGMA's three baseline papers.

Checks algebraic consistency of the *stated models*, not empirical premises,
source accuracy, model-generated reasoning outside these formulas, or biology.
No network, provider calls, or external datasets.
"""
from __future__ import annotations

from fractions import Fraction as F
from itertools import product


def check_agent_outcome_identity() -> int:
    # Y=actual correctness, O=automated acceptance, R=reference certification.
    # Enumerate small rational distributions over all eight joint atoms.
    atoms = list(product((0, 1), repeat=3))
    checked = 0
    for weights in product((0, 1, 2), repeat=8):
        total = sum(weights)
        if total == 0:
            continue
        probs = [F(w, total) for w in weights]
        p = sum((w for (y, o, r), w in zip(atoms, probs) if y), F(0))
        q = sum((w for (y, o, r), w in zip(atoms, probs) if o), F(0))
        false_accept = sum((w for (y, o, r), w in zip(atoms, probs) if o and not y), F(0))
        false_reject = sum((w for (y, o, r), w in zip(atoms, probs) if y and not o), F(0))
        assert p == q - false_accept + false_reject
        a = sum((w for (y, o, r), w in zip(atoms, probs) if o and not r), F(0))
        c = sum((w for (y, o, r), w in zip(atoms, probs) if o and r and not y), F(0))
        assert p >= max(F(0), q - a - c)
        checked += 1
    return checked


def check_retry_minimax() -> None:
    for numerator in range(101):
        q = F(numerator, 100)
        worst_case_failure = max(q, 1 - q)
        assert worst_case_failure >= F(1, 2)
        if numerator == 50:
            assert worst_case_failure == F(1, 2)
    # This is only for a retry that *commits*, not arbitrary message delivery.


def check_sovereign_cost_threshold() -> int:
    checked = 0
    for cost in range(1, 10):
        for success in range(1, 10):
            for delta_cost in range(0, 6):
                for delta_success in range(0, 6):
                    cheaper_per_success = F(cost + delta_cost, success + delta_success) < F(cost, success)
                    ratio_condition = F(delta_success, success) > F(delta_cost, cost)
                    assert cheaper_per_success == ratio_condition
                    checked += 1
    return checked


def check_xenopus_model() -> None:
    # U ~ Uniform(0,1); E=U, R=U vs R=1-U.
    e_u = F(1, 2)
    e_u2 = F(1, 3)
    variance = e_u2 - e_u * e_u
    covariance_positive = variance
    covariance_negative = (e_u - e_u2) - e_u * (1 - e_u)
    assert variance == F(1, 12)
    assert covariance_positive / variance == 1
    assert covariance_negative / variance == -1

    # With E=e0+(e1-e0)S and binary S, SE=e1*S for both S=0,1.
    for e0, e1 in [(F(1, 3), F(4, 5)), (F(-2), F(3))]:
        for stage in (0, 1):
            early = e0 + (e1 - e0) * stage
            assert stage * early == e1 * stage

    # Matched pulse integral Q, early-only vs late-only receptivity c.
    k, c, q = F(3, 2), F(4, 3), F(7, 5)
    assert k * (0 - c * q) == -k * c * q
    assert k * (c * q - 0) == +k * c * q

    # A persistence score proportional to an integral cannot vary if that
    # same integral is fixed, whatever the pulse's temporal shape.
    exposure_integral = F(17, 8)
    p1 = exposure_integral / F(11, 2)
    p2 = exposure_integral / F(11, 2)
    assert p1 == p2


def main() -> None:
    n_agent = check_agent_outcome_identity()
    check_retry_minimax()
    n_cost = check_sovereign_cost_threshold()
    check_xenopus_model()
    print(f"PASS: {n_agent} exact agent joint distributions, 101 retry policies, "
          f"{n_cost} cost/success cases, and Xenopus conditional algebra checks")
    print("Scope: mathematical consistency under stated assumptions; no empirical verification")


if __name__ == "__main__":
    main()
