"""Tests for temp file cleanup (settings + prompt files)."""

import os
from pathlib import Path
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from coral.store import CoralStore as SessionStore
from coral.tools.session_manager import _cleanup_temp_files


@pytest.fixture(autouse=True)
def _mock_transcript_check():
    """Make resolve_transcript_path always find a transcript so resume tests
    don't get short-circuited by the 'no transcript -> mark sleeping' guard."""
    _fake = Path("/tmp/fake-transcript.jsonl")
    with patch(
        "coral.agents.claude.ClaudeAgent.resolve_transcript_path",
        return_value=_fake,
    ), patch(
        "coral.agents.base.BaseAgent.resolve_transcript_path",
        return_value=_fake,
    ):
        yield


@pytest_asyncio.fixture
async def store(tmp_path):
    """Create a SessionStore backed by a temp DB and close it after the test."""
    s = SessionStore(db_path=tmp_path / "test.db")
    yield s
    await s.close()


# -- _cleanup_temp_files helper ------------------------------------------------


def test_cleanup_removes_settings_file(tmp_path):
    """_cleanup_temp_files should remove the settings file."""
    sid = "test-cleanup-sid"
    settings = Path(f"/tmp/coral_settings_{sid}.json")
    settings.write_text("{}")
    try:
        _cleanup_temp_files(sid)
        assert not settings.exists()
    finally:
        settings.unlink(missing_ok=True)


def test_cleanup_removes_prompt_file(tmp_path):
    """_cleanup_temp_files should remove the prompt file."""
    sid = "test-cleanup-sid"
    prompt = Path(f"/tmp/coral_prompt_{sid}.txt")
    prompt.write_text("hello")
    try:
        _cleanup_temp_files(sid)
        assert not prompt.exists()
    finally:
        prompt.unlink(missing_ok=True)


def test_cleanup_removes_both_files(tmp_path):
    """_cleanup_temp_files should remove both settings and prompt files."""
    sid = "test-cleanup-both"
    settings = Path(f"/tmp/coral_settings_{sid}.json")
    prompt = Path(f"/tmp/coral_prompt_{sid}.txt")
    settings.write_text("{}")
    prompt.write_text("hello")
    try:
        _cleanup_temp_files(sid)
        assert not settings.exists()
        assert not prompt.exists()
    finally:
        settings.unlink(missing_ok=True)
        prompt.unlink(missing_ok=True)


def test_cleanup_noop_when_files_missing():
    """_cleanup_temp_files should not raise when files don't exist."""
    _cleanup_temp_files("nonexistent-session-id-12345")


# -- Temp file naming in build_launch_command ----------------------------------


def test_settings_file_uses_session_id_not_resume_id(tmp_path):
    """build_launch_command should name settings file with session_id, not resume_session_id."""
    from coral.agents.claude import ClaudeAgent

    agent = ClaudeAgent()
    session_id = "new-session-abc"
    resume_id = "old-session-xyz"

    cmd = agent.build_launch_command(
        session_id,
        protocol_path=None,
        resume_session_id=resume_id,
        working_dir=str(tmp_path),
    )

    # Settings file should use session_id
    assert f"coral_settings_{session_id}.json" in cmd
    assert f"coral_settings_{resume_id}.json" not in cmd

    # Clean up created temp files
    _cleanup_temp_files(session_id)


def test_prompt_file_uses_session_id_not_resume_id(tmp_path):
    """build_launch_command should name prompt file with session_id, not resume_session_id."""
    from coral.agents.claude import ClaudeAgent

    agent = ClaudeAgent()
    session_id = "new-session-abc"
    resume_id = "old-session-xyz"

    cmd = agent.build_launch_command(
        session_id,
        protocol_path=None,
        resume_session_id=resume_id,
        working_dir=str(tmp_path),
        prompt="Do something",
    )

    # Prompt file should use session_id
    assert f"coral_prompt_{session_id}.txt" in cmd
    assert f"coral_prompt_{resume_id}.txt" not in cmd

    # Clean up created temp files
    _cleanup_temp_files(session_id)


# -- Resume cleanup integration ------------------------------------------------


@pytest.mark.asyncio
async def test_resume_cleans_up_old_settings_on_success(store, tmp_path):
    """Successful resume should delete old session's temp files."""
    work_dir = str(tmp_path)
    old_sid = "old-sid-cleanup"
    settings_file = Path(f"/tmp/coral_settings_{old_sid}.json")
    prompt_file = Path(f"/tmp/coral_prompt_{old_sid}.txt")
    settings_file.write_text("{}")
    prompt_file.write_text("hello")

    await store.register_live_session(old_sid, "claude", "wt1", work_dir)

    launch_result = {
        "session_name": "claude-new-sid",
        "session_id": "new-sid-cleanup",
        "log_file": "/tmp/claude_coral_new-sid-cleanup.log",
        "working_dir": work_dir,
        "agent_type": "claude",
    }

    try:
        with patch("coral.tools.session_manager.discover_coral_agents", AsyncMock(return_value=[])), \
             patch("coral.tools.session_manager.launch_claude_session", AsyncMock(return_value=launch_result)):
            from coral.tools.session_manager import resume_persistent_sessions
            await resume_persistent_sessions(store)

        assert not settings_file.exists(), "Settings file should be deleted after resume"
        assert not prompt_file.exists(), "Prompt file should be deleted after resume"
    finally:
        settings_file.unlink(missing_ok=True)
        prompt_file.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_resume_cleans_up_old_settings_on_failure(store, tmp_path):
    """Failed resume should also delete old session's temp files."""
    work_dir = str(tmp_path)
    old_sid = "old-sid-fail"
    settings_file = Path(f"/tmp/coral_settings_{old_sid}.json")
    settings_file.write_text("{}")

    await store.register_live_session(old_sid, "claude", "wt1", work_dir)

    try:
        with patch("coral.tools.session_manager.discover_coral_agents", AsyncMock(return_value=[])), \
             patch("coral.tools.session_manager.launch_claude_session", AsyncMock(return_value={"error": "fail"})):
            from coral.tools.session_manager import resume_persistent_sessions
            await resume_persistent_sessions(store)

        assert not settings_file.exists(), "Settings file should be deleted even on failure"
    finally:
        settings_file.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_resume_cleans_up_on_missing_dir(store, tmp_path):
    """Sessions with missing working dir should have temp files cleaned up."""
    missing_dir = str(tmp_path / "gone")
    old_sid = "old-sid-gone"
    settings_file = Path(f"/tmp/coral_settings_{old_sid}.json")
    settings_file.write_text("{}")

    await store.register_live_session(old_sid, "claude", "wt1", missing_dir)

    try:
        with patch("coral.tools.session_manager.discover_coral_agents", AsyncMock(return_value=[])), \
             patch("coral.tools.session_manager.launch_claude_session", AsyncMock()) as mock_launch:
            from coral.tools.session_manager import resume_persistent_sessions
            await resume_persistent_sessions(store)

        mock_launch.assert_not_called()
        assert not settings_file.exists(), "Settings file should be deleted for missing dir"
    finally:
        settings_file.unlink(missing_ok=True)


# -- Startup sweep -------------------------------------------------------------


@pytest.mark.asyncio
async def test_startup_sweep_removes_orphaned_files(store, tmp_path):
    """Orphaned temp files not matching any live tmux session should be swept."""
    work_dir = str(tmp_path)
    orphan_sid = "orphan-sweep-test"
    live_sid = "live-sweep-test"

    orphan_settings = Path(f"/tmp/coral_settings_{orphan_sid}.json")
    live_settings = Path(f"/tmp/coral_settings_{live_sid}.json")
    orphan_settings.write_text("{}")
    live_settings.write_text("{}")

    # Register a session so resume_persistent_sessions has work to do
    await store.register_live_session("some-dead-sid", "claude", "wt1", work_dir)

    # Mock discover to show only `live_sid` as alive
    live_agents = [{"session_id": live_sid, "agent_type": "claude", "agent_name": "wt1",
                    "working_directory": work_dir, "tmux_session": f"claude-{live_sid}",
                    "log_path": f"/tmp/claude_coral_{live_sid}.log"}]

    launch_result = {
        "session_name": f"claude-new",
        "session_id": "new-sid",
        "log_file": "/tmp/claude_coral_new.log",
        "working_dir": work_dir,
        "agent_type": "claude",
    }

    try:
        # First call: initial discovery (no live sessions)
        # Second call: sweep discovery (live_sid is running)
        with patch("coral.tools.session_manager.discover_coral_agents",
                   AsyncMock(side_effect=[[], live_agents])), \
             patch("coral.tools.session_manager.launch_claude_session",
                   AsyncMock(return_value=launch_result)):
            from coral.tools.session_manager import resume_persistent_sessions
            await resume_persistent_sessions(store)

        assert not orphan_settings.exists(), "Orphaned settings should be swept"
        assert live_settings.exists(), "Live session settings should NOT be swept"
    finally:
        orphan_settings.unlink(missing_ok=True)
        live_settings.unlink(missing_ok=True)


# -- Terminal session guard ----------------------------------------------------


@pytest.mark.asyncio
async def test_terminal_sessions_marked_sleeping_not_relaunched(store, tmp_path):
    """Terminal sessions should be marked sleeping, not relaunched."""
    work_dir = str(tmp_path)
    await store.register_live_session("term-sid", "terminal", "wt1", work_dir)

    with patch("coral.tools.session_manager.discover_coral_agents", AsyncMock(return_value=[])), \
         patch("coral.tools.session_manager.launch_claude_session", AsyncMock()) as mock_launch:
        from coral.tools.session_manager import resume_persistent_sessions
        await resume_persistent_sessions(store)

    mock_launch.assert_not_called()

    sessions = await store.get_all_live_sessions()
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "term-sid"
    assert sessions[0]["is_sleeping"] is True


@pytest.mark.asyncio
async def test_terminal_and_claude_mixed_resume(store, tmp_path):
    """Terminal sessions should sleep while Claude sessions resume normally."""
    work_dir = str(tmp_path)
    await store.register_live_session("term-sid", "terminal", "wt1", work_dir)
    await store.register_live_session("claude-sid", "claude", "wt2", work_dir)

    launch_result = {
        "session_name": "claude-new-sid",
        "session_id": "new-claude-sid",
        "log_file": "/tmp/claude_coral_new.log",
        "working_dir": work_dir,
        "agent_type": "claude",
    }

    with patch("coral.tools.session_manager.discover_coral_agents", AsyncMock(return_value=[])), \
         patch("coral.tools.session_manager.launch_claude_session", AsyncMock(return_value=launch_result)) as mock_launch:
        from coral.tools.session_manager import resume_persistent_sessions
        await resume_persistent_sessions(store)

    # Only Claude should have been launched
    assert mock_launch.call_count == 1
    call_kwargs = mock_launch.call_args
    assert call_kwargs[1].get("resume_session_id") == "claude-sid" or call_kwargs[0][1] == "claude"

    # Terminal should be sleeping
    sessions = await store.get_all_live_sessions()
    term = next((s for s in sessions if s["agent_type"] == "terminal"), None)
    assert term is not None
    assert term["is_sleeping"] is True
