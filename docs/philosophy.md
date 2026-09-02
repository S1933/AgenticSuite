# Philosophy

Agentic Suite is not an attempt to build the smartest autonomous coding agent.

It is an attempt to build a better way to work with AI agents.

The project treats models, agent harnesses, and subscriptions as replaceable infrastructure. The durable part is the engineering workflow around them.

## 1. Workflow first

The primary abstraction is the workflow.

Users should think:

> I am running a bugfix workflow.

Not:

> I am running model X inside tool Y with prompt Z.

Agents are execution resources.

Models are execution resources.

Skills are execution primitives.

The workflow gives those resources purpose, order, and context.

## 2. Context is part of the work

AI agents are often given requests that are incomplete, ambiguous, or badly structured.

Starting implementation immediately is therefore a mistake.

Agentic Suite treats context acquisition as a first-class workflow phase.

For a bugfix, the workflow begins with discovery.

The agent should interview the user one question at a time, adapt the next question to previous answers, and continue until the problem is sufficiently understood.

The quality of execution depends on the quality of context.

## 3. Ask before making important assumptions

Agents are good at implementation.

They are less reliable when silently making product, architectural, domain, or operational decisions on behalf of the developer.

When a decision materially changes the solution, the system should prefer explicit clarification over hidden assumption.

This does not mean requiring human approval for every workflow transition.

It means distinguishing between:

- missing context that must be clarified,
- execution decisions the agent can make autonomously,
- important design decisions that belong to the human.

## 4. Declarative over imperative

Workflows should be readable without reading runtime code.

A workflow definition should describe:

- its states,
- responsibilities,
- roles,
- transition criteria,
- expected artifacts.

YAML is the initial representation because it is readable, diffable, portable, and easy for both humans and agents to edit.

The runtime interprets the workflow.

The workflow should not be embedded in the runtime.

## 5. Roles over model names

A workflow should request an `investigator`, `implementer`, or `reviewer`.

It should not require a specific commercial model.

Models change quickly.

Pricing changes quickly.

Subscriptions change quickly.

Providers disappear.

A stable workflow should survive all of those changes.

Concrete models belong in configuration.

Responsibilities belong in workflows.

## 6. Capabilities over vendors

Roles may require capabilities such as:

- reasoning,
- code editing,
- repository access,
- web research,
- tool execution,
- long context,
- low latency,
- low cost.

Capabilities provide a layer between workflow roles and providers.

This allows a role to be remapped without changing workflow semantics.

## 7. Skills are primitives, not workflows

A skill should do one reusable thing well.

Examples:

- diagnose a bug,
- review code,
- create a spec,
- create tickets,
- verify completion,
- use a worktree,
- perform a security review.

Higher-level behavior belongs in Agentic Suite.

Agentic Suite composes skills into workflows.

This separation keeps the Skills registry reusable and prevents it from becoming an application framework.

## 8. Repeated behavior should become reusable

Repeated single-step behavior can become a shortcut, preset, or command.

Repeated multi-step behavior should become a workflow.

Repeated domain-specific execution logic can become a skill.

The goal is to reduce manual glue while keeping abstractions understandable.

## 9. Explicit state beats invisible agent behavior

A long-running agent should not feel like a black box.

A workflow should expose where it is:

```text
Discovery → Investigation → Fix → Validation → Done
```

State provides:

- observability,
- resumability,
- debugging,
- predictable automation,
- a better mental model for the user.

The user should be able to understand what the system is currently doing without reading the full conversation history.

## 10. Sessions are persistent

A workflow execution is a session, not a disposable prompt.

Sessions should preserve:

- context,
- decisions,
- history,
- artifacts,
- current state.

A developer must be able to stop working and resume later without reconstructing the whole problem.

Persistence is therefore a core requirement, even if the initial implementation is simple.

## 11. Autonomous transitions, explicit contracts

The user should not need to approve every normal transition.

Instead, each workflow state should define clear exit criteria.

If the criteria are satisfied, the agent may advance automatically.

This gives autonomy boundaries.

The goal is not unrestricted autonomy.

The goal is **contract-driven autonomy**.

## 12. Verification before completion

An agent should not declare success because it changed code.

Completion requires evidence.

Depending on the workflow, evidence may include:

- reproduction no longer failing,
- relevant tests passing,
- regression checks,
- linting or static analysis,
- review,
- security checks,
- documented limitations.

"Done" is a workflow state with criteria, not a sentence generated by a model.

## 13. Use different perspectives when review matters

The agent that implemented a change should not automatically be considered the best reviewer of that same change.

For medium or high-risk work, Agentic Suite should make it possible to use a different role, agent, or model for review.

Cross-model review may be useful, but recursive review loops should be avoided.

More review is not automatically better review.

## 14. Parallelism is optional complexity

Multiple agents, subagents, worktrees, and manager/worker architectures are powerful.

They are also expensive and complex.

Agentic Suite should introduce parallelism only where it solves a demonstrated problem.

A small task should remain small.

A single workflow with one active execution path is the correct starting point.

## 15. Human control lives at the right level

The human should control:

- intent,
- important trade-offs,
- architecture,
- risk tolerance,
- final accountability.

The system should handle:

- repetitive execution,
- state progression,
- context preservation,
- skill selection,
- verification steps,
- routine orchestration.

The purpose of the system is not to remove the developer.

It is to let the developer operate at a higher level.

## 16. Optimize for real usage

Agentic Suite should evolve from actual workflows, not imagined platform requirements.

The first implementation intentionally supports one workflow: `bugfix`.

The project should resist adding:

- generic plugin systems,
- distributed schedulers,
- multi-agent swarms,
- complex UIs,
- elaborate schemas,

until real usage creates a clear need.

## 17. Portability is a feature

The project should be useful even when the surrounding AI ecosystem changes.

A workflow created today should ideally remain understandable and adaptable later.

That means preferring:

- plain text,
- Markdown,
- YAML,
- explicit contracts,
- simple storage,
- open formats,
- interchangeable execution backends.

## 18. The system should remain understandable

Agentic engineering can easily become a stack of agents managing agents that invoke skills that spawn more agents.

Agentic Suite should resist unnecessary indirection.

A developer should be able to answer:

- Which workflow is running?
- Which state is active?
- Which role is responsible?
- Which skills are being used?
- Why can the workflow advance?
- What artifacts were produced?

If those questions become difficult to answer, the architecture has become too complex.

## Summary

Agentic Suite follows this hierarchy:

```text
Human intent
    ↓
Workflow
    ↓
State
    ↓
Agent role
    ↓
Skills
    ↓
Provider / Model / Tools
```

The higher layers should remain stable.

The lower layers are allowed to change.

That separation is the foundation of the project.
