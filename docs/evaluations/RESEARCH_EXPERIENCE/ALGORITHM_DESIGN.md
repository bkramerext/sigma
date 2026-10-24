# Design and Verify an Incremental Dependency Scheduler — research experience evaluation

Study in progress. Blue; assignment supplied directly by the human, 2026-10-24.

## Sample identity and research objective

`algorithm-design` — Design an algorithm for a build system that maintains a directed dependency graph under edge additions and removals, answers whether the graph contains a cycle, and, when acyclic, produces a valid build order. Assume up to 100,000 vertices and 1,000,000 edges, with long sequences of updates and queries. Specify exact semantics for updates, including duplicate edges and nonexistent removals, data structures, pseudocode, correctness invariants and proofs, time and space complexity, and adversarial tests. Compare at least two approaches, including a straightforward recomputation baseline. Seek useful incremental performance without asserting an unproved bound. If worst-case efficient fully dynamic maintenance is not established, distinguish a correct implementable solution from a proposed optimization and give a discriminating benchmark.

## Researcher expectation

A correct recomputation baseline, precise update semantics, a cycle witness, and an adversarial update sequence should precede any incremental speed claim. Useful progress is a proved invariant or a benchmark that rejects a proposed optimization at the stated graph scale.

## Evaluation status

Expectation recorded before detailed outcome assessment. Browser and evidence findings will replace this provisional status. No live model calls authorized.
