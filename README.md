# Agentic Suite

Agentic Suite is a declarative workflow system for working with AI agents on software engineering tasks.

The project is built around one core idea:

> **Humans launch workflows. Workflows coordinate agents. Agents use skills. Providers and models remain interchangeable.**

Agentic Suite is initially a personal engineering setup, but it is designed to stay generic enough to be cloned, forked, and adapted by other developers.

## Why this project exists

Modern AI-assisted development is fragmented across tools, agents, models, subscriptions, prompts, skills, and local conventions.

A developer may use:

- one model for planning,
- another for implementation,
- another for difficult debugging,
- dedicated skills for discovery, testing, review, or delivery,
- different agent harnesses depending on the environment.

The individual tools are useful, but the workflow around them often remains manual.

Agentic Suite provides the layer above those tools.

It defines:

- which workflow is being executed,
- which state the workflow is currently in,
- which agent role should act next,
- which skills are available,
- what conditions allow the workflow to advance,
- what context and artifacts must persist between steps.

The goal is not to build another AI coding agent.

The goal is to build a reusable engineering workflow that can use many AI agents.

## Design principles

Agentic Suite follows a small set of principles:

1. **Workflow first**  
   The workflow is the primary unit of execution. Agents exist to serve the workflow.

2. **Declarative by default**  
   Workflows should be described as data, initially in YAML, instead of being hard-coded into the runtime.

3. **Provider independent**  
   Workflows target roles and capabilities, not specific vendors or model names.

4. **Persistent sessions**  
   A workflow execution has an identity, a current state, history, context, and generated artifacts.

5. **Context before execution**  
   Poorly defined requests should be clarified before implementation begins.

6. **Autonomy with explicit contracts**  
   Agents may advance a workflow automatically when the exit criteria of the current state are satisfied.

7. **Skills are reusable primitives**  
   Skills remain small, focused building blocks. Agentic Suite composes them into higher-level workflows.

8. **Start simple**  
   The first version supports one isolated workflow before introducing multi-workflow orchestration, large agent fleets, or complex scheduling.

## Relationship with the Skills repository

The existing `S1933/Skills` repository remains the registry of reusable agent skills.

It already provides primitives across discovery, design, implementation, quality, delivery, setup, and output style.

Agentic Suite does not replace that repository.

Instead:

```text
Agentic Suite
    │
    ├── Workflows
    │     └── coordinate roles, states, skills and artifacts
    │
    ├── Agents / Roles
    │     └── execute workflow responsibilities
    │
    ├── Skills
    │     └── reusable engineering primitives
    │
    └── Providers / Models
          └── interchangeable execution backends
```

The Skills repository answers:

> What reusable engineering capability is available?

Agentic Suite answers:

> When should that capability be used, by whom, and as part of which workflow?

## Core concepts

### Workflow

A workflow is the main executable unit in Agentic Suite.

Examples:

- `bugfix`
- `feature`
- `review`
- `research`
- `release`

A workflow defines a sequence of states, their responsibilities, transition conditions, required roles, and outputs.

### Workflow definition

Workflow definitions are declarative YAML files.

A definition should describe intent and contracts rather than implementation details.

Example:

```yaml
id: bugfix
version: 1

states:
  - id: discovery
    role: investigator
    exit_when:
      - problem_is_understood
      - reproduction_context_is_sufficient

  - id: investigation
    role: investigator
    exit_when:
      - likely_root_cause_is_identified

  - id: fix
    role: implementer
    exit_when:
      - change_is_implemented

  - id: validation
    role: reviewer
    exit_when:
      - regression_is_verified
      - completion_checks_pass

  - id: done
    terminal: true
```

This format is intentionally incomplete. The schema should evolve from real usage rather than speculative design.

### Session

Each workflow execution creates a persistent session.

A session should eventually contain at least:

- a unique ID,
- the workflow name and version,
- the current state,
- user-provided context,
- agent-generated context,
- transition history,
- decisions,
- generated artifacts,
- timestamps,
- completion status.

A session can be paused and resumed later.

### State

A state is one meaningful phase of a workflow.

Each state should have a clear contract:

- entry conditions,
- responsibilities,
- allowed actions,
- required context,
- expected artifacts,
- exit conditions.

The agent may move to the next state automatically when the exit conditions are satisfied.

### Agent role

Workflows reference roles rather than concrete models.

Examples:

- `investigator`
- `planner`
- `implementer`
- `reviewer`
- `researcher`

A role describes responsibility.

It should not imply a specific provider.

### Capability

Capabilities describe what a role needs from an execution backend.

Possible examples:

- strong reasoning,
- code editing,
- repository access,
- web research,
- long context,
- tool execution,
- fast low-cost inference.

Capabilities make it possible to change the underlying model without rewriting workflows.

### Provider

A provider is an execution backend such as an agent harness, coding environment, API, or subscription-backed tool.

Provider configuration belongs below workflows and roles.

The workflow should not care whether a role is currently executed through Codex, Claude Code, OpenCode, Cursor, Hermes, Pi, or another future tool.

## First workflow: Bugfix

The first supported workflow is `bugfix`.

This is deliberate: bug reports often arrive with incomplete, ambiguous, or low-quality context.

The first phase is therefore not implementation.

It is **discovery**.

The initial workflow is expected to look approximately like this:

```text
Reported
   ↓
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

### Discovery

The agent interviews the user one question at a time.

The next question should depend on previous answers.

The purpose is to build enough context to investigate safely.

Potential topics include:

- observed behavior,
- expected behavior,
- reproduction steps,
- affected environments,
- scope of impact,
- regression history,
- relevant logs,
- relevant code areas,
- known constraints.

### Investigation

The agent examines the available evidence and codebase before proposing a fix.

The output should include a concrete diagnosis or clearly documented uncertainty.

### Fix

The implementation role makes the smallest justified change that addresses the diagnosed cause.

### Validation

The workflow verifies the fix before declaring completion.

Validation may invoke existing quality and delivery skills.

### Done

The workflow records the final outcome and generated artifacts.

## Interaction model

The long-term interface is expected to present a list of available workflows rather than requiring the user to remember low-level commands.

Conceptually:

```text
Agentic Suite

Available workflows
  → Bugfix
    Feature
    Review
    Research
    Release
```

Selecting a workflow starts or resumes a session.

The first implementation may be CLI-based. The workflow model should not depend on the interface.

## Initial scope

Version 0 should stay intentionally small.

Included:

- one workflow: `bugfix`,
- declarative YAML definition,
- persistent session identity,
- explicit workflow states,
- autonomous transitions based on exit criteria,
- one active workflow session at a time,
- integration with reusable skills.

Not included initially:

- workflow-to-workflow calls,
- manager/worker agent trees,
- dozens of parallel agents,
- automatic model benchmarking,
- complex scheduling,
- distributed execution,
- a full graphical application.

These can be added only when real usage demonstrates the need.

## Proposed repository layout

```text
.
├── README.md
├── docs/
│   ├── philosophy.md
│   └── adr/
│       └── 0001-workflow-first.md
├── workflows/
│   └── bugfix.yaml
├── agents/
├── providers/
├── commands/
├── hooks/
└── config/
```

The layout is a starting point, not a frozen contract.

## Roadmap

### Phase 1 — Foundations

- define the project philosophy,
- define the core architecture decisions,
- define the first `bugfix` workflow,
- define a minimal workflow schema.

### Phase 2 — Minimal runtime

- load a YAML workflow,
- start a session,
- persist state,
- advance between states,
- pause and resume a session.

### Phase 3 — Agent integration

- map workflow roles to concrete agents,
- expose existing Skills as reusable primitives,
- introduce provider configuration.

### Phase 4 — Real-world iteration

Use the `bugfix` workflow on real tasks.

Only add abstractions that are justified by repeated usage.

### Later

Potential future directions:

- feature development workflows,
- research workflows,
- review orchestration,
- release workflows,
- worktree-aware parallel execution,
- manager/worker agents,
- graphical workflow status,
- remote and persistent cloud execution.

## Status

Agentic Suite is currently in its architecture and design phase.

The first milestone is simple:

> Successfully use one declarative `bugfix` workflow on real software engineering work from discovery to validated completion.
