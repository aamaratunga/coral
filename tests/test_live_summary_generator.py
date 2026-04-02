"""Tests for LiveSummaryGenerator and related store methods."""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock

from coral.store import CoralStore as SessionStore
from coral.background_tasks.live_summary_generator import LiveSummaryGenerator


@pytest_asyncio.fixture
async def store(tmp_path):
    s = SessionStore(db_path=tmp_path / "test.db")
    yield s
    await s.close()


# ── Store methods ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_auto_names_empty_list(store):
    result = await store.get_auto_names([])
    assert result == {}


@pytest.mark.asyncio
async def test_set_and_get_auto_name(store):
    await store.register_live_session("sess-1", "claude", "agent-1", "/tmp")
    await store.set_auto_name("sess-1", "Auth Refactor")
    names = await store.get_auto_names(["sess-1"])
    assert names == {"sess-1": "Auth Refactor"}


@pytest.mark.asyncio
async def test_get_auto_names_excludes_null(store):
    await store.register_live_session("sess-1", "claude", "agent-1", "/tmp")
    await store.register_live_session("sess-2", "claude", "agent-2", "/tmp")
    await store.set_auto_name("sess-1", "Fix Tests")
    names = await store.get_auto_names(["sess-1", "sess-2"])
    assert names == {"sess-1": "Fix Tests"}


@pytest.mark.asyncio
async def test_get_auto_names_excludes_empty_sentinel(store):
    """Empty string sentinel (naming attempted but failed) should not be returned."""
    await store.register_live_session("sess-1", "claude", "agent-1", "/tmp")
    await store.set_auto_name("sess-1", "")
    names = await store.get_auto_names(["sess-1"])
    assert names == {}


@pytest.mark.asyncio
async def test_set_auto_name_updates_existing(store):
    await store.register_live_session("sess-1", "claude", "agent-1", "/tmp")
    await store.set_auto_name("sess-1", "Old Name")
    await store.set_auto_name("sess-1", "New Name")
    names = await store.get_auto_names(["sess-1"])
    assert names == {"sess-1": "New Name"}


@pytest.mark.asyncio
async def test_auto_name_carried_forward_on_replace(store):
    """replace_live_session should preserve auto_name from old session."""
    await store.register_live_session("sess-old", "claude", "agent-1", "/tmp")
    await store.set_auto_name("sess-old", "Auth Refactor")
    await store.replace_live_session("sess-old", "sess-new", "claude", "agent-1", "/tmp")
    names = await store.get_auto_names(["sess-new"])
    assert names == {"sess-new": "Auth Refactor"}


# ── Heuristic name ────────────────────────────────────────────────────────


def test_heuristic_name_extracts_directory():
    summaries = [
        "Edited src/coral/tools/utils.py",
        "Read src/coral/tools/session_manager.py",
        "Edited src/coral/tools/tmux_manager.py",
    ]
    name = LiveSummaryGenerator._heuristic_name(summaries)
    assert name == "Tools"


def test_heuristic_name_returns_none_for_no_paths():
    summaries = ["Running tests", "Checking output", "Done"]
    name = LiveSummaryGenerator._heuristic_name(summaries)
    assert name is None


def test_heuristic_name_returns_none_for_empty():
    assert LiveSummaryGenerator._heuristic_name([]) is None


def test_heuristic_name_skips_urls():
    summaries = ["Fetched https://api.example.com/v1/data"]
    name = LiveSummaryGenerator._heuristic_name(summaries)
    assert name is None


def test_heuristic_name_handles_underscores_and_dashes():
    summaries = [
        "Edited src/background_tasks/foo.py",
        "Read src/background_tasks/bar.py",
    ]
    name = LiveSummaryGenerator._heuristic_name(summaries)
    assert name == "Background Tasks"


# ── run_once ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_once_no_candidates(store):
    gen = LiveSummaryGenerator(store)
    count = await gen.run_once()
    assert count == 0


@pytest.mark.asyncio
async def test_run_once_writes_sentinel_on_failure(store):
    """When _generate_name returns None, an empty sentinel is written."""
    gen = LiveSummaryGenerator(store)

    with patch.object(gen._store, "get_sessions_needing_auto_name", return_value=["sess-1"]):
        with patch.object(gen, "_generate_name", return_value=None):
            with patch.object(gen._store, "set_auto_name") as mock_set:
                count = await gen.run_once()
                assert count == 0
                mock_set.assert_called_once_with("sess-1", "")


@pytest.mark.asyncio
async def test_run_once_stores_name_on_success(store):
    gen = LiveSummaryGenerator(store)

    with patch.object(gen._store, "get_sessions_needing_auto_name", return_value=["sess-1"]):
        with patch.object(gen, "_generate_name", return_value="Auth Refactor"):
            with patch.object(gen._store, "set_auto_name") as mock_set:
                count = await gen.run_once()
                assert count == 1
                mock_set.assert_called_once_with("sess-1", "Auth Refactor")


# ── _call_haiku ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_haiku_returns_name():
    gen = LiveSummaryGenerator(None)
    with patch("coral.tools.utils.run_cmd",
               return_value=(0, "Auth Middleware Refactor\n", "")):
        name = await gen._call_haiku("- Edited auth.py\n- Edited middleware.py")
        assert name == "Auth Middleware Refactor"


@pytest.mark.asyncio
async def test_call_haiku_returns_none_on_failure():
    gen = LiveSummaryGenerator(None)
    with patch("coral.tools.utils.run_cmd",
               return_value=(1, "", "error")):
        name = await gen._call_haiku("- Edited foo.py")
        assert name is None


@pytest.mark.asyncio
async def test_call_haiku_truncates_long_output():
    gen = LiveSummaryGenerator(None)
    long_name = "A" * 70
    with patch("coral.tools.utils.run_cmd",
               return_value=(0, long_name, "")):
        name = await gen._call_haiku("- Edited foo.py")
        assert name is not None
        assert len(name) <= 50


@pytest.mark.asyncio
async def test_call_haiku_handles_multiline():
    gen = LiveSummaryGenerator(None)
    with patch("coral.tools.utils.run_cmd",
               return_value=(0, "Auth Refactor\nExtra explanation here", "")):
        name = await gen._call_haiku("- Edited foo.py")
        assert name == "Auth Refactor"
