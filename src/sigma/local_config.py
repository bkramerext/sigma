"""Read checkout-local dotenv data without shell evaluation or credential logging."""

import os
from pathlib import Path

from dotenv.parser import parse_stream

from sigma.investigations import ROOT


def load_local_config(root: Path = ROOT) -> None:
    path = root / ".env"
    try:
        with path.open(encoding="utf-8") as stream:
            bindings = list(parse_stream(stream))
    except FileNotFoundError:
        return
    except (OSError, UnicodeError):
        raise RuntimeError(
            "Cannot read checkout .env. Fix its permissions/UTF-8 encoding and retry."
        ) from None
    for binding in bindings:
        if binding.error or (binding.key is not None and binding.value is None):
            raise RuntimeError(
                f"Invalid checkout .env at line {binding.original.line}. "
                'Use NAME=value or export NAME="value"; fix the file and retry.'
            )
    # Parse the entire file before changing anything. No expansion, evaluation or logs.
    for binding in bindings:
        if binding.key is not None and binding.value is not None:
            os.environ.setdefault(binding.key, binding.value)
