"""Offline success and failure checks for public DNS/TLS/API validation."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from sigma import public_endpoint as verify_public_endpoint


class PublicEndpointTests(unittest.TestCase):
    def probe(
        self,
        *,
        answers: set[str] | None = None,
        responses: list[tuple[int, dict[str, str], bytes]] | None = None,
    ) -> list[str]:
        queued = iter(
            responses
            or [
                (301, {"Location": "https://sigma.example.test/"}, b""),
                (200, {}, b"index"),
                (200, {}, b"index"),
                (200, {}, b'{"enabled":true,"ready":true,"target":"hosted"}'),
            ]
        )
        return verify_public_endpoint.validate_public_endpoint(
            "sigma.example.test",
            "203.0.113.10",
            resolver=lambda _: answers if answers is not None else {"203.0.113.10"},
            fetch=lambda _: next(queued),
            check_private_ports=lambda _: None,
        )

    def test_accepts_expected_dns_redirect_tls_spa_and_hosted_api(self) -> None:
        checks = self.probe()
        self.assertEqual(len(checks), 6)

    def test_rejects_dns_mismatch_before_http_requests(self) -> None:
        with self.assertRaisesRegex(ValueError, "DNS A record"):
            self.probe(answers={"203.0.113.11"})

    def test_private_port_probe_fails_on_an_open_service_port(self) -> None:
        with patch.object(verify_public_endpoint.socket, "create_connection") as connect:
            connect.return_value = MagicMock()
            with self.assertRaisesRegex(ValueError, "port 8000"):
                verify_public_endpoint.require_private_ports_closed("203.0.113.10")

    def test_rejects_noncanonical_or_missing_http_redirect(self) -> None:
        with self.assertRaisesRegex(ValueError, "redirect"):
            self.probe(responses=[(200, {}, b"")])

    def test_rejects_invalid_https_status_and_spa_route(self) -> None:
        cases = [
            (301, {"Location": "https://sigma.example.test/"}, b""),
            (200, {}, b"index"),
            (404, {}, b""),
        ]
        with self.assertRaisesRegex(ValueError, "SPA deep link"):
            self.probe(responses=cases)

    def test_rejects_unready_or_malformed_hosted_api_status(self) -> None:
        for payload in (b"not-json", b'{"enabled":true,"ready":false,"target":"hosted"}'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.probe(
                    responses=[
                        (301, {"Location": "https://sigma.example.test/"}, b""),
                        (200, {}, b"index"),
                        (200, {}, b"index"),
                        (200, {}, payload),
                    ]
                )


if __name__ == "__main__":
    unittest.main()
