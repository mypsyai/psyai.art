"""
Phase: Sense <-> Think.

Specified as concurrent/alternating, not sequential: the agent shifts back
and forth between gathering input and reasoning about it until an actionable
Objective falls out. This module models that as a bounded loop rather than
two separate one-shot calls, since "alternates until resolved" is the actual
behavior described.

Real camera/mic/RAG/LLM calls are NOT wired up here -- this is the frame.
Each hook point is a plain function so swapping in a real implementation
later doesn't require touching the control flow.
"""

from __future__ import annotations

from typing import Callable

from ..agentd_client import AgentDClient
from ..models import (
    AgentIdentity,
    Intent,
    Objective,
    SenseSnapshot,
    ThinkChainStep,
    ThinkResult,
)

# Hook signatures. Swap these for real implementations; the loop below only
# depends on the shapes.
SenseHook = Callable[[], SenseSnapshot]
ThinkHook = Callable[[SenseSnapshot, ThinkResult, Intent], ThinkResult]


def default_sense_hook(agentd: AgentDClient, identity: AgentIdentity) -> SenseSnapshot:
    """Stub: no real cam/mic. Reads nothing, just stamps identity + sys state."""
    return SenseSnapshot(
        cam=None,
        mic=None,
        u2i=[],
        sys=agentd.get_state_snapshot("self"),
        iam=identity,
        interrupt_attention=None,
    )


def default_think_hook(
    sense: SenseSnapshot, prior: ThinkResult, intent: Intent
) -> ThinkResult:
    """
    Stub reasoning: takes whatever Sense produced and whatever Think has
    accumulated so far, and either asks another question or -- if it judges
    itself done -- resolves an Objective from the first open mission/agenda.
    Standing in for a real thinking-chain / LLM call.
    """
    step_n = len(prior.chains) + 1
    chains = list(prior.chains)

    if step_n == 1:
        chains.append(
            ThinkChainStep(
                question="Is there a clear open objective already?",
                answer="no" if not intent.missions and not intent.agendas else "yes",
                resolved=True,
            )
        )
        return ThinkResult(chains=chains, notes="first pass")

    # Second pass: resolve.
    objective = None
    if intent.missions:
        m = intent.missions[0]
        objective = Objective(description=m.description, source_mission_id=m.mission_id)
    elif intent.agendas:
        a = intent.agendas[0]
        objective = Objective(
            description=f"advance agenda: {a.description}", source_agenda_id=a.agenda_id
        )

    return ThinkResult(
        chains=chains,
        notes=prior.notes,
        output="objective resolved" if objective else "nothing to do",
        objective=objective,
    )


def sense_think(
    agentd: AgentDClient,
    identity: AgentIdentity,
    intent: Intent,
    *,
    sense_hook: SenseHook | None = None,
    think_hook: ThinkHook | None = None,
    max_alternations: int = 4,
) -> tuple[SenseSnapshot, ThinkResult]:
    """
    Alternate Sense and Think until Think produces a resolved Objective, or
    max_alternations is hit (safety valve -- a real implementation would
    likely replace this with a "give up and ask" branch rather than a hard
    cap, but that's an escalation-policy decision, not a framing one).
    """
    sense_hook = sense_hook or (lambda: default_sense_hook(agentd, identity))
    think_hook = think_hook or default_think_hook

    think_result = ThinkResult()
    sense_snapshot = SenseSnapshot(iam=identity)

    for _ in range(max_alternations):
        sense_snapshot = sense_hook()
        think_result = think_hook(sense_snapshot, think_result, intent)
        if think_result.objective is not None:
            break

    return sense_snapshot, think_result
