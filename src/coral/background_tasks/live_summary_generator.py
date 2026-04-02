"""Auto-naming background task — generates short session names via Haiku LLM."""

from __future__ import annotations

import asyncio
import logging
import shutil

log = logging.getLogger(__name__)

_NAMING_PROMPT = """\
You are naming a coding session for a dashboard sidebar. Given these recent agent actions,
generate a 2-5 word name that describes the overall task. Be specific and concise.

Examples:
- "Auth Middleware Refactor"
- "Fix Flaky Tests"
- "Database Migration"
- "API Endpoint Cleanup"

Recent actions:
{actions}

Return ONLY the name. No quotes, no explanation."""


class LiveSummaryGenerator:
    """Periodically checks for live sessions that lack an auto-generated name
    and assigns one using Haiku LLM (or a heuristic fallback)."""

    def __init__(self, store) -> None:
        self._store = store

    async def run_forever(self, interval: float = 30) -> None:
        while True:
            try:
                await self.run_once()
            except Exception:
                log.exception("LiveSummaryGenerator error")
            await asyncio.sleep(interval)

    async def run_once(self) -> int:
        """Find candidate sessions and generate names. Returns count of names generated."""
        session_ids = await self._store.get_sessions_needing_auto_name()

        if not session_ids:
            return 0

        count = 0
        for session_id in session_ids:
            try:
                name = await self._generate_name(session_id)
                if name:
                    await self._store.set_auto_name(session_id, name)
                    log.info("Auto-named session %s: %s", session_id[:8], name)
                    count += 1
                else:
                    # Write empty string sentinel to prevent re-selection on next cycle
                    await self._store.set_auto_name(session_id, "")
                    log.debug("No name generated for session %s, marking as attempted", session_id[:8])
            except Exception:
                log.exception("Failed to auto-name session %s", session_id[:8])

        return count

    async def _generate_name(self, session_id: str) -> str | None:
        """Generate a name for a session from its recent events."""
        summaries = await self._store.get_event_summaries(session_id)

        if not summaries:
            return None

        actions_text = "\n".join(f"- {s}" for s in summaries)

        # Try CLI-based LLM call first
        if shutil.which("claude"):
            return await self._call_haiku(actions_text)

        # Fallback: extract most common directory from event summaries
        return self._heuristic_name(summaries)

    async def _call_haiku(self, actions_text: str) -> str | None:
        """Call claude CLI with Haiku to generate a session name."""
        from coral.tools.utils import run_cmd

        prompt = _NAMING_PROMPT.replace("{actions}", actions_text)
        rc, stdout, stderr = await run_cmd(
            "claude", "--print", "--model", "haiku",
            "--no-session-persistence", prompt,
            timeout=30.0,
        )
        if rc != 0 or not stdout:
            log.warning("Haiku naming call failed (rc=%s): %s", rc, stderr)
            return None

        name = stdout.strip().strip('"').strip("'").strip()
        # Sanity check: should be short
        if len(name) > 60 or "\n" in name:
            log.warning("Haiku returned bad name, truncating: %s", name[:80])
            name = name.split("\n")[0][:50]

        return name if name else None

    @staticmethod
    def _heuristic_name(summaries: list[str]) -> str | None:
        """Extract a name from event summaries without LLM.

        Looks for the most common directory path component across events.
        """
        from collections import Counter

        dirs: list[str] = []
        for s in summaries:
            # Look for file paths in summaries (e.g. "Edited src/foo/bar.py")
            for word in s.split():
                if "/" in word and not word.startswith("http"):
                    parts = word.strip("'\"()").split("/")
                    # Take the most specific directory (second-to-last component)
                    if len(parts) >= 2:
                        dirs.append(parts[-2])

        if not dirs:
            return None

        most_common = Counter(dirs).most_common(1)[0][0]
        return most_common.replace("_", " ").replace("-", " ").title()
