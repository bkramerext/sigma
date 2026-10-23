# SIGMA: Lean Verification Plan

**Status:** Future feature proposal, outside A18  
**Purpose:** Integrate formal mathematical verification into SIGMA's existing research workflow without turning SIGMA into a theorem-proving IDE.

## Why this matters

SIGMA helps users pursue difficult problems through sustained, multi-agent investigation. Its Investigator and Skeptic can construct and challenge arguments, but model agreement is not mathematical certification. Lean provides a different kind of evidence: a proof accepted by a formal proof checker.

The immediate motivation is SIGMA's *Maximum Number of Regions Formed by Lines* paper. Its proof appears mathematically sound on independent review, but the research record labels it unverified. Lean could provide stronger, reproducible assurance for an appropriately formalized version of the theorem. Formalization is not automatic, however, and a checked theorem may still fail to express the intended informal claim.

## Product principles

1. **Verification is optional and attached to claims.** Do not require a separate project type or research mode.
2. **Reuse the existing workspace.** Put verification status and actions in Research Session artifacts and claim views, not a new top-level pane or dashboard.
3. **Separate mathematical judgment from formal verification.** A persuasive informal proof, a Lean-checked formal statement, and a validated correspondence between them are different things.
4. **Preserve exact provenance.** Results attach to immutable versions of the claim, formal statement, Lean source, environment, and checker output.
5. **Failures become useful research obligations.** When a formalization fails, SIGMA can investigate missing lemmas rather than merely displaying an error.
6. **Bound autonomous work.** Formalization agents operate under explicit time, call, compute, and retry limits, with cancellation and no hidden provider fallback.
7. **Be honest about limitations.** Lean acceptance is strong evidence for a formal theorem, not a universal guarantee that the original natural-language claim is correct.

## Proposed user experience

### 1. Claim or artifact action

When a research artifact contains a mathematical claim or proof, expose **Verify with Lean**. Selecting it opens a collapsible verification workspace inside the existing artifact view. The user can inspect the proposed formal statement and Lean source before running the checker, or authorize an agent to prepare and iterate on a formalization.

A Verify action should not appear on artifacts for which Lean is inapplicable. It should also be clear whether a claim is merely eligible for verification, already has a draft formalization, or has a completed verification attempt.

### 2. Claim-level verification status

Show a compact status adjacent to each mathematical claim:

| Status | Meaning |
| --- | --- |
| Not attempted | No formal verification has been run for this claim version. |
| Formalizing | An agent or user is preparing a Lean statement/proof. |
| Checking | Lean is executing against the submitted source. |
| Lean verified | Lean accepted the submitted proof of the recorded formal statement under the recorded environment and trust policy. |
| Incomplete | A formalization or proof obligation remains unresolved within the current attempt. |
| Rejected | Lean reported a source, elaboration, type, or proof-checking error. |
| Interrupted | Verification was stopped or failed operationally; this is not a mathematical refutation. |
| Stale | The underlying claim or relevant verification inputs changed after the recorded result. |

Keep **informal assessment** and **formal verification** visually distinct. For example:

> Mathematical assessment: Convincing, unverified  
> Formal verification: In progress

Avoid displaying an unconditional green checkmark for a natural-language claim merely because some Lean theorem was accepted. Where practical, expose a separate **formalization correspondence reviewed** indicator.

### 3. Collapsible verification workspace

A compact example:

```text
C3: Maximum number of regions

Mathematical assessment: Convincing, unverified
Formal verification:    In progress

Lean verification
  Attempt 3 of 5
  Formalizing the region-counting lemma...
  ✓ Definition of line arrangement
  ✓ Upper-bound lemma
  ◌ Attainability lemma

  [Stop verification]

[View formal statement] [View Lean source] [View diagnostics]
```

Progress labels must reflect actual persisted steps or tool results, not invented percentages or inferred success. For concurrent verification tasks, show compact per-claim activity without obscuring the main research session.

### 4. Research feedback loop

If Lean cannot establish a lemma, surface a concrete obligation, for example:

> Verification incomplete: the proof has not established that the line segments occupy distinct regions.

Offer **Investigate with SIGMA**. This creates a linked research obligation containing the precise Lean goal or diagnostic, relevant definitions, the attempted source, and its provenance. The existing strategy/agent workflow can investigate the obligation and produce candidate repairs. A later verification attempt consumes the resulting artifacts, without modifying historical attempts.

The intended cycle is:

**Research → Formalize → Check → Identify obligations → Research → Recheck**

A compiler error is not automatically a mathematical counterexample. Classify syntax/type issues, missing lemmas, timeouts, and genuine logical obstructions separately.

### 5. Verification history

Each attempt is a durable, inspectable artifact. Users can compare attempts, read Lean source and diagnostics, see which research artifacts contributed, and inspect the exact theorem statement that was accepted. A changed claim, statement, proof, dependency, or relevant environment must not silently inherit an earlier green status.

## Technical architecture

### Verification service

Provide a local Lean 4 execution adapter with a pinned Lean and Mathlib environment. Run it in a constrained subprocess or sandbox with bounded CPU, memory, runtime, output size, and filesystem/network access. Keep provider calls separate from local checker execution; report both resource categories accurately.

The adapter accepts a versioned verification request, executes Lean, and returns structured diagnostics and an immutable attempt record. It must handle cancellation, process termination, malformed diagnostics, toolchain unavailability, and restart/reload safely.

### Agent-assisted formalization

An optional formalization agent may:

1. Identify a precise mathematical claim and propose a Lean theorem statement.
2. Reuse existing Mathlib definitions and lemmas where appropriate.
3. Generate proof code and invoke the checker.
4. Interpret diagnostics and attempt bounded repairs.
5. Convert unresolved mathematical goals into SIGMA research obligations.

Agent outputs are proposals, not trusted verification. Do not claim success on the basis of model self-assessment. Prevent an agent from “succeeding” by weakening the statement, changing quantifiers, adding assumptions, or replacing the intended theorem with a trivial proposition. Material statement changes require explicit visibility and correspondence review.

### Trust and security

A verified status requires the Lean kernel to accept the proof under an explicit trust policy. Reject placeholder proofs such as `sorry`, and audit or disallow untrusted axioms, custom unsafe shortcuts, and environment modifications that would undermine the intended guarantee. Record any nonstandard assumptions or axioms in the verification result. Checking the theorem's *meaning* relative to the informal claim remains a separate review task.

Formalization code and model-generated content are untrusted inputs. Use execution isolation, strict resource bounds, and controlled dependencies. No arbitrary external network access should be required for routine checking after the toolchain is installed.

### Proposed persisted record

Each verification attempt should include at least:

- Project, session, artifact, claim, and claim-version identifiers.
- Exact informal claim snapshot and proposed formal Lean statement.
- Lean source and content hashes.
- Lean/Mathlib versions, dependency lock information, and relevant trust policy.
- Start/end timestamps, status, diagnostics, and resource usage.
- Agent/provider provenance and limits, if AI-assisted.
- Explicit list of outstanding proof obligations and their linked research artifacts.
- Correspondence-review status: unreviewed, reviewed, or disputed, with rationale.

Maintain a clear distinction between operational failures and logical verification outcomes. Exports and reports should reproduce the saved status, not recalculate it optimistically.

## Delivery approach

**Phase 1 — Checking infrastructure and UI.** Add the claim-level Verify action, collapsible details, Lean runner, durable attempts, status indicators, diagnostics, cancellation, and export support. Start with a small known Lean theorem to validate the end-to-end mechanism. This phase does not promise automatic proof generation.

**Phase 2 — Assisted formalization.** Add bounded agent generation and repair of Lean statements/proofs, reuse Mathlib, expose proposed statements for review, and report success rates honestly. Start with elementary algebra and discrete mathematics before geometric arrangements.

**Phase 3 — Research integration.** Feed failed or incomplete mathematical obligations into SIGMA's existing multi-strategy workflow; track their resolution and retry formalization using new durable evidence. Preserve provenance across sessions and forks.

**Phase 4 — Harder mathematics and evaluation.** Build a diverse benchmark with held-out theorem statements, independent correspondence review, reproducible Lean environments, and measures of verification success, time, cost, and failure modes. The Maximum Regions theorem is a useful later integration case because formalizing planar regions and their connectivity may require significant geometric infrastructure.

These phases describe a future capability roadmap, **not additional A18 work**. A18 should establish substantive research quality first.

## Acceptance and evaluation

A minimal release is acceptable when a user can select an eligible claim, run Lean against a saved formalization, inspect the exact checked theorem and diagnostics, cancel safely, reload the result, and see an accurate status in the report. Regression tests must cover rejected proofs, placeholders, toolchain failure, timeout, cancellation, stale claims, and attempts to weaken the theorem.

Assisted-formalization quality should be evaluated separately from infrastructure correctness. Track:

- Percentage of intended claims formalized faithfully.
- Percentage of faithful formalizations successfully proved by Lean.
- Human correspondence-review outcomes.
- Number and nature of unresolved obligations.
- Compute/model usage and elapsed time.
- Rate of misleading positives (especially statement weakening or unsound trust assumptions).

**Never equate a checked Lean file with verified correctness of the original natural-language research result unless the correspondence and trust assumptions have also been examined.**

## Risks and open decisions

- **Formalization cost:** For geometry-heavy problems, defining the objects may be harder than proving the final numerical identity.
- **Mathlib coverage:** Existing libraries may not match SIGMA's informal formulation; reusable domain libraries may be needed.
- **Statement drift:** Agents may inadvertently simplify away the difficult claim. This is a central evaluation risk.
- **Axiom policy:** Define exactly which Lean axioms, classical principles, and dependencies are acceptable for the product's verification badge.
- **Toolchain packaging:** Choose a reproducible installation/update mechanism for local users.
- **UI restraint:** Keep the verification experience integrated with research artifacts; avoid a separate theorem-proving cockpit unless real usage demonstrates a need.

## Recommendation

Implement Lean as an **optional formal verification capability attached to mathematical claims**, with a durable verification history and a path for failed obligations to re-enter SIGMA research. Begin with a reliable local checker and truthful UI; add autonomous formalization only after the checking and provenance contracts are sound.

This would let SIGMA move from *agents find an argument convincing* to *a precise mathematical statement has a machine-checked proof*, while preserving the essential distinction between those two assertions.