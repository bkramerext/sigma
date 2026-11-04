"""Importable SIGMA project mail with optional saved-paper attachments.

Only the explicit SMTP configuration on the SIGMA server is used. Saved
papers are intentionally excluded from the importable project attachment:
recipients can resume the research and generate their own papers.
"""

from __future__ import annotations

import json
import re
from email.message import EmailMessage
from typing import Literal

from sigma import cloud_auth, papers
from sigma.project_bundle import download_bytes, encode
from sigma.projects import ProjectError, inspect_project, project_path

MailMode = Literal["project", "pdf", "pdf_tex"]
MAX_RECIPIENTS = 10
MAX_ATTACHMENT_BYTES = 18 * 1024 * 1024


def parse_recipients(raw: str) -> list[str]:
    """Comma- or whitespace-separated, distinct, validated mailboxes."""
    parts = [part for part in re.split(r"[\s,]+", raw.strip()) if part]
    if not parts:
        raise ProjectError("Enter at least one email address.")
    if len(parts) > MAX_RECIPIENTS:
        raise ProjectError(f"Enter at most {MAX_RECIPIENTS} email addresses.")
    recipients: list[str] = []
    for part in parts:
        try:
            address = cloud_auth._normalize_email(part)
        except ValueError as exc:
            raise ProjectError(f"Invalid recipient email address: {part[:80]}") from exc
        if address not in recipients:
            recipients.append(address)
    return recipients


def email_project_bundle(path: str) -> tuple[bytes, str]:
    """Use Export's portable format, retaining all sessions but not saved papers."""
    authorized = project_path(path)
    project = inspect_project(authorized).project
    if authorized.suffix == ".json":
        raw = download_bytes(authorized)
    elif authorized.suffix == ".sigma" and authorized.is_dir():
        raw = encode(authorized)
    else:
        raise ProjectError("Unsupported project storage format")
    bundle = json.loads(raw)
    # Paper artifacts travel as *separate* attachments when requested. Do not
    # put them in the project import, even for a sender with saved versions.
    files = bundle["files"]
    for name in tuple(files):
        if name.startswith(("artifacts/papers/", "papers/")):
            del files[name]
    content = (json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", project.title).strip("-")[:80] or "project"
    return content, f"sigma-{slug}.json"


def send_project_email(
    path: str,
    raw_recipients: str,
    body: str,
    mode: MailMode,
    paper_id: str | None,
) -> int:
    """Send project + requested attachments; reject invalid inputs before SMTP."""
    recipients = parse_recipients(raw_recipients)
    if mode not in {"project", "pdf", "pdf_tex"}:
        raise ProjectError("Choose a supported attachment option.")
    if len(body) > 10_000:
        raise ProjectError("Email body is too long.")
    project = inspect_project(path).project
    project_bytes, project_filename = email_project_bundle(path)
    attachments: list[tuple[str, bytes, str, str]] = [
        (project_filename, project_bytes, "application", "json")
    ]
    if mode != "project":
        if not paper_id:
            raise ProjectError("Select a generated paper.")
        available = next(
            (
                item
                for item in papers.list_papers(path)
                if item["paper_id"] == paper_id and item["pdf_available"]
            ),
            None,
        )
        if available is None:
            raise ProjectError("The selected paper is no longer available.")
        basename = papers.paper_download_basename(path, paper_id)
        attachments.append(
            (f"{basename}.pdf", papers.get_pdf(path, paper_id), "application", "pdf")
        )
        if mode == "pdf_tex":
            attachments.append(
                (
                    f"{basename}.tex",
                    papers.paper_tex(path, paper_id).encode("utf-8"),
                    "application",
                    "x-tex",
                )
            )
    if sum(len(item[1]) for item in attachments) > MAX_ATTACHMENT_BYTES:
        raise ProjectError(
            "Attachments exceed the email size limit (18 MB). Export the project instead."
        )
    title = re.sub(r"[\r\n\x00-\x1f]+", " ", project.title).strip()[:180] or "Untitled project"
    message = EmailMessage()
    message["Subject"] = f"SIGMA project: {title}"
    introduction = body.strip()
    instructions = (
        f"Attached: SIGMA project '{title}'.\n"
        "Import the attached .json file in SIGMA to continue the research, "
        "including stopped sessions. Papers can be generated from the imported project.\n"
    )
    message.set_content(f"{introduction}\n\n{instructions}" if introduction else instructions)
    for filename, data, maintype, subtype in attachments:
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    cloud_auth.send_smtp_message(message, recipients)
    return len(recipients)
