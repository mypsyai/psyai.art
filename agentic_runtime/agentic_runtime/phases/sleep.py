"""
Phase: SLEEP.

Mirrors Awake. Closes out the chapter, writes a final cycle-level analysis,
prepares for the next Awakening. What actually triggers Sleep is an open
question (see loop.should_sleep) -- this module just does the closing work
once triggered.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import AnalysisResult, IntrospectionEntry, SleepRecord, StoryChapter


def sleep(
    chapter: StoryChapter | None,
    analysis_results: list[AnalysisResult],
    introspection_entries: list[IntrospectionEntry],
) -> SleepRecord | None:
    """
    Ephemeral agents (chapter=None) don't sleep in this sense -- they're just
    dissolved when their contract completes. Sleep only applies to persistent
    agents with a chapter to close.
    """
    if chapter is None:
        return None

    now = datetime.now(timezone.utc)
    chapter.closed_at = now

    passes = sum(1 for a in analysis_results if a.verdict.value == "pass")
    total = len(analysis_results)
    summary = (
        f"Cycle closed. {passes}/{total} actions passed audit. "
        f"{len(introspection_entries)} introspection entries written this cycle."
    )

    return SleepRecord(
        cycle_summary=summary,
        chapter_id=chapter.chapter_id,
        closed_at=now,
    )
