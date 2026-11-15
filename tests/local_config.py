"""Dotenv syntax, precedence, atomic rejection and credential-safe diagnostics."""

import os
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sigma.local_config import load_local_config

with TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True):
    root = Path(temporary)
    load_local_config(root)  # Absent is normal.
    sentinel = root / "must-not-exist"
    key = "explicit-dummy-key-never-log"
    (root / ".env").write_text(
        f'\n# comment\nexport OPENAI_API_KEY="{key}"\nexport SIGMA_AI_ENABLED=1\n'
        "SINGLE='quoted # value'\nPLAIN=value # comment\nEMPTY=\n"
        f'EXEC="$(touch {sentinel})"\nBACKTICK="`touch {sentinel}`"\n'
        'LITERAL="${OPENAI_API_KEY}"\n',
        encoding="utf-8",
    )
    output = StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        load_local_config(root)
    assert not output.getvalue() and not sentinel.exists()
    assert os.environ["OPENAI_API_KEY"] == key
    assert os.environ["SIGMA_AI_ENABLED"] == "1"
    assert os.environ["SINGLE"] == "quoted # value"
    assert os.environ["PLAIN"] == "value" and os.environ["EMPTY"] == ""
    assert os.environ["LITERAL"] == "${OPENAI_API_KEY}"
    os.environ["OPENAI_API_KEY"] = "explicit-environment-wins"
    os.environ["SIGMA_AI_ENABLED"] = "0"
    load_local_config(root)
    assert os.environ["OPENAI_API_KEY"] == "explicit-environment-wins"
    assert os.environ["SIGMA_AI_ENABLED"] == "0"
    for content in (f'NEW=value\nSECRET="{key}\n', "BARE_VARIABLE\n", "export =invalid\n"):
        (root / ".env").write_text(content)
        try:
            load_local_config(root)
            raise AssertionError("Malformed configuration accepted")
        except RuntimeError as exc:
            assert key not in str(exc) and "line" in str(exc)
        assert "NEW" not in os.environ
    (root / ".env").write_bytes(b"\xff")
    try:
        load_local_config(root)
        raise AssertionError("Invalid UTF-8 accepted")
    except RuntimeError as exc:
        assert "UTF-8" in str(exc)
    with patch("pathlib.Path.open", side_effect=PermissionError(key)):
        try:
            load_local_config(root)
            raise AssertionError("Unreadable file accepted")
        except RuntimeError as exc:
            assert key not in str(exc) and "permissions" in str(exc)
print(
    "PASS checkout dotenv syntax, missing file, environment precedence, no evaluation/expansion, atomic rejection and safe errors"
)
