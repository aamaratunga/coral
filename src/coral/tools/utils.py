"""Generic utilities and configuration for Coral."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Tuple

# Configuration Constants
import tempfile
LOG_DIR = tempfile.gettempdir().rstrip("/")
LOG_PATTERN = f"{LOG_DIR}/*_coral_*.log"

# Ensure common macOS binary paths are in PATH so tmux can be found
# when running inside a .app bundle (which has a restricted PATH).
_EXTRA_PATHS = ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"]
for _p in _EXTRA_PATHS:
    if _p not in os.environ.get("PATH", "") and os.path.isdir(_p):
        os.environ["PATH"] = _p + ":" + os.environ.get("PATH", "")

# Prevent git from acquiring optional index locks during read-only operations
# (e.g. git status refreshing stat cache). The Coral server polls git state every
# 30s across all agent worktrees; without this, those reads contend with agents
# running git add/commit in the same directories.
os.environ["GIT_OPTIONAL_LOCKS"] = "0"


def get_package_dir() -> Path:
    """Return the root coral package directory.

    Inside a py2app .app bundle, resources are at $RESOURCEPATH/coral.
    Otherwise, returns the ``src/coral`` directory relative to this file.
    """
    resource_path = os.environ.get("RESOURCEPATH")
    if resource_path:
        return Path(resource_path) / "coral"
    return Path(__file__).resolve().parent.parent  # tools/ -> coral/

HISTORY_PATH = Path(os.environ.get("CLAUDE_PROJECTS_DIR", Path.home() / ".claude" / "projects"))
GEMINI_HISTORY_BASE = Path(os.environ.get("GEMINI_TMP_DIR", Path.home() / ".gemini" / "tmp"))


async def get_diff_base(workdir: str) -> str:
    """Return the base ref to diff against for a working directory.

    On a feature branch: merge-base with main/master (shows all branch work).
    On the default branch (or merge-base fails): HEAD (shows uncommitted changes).
    """
    rc, branch, _ = await run_cmd(
        "git", "-C", workdir, "rev-parse", "--abbrev-ref", "HEAD", timeout=5.0,
    )
    current_branch = branch.strip() if rc == 0 else ""

    if current_branch not in ("main", "master", "HEAD", ""):
        for base_branch in ("main", "master"):
            rc, stdout, _ = await run_cmd(
                "git", "-C", workdir, "merge-base", base_branch, "HEAD", timeout=5.0,
            )
            if rc == 0 and stdout:
                return stdout.strip()

    return "HEAD"


async def run_cmd(*args: str, timeout: float | None = None) -> Tuple[int, str, str]:
    """Execute a subprocess command asynchronously.

    Args:
        *args: Command and arguments.
        timeout: Optional timeout in seconds.

    Returns:
        Tuple of (returncode, stdout, stderr).
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if timeout is not None:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        else:
            stdout, stderr = await proc.communicate()

        return proc.returncode or 0, stdout.decode().strip(), stderr.decode().strip()
    except asyncio.TimeoutError:
        # If timeout, try to terminate the process
        if proc:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=1.0)
            except Exception:
                pass
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


_GIT_LOCK_ERRORS = ("index.lock", "Unable to create", "lock file")


async def run_cmd_with_retry(
    *args: str,
    timeout: float | None = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Tuple[int, str, str]:
    """Like run_cmd but retries on git index lock errors with exponential backoff."""
    import logging
    _log = logging.getLogger(__name__)

    for attempt in range(max_retries + 1):
        rc, stdout, stderr = await run_cmd(*args, timeout=timeout)
        if rc == 0:
            return rc, stdout, stderr
        if not any(e in stderr for e in _GIT_LOCK_ERRORS):
            return rc, stdout, stderr
        if attempt < max_retries:
            delay = base_delay * (2 ** attempt)
            _log.warning(
                "Git lock contention (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1, max_retries + 1, delay, stderr,
            )
            await asyncio.sleep(delay)
    return rc, stdout, stderr
