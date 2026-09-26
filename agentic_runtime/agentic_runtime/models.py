"""
Core data models for the agentic runtime ("the Loop").

Naming convention: every field group that was specified with dotted shorthand
in design (e.g. `awake.iam`, `think.tru`) gets a docstring noting the original
name, so this file can be cross-referenced against the design notes directly.
Where the original name isn't valid Python (`think.4me`, `think.not`) it's
renamed and the original is noted.

This module defines *shape*, not *behavior*. Nothing here calls a model,
touches disk, or talks to agentd. That all happens in phases/ and loop.py.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------

class AgentClass(str, Enum):
    """Persistent agents get a persona + story. Ephemeral agents don't."""
    PERSISTENT = "persistent"
    EPHEMERAL = "ephemeral"  # auditors, testers, single-task workers


class MissionStatus(str, Enum):
    OPEN = "open"
    COMPLETE = "complete"
    ABANDONED = "abandoned"


class InputProvenance(str, Enum):
    """
    The instruction/information binary. Set once, at the IO Daemon boundary,
    before anything reaches Sense. Never re-derived by the agent itself.
    """
    INSTRUCTION = "instruction"   # verified user channel -> can direct behavior
    INFORMATION = "information"   # everything else -> content only, never a directive


class AuditVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class FailureResponse(str, Enum):
    """
    What a failed audit means for the agent, as specified per-ContrAct rather
    than globally. "back to the drawing board" / "keep doing what you're
    doing" / "shift the whole approach".
    """
    RETRY_SAME_APPROACH = "retry_same_approach"     # keep doing what you're doing
    REVISE_APPROACH = "revise_approach"              # back to the drawing board (re-Think)
    PIVOT_OBJECTIVE = "pivot_objective"              # the whole approach needs to shift


# ---------------------------------------------------------------------------
# Persona + Story  (awake.iam persona half, awake.was/now/will trajectory)
# ---------------------------------------------------------------------------

class Persona(BaseModel):
    """
    awake.iam = agent.mdl + persona.md

    Behavioral preference layer. Modifies style, not capability. Also the
    thing that *hosts* the story -- persistent agents only. Ephemeral agents
    have no Persona at all (see AgentIdentity.persona being Optional).
    """
    name: str
    preferences: dict[str, str] = Field(default_factory=dict)
    preferred_skills: list[str] = Field(default_factory=list)


class StoryChapter(BaseModel):
    """
    One chapter == one cycle (one Awake-to-Sleep span). Chapter is the story's
    unit; cycle is the session's unit; they're the same span looked at from
    two angles.

    `compression_level` is set by agentd at Awake time based on age + story
    space budget (exponential compression by chapter age -- the actual
    compression *algorithm* lives with agentd/the memory layer, not here;
    this field just records the target this chapter was compressed to).
    """
    chapter_id: UUID = Field(default_factory=uuid4)
    opened_at: datetime
    closed_at: Optional[datetime] = None
    entries: list[str] = Field(default_factory=list)   # introspection writes land here
    compression_level: float = 0.0                      # 0 = uncompressed, 1 = fully summarized


class StoryTrajectory(BaseModel):
    """
    awake.was + awake.now + awake.will, grouped -- these three are explicitly
    sub-components of the story, not independent fields.
    """
    was: list[StoryChapter] = Field(default_factory=list)   # continuity / old_memory.log, prior chapters
    now: "CurrentState"                                       # current state + date&time
    will: "Intent"                                            # mission/projects + agenda


# ---------------------------------------------------------------------------
# Mission / Agenda / Objective
# ---------------------------------------------------------------------------

class Mission(BaseModel):
    """
    A mission has a completion state. Objectives unite into a long-horizon
    coordination of intent that ends somewhere specific.
    """
    mission_id: UUID = Field(default_factory=uuid4)
    description: str
    status: MissionStatus = MissionStatus.OPEN
    parent_agenda_id: Optional[UUID] = None   # missions can be spawned from an agenda


class Agenda(BaseModel):
    """
    An agenda is continuous and, by design, never completes. It's a guiding
    principle that shapes which missions get planned. Example: "optimize
    system efficiency."
    """
    agenda_id: UUID = Field(default_factory=uuid4)
    description: str


class Intent(BaseModel):
    """awake.will: the full set of missions + agendas an agent is carrying."""
    missions: list[Mission] = Field(default_factory=list)
    agendas: list[Agenda] = Field(default_factory=list)


class Objective(BaseModel):
    """
    The short-term binary intent that Think resolves mission+agenda down
    into. This is what actually drives one pass through Contract->Action.
    """
    objective_id: UUID = Field(default_factory=uuid4)
    description: str
    source_mission_id: Optional[UUID] = None
    source_agenda_id: Optional[UUID] = None


class CurrentState(BaseModel):
    """awake.now: current state + date & time."""
    timestamp: datetime
    summary: str = ""


# ---------------------------------------------------------------------------
# Agent identity (awake.iam, awake.job, ContrAct outputs)
# ---------------------------------------------------------------------------

class AgentJob(BaseModel):
    """awake.job = role + skills + tools."""
    role: str
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class AgentIdentity(BaseModel):
    """
    An agent that exists, pre- or post-certification. `agent_id` is only
    populated once agentd has certified a ContrAct for this agent (see
    ContrAct.agentid_sys below) -- an agent can exist and be thinking before
    it's ever certified, if what it's doing doesn't require a contract yet.
    """
    model: str
    agent_class: AgentClass
    job: AgentJob
    persona: Optional[Persona] = None   # None for ephemeral agents
    agent_id: Optional[str] = None      # set once agentd certifies


class AwakeState(BaseModel):
    """
    The full aia_awake bundle, built once per cycle by the init phase.

    aia_awake fields, as specified:
      awake.set = settings.config              -> settings
      awake.iam = agent.mdl + persona.md        -> identity (model+job+persona)
      awake.mem = active_memory.log             -> active_memory
      awake.job = role+skills+tools             -> identity.job
      awake.sys = rootfs+env                    -> sys_env
      awake.was = continuity old_memory.log     -> trajectory.was
      awake.now = current state+date&time       -> trajectory.now
      awake.will = mission/projects + agenda    -> trajectory.will
      awake.day = (superseded -- was just the now.timestamp source; folded
                   into trajectory.now, not a separate field)
    """
    settings: dict = Field(default_factory=dict)
    identity: AgentIdentity
    active_memory: list[str] = Field(default_factory=list)
    sys_env: dict = Field(default_factory=dict)
    trajectory: StoryTrajectory


# ---------------------------------------------------------------------------
# Sense (aia_sense)
# ---------------------------------------------------------------------------

class ClearedInput(BaseModel):
    """
    What the IO Daemon hands back after screening raw input. This is the
    *only* form input is allowed to reach Sense in -- provenance is decided
    once, here, and never re-derived downstream.
    """
    raw: str
    provenance: InputProvenance
    source_id: Optional[str] = None            # for source-relation mapping
    threat_flag: bool = False


class SenseSnapshot(BaseModel):
    """
    aia_sense: sense.cam, sense.mic, sense.u2i, sense.sys, sense.iam, ntrupt.attn
    """
    cam: Optional[str] = None                  # camera read, if present
    mic: Optional[str] = None                  # mic read, if present
    u2i: list[ClearedInput] = Field(default_factory=list)  # user/UI input, post-IO-Daemon
    sys: dict = Field(default_factory=dict)     # internal system status
    iam: AgentIdentity | None = None            # self-state snapshot
    interrupt_attention: Optional[str] = None   # ntrupt.attn -- what broke focus, if anything


# ---------------------------------------------------------------------------
# Think (aia_think)
# ---------------------------------------------------------------------------

class ThinkChainStep(BaseModel):
    """
    One link of a thinking chain. Chains are structured like logic gates:
    a question in, an answer out, chained until a conclusion. Each step is
    effectively its own function call -- this model is the generic envelope
    for any of them; specific chain logic doesn't need to be nailed down to
    get the runtime frame working.
    """
    question: str
    answer: str = ""
    resolved: bool = False


class ThinkResult(BaseModel):
    """
    aia_think fields, renamed where the shorthand wasn't a valid identifier:
      think.rag  -> rag        retrieval augmented generation pull, if used
      think.pln  -> pln        plan/graph output
      think.not  -> notes      ("not" is a Python keyword)
      think.4me  -> for_me     ("4me" isn't a valid identifier)
      think.ovu  -> overview
      think.out  -> output     the externally-visible conclusion
      think.tru  -> truth_check   query against agentd's source-proximity map
      think.map  -> map_       ("map" shadows a builtin)
      think.way  -> way        chosen method/approach
    """
    chains: list[ThinkChainStep] = Field(default_factory=list)
    rag: Optional[str] = None
    pln: Optional[str] = None
    notes: Optional[str] = None
    for_me: Optional[str] = None
    overview: Optional[str] = None
    output: Optional[str] = None
    truth_check: Optional[str] = None
    map_: Optional[str] = None
    way: Optional[str] = None
    objective: Optional[Objective] = None       # what Sense+Think converged on


# ---------------------------------------------------------------------------
# ContrAct
# ---------------------------------------------------------------------------

class ContrActRules(BaseModel):
    """Rules and constraints for what a certified agent may do under this contract."""
    tool_allowlist: list[str] = Field(default_factory=list)
    scope: str = ""
    persistent: bool = False           # can outlive a single cycle
    failure_response: FailureResponse = FailureResponse.REVISE_APPROACH


class ContrAct(BaseModel):
    """
    objective = agent.job
    aia_cert.tpm(agent.job + agent.iam + time.now) = agentid.sys

    Not every action needs one -- minor, no-external-effect, in-VM actions
    can skip contracting entirely (see Loop.requires_contract).
    """
    objective: Objective
    agent_job: AgentJob
    agent_iam: AgentIdentity
    issued_at: datetime
    agentid_sys: str                    # the certified agent ID, from agentd
    rules: ContrActRules


# ---------------------------------------------------------------------------
# Action (aia_action)
# ---------------------------------------------------------------------------

class ActionRecord(BaseModel):
    """
    aia_action: action.how, action.tool, action.log, action.why, action.win,
                action.map, action.env
    """
    how: str
    tool: str
    log: str = ""
    why: str = ""
    win: bool = False        # did the action succeed on its own terms
    map_: Optional[str] = None
    env: dict = Field(default_factory=dict)
    artifact: Optional[str] = None   # whatever the action actually produced


# ---------------------------------------------------------------------------
# Analysis / Introspection
# ---------------------------------------------------------------------------

class AnalysisResult(BaseModel):
    """
    Produced by an (often ephemeral) auditor agent, checking ActionRecord
    against the Objective it was meant to satisfy.
    """
    verdict: AuditVerdict
    reasoning: str
    auditor_agent_id: Optional[str] = None


class IntrospectionEntry(BaseModel):
    """
    What the acting agent writes into its own story while Analysis runs
    concurrently. Not evaluation -- self-authored narrative: what happened,
    how it lines up with the plan, and (when Analysis disagrees) what the
    discrepancy might mean.
    """
    text: str
    discrepancy_noted: bool = False


# ---------------------------------------------------------------------------
# Sleep
# ---------------------------------------------------------------------------

class SleepRecord(BaseModel):
    """
    Mirrors Awake. Final analysis of the whole cycle, written to memory,
    chapter closed. What actually *triggers* Sleep (mission completion vs.
    agenda checkpoint vs. an agentd-issued budget signal vs. self-initiated)
    is still an open decision -- Loop.should_sleep() is the seam for it.
    """
    cycle_summary: str
    chapter_id: UUID
    closed_at: datetime
