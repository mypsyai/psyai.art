"""
Phase: Action.

Tool use, shaped by the ContrAct's rules (tool allowlist, scope) and by
whatever skills/artifact-design constraints apply. Real tool dispatch isn't
wired here -- `tool_hook` is the seam for that.
"""

from __future__ import annotations

from typing import Callable

from ..agentd_client import AgentDClient
from ..models import ActionRecord, ContrAct

ToolHook = Callable[[ContrAct], ActionRecord]


def default_tool_hook(contract: ContrAct) -> ActionRecord:
    """Stub: 'performs' the objective by just recording that it would have."""
    return ActionRecord(
        how="stub execution -- no real tool wired up yet",
        tool=contract.rules.tool_allowlist[0] if contract.rules.tool_allowlist else "none",
        log=f"pretended to satisfy objective: {contract.objective.description}",
        why=contract.objective.description,
        win=True,
        env={},
        artifact=None,
    )


def action(
    agentd: AgentDClient, contract: ContrAct, *, tool_hook: ToolHook | None = None
) -> ActionRecord:
    tool_hook = tool_hook or default_tool_hook

    record = tool_hook(contract)

    # Policy is enforced by agentd, not self-reported by the action -- check
    # after the fact isn't right for a real system (you'd want a pre-check
    # before the tool actually runs), but the hook boundary is where that
    # pre-check belongs once real tools exist.
    allowed = agentd.check_policy(record.how, contract.agentid_sys)
    if not allowed:
        record.win = False
        record.log += " | BLOCKED by policy"

    return record
