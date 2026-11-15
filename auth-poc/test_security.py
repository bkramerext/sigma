"""Negative security checks for the credential worker (no OpenAI traffic)."""
from __future__ import annotations

import urllib.error
import urllib.request


def assert_denied(request: urllib.request.Request, code: int) -> None:
    try:
        urllib.request.urlopen(request, timeout=3)
    except urllib.error.HTTPError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError("Protected worker API accepted an invalid request")


if __name__ == "__main__":
    # A different website cannot trigger account verification or inference.
    assert_denied(
        urllib.request.Request(
            "http://127.0.0.1:8001/verify", data=b"", method="POST"
        ),
        403,
    )
    assert_denied(
        urllib.request.Request(
            "http://127.0.0.1:8001/inference",
            data=b"",
            method="POST",
            headers={"Origin": "https://evil.invalid"},
        ),
        403,
    )
    # Host-header rebinding must not expose the internal OAuth worker.
    assert_denied(
        urllib.request.Request(
            "http://127.0.0.1:8001/health",
            headers={"Host": "evil.invalid"},
        ),
        400,
    )
    print("PASS worker origin and host boundaries")
