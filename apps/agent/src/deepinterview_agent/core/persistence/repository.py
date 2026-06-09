"""Session persistence.

The :class:`SessionRepository` protocol is the storage contract used by the prep
and post pipelines. :class:`MemoryRepository` is the default (a process-wide
singleton so a session written during ``POST /api/prep`` is visible to later
reads in the same process). :class:`SupabaseRepository` persists to the
``public.sessions`` table (see ``supabase/migrations/0001_init.sql``) and
lazy-imports the ``supabase`` SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import uuid4

from ...api.views import SessionView
from ...shared_models import AnswerRecord, InterviewContext, PrepRequest, ScoreCard
from ..logging import get_logger

if TYPE_CHECKING:
    from ..config import Settings

log = get_logger(__name__)


def _new_session_id() -> str:
    return f"sess_{uuid4().hex}"


@runtime_checkable
class SessionRepository(Protocol):
    """Storage contract for interview sessions."""

    async def create_session(self, req: PrepRequest) -> str: ...

    async def save_context(self, session_id: str, ctx: InterviewContext) -> None: ...

    async def load_context(self, session_id: str) -> InterviewContext | None: ...

    async def update_status(self, session_id: str, status: str) -> None: ...

    async def append_answer(self, session_id: str, a: AnswerRecord) -> None: ...

    async def save_scorecard(self, session_id: str, sc: ScoreCard) -> None: ...

    async def save_transcript(self, session_id: str, turns: list[dict]) -> None: ...

    async def mark_progress(self, session_id: str, step: str) -> None: ...

    async def add_warnings(self, session_id: str, warnings: list[str]) -> None: ...

    async def get_session_view(self, session_id: str) -> SessionView | None: ...


@dataclass
class _SessionRow:
    id: str
    status: str = "prep"
    # Owning user (Supabase auth uid); None for the offline/dev path. Stamped so
    # the web report's RLS read (auth.uid() = user_id) can see the row.
    user_id: str | None = None
    company: str | None = None
    cv_url: str | None = None
    jd_text: str | None = None
    language_mode: dict[str, Any] = field(default_factory=lambda: {"primary": "en", "mixed": False})
    context: dict[str, Any] | None = None
    scorecard: dict[str, Any] | None = None
    transcript: list[dict] | None = None
    answers: list[dict] = field(default_factory=list)
    progress: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class MemoryRepository:
    """In-memory repository. Status is tracked per row for test inspection."""

    def __init__(self) -> None:
        self._rows: dict[str, _SessionRow] = {}

    async def create_session(self, req: PrepRequest) -> str:
        session_id = _new_session_id()
        self._rows[session_id] = _SessionRow(
            id=session_id,
            status="prep",
            user_id=req.user_id,
            company=req.company,
            cv_url=req.cv_url,
            jd_text=req.jd_text,
            language_mode=req.language_mode.model_dump(),
        )
        return session_id

    async def save_context(self, session_id: str, ctx: InterviewContext) -> None:
        row = self._require(session_id)
        row.context = ctx.model_dump()

    async def load_context(self, session_id: str) -> InterviewContext | None:
        row = self._rows.get(session_id)
        if row is None or row.context is None:
            return None
        return InterviewContext.model_validate(row.context)

    async def update_status(self, session_id: str, status: str) -> None:
        self._require(session_id).status = status

    async def append_answer(self, session_id: str, a: AnswerRecord) -> None:
        row = self._require(session_id)
        row.answers.append(a.model_dump())
        # Persist into the canonical context too, so load_context() sees the
        # appended answer (mirrors SupabaseRepository).
        if row.context is not None:
            ctx = InterviewContext.model_validate(row.context)
            ctx.answers.append(a)
            row.context = ctx.model_dump()

    async def save_scorecard(self, session_id: str, sc: ScoreCard) -> None:
        self._require(session_id).scorecard = sc.model_dump()

    async def save_transcript(self, session_id: str, turns: list[dict]) -> None:
        self._require(session_id).transcript = list(turns)

    async def mark_progress(self, session_id: str, step: str) -> None:
        row = self._require(session_id)
        if step not in row.progress:
            row.progress.append(step)

    async def add_warnings(self, session_id: str, warnings: list[str]) -> None:
        row = self._require(session_id)
        for w in warnings:
            if w not in row.warnings:
                row.warnings.append(w)

    async def get_session_view(self, session_id: str) -> SessionView | None:
        row = self._rows.get(session_id)
        if row is None:
            return None
        context = (
            InterviewContext.model_validate(row.context) if row.context else None
        )
        scorecard = (
            ScoreCard.model_validate(row.scorecard) if row.scorecard else None
        )
        return SessionView(
            session_id=row.id,
            status=row.status,
            progress=list(row.progress),
            prep_warnings=list(row.warnings),
            context=context,
            scorecard=scorecard,
        )

    # --- test / inspection helpers (not part of the protocol) ----------------
    def get_status(self, session_id: str) -> str | None:
        row = self._rows.get(session_id)
        return row.status if row else None

    def _require(self, session_id: str) -> _SessionRow:
        row = self._rows.get(session_id)
        if row is None:
            raise KeyError(f"Unknown session_id: {session_id}")
        return row


class SupabaseRepository:
    """Persist sessions to Supabase ``public.sessions`` (lazy ``supabase`` SDK)."""

    def __init__(self, url: str, service_role_key: str) -> None:
        self._url = url
        self._key = service_role_key
        self._client: Any | None = None

    def _table(self) -> Any:
        if self._client is None:
            try:
                from supabase import create_client  # noqa: PLC0415
            except ImportError as exc:  # pragma: no cover - depends on optional SDK
                raise RuntimeError(
                    "supabase is not installed; install the 'supabase' extra."
                ) from exc
            self._client = create_client(self._url, self._key)
        return self._client.table("sessions")

    async def _exec(self, build: Any) -> Any:
        import asyncio  # noqa: PLC0415

        return await asyncio.to_thread(build)

    async def create_session(self, req: PrepRequest) -> str:
        session_id = _new_session_id()
        payload = {
            "id": session_id,
            "status": "prep",
            # Stamp the owner so the web report's RLS read (auth.uid() = user_id)
            # can see this row. None on the offline/dev path (column is nullable).
            "user_id": req.user_id,
            "company": req.company,
            "cv_url": req.cv_url,
            "jd_text": req.jd_text,
            "language_mode": req.language_mode.model_dump(),
            "progress": [],
            "prep_warnings": [],
        }
        await self._exec(lambda: self._table().insert(payload).execute())
        return session_id

    async def save_context(self, session_id: str, ctx: InterviewContext) -> None:
        await self._update(session_id, {"context": ctx.model_dump()})

    async def load_context(self, session_id: str) -> InterviewContext | None:
        def _build() -> Any:
            return self._table().select("context").eq("id", session_id).limit(1).execute()

        resp = await self._exec(_build)
        rows = getattr(resp, "data", None) or []
        if not rows or not rows[0].get("context"):
            return None
        return InterviewContext.model_validate(rows[0]["context"])

    async def update_status(self, session_id: str, status: str) -> None:
        await self._update(session_id, {"status": status})

    async def append_answer(self, session_id: str, a: AnswerRecord) -> None:
        def _build() -> Any:
            return self._table().select("context").eq("id", session_id).limit(1).execute()

        resp = await self._exec(_build)
        rows = getattr(resp, "data", None) or []
        if not rows or not rows[0].get("context"):
            return
        ctx = InterviewContext.model_validate(rows[0]["context"])
        ctx.answers.append(a)
        await self._update(session_id, {"context": ctx.model_dump()})

    async def save_scorecard(self, session_id: str, sc: ScoreCard) -> None:
        await self._update(session_id, {"scorecard": sc.model_dump()})

    async def save_transcript(self, session_id: str, turns: list[dict]) -> None:
        await self._update(session_id, {"transcript": list(turns)})

    async def mark_progress(self, session_id: str, step: str) -> None:
        def _build() -> Any:
            return self._table().select("progress").eq("id", session_id).limit(1).execute()

        resp = await self._exec(_build)
        rows = getattr(resp, "data", None) or []
        progress = list(rows[0].get("progress") or []) if rows else []
        if step not in progress:
            progress.append(step)
            await self._update(session_id, {"progress": progress})

    async def add_warnings(self, session_id: str, warnings: list[str]) -> None:
        def _build() -> Any:
            return self._table().select("prep_warnings").eq("id", session_id).limit(1).execute()

        resp = await self._exec(_build)
        rows = getattr(resp, "data", None) or []
        existing = list(rows[0].get("prep_warnings") or []) if rows else []
        changed = False
        for w in warnings:
            if w not in existing:
                existing.append(w)
                changed = True
        if changed:
            await self._update(session_id, {"prep_warnings": existing})

    async def get_session_view(self, session_id: str) -> SessionView | None:
        def _build() -> Any:
            return (
                self._table()
                .select("id,status,progress,prep_warnings,context,scorecard")
                .eq("id", session_id)
                .limit(1)
                .execute()
            )

        resp = await self._exec(_build)
        rows = getattr(resp, "data", None) or []
        if not rows:
            return None
        row = rows[0]
        ctx_data = row.get("context")
        context = InterviewContext.model_validate(ctx_data) if ctx_data else None
        sc_data = row.get("scorecard")
        scorecard = ScoreCard.model_validate(sc_data) if sc_data else None
        return SessionView(
            session_id=row["id"],
            status=row.get("status", "prep"),
            progress=list(row.get("progress") or []),
            prep_warnings=list(row.get("prep_warnings") or []),
            context=context,
            scorecard=scorecard,
        )

    async def _update(self, session_id: str, values: dict[str, Any]) -> None:
        await self._exec(lambda: self._table().update(values).eq("id", session_id).execute())


# Module-wide singleton so MemoryRepository state survives across build_deps() calls.
_MEMORY_REPO = MemoryRepository()


def get_repository(settings: Settings) -> SessionRepository:
    """Return a repository: Supabase if fully configured, else the memory singleton."""
    if settings.supabase_url and settings.supabase_service_role_key:
        return SupabaseRepository(settings.supabase_url, settings.supabase_service_role_key)
    return _MEMORY_REPO
