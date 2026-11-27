"""SQLite-backed session repository (zero-infra local persistence).

Enabled by setting ``SQLITE_PATH`` (and leaving Supabase unset). Each session is
one row holding the same :class:`_SessionRow` the in-memory repo uses,
serialized as JSON, so behaviour is identical to :class:`MemoryRepository` —
it just survives restarts and is shared between the API and worker processes.

Every operation opens a short-lived connection (WAL mode), reads the row fresh,
applies the in-memory logic, and writes it back — no process-local cache, so
the API and the LiveKit worker never see stale state.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ...shared_models import AnswerRecord, InterviewContext, PrepRequest, ScoreCard
from .repository import MemoryRepository, _SessionRow

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    data TEXT NOT NULL
)
"""


class _DbRows:
    """Dict-like view over the sessions table, used as ``MemoryRepository._rows``."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10)

    def get(self, session_id: str) -> _SessionRow | None:
        with self._connect() as conn:
            hit = conn.execute(
                "SELECT data FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return _SessionRow(**json.loads(hit[0])) if hit else None

    def __getitem__(self, session_id: str) -> _SessionRow:
        row = self.get(session_id)
        if row is None:
            raise KeyError(session_id)
        return row

    def __setitem__(self, session_id: str, row: _SessionRow) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, created_at, updated_at, data) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at, "
                "data = excluded.data",
                (session_id, now, now, json.dumps(asdict(row))),
            )

    def recent(self, limit: int) -> list[tuple[_SessionRow, float, float]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data, created_at, updated_at FROM sessions "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [(_SessionRow(**json.loads(d)), c, u) for d, c, u in rows]


class SqliteRepository(MemoryRepository):
    """:class:`MemoryRepository` semantics, persisted to a SQLite file."""

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self._rows: Any = _DbRows(Path(path).expanduser())

    def _require(self, session_id: str) -> _SessionRow:
        row = self._rows.get(session_id)
        if row is None:
            raise KeyError(f"Unknown session_id: {session_id}")
        return row

    async def _mutate(self, session_id: str, op: Any) -> None:
        # Load fresh → run the parent's in-memory logic against a one-row cache
        # → write back. Keeps all field semantics in one place (MemoryRepository).
        row = self._require(session_id)
        db, self._rows = self._rows, {session_id: row}
        try:
            await op()
        finally:
            self._rows = db
        db[session_id] = row

    async def create_session(self, req: PrepRequest) -> str:
        db, self._rows = self._rows, {}
        try:
            session_id = await super().create_session(req)
            row = self._rows[session_id]
        finally:
            self._rows = db
        db[session_id] = row
        return session_id

    async def save_context(self, session_id: str, ctx: InterviewContext) -> None:
        await self._mutate(session_id, lambda: super(SqliteRepository, self).save_context(session_id, ctx))

    async def update_status(self, session_id: str, status: str) -> None:
        await self._mutate(session_id, lambda: super(SqliteRepository, self).update_status(session_id, status))

    async def append_answer(self, session_id: str, a: AnswerRecord) -> None:
        await self._mutate(session_id, lambda: super(SqliteRepository, self).append_answer(session_id, a))

    async def save_scorecard(self, session_id: str, sc: ScoreCard) -> None:
        await self._mutate(session_id, lambda: super(SqliteRepository, self).save_scorecard(session_id, sc))

    async def save_transcript(self, session_id: str, turns: list[dict]) -> None:
        await self._mutate(session_id, lambda: super(SqliteRepository, self).save_transcript(session_id, turns))

    async def save_coach_transcript(self, session_id: str, turns: list[dict]) -> None:
        await self._mutate(session_id, lambda: super(SqliteRepository, self).save_coach_transcript(session_id, turns))

    async def mark_progress(self, session_id: str, step: str) -> None:
        await self._mutate(session_id, lambda: super(SqliteRepository, self).mark_progress(session_id, step))

    async def add_warnings(self, session_id: str, warnings: list[str]) -> None:
        await self._mutate(session_id, lambda: super(SqliteRepository, self).add_warnings(session_id, warnings))

    async def list_sessions(self, limit: int = 50) -> list[dict]:
        return [
            _summary(row, created_at=c, updated_at=u)
            for row, c, u in self._rows.recent(limit)
        ]

    async def list_library(self, limit: int = 30) -> dict[str, list[dict]]:
        """Deduplicated saved resumes and JDs from recent sessions for mix-and-match reuse."""
        resumes: list[dict] = []
        jobs: list[dict] = []
        seen_cv: set[str] = set()
        seen_jd: set[str] = set()

        for row, _c, updated_at in self._rows.recent(limit):
            ctx = row.context or {}
            cand = ctx.get("candidate") or {}
            job = ctx.get("job") or {}
            company = (row.company or job.get("company_name") or "").strip()
            role = (job.get("title") or "").strip()

            cv = (row.cv_url or "").strip()
            if cv and cv not in seen_cv:
                seen_cv.add(cv)
                is_file = cv.startswith(("http://", "https://", "data:"))
                cand_name = (cand.get("name") or "").strip()
                if cand_name:
                    cv_label = cand_name
                elif not is_file:
                    first_line = cv.splitlines()[0].strip()
                    cv_label = first_line[:60] + ("…" if len(first_line) > 60 else "")
                else:
                    cv_label = f"Saved CV ({company})" if company else f"Saved CV ({row.id[:12]})"
                resumes.append(
                    {
                        "id": row.id,
                        "label": cv_label,
                        "cv_url": cv,
                        "is_file": is_file,
                        "updated_at": updated_at,
                    }
                )

            jd = (row.jd_text or "").strip()
            jd_key = f"{company.lower()}::{jd}"
            if jd and jd_key not in seen_jd:
                seen_jd.add(jd_key)
                if role and company:
                    jd_label = f"{role} · {company}"
                elif company:
                    snippet = jd.splitlines()[0].strip()[:40]
                    jd_label = f"{company} · {snippet}"
                else:
                    first_line = jd.splitlines()[0].strip()
                    jd_label = first_line[:60] + ("…" if len(first_line) > 60 else "")
                jobs.append(
                    {
                        "id": row.id,
                        "label": jd_label,
                        "company": company,
                        "jd_text": jd,
                        "updated_at": updated_at,
                    }
                )

        return {"resumes": resumes, "jobs": jobs}


def _summary(row: _SessionRow, *, created_at: float | None, updated_at: float | None) -> dict:
    """Lightweight listing entry — never includes CV/JD text or transcripts."""
    job = (row.context or {}).get("job") or {}
    return {
        "session_id": row.id,
        "status": row.status,
        "company": row.company or job.get("company_name"),
        "role": job.get("title"),
        "has_scorecard": row.scorecard is not None,
        "has_coach_transcript": bool(row.coach_transcript),
        "created_at": created_at,
        "updated_at": updated_at,
    }
