"""
Loop: the orchestrator that wires the phases into one cycle.

One Loop instance == one agent's phased runtime. agentd is continuous and
shared across many Loop instances; this class only ever talks to it through
AgentDClient, never assumes anything about how many other Loops exist.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .agentd_client import AgentDClient
from .models import (
    ActionRecord,
    AgentIdentity,
    AgentJob,
    AnalysisResult,
    ContrAct,
    Intent,
    IntrospectionEntry,
    Persona,
    SenseSnapshot,
    SleepRecord,
    StoryChapter,
    ThinkResult,
)
from .phases.action import action as run_action
from .phases.analysis_introspection import analysis_and_introspection
from .phases.awake import awake as run_awake
from .phases.contract import contract as run_contract
from .phases.contract import requires_contract
from .phases.sense_think import sense_think
from .phases.sleep import sleep as run_sleep


@dataclass
class CycleLog:
    """Everything one call to Loop.run_cycle produced, for inspection/printing."""
    identity: AgentIdentity
    sense: SenseSnapshot | None = None
    think: ThinkResult | None = None
    contract: ContrAct | None = None
    action: ActionRecord | None = None
    analysis: AnalysisResult | None = None
    introspection: IntrospectionEntry | None = None
    sleep_record: SleepRecord | None = None
    objectives_processed: int = 0
    notes: list[str] = field(default_factory=list)


class Loop:
    def __init__(
        self,
        agentd: AgentDClient,
        *,
        model: str,
        job: AgentJob,
        persona: Persona | None,
        intent: Intent,
        settings: dict | None = None,
        sys_env: dict | None = None,
    ) -> None:
        self.agentd = agentd
        self.model = model
        self.job = job
        self.persona = persona
        self.intent = intent
        self.settings = settings or {}
        self.sys_env = sys_env or {}
        self._prior_chapters: list[StoryChapter] = []

    def should_continue_cycle(self, objectives_processed: int) -> bool:
        """
        Open decision, per the design conversation: does the Loop keep
        pulling objectives out of Sense/Think until the mission/agenda set is
        exhausted, or sleep after one? Framed here as a single override
        point rather than baked into run_cycle's control flow. Default: one
        objective per cycle.
        """
        return objectives_processed < 1

    async def run_cycle(self) -> CycleLog:
        # --- AWAKE ---
        state, chapter = run_awake(
            model=self.model,
            job=self.job,
            settings=self.settings,
            sys_env=self.sys_env,
            intent=self.intent,
            persona=self.persona,
            prior_chapters=self._prior_chapters,
        )
        log = CycleLog(identity=state.identity)

        analyses: list[AnalysisResult] = []
        introspections: list[IntrospectionEntry] = []
        objectives_processed = 0

        while self.should_continue_cycle(objectives_processed):
            # --- SENSE <-> THINK ---
            sense_snapshot, think_result = sense_think(
                self.agentd, state.identity, self.intent
            )
            log.sense, log.think = sense_snapshot, think_result

            if think_result.objective is None:
                log.notes.append("no objective resolved -- nothing to act on this pass")
                break

            # --- CONTRACT (conditional) ---
            act_contract: ContrAct | None = None
            if requires_contract(think_result.objective, state.identity.job):
                act_contract = run_contract(self.agentd, think_result.objective, state.identity)
                state.identity.agent_id = act_contract.agentid_sys
                log.contract = act_contract
            else:
                log.notes.append("objective did not require a contract -- skipped")

            # --- ACTION ---
            if act_contract is not None:
                action_record = run_action(self.agentd, act_contract)
            else:
                # Un-contracted minor action -- still needs *a* record; build
                # a throwaway contract-shaped context isn't right here, so
                # this is the seam a real implementation fills in for the
                # no-contract path specifically.
                action_record = ActionRecord(
                    how="uncontracted in-VM action",
                    tool="none",
                    log="stub: no-contract path not fully specified yet",
                    why=think_result.objective.description,
                    win=True,
                )
            log.action = action_record

            # --- ANALYSIS || INTROSPECTION ---
            analysis_result, introspection_entry = await analysis_and_introspection(
                self.agentd,
                action_record,
                think_result.objective,
                think_result,
                chapter,
            )
            log.analysis, log.introspection = analysis_result, introspection_entry
            analyses.append(analysis_result)
            introspections.append(introspection_entry)

            objectives_processed += 1

        log.objectives_processed = objectives_processed

        # --- SLEEP ---
        sleep_record = run_sleep(chapter, analyses, introspections)
        log.sleep_record = sleep_record
        if chapter is not None:
            self._prior_chapters.append(chapter)

        return log
