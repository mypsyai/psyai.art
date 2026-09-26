"""
Phase: ContrAct.

Turns a resolved Objective into a certified, ruled agent identity via agentd.
Not every objective needs this -- minor, no-external-effect, in-VM-only
actions can bypass contracting entirely. `requires_contract` is the decision
point; it's deliberately conservative (defaults to requiring a contract)
since under-contracting is the dangerous direction to be wrong in.
"""

from __future__ import annotations

from ..agentd_client import AgentDClient
from ..models import AgentIdentity, AgentJob, ContrAct, Objective


def requires_contract(objective: Objective, job: AgentJob) -> bool:
    """
    Conservative default: only skip contracting for objectives explicitly
    scoped to in-VM, no-tool, no-external-effect work. Everything else --
    including anything that touches a tool in `job.tools` -- gets a contract.
    """
    if job.tools:
        return True
    return "in-vm" not in objective.description.lower()


def contract(
    agentd: AgentDClient, objective: Objective, identity: AgentIdentity
) -> ContrAct:
    """Request certification from agentd. Raises nothing here -- a real
    implementation would need to decide what an agentd refusal means for the
    Loop (retry Think? escalate to the user?); that's a next-session question."""
    return agentd.certify(objective=objective, agent_job=identity.job, agent_iam=identity)
