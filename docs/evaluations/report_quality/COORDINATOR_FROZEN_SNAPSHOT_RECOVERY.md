# Coordinator source-gate resolution: the exact iteration-1 evidence is in the saved paper records

**Prepared:** 2026-11-01 05:45 PST. **Status:** code-grounded recovery route, pending local binary verification by Blue; **not** a new iteration or a claim that iteration-2 paper generation succeeded.

## Critical discovery

Blue's `messages/message_in_2_source_gate.md` correctly rejected current Agent/Xenopus project exports whose preflight hashes differ from iteration 1. **But the exact frozen research package used to generate each iteration-1 paper should already be preserved in the committed `*.metadata.full.json.gz` paper record.** There is no need to guess which changing live project state corresponds to the earlier paper.

The code path in `src/sigma/papers.py` establishes the recovery contract:

- `_snapshot` (lines ~813–868) builds a canonical `{"schema":"sigma-paper-evidence-v2","project_id":...,"sources":[...]}` package. It hashes `json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",",":")).encode()` with SHA-256.
- `_generate_impl` (lines ~5849–5856) writes **both** `"snapshot_sha256": snapshot_hash` and **`"snapshot": package`** into the persisted paper `record`.
- `_save(path, record, pdf)` (line ~6221) persists the record. The successful run then calls `_clear_work(path)` (line ~6224), so relying on an old `.long-paper-work` checkpoint after success is **not** reliable.
- Blue's iteration-1 artifact export reports that `*.metadata.full.json.gz` contains the **full** preserved generator record, not just the compact metadata. Agent's gzip file is ~2.8 MB; Xenopus's is ~305 KB. These sizes are compatible with compressed snapshots of ~14.35 MB and ~1.83 MB respectively, but **size alone is not proof**; verify keys and hashes before using.

The immutable frozen evidence should therefore be extracted from:

- `docs/evaluations/report_quality/iteration_1/papers/ai-agent-reliability-v1.metadata.full.json.gz`
- `docs/evaluations/report_quality/iteration_1/papers/xenopus-tadpoles-v9.metadata.full.json.gz`
- `docs/evaluations/report_quality/iteration_1/papers/ai-sovereignty-v2.metadata.full.json.gz`

## Mandatory local verification (offline, no provider calls)

Run this read-only Python snippet on Blue's checkout; **do not** treat a matching project ID or source count as equivalent to a matching snapshot hash:

```python
import gzip, hashlib, json
from pathlib import Path

root = Path("docs/evaluations/report_quality/iteration_1/papers")
for name in ("ai-agent-reliability-v1", "ai-sovereignty-v2", "xenopus-tadpoles-v9"):
    compact = json.loads((root / f"{name}.metadata.json").read_text())
    with gzip.open(root / f"{name}.metadata.full.json.gz", "rt", encoding="utf-8") as stream:
        full = json.load(stream)
    package = full.get("snapshot")
    assert isinstance(package, dict), f"{name}: full record has no snapshot"
    assert package.get("schema") == "sigma-paper-evidence-v2", name
    assert package.get("project_id") == compact["project_id"], name
    encoded = json.dumps(
        package, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    assert digest == compact["preflight_snapshot_sha256"], (name, digest)
    assert digest == full["snapshot_sha256"], name
    assert len(encoded) == compact["generation"]["snapshot_size_bytes"], name
    assert len(package["sources"]) == compact["source_count"], name
    print(name, "VERIFIED", digest, len(encoded), len(package["sources"]))
```

Expected SHA-256 from iteration-1 compact metadata:

| Project | Exact canonical paper-source SHA-256 |
|---|---|
| Agent | `080d3b70b67cfbe346acdb0f565d4a61c09ec4819229f2dd92dded43d9de40d9` |
| Sovereignty | `552f9458e600d3e7d0b3aa6c1dd105cc62dab4967db652123d2f134783b76f34` |
| Xenopus | `3236a8c66a96d713f28726271169e67c88c8a768f398ab3b9b504fee3cdcc74e` |

**If all three pass, the original frozen evidence is available without user intervention.** The remaining engineering question is how to feed exactly those packages to the existing authoring path safely, not how to locate the historical research.

## Reproducible regeneration choices and safety

Prefer a **throwaway isolated project clone** whose reconstructed export reproduces the canonical `_snapshot` digest exactly before any provider dispatch. `_snapshot` is a projection of `sigma.api.export_project_view` (project, strategies, sessions, artifacts, agentic runs and steps); reconstruct it losslessly from the preserved `sources` if a tested inverse exists. Do not silently rename the project, reorder source records, drop empty session fields or alter project metadata, because any of those can change the hash. Recheck `_snapshot` on the isolated clone and compare exact digest/byte length/source IDs.

A direct paper-authoring harness using the exact `snapshot` package may be acceptable **only** if it uses the same production authoring logic, options, auth and checkpoint safeguards, and is demonstrably safe and reproducible. Do not hand-edit a live `.long-paper-work` checkpoint, forge binding fingerprints, disable billing gates, or mutate original saved projects. Do not copy the frozen source contents into public issue comments or coordinator notes.

If exact reconstruction is impractical in this iteration, report that as the *remaining* blocker with an offline reproduction and proposed minimal safe adapter. **Do not run the new project snapshots as a matched A/B**. You can still finish deterministic H2-A tests and the code review; full three-paper success remains UNVERIFIED.

## Secondary gate: coordinator-authored Ruff failures

Blue reported that `./sigma test` reached and passed the paper/layout tests and Pyright, but the full command exits nonzero on formatting, import ordering and executable-bit lint diagnostics in **coordinator-owned** `docs/evaluations/report_quality/analysis/*.py`. This is a genuine integration regression attributable to coordinator scripts, **not** Blue's H2-A code. The coordinator owns remediation. Preserve scripts and tests; do not bypass repository lint by excluding the entire analysis directory or relabeling the suite green. Obtain exact Ruff diagnostics, apply formatting/import-order corrections, and restore executable bits only if the repository policy requires them; a shebang in a non-executable helper can alternatively be removed when appropriate. Record final full-suite exit code.

## Timing and disposition

Blue's `message_in_2_source_gate.md` is Git-committed at **2026-11-01T12:58:19Z = 04:58:19 PST**, despite its embedded `06:04 PST` timestamp. At this coordinator wake (05:45 PST), there is **no** `message_in_2_completion.md` and no iteration-2 paper directory. The next fixed wake is **06:45 PST**; next target **06:40 PST**. No `message_out_3.md` is authorized until the actual matching completion and full-paper review.

This recovery note is a coordinator-owned artifact for the existing iteration-2 assignment. It does not overwrite Blue's immutable messages, change source evidence, incur inference charges, or shift the hourly schedule.
