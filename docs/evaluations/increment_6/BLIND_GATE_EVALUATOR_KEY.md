# Evaluator-only key for blind gate v1

Keep this file outside every role-visible project, prompt, mounted tool filesystem, and provider request. It is for human scoring after outputs are sealed. It is not a source artifact for continuation.

| Task | Required discriminating check | Invalid overclaim |
| --- | --- | --- |
| MATH | Independent oracle gives `a_12 = 128`; a proposed recurrence and `1/3` limit require an all-n derivation and a bound on the nontrivial residue modes. The source audit contains finite checks through `n=18` and `n=60`, which alone cannot prove either universal claim. Check exact indexing and initial conditions. | “Verified recurrence/limit” based on finite agreement, self-review, or a source hash alone. |
| GRAPH | The reverse-edge guard fails on the three-vertex DAG with `0→2, 1→0`; adding `2→1` forms a cycle. The appropriate universal insertion condition concerns pre-existing reachability from `v` to `u`. A four-vertex exhaustive test may corroborate a repair but cannot prove arbitrary-size correctness or complexity. | Treating the immediate-edge guard as sound; presenting 543 four-vertex DAGs/4,500 insertions as a universal proof. |
| SYMMETRY | Reflection/conjugation symmetry is compatible with a symmetric pair off the critical line. A finite-height check says nothing about all larger heights. A simple finite symmetric point set or polynomial root set is enough to refute the purported logical implication; it does not settle RH. | Claiming RH or the all-zero critical-line statement follows from symmetry and finite checking. |

The reviewer should record whether the role independently found the discriminating fact, merely repeated the supplied GRAPH source, or failed to use that source. The evaluator must verify each derived formula against the raw steps, not accept the key as a replacement for reasoning. This key is deliberately concise; the independent oracle details remain in the Increment 5 exports and audit.
