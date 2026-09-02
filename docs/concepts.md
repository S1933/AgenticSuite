# Concepts

This file is the single definition of the project vocabulary. The README summarises it; the ADRs decide how each concept behaves.

## Workflow

The main executable unit. A workflow defines states, the role responsible for each, transition conditions, and expected outputs.

Candidate workflows: `bugfix`, `feature`, `review`, `research`, `release`. Only `bugfix` is in scope for v0.

## Workflow definition

The declarative description of a workflow, initially YAML. It describes intent and contracts, not implementation.

```yaml
id: bugfix
version: 1

states:
  - id: discovery
    role: investigator
    exit_when:
      - problem_is_understood
      - reproduction_context_is_sufficient
```

This snippet is illustrative and incomplete. The schema is deliberately undecided until real usage constrains it (see ADR 0003, not yet written).

## Session

One execution of a workflow, with a stable identity and enough recorded information to be paused and resumed.

A session holds: session ID, workflow ID and version, current state, user-provided context, agent-generated context, transition history, decisions, artifacts, timestamps, status.

## State

One meaningful phase of a workflow. A state contract may define entry conditions, responsibilities, required context, allowed actions and skills, expected artifacts, and exit conditions.

## Exit criteria

The conditions that allow a session to leave a state. Each is either a **check**, evaluated deterministically by the runtime, or an **assertion**, evaluated by an agent against recorded evidence. See ADR 0002.

## Transition

A recorded move from one state to another. Transitions may go forward, backward, or into a failure state, and are always counted against a budget. See ADR 0002.

## Agent role

The responsibility requested by a state, expressed independently of any provider: `investigator`, `planner`, `implementer`, `reviewer`, `researcher`.

## Capability

What a role needs from an execution backend: reasoning, code editing, repository access, web research, tool execution, long context, low latency, low cost.

Capabilities are the layer that lets a role be remapped to a different backend without changing workflow semantics.

## Provider

An execution backend: an agent harness, coding environment, API, or subscription-backed tool. Provider choice belongs in configuration, below workflows and roles.

## Skill

A reusable engineering primitive that does one thing well, maintained in the [`S1933/Skills`](https://github.com/S1933/Skills) registry. Agentic Suite composes skills; it does not own them.

## Artifact

Anything a state produces that later states or a human may need: a diagnosis, a reproduction, a patch, a test result, a decision record.
