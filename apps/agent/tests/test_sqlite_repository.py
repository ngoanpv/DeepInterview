"""SqliteRepository: same semantics as MemoryRepository, but persistent."""

from __future__ import annotations

import asyncio

import pytest

from deepinterview_agent.core.persistence.sqlite_repository import SqliteRepository
from deepinterview_agent.shared_models import PrepRequest


def _req() -> PrepRequest:
    return PrepRequest.model_validate(
        {
            "cv_url": "https://example.com/cv.pdf",
            "jd_text": "Senior backend engineer, Python, distributed systems.",
            "company": "Acme",
            "language_mode": {"primary": "en", "mixed": False},
        }
    )


def test_persists_across_instances(tmp_path) -> None:
    asyncio.run(_persists(tmp_path))


async def _persists(tmp_path) -> None:
    db = tmp_path / "s.db"
    repo = SqliteRepository(db)
    sid = await repo.create_session(_req())
    await repo.mark_progress(sid, "cv_analysis")
    await repo.mark_progress(sid, "cv_analysis")
    await repo.add_warnings(sid, ["thin cv"])
    await repo.update_status(sid, "ready")
    await repo.save_coach_transcript(sid, [{"role": "coach", "text": "hi"}])

    reopened = SqliteRepository(db)
    view = await reopened.get_session_view(sid)
    assert view is not None
    assert view.status == "ready"
    assert view.progress == ["cv_analysis"]
    assert view.prep_warnings == ["thin cv"]

    listed = await reopened.list_sessions()
    assert [s["session_id"] for s in listed] == [sid]
    assert listed[0]["company"] == "Acme"
    assert listed[0]["has_coach_transcript"] is True
    assert "jd_text" not in listed[0]


def test_unknown_session(tmp_path) -> None:
    asyncio.run(_unknown(tmp_path))


async def _unknown(tmp_path) -> None:
    repo = SqliteRepository(tmp_path / "s.db")
    assert await repo.get_session_view("nope") is None
    assert await repo.load_context("nope") is None
    with pytest.raises(KeyError):
        await repo.update_status("nope", "ready")
