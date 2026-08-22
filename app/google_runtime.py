"""Optional Google GenAI runtime for the All Things Agentic submission.

The adapter is intentionally narrow: it prepares a reviewable brief and never
sends messages or executes arbitrary tools. Offline mode remains the default so
judges can run the repository without cloud credentials. When configured, the
same contract can use either the Gemini Developer API key or Vertex AI /
Gemini Enterprise Agent Platform through Application Default Credentials.
"""
from __future__ import annotations

import os
from typing import Any


def _client_config() -> tuple[Any, str]:
    """Build a Google GenAI client using explicit API-key or Vertex ADC mode."""
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover - optional cloud dependency
        raise RuntimeError(
            "Gemini mode requires the optional 'google-genai' dependency"
        ) from exc

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key), "gemini-api-key"

    use_enterprise = os.getenv("GOOGLE_GENAI_USE_ENTERPRISE", "").lower() in {
        "1",
        "true",
        "yes",
    }
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    if use_enterprise or project:
        if not project:
            raise RuntimeError(
                "Vertex AI mode requires GOOGLE_CLOUD_PROJECT or GCP_PROJECT"
            )
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        return (
            genai.Client(enterprise=True, project=project, location=location),
            "vertex-adc",
        )

    raise RuntimeError(
        "Gemini mode requires GEMINI_API_KEY/GOOGLE_API_KEY or "
        "Vertex AI settings GOOGLE_GENAI_USE_ENTERPRISE=true and "
        "GOOGLE_CLOUD_PROJECT"
    )


def generate_reviewable_brief(intent: str) -> str:
    """Generate a bounded brief with Gemini through the Google GenAI SDK."""
    client, _ = _client_config()
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
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
    api_key_mode = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    enterprise_mode = os.getenv("GOOGLE_GENAI_USE_ENTERPRISE", "").lower() in {
        "1",
        "true",
        "yes",
    }
    return {
        "provider": "Google GenAI SDK",
        "model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        "cloudTarget": "Cloud Run",
        "authentication": "gemini-api-key" if api_key_mode else "vertex-adc" if enterprise_mode else "unconfigured",
        "approvalBoundary": "human approval required; no automatic send",
    }
