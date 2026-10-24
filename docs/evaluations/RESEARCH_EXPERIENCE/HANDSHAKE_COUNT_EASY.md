# Counting Pairwise Handshakes — research experience evaluation

Blue · 2026-10-24 · browser/scaffolding evaluation; no research run.

## 1. Sample identity and research objective

`handshake-count-easy`: count pairs of distinct people when each pair shakes hands once. The [sample](../../../samples/handshake-count-easy/project.json) has one human strategy, Direct counting, and zero sessions.

## 2. Researcher expectation

A short unordered-pair argument, no self-pairs and checks at n=1,2,3 should finish this question. I would expect immediate comprehension, not a research program.

## 3. Environment and runs

App `6059d67`, Chrome `156.0.8078.47`, isolated browser-created copy. Desktop 1440×1000; 390×844/320×700 emulation. Sol/High is an unverified saved preference; no model ran. Sessions/IDs: none. Provider calls **0**, charge **$0**, no fixture playback. Default future limits: three iterations, 30 calls, one hour, 12,000 output tokens/call, no cost cap. Those are ceilings, not consumption. Capture took 1.16s, excluding assessment; [METHOD](METHOD.md) defines isolation and boundaries.

## 4. Research journey

From Home → Samples → Mathematics I expanded Direct counting. It asks for a general answer, small checks and exact counting, but supplies no argument. I forked “Check unordered pairs without self-pairs,” saved it, reloaded, disabled/restored it and reopened from Recent. Stock and continued text reports downloaded. Generation and paper setup were visible; I cancelled without inference.

## 5. Substantive findings

SIGMA produced no count or explanation. It stored my plan. Independently, counting pairs `i<j` gives `n(n−1)/2`; this elementary evaluator observation is not a SIGMA result.

## 6. Independent critical assessment

Direct counting mostly restates the task. A useful answer must explain why summing each person's `n−1` partners counts each handshake twice. A longer agent session would need unusual teaching value to justify itself. No session exists to test that value.

## 7. Rubric

Scores concern observed scaffolding, not model behavior.

| Dimension | Score | Evidence and rationale |
|---|---:|---|
| Problem orientation | 4 | Short visible question states the self-pair ambiguity. |
| Strategy quality | 3 | Direct counting requests checks but adds little method. Human-authored. |
| Intellectual substance | N/O | No argument or analytical artifact. My count is not app output. |
| Skepticism and epistemic integrity | 3 | Written strategy requests assumptions and exact counting; review behavior unobserved. |
| Research continuity | 3 | My fork survives reload and Recent. Session continuity unobserved. |
| Outcome usefulness | N/O | No Outcome or Conclusion exists. |
| Evidence inspectability | N/O | No research evidence to inspect. |
| Researcher agency | 4 | Fork/save, eligibility toggling and reopening worked. Agent intervention untested. |
| Interaction quality and delight | 2 | Full research/paper apparatus surrounds a few-line exercise; both mobile widths fit. |
| Communication and reuse | 3 | Text exports preserve the brief and plans; no result-bearing paper generated. |

## 8. Delight and friction

The question is readable and saving is smooth. Forking a plan to count handshakes felt unnecessary. The export is a clear brief, but I still supply the intellectual content.

## 9. Continuation test

Give the pair-count explanation, check n=1,2,3 and stop. The saved fork can request this, but concise completion was not observed.

## 10. Defects and opportunities

**Medium — scale mismatch.** Reproduce: open the Easy sample and compare its generic Direct counting card and zero sessions with full research/paper controls. Remedy: a compact explanation-and-check path with a clear end. This is an observed onboarding weakness, not a failed live answer. No fix implemented.

## 11. Overall judgment

- **Continue? No.** I would answer directly; the observed machinery adds overhead.
- **Meaningful research progress: Not observable.** Only manual planning occurred.
- **Trust: Conditional.** Persistence works; generated reasoning is untested.

## 12. Evidence appendix

[Initial workspace](evidence/handshake-count-easy-workspace.txt), [stock report](evidence/handshake-count-easy-report.txt), [manual continuation](evidence/handshake-count-easy-continuation.txt), [continued report](evidence/handshake-count-easy-continuation-report.txt), [limits](evidence/handshake-count-easy-limits.txt), [generation setup](evidence/handshake-count-easy-generation-preflight.txt), [paper setup](evidence/handshake-count-easy-paper-preflight.txt), [continuation ledger](evidence/continuations.json). Canonical hashes remained unchanged; [full offline tests passed](evidence/sigma-test.log).
