# Increment 17: longitudinal research-quality audit

## Finding: gate not met

Existing SIGMA archives demonstrate valuable research provenance, actual computation and an independently reviewed one-problem real Skeptic correction. They do **not** demonstrate that the system reliably produces better unscripted cumulative research than a strong single-role self-review baseline. This is a scientific evidence gap, not a failed randomized experiment.

## Two substantive defects in archived behavior

1. **Unsupported computational lead survives in the user-facing result.** The Increment 7 `graph-withheld` session contains **zero Python executions** but opens its outcome summary and saved Conclusion with a sentence claiming a bounded computational observation supports the candidate. Typed verification correctly says *Incomplete* and reports zero executions; that prevents false theorem verification but does not prevent a misleading first impression. The archive is a scripted control, so this shows an output-integrity/UI trust-boundary weakness, not proof a live model would behave identically.
2. **Cumulative question resets to generic.** In the three-session `graph-present` archive, session 1's specific next step is to replace failed code with a bounded three-vertex witness search; the second session's current question starts with the generic 'Advance this strategy...' instead. The later approved continuation correctly includes the negative witness and retains the arbitrary-size proof obligation. Persistence works, but automatic longitudinal prioritization is not yet reliable. This is particularly damaging for a system promising cumulative research.

## Controls and scientific limits

The read-only checker `scripts/increment17_longitudinal_audit.py` confirms both defects using the archived API exports, rather than trusting a narrative score. It also confirms three distinct saved graph sessions, preservation of the negative witness in approved continuation, and an incomplete verification label on the unsupported claim.

Neither an automated text rule nor a structural archive audit is a mathematical semantics verifier. Avoid patching role-authored history. The proper product remedy for the first defect is a clearly distinct evidence-derived status before unverified prose; for the second, a subsequent session should privilege the strongest explicitly recorded unresolved next question unless the user overrides it. Both require coordinated production ownership and acceptance, especially while Cloud is the priority.

## Increment 17 verdict

- **Integrity audit:** independently reproducible, bounded, and zero additional inference spend.
- **Cumulative quality:** partial; evidence survives manual approval but a generic automatic reset remains.
- **User-facing calibration:** known defect; caveats do not eliminate misleading opening language.
- **Multi-agent advantage:** not demonstrated by the current archive; no matched-budget self-review arm exists.

**Do not mark the overarching research-quality gate as passed.** This evidence warrants targeted product fixes and a later genuine experiment if resources permit, not further scripted demonstration or premature simplification. Increment 17 is a milestone, not necessarily the last research increment.

## Corrective action against current main (October 25)

Current main already contains `_saved_followup_questions` with frozen-context provenance checks and automatic transfer into a new session's first Investigator question. Its existing tests exercise actual subsequent dispatch, precedence of approved continuations, and tampered/truncated source rejection. Therefore the archived generic reset describes the earlier captured run; **it must not be represented as an outstanding current-main engine regression without a new reproduction**. No redundant changes to the research engine are introduced by this PR.

Current main also already renders recorded computation provenance *before* agent-authored Outcome prose. This PR strengthens that guard with an explicit **zero saved local computations** warning, where the recorded metric or saved provenance confirms none. It does not rewrite historical conclusions or claim to perform semantic verification. The archived scripted misleading sentence remains as an honest negative control. Browser acceptance and full verification are required because the display changed.

## Release verification

Shared Cloud CI preflight negative-control test corrected independently in merged PR #122. Production installer and preflight behavior remain unchanged. Increment 17 acceptance additionally requires its own browser checks and full SIGMA verification on the updated base.
