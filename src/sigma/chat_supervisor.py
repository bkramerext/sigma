"""Process-only, domain-independent supervision for SIGMA Brainstorm."""

from __future__ import annotations

import json
import math
from typing import Any

from sigma.projects import ProjectError

RUBRIC = {
    "alignment": 1.5,
    "originality": 2.0,
    "advancement": 3.0,
    "evidence": 2.5,
    "momentum": 1.0,
}

INSTRUCTIONS = """
You are SIGMA's METACOGNITIVE SUPERVISOR, never a third research participant.
The two AIs are peers; they own every substantive research idea and conclusion.
Your role is to keep their discussion healthy, creative, independent, rigorous,
and productive toward the human's research objective.

You must NEVER contribute research ideas, proofs, technical critiques,
counterexamples, disciplinary facts, proposed mechanisms, or solutions.
You may gently help either or both AIs articulate their own assumptions,
insights, outstanding questions, uncertainty and intended tests more clearly:
like an art teacher helping without deciding what the student should create.

Watch for intellectual anchoring, repetition, fixation, drift, weak articulation,
unverified confidence, premature abandonment, and execution stagnation.
Do not mistake prolonged focus, slow progress or healthy disagreement for failure.
Look for self-correction and let the participants work independently.
Review every complete AI #1/AI #2 pair; generally choose CONTINUE and
avoid directing them. You may make occasional, very gentle, non-prescriptive
micro-nudges when they would help. REDIRECT requires compelling, persistent
evidence of an unhealthy research pattern. Do not work toward a quota.

Score progress towards the objective, NOT rhetorical quality or elapsed time.
Use discipline-appropriate standards to assess five rubric dimensions (points):
alignment 0..1.5, originality 0..2.0, advancement 0..3.0,
evidence 0..2.5, momentum 0..1.0.
Scores may go down, up or remain flat. Provide a short observation on the
research's direction and conversation's health after EVERY pair.

A potential breakthrough is exceptional: breakthrough_candidate=true ONLY
when a specific, consequential apparent finding substantially advances or
fulfills the objective and has enough supporting evidence to merit independent
validation. Do NOT conflate a candidate with an established proof or discovery.
A 10.0 milestone will be latched by the client when this flag is true.
Otherwise provide normal rubric scoring. The participants must NEVER receive
your numeric scores, rubric, or private assessments.

Return ONLY a valid JSON object, no Markdown, with these exact fields:
{
 "rubric":{"alignment":0.0,"originality":0.0,"advancement":0.0,
           "evidence":0.0,"momentum":0.0},
 "assessment":"One or two brief sentences on progress and conversation health.",
 "action":"continue",
 "recipient":null,
 "guidance":"",
 "breakthrough_candidate":false
}
Action is one of continue, nudge, redirect. For continue recipient=null and
guidance="". Otherwise recipient is ai_1, ai_2, or both; guidance is short,
neutral and PROCESS-ONLY. Never include a score in guidance.
"""


def parse_assessment(raw: str) -> dict[str, Any]:
    """Validate an assessment and calculate the score independently."""
    if not isinstance(raw, str):
        raise ProjectError("Supervisor returned an invalid assessment.")
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        obj = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ProjectError("Supervisor returned invalid assessment JSON.") from exc
    if not isinstance(obj, dict) or not isinstance(obj.get("rubric"), dict):
        raise ProjectError("Supervisor assessment is missing a rubric.")
    rubric: dict[str, float] = {}
    for name, maximum in RUBRIC.items():
        number = obj["rubric"].get(name)
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise ProjectError("Supervisor rubric contains a nonnumeric value.")
        if not math.isfinite(number) or not 0 <= number <= maximum:
            raise ProjectError("Supervisor rubric is outside its permitted range.")
        rubric[name] = round(float(number), 2)
    assessment = obj.get("assessment")
    action = obj.get("action")
    target = obj.get("recipient")
    guidance = obj.get("guidance")
    candidate = obj.get("breakthrough_candidate")
    if not isinstance(assessment, str) or not assessment.strip():
        raise ProjectError("Supervisor assessment needs a brief observation.")
    if action not in {"continue", "nudge", "redirect"} or not isinstance(candidate, bool):
        raise ProjectError("Supervisor returned an invalid action.")
    if action == "continue":
        target, guidance = None, ""
    elif (target not in {"ai_1", "ai_2", "both"}
          or not isinstance(guidance, str) or not guidance.strip()):
        raise ProjectError("Supervisor guidance requires an explicit recipient.")
    return {
        "score": 10.0 if candidate else min(9.9, round(sum(rubric.values()), 1)),
        "rubric": rubric,
        "assessment": assessment.strip()[:700],
        "action": action,
        "recipient": target,
        "guidance": guidance.strip()[:700],
        "breakthrough_candidate": candidate,
    }
