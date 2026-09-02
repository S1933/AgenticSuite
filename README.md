# Agentic Suite

Agentic Suite est un système de workflows déclaratifs pour travailler avec des agents IA sur des tâches d'ingénierie logicielle.

> **L'humain lance des workflows. Les workflows coordonnent des agents. Les agents utilisent des skills. Les fournisseurs et les modèles restent interchangeables.**

C'est d'abord un setup d'ingénierie personnel, gardé assez générique pour être cloné et adapté.

**Statut : phase de conception. Pas encore de runtime.** Le premier jalon est d'exécuter un workflow `bugfix` déclaratif sur du travail réel, de la découverte à une complétion validée.

## Pourquoi

Le développement assisté par IA est fragmenté entre outils, modèles, abonnements, prompts et conventions locales. Un développeur peut planifier avec un modèle, implémenter avec un autre, déboguer avec un troisième, et s'appuyer sur des skills distinctes pour la découverte, les tests, la revue et la livraison. Les outils pris isolément sont utiles ; le workflow autour d'eux reste manuel.

Agentic Suite est la couche au-dessus de ces outils. Elle définit quel workflow tourne, dans quel état il se trouve, quel rôle agit ensuite, quelles skills sont disponibles, ce qui autorise le workflow à avancer, et ce qui doit persister entre les étapes.

L'objectif n'est pas un agent de code de plus. C'est un workflow d'ingénierie réutilisable, capable d'utiliser plusieurs agents.

## Articulation avec le dépôt Skills

[`S1933/Skills`](https://github.com/S1933/Skills) reste le registre des primitives réutilisables. Agentic Suite ne le remplace pas.

```
Agentic Suite
    │
    ├── Workflows      coordonnent rôles, états, skills et artefacts
    ├── Agents/Rôles   exécutent les responsabilités du workflow
    ├── Skills         primitives d'ingénierie réutilisables
    └── Fournisseurs   backends d'exécution interchangeables
```

Skills répond à *quelle capacité existe*. Agentic Suite répond à *quand elle est utilisée, par qui, et dans quel workflow*.

## Concepts

Workflow, session, état, transition, critères de sortie, rôle, capacité, fournisseur, skill et artefact sont définis dans [`docs/concepts.md`](docs/concepts.md).

Le raisonnement derrière la conception est dans [`docs/philosophy.md`](docs/philosophy.md).

## Premier workflow : bugfix

Les rapports de bug arrivent avec un contexte incomplet. Le workflow ne commence donc pas par l'implémentation, mais par la découverte.

```
Reported → Discovery → Investigation → Fix → Validation → Done
                ↑            ↑                    │
                └────────────┴────────────────────┘
                      (enregistré, compté)

Tout état → Blocked        en attente d'un humain, reprenable
Discovery → Reclassified   ce n'est pas un bug
Tout état → Abandoned      aucun correctif livré
```

- **Discovery** — l'agent interroge l'utilisateur une question à la fois, en s'adaptant aux réponses précédentes, jusqu'à ce que le contexte requis soit collecté.
- **Investigation** — les preuves et le code sont examinés ; la sortie est un diagnostic ou une incertitude documentée.
- **Fix** — le plus petit changement justifié qui adresse la cause diagnostiquée.
- **Validation** — le correctif est vérifié avant complétion, en réutilisant les skills de qualité et de livraison existantes.
- **Done** — le résultat et les artefacts sont enregistrés.

Les conditions qui autorisent un état à être quitté, et ce qui se passe quand elles ne peuvent pas l'être, sont définies dans l'[ADR 0002](docs/adr/0002-exit-criteria-and-failure-paths.md).

## Périmètre de la v0

Inclus : un workflow (`bugfix`), définition déclarative en YAML, identité de session persistante, états explicites, transitions sous contrat, une seule session active à la fois, intégration avec les skills existantes.

Exclus : appels d'un workflow à un autre, arbres manager/worker, flottes d'agents parallèles, benchmark de modèles, ordonnancement, exécution distribuée, application graphique.

Ces éléments ne seront ajoutés que si l'usage réel en démontre le besoin.

## Interface

L'interface visée présente une liste de workflows à démarrer ou reprendre, plutôt que des commandes de bas niveau. La première implémentation sera probablement une CLI, mais le modèle de workflow ne doit pas dépendre de l'interface.

## Arborescence proposée

```
.
├── README.md
├── LICENSE
├── docs/
│   ├── concepts.md
│   ├── philosophy.md
│   └── adr/
├── workflows/
├── agents/
├── providers/
├── commands/
├── hooks/
└── config/
```

Un point de départ, pas un contrat figé. Seul `docs/` existe aujourd'hui.

## Feuille de route

**Phase 1 — Fondations.** Philosophie ✅ · architecture centrée workflow ✅ · critères de sortie et chemins d'échec ✅ · première définition `bugfix` ⬜ · schéma minimal ⬜

**Phase 2 — Runtime minimal.** Charger un workflow YAML, démarrer une session, persister l'état, avancer entre les états, interrompre et reprendre.

**Phase 3 — Intégration des agents.** Mapper les rôles à des agents concrets, exposer les Skills comme primitives, introduire la configuration des fournisseurs.

**Phase 4 — Itération sur le réel.** Utiliser `bugfix` sur de vraies tâches. N'ajouter des abstractions que lorsqu'un usage répété les justifie.

**Plus tard.** Workflows feature, research, review et release ; exécution parallèle par worktree ; agents manager/worker ; visualisation de l'état des workflows ; exécution distante.

## Documentation

- [`docs/concepts.md`](docs/concepts.md) — vocabulaire
- [`docs/philosophy.md`](docs/philosophy.md) — principes et raisonnement
- [`docs/adr/`](docs/adr/) — décisions d'architecture

## Licence

MIT. Voir [LICENSE](LICENSE).
