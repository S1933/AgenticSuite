# ADR 0002: Exit Criteria and Failure Paths

- **Status:** Accepted
- **Date:** 2026-09-02
- **Supersedes:** none
- **Refines:** ADR 0001 (Workflow First Architecture)

## Context

ADR 0001 established contract-driven autonomy: an agent may advance a session when the exit criteria of the current state are satisfied. It did not define two things that autonomy depends on.

**How a criterion is evaluated.** Criteria such as `problem_is_understood` are natural-language predicates. If the agent that produced the work also decides whether the criterion holds, the system reproduces the failure mode that Philosophy 12 rejects: declaring success because work happened rather than because evidence exists.

**What happens when a criterion cannot be satisfied.** The `bugfix` state chain in ADR 0001 only moves forward. Real bug work produces outcomes that chain cannot express: the bug is not reproducible, no root cause is found, the fix does not survive validation, or discovery reveals the report is not a bug at all. A state machine with no failure path either stalls or invents a way forward.

Both gaps affect the same guarantee. Autonomy is only acceptable if advancing is verifiable and not advancing is a legal outcome.

## Decision

### 1. Two kinds of exit criteria

Every exit criterion is either a **check** or an **assertion**.

A **check** is deterministic and evaluated by the runtime, never by an agent. Examples: a required context field is present and non-empty, a named artifact exists, a command exits with status 0.

An **assertion** is a judgment and is evaluated by an agent.

A state may not rely on an assertion when the same condition is expressible as a check. Checks are preferred wherever the condition can be reduced to a fact.

### 2. Required context turns judgment into a checklist

Most discovery-style criteria are not really judgments. `problem_is_understood` is a derived predicate over a set of fields that must be collected.

Each state declares the context fields it requires before it can exit. A field may be filled with an explicit "unknown, and here is why", but it may not be left empty. The check is the presence of the fields; the assertion, if any, only covers what remains genuinely subjective.

### 3. Assertions require evidence

An assertion may only evaluate to true by referring to something already recorded in the session: a collected context field, an artifact, a command output, a diagnosis.

An assertion that cites nothing evaluates to false. New claims produced at evaluation time are not evidence.

### 4. The evaluator is not the actor

Assertions are evaluated in a separate step whose input is the session record, not the working conversation that produced it.

The workflow may assign a different role to the evaluation. Doing so is required for states that produce a change to the codebase, and optional elsewhere. This is the same reasoning as Philosophy 13 applied to transitions rather than to code review.

### 5. Failure states are first-class

The following states exist in addition to the happy path.

`blocked` — non-terminal. The session cannot advance and waits for a human. It records what is missing and what would unblock it. A blocked session is resumable.

`abandoned` — terminal. No fix was delivered. It records why, and what was learned.

`reclassified` — terminal for this workflow. Discovery concluded the report is not a bug: expected behaviour, a feature request, or an external cause. It records the conclusion and the evidence.

### 6. Backward transitions are legal and counted

A workflow may declare backward transitions. For `bugfix`, at least:

- `validation → investigation` when a regression or completion check fails,
- `investigation → discovery` when the evidence shows required context is missing.

Every backward transition increments an attempt counter on the target state.

### 7. Budgets, not loops

A workflow declares a maximum number of attempts per state and a maximum number of transitions per session.

Exceeding either budget forces a transition to `blocked`. The system never loops silently and never lowers a criterion to make it pass.

### 8. Mandatory escalation

Regardless of criteria, a session moves to `blocked` when any of the following occurs:

- a budget is exceeded,
- the next action is irreversible or destructive,
- the change is security-relevant,
- the agent identifies a product, architectural, or domain decision that belongs to the human,
- the collected context contains a contradiction that cannot be resolved from the session.

### 9. Every transition is recorded

A transition is only valid if the session records: origin state, target state, timestamp, the criteria evaluated, the kind of each (check or assertion), the evidence referenced, the evaluating role, and the attempt counter.

An unrecorded transition is invalid. This is what makes autonomy auditable rather than trusted.

## Consequences

### Positive

- Advancing becomes verifiable instead of asserted.
- Not advancing becomes a legal, recorded outcome rather than a stall or a fabrication.
- Budgets bound the cost and duration of an autonomous session.
- The transition record gives a concrete debugging surface when a workflow behaves badly.
- Required-context checklists make discovery testable without a runtime.

### Negative

- Workflow definitions become more verbose: fields, checks, budgets, and backward transitions all have to be written.
- Separating evaluator from actor costs an extra agent call per transition.
- Deciding which conditions can be reduced to checks is real design work per state.
- Poorly chosen required fields will make discovery feel like a form rather than an interview.

## Alternatives considered

**Human approval at every transition.** Rejected: it removes the autonomy that motivates the project and makes long sessions unusable.

**Agent self-judgment only.** Rejected: this is the current implicit design and the reason for this ADR.

**Deterministic checks only.** Rejected: conditions such as "a plausible root cause is identified" cannot be reduced to a check without losing their meaning.

**Confidence scores on criteria.** Rejected: model-reported confidence is not calibrated, and a numeric threshold would give the appearance of rigour without the substance.

**Failure handled as free-text at the end of a session.** Rejected: failure needs to be a state so that it is resumable, countable, and visible in the same place as progress.

## Validation

This decision is considered successful when, on real sessions:

1. a bug that cannot be reproduced ends in `blocked` with a stated missing element, and no fix is proposed,
2. a failed validation returns the session to `investigation` with an incremented counter rather than a second declaration of success,
3. a report that turns out not to be a bug ends in `reclassified`,
4. exceeding the attempt budget produces `blocked` rather than continued attempts,
5. every state change in the session record carries its evidence.

## Follow-up decisions

- ADR 0003: workflow YAML schema, including the syntax for fields, checks, assertions, budgets, and transitions.
- ADR 0004: session persistence format and the transition record.
- A later ADR on skill invocation contracts, once a state needs to call a skill as part of a check.
