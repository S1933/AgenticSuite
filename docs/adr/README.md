# Architecture Decision Records

Numbered, immutable once accepted. A decision that changes is superseded by a new ADR rather than edited in place.

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-workflow-first.md) | Workflow first architecture | Accepted |
| [0002](0002-exit-criteria-and-failure-paths.md) | Exit criteria and failure paths | Proposed |

## Planned

- 0003 — workflow YAML schema
- 0004 — session persistence format
- 0005 — role, capability and provider configuration
- 0006 — skill invocation contract

## Template

```markdown
# ADR NNNN: Title

- **Status:** Proposed | Accepted | Superseded by ADR NNNN
- **Date:** YYYY-MM-DD

## Context
What forces this decision, and what constraints apply.

## Decision
What is decided, stated so it can be followed without reading the rationale.

## Consequences
### Positive
### Negative

## Alternatives considered
Each with the reason it was rejected.

## Validation
How we will know the decision was right.
```
