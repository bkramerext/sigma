"""Provider-free strict Responses schema contract and P0 #509 regressions.

The Crucible's saved Skeptic calls were rejected before inference because
Pydantic's nested ScientificEvidenceReview retained defaults and non-required
properties. No live provider calls occur in these tests.
"""

import json
from unittest.mock import patch

from sigma import (
    agentic,
    proposals,
    research_reference_compiler,
    research_reference_content,
    research_sessions,
)
from sigma.research_sessions import Investigator, ScientificEvidenceReview, Skeptic


def _assert_strict_schema(node, path="$"):
    """The strict-object contract applies recursively, even through $defs/anyOf."""
    if isinstance(node, dict):
        assert "default" not in node, f"{path}: Pydantic default leaked to provider"
        if node.get("type") == "object":
            properties = node.get("properties", {})
            assert isinstance(properties, dict), path
            assert node.get("additionalProperties") is False, path
            assert set(node.get("required", [])) == set(properties), path
            assert len(node.get("required", [])) == len(properties), path
        for key, value in node.items():
            _assert_strict_schema(value, f"{path}.{key}")
    elif isinstance(node, list):
        for number, value in enumerate(node):
            _assert_strict_schema(value, f"{path}[{number}]")


def test_crucible_provider_role_wire_schemas_are_strict_all_the_way_down():
    for model in (Investigator, Skeptic):
        schema = research_sessions._research_schema(model)
        _assert_strict_schema(schema)
        assert set(schema["required"]) == set(schema["properties"])
        assert schema["additionalProperties"] is False
        assert len(json.dumps(schema)) < 120_000


def test_skeptic_nested_scientific_evidence_is_required_and_default_free():
    schema = research_sessions._research_schema(Skeptic)
    scientific = schema["$defs"]["ScientificEvidenceReview"]
    assert scientific["type"] == "object"
    assert scientific["required"] == list(scientific["properties"])
    assert {"claim_kind", "basis_artifact_ids", "basis_step_numbers"} <= set(scientific["required"])
    assert "default" not in scientific["properties"]["claim_kind"]
    assert "default" not in schema["properties"]["scientific_evidence_review"]
    assert {"scientific_evidence_review", "negative_target", "objective_retracted"} <= set(
        schema["required"]
    )
    # Scientific evidence is not omitted just to make a provider schema pass.
    assert "ScientificEvidenceReview" in schema["$defs"]
    assert {"objective_requirements", "rationale", "sufficiency"} <= set(scientific["properties"])


def test_role_payloads_marshal_and_pydantic_validate_after_wire_normalization():
    investigator = Investigator.model_validate(
        {
            "claim": "Unverified candidate",
            "method": "Check a bounded inference.",
            "reasoning_steps": [],
            "claim_is_conditional": False,
            "assumptions": [],
            "evidence_status": "No independent verification.",
            "open_obligations": [],
            "python_code": None,
            "prior_session_failure_attempt_ids": [],
            "human_guidance_reviews": [],
            "computational_citations": [],
        }
    )
    skeptic = Skeptic.model_validate(
        {
            "assessment": "continue",
            "stop_reason": "unresolved",
            "response": "Evidence remains incomplete.",
            "objections": [],
            "remaining_obligations": [],
            "next_question": "",
            "objective_status": "partial",
            "solution_claim": "",
            "argument_summary": "",
            "reasoning_assessments": [],
            "claim_is_conditional": False,
            "assumptions_reviewed": [],
            "proof_obligations": [],
            "unresolved_objections": [],
            "supporting_cycles": [],
            "verification_status": "incomplete",
            "strategy_contribution": "unproductive",
            "contribution_rationale": "Unverified",
            "cross_strategy_relations": [],
            "retracted_cross_strategy_source_artifact_ids": [],
            "peer_handoff_reviews": [],
            "obligation_reviews": [],
            "human_guidance_reviews": [],
            "computational_citations": [],
            "scientific_evidence_review": {
                "sufficiency": "unassessed",
                "objective_requirements": [],
                "basis_artifact_ids": [],
                "basis_step_numbers": [],
                "rationale": "The recorded findings do not yet establish the scoped objective.",
            },
        }
    )
    for role, parsed in (("investigator", investigator), ("skeptic", skeptic)):
        schema = research_sessions._research_schema(type(parsed))
        on_wire = parsed.model_dump(mode="json")
        assert set(on_wire) == set(schema["properties"]), role
        assert type(parsed).model_validate_json(json.dumps(on_wire)) == parsed
        packet = research_sessions._role_request_payload(
            {"model": "gpt-6.1-sol", "reasoning_effort": "high", "mode": "api_key"},
            role,
            {"problem": "Provider-free Crucible schema preflight."},
        )
        assert packet["text"]["format"]["schema"] == schema
    assert skeptic.scientific_evidence_review is not None
    assert skeptic.scientific_evidence_review.claim_kind == "unassessed"
    try:
        ScientificEvidenceReview.model_validate(
            {
                **skeptic.scientific_evidence_review.model_dump(),
                "rationale": "too short",
            }
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Scientific evidence validation was weakened")


def test_other_generated_role_schema_contracts_and_compiler():
    # Other roles generate schemas directly. Preserve coverage if defaults
    # are introduced there; papers have their own recursive normalization.
    for model in (
        agentic.Candidate,
        agentic.Review,
        proposals.Proposal,
        proposals.StrategySuggestion,
        proposals.InferredStrategy,
    ):
        _assert_strict_schema(model.model_json_schema())
    request = research_reference_compiler.build_request(
        {
            "model": "gpt-6.1-sol",
            "mode": "api_key",
            "problem": "Provider-free schema check",
            "research_method_sources": {"sources": []},
            "strategy_runs": [],
        }
    )
    _assert_strict_schema(request["text"]["format"]["schema"])
    assert request["text"]["format"]["name"] == "research_reference_compilation"


def test_brandeis_access_denial_remains_explicit_unavailable():
    urls = (
        "https://www.brandeis.edu/writing-program/resources/faculty/handouts/writing-a-literature-review.html",
        "https://www.brandeis.edu/writing-program/resources/faculty/writing-handbook/01-critical-thinking/close-reading-step-by-step.html",
    )
    for url in urls:
        with patch.object(
            research_reference_content, "_read_remote", return_value=(403, "text/html", b"", None)
        ):
            frozen = research_reference_content.freeze_reference_content(url)
        assert frozen["status"] == "unavailable"
        assert frozen["reason"] == "http_403"
        assert frozen["excerpt"] is None
        assert frozen["content_sha256"] is None
        assert frozen["retrieved_at"] is None


if __name__ == "__main__":
    test_crucible_provider_role_wire_schemas_are_strict_all_the_way_down()
    test_skeptic_nested_scientific_evidence_is_required_and_default_free()
    test_role_payloads_marshal_and_pydantic_validate_after_wire_normalization()
    test_other_generated_role_schema_contracts_and_compiler()
    test_brandeis_access_denial_remains_explicit_unavailable()
    print("Research provider schema contracts: PASS")
