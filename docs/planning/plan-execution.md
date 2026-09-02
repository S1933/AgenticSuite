# Plan d'exécution

**Statut :** document de travail. Ce qui est décidé est écrit, ce qui n'est pas démontré n'est pas construit.

**Date :** 2026-09-02

## Point de départ

ADR 0001 à 0007 acceptées, schéma de workflow stable, premier runtime (linter) fonctionnel, 95 tests passants. Le premier jalon du README — utiliser un workflow `bugfix` déclaratif sur du vrai travail d'ingénierie, de la découverte à une complétion validée — n'est pas atteint.

## État réel au démarrage

Ce qui existe et fonctionne :

| Élément | État | Preuve |
|---|---|---|
| Philosophie, concepts | Écrit | `docs/philosophy.md`, `docs/concepts.md` |
| ADR 0001-0007 + précisions | Acceptées | `docs/adr/` |
| `workflows/v1/bugfix.yaml` | Lint-clean | 0 erreur, 0 warning |
| Linter des workflows | Fonctionnel | 19 règles, 95 tests |
| CI GitHub Actions | Configurée | matrix Python 3.11-3.13 |

Ce qui n'existe pas encore :

| Manque | Conséquence |
|---|---|
| Runtime des sessions (start, transition, pause, resume) | Aucune session ne peut tourner |
| Persistance JSONL append-only | Aucune intégrité de session |
| Chaînage par hash SHA-256 | Une session éditée à la main passe |
| Invalidation a posteriori des transitions | Écrase un artefact ne casse rien |
| Résolveur `command_ref` | Les checks `command_exit_zero` ne s'exécutent pas |
| Chargement de fournisseurs | `actor` et `evaluator` sont des noms, pas des instances |
| Boucle agent | Tout se pilote à la main |
| Tests bout en bout sur cas réels | Aucun retour d'usage réel |

## Règles de conduite

Cinq règles qui arbitrent les décisions non prévues par ce document.

- **R1 — Le workflow avant le runtime.** Une amélioration du runtime qui ne débloque aucun état ou critère du workflow est reportée. Le risque principal du projet n'est pas un runtime insuffisant, c'est un runtime qui devient le produit.
- **R2 — Trois sessions avant une abstraction.** Aucune généralisation n'est introduite avant que trois sessions réelles distinctes l'aient réclamée. Une session qui râle est une anecdote.
- **R3 — Un mécanisme, une ADR.** Tout ajout qui change le schéma, l'évaluation, les budgets ou la persistance exige une ADR numérotée avant le code.
- **R4 — Les garanties se testent, pas se déclarent.** Un mécanisme d'ADR 0002 ou 0003 n'est considéré implémenté que lorsqu'un test le fait échouer quand on le retire.
- **R5 — Le plan se révise après chaque lot.** Un lot terminé produit un constat écrit. Si le constat contredit un lot ultérieur, c'est le lot ultérieur qui change.

## Lots d'exécution

Sept lots. Chacun porte des tâches, une définition de fin dans le vocabulaire du projet (vérifications et assertions), ses dépendances et son risque propre.

### Lot 0 — Consolidation du linter ✅

**Intention :** transformer un linter jetable en base modifiable sans peur.

**Réalisé :** 19 règles de lint couvrant D1, D2, D3, D4, D5, D6, D7, D8, D9 + ADR 0007 + P1/P2/P3 ; 95 tests ; CI matrix Python 3.11-3.13 ; package installable avec `pip install -e .[test]`.

**Découvertes significatives :**

- La regex R17 doit être plus stricte que la première intuition (`cannot_` / `fails_` / `invalid_` nomment des conditions, pas des négations).
- `bugfix.yaml` v1 contenait `report_is_not_a_bug` qui violait R17. Renommé en `report_is_a_feature_request` pour suivre ADR 0007 D5.

### Lot 1 — Fermer les trous de garantie ⬜

**Intention :** rendre vraies les garanties que les ADR 0002 et 0003 affirment déjà.

**Tâches principales :**

1. Intégrité de session (ADR 0004 D3, D4, D5) — chaîage SHA-256, refus dur à la lecture, invalidation a posteriori.
2. Test d'invariant D9 — capturer la conversation de l'acteur, faire évaluer par l'évaluateur, vérifier que l'évaluateur n'a référencé aucun élément absent de l'enregistrement de session.
3. Isolation de processus de l'évaluateur — l'évaluateur reçoit le fichier de session et rien d'autre.
4. Précision de l'ADR 0003 D7 sur les états à évaluateur `actor`.

**Dépendances :** aucune (le Lot 0 a posé les bases).

**Risque :** les tâches 1.2 et 1.3 sont les plus lourdes. Sans elles, la qualification « workflow validé » n'existe pas.

### Lot 2 — ADR 0005 : rôles, capacités, fournisseurs ⬜

**Intention :** remplacer les rôles implicites par la couche de résolution.

**Tâches principales :**

1. Écrire `config/role_assignments.yaml`, `config/providers.yaml`.
2. Résolution `command_ref` par projet (`<projet>/.agentic/commands.yaml`).
3. Rejouer la session du Lot 1 avec deux fournisseurs distincts.

**Dépendances :** Lot 1.

**Risque :** dérive vers un système de plugins générique. Le principe 16 l'interdit.

### Lot 3 — ADR 0006 : contrat d'invocation des skills ⬜

**Intention :** rendre réelle la séparation Skills / Agentic Suite.

**Dépendances :** Lot 2.

### Lot 4 — Boucle agent ⬜

**Intention :** arrêter de piloter le CLI à la main.

**Dépendances :** Lots 1, 2, 3.

### Lot 5 — Validation Phase 4 sur cas réels ⬜

**Intention :** le seul lot qui décide si le projet vaut quelque chose.

**Tâches principales :**

1. Dix sessions bugfix sur de vrais bugs, non choisis pour arranger le workflow.
2. Provoquer les sept scénarios de validation des ADR 0002 et 0003.
3. Mesurer le ratio de champs sortis inconnus (signal de découverte-formulaire).
4. Mesurer les refus par type (un refus jamais déclenché est un mécanisme mort).

**Dépendances :** Lot 4. C'est le chemin critique du projet.

**Risque majeur :** choisir des bugs faciles pour faire passer les scénarios. Les bugs viennent du travail réel en cours, pas d'une liste établie pour le plan.

### Lot 6 — Interface ⬜

**Intention :** rendre le système utilisable sans mémoriser le CLI.

**Dépendances :** Lot 5.

### Lot 7 — Deuxième workflow ⬜

**Intention :** vérifier que le schéma généralise.

**Condition d'entrée stricte :** dix sessions bugfix terminées et le Lot 5 clos.

## Chemin critique

```
Lot 0 (✅) → Lot 1 → Lot 2 → Lot 4 → Lot 5
                                  ↑
                            Lot 3 (parallélisable avec la fin de Lot 2)
                                  ↓
                              Lot 6 → Lot 7
```

## Hors périmètre

Refusé explicitement, tant qu'aucune session réelle ne le réclame trois fois :

- workflows qui appellent d'autres workflows
- hiérarchies manager/worker
- agents parallèles, worktrees multiples
- exécution distribuée ou cloud
- interface graphique
- benchmark ou optimisation automatique de fournisseur
- système de plugins générique
- budget en tokens ou en coût
- quatrième type de vérification
- semver sur les workflows

## Ce qui déclare le plan réussi

- Les sept scénarios de validation sont obtenus sur des sessions réelles et enregistrés.
- Dix sessions bugfix ont atteint un état terminal.
- Le test d'invariant D9 passe en CI.
- Le même workflow tourne sur deux projets et deux fournisseurs sans modification du YAML.
- Le développeur préfère lancer le workflow que travailler sans lui, sur du vrai travail, sans se forcer.

La dernière ligne est la seule qui compte vraiment, et c'est la seule qu'aucun test ne peut établir.