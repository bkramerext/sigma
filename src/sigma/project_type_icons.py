"""Opt-in AI generation of project type icons from checked-in visual references.

No provider call occurs during catalog CRUD or automated tests. An explicit
Generate/Regenerate action is required. The selected API-key connection alone is
eligible; do not silently charge a sponsor or substitute a ChatGPT token.
"""

from __future__ import annotations

import base64
import binascii
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, UnidentifiedImageError

from sigma.openai_connection import auth_context, provider_endpoint
from sigma.projects import ProjectError

STYLE_REFERENCE = Path(__file__).with_name("data") / "project_type_icon_style_reference.png"
MODEL = "gpt-image-2.5-flare"
MAX_RESPONSE_BYTES = 15_000_000
MAX_ICON_SIDE = 128


async def generate_icon(name: str, scope: str) -> dict[str, str]:
    # Sponsored provider accounting is a separate authorization boundary. An
    # icon generation must not bypass that allowance merely because a key exists.
    from sigma import cloud_workspaces

    if cloud_workspaces.enabled():
        raise ProjectError(
            "Icon generation is not yet enabled for hosted accounts; "
            "sponsored usage accounting must be configured first."
        )
    auth = await auth_context()
    if (auth["mode"] != "api_key" or auth["status"] != "connected"
            or auth["identity"] != "api_key"):
        raise ProjectError(
            "Icon generation needs the selected OpenAI API-key connection. "
            "No ChatGPT or sponsor account will be charged automatically."
        )
    try:
        style = STYLE_REFERENCE.read_bytes()
    except OSError as exc:
        raise ProjectError("The SIGMA icon style reference is unavailable") from exc
    if not style.startswith(b"\x89PNG\r\n\x1a\n") or len(style) > 4_000_000:
        raise ProjectError("The SIGMA icon style reference is invalid")

    prompt = (
        "Generate one clean, compact, symbolic project-type icon. The attached "
        "PNG is the actual SIGMA icon style reference: closely match its palette, "
        "stroke thickness, simplicity, geometry, visual weight and icon framing. "
        "This is a NEW icon, not a copy of an existing pictured subject. "
        "Use a transparent background, no letters, no text, no border, no shadow. "
        f"Project type: {name}. Scope: {scope}."
    )
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(105.0, connect=10.0),
            trust_env=False,
            follow_redirects=False,
        ) as client:
            response = await client.post(
                provider_endpoint("images/edits"),
                headers={"Authorization": f"Bearer {auth['token']}"},
                data={
                    "model": MODEL,
                    "prompt": prompt,
                    "n": "1",
                    "quality": "low",
                    "size": "1024x1024",
                    "background": "transparent",
                    "output_format": "png",
                },
                files={"image": ("sigma-icon-style-reference.png", style, "image/png")},
            )
    except (httpx.HTTPError, TimeoutError) as exc:
        raise ProjectError("Image provider unavailable; existing icon was preserved") from exc
    if response.status_code != 200:
        if response.status_code in (401, 403):
            raise ProjectError("Image provider rejected the selected API-key permissions")
        if response.status_code == 429:
            raise ProjectError("Image provider rate limit or quota reached")
        raise ProjectError("Image provider could not generate an icon; try again later")
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ProjectError("Image provider returned an oversized response")
    try:
        payload = response.json()
        encoded = payload["data"][0]["b64_json"]
        if not isinstance(encoded, str) or len(encoded) > MAX_RESPONSE_BYTES:
            raise ValueError("Invalid base64 payload")
        image_bytes = base64.b64decode(encoded, validate=True)
        with Image.open(BytesIO(image_bytes)) as source:
            source.verify()
        with Image.open(BytesIO(image_bytes)) as source:
            if source.width > 4096 or source.height > 4096:
                raise ValueError("Image is too large")
            icon = source.convert("RGBA")
            icon.thumbnail((MAX_ICON_SIDE, MAX_ICON_SIDE), Image.Resampling.LANCZOS)
            output = BytesIO()
            icon.save(output, format="PNG", optimize=True)
        from sigma.project_types import MAX_ICON_BYTES
        result = output.getvalue()
        if not result or len(result) > MAX_ICON_BYTES:
            raise ValueError("Generated icon exceeds storage limit")
    except (
        KeyError, IndexError, TypeError, ValueError, binascii.Error,
        UnidentifiedImageError, OSError,
    ) as exc:
        raise ProjectError("Image provider returned invalid icon data") from exc
    return {"kind": "data", "data_uri": "data:image/png;base64," + base64.b64encode(result).decode("ascii")}
