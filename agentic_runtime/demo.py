"""
Runs one full cycle through the framed Loop with dummy data and a MockAgentD,
so the wiring can be checked end to end without any real model, tool, or
agentd behind it. This is the "does the frame stand up" check, not a
demonstration of real agent behavior.
"""

from __future__ import annotations

import asyncio

from agentic_runtime import Loop, MockAgentD
from agentic_runtime.models import AgentJob, Agenda, Intent, Mission, Persona


def build_demo_loop() -> Loop:
    agentd = MockAgentD()

    job = AgentJob(
        role="general-purpose-worker",
        skills=["writing", "research"],
        tools=["shell", "file-write"],
    )

    persona = Persona(
        name="demo-agent",
        preferences={"tone": "direct"},
        preferred_skills=["writing"],
    )

    intent = Intent(
        missions=[Mission(description="Draft the runtime framing README")],
        agendas=[Agenda(description="optimize agent efficiency over time")],
    )

    return Loop(
        agentd,
        model="demo-model-v0",
        job=job,
        persona=persona,
        intent=intent,
        settings={"max_tool_calls_per_cycle": 10},
        sys_env={"rootfs": "/demo-vm"},
    )


def print_cycle_log(log) -> None:
    print("=" * 60)
    print(f"AGENT      : {log.identity.model} ({log.identity.agent_class.value})")
    print(f"AGENT ID   : {log.identity.agent_id}")
    print("-" * 60)
    if log.think and log.think.objective:
        print(f"OBJECTIVE  : {log.think.objective.description}")
    else:
        print("OBJECTIVE  : none resolved")
    if log.contract:
        print(f"CONTRACT   : {log.contract.agentid_sys} | scope={log.contract.rules.scope}")
    if log.action:
        print(f"ACTION     : tool={log.action.tool} win={log.action.win}")
        print(f"             {log.action.log}")
    if log.analysis:
        print(f"ANALYSIS   : {log.analysis.verdict.value} -- {log.analysis.reasoning}")
    if log.introspection:
        print(f"STORY WRITE: {log.introspection.text}")
    if log.notes:
        for n in log.notes:
            print(f"NOTE       : {n}")
    if log.sleep_record:
        print("-" * 60)
        print(f"SLEEP      : {log.sleep_record.cycle_summary}")
        print(f"CHAPTER    : {log.sleep_record.chapter_id}")
    print("=" * 60)


async def main() -> None:
    loop = build_demo_loop()

    # Run two cycles back to back to show story continuity across Awakenings
    # (second cycle's `was` should carry the first cycle's closed chapter).
    for i in range(2):
        print(f"\n### CYCLE {i + 1} ###")
        log = await loop.run_cycle()
        print_cycle_log(log)

    print(f"\nPrior chapters retained after 2 cycles: {len(loop._prior_chapters)}")


if __name__ == "__main__":
    asyncio.run(main())
