# T114 offline preparation evidence

`evidence/cumulative-plan-dry-run.json` is generated from 12 synthetic opaque
commitments. It demonstrates the seeded pair/arm schedule and proposed ceiling
arithmetic. It contains no real task, key, model output, provider request, or
scored result. The adversarial unit test also confirms incomplete and duplicate
arm records are rejected and a failed arm remains represented.

Reproduce from the repository root:

```sh
uv run --locked --no-sync python scripts/t114_cumulative_dry_run.py \
  --output docs/evaluations/t114/evidence/cumulative-plan-dry-run.json
uv run --locked --no-sync python tests/t114_cumulative_dry_run.py
```

See the [active preregistration](../T114_CUMULATIVE_PREREGISTRATION.md) for
study design, score definitions, authorization ceilings, and live freeze gates.
