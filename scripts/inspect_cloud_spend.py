"""Read-only, identity-free diagnostic of SIGMA's durable inference budget.

This is an operator troubleshooting tool, not a budget reset. It never reads
provider credentials, records workspace identities, or changes the ledger.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import stat
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote

USD_UNITS = 1_000_000_000
STATUSES = ("usage_estimated", "reserved", "unknown", "not_dispatched")


def default_ledger() -> Path:
    configured = os.environ.get("SIGMA_CLOUD_WORKSPACES_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser() / "cloud-research.sqlite3"
    auth = Path(
        os.environ.get("SIGMA_CLOUD_AUTH_HOME", str(Path.home() / ".sigma" / "local-cloud-auth"))
    ).expanduser()
    return auth / "workspaces" / "cloud-research.sqlite3"


def _usd_units(value: object) -> int:
    try:
        cost = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Ledger contains invalid amount") from exc
    if not cost.is_finite() or cost < 0:
        raise ValueError("Ledger contains invalid amount")
    return int((cost * USD_UNITS).to_integral_value(rounding=ROUND_CEILING))


def inspect_ledger(path: Path) -> dict[str, object]:
    # Never create, migrate or rewrite a ledger merely to inspect it.
    if path.is_symlink():
        raise ValueError("Refusing symlinked ledger")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError("Refusing a ledger with unsafe ownership or permissions")
    uri = f"file:{quote(str(path.resolve()), safe='/')}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5) as db:
        rows = db.execute("SELECT status,amount_usd FROM calls").fetchall()
    amounts = {name: 0 for name in STATUSES}
    counts = {name: 0 for name in STATUSES}
    for name, cost in rows:
        if name not in amounts:
            raise ValueError("Ledger contains unknown call status")
        amounts[name] += _usd_units(cost)
        counts[name] += 1

    total = sum(amounts.values())
    configured = os.environ.get("SIGMA_CLOUD_GLOBAL_SPEND_CEILING_USD", "").strip()
    # This standalone process does not inherit environment variables injected
    # only into the running web server. Do not present an inferred cap as fact.
    return {
        "format_version": 1,
        "diagnostic": "read_only_aggregate_without_workspace_identifiers",
        "status_counts": counts,
        "status_amounts_usd": {
            key: round(amounts[key] / USD_UNITS, 9) for key in STATUSES
        },
        "global_obligations_usd": round(total / USD_UNITS, 9),
        "held_or_unknown_usd": round(
            (amounts["reserved"] + amounts["unknown"]) / USD_UNITS, 9
        ),
        "configured_ceiling_in_this_shell": configured or None,
        "local_sponsored_default_ceiling_if_unset": "0.25",
        "note": "Runtime ceiling/provider may differ from this shell. No reset performed.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger", type=Path, default=default_ledger(), help="Existing private ledger file"
    )
    args = parser.parse_args()
    try:
        summary = inspect_ledger(args.ledger)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(2, f"Cannot inspect inference ledger safely: {exc}\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
