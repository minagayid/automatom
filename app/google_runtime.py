"""Optional Google GenAI runtime for the All Things Agentic submission.

The adapter is intentionally narrow: it prepares a reviewable brief and never
sends messages or executes arbitrary tools. Offline mode remains the default so
judges can run the repository without cloud credentials.
"""
from __future__ import annotations

import os
from typing import Any


def generate_reviewable_brief(intent: str) -> str:
    """Generate a bounded brief with Gemini through the Google GenAI SDK."""
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover - optional cloud dependency
        raise RuntimeError(
            "Gemini mode requires the optional 'google-genai' dependency"
        ) from exc

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Gemini mode requires GEMINI_API_KEY or GOOGLE_API_KEY")

    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    client = genai.Client(api_key=api_key)
    prompt = f"""You are BriefRunner, a bounded professional workflow agent.
Prepare a concise, reviewable brief for this request:

{intent}

Return these sections:
- Audience and objective
- Key findings (label assumptions and unknowns)
- Recommended next action
- Approval checkpoint

Rules:
- Do not claim live data unless it is explicitly provided.
- Do not send notifications, call arbitrary tools, or make irreversible changes.
- End with a clear human approval checkpoint.
"""
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "temperature": 0.2,
            "system_instruction": (
                "You are a safety-first agent for reviewable professional briefs. "
                "Use bounded context, state uncertainty, and preserve human approval."
            ),
        },
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini returned no text content")
    return str(text).strip()


def runtime_metadata() -> dict[str, Any]:
    return {
        "provider": "Google GenAI SDK",
        "model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        "cloudTarget": "Cloud Run",
        "approvalBoundary": "human approval required; no automatic send",
    }
