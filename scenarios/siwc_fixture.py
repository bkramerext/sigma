"""Explicit no-network OAuth/JWKS/model/SSE fixture shared by executable checks."""

import base64
import hashlib
import json
import time
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from sigma.chatgpt_auth import EXPECTED_ENDPOINTS, ISSUER, RESOURCE, SCOPES
from sigma.proposals import Proposal

DRAFT = {
    "title": "A finite moment obstruction",
    "summary": "Compare necessary moment inequalities with independently checked cases.",
    "approach": "Construct a parameterized moment matrix and test necessary positivity inequalities without assuming sufficiency.",
    "first_tests": "Compute principal minors on independent verified inputs and perturb parameters.",
    "assumptions": "Justify convergence before interchanging sums or limits.",
    "failure_modes": "Necessary positivity may not distinguish a counterexample; finite checks are not proof.",
}


class Fixture:
    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.jwk = cast(dict[str, Any], RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True))
        self.jwk.update(kid="sigma-explicit-fixture", use="sig", alg="RS256")
        self.codes = {}
        self.refreshes = {}
        self.accesses = {}
        self.requests = []
        self.subject = "fixture-subject-one"
        self.scope = SCOPES
        self.claims_override = {}
        self.token_override = {}
        self.refresh_error: str | None = None
        self.code_error: str | None = None
        self.discovery_override = {}
        self.catalog_override: dict | None = None
        self.inference_error: tuple[int, dict] | None = None
        self.stream_override: bytes | None = None
        self.revocation_error = False
        self.serial = 0
        self.generated = 0
        self.refreshed = 0
        self.tokens = []

    def authorize(self, url, error=None, client_override=None):
        assert url.startswith(EXPECTED_ENDPOINTS["authorization_endpoint"] + "?")
        args = {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}
        assert set(args["scope"].split()) == set(SCOPES.split())
        assert args["resource"] == RESOURCE
        assert args["response_type"] == "code" and args["code_challenge_method"] == "S256"
        assert args["ext_agent_host_id"].startswith("urn:uuid:")
        assert args["redirect_uri"].startswith("http://127.0.0.1:") and args[
            "redirect_uri"
        ].endswith("/auth/callback")
        new = args["client_id"] == "dynamic_agent_client"
        assert (args.get("agent_name_hint") == "SIGMA") if new else "agent_name_hint" not in args
        self.serial += 1
        issued = f"oaiapp_fixture_{self.serial:06}" if new else args["client_id"]
        code = f"fixture-code-{self.serial}"
        self.codes[code] = {**args, "issued": issued, "subject": self.subject}
        query = {"state": args["state"]}
        if error:
            query["error"] = error
        else:
            query.update(code=code, client_id=client_override or issued)
        return args["redirect_uri"] + "?" + urlencode(query)

    def token_response(self, registration, nonce=None):
        self.serial += 1
        access, refresh = f"fixture-access-{self.serial}", f"fixture-refresh-{self.serial}"
        claims = {
            "iss": ISSUER,
            "sub": registration["subject"],
            "aud": registration["issued"],
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "email": "same-email@example.test",
            "email_verified": True,
            "name": "Controlled fixture account",
            **self.claims_override,
        }
        if nonce:
            claims["nonce"] = nonce
        if "nonce" in self.claims_override:
            claims["nonce"] = self.claims_override["nonce"]
        token = jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": self.jwk["kid"]})
        self.refreshes[refresh] = registration
        self.accesses[access] = registration
        raw = {
            "access_token": access,
            "refresh_token": refresh,
            "id_token": token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": self.scope,
            "earliest_refresh_at": time.time() + 10,
            **self.token_override,
        }
        self.tokens.extend([access, refresh, token])
        return raw

    def events(self):
        response = {
            "id": "resp-fixture",
            "status": "completed",
            "model": "gpt-6.1-sol-fixture-returned",
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": json.dumps(DRAFT)}]}
            ],
        }
        return [
            {
                "type": "response.created",
                "sequence_number": 0,
                "response": {"id": "resp-fixture", "status": "in_progress"},
            },
            {
                "type": "response.output_text.delta",
                "sequence_number": 1,
                "delta": json.dumps(DRAFT),
            },
            {"type": "response.completed", "sequence_number": 2, "response": response},
        ]

    def handler(self, request):
        self.requests.append((request.method, str(request.url)))  # Never record headers/bodies.
        url = str(request.url)
        if url == ISSUER + "/.well-known/openid-configuration":
            return httpx.Response(200, json={**EXPECTED_ENDPOINTS, **self.discovery_override})
        if url == EXPECTED_ENDPOINTS["jwks_uri"]:
            return httpx.Response(200, json={"keys": [self.jwk]})
        if url == EXPECTED_ENDPOINTS["token_endpoint"]:
            form = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
            assert form["resource"] == RESOURCE and "client_secret" not in form
            if form["grant_type"] == "authorization_code":
                registration = self.codes.pop(form["code"])
                if self.code_error:
                    return httpx.Response(400, json={"error": self.code_error})
                assert form["client_id"] == registration["issued"] != "dynamic_agent_client"
                assert form["redirect_uri"] == registration["redirect_uri"]
                challenge = (
                    base64.urlsafe_b64encode(
                        hashlib.sha256(form["code_verifier"].encode()).digest()
                    )
                    .rstrip(b"=")
                    .decode()
                )
                assert challenge == registration["code_challenge"]
                return httpx.Response(
                    200, json=self.token_response(registration, registration["nonce"])
                )
            assert form["grant_type"] == "refresh_token" and "scope" not in form
            self.refreshed += 1
            registration = self.refreshes.pop(form["refresh_token"], None)
            if self.refresh_error or registration is None:
                return httpx.Response(400, json={"error": self.refresh_error or "invalid_grant"})
            assert form["client_id"] == registration["issued"]
            return httpx.Response(200, json=self.token_response(registration))
        if url == EXPECTED_ENDPOINTS["revocation_endpoint"]:
            if self.revocation_error:
                return httpx.Response(503, json={})
            form = parse_qs(request.content.decode())
            assert form["token_type_hint"] == ["refresh_token"]
            registration = self.refreshes.pop(form["token"][0], None)
            if registration:
                assert form["client_id"] == [registration["issued"]]
            return httpx.Response(200)
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        assert token in self.accesses or token == "explicit-api-key-fixture"
        plan = token in self.accesses
        if url == RESOURCE + "/models" and request.method == "GET":
            if self.catalog_override is not None:
                return httpx.Response(200, json=self.catalog_override)
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"slug": model, "display_name": model + " (plan)", "visibility": "list"}
                        for model in ("gpt-6.1-sol", "gpt-6-luna", "gpt-6-astra")
                    ]
                }
                if plan
                else {"object": "list", "data": [{"id": "gpt-6.1-sol"}]},
            )
        assert url == RESOURCE + "/responses" and request.method == "POST"
        payload = json.loads(request.content)
        assert payload["store"] is False
        assert payload["text"]["format"]["schema"] == Proposal.model_json_schema()
        assert payload["text"]["format"]["strict"] is True
        assert payload["reasoning"]["effort"] in ("low", "medium", "high", "xhigh")
        self.generated += 1
        if self.inference_error:
            status, body = self.inference_error
            return httpx.Response(status, json=body)
        if plan:
            forbidden = {
                "max_output_tokens",
                "previous_response_id",
                "background",
                "conversation",
                "max_tool_calls",
                "metadata",
                "moderation",
                "multi_agent",
                "prompt",
                "prompt_cache_retention",
                "safety_identifier",
                "temperature",
                "top_logprobs",
                "top_p",
                "truncation",
                "user",
            }
            assert not forbidden.intersection(payload)
            assert payload["stream"] is True and isinstance(payload["input"], list)
            assert all(item.get("role") != "system" for item in payload["input"])
            content = (
                self.stream_override
                if self.stream_override is not None
                else "".join(
                    "event: " + event["type"] + "\ndata: " + json.dumps(event) + "\n\n"
                    for event in self.events()
                ).encode()
            )
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=content
            )
        assert payload["max_output_tokens"] == 25000 and isinstance(payload["input"], str)
        return httpx.Response(200, json=self.events()[-1]["response"])
