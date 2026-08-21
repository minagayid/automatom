"""Safe professional-agent boundary for the Agents for Humans demo.

Strands and Bedrock are optional at import time. The default path is an honest,
deterministic offline brief so judges can run the project without AWS
credentials. When explicitly configured, the same interface delegates to a
Strands Agent backed by Amazon Bedrock and a small allow-list of tools.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, replace
from typing import Any, Literal


AgentMode = Literal["offline", "strands", "gemini"]
AgentStatus = Literal["awaiting_approval", "approved"]
NotificationStatus = Literal["pending_approval", "approved_for_send"]


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


def _offline_brief(intent: str) -> str:
    topic = intent.strip().rstrip(".")
    return (
        f"Weekly professional brief for: {topic}.\n"
        "Audience: a small professional team that needs a fast, reviewable update.\n"
        "Highlights: collect the latest context, group meaningful changes, and call out uncertainty.\n"
        "Recommended next action: review the draft, approve the notification, and assign follow-up owners.\n"
        "Source mode: deterministic demo context; verify externally before making business decisions."
    )


class ProfessionalBriefAgent:
    """Turn a repetitive professional request into an approval-gated brief."""

    def __init__(self, mode: str | None = None) -> None:
        requested = mode or os.getenv("AUTOMATOM_AGENT_MODE", "offline")
        if requested == "auto":
            if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
                requested = "gemini"
            else:
                requested = "strands" if os.getenv("STRANDS_MODEL_ID") else "offline"
        if requested not in {"offline", "strands", "gemini"}:
            raise ValueError("mode must be 'offline', 'strands', 'gemini', or 'auto'")
        self.mode: AgentMode = requested  # type: ignore[assignment]
        self._runs: dict[str, AgentResult] = {}

    def run(self, intent: str) -> AgentResult:
        cleaned = intent.strip()
        if len(cleaned) < 3:
            raise ValueError("intent must contain at least three non-whitespace characters")

        run_id = f"brief_{uuid.uuid4().hex[:12]}"
        mode: AgentMode = self.mode
        brief = _offline_brief(cleaned)
        if self.mode == "strands":
            brief = self._run_strands(cleaned)
        elif self.mode == "gemini":
            from google_runtime import generate_reviewable_brief
            brief = generate_reviewable_brief(cleaned)
        result = AgentResult(
            run_id=run_id,
            mode=mode,
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

    def _run_strands(self, intent: str) -> str:
        """Run the optional Strands path with only safe, read-only tools."""

        try:
            from strands import Agent, tool
            from strands.models import BedrockModel
        except ImportError as exc:
            raise RuntimeError(
                "Strands mode requires the optional 'strands-agents' dependency"
            ) from exc

        @tool
        def lookup_demo_context(topic: str) -> str:
            """Return bounded demo context for a professional brief topic."""

            return (
                f"Demo context for {topic}: three recent changes, two open questions, "
                "and one decision requiring owner approval."
            )

        @tool
        def draft_brief(context: str) -> str:
            """Turn bounded context into a concise reviewable professional brief."""

            return f"Draft from bounded context:\n{context}"

        model = BedrockModel(
            model_id=os.getenv("STRANDS_MODEL_ID", "amazon.nova-lite-v1:0"),
            region_name=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
            temperature=0.2,
        )
        agent = Agent(
            model=model,
            tools=[lookup_demo_context, draft_brief],
            system_prompt=(
                "You prepare concise professional briefs. Use only the provided tools. "
                "Never send messages, execute code, or claim facts not supported by context. "
                "End with a clear decision that requires human approval."
            ),
        )
        response = agent(
            f"Prepare a weekly professional brief for this request: {intent}. "
            "Include audience, highlights, uncertainty, and a recommended next action."
        )
        return str(response)
