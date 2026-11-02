# Coordinator exact-arithmetic audit of selected three-paper claims

**Executed:** 2026-11-01 PST, using Python 3's exact `fractions.Fraction` and no external inference/data. Reproducible code: `analysis/claim_math_checks.py`. **This verifies limited algebraic consistency under explicitly stated models, not scientific validity, independent source provenance or deployment outcomes.**

## Agent reliability

Enumerated **6,560** nonzero rational distributions over all eight `(Y,O,R)` joint outcomes, with atom weights in `{0,1,2}`. Verified for every case:

- `p = q - f + g` where `p=P(Y=1)`, `q=P(O=1)`, `f=P(O=1,Y=0)`, `g=P(O=0,Y=1)`.
- `p ≥ max(0,q-a-c)` with `a=P(O=1,R=0)` and `c=P(O=1,R=1,Y=0)`. The paper's `η` version follows **only if** `c≤η` is externally justified.

Also checked **101** retry probabilities `q∈{0,0.01,...,1}`: the restricted indistinguishable two-history decision has worst-case failure `max(q,1-q)≥1/2`, equality at `q=1/2`. This does **not** validate the same bound for dropped retries or policies with authoritative lookup.

**Result:** PASS for the stated algebra. No reference-adjudicator calibration, fault injection or deployment reliability was established.

## Sovereignty

Checked **2,916** combinations of positive baseline cost and successful task count (1–9), and nonnegative added cost and added successful tasks (0–5). Verified exact equivalence:

`(C_G+ΔC)/(S_G+ΔS) < C_G/S_G` iff `ΔS/S_G > ΔC/C_G`.

This confirms the **conditional cost-per-success inequality** under positive denominators. It does not verify actual campus costs, task completion gains, quality comparability, budget feasibility or policy approval.

**Result:** PASS for the stated identity.

**Saved sensitive-stratum counterexample (artifact `d802474b`):** `200×0+800×1=800` gives 80% aggregate local usefulness but **zero** sensitive successes. Under the explicitly repaired hypothetical `q_S=q_N=0.80`, local expected successes are 160 sensitive and 800 total. Reaching 1,400 overall at 90% useful API completions requires `ceil((1400−800)/0.90)=667` additional admitted roots. API-only can hypothetically yield 1,620 overall from 1,800 roots but still **zero sensitive coverage**. Exact arithmetic checks pass; these are conditional expectations, not measured campus outcomes or realized service guarantees.

**Additional source-specific check:** The saved Sovereignty Investigator call 14 derives a conditional **80% power sufficient bound** for the conservative paired confidence gate under hypothetical `Δ=0.20`, discordance `q=0.40`, and IID paired episodes. The Cantelli–Hoeffding threshold is `n>1730.9048...`, so `n=1800` satisfies it; the smallest integer satisfying *this particular sufficient inequality* is **1731**, not a claim of minimum actual enrollment. The final Skeptic review of this step **failed**; see `COORDINATOR_SOURCE_AUDIT_SOVEREIGN_1.md`. Independent arithmetic checking does not substitute for a completed adversarial review or empirical validation.



## Xenopus

Verified exactly:

- For `U∼Uniform(0,1)`, `Var(U)=1/12`, and `Cov(U,U)=+1/12` versus `Cov(U,1-U)=-1/12`, giving slopes **+1** and **−1** despite equal uniform marginals.
- For binary stage `S`, assigned `E=e_0+(e_1-e_0)S` implies `SE=e_1S`, so the artificial interaction adds no independent predictor dimension.
- For matched pulse integral `Q` and idealized early-only versus late-only constant receptivity `c>0`, the late-minus-early transition-drive contrast is respectively `−kcQ` or `+kcQ`.
- A persistence score exactly proportional to a fixed exposure integral cannot distinguish alternative temporal shapes with that same integral.

These are **mathematical model checks**, not biological measurements or verification that the proposed stage-specific model applies to `X. laevis`.

**Result:** PASS for the restricted algebra.

## Quality implications

The three papers contain substantive, conditionally sound analytical content worth preserving. The immediate Agent failure is **presentation/claim-assembly corruption**, not a demonstrated mathematical error in the cited formulas. Future changes must retain these precise conditional results and their counterexamples; see `COORDINATOR_CRITICAL_EVIDENCE_MANIFEST.md`.

No TeX/PDF visual verification, external literature verification, dataset inspection, or new provider call was performed by this script.
