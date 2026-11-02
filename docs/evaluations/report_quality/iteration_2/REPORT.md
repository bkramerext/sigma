# Iteration 2 — H2-A deterministic fallback

## Disposition

Mixed result; **publication-quality acceptance is not met**. The Agent paper's fallback claim/abstract corruption is materially improved. Xenopus remains a careful analytical hypothesis paper. Sovereignty regressed when its planning call failed and the deterministic fallback produced a thin paper. Do not treat H2-A as globally successful until that fallback is improved and the papers regenerated. No research was rerun and no source project was changed.

## Frozen inputs and treatment

Recovered exact I1 frozen snapshots from each saved I1 paper record (the compact metadata gzip did not contain the snapshots). The source-gate checkpoint was therefore resolved; it is not a missing-source blocker. IDs and snapshot SHA-256:

| Project | Project ID | Sources | Frozen snapshot SHA-256 | I1 paper ID |
|---|---|---:|---|---|
| Agent Reliability v1 | `da4580f5-7620-49b0-882e-aee34fcdc05d` | 36 | `080d3b70b67cfbe346acdb0f565d4a61c09ec4819229f2dd92dded43d9de40d9` | `13a908d9b3074cb49b993186164559cb` |
| Sovereign AI Federation v2 (coordinator's AI Sovereignty identity caveat applies) | `9175d73d-62aa-4523-a286-445f5390ae1d` | 13 | `552f9458e600d3e7d0b3aa6c1dd105cc62dab4967db652123d2f134783b76f34` | `391e8f84540c4774af600ef95b47680f` |
| Xenopus Tadpoles v9 | `01de54c9-9593-413a-9577-1a952d28da70` | 15 | `3236a8c66a96d713f28726271169e67c88c8a768f398ab3b9b504fee3cdcc74e` | `880b802fdc534200807047b107aebaaf` |

The paper runs used implementation `2469661d` (source-verified candidate selection and snapshot gate). Commit `e9fb2396` landed after runs began; it adds exact indexed-fragment reassembly, nonterminal-cutoff rejection, and stronger substantive conclusion assembly. Those additions pass the paper tests but were **not exercised by these three generated papers**. The artifact results must be judged against `2469661d`, not attributed to `e9fb2396`.

Options were held to I1: ChatGPT-plan, `gpt-6.1-sol`, high effort, long form, research/claim/validation detail and diagrams enabled, excerpts disabled. No metered API keys/costs; no live research or source edits. AI proofreader calls were attempted but every run fell back without accepted correction.

## A/B results

| Project | I1 → I2 words/pages/claims | I2 time; generation calls | Assessment |
|---|---|---|---|
| Agent | 5,050/27/5 → 8,849/42/17 | 677s; 16 | Strong improvement: abstract and claims now state substantive, human-readable results with exact artifact provenance; conclusion synthesizes bounded findings and gaps. Distinguishes retry issuance from commitment and effect-first duplication from marker-first loss. Remains analytical, not empirical deployed-agent validation; omissions remain high (32,189 fields). |
| Sovereignty | 9,518/42/19 → 5,272/26/4 | 1,138s; 12 | Regression. Planner failed; deterministic fallback paper has only four claims and a generic abstract, dropping much of the I1 cost/federation comparison. Some sensitive-stratum conditional gate and partition/accounting reasoning remain, but not enough to accept. Candidate after `e9fb2396` is richer in offline tests; current generated paper does not reflect it. |
| Xenopus | 5,975/24/12 → 5,765/25/11 | 504s; 13 | Substantively maintained: preserves marginal-vs-joint nonidentifiability and conditional receptivity-pulse hypothesis; explicitly reports no biological-data analysis, measured effect, perturbation, or independent replication. Analytical hypothesis only. |

All three were ChatGPT-plan provider `chatgpt`; elapsed generation times sum to 2,319 seconds (38m39s), excluding proofreading/layout and implementation/test time. Sovereignty’s planner failure is a real treatment outcome, not replaced by a synthetic paper. There is no claim of independent literature review or biological validation.

## Artifacts and hashes

All complete artifacts and their compact/full production metadata are in `docs/evaluations/report_quality/iteration_2/papers/`. Hashes below are SHA-256.

| Stem | TXT | TeX | PDF |
|---|---|---|---|
| `ai-agent-reliability-v1` | `1725678e7784784c0e74f7c944b9e0f90f806bef97eba4bd16c7bffc7de2919e` | `fd997113c9a0eac7e40d1fdcbb5800c75f608852387115b1a0baf068d6ff41c3` | `19d4db9cd1f41b2b4bad9057380c20051fce1577550f086400d4bb9c19eb5f4e` |
| `ai-sovereignty-v2` | `4ee0ae562c427232ac96717c1239e2d54b8598afeb4d4c8e698a9d1571fa95fe` | `c3e8ef2a3a90e75a61fdd7d7195a513b13c69c272d6ff0348503f088d8ba095f` | `d4282a71de86107d59973fc22115ebc06a08607a0ff87ef1e419684d1eda51fd` |
| `xenopus-tadpoles-v9` | `30eb55a87ed0ce474aac9ff1ff0ac144b797e9023f29e7f757dee7d5dba7569f` | `d88c180fe1f506bc219e1f50051c17311e14f1419339d3d4e20343fb9296af9c` | `3438962e178f8578fd22d0895da6a287adeba59e64b088e00a4643f56ffb507e` |

## Validation and unresolved issues

- Focused `tests/papers.py`: passed, including operational metadata negative controls, meaningful failure positive control, opposing findings, exact source locators, incomplete-fragment rejection and exact multi-fragment reconstruction.
- `ruff check src/sigma/papers.py tests/papers.py`: passed.
- `pyright src/sigma/papers.py tests/papers.py`: passed.
- `./sigma test`: **all steps passed**.
- `semantic_gate.py`, `manuscript_audit.py`, and `claim_provenance_gate.py`: inspected; Agent/Xenopus avoid raw abstract paths and operational headline claims; all three have complete claim provenance.
- Excerpts-disabled TeX option mismatch exists in both I1 and I2 (appendix rendered for all projects), so it is pre-existing and outside this iteration. Xenopus also retains serialized provider schema in its appendix, likewise present in I1. `layout_status=needs_review` on all papers; proofreader accepted zero corrections. PDF overflow/font warnings persist. These remain independent rendering/review defects and are not paper-quality acceptance.
- Full paper A/B was performed. Agent and Xenopus checked for claim support, negative findings, limitations and source references; Sovereignty’s substantive loss is explicitly recorded above.

**MET:** deterministic fallback bug reproduced and fixed in focused code paths; source-linked claims; frozen-source generation of all three TXT/TeX/PDF; regression tests and full test suite. **UNMET:** consistent substantive quality across three projects; Sovereignty fallback robustness; proofreading/rendering quality. **UNVERIFIED:** the final `e9fb2396` fragment/conclusion hardening's effect on regenerated full papers. Recommendation: coordinator should reject paper-quality acceptance, review the Sovereignty failure, then decide a narrowly controlled rerun after checking current fallback behavior.
