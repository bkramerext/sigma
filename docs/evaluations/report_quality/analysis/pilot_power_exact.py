#!/usr/bin/env python3
"""Numerically evaluate the exact paired-discordance pilot gate in SIGMA's frozen
Sovereign AI Federation v2 paper. No inference, data access, or provider calls.

Requires NumPy and SciPy. The summation is exact over the multinomial count
distribution up to floating-point evaluation of beta quantiles and binomial CDFs.
It is NOT a proof of statistical assumptions, an empirical pilot, or a validated
sample-size recommendation.
"""
from __future__ import annotations

import argparse

import numpy as np
from scipy.stats import beta, binom


def gate_power(
    n: int,
    p10: float = 0.30,
    p01: float = 0.10,
    improvement_margin: float = 0.10,
) -> float:
    """P(CP_lower(X) - CP_upper(Z) > margin) for IID multinomial pairs.

    X = federation-only successes, Z = gateway-only successes.
    Each marginal uses a TWO-sided equal-tailed 97.5% Clopper-Pearson interval.
    Thus the simultaneous lower bound has at least 95% coverage by union bound.
    """
    if n < 1 or p10 < 0 or p01 < 0 or p10 + p01 > 1:
        raise ValueError("Invalid sample size or discordance probabilities")
    x = np.arange(n + 1)
    lower = np.zeros(n + 1)
    upper = np.ones(n + 1)
    lower[1:] = beta.ppf(0.0125, x[1:], n - x[1:] + 1)
    upper[:-1] = beta.ppf(0.9875, x[:-1] + 1, n - x[:-1])

    # CP_upper(z) increases with z. For each X, find the largest Z for which
    # the strict efficacy gate holds, respecting X + Z <= n.
    z_max = np.searchsorted(upper, lower - improvement_margin, side="left") - 1
    z_max = np.minimum(z_max, n - x)

    # X ~ Binomial(n, p10); Z | X=x ~ Binomial(n-x, p01/(1-p10)).
    # No independence of X and Z is assumed.
    if p10 == 1.0:
        conditional = np.where(z_max >= 0, 1.0, 0.0)
    else:
        conditional = np.where(
            z_max >= 0,
            binom.cdf(z_max, n - x, p01 / (1.0 - p10)),
            0.0,
        )
    return float(np.sum(binom.pmf(x, n, p10) * conditional))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p10", type=float, default=0.30)
    parser.add_argument("--p01", type=float, default=0.10)
    parser.add_argument("--margin", type=float, default=0.10)
    parser.add_argument("sample_sizes", type=int, nargs="*", default=[486, 521, 800, 1800])
    args = parser.parse_args()
    for n in args.sample_sizes:
        print(f"n={n:4d} power={gate_power(n, args.p10, args.p01, args.margin):.9f}")


if __name__ == "__main__":
    main()
