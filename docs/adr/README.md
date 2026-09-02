# Décisions d'architecture (ADR)

Numérotées, immuables une fois acceptées. Une décision qui change est remplacée par une nouvelle ADR plutôt que modifiée sur place.

| ADR | Titre | Statut |
| --- | --- | --- |
| [0001](0001-workflow-first.md) | Architecture centrée workflow | Acceptée |
| [0002](0002-exit-criteria-and-failure-paths.md) | Critères de sortie et chemins d'échec | Acceptée |
| [0003](0003-workflow-schema.md) | Schéma déclaratif de workflow | Acceptée |
| [0004](0004-session-persistence.md) | Persistance des sessions | Acceptée |
| [0007](0007-assertion-polarity.md) | Polarité des assertions de transition | Acceptée |
| [0003-précisions](0003-precisions-evaluator-initial-state-context-scope.md) | Évaluateur explicite, état initial, portée des références | Acceptée |
| [0005](0005-roles-providers-command-ref.md) | Rôles, fournisseurs, résolution de command_ref | Acceptée |

## Prévues
- 0006 — contrat d'invocation des skills
- 0008 — sécurité opérationnelle (éventuelle)

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