"""Starter API and engine wiring.

Scaffolded to match platform expectations for the workflow runtime:
- POST /workflows
- POST /runs
- GET  /runs/:runUid
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import List, Optional, Sequence

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from schemas import (
    InvocationType,
    Message,
    Run,
    RunStatus,
    StepType,
    Workflow,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowTrigger,
)
from services import records
from strands_runtime import ProfessionalBriefAgent, result_payload

app = FastAPI(title="Automatom")
professional_agent = ProfessionalBriefAgent()


class CreateWorkflowRequest(BaseModel):
    workplaceId: str
    input: List[Message]
    trigger: Optional[WorkflowTrigger] = None
    steps: Optional[List[WorkflowStep]] = None


class DemoRunRequest(BaseModel):
    """Small, human-readable request for the hackathon demo."""

    workplaceId: str = "demo"
    intent: str = Field(min_length=3)


def _step_output(step: WorkflowStep, intent: str, previous: str) -> str:
    settings = step.settings or {}
    if step.type == StepType.LLM:
        provider = settings.get("provider", "gemini-3.5-flash")
        return f"{provider} plan: {settings.get('instruction') or intent}"
    if step.type == StepType.SEARCH:
        return f"search results ready for: {settings.get('query') or previous or intent}"
    if step.type == StepType.NOTIFY:
        return f"notification prepared for {settings.get('to') or 'the configured channel'}"
    if step.type == StepType.DELAY:
        return f"background wait completed ({settings.get('seconds', 0)}s)"
    if step.type == StepType.CODE:
        return f"safe code step recorded: {settings.get('label') or step.label}"
    return f"{step.type.value} step completed: {step.label}"


async def _execute_background(run_uid: str, workflow: Workflow) -> None:
    """Run a workflow asynchronously while keeping the API responsive."""

    records.update_run(run_uid, status=RunStatus.RUNNING.value)
    outputs: list[str] = []
    try:
        intent = " ".join(message.content for message in workflow.input)
        if workflow.meta.get("agent") == "professional_brief":
            agent_result = professional_agent.run(intent)
            records.update_run(
                run_uid,
                status=RunStatus.DONE.value,
                finished_at=datetime.now(timezone.utc).isoformat(),
                result=json.dumps(result_payload(agent_result)),
            )
            return

        steps = workflow.workflow.steps if workflow.workflow else []
        for step in steps:
            seconds = float((step.settings or {}).get("seconds", 0))
            if step.type == StepType.DELAY and seconds > 0:
                await asyncio.sleep(min(seconds, 2))
            outputs.append(_step_output(step, intent, outputs[-1] if outputs else ""))
            await asyncio.sleep(0)
        records.update_run(
            run_uid,
            status=RunStatus.DONE.value,
            finished_at=datetime.now(timezone.utc).isoformat(),
            result="\n".join(outputs) or "completed with no steps",
        )
    except Exception as exc:  # pragma: no cover - defensive runtime boundary
        records.update_run(
            run_uid,
            status=RunStatus.FAILED.value,
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
        )


def _stable_uid(prefix: str, payload: str) -> str:
    raw = f"{prefix}:{payload}:{datetime.now(timezone.utc).isoformat()}".encode()
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:16]}"


@app.post("/workflows", response_model=Workflow)
async def create_workflow(req: CreateWorkflowRequest):
    intent_text = " ".join(m.content for m in req.input)
    workflow_uid = _stable_uid("wf", intent_text)

    steps = req.steps or [
        WorkflowStep(
            type=StepType.LLM,
            label="Interpret intent",
            settings={"instruction": intent_text},
        )
    ]

    workflow = Workflow(
        workplaceId=req.workplaceId,
        invocationType=InvocationType.INTENT,
        input=req.input,
        trigger=req.trigger,
        workflow=WorkflowDefinition(steps=steps),
    )

    records.insert_workflow(workflow_uid, workflow)

    return Workflow.model_construct(
        **workflow.model_dump(),
        schemaUid=f"{Workflow.model_fields['schemaUid'].default}:{workflow_uid[:8]}",
        taskTriggerUid=_stable_uid("trig", intent_text),
    )


@app.post("/runs", response_model=Run)
async def start_run(workflow: Workflow, background_tasks: BackgroundTasks):
    run_uid = _stable_uid("run", workflow.model_dump_json())
    run = Run(
        runUid=run_uid,
        workflow=workflow,
        status=RunStatus.QUEUED,
        startedAt=datetime.now(timezone.utc).isoformat(),
    )
    records.insert_run(run)
    background_tasks.add_task(_execute_background, run_uid, workflow)
    return run


@app.post("/demo-runs", response_model=Run)
async def start_demo_run(request: DemoRunRequest, background_tasks: BackgroundTasks):
    """Create a ready-to-watch agent run for a live demo or judge review."""

    workflow = await create_workflow(
        CreateWorkflowRequest(
            workplaceId=request.workplaceId,
            input=[Message(role="user", content=request.intent)],
            steps=[
                WorkflowStep(
                    type=StepType.LLM,
                    label="Plan with Gemini",
                    settings={"provider": "gemini-3.5-flash"},
                ),
                WorkflowStep(
                    type=StepType.SEARCH,
                    label="Gather context",
                ),
                WorkflowStep(
                    type=StepType.DELAY,
                    label="Continue in the background",
                    settings={"seconds": 0.1},
                ),
                WorkflowStep(
                    type=StepType.NOTIFY,
                    label="Return a completion handoff",
                    settings={"to": "demo inbox"},
                ),
            ],
        )
    )
    workflow.meta = {"agent": "professional_brief", "approval_required": True}
    return await start_run(workflow, background_tasks)


@app.get("/health")
async def health():
    return {"ok": True, "service": "automatom", "execution": "asynchronous"}


@app.get("/runs/{run_uid}", response_model=Optional[Run])
async def get_run(run_uid: str):
    return records.get_run(run_uid)


@app.post("/runs/{run_uid}/approve", response_model=Run)
async def approve_run(run_uid: str):
    """Approve a prepared notification without sending it automatically."""

    record = records.get_run(run_uid)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    try:
        payload = json.loads(record.get("result") or "{}")
        approved = professional_agent.approve(payload["runId"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="run is not awaiting agent approval") from exc

    records.update_run(
        run_uid,
        result=json.dumps(result_payload(approved)),
    )
    updated = records.get_run(run_uid)
    return Run.model_validate(updated)
