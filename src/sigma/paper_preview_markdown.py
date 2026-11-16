"""Ephemeral paper-preview Markdown formatting using the standard Cheap/Medium model.

This is a read-only view conversion; it never mutates the saved PDF, paper
record, canonical TeX, provenance, or provider-call checkpoint.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from sigma import papers
from sigma.model_catalog import validate_pair
from sigma.openai_connection import auth_context
from sigma.projects import ProjectError, inspect_project
from sigma.proposals import configuration
from sigma.text_conversion import FORMAT_MODEL, FORMAT_EFFORT, INSTRUCTIONS

class PaperPreviewMarkdown(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str

async def format_paper_preview(path: str, paper_id: str, expected_project_id: str) -> str:
    view = inspect_project(path)
    if view.project.id != expected_project_id:
        raise ProjectError("Project identity changed; reopen and retry.")
    text = papers.paper_text(path, paper_id)
    if len(text.encode("utf-8")) > 24000:
        raise ProjectError("Paper preview is too long for one Markdown conversion.")
    auth = await auth_context()
    config = await configuration(
        view=view, context=auth, frozen_model=FORMAT_MODEL, frozen_effort=FORMAT_EFFORT
    )
    if not config["available"]:
        raise ProjectError(config["message"])
    result, _ = await papers._provider_structured(
        {"source_format": "plain", "target_format": "markdown", "text": text},
        auth, config,
        instructions=INSTRUCTIONS + " Convert the entire saved paper text into readable Markdown, including all headings and paragraphs. Preserve all content and mathematics, without summarizing.",
        schema_name="sigma_paper_preview_markdown",
        response_model=PaperPreviewMarkdown,
        max_input_bytes=32000,
        max_output_tokens=14000,
        project_id=expected_project_id,
        project_path_value=path,
    )
    markdown = result.body
    if not markdown.strip() or len(markdown) < max(1, len(text.strip()) // 5):
        raise ProjectError("Paper formatting appears incomplete; the original preview is unchanged.")
    return markdown
