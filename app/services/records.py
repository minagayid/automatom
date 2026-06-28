"""Read/write layer.

Pluggable implementation: SQLite now as the least lazy move that actually works.
A file-based DB means no extra process, migrations, or infra for v0.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

import aiosqlite

DB_PATH = Path(__file__).with_name("automatom.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=True, default=str)


def _deserialize(raw: str) -> Any:
    import json

    return json.loads(raw)


class Store:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = str(path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflows(
                  workflow_uid TEXT PRIMARY KEY,
                  workplace_id TEXT NOT NULL,
                  schema TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs(
                  run_uid TEXT PRIMARY KEY,
                  workflow_uid TEXT NOT NULL,
                  status TEXT NOT NULL,
                  schema TEXT NOT NULL,
                  started_at TEXT NOT NULL,
                  finished_at TEXT,
                  result TEXT,
                  error TEXT
                );
                CREATE TABLE IF NOT EXISTS events(
                  event_uid TEXT PRIMARY KEY,
                  workflow_uid TEXT NOT NULL,
                  event_type TEXT NOT NULL,
                  schema TEXT NOT NULL,
                  received_at TEXT NOT NULL
                );
                """
            )

    def insert_workflow(self, workflow_uid: str, workflow: Any, workplace_id: Optional[str] = None) -> None:
        schema = workflow.model_dump()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO workflows(workflow_uid, workplace_id, schema, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    workflow_uid,
                    workplace_id or schema.get("workplaceId"),
                    _serialize(schema),
                    _now(),
                ),
            )
            conn.commit()

    def get_workflow(self, workflow_uid: str) -> Optional[dict]:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT schema FROM workflows WHERE workflow_uid = ?",
                (workflow_uid,),
            ).fetchone()
        return _deserialize(row[0]) if row else None

    def list_workflows(self, workplace_id: str) -> list[dict]:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT schema FROM workflows WHERE workplace_id = ?",
                (workplace_id,),
            ).fetchall()
        return [_deserialize(r[0]) for r in rows]

    def insert_run(self, run: Any) -> str:
        schema = run.model_dump()
        run_uid = schema.get("runUid") or schema.get("run_uid")
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO runs(run_uid, workflow_uid, status, schema, started_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_uid,
                    schema.get("workflow", {}).get("workplaceId"),
                    schema.get("status", "queued"),
                    _serialize(schema),
                    _now(),
                ),
            )
            conn.commit()
        return run_uid

    def get_run(self, run_uid: str) -> Optional[dict]:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT schema FROM runs WHERE run_uid = ?",
                (run_uid,),
            ).fetchone()
        return _deserialize(row[0]) if row else None

    def update_run(
        self,
        run_uid: str,
        *,
        status: Optional[str] = None,
        finished_at: Optional[str] = None,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        updates: list[str] = []
        params: list[Any] = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if finished_at is not None:
            updates.append("finished_at = ?")
            params.append(finished_at)
        if result is not None:
            updates.append("result = ?")
            params.append(result)
        if error is not None:
            updates.append("error = ?")
            params.append(error)
        if not updates:
            return
        params.append(run_uid)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                f"UPDATE runs SET {', '.join(updates)} WHERE run_uid = ?",
                params,
            )
            conn.commit()

    def insert_event(self, event_uid: str, schema: dict, event_type: str) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO events(event_uid, workflow_uid, event_type, schema, received_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_uid,
                    schema.get("workplaceId", ""),
                    event_type,
                    _serialize(schema),
                    _now(),
                ),
            )
            conn.commit()


class AsyncStore:
    def __init__(self, path: str = str(DB_PATH)) -> None:
        self.path = path

    @contextmanager
    def _connection(self) -> Iterator[aiosqlite.Connection]:
        conn = aiosqlite.connect(self.path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            conn.close()

    async def insert_run(self, schema: dict) -> str:
        run_uid = schema.get("runUid") or schema.get("run_uid")
        if not run_uid:
            run_uid = schema["run_uid"] = _make_uid()
        async with self._connection() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO runs(run_uid, workflow_uid, status, schema, started_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_uid,
                    schema.get("workplaceId"),
                    schema.get("status") or "queued",
                    _serialize(schema),
                    _now(),
                ),
            )
            await conn.commit()
        return run_uid

    async def get_run(self, run_uid: str) -> Optional[dict]:
        async with self._connection() as conn:
            row = await conn.execute(
                "SELECT schema FROM runs WHERE run_uid = ?",
                (run_uid,),
            )
            row = await row.fetchone()
        return _deserialize(row["schema"]) if row else None

    async def update(self, uid: str, **fields: Any) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        params = list(fields.values()) + [uid]
        async with self._connection() as conn:
            await conn.execute(
                f"UPDATE runs SET {set_clause} WHERE run_uid = ?",
                params,
            )
            await conn.commit()

    async def insert_workflow(self, schema: dict, created_at: Optional[str] = None) -> None:
        workplace_id = schema.get("workplaceId", "")
        workflow_uid = schema.get("workflowUid") or _make_uid()
        schema["workflowUid"] = workflow_uid
        created_at = created_at or _now()
        async with self._connection() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO workflows(workflow_uid, workplace_id, schema, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (workflow_uid, workplace_id, _serialize(schema), created_at),
            )
            await conn.commit()

    async def list_workflows(self, workplace_id: str) -> list[dict]:
        async with self._connection() as conn:
            rows = await conn.execute(
                "SELECT schema FROM workflows WHERE workplace_id = ?",
                (workplace_id,),
            )
            rows = await rows.fetchall()
        return [_deserialize(r["schema"]) for r in rows]


def _make_uid(prefix: str = "auto") -> str:
    import secrets

    return f"{prefix}_{secrets.token_hex(6)}"


def init_db(path: Optional[str] = None) -> None:
    target = path or str(DB_PATH)
    with sqlite3.connect(target) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workflows(
              workflow_uid TEXT PRIMARY KEY,
              workplace_id TEXT NOT NULL,
              schema TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs(
              run_uid TEXT PRIMARY KEY,
              workflow_uid TEXT NOT NULL,
              status TEXT NOT NULL,
              schema TEXT NOT NULL,
              started_at TEXT NOT NULL,
              finished_at TEXT,
              result TEXT,
              error TEXT
            );
            CREATE TABLE IF NOT EXISTS events(
              event_uid TEXT PRIMARY KEY,
              workflow_uid TEXT NOT NULL,
              event_type TEXT NOT NULL,
              schema TEXT NOT NULL,
              received_at TEXT NOT NULL
            );
            """
        )
