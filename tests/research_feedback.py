"""Exact evidence-binding guards; no inference from a program/fixture alone."""

import hashlib
from copy import deepcopy

from sigma.continuations import compact_dispatch_packet, expand_dispatch_packet
from sigma.projects import ProjectError
from sigma.research_feedback import ComputationFeedback, validate_feedback


def rejected(action):
    try:
        action()
    except ProjectError:
        return
    raise AssertionError("Expected fail-closed evidence refusal")


def main():
    text = (
        "An unverified long claim, with the decisive local counterexample and its remaining proof obligation. "
        * 8
    )
    packet = {
        "packet_digest": "saved-source-digest",
        "sources": [
            {
                "artifact_id": "source",
                "status": "local_refutation_reported",
                "artifact": {
                    "claim": text,
                    "skeptic_output": {"stop_reason": "decisive_counterexample", "response": text},
                    "objections": [text],
                },
            }
        ],
    }
    compact = compact_dispatch_packet(packet)
    assert expand_dispatch_packet(compact) == packet
    assert (
        compact["sources"][0]["artifact"]["skeptic_output"]["stop_reason"]
        == "decisive_counterexample"
    )
    assert len(str(compact)) < len(str(packet))
    assert compact_dispatch_packet({"question": "Small input"}) == {"question": "Small input"}
    corrupt = deepcopy(compact)
    corrupt["dispatch_text_pool"] = {}
    rejected(lambda: expand_dispatch_packet(corrupt))
    rejected(lambda: compact_dispatch_packet({"artifact": {"$sigma_text": "foreign alias"}}))
    execution = {
        "id": "exec",
        "status": "completed",
        "exit_code": 0,
        "stdout": '{"witness": [2,19,21]}\n',
        "stderr": "",
    }
    target = {"research_artifact_id": None, "execution": execution}
    citation = {
        "research_artifact_id": None,
        "execution_id": "exec",
        "evidence": "output",
        "filename": None,
        "use": "result",
    }
    feedback = ComputationFeedback(
        research_artifact_id=None,
        execution_id="exec",
        observed_status="completed",
        observed_field="stdout",
        observed_text_sha256=hashlib.sha256(execution["stdout"].encode()).hexdigest(),
        reported_effect="counterexample",
        next_test="Isolate the failed boundary and test the revised local conjecture.",
    ).model_dump()

    def check(f=feedback, citations=None, targets=None, question=None):
        validate_feedback(
            f,
            [citation] if citations is None else citations,
            [target] if targets is None else targets,
            next_question=feedback["next_test"] if question is None else question,
            assessment="revise",
        )

    check()
    warning = {**execution, "stderr": "A runtime warning is not a mathematical observation"}
    rejected(
        lambda: check(
            {
                **feedback,
                "observed_field": "stderr",
                "observed_text_sha256": hashlib.sha256(warning["stderr"].encode()).hexdigest(),
            },
            targets=[{**target, "execution": warning}],
            citations=[{**citation, "evidence": "error"}],
        )
    )
    rejected(lambda: check(citations=[]))
    rejected(lambda: check(targets=[]))
    rejected(lambda: check(question="Unrelated task without the observed constraint."))
    rejected(lambda: check({**feedback, "observed_status": "failed"}))
    rejected(lambda: check({**feedback, "observed_text_sha256": "0" * 64}))
    failed = {
        **execution,
        "status": "failed",
        "exit_code": 1,
        "stdout": "",
        "stderr": "RuntimeError: no observed result",
    }
    failure = {
        **feedback,
        "observed_status": "failed",
        "observed_field": "stderr",
        "observed_text_sha256": hashlib.sha256(failed["stderr"].encode()).hexdigest(),
    }
    rejected(lambda: check(failure, targets=[{**target, "execution": failed}]))
    failure["reported_effect"] = "inconclusive"
    check(
        failure,
        citations=[{**citation, "evidence": "error", "use": "limitation"}],
        targets=[{**target, "execution": failed}],
    )
    print(
        "PASS lossless evidence pooling, exact negative constraints and source coverage; missing/foreign/status/hash/citation/follow-up checks; execution failure cannot be a counterexample"
    )


if __name__ == "__main__":
    main()
