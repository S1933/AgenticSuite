# Décisions d'architecture (ADR)

Numérotées, immuables une fois acceptées. Une décision qui change est remplacée par une nouvelle ADR plutôt que modifiée sur place.

| ADR | Titre | Statut |
| --- | --- | --- |
| [0001](0001-workflow-first.md) | Architecture centrée workflow | Acceptée |
| [0002](0002-exit-criteria-and-failure-paths.md) | Critères de sortie et chemins d'échec | Acceptée |

## Prévues

- 0003 — schéma YAML des workflows
- 0004 — format de persistance des sessions
- 0005 — configuration des rôles, capacités et fournisseurs
- 0006 — contrat d'invocation des skills

## Modèle

```markdown
# ADR NNNN : Titre

- **Statut :** Proposée | Acceptée | Remplacée par l'ADR NNNN
- **Date :** AAAA-MM-JJ

## Contexte
Ce qui impose cette décision, et quelles contraintes s'appliquent.

## Décision
Ce qui est décidé, formulé de façon à pouvoir être suivi sans lire le raisonnement.

## Conséquences
### Positives
### Négatives

## Alternatives considérées
Chacune avec la raison de son rejet.

## Validation
Comment nous saurons que la décision était la bonne.
```
