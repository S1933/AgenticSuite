# ADR 0001: Workflow First Architecture

- **Status:** Accepted
- **Date:** 2026-09-02
- **Decision owners:** Agentic Suite maintainers

## Context

Agentic Suite is intended to provide a complete working method for software development with AI agents.

The surrounding ecosystem changes rapidly:

- model quality changes,
- providers change,
- subscription limits change,
- agent harnesses appear and disappear,
- different tools provide different strengths.

Building the project around one agent, model, vendor, or CLI would make the architecture fragile.

The existing Skills repository already provides reusable engineering primitives across discovery, design, implementation, quality, and delivery.

What is missing is a higher-level layer that decides how those primitives are composed into a complete engineering process.

The first concrete use case is bug fixing.

Bug reports frequently arrive with insufficient context, so a useful bugfix process cannot begin directly with code modification.

The system needs an explicit process for:

1. acquiring context,
2. investigating the problem,
3. implementing a fix,
4. validating the result,
5. recording completion.

## Decision

Agentic Suite will use a **workflow-first architecture**.

The workflow is the primary unit launched by the user.

Agents, skills, providers, and models exist below the workflow and serve its execution.

The initial conceptual hierarchy is:

```text
User
  ↓
Workflow
  ↓
Session
  ↓
State
  ↓
Agent role
  ↓
Skills
  ↓
Provider / Model / Tools
```

## Workflow definitions

Workflows will be declarative.

The initial representation will be YAML.

A workflow definition is expected to describe:

- workflow identity,
- version,
- ordered or reachable states,
- role responsible for each state,
- state responsibilities,
- expected artifacts,
- exit criteria,
- terminal states.

The runtime must interpret the workflow definition instead of embedding workflow-specific behavior directly in code.

## Sessions

Every workflow execution creates a persistent session.

A session must have a stable identity and preserve enough information to pause and resume execution.

The initial session model should include:

- session ID,
- workflow ID,
- workflow version,
- current state,
- collected context,
- transition history,
- generated artifacts,
- status.

Persistence technology is intentionally not decided in this ADR.

## State machine

A workflow progresses through explicit states.

The first `bugfix` workflow is expected to use approximately:

```text
Discovery
  ↓
Investigation
  ↓
Fix
  ↓
Validation
  ↓
Done
```

Each non-terminal state must eventually define an execution contract.

That contract may contain:

- entry conditions,
- responsibilities,
- required context,
- allowed tools or skills,
- expected outputs,
- exit conditions.

## Discovery is a first-class state

The first bugfix state will be `discovery`.

It exists because the initial bug report cannot be assumed to contain sufficient context.

During discovery, the system should interview the user interactively.

Questions should be asked one at a time.

The next question may depend on previous answers.

Discovery ends only when the workflow has enough context to begin investigation.

The exact completeness criteria will be refined through real usage.

## Autonomous state transitions

Normal workflow transitions do not require explicit human approval.

An agent may move the session to the next state when the current state's exit criteria are satisfied.

This is **contract-driven autonomy**, not unrestricted autonomy.

Important product, architectural, security, or irreversible decisions may still require explicit human input when a workflow or state defines that requirement.

## Roles instead of model names

Workflow definitions must refer to agent roles rather than specific models or providers.

Example roles may include:

- `investigator`,
- `planner`,
- `implementer`,
- `reviewer`.

The mapping from role to provider/model belongs in configuration outside the workflow definition.

This allows the execution backend to change without changing the workflow.

## Skills remain separate primitives

Agentic Suite will consume reusable skills rather than absorb skill content into the workflow runtime.

The Skills repository remains responsible for the registry and installation of focused engineering skills.

Agentic Suite is responsible for deciding when those skills participate in a workflow.

This preserves a clean separation:

```text
Skills repo
  → reusable capabilities

Agentic Suite
  → orchestration and lifecycle
```

## Initial scope

The first implementation will intentionally support:

- one workflow: `bugfix`,
- one active execution path,
- declarative YAML,
- explicit states,
- persistent sessions,
- autonomous transitions,
- reusable skills.

The following are out of scope for the first version:

- workflows calling other workflows,
- manager/worker agent hierarchies,
- large-scale parallel agents,
- distributed execution,
- complex scheduling,
- a full graphical UI,
- automatic provider optimization.

## Consequences

### Positive

- Workflows remain stable while models and providers change.
- Workflow behavior becomes inspectable and version-controlled.
- Sessions can be paused and resumed.
- Agents gain autonomy within explicit boundaries.
- Existing skills can be reused without turning the Skills repository into an orchestration framework.
- The architecture can evolve toward multiple workflows without redesigning the core mental model.

### Negative

- A workflow engine and state persistence must exist before the system becomes useful.
- Declarative schemas introduce design and validation work.
- Some behavior may be harder to express declaratively than directly in code.
- Role/provider indirection adds configuration.
- Exit criteria must be designed carefully or autonomous transitions may be unreliable.

## Alternatives considered

### Agent-first architecture

The user launches an agent and the agent decides how to perform the whole task.

Rejected because the process becomes dependent on agent behavior and is harder to observe, resume, test, and reuse.

### Provider-first architecture

The project is organized around Codex, Claude Code, OpenCode, Cursor, or another specific tool.

Rejected because providers and subscriptions change too quickly.

### Skill-first architecture

Complex workflows are implemented directly as large orchestration skills.

Rejected as the primary architecture because skills should remain reusable primitives and should not own persistent workflow lifecycle or application state.

### Hard-coded workflows

Each workflow is implemented directly in application code.

Rejected as the default because workflow behavior should be inspectable, editable, and versioned independently of the runtime.

## Validation

This decision is considered successful when Agentic Suite can run a real `bugfix` session that:

1. starts from an incomplete bug report,
2. performs interactive discovery,
3. persists the collected context,
4. advances to investigation without manual state manipulation,
5. records a diagnosis,
6. executes a fix,
7. validates the result,
8. reaches `done`,
9. can be paused and resumed during the process.

## Follow-up decisions

Future ADRs may define:

- the workflow YAML schema,
- session persistence format,
- role and capability configuration,
- provider adapters,
- skill invocation contracts,
- human approval boundaries,
- interface architecture.
