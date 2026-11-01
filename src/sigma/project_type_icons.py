"""Explicitly configured OpenAI image editing for custom project type icons."""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from sigma import openai_connection
from sigma.projects import ProjectError

_REFERENCE = Path(__file__).with_name("data") / "project_type_icon_style_reference.png"
_MAX_PROVIDER_BYTES = 8_000_000


async def generate(name: str, scope: str, description: str) -> dict[str, str]:
    enabled = os.environ.get("SIGMA_PROJECT_TYPE_IMAGE_GENERATION_ENABLED", "").casefold()
    if enabled not in {"1", "true", "yes"}:
        raise ProjectError(
            "AI icon generation is disabled. An operator must explicitly enable it and configure API-key billing."
        )
    context = await openai_connection.auth_context()
    if (
        context.get("status") != "connected"
        or context.get("mode") != "api_key"
        or not context.get("token")
    ):
        raise ProjectError(
            "AI icon generation requires a connected OpenAI API-key billing selection. ChatGPT plan access is not used for image generation."
        )
    if not _REFERENCE.is_file() or _REFERENCE.stat().st_size > 2_000_000:
        raise ProjectError("SIGMA's built-in icon style reference is unavailable.")
    prompt = (
        "Create one minimal SIGMA project-category icon. Use the supplied image only as the visual "
        "style reference: a 24 by 24 viewBox, one copper-gold line (#d6a36f), thin rounded strokes, "
        "transparent background, no border, no lettering, no shadows, no gradients, no surrounding "
        "scene. Output a single centered, legible symbol that will be displayed at 20 to 26 pixels. "
        f"Category name: {name.strip()}\nScope: {scope.strip()}\nDescription: {description.strip()}"
    )
    reference = "data:image/png;base64," + base64.b64encode(_REFERENCE.read_bytes()).decode("ascii")
    payload = {
        "model": "gpt-image-2.5-sunburst",
        "images": [{"image_url": reference}],
        "prompt": prompt,
        "background": "transparent",
        "output_format": "png",
        "quality": "low",
        "size": "1024x1024",
        "n": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
            response = await client.post(
                "https://api.openai.com/v1/images/edits",
                headers={"Authorization": f"Bearer {context['token']}"},
                json=payload,
            )
    except (httpx.HTTPError, OSError) as exc:
        raise ProjectError(
            "Image provider is unavailable. Retry later; your current icon is unchanged."
        ) from exc
    if len(response.content) > _MAX_PROVIDER_BYTES:
        raise ProjectError(
            "Image provider returned an oversized result. Your current icon is unchanged."
        )
    if not response.is_success:
        raise ProjectError(
            f"Image generation failed (HTTP {response.status_code}). Retry; your current icon is unchanged."
        )
    try:
        document: Any = response.json()
        encoded = document["data"][0]["b64_json"]
        source = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(source)) as image:
            if image.format != "PNG" or image.width < 64 or image.height < 64:
                raise ValueError("unexpected image format or dimensions")
            image.load()
            image.thumbnail((128, 128), Image.Resampling.LANCZOS)
            optimized = io.BytesIO()
            image.convert("RGBA").save(optimized, format="WEBP", quality=82, method=6)
            data = optimized.getvalue()
        if not data.startswith(b"RIFF") or len(data) > 450_000:
            raise ValueError("optimized icon exceeds the storage limit")
    except (ValueError, TypeError, KeyError, IndexError, OSError) as exc:
        raise ProjectError(
            "Image provider returned an invalid icon. Your current icon is unchanged."
        ) from exc
    return {
        "kind": "data",
        "data_uri": "data:image/webp;base64," + base64.b64encode(data).decode("ascii"),
    }
