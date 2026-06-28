"""Starter API and engine wiring.

Scaffolded to match platform expectations for the workflow runtime:
- POST /workflows
- POST /runs
- GET  /runs/:runUid
"""
from __future__ import annotations

import contextlib
import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional, Sequence

from fastapi import FastAPI
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

app = FastAPI(title="Automatom")


class CreateWorkflowRequest(BaseModel):
    workplaceId: str
    input: List[Message]
    trigger: Optional[WorkflowTrigger] = None
    steps: Optional[List[WorkflowStep]] = None


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
async def start_run(workflow: Workflow):
    run_uid = _stable_uid("run", workflow.model_dump_json())
    run = Run(
        runUid=run_uid,
        workflow=workflow,
        status=RunStatus.QUEUED,
        startedAt=datetime.now(timezone.utc).isoformat(),
    )
    records.insert_run(run)
    return run


@app.get("/runs/{run_uid}", response_model=Optional[Run])
async def get_run(run_uid: str):
    return records.get_run(run_uid)
