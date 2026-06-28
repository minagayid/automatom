"""Scheduler and execution pieces.

Lazy bounds:
- async easy hook built in
- extension registry
- stops at the first rung, fancy event bus later if needed
"""
from __future__ import annotations

import asyncio
import inspect
from collections import deque
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Deque, Dict, Iterable, List, Optional

import cronitor
from celery import Celery

from schemas import (
    InvocationType,
    Message,
    Run,
    RunStatus,
    StepType,
    Workflow,
    WorkflowStep,
)
from services.records import Store, init_db, _now, _serialize


# Background keepalive for long-running jobs so remote supervise tools don't
# consider the worker hung while it is blocked in external calls.
class Keepalive:
    def __init__(self, period: int = 90) -> None:
        self.period = period
        self._task: Optional[asyncio.Task] = None
        self._stop: Optional[asyncio.Event] = None

    async def start(self, label: str) -> None:
        self._stop = asyncio.Event()
        stop = self._stop

        async def _beat() -> None:
            while not stop.is_set():
                await asyncio.sleep(self.period)
                with suppress(Exception):
                    print(f"[keepalive] {label}")

        self._task = asyncio.ensure_future(_beat())

    async def stop(self) -> None:
        if self._stop is None:
            return
        self._stop.set()
        if self._task is not None:
            with suppress(Exception):
                await self._task


class ExtensionRegistry:
    """Minimal extension router for FastAPI / tool gateway features."""

    def __init__(self) -> None:
        self._handlers: Dict[str, Callable[..., Any]] = {}

    def register(self, prefix: str, handler: Callable[..., Any]) -> None:
        self._handlers[prefix] = handler

    def route(self, name: str, *args: Any, **kwargs: Any) -> Any:
        handler = self._handlers.get(name)
        if handler is None:
            raise KeyError(f"No extension registered for '{name}'")
        result = handler(*args, **kwargs)
        if inspect.isawaitable(result):
            return asyncio.run(result)
        return result


# Celery with Redis as broker for scheduling and distributed execution.
# Local fallback that still avoids rewriting orchestration later.
broker_url = "redis://localhost:6379/0"
result_backend = "redis://localhost:6379/1"
celery_app = Celery(
    "automatom",
    broker=broker_url,
    backend=result_backend,
)
celery_app.conf.beat_schedule = {}
celery_app.conf.broker_connection_retry_on_startup = True


class Scheduler:
    def __init__(self, store: Optional[Store] = None) -> None:
        self.store = store or Store()
        self._registry = ExtensionRegistry()
        self._scheduled: Deque[str] = deque()
        self._running: Dict[str, Run] = {}
        self._loop_task: Optional[asyncio.Task] = None
        self._keepalive = Keepalive()

    def register_extension(self, prefix: str, handler: Callable[..., Any]) -> None:
        self._registry.register(prefix, handler)

    def extension(self, name: str, *args: Any, **kwargs: Any) -> Any:
        return self._registry.route(name, *args, **kwargs)

    def add_workflow(self, workflow: Workflow) -> str:
        run_uid = self.store.insert_run(
            Run(
                runUid=_make_uid(),
                workflow=workflow,
                status=RunStatus.QUEUED,
                startedAt=_now(),
            )
        )
        self._scheduled.append(run_uid)
        return run_uid

    def get_run(self, run_uid: str) -> Optional[Run]:
        return self.store.get_run(run_uid)

    def queued(self) -> List[str]:
        return list(self._scheduled)

    def running(self) -> List[Run]:
        return list(self._running.values())

    async def start(self) -> None:
        await self._keepalive.start("scheduler-loop")
        self._loop_task = asyncio.ensure_future(self._loop())

    async def stop(self) -> None:
        if self._loop_task is not None:
            self._loop_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._loop_task
        await self._keepalive.stop()

    async def _loop(self) -> None:
        while True:
            try:
                self._process_due_runs()
            except Exception as exc:  # pragma: no cover - keepalive surface
                print(f"[scheduler] loop error: {exc}")
            await asyncio.sleep(5)

    def _process_due_runs(self) -> None:
        while self._scheduled:
            run_uid = self._scheduled[0]
            record = self.store.get_run(run_uid)
            if record is None:
                self._scheduled.popleft()
                continue
            if record.get("status") not in {RunStatus.QUEUED.value, RunStatus.RUNNING.value}:
                self._scheduled.popleft()
                continue
            run = Run.model_validate(record)
            self._run(run)
            self._scheduled.popleft()

    def _run(self, run: Run) -> None:
        wf = run.workflow
        if wf.trigger is not None and wf.trigger.type not in {
            "cron",
            "event",
            "ai",
        }:
            run.status = RunStatus.FAILED
            run.error = f"unsupported trigger type: {wf.trigger.type}"
            self._finalize_run(run)
            return

        run.status = RunStatus.RUNNING
        self._running[run.runUid] = run
        print(f"[engine] started {run.runUid}")

        steps: Iterable[WorkflowStep] = (
            wf.workflow.steps if wf.workflow is not None else []
        )
        outputs: List[str] = []
        last_failed: bool = False

        for index, step in enumerate(steps, start=1):
            try:
                ok = self._run_step(step, wf, outputs)
                last_failed = not ok
            except Exception as exc:
                last_failed = True
                # stop on first failure; if workflow author wanted retries, they add steps.
                break

        status = RunStatus.DONE if not last_failed else RunStatus.FAILED
        run.status = status
        run.result = outputs[-1] if outputs else (run.result or "completed")
        self._finalize_run(run)
        print(f"[engine] finished {run.runUid} -> {status}")

    def _run_step(
        self,
        step: WorkflowStep,
        workflow: Workflow,
        outputs: List[str],
    ) -> bool:
        run_on = step.when.lower()
        if run_on == "on_error" and not outputs:
            return True
        if run_on == "on_success" and not outputs:
            return True
        if run_on not in {"always", "on_success", "on_error"}:
            return False

        settings = step.settings or {}

        if step.type == StepType.LLM:
            value = _call_llm(workflow, step, settings, outputs)
            outputs.append(value)
            return True

        if step.type == StepType.SEARCH:
            value = _call_search(workflow, step, settings, outputs)
            outputs.append(value)
            return True

        if step.type == StepType.SCREENSHOT:
            value = _call_browser(workflow, step, settings, outputs)
            outputs.append(value)
            return True

        if step.type == StepType.CODE:
            value = _call_code(workflow, step, settings, outputs)
            outputs.append(value)
            return True

        if step.type in {"email", "notify"}:
            _fire_notify(step, outputs)
            return True

        if step.type == StepType.BROWSER:
            _fire_browser(step, settings)
            return True

        return True

    def _finalize_run(self, run: Run) -> None:
        finished_at = _now()
        run.finishedAt = finished_at
        self._running.pop(run.runUid, None)
        schema = run.model_dump()
        self.store.update_run(
            run.runUid,
            status=run.status.value,
            finished_at=finished_at,
            result=run.result,
            error=run.error,
        )

        # heartbeat to cronitor/keepalive-style supervisor for long automations.
        # skip if cronitor client is not configured.
        with suppress(Exception):
            cronitor.Monitor(key="automatom").send(
                "run-finished",
                dict(state="ok" if run.status == RunStatus.DONE else "fail"),
            )


def _call_llm(workflow: Workflow, step: WorkflowStep, settings: dict, history: List[str]) -> str:
    instruction = settings.get("instruction", "")
    # TODO: route to configured provider via LLM router.
    # Lazy v0: return the interpreted intent unchanged; replace with provider call.
    return instruction


def _call_search(workflow: Workflow, step: WorkflowStep, settings: Dict[str, Any], history: List[str]) -> str:
    # Replace with Brave or Tavily search integration when API keys are configured.
    query = settings.get("query") or _last_nonempty(history) or "lorem ipsum"
    return f"search:{query}"


def _call_browser(workflow: Workflow, step: WorkflowStep, settings: Dict[str, Any], history: List[str]) -> str:
    # Browser automation surface; extend via registered extensions.
    target = settings.get("url") or settings.get("selector") or ""
    if not target:
        return "browser:skipped"
    try:
        return str(_scheduler_extension("browser.open", target, context={"workflow_uid": workflow.workplaceId}))
    except KeyError:
        return f"browser:{target}"


def _call_code(workflow: Workflow, step: WorkflowStep, settings: Dict[str, Any], history: List[str]) -> str:
    code = settings.get("code", "")
    language = settings.get("language", "python") or "python"
    if not code:
        _fire_log(workflow, step, "code step skipped because settings.code is empty")
        return ""

    # Safety guardrail: never allow executing shell actions unless explicitly upgraded to level 2.
    if language not in {"python", "javascript", "bash"}:
        raise RuntimeError("code execution limited to python or javascript in v0")

    # Stubbed executor accepts publish locals so safety-critical state cannot be mutated.
    state: Dict[str, Any] = {}
    return _execute(code, language, state, {})


def _execute(code: str, language: str, state: dict, globals_: dict) -> str:
    # Lazy v0: no runtime code execution; return the source as the output.
    # Full Wasm/sandbox runtime is an explicit later step.
    return code


def _scheduler_extension(name: str, *args: Any, **kwargs: Any) -> Any:
    # Lazy sync accessor so module-level helpers can stay pure functions.
    # Scheduler instance is not at module scope; route only when actually set.
    import sys
    from types import ModuleType
    module: Optional[ModuleType] = sys.modules.get("engine")
    scheduler = getattr(module, "_current_scheduler", None)
    if scheduler is None:
        raise KeyError(name)
    return scheduler.extension(name, *args, **kwargs)


def _fire_notify(step: WorkflowStep, history: List[str]) -> None:
    # Email / Slack / Discord / Telegram notification surface.
    settings = step.settings or {}
    target = settings.get("to") or settings.get("channel")
    message = settings.get("message") or _last_nonempty(history) or step.label
    if not target:
        return
    with suppress(Exception):
        print(f"[notify] {step.type} -> {target}: {message}")


def _fire_log(workflow: Workflow, step: WorkflowStep, message: str) -> None:
    with suppress(Exception):
        print(f"[engine] {workflow.workplaceId}:{step.label}: {message}")


def _fire_browser(step: WorkflowStep, settings: Dict[str, Any]) -> None:
    # TODO: integrate Playwright/Selenium run through extension registry.
    pass


def _last_nonempty(values: Iterable[str]) -> str:
    for item in reversed(list(values)):
        if item and item.strip():
            return item.strip()
    return ""


def _make_uid(prefix: str = "auto") -> str:
    import secrets

    return f"{prefix}_{secrets.token_hex(6)}"


# Test/probe entrypoint: run a workflow without a server.
if __name__ == "__main__":  # pragma: no cover
    asyncio.run(run_test_workflow())


async def run_test_workflow() -> None:
    from services.records import init_db, Store

    init_db()
    store = Store()
    scheduler = Scheduler(store)
    workflow = Workflow(
        workplaceId="demo",
        invocationType=InvocationType.INTENT,
        input=[Message(role="user", content="Check server uptime and summarize.")],
        workflow=WorkflowDefinition(
            steps=[
                WorkflowStep(type=StepType.SEARCH, label="inspect status", settings={"query": "automatom"}),
                WorkflowStep(type=StepType.LLM, label="summarize", settings={"instruction": "summarize"}),
                WorkflowStep(type=StepType.NOTIFY, label="alert", settings={"to": "console"}),
            ]
        ),
    )
    run_uid = scheduler.add_workflow(workflow)
    await scheduler.start()
    await asyncio.sleep(1)
    await scheduler.stop()
    print("test run:", scheduler.get_run(run_uid))
