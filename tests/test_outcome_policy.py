"""Provider-free regression tests for scientific Outcome policy v2."""

from copy import deepcopy

from sigma import research_sessions
from sigma.research_epistemics import objective_obligation_impact


def _artifact(identifier="a", strategy="s", cycle=1, *, notes=(), achieved=True):
    argument = [
        {
            "number": 1,
            "title": "Insertion bound",
            "argument": "A new line meets at most k-1 earlier lines, making at most k new regions.",
            "epistemic_status": "deduction",
            "basis_artifact_ids": [],
            "review": {
                "disposition": "accepted",
                "rationale": "The crossing count bounds the number of newly split regions.",
                "objection": "",
                "basis_artifact_ids": [],
            },
        },
        {
            "number": 2,
            "title": "Attainment",
            "argument": "Lines y=kx+k squared have distinct pairwise crossing positions and attain each bound.",
            "epistemic_status": "deduction",
            "basis_artifact_ids": [],
            "review": {
                "disposition": "accepted",
                "rationale": "The explicit family has no triple crossings, giving exactly k new regions.",
                "objection": "",
                "basis_artifact_ids": [],
            },
        },
    ]
    investigation = {
        "claim": "R(n)=1+n(n+1)/2",
        "method": "Insertion induction with an explicit attaining family.",
        "reasoning_steps": argument,
        "assumptions": [],
        "claim_is_conditional": False,
        "open_obligations": list(notes),
        "evidence_status": "A reviewed candidate, not independently verified.",
    }
    skeptic = {
        "objective_status": "achieved" if achieved else "partial",
        "verification_status": "convincing_unverified" if achieved else "incomplete",
        "solution_claim": "R(n)=1+n(n+1)/2",
        "argument_summary": "The upper bound and attaining construction match for each k.",
        "proof_obligations": ["Upper bound", "Attainment", "Base case"],
        "supporting_cycles": [cycle],
        "claim_is_conditional": False,
        "assumptions_reviewed": [],
        "remaining_obligations": list(notes),
        "unresolved_objections": [],
        "obligation_impacts": [],
        "assessment": "continue",  # Scheduling is not evidence of proof incompleteness.
        "next_question": "Check optional peer evidence.",
        "stop_reason": "productive_conclusion",
        "objections": [],
    }
    return {
        "id": identifier,
        "strategy_id": strategy,
        "strategy_title": strategy,
        "strategy_cycle": cycle,
        "sequence": cycle,
        "coordinator_decision": "continue",
        "claim_or_question": investigation["claim"],
        "skeptic_response": "The argument is coherent, but not independently verified.",
        "objections": [],
        "open_obligations": list(notes),
        "reasoning_steps": argument,
        "investigator_output": investigation,
        "skeptic_output": skeptic,
        # Deliberately reproduce v4's incorrectly downgraded saved review.
        "objective_review": {
            "status": "partial",
            "claim": investigation["claim"],
            "argument_steps": argument,
            "argument_summary": skeptic["argument_summary"],
            "verification_status": "incomplete",
            "basis_artifact_ids": [identifier],
        },
    }


def _record(*artifacts, investigation_type="mathematical"):
    strategies = {}
    for artifact in artifacts:
        strategies[artifact["strategy_id"]] = {
            "strategy_id": artifact["strategy_id"],
            "strategy_title": artifact["strategy_title"],
            "status": "ended",
            "artifacts": [artifact["id"]],
        }
    return {
        "status": "ended",
        "investigation_type": investigation_type,
        "artifacts": list(artifacts),
        "strategy_runs": list(strategies.values()),
    }


def test_e1_complete_candidate_survives_explicit_peer_inspection_without_rewriting_history():
    note = (
        "This peer-source proof inspection is nonblocking and independent of the "
        "completed Euclidean argument; it is not a premise of that proof."
    )
    saved = _record(_artifact(notes=[note]))
    snapshot = deepcopy(saved)
    outcome = research_sessions._outcome(saved)
    assert outcome["assessment"] == "positive"
    assert outcome["label"] == "Positive · solution candidate (unverified)"
    assert outcome["solution_review"]["status"] == "achieved"
    assert outcome["solution_review"]["open_obligations"] == [note]
    assert outcome["solution_review"]["obligation_impacts"][0]["impact"] == "nonblocking_followup"
    assert outcome["verification_label"] == "Convincing but unverified"
    assert saved == snapshot


def test_unknown_and_critical_dependencies_fail_closed():
    a = _artifact(notes=["Prove that no three lines meet at one point."])
    outcome = research_sessions._outcome(_record(a))
    assert outcome["assessment"] == "mixed"
    assert outcome["solution_review"]["blocking_reasons"] == ["objective_dependency_open"]
    assert outcome["solution_review"]["obligation_impacts"][0]["impact"] == "undetermined"


def test_not_a_keyword_based_peer_exemption():
    a = _artifact(notes=["Peer-source investigation must establish the missing attainment lemma."])
    assert research_sessions._outcome(_record(a))["assessment"] == "mixed"


def test_challenged_step_blocks_achievement():
    a = _artifact()
    a["reasoning_steps"][1]["review"]["disposition"] = "challenged"
    a["reasoning_steps"][1]["review"]["objection"] = "No construction is proved."
    outcome = research_sessions._outcome(_record(a))
    assert outcome["assessment"] == "mixed"
    assert "critical_reasoning_incomplete" in outcome["solution_review"]["blocking_reasons"]


def test_unsupported_assumptions_block():
    a = _artifact()
    a["investigator_output"]["assumptions"] = ["General position for every arrangement"]
    assert research_sessions._outcome(_record(a))["assessment"] == "mixed"


def test_typed_nonblocking_requires_accepted_dependency_steps():
    note = "Inspect peer reference independently of the conclusion."
    a = _artifact(notes=[note])
    a["skeptic_output"]["obligation_impacts"] = [
        {
            "obligation_text": note,
            "impact": "nonblocking_followup",
            "dependency_rationale": "The reviewed deduction does not use this peer reference as a premise.",
            "basis_step_numbers": [1],
        }
    ]
    impact = objective_obligation_impact(
        note, skeptic=a["skeptic_output"], reviewed_steps=a["reasoning_steps"], mathematical=True
    )
    assert impact["impact"] == "nonblocking_followup"
    a["skeptic_output"]["obligation_impacts"][0]["basis_step_numbers"] = [8]
    impact = objective_obligation_impact(
        note, skeptic=a["skeptic_output"], reviewed_steps=a["reasoning_steps"], mathematical=True
    )
    assert impact["impact"] == "undetermined"


def test_portfolio_order_independent_and_partial_sibling_does_not_veto():
    complete = _artifact("a", "alpha")
    partial = _artifact("b", "beta", achieved=False)
    first = research_sessions._outcome(_record(complete, partial))
    second = research_sessions._outcome(_record(partial, complete))
    assert first["assessment"] == second["assessment"] == "positive"
    assert first["label"] == second["label"]
    assert first["solution_review"]["claim"] == second["solution_review"]["claim"]


def test_explicit_cross_strategy_contradiction_blocks():
    a = _artifact("a", "alpha")
    b = _artifact("b", "beta")
    a["skeptic_output"]["cross_strategy_relations"] = [
        {
            "artifact_id": "b",
            "strategy_id": "beta",
            "relation": "contradicts",
            "rationale": "The same objective and assumptions have incompatible results.",
        }
    ]
    for artifacts in ((a, b), (b, a)):
        outcome = research_sessions._outcome(_record(*artifacts))
        assert outcome["label"] == "Mixed · conflicting findings, unresolved"


def test_wording_difference_alone_is_not_a_conflict():
    a = _artifact("a", "alpha")
    b = _artifact("b", "beta")
    b["objective_review"]["claim"] = "The maximum count is one plus a triangular number."
    assert research_sessions._outcome(_record(a, b))["assessment"] == "positive"


def test_supported_negative_result_vs_failed_strategy():
    a = _artifact(achieved=False)
    a["coordinator_decision"] = "stop_decisive_counterexample"
    sk = a["skeptic_output"]
    sk.update(
        {
            "stop_reason": "decisive_counterexample",
            "objections": ["An explicit counterexample falsifies the exact hypothesis."],
            "negative_target": "project_objective",
            "negative_evidence_basis_artifact_ids": ["a"],
            "negative_rationale": "The reviewed counterexample addresses the stated hypothesis and rules it out.",
        }
    )
    assert research_sessions._outcome(_record(a))["label"] == (
        "Negative · supported negative finding (unverified)"
    )
    sk["negative_target"] = "strategy_claim"
    assert research_sessions._outcome(_record(a))["assessment"] == "mixed"


def test_retraction_and_absence_are_not_negative_findings():
    a = _artifact(achieved=False)
    a["skeptic_output"]["objective_retracted"] = True
    assert research_sessions._outcome(_record(a))["label"] == "Mixed · claim retracted"
    a["skeptic_output"]["objective_retracted"] = False
    a["objective_review"]["status"] = "not_achieved"
    assert research_sessions._outcome(_record(a))["assessment"] == "mixed"


def test_empirical_claim_requires_recorded_evidence_not_only_agent_agreement():
    a = _artifact()
    a["skeptic_output"]["scientific_evidence_review"] = {
        "sufficiency": "sufficient_for_scoped_claim",
        "claim_kind": "empirical",
        "objective_requirements": ["An actual controlled observation"],
        "basis_artifact_ids": ["a"],
        "rationale": "The agents report the effect and characterize the necessary supporting observations.",
    }
    outcome = research_sessions._outcome(_record(a, investigation_type="biology"))
    assert outcome["assessment"] == "mixed"
    assert "empirical_observations_not_recorded" in outcome["solution_review"]["blocking_reasons"]


def test_reported_verification_is_not_an_independent_check():
    a = _artifact()
    a["objective_review"]["status"] = "achieved"
    a["objective_review"]["verification_status"] = "verified"
    outcome = research_sessions._outcome(_record(a))
    assert outcome["assessment"] == "mixed"
    assert outcome["verification_label"] == "Reported verified; not independently checked by SIGMA"


def test_saved_counterexample_not_automatically_negative_when_objective_solved():
    a = _artifact()
    a["skeptic_output"]["negative_target"] = "strategy_claim"
    a["skeptic_output"]["objections"] = []
    assert research_sessions._outcome(_record(a))["assessment"] == "positive"


def test_e2_typed_peer_followup_requires_cited_saved_peer_artifact():
    note = "Inspect the independent peer proof source for future publication."
    complete = _artifact("a", "incremental", notes=[note])
    other = _artifact("peer", "euler", achieved=False)
    complete["skeptic_output"]["verification_followups"] = [
        {
            "text": note,
            "kind": "peer_source_inspection",
            "basis_artifact_ids": ["peer"],
            "rationale": (
                "The accepted local proof derives both bounds without using "
                "the peer artifact as a mathematical premise."
            ),
        }
    ]
    record = _record(complete, other)
    assert research_sessions._outcome(record)["assessment"] == "positive"

    complete["skeptic_output"]["verification_followups"][0]["basis_artifact_ids"] = ["unknown-peer"]
    blocked = research_sessions._outcome(record)
    assert blocked["assessment"] == "mixed"
    assert "peer_followup_reference_invalid" in blocked["solution_review"]["blocking_reasons"]


def test_execution_failure_does_not_erase_existing_complete_candidate():
    record = _record(_artifact())
    record["status"] = "failed"
    outcome = research_sessions._outcome(record)
    assert outcome["assessment"] == "positive"
    assert "execution failed" in " ".join(outcome["caveats"]).lower()
    assert "Complete reviewed candidate answer" in outcome["conclusion"]


def test_unlinked_model_contradiction_fails_conservatively():
    complete = _artifact("a", "alpha")
    disputed = _artifact("b", "beta", achieved=False)
    disputed["skeptic_output"]["cross_strategy_relations"] = [{"relation": "contradicts"}]
    assert (
        research_sessions._outcome(_record(complete, disputed))["label"]
        == "Mixed · conflicting findings, unresolved"
    )


def test_two_incomplete_strategies_do_not_combine_into_a_solution():
    a = _artifact("a", "alpha", achieved=False)
    b = _artifact("b", "beta", achieved=False)
    result = research_sessions._outcome(_record(a, b))
    assert result["assessment"] == "mixed"
    assert result["solution_review"]["status"] != "achieved"
