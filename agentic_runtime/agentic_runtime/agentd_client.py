"""
The interface the Loop needs from agentd.

agentd itself is NOT built here -- per the design conversation it's a
separate, continuously-running process (its own runtime, its own session of
work), not a phase of the Loop. This file only defines the *seam*: what the
Loop calls, and what it gets back. `MockAgentD` is a standalone stand-in so
the Loop can run and be tested before agentd exists for real.

Everything agentd owns per the design so far:
  - certification (ContrAct signing -> agent IDs)
  - policy enforcement (the real gate; Policy Settings are consumed by the
    agent for self-awareness, but agentd is what can't be talked past)
  - identity/credential custody (agents get a proxy, never the raw secret)
  - the State Engine (composite model of agents/models/user/environment --
    homed here because it's cross-agent and privacy-adjacent, same as
    identity/credentials)
  - IO Daemon (subprocess of agentd, replicable, escalates threats up)
  - the source-relation "truth proximity" map (built over time, IO Daemon
    plots onto it, agents get tasked via the agenda to fill it in)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from .models import (
    AgentIdentity,
    AgentJob,
    ClearedInput,
    ContrAct,
    ContrActRules,
    InputProvenance,
    Objective,
)


class AgentDClient(Protocol):
    """What the Loop is allowed to ask agentd for. Nothing else."""

    def clear_input(self, raw: str, claimed_source: str | None = None) -> ClearedInput:
        """
        Run raw input through the IO Daemon. Returns it tagged with
        provenance (instruction vs. information) and, if something looked
        threatening, escalates internally -- the Loop only ever sees the
        cleared/tagged result, never the escalation itself.
        """
        ...

    def certify(
        self, objective: Objective, agent_job: AgentJob, agent_iam: AgentIdentity
    ) -> ContrAct:
        """aia_cert.tpm: turn an objective + job + identity into a signed ContrAct."""
        ...

    def check_policy(self, action_description: str, agent_id: str) -> bool:
        """The real enforcement point for Policy Settings. True = allowed."""
        ...

    def get_state_snapshot(self, query: str) -> dict:
        """Read from the State Engine (composite model of agents/user/env)."""
        ...

    def query_truth_proximity(self, source_a: str, source_b: str) -> float:
        """
        0.0-1.0 confidence that source_a and source_b are consistent, per the
        source-relation map. Map starts uninformative (near-0.5 / unknown
        everywhere) and only gets useful as agents fill it in over time --
        callers should not expect a good answer from a fresh map.
        """
        ...


class MockAgentD:
    """
    Minimal standalone implementation so the Loop can run end-to-end without
    a real agentd. Every call is a stub with the right shape, not real
    security or real state -- do not use this for anything but exercising
    the Loop's wiring.
    """

    def __init__(self) -> None:
        self._cert_counter = 0

    def clear_input(self, raw: str, claimed_source: str | None = None) -> ClearedInput:
        # Toy rule: only input explicitly marked as coming from "user" is
        # ever treated as instruction. Everything else is information, full
        # stop, regardless of what it claims or what it says.
        provenance = (
            InputProvenance.INSTRUCTION
            if claimed_source == "user"
            else InputProvenance.INFORMATION
        )
        return ClearedInput(
            raw=raw,
            provenance=provenance,
            source_id=claimed_source,
            threat_flag=False,
        )

    def certify(
        self, objective: Objective, agent_job: AgentJob, agent_iam: AgentIdentity
    ) -> ContrAct:
        self._cert_counter += 1
        agent_id = f"agent-{self._cert_counter:04d}"
        return ContrAct(
            objective=objective,
            agent_job=agent_job,
            agent_iam=agent_iam,
            issued_at=datetime.now(timezone.utc),
            agentid_sys=agent_id,
            rules=ContrActRules(
                tool_allowlist=agent_job.tools,
                scope=objective.description,
            ),
        )

    def check_policy(self, action_description: str, agent_id: str) -> bool:
        return True  # mock: everything's allowed

    def get_state_snapshot(self, query: str) -> dict:
        return {"query": query, "note": "mock state engine -- no real data yet"}

    def query_truth_proximity(self, source_a: str, source_b: str) -> float:
        return 0.5  # mock: map starts uninformative everywhere
