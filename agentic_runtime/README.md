# Agentic Runtime -- Framing Pass

This is a structural skeleton, not a working agent. Nothing here calls a real
model, a real tool, or a real agentd. The goal was to get the shape and the
data flow right -- typed, runnable end to end with dummy data -- so the next
sessions are filling in rooms in a house with a floor plan already standing,
rather than each piece being built in isolation and reconciled later.

## Run it

```
python3 demo.py
```

Runs two cycles back to back through a `MockAgentD`, printing each phase's
output, and shows story continuity (chapters accumulating) across Awakenings.

## Layout

```
agentic_runtime/
  models.py                          typed shape of every aia_* field group,
                                      Persona, Story, Mission/Agenda/Objective,
                                      ContrAct, ActionRecord, etc.
  agentd_client.py                   the interface the Loop needs from agentd
                                      (Protocol) + MockAgentD (standalone stub)
  loop.py                            orchestrator: wires phases into one cycle
  phases/
    awake.py                         Phase 0: pairs model+persona, opens
                                      story chapter (persistent agents only)
    sense_think.py                   Sense<->Think, alternating until an
                                      Objective resolves
    contract.py                      ContrAct: objective -> certified agent ID,
                                      + the skip-contract decision point
    action.py                        tool use under contract rules
    analysis_introspection.py        Analysis (ephemeral auditor) run
                                      concurrently with Introspection (story
                                      write), via asyncio.gather
    sleep.py                         closes the chapter, final cycle summary
demo.py                              runs the above end to end with dummy data
```

## What's real vs. stubbed

**Real (typed, wired, worth keeping as-is going forward):**
- Every `aia_*` field group as a Pydantic model, cross-referenced by
  docstring back to the original dotted names.
- The Awake -> Sense/Think -> ContrAct -> Action -> (Analysis || Introspection)
  -> Sleep phase transition sequence, actually executing in that order.
- Persistent vs. ephemeral agent distinction (persona/story vs. none),
  running through Awake and Analysis's auditor-spawning.
- Mission (completable) vs. Agenda (continuous) as distinct types, with
  Objective as what Think resolves them into.
- The instruction/information provenance binary, decided once at the IO
  Daemon boundary (`ClearedInput.provenance`) and never re-derived downstream.
- Analysis and Introspection genuinely running concurrently
  (`asyncio.gather`), not just sequenced to look concurrent.
- The Loop <-> agentd seam as an actual interface (`AgentDClient` Protocol),
  not shared internals -- swapping `MockAgentD` for a real agentd later is a
  drop-in.

**Stubbed on purpose (the "drywall," per your framing metaphor):**
- No real model calls anywhere -- `default_think_hook` resolves an Objective
  by picking the first mission/agenda off the list, not by reasoning.
- No real tool dispatch -- `default_tool_hook` just records that it would
  have run something.
- No real IO Daemon logic -- `MockAgentD.clear_input` uses a toy rule
  (`claimed_source == "user"`) instead of actual verified-channel checking.
- No real State Engine, no real source-relation map -- both return
  placeholder values from `MockAgentD`.
- No real certification/crypto -- `MockAgentD.certify` just increments a
  counter.
- Story compression (the exponential, age-based algorithm) isn't
  implemented -- `StoryChapter.compression_level` exists as a field for it to
  write into, but nothing sets it yet.

## Open decisions (deferred, not forgotten)

These came up while framing and don't have to be settled to keep building,
but they're the seams that will need real answers:

1. **Escalation policy** (IO Daemon -> agentd -> Loop). Does a flagged input
   get silently downgraded to information, does it halt the phase transition,
   or does it surface into Think as something the agent has to reason about?
   You've called this its own policy-group/session -- `ClearedInput.threat_flag`
   exists as the hook point for whatever that becomes.
2. **Sleep trigger.** Mission completion, agenda checkpoint, an agentd-issued
   budget/context signal, or self-initiated? `Loop.should_continue_cycle` is
   currently a hardcoded "one objective per cycle" -- that's a placeholder,
   not a design decision.
3. **No-contract action path.** The spec is clear that minor in-VM actions
   can skip ContrAct, but what an `ActionRecord` looks like without a
   contract behind it (no `agentid_sys`, no rules to check against) isn't
   fully worked out -- see the TODO note in `loop.py`'s no-contract branch.
4. **Plan/Graph as a data structure.** Mission vs. Agenda semantics are
   settled; whether the graph representation itself lives inside the State
   Engine's model or as its own structure alongside Memory isn't.
5. **agentd's own runtime/language.** Explicitly out of scope for this pass
   -- framed as an interface only. Python's the working assumption for
   everything above; agentd is the one piece where Rust was floated once the
   interface is proven.

## Naming note

A few `aia_*` field names weren't valid Python identifiers or collided with
builtins/keywords (`think.4me`, `think.not`, `think.map`, `action.map`).
Each rename is documented in the model's docstring next to the original --
`models.py` is the place to check if a field name here doesn't match what you
expect from the design notes.
