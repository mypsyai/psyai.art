"""
Phase: Analysis (external, often an ephemeral auditor agent) concurrent with
Introspection (internal, the acting agent writing into its own story).

These are specified as happening in unison, not sequence: instead of the
acting agent idling while an auditor works, it uses that time to write memory
based on what it can already see (its own thinking chain + the action's
result), independent of whatever verdict the auditor eventually returns.
"""

from __future__ import annotations

import asyncio
from typing import Callable

from ..agentd_client import AgentDClient
from ..models import (
    ActionRecord,
    AgentClass,
    AgentIdentity,
    AgentJob,
    AnalysisResult,
    AuditVerdict,
    Intent,
    IntrospectionEntry,
    Objective,
    StoryChapter,
    ThinkResult,
)
from .awake import awake

AuditorHook = Callable[[ActionRecord, Objective], AnalysisResult]


def default_auditor_hook(action: ActionRecord, objective: Objective) -> AnalysisResult:
    """Stub adversarial audit: passes iff the action self-reported a win.
    A real auditor obviously shouldn't trust the actor's own win flag --
    this stands in for a genuinely independent check."""
    verdict = AuditVerdict.PASS if action.win else AuditVerdict.FAIL
    return AnalysisResult(
        verdict=verdict,
        reasoning=f"stub audit: action.win={action.win}",
    )


def spawn_ephemeral_auditor(agentd: AgentDClient) -> AgentIdentity:
    """
    Ephemeral agents get a stripped-down Awake: sys/job/now, no persona, no
    story. This is the pattern any single-task worker (auditor, tester,
    one-off generator) should follow.
    """
    job = AgentJob(role="auditor", skills=["adversarial-audit"], tools=[])
    state, _chapter = awake(
        model="auditor-model",  # a real system might use a cheaper/different model here
        job=job,
        settings={},
        sys_env=agentd.get_state_snapshot("sys_env_for_ephemeral"),
        intent=Intent(),
        persona=None,
    )
    return state.identity


async def analyze(
    agentd: AgentDClient,
    action: ActionRecord,
    objective: Objective,
    *,
    auditor_hook: AuditorHook | None = None,
) -> AnalysisResult:
    auditor_hook = auditor_hook or default_auditor_hook
    # spawn_ephemeral_auditor() is called for shape/traceability even though
    # the stub hook doesn't use the identity yet -- a real auditor would.
    auditor_identity = spawn_ephemeral_auditor(agentd)
    result = auditor_hook(action, objective)
    result.auditor_agent_id = auditor_identity.agent_id
    return result


async def introspect(
    action: ActionRecord, think: ThinkResult, chapter: StoryChapter | None
) -> IntrospectionEntry:
    """
    Ephemeral agents (chapter=None) don't get an IntrospectionEntry written
    anywhere durable -- they still produce one here for uniformity, but the
    Loop should not attempt to persist it.
    """
    text = (
        f"Attempted: {think.objective.description if think.objective else 'unknown'}. "
        f"Result: {'succeeded' if action.win else 'did not succeed'} via {action.tool}."
    )
    return IntrospectionEntry(text=text, discrepancy_noted=False)


async def analysis_and_introspection(
    agentd: AgentDClient,
    action: ActionRecord,
    objective: Objective,
    think: ThinkResult,
    chapter: StoryChapter | None,
    *,
    auditor_hook: AuditorHook | None = None,
) -> tuple[AnalysisResult, IntrospectionEntry]:
    """Run both concurrently -- this is the literal 'analysis || introspection'."""
    analysis_task = analyze(agentd, action, objective, auditor_hook=auditor_hook)
    introspection_task = introspect(action, think, chapter)
    analysis_result, introspection_entry = await asyncio.gather(
        analysis_task, introspection_task
    )

    # Reconcile: if the auditor disagreed with what the agent told itself,
    # flag it -- this is the "discrepancy -> more thinking chains" hook point.
    if analysis_result.verdict is AuditVerdict.FAIL and action.win:
        introspection_entry.discrepancy_noted = True
        introspection_entry.text += " [discrepancy: self-reported win, audit failed]"

    if chapter is not None:
        chapter.entries.append(introspection_entry.text)

    return analysis_result, introspection_entry
