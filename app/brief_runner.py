"""Approval-gated BriefRunner agent for the All Things Agentic submission.

The production path invokes Gemini through the Google Gen AI SDK on Vertex AI.
A deterministic fallback is retained solely for local installation without cloud
credentials; it must not be represented as Gemini output.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, replace
from typing import Any, Literal


AgentMode = Literal["offline", "gemini"]
AgentStatus = Literal["awaiting_approval", "approved"]
NotificationStatus = Literal["pending_approval", "approved_for_send"]
_TRUE_VALUES = {"1", "true", "yes"}


@dataclass(frozen=True)
class AgentResult:
    run_id: str
    mode: AgentMode
    status: AgentStatus
    brief: str
    notification_status: NotificationStatus
    sent: bool = False


def result_payload(result: AgentResult) -> dict[str, Any]:
    """Serialize the agent result using the API's camel-case contract."""

    return {
        "runId": result.run_id,
        "agentMode": result.mode,
        "status": result.status,
        "brief": result.brief,
        "approvalRequired": result.notification_status == "pending_approval",
        "notificationStatus": result.notification_status,
        "sent": result.sent,
    }


def _vertex_requested() -> bool:
    return (
        os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in _TRUE_VALUES
        or bool(os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT"))
    )


def _offline_brief(intent: str) -> str:
    topic = intent.strip().rstrip(".")
    return (
        f"Weekly professional brief for: {topic}.\n"
        "Audience and objective: a small professional team needs a fast, reviewable update.\n"
        "Key findings: deterministic demo context only; verify externally before decisions.\n"
        "Recommended next action: review the draft and assign follow-up owners.\n"
        "Approval checkpoint: explicit human approval is required; no message will be sent."
    )


def _generate_with_gemini(intent: str) -> str:
    """Import lazily so offline local installation needs no Google dependency."""

    try:  # Supports both `uvicorn main:app` and package-based test imports.
        from .google_runtime import generate_reviewable_brief
    except ImportError:
        from google_runtime import generate_reviewable_brief
    return generate_reviewable_brief(intent)


class ProfessionalBriefAgent:
    """Turn a repetitive professional request into an approval-gated brief."""

    def __init__(self, mode: str | None = None) -> None:
        requested = mode or os.getenv("AUTOMATOM_AGENT_MODE", "auto")
        if requested == "auto":
            requested = (
                "gemini"
                if (
                    os.getenv("GEMINI_API_KEY")
                    or os.getenv("GOOGLE_API_KEY")
                    or _vertex_requested()
                )
                else "offline"
            )
        if requested not in {"offline", "gemini"}:
            raise ValueError("mode must be 'offline', 'gemini', or 'auto'")
        self.mode: AgentMode = requested  # type: ignore[assignment]
        self._runs: dict[str, AgentResult] = {}

    def run(self, intent: str) -> AgentResult:
        cleaned = intent.strip()
        if len(cleaned) < 3:
            raise ValueError("intent must contain at least three non-whitespace characters")

        run_id = f"brief_{uuid.uuid4().hex[:12]}"
        brief = _generate_with_gemini(cleaned) if self.mode == "gemini" else _offline_brief(cleaned)
        result = AgentResult(
            run_id=run_id,
            mode=self.mode,
            status="awaiting_approval",
            brief=brief,
            notification_status="pending_approval",
        )
        self._runs[run_id] = result
        return result

    def approve(self, run_id: str) -> AgentResult:
        current = self._runs.get(run_id)
        if current is None:
            raise KeyError(f"unknown agent run: {run_id}")
        approved = replace(
            current,
            status="approved",
            notification_status="approved_for_send",
            sent=False,
        )
        self._runs[run_id] = approved
        return approved
