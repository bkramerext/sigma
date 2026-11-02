"""Plain-language explanations of immutable paper versions."""
from __future__ import annotations

import asyncio
import fcntl
import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sigma.projects import ProjectError, _stage, inspect_project, project_path

class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    markdown: str = Field(min_length=150, max_length=12000)

INSTRUCTIONS = """Explain this saved research paper to an intelligent nonspecialist, in accessible language.
Return concise Markdown (roughly 300-600 words) with headings: The question, The idea,
What the paper finds, What remains uncertain, and Why it matters.
Use concrete analogies only when accurate. Explain terms without sounding childish.
Never invent a result, experiment, proof, or citation. Treat unverified paper claims as claims,
not established truths. Clearly distinguish evidence from speculation, and retain limitations.
The final Markdown must start with: *AI-generated explanation; not independent verification.*
Do not output JSON except as required by the structured response schema."""

_tasks: dict[tuple[str, str, str], asyncio.Task[str]] = {}
_lock = asyncio.Lock()

def cached(record: dict[str, Any]) -> str | None:
    value = record.get("eli5")
    if (
        isinstance(value, dict)
        and value.get("source_sha256") == record.get("pdf_sha256")
        and isinstance(value.get("markdown"), str)
        and 150 <= len(value["markdown"]) <= 12000
    ):
        return value["markdown"]
    return None

def _save(path: str, paper_id: str, sha: str, markdown: str) -> str:
    from sigma import papers
    lock = papers._paper_version_lock(path)
    try:
        record = papers._read_one(path, paper_id)
        if record.get("project_id") != inspect_project(path).project.id or record.get("pdf_sha256") != sha:
            raise ProjectError("Paper changed during explanation; please retry.")
        existing = cached(record)
        if existing is not None:
            return existing
        record["eli5"] = {"source_sha256": sha, "markdown": markdown}
        data = papers._json(record)
        if len(data) > papers.MAX_PAPER_BYTES:
            raise ProjectError("Paper explanation exceeds storage limit.")
        target = project_path(path)
        if target.suffix == ".json":
            from sigma.projects import save_project_artifacts
            save_project_artifacts(target, {f"artifacts/papers/{paper_id}.json": data})
        else:
            directory = papers._paper_dir(path, create=False)
            destination = directory / f"{paper_id}.json"
            staged = _stage(directory, data)
            try:
                os.replace(staged, destination)
            finally:
                staged.unlink(missing_ok=True)
        return markdown
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        os.close(lock)

async def explain(path: str, paper_id: str, expected_binding: str, expected_project_id: str) -> str:
    from sigma import papers
    from sigma.openai_connection import auth_context
    from sigma.proposals import configuration
    record = papers.get_paper(path, paper_id)
    if record["project_id"] != expected_project_id:
        raise ProjectError("Project identity changed; reopen and retry.")
    prior = cached(record)
    if prior is not None:
        return prior
    auth = await auth_context()
    if auth["identity"] != expected_binding:
        raise ProjectError("AI connection changed; reconnect and retry.")
    config = await configuration(view=inspect_project(path), context=auth)
    if not config["available"]:
        raise ProjectError(config["message"])
    sha = record.get("pdf_sha256")
    if not isinstance(sha, str) or not record.get("pdf_available"):
        raise ProjectError("A valid saved paper PDF is required.")
    key = (str(project_path(path).resolve()), paper_id, sha)
    async with _lock:
        task = _tasks.get(key)
        if task is None or task.done():
            async def generate() -> str:
                draft = record["draft"]
                payload: dict[str, Any] = {
                    "title": record["title"], "abstract": draft.get("abstract"),
                    "problem_framing": draft.get("problem_framing", []),
                    "methods": draft.get("methods", []),
                    "sections": [
                        {"heading": part.get("heading"), "paragraphs": part.get("paragraphs", [])}
                        for part in draft.get("sections", [])
                    ],
                    "conclusions": draft.get("conclusions", []),
                    "limitations": draft.get("limitations", []),
                    "open_obligations": draft.get("open_obligations", []),
                }
                result, _ = await papers._provider_structured(
                    payload, auth, config,
                    instructions=INSTRUCTIONS, schema_name="sigma_paper_eli5_v1",
                    response_model=Explanation, max_input_bytes=110000,
                    project_id=expected_project_id, project_path_value=path,
                )
                return _save(path, paper_id, sha, result.markdown)
            task = asyncio.create_task(generate())
            _tasks[key] = task
    try:
        return await asyncio.shield(task)
    finally:
        if task.done():
            async with _lock:
                if _tasks.get(key) is task:
                    _tasks.pop(key, None)
