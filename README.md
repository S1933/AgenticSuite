# Agentic Suite

Agentic Suite est un système de workflows déclaratifs pour travailler avec des agents IA sur des tâches d'ingénierie logicielle.

> **L'humain lance des workflows. Les workflows coordonnent des agents. Les agents utilisent des skills. Les fournisseurs et les modèles restent interchangeables.**

C'est d'abord un setup d'ingénierie personnel, gardé assez générique pour être cloné et adapté.

**Phase actuelle : Phase 2-3 livrées, Phase 4 amorcée.** Le runtime minimal est complet
(sessions chaînées, évaluateur isolé, acteur model réel, boucle `run` jusqu'à
terminal/blocked), l'intégration des agents est en place (providers injectés
opencode-go), et les premières sessions réelles de validation du workflow `bugfix`
tournent. Le jalon restant — un workflow `bugfix` qui va de la découverte à une
**complétion validée** (patch appliqué + tests verts) — est le chemin critique du
Lot 5. Voir la feuille de route plus bas.

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
- **Validation** — le correctif est appliqué à l'arbre de travail (check `artifact_applied`, ADR 0009) puis vérifié avant complétion.
- **Done** — le résultat et les artefacts sont enregistrés.

Une définition complète et lintée de ce workflow vit dans [`workflows/v1/bugfix.yaml`](workflows/v1/bugfix.yaml). Les conventions utilisées par cette définition et qui attendent d'être ratifiées sont documentées dans [`workflows/v1/DECISIONS.md`](workflows/v1/DECISIONS.md).

Les conditions qui autorisent un état à être quitté, et ce qui se passe quand elles ne peuvent pas l'être, sont définies dans l'[ADR 0002](docs/adr/0002-exit-criteria-and-failure-paths.md).

## Périmètre de la v0

**Inclus :** deux workflows (`bugfix`, `feature`), définition déclarative en YAML, identité de session persistante (journal JSONL chaîné SHA-256), états explicites, transitions sous contrat, sessions multiples concurrentes, évaluateur distinct de l'acteur, application du patch avant validation (ADR 0009), linter des workflows, interface menu.

**Exclus :** appels d'un workflow à un autre, arbres manager/worker, flottes d'agents parallèles, benchmark de modèles, ordonnancement, exécution distribuée, application graphique, optimisation automatique de fournisseur, hiérarchies manager/worker.

Ces éléments ne seront ajoutés que si l'usage réel en démontre le besoin (cf. principe 16 de la philosophie).

## Interface

L'interface visée présente une liste de workflows à démarrer ou reprendre, plutôt que des commandes de bas niveau. La première implémentation est une CLI, mais le modèle de workflow ne dépend pas de l'interface.

```bash
agentic                                          # menu : workflows + sessions
agentic lint workflows/v1/bugfix.yaml            # valide un workflow
agentic start bugfix                              # ouvre une session, une tentative
agentic run bugfix --context rapport.json         # boucle complète jusqu'à terminal/blocked
agentic status <session_id>                       # état + intégrité
agentic resume <session_id> <state>               # reprend une session bloquée
agentic log <session_id>                          # affiche le journal
```

`agentic` sans argument ouvre le menu (Lot 6) : liste les workflows et les
sessions (état + intégrité), actions numérotées — un workflow se démarre, une
session se reprend ou se lit. Rendu et numérotation sont dans
`src/agentic_suite/ui.py`, purs et testés.

L'exécution fait appel à deux providers injectés (ADR 0005) : un **acteur**
(`AGENTIC_ACTOR_CMD`, produit contexte + artefacts) et un **évaluateur**
(`AGENTIC_EVALUATOR_CMD`, juge les assertions — distinct de l'acteur, ADR 0003 D9).
Les adaptateurs model de référence (opencode-go) sont dans
`src/agentic_suite/providers/` ; la CI n'appelle jamais un vrai modèle. Les
verdicts du juge sont journalisés par transition (`criteria_verdicts`, visible via
`agentic log`) — le « pourquoi » d'un blocked se lit dans le journal, pas par
devinette.

## Arborescence actuelle

```
.
├── README.md
├── LICENSE
├── pyproject.toml                  # packaging Python, entry point `agentic`
├── docs/
│   ├── concepts.md
│   ├── philosophy.md
│   └── adr/                        # 9 ADR + 1 fichier de précisions
├── workflows/
│   └── v1/
│       ├── bugfix.yaml             # workflow déclaratif, lint-clean
│       ├── feature.yaml            # second workflow (test de généricité)
│       └── DECISIONS.md            # conventions provisoires, ratifiées par ADR
├── src/agentic_suite/              # linter, session, runtime, providers, UI
├── tests/                          # 236 tests (lint, vérification, refus, session, ui, e2e)
└── .github/workflows/ci.yml        # CI matrix Python 3.11-3.13
```

## Feuille de route

**Phase 1 — Fondations.** Philosophie ✅ · architecture centrée workflow ✅ · critères de sortie et chemins d'échec ✅ · schéma déclaratif ✅ · persistance des sessions ✅ · première définition `bugfix` ✅ · linter ✅

**Phase 2 — Runtime minimal.** Charger un workflow YAML, démarrer une session, persister l'état, avancer entre les états, interrompre et reprendre. ✅ (engine, runner, CLI `start/status/resume/log`)

**Phase 3 — Intégration des agents.** Mapper les rôles à des agents concrets, exposer les Skills comme primitives, introduire la configuration des fournisseurs. ✅ (providers acteur/évaluateur opencode-go, résolution `command_ref`)

**Phase 4 — Itération sur le réel.** Utiliser `bugfix` sur de vraies tâches. N'ajouter des abstractions que lorsqu'un usage répété les justifie. 🔄 en cours (Lot 5 : sessions réelles, patch appliqué via ADR 0009, chemin vers `done`). Le menu interactif (Lot 6) est livré.

**Plus tard.** Workflows feature, research, review et release ; exécution parallèle par worktree ; agents manager/worker ; visualisation de l'état des workflows ; exécution distante.

## Plan d'exécution

Le travail vers la Phase 4 est découpé en sept lots — `Lot 0` à `Lot 7` — dans le document de travail [`docs/planning/plan-execution.md`](docs/planning/plan-execution.md). Les lots sont conçus pour que le workflow précède le runtime : aucune abstraction n'est introduite avant que trois sessions réelles ne l'aient réclamée.

## Documentation

**Conception — pourquoi**

- [`docs/philosophy.md`](docs/philosophy.md) — principes et raisonnement
- [`docs/concepts.md`](docs/concepts.md) — vocabulaire
- [`docs/adr/`](docs/adr/) — décisions d'architecture (ADR 0001 à 0009, plus les fichiers de précisions)

**Technique — comment**

- [`docs/architecture.md`](docs/architecture.md) — modules, frontières, ce qui n'existe pas encore
- [`docs/development.md`](docs/development.md) — installation, tests, ajout d'une règle de lint
- [`docs/reference/workflow-schema.md`](docs/reference/workflow-schema.md) — référence complète du schéma YAML
- [`docs/reference/lint-rules.md`](docs/reference/lint-rules.md) — catalogue des 20 règles de lint
- [`docs/reference/cli.md`](docs/reference/cli.md) — commandes, codes de sortie, usage en CI

**Workflow de référence**

- [`workflows/v1/bugfix.yaml`](workflows/v1/bugfix.yaml) — première définition complète du workflow bugfix
- [`workflows/v1/DECISIONS.md`](workflows/v1/DECISIONS.md) — conventions provisoires et leur statut de ratification

## Licence

MIT. Voir [LICENSE](LICENSE).