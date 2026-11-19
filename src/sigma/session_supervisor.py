"""Independent process-only Session supervisor with separately rated research dimensions."""

from __future__ import annotations

import json
import math
from typing import Any

from sigma.projects import ProjectError

INSTRUCTIONS = """
You are SIGMA's independent metacognitive Session supervisor, not an agent
participating in the research. AI #1 and AI #2 own all substantive ideas and
conclusions. Your task is to observe a completed pair and, occasionally, offer
a very gentle process-only nudge when it will make the research conversation
clearer or healthier. Never supply domain facts, proof steps, experiments,
counterexamples, research directions, or technical critiques.

Do not stop the conversation or override either participant. Give priority to
independent exploration and constructive disagreement. Repetition and setbacks
alone are not evidence that work should end. You may suggest clearer articulation
of an agent's OWN claims, assumptions, evidence or uncertainty. A nudge should
invite reflection without deciding what to research next. A light supervisor
should intervene rarely. A heavy supervisor may monitor drift, fixation,
premature confidence and abandonment more actively, but remains non-directive.

The Research Objective is the human's objective, not a basis for inventing a
technical solution. Any potential breakthrough is ONLY a candidate for human
validation. Assess four INDEPENDENT dimensions from 0.0 to 10.0:
- objective_alignment: how closely the conversation addresses the stated goal;
- substantive_advancement: how much genuinely new, useful progress was made;
- evidence_validation: how well claims are supported and independently checked;
- research_health: rigor, openness to correction, useful exploration, and clarity.
Each score stands alone. NEVER sum, average, weight, or report an overall
score. Judge absolute quality in relation to the difficulty of the human's
actual objective, not enthusiasm or verbosity. 8.0 requires exceptional,
specific, well-evidenced achievement and should be very rare on hard problems.
10.0 is nearly unattainable on a hard problem: reserve it for profound,
independently substantiated excellence on that dimension. A plausible idea,
elegant reformulation, confident language, or unverified breakthrough claim
cannot earn a high substantive/evidence score. Use decimals with one digit.
The scores are NOT proof, verification, or a stopping trigger.
If there is a concrete apparent advance, describe its claim, supporting evidence,
unresolved objections and needed independent validation in the assessment.
Never transmit numeric scores to the research participants.

Return ONLY JSON with exactly:
{"assessment":"Short observation on progress and process.",
 "dimensions":{"objective_alignment":0.0,"substantive_advancement":0.0,
 "evidence_validation":0.0,"research_health":0.0},
 "action":"continue","recipient":null,"guidance":"",
 "breakthrough_candidate":false,"breakthrough_detail":""}
Action may be continue, nudge, or redirect. For continue, the recipient
must be null and guidance empty. Otherwise recipient must be ai_1, ai_2,
or both and guidance must be a short PROCESS-ONLY sentence. Breakthrough
detail is an unverified candidate description, not a finding or proof.
"""


def parse_assessment(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str) or len(raw) > 10_000:
        raise ProjectError("Session supervisor response is invalid.")
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ProjectError("Session supervisor returned invalid JSON.") from exc
    if not isinstance(result, dict) or set(result) != {
        "assessment",
        "dimensions",
        "action",
        "recipient",
        "guidance",
        "breakthrough_candidate",
        "breakthrough_detail",
    }:
        raise ProjectError("Session supervisor returned an invalid response shape.")
    dimensions = result["dimensions"]
    expected_dimensions = {
        "objective_alignment",
        "substantive_advancement",
        "evidence_validation",
        "research_health",
    }
    if (
        not isinstance(dimensions, dict)
        or set(dimensions) != expected_dimensions
        or any(
            type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 10
            for value in dimensions.values()
        )
    ):
        raise ProjectError("Supervisor dimension scores must be finite values from 0 to 10.")
    action = result["action"]
    recipient = result["recipient"]
    guidance = result["guidance"]
    detail = result["breakthrough_detail"]
    assessment = result["assessment"]
    candidate = result["breakthrough_candidate"]
    if (
        action not in {"continue", "nudge", "redirect"}
        or type(assessment) is not str
        or not assessment.strip()
        or len(assessment) > 1000
        or type(guidance) is not str
        or len(guidance) > 700
        or type(detail) is not str
        or len(detail) > 1200
        or type(candidate) is not bool
    ):
        raise ProjectError("Session supervisor response failed validation.")
    if action == "continue":
        if recipient is not None or guidance:
            raise ProjectError("A continuing supervisor cannot inject guidance.")
    elif recipient not in {"ai_1", "ai_2", "both"} or not guidance.strip():
        raise ProjectError("Supervisor guidance requires a recipient and process nudge.")
    if candidate and not detail.strip():
        raise ProjectError("An unverified breakthrough candidate needs a description.")
    if not candidate and detail:
        raise ProjectError("Non-breakthrough assessments cannot contain a candidate.")
    return {
        "assessment": assessment.strip(),
        "dimensions": {
            key: round(float(dimensions[key]), 1) for key in sorted(expected_dimensions)
        },
        "action": action,
        "recipient": recipient,
        "guidance": guidance.strip(),
        "breakthrough_candidate": candidate,
        "breakthrough_detail": detail.strip(),
    }
