"""Regression tests for the livekit-COUPLED pieces of the WP-5 worker.

Unlike ``test_live.py`` (which pins the pure ``live.state`` machine), this module
imports ``deepinterview_agent.worker`` — which imports ``livekit.agents`` at load
time — so it SKIPS cleanly wherever the optional ``livekit`` extra is absent
(plain CI venv) and RUNS inside the worker docker image (``uv sync --extra
livekit``). Everything stays offline and deterministic: no provider construction
here performs network I/O (verified against the installed plugin source — the
Deepgram ``STT.__init__`` only validates kwargs and builds an ``STTOptions``
dataclass), and the ``InterviewContext`` comes from the WP-6 prep pipeline with
the mock adapters forced by ``conftest.py``.

What is pinned, and why it must not regress:

* ``wire_transcript_capture`` — the shutdown-time answer recovery
  (``state.reconstruct_answers``) can only recover what this wiring captured,
  tagged with the question active when it was spoken. If the
  ``conversation_item_added`` hookup or its question_id tagging breaks, sessions
  with real speech silently land on ``no_answers`` ("no report") again.
* ``_deepgram_stt`` / ``build_stt`` — plugin kwargs are passed positionally by
  name into ``deepgram.STT``; a plugin signature drift would raise at session
  start and break EVERY interview. The language→model routing (non-English →
  nova-2) exists because nova-3 streams NO Vietnamese transcripts (confirmed
  live 2026-06-10), and the per-model ``endpointing_ms`` split (25 vs 300)
  keeps Vietnamese answers from being chopped into fragments.
* ``entrypoint``'s REAL ``_on_shutdown`` closure — driven end-to-end with every
  livekit-coupled seam faked (no room, no providers, no network). This is the
  write-back that fixed the production "no report" bug, and it only exists as
  a closure: ``state.reconstruct_answers`` must run BEFORE ``has_answers`` is
  computed, the live-result POST must carry the ``no_answers`` hint only for
  truly answer-less sessions, the API→repo fallback order (and the
  save_context-failure → ``error`` branch) must hold, the payload built from
  python-mode ``ctx.model_dump()`` must stay JSON-encodable AND parse as the
  API's ``LiveResultRequest``, and scoring must fire only after a successful
  persist of a session with real answers.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, Callable

import httpx
import pytest

pytest.importorskip("livekit.agents")

from deepinterview_agent import worker  # noqa: E402
from deepinterview_agent.api.session import LiveResultRequest  # noqa: E402
from deepinterview_agent.core.deps import build_deps  # noqa: E402
from deepinterview_agent.live import state  # noqa: E402
from deepinterview_agent.live.state import InterviewUserdata  # noqa: E402
from deepinterview_agent.prep import run_prep  # noqa: E402
from deepinterview_agent.shared_models import (  # noqa: E402
    InterviewContext,
    LanguageMode,
    PrepRequest,
)

# --- helpers (same construction as tests/test_live.py) -----------------------


def _build_context() -> InterviewContext:
    """Run the offline prep pipeline and load the resulting InterviewContext."""
    deps = build_deps()
    req = PrepRequest(
        cv_url="https://example.com/cv.pdf",
        jd_text="Senior Backend Engineer building distributed payment systems in Python.",
        company="ExampleCorp",
        language_mode=LanguageMode(primary="en", mixed=False),
    )
    session_id = asyncio.run(run_prep(req, deps))
    ctx = asyncio.run(deps.repo.load_context(session_id))
    assert ctx is not None
    return ctx


def _userdata_two_sections() -> InterviewUserdata:
    """Userdata whose plan has a second question in a different section.

    The mock plan carries exactly one question (section ``intro``); a second
    one lets the tests observe the question_id tag CHANGE when the cursor
    advances.
    """
    ctx = _build_context()
    first = ctx.plan.questions[0]
    second = first.model_copy(update={"id": "q_behavioral", "section": "behavioral"})
    ctx.plan.questions.append(second)
    return InterviewUserdata(ctx=ctx, session_id=ctx.session_id)


class FakeAgentSession:
    """Minimal stand-in for the ``AgentSession`` event surface the worker uses.

    ``wire_transcript_capture`` registers via the EventEmitter decorator form
    ``@session.on("conversation_item_added")`` — i.e. ``.on(event)`` with no
    callback returns a decorator (mirrors ``livekit.agents``' ``EventEmitter.on``,
    which also accepts ``.on(event, callback)`` directly). ``emit`` then fires
    the registered handlers synchronously, exactly like the SDK does.
    """

    def __init__(self) -> None:
        self.handlers: dict[str, list[Callable[..., Any]]] = {}

    def on(
        self, event: str, callback: Callable[..., Any] | None = None
    ) -> Callable[..., Any]:
        if callback is not None:
            self.handlers.setdefault(event, []).append(callback)
            return callback

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.handlers.setdefault(event, []).append(fn)
            return fn

        return decorator

    def emit(self, event: str, ev: Any) -> None:
        for handler in self.handlers.get(event, []):
            handler(ev)


def _item_event(role: Any, text: Any) -> SimpleNamespace:
    """A fake ``conversation_item_added`` event: ``ev.item.role`` / ``.text_content``."""
    return SimpleNamespace(item=SimpleNamespace(role=role, text_content=text))


# --- wire_transcript_capture --------------------------------------------------


def test_wire_transcript_capture_tags_turns() -> None:
    """Committed turns land in userdata.transcript tagged with the ACTIVE question.

    This tag is what ``state.reconstruct_answers`` keys on at shutdown — lose it
    and unsaved answers can no longer be recovered per question.
    """
    ud = _userdata_two_sections()
    q1 = state.current_question(ud)
    assert q1 is not None

    session = FakeAgentSession()
    worker.wire_transcript_capture(session, ud)
    assert session.handlers.get("conversation_item_added"), (
        "wire_transcript_capture must register on conversation_item_added"
    )

    session.emit(
        "conversation_item_added",
        _item_event("user", "I traced a race condition in our ledger writer."),
    )
    assert ud.transcript == [
        {
            "role": "user",
            "text": "I traced a race condition in our ledger writer.",
            "question_id": q1.id,
        }
    ]

    # Advance the cursor to the second question: subsequent turns must carry
    # the NEW question's id, not the stale one.
    state.advance(ud)
    session.emit(
        "conversation_item_added",
        _item_event("assistant", "Tell me about a time you led a team."),
    )
    assert ud.transcript[-1] == {
        "role": "assistant",
        "text": "Tell me about a time you led a team.",
        "question_id": "q_behavioral",
    }
    assert len(ud.transcript) == 2


def test_wire_transcript_capture_ignores_non_turns() -> None:
    """Events without a user/assistant role or without text must not append."""
    ud = _userdata_two_sections()
    session = FakeAgentSession()
    worker.wire_transcript_capture(session, ud)

    session.emit("conversation_item_added", _item_event(None, "text with no role"))
    session.emit("conversation_item_added", _item_event("user", ""))
    session.emit("conversation_item_added", _item_event("user", None))
    session.emit("conversation_item_added", _item_event("assistant", ""))
    session.emit("conversation_item_added", _item_event("system", "function call noise"))

    assert ud.transcript == []


# --- Deepgram STT construction + routing --------------------------------------


def test_deepgram_stt_kwargs_are_valid() -> None:
    """Both tuned kwarg sets must CONSTRUCT against the installed plugin.

    ``_deepgram_stt`` passes its kwargs straight into ``deepgram.STT``; a plugin
    signature drift (renamed/removed kwarg) raises here instead of at the start
    of every live session. Construction is offline: the plugin ``__init__`` only
    validates and stores options, so a dummy ``api_key="x"`` suffices. Also pins
    the documented per-model endpointing split: nova-3 rides the semantic EOU
    model (25ms), nova-2 needs Deepgram's own 300ms silence window so languages
    with within-utterance pauses (e.g. Vietnamese) aren't fragmented.
    """
    pytest.importorskip("livekit.plugins.deepgram")

    stt_en = worker._deepgram_stt("en", "nova-3", api_key="x")
    stt_vi = worker._deepgram_stt("vi", "nova-2", api_key="x")

    assert stt_en._opts.model == "nova-3"
    assert stt_en._opts.language == "en"
    assert stt_en._opts.endpointing_ms == 25

    assert stt_vi._opts.model == "nova-2"
    assert stt_vi._opts.language == "vi"
    assert stt_vi._opts.endpointing_ms == 300
    # smart_format=True applies to both tiers (language-native number/date
    # formatting).
    assert stt_vi._opts.smart_format is True
    assert stt_en._opts.smart_format is True

    # numerals stays on the nova-3 tier only: the nova-2 tier keeps a minimal
    # flag set because unsupported combos fail SILENTLY with zero transcripts
    # (the exact vi failure mode debugged live 2026-06-10).
    assert stt_en._opts.numerals is True
    assert stt_vi._opts.numerals is False


def test_build_stt_language_routing() -> None:
    """build_stt routes language → model: vi→nova-2, en→nova-3, mixed→multi/nova-3.

    nova-3 streams NO Vietnamese transcripts (confirmed live 2026-06-10), so
    every non-English/multi language MUST route to nova-2; code-switching
    sessions use Deepgram's "multi" on nova-3.
    """
    pytest.importorskip("livekit.plugins.deepgram")
    settings = SimpleNamespace(stt_provider="deepgram", deepgram_api_key="x")

    vi = worker.build_stt(settings, "vi")
    assert (vi._opts.model, str(vi._opts.language)) == ("nova-2", "vi")

    en = worker.build_stt(settings, "en")
    assert (en._opts.model, str(en._opts.language)) == ("nova-3", "en")

    mixed = worker.build_stt(settings, "vi", mixed=True)
    assert (mixed._opts.model, str(mixed._opts.language)) == ("nova-3", "multi")


# --- the REAL _on_shutdown closure (entrypoint driven with faked seams) --------
#
# ``_on_shutdown`` is a closure inside ``worker.entrypoint``; it cannot be
# imported, only registered. So these tests run the genuine ``entrypoint`` with
# every livekit-coupled collaborator replaced by an offline fake (the session,
# room, director, guard, providers, and httpx), capture the callback it
# registers via ``ctx.add_shutdown_callback``, mutate the live state exactly as
# a real call would, and then invoke the callback. Whatever ordering bug is
# reintroduced inside the closure fails HERE, not in production.

_SPOKEN = (
    "I led the incident response when our payments ledger started double-charging "
    "customers, traced it to a race between the retry worker and the settlement "
    "job, and added an idempotency key on every write."
)


class _RecordingHttpx:
    """Stand-in for ``httpx.AsyncClient``: records POSTs, never touches the network.

    ``json.dumps`` runs at the exact boundary where the real client serializes
    ``json=`` — so a non-JSON-encodable field (datetime/enum) sneaking into the
    worker's python-mode ``ctx.model_dump()`` payload fails here exactly as it
    would in production.
    """

    def __init__(self, live_result_ok: bool = True) -> None:
        self.posts: list[tuple[str, Any]] = []
        self.live_result_ok = live_result_ok

    def urls(self) -> list[str]:
        return [url for url, _ in self.posts]

    def client_cls(self) -> type:
        recorder = self
        dumps = json.dumps

        class _Client:
            def __init__(self, *args: Any, **kwargs: Any) -> None: ...

            async def __aenter__(self) -> _Client:
                return self

            async def __aexit__(self, *exc: Any) -> bool:
                return False

            async def post(self, url: str, json: Any = None) -> SimpleNamespace:  # noqa: A002 - mirrors httpx
                dumps(json)  # what the real client does with json=
                recorder.posts.append((url, json))
                if url.endswith("/live-result") and not recorder.live_result_ok:
                    raise RuntimeError("api unreachable")
                return SimpleNamespace(status_code=200)

        return _Client


class _RecordingRepo:
    """Wraps the real repo, recording the direct-store calls the fallback makes."""

    def __init__(self, inner: Any, fail_save_context: bool = False) -> None:
        self.inner = inner
        self.calls: list[tuple[str, str]] = []
        self.fail_save_context = fail_save_context

    async def save_transcript(self, session_id: str, turns: list[dict]) -> None:
        self.calls.append(("save_transcript", session_id))
        await self.inner.save_transcript(session_id, turns)

    async def save_context(self, session_id: str, ctx: Any) -> None:
        self.calls.append(("save_context", session_id))
        if self.fail_save_context:
            raise RuntimeError("store down")
        await self.inner.save_context(session_id, ctx)

    async def update_status(self, session_id: str, status: str) -> None:
        self.calls.append((f"update_status:{status}", session_id))
        await self.inner.update_status(session_id, status)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


class _FakeRoom(FakeAgentSession):
    """Bare room surface: ``.on`` decorators plus the identity fields read by
    ``wire_audio_path_logging`` / ``_session_id_from_room`` (metadata=None →
    the session id is the room name)."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.metadata = None
        self.remote_participants: dict[str, Any] = {}


class _FakeJobContext:
    def __init__(self, room: _FakeRoom) -> None:
        self.room = room
        self.proc = SimpleNamespace(userdata={})
        self.shutdown_callbacks: list[Callable[[], Any]] = []

    async def connect(self) -> None:
        return None

    def add_shutdown_callback(self, cb: Callable[[], Any]) -> None:
        self.shutdown_callbacks.append(cb)


class _FakeLifecycle:
    """Stands in for Director / SessionGuard: sync start(), async aclose()."""

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def start(self) -> None: ...

    async def aclose(self) -> None: ...


class _FakeUsageCollector:
    def collect(self, m: Any) -> None: ...

    def get_summary(self) -> dict:
        return {}


def _drive_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
    *,
    live_result_ok: bool = True,
    fail_save_context: bool = False,
) -> SimpleNamespace:
    """Run the real ``worker.entrypoint`` offline and capture its shutdown closure.

    Only livekit/network seams are faked; the persistence ordering, the
    has_answers decision, the payload construction and the scoring trigger all
    run the REAL closure code. Returns the registered shutdown callback, the
    live userdata, and the http/repo recorders.
    """
    interview_ctx = _build_context()
    session_id = interview_ctx.session_id

    rec_http = _RecordingHttpx(live_result_ok=live_result_ok)
    rec_repo = _RecordingRepo(build_deps().repo, fail_save_context=fail_save_context)
    deps = replace(build_deps(), repo=rec_repo)

    async def _fake_load(sid: str, settings: Any) -> Any:
        assert sid == session_id
        return interview_ctx

    sessions: list[FakeAgentSession] = []

    class _FakeSession(FakeAgentSession):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__()
            self.kwargs = kwargs
            sessions.append(self)

        async def start(self, *args: Any, **kwargs: Any) -> None:
            return None

    monkeypatch.setattr(worker, "_load_context_via_api", _fake_load)
    monkeypatch.setattr(worker, "build_deps", lambda settings=None: deps)
    monkeypatch.setattr(worker, "AgentSession", _FakeSession)
    monkeypatch.setattr(
        worker, "Interviewer", lambda userdata: SimpleNamespace(userdata=userdata)
    )
    monkeypatch.setattr(worker, "Director", _FakeLifecycle)
    monkeypatch.setattr(worker, "SessionGuard", _FakeLifecycle)
    monkeypatch.setattr(
        worker, "metrics", SimpleNamespace(UsageCollector=_FakeUsageCollector)
    )
    for factory in ("build_stt", "build_llm", "build_tts", "build_vad"):
        monkeypatch.setattr(worker, factory, lambda *a, **k: None)
    monkeypatch.setattr(worker, "build_turn_handling", lambda *a, **k: {})
    monkeypatch.setattr(worker, "build_room_options", lambda *a, **k: None)
    monkeypatch.setattr(httpx, "AsyncClient", rec_http.client_cls())

    job_ctx = _FakeJobContext(_FakeRoom(session_id))
    asyncio.run(worker.entrypoint(job_ctx))

    assert len(job_ctx.shutdown_callbacks) == 1, (
        "entrypoint must register exactly one shutdown callback"
    )
    assert len(sessions) == 1
    userdata = sessions[0].kwargs["userdata"]
    assert userdata.session_id == session_id

    return SimpleNamespace(
        shutdown=job_ctx.shutdown_callbacks[0],
        userdata=userdata,
        http=rec_http,
        repo=rec_repo,
        session_id=session_id,
    )


def test_shutdown_recovers_unsaved_answers_before_deciding_has_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE production-bug ordering, in the real closure: real speech with NO
    save_answer call must reach the live-result payload as a recovered answer
    with status hint None — and scoring must fire AFTER the persist. Deleting
    or reordering ``state.reconstruct_answers`` (or computing ``has_answers``
    before it) flips the payload to ``no_answers`` and kills the score POST."""
    drive = _drive_entrypoint(monkeypatch)
    ud = drive.userdata
    q1 = state.current_question(ud)
    assert q1 is not None

    state.add_turn(ud, "assistant", "Tell me about a hard production bug you fixed.")
    state.add_turn(ud, "user", _SPOKEN)
    assert ud.ctx.answers == [], "precondition: the model never called save_answer"

    asyncio.run(drive.shutdown())

    assert len(drive.http.posts) == 2, "exactly: live-result persist, then score"
    url, payload = drive.http.posts[0]
    assert url.endswith(f"/api/session/{drive.session_id}/live-result")
    assert payload["status"] is None, (
        "recovered speech counts as answers — no terminal no_answers hint"
    )
    answers = payload["context"]["answers"]
    assert [a["question_id"] for a in answers] == [q1.id]
    assert answers[0]["transcript"] == _SPOKEN
    # Persist first, score second — and only against this session.
    score_url, score_body = drive.http.posts[1]
    assert score_url.endswith("/api/score")
    assert score_body == {"session_id": drive.session_id}
    # The API persist succeeded, so the direct-repo fallback must stay untouched.
    assert drive.repo.calls == []


def test_shutdown_payload_is_json_encodable_and_parses_as_live_result_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The worker builds its payload with python-mode ``ctx.model_dump()`` and
    hands it to httpx ``json=``: it must stay ``json.dumps``-encodable AND
    validate as the API's ``LiveResultRequest`` (the worker→API wire contract).
    A datetime/enum field added to InterviewContext breaks this first."""
    drive = _drive_entrypoint(monkeypatch)
    ud = drive.userdata
    state.add_turn(ud, "user", _SPOKEN)
    state.save_answer(
        ud,
        transcript=_SPOKEN,
        started_at="2026-06-11T09:00:00Z",
        ended_at="2026-06-11T09:02:00Z",
    )

    asyncio.run(drive.shutdown())

    url, payload = drive.http.posts[0]
    assert url.endswith("/live-result")
    json.dumps(payload)  # the fake client also dumps at the boundary
    req = LiveResultRequest.model_validate(payload)
    assert req.transcript == ud.transcript
    assert [a.transcript for a in req.context.answers] == [_SPOKEN]
    assert req.status is None


def test_shutdown_silent_call_sends_no_answers_hint_and_skips_scoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A call with no user speech must POST the terminal ``no_answers`` hint and
    must NOT trigger scoring (which would read an answer-less context)."""
    drive = _drive_entrypoint(monkeypatch)
    state.add_turn(drive.userdata, "assistant", "Hello? Are you still there?")

    asyncio.run(drive.shutdown())

    url, payload = drive.http.posts[0]
    assert url.endswith("/live-result")
    assert payload["status"] == "no_answers"
    assert payload["context"]["answers"] == []
    assert not any(u.endswith("/api/score") for u in drive.http.urls())


def test_shutdown_blank_saved_answers_still_count_as_no_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``has_answers`` uses the non-empty-transcript rule, not list truthiness:
    a lone ``save_answer("")`` with no recoverable speech keeps the
    ``no_answers`` hint and skips scoring (no all-zeros card downstream)."""
    drive = _drive_entrypoint(monkeypatch)
    state.save_answer(drive.userdata, transcript="", started_at="", ended_at="")

    asyncio.run(drive.shutdown())

    assert drive.http.posts[0][1]["status"] == "no_answers"
    assert not any(u.endswith("/api/score") for u in drive.http.urls())


def test_shutdown_falls_back_to_repo_when_api_post_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API-first, direct-repo second: when the live-result POST raises, the
    fallback persists transcript THEN context (answers included) to the shared
    store, leaves the status untouched for an answered session, and scoring
    still fires off the successful repo persist."""
    drive = _drive_entrypoint(monkeypatch, live_result_ok=False)
    ud = drive.userdata
    q1 = state.current_question(ud)
    assert q1 is not None
    state.add_turn(ud, "user", _SPOKEN)

    asyncio.run(drive.shutdown())

    # The API path was attempted FIRST...
    assert drive.http.urls()[0].endswith("/live-result")
    # ...then the repo fallback persisted everything, in write order.
    assert drive.repo.calls == [
        ("save_transcript", drive.session_id),
        ("save_context", drive.session_id),
    ]
    repo = build_deps().repo  # the memory singleton behind the recorder
    persisted = asyncio.run(repo.load_context(drive.session_id))
    assert persisted is not None
    assert [a.question_id for a in persisted.answers] == [q1.id]
    assert persisted.answers[0].transcript == _SPOKEN
    # has_answers is True -> the fallback must NOT flip the status to no_answers.
    assert repo.get_status(drive.session_id) == "ready"
    # Repo persist succeeded for an answered session -> scoring still triggered.
    assert drive.http.urls()[-1].endswith("/api/score")


def test_shutdown_repo_save_context_failure_marks_error_and_skips_scoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The only ready→error transition on the live path: when BOTH the API POST
    and the fallback ``save_context`` fail, answers were NOT persisted — the
    session is marked ``error`` (honest report, not zeros) and scoring is
    skipped (it would score the answer-less prep-time context)."""
    drive = _drive_entrypoint(monkeypatch, live_result_ok=False, fail_save_context=True)
    state.add_turn(drive.userdata, "user", _SPOKEN)

    asyncio.run(drive.shutdown())

    assert ("update_status:error", drive.session_id) in drive.repo.calls
    assert build_deps().repo.get_status(drive.session_id) == "error"
    assert not any(u.endswith("/api/score") for u in drive.http.urls())
