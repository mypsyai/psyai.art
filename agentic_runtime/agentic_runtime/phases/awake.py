"""
Phase 0: AWAKE.

One-shot per cycle. Pairs model+persona into an agent, restores continuity
(the "was" trajectory), establishes "now", pulls "will" (mission/agenda), and
opens a new story chapter. Persistent agents get the full treatment; ephemeral
agents get a stripped-down version (no persona, no story participation).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..models import (
    AgentClass,
    AgentIdentity,
    AgentJob,
    AwakeState,
    CurrentState,
    Intent,
    Persona,
    StoryChapter,
    StoryTrajectory,
)


def awake(
    *,
    model: str,
    job: AgentJob,
    settings: dict,
    sys_env: dict,
    intent: Intent,
    persona: Persona | None = None,
    prior_chapters: list[StoryChapter] | None = None,
    active_memory: list[str] | None = None,
) -> tuple[AwakeState, StoryChapter | None]:
    """
    Build the full AwakeState for one cycle.

    persona=None => this is an ephemeral agent: it still gets sys/job/now,
    but no story participation (no chapter opened, `was` stays empty).

    Returns (state, current_chapter). current_chapter is None for ephemeral
    agents; the Loop holds onto it to write Introspection entries into and
    to close out at Sleep.
    """
    agent_class = AgentClass.PERSISTENT if persona is not None else AgentClass.EPHEMERAL

    identity = AgentIdentity(
        model=model,
        agent_class=agent_class,
        job=job,
        persona=persona,
        agent_id=None,  # not certified yet -- that happens at ContrAct time
    )

    now = CurrentState(timestamp=datetime.now(timezone.utc), summary="cycle start")

    if agent_class is AgentClass.PERSISTENT:
        chapter = StoryChapter(opened_at=now.timestamp)
        was = prior_chapters or []
    else:
        chapter = None
        was = []

    trajectory = StoryTrajectory(
        was=was,
        now=now,
        will=intent,
    )

    state = AwakeState(
        settings=settings,
        identity=identity,
        active_memory=active_memory or [],
        sys_env=sys_env,
        trajectory=trajectory,
    )

    return state, chapter

