"""Shared workflow schema: intent -> executable workflow + run record."""
from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    CRON = "cron"
    EVENT = "event"
    AI = "ai"


class InvocationType(str, Enum):
    INTENT = "intent"
    NATURAL_LANGUAGE = "natural_language"
    STRUCTURED = "structured"


class StepType(str, Enum):
    SEARCH = "search"
    SCREENSHOT = "screenshot"
    LLM = "llm"
    CODE = "code"
    EMAIL = "email"
    NOTIFY = "notify"
    BROWSER = "browser"
    DELAY = "delay"


class Message(BaseModel):
    """Task payload the platform can hand to agents."""

    role: str
    content: str


class WorkflowStep(BaseModel):
    type: StepType
    label: str
    when: str = Field(
        default="always",
        description="Execution gate: always / on_error / on_success.",
    )
    settings: dict = Field(default_factory=dict)


class WorkflowDefinition(BaseModel):
    steps: List[WorkflowStep]
    names: List[str] = Field(default_factory=list)
    selector: str = Field(default="last-result")
    negative: bool = False


class WorkflowTrigger(BaseModel):
    type: TriggerType
    cron: str = Field(default="0 * * * *")
    event: str = Field(default="")
    condition: str = Field(default="")


class Workflow(BaseModel):
    workplaceId: str
    path: str = Field(default="/")
    schemaUid: str = Field(default="workflow-automation")
    taskTriggerUid: str = Field(default="")

    invocationType: InvocationType
    input: List[Message] = Field(default_factory=list)
    preplanned: bool = True

    trigger: Optional[WorkflowTrigger] = None
    workflow: Optional[WorkflowDefinition] = None
    meta: dict = Field(default_factory=dict)


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Run(BaseModel):
    runUid: str
    workflow: Workflow
    status: RunStatus
    startedAt: str
    finishedAt: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None


def normalize_intent(text: str) -> str:
    """Minimal intent cleanup so intent-driven scheduling is stable."""

    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned
