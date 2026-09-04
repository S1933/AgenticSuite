# Plan d'exécution — Lot F : second workflow `feature`

Document de travail. Le lot complet est décrit dans le document source
« Plan d'exécution — Lot F » ; ce fichier en est la version de travail dans le repo,
avec les prédictions et les constats.

## 1. Le but réel

L'objectif visible est d'avoir un workflow `feature`. Ce n'est pas l'objectif réel.

Le schéma, les règles de lint et les ADR 0002 à 0006 n'ont jamais vu qu'un seul
workflow. Tout ce qu'ils contiennent de spécifique à `bugfix` est aujourd'hui
indiscernable de ce qu'ils contiennent de générique. `architecture.md` le reconnaît
pour R10, qui code en dur `discovery` et `reclassified`.

Le Lot F est le **premier test de généricité du projet**. Le workflow `feature` est
l'instrument, pas le produit.

Conséquence sur la méthode : les échecs de lint attendus sont écrits **avant**
d'écrire le YAML (section 4). Un lot dont on ne peut pas dire à l'avance ce qui le
falsifierait ne prouve rien.

## 2. Prérequis bloquants (résolus)

- **P1 — Réconcilier `architecture.md`** : fait. La section 4 ne liste plus comme
  absents les modules livrés (Lots 1-4). Le test `tests/e2e/test_architecture_doc.py`
  vérifie que les modules de la section 2 importent, que les modules déclarés absents
  dans la section 4 lèvent `ImportError`, et que les sous-commandes documentées dans
  `reference/cli.md` correspondent au CLI réel.
- **P2 — Ratifier C1-C5** : fait. C2 → ADR 0007 ; C3/C5/C6 →
  `0003-precisions-evaluator-initial-state-context-scope.md` ; C1/C4 →
  `0003-precisions-conventions-C1-C4.md` (nouvelle). `DECISIONS.md` mis à jour :
  les conventions ne sont plus provisoires.

## 3. Ce que le schéma actuel ne sait pas exprimer

Ces manques ne sont **pas corrigés dans ce lot** — ils sont documentés, et le YAML
est écrit avec les primitives existantes. Règle du projet : pas d'abstraction avant
trois usages réels.

| Manque | Contournement retenu pour v1 |
|---|---|
| Pas de gate humaine obligatoire | Une gate est exprimée comme un déclencheur d'escalade global qui force `blocked` ; `blocked` est reprenable et `session_resumed` ne consomme pas le budget. Fonctionnellement une gate, mais conditionnelle, pas obligatoire. |
| Pas de boucle sur des sous-tâches | Le découpage en étapes vit dans un artefact `implementation_plan`, pas dans le schéma. `implementation` est un seul état ; le respect du découpage est une assertion. |
| Rôles fermés à actor/evaluator | Pas de rôle `architect` ni `planner`. Tous les états actifs sont `role: actor`. La différence de responsabilité vit dans `description` et dans les champs exigés. |
| `ALLOWED_KINDS` est fermé et non vérifié | v1 n'utilise que les kind déjà présents dans `bugfix.yaml` : `note`, `decision`, `patch`, `test_result`. Aucun kind nouveau avant vérification. |

La gate manquante est la principale sortie attendue du lot : sur `feature`, une
transition automatique design → implementation coûte une implémentation entière de la
mauvaise chose. Si trois sessions confirment cette friction → ADR 0008 (gates).

## 4. Prédictions de lint — à vérifier AVANT de corriger quoi que ce soit

Enregistrées avant d'exécuter `agentic lint workflows/v1/feature.yaml`. Chaque
prédiction vérifiée est un défaut de généricité du linter, pas du workflow.

| # | Prédiction | Si vérifiée |
|---|---|---|
| L1 | R10 échoue ou ne s'applique pas : elle cite `discovery` et `reclassified`. `feature` utilise `intake` et `descoped` | Généraliser R10 : la contrainte porte sur « le terminal de reclassement n'est atteignable que depuis l'état initial », pas sur deux noms |
| L2 | Une règle sur `initial_state` peut supposer `discovery` | Même traitement |
| L3 | La règle de polarité (POLARITY_NEGATION_RE) peut refuser des identifiants d'assertion d'échec. `bugfix` contient `no_root_cause_found` → la règle tolère probablement la négation côté échec. À confirmer. Documenter la convention réelle dans DECISIONS.md |
| L4 | R21 (atteignabilité) doit passer : `abandoned` est déclaré dans `escape_states` et non routé depuis aucun état — comme dans `bugfix`, qui est lint-clean. Si R21 échoue ici mais pas sur `bugfix` → bug de règle | Traiter comme bug de règle |
| L5 | Aucune règle ne signalera l'absence de gate (le concept n'existe pas) | Confirme que le manque est invisible au linter — argument pour l'ADR 0008 |

**Résultats effectifs** (remplis à la première exécution) :

| # | Prédit | Résultat |
|---|---|---|
| L1 | R10 échoue ou ne s'applique pas | ✅ vérifiée, dans le pire des cas : R10 est devenue **silencieuse** sur feature (aucun état nommé `reclassified` → aucune erreur), donc `descoped` (le terminal de reclassement de feature) n'était **pas protégé**. R10 généralisée : un terminal local cible d'un `on_failure` n'est atteignable que depuis `initial_state` — aucun nom d'état codé. Testé (`tests/lint/test_R10_generic.py`) |
| L2 | initial_state suppose discovery | ❌ non vérifiée : R20 est déjà générique (vérifie présence + non-terminal + non-escape), nulle part `discovery` n'est supposé |
| L3 | polarité tolère la négation côté échec | ✅ vérifiée : feature est lint-clean, aucun identifiant d'assertion d'échec (`plan_is_invalidated`, `implementation_cannot_proceed`, …) n'est refusé. La regex `is_not/not_/does_not_` ne matche pas ces formes |
| L4 | R21 passe | ✅ vérifiée : `abandoned` non routé passe sur feature comme sur bugfix — la règle ne traite pas les deux fichiers différemment |
| L5 | absence de gate invisible au linter | ✅ vérifiée : feature passe 0/0 sans aucune primitive de gate. Le manque est invisible au linter — argument en faveur d'une ADR 0008 (gates) si la friction se confirme en sessions réelles |

## 5. Lot F.1 — `workflows/v1/feature.yaml`

Cinq états actifs, deux terminaux propres, les deux états d'échappement de l'ADR 0003
D5 : `Requested → Intake → Exploration → Design → Implementation → Validation → Done`,
avec retours arrière enregistrés (`Intake → Descoped`, tout → `Blocked`/`Abandoned`).

Calibrages assumés : `max_attempts: 3` sur `implementation` (contre 2 partout ailleurs),
`max_transitions: 24` (contre 20 pour bugfix : cinq états actifs, six arêtes arrière).
À recalibrer après la première session réelle (F.4), pas avant.

## 6. Lots suivants

- **F.2 — Généraliser le linter** : R10 sans noms d'états codés en dur ;
  `ALLOWED_KINDS` vérifié contre le contenu réel ; R11/R12 refusent les booléens
  (`max_attempts: true`) ; supprimer `LintError` mort ; ratifier ou remplacer
  `{"_unknown": True}`.
- **F.3 — DECISIONS.md** : polarité (L3), gate manquante et contournement, boucle
  manquante et localisation du découpage.
- **F.4 — Session réelle** : une session `feature` sur une petite fonctionnalité
  réelle. Candidat naturel : F.2 lui-même, exécuté par le workflow qu'il vient de
  valider. À mesurer sans rien corriger : où la session atterrit (budget) ; faux
  positifs de l'évaluateur ; déclenchement de `scope_expansion_beyond_intake` ;
  coût de l'absence de gate obligatoire.
- **F.5 — Ratification conditionnelle** : ne pas exécuter avant trois sessions
  réelles. Si les trois confirment que la transition automatique design →
  implementation coûte trop → ADR 0008 (gates humaines). Sinon, ne rien écrire.

## 7. Ce que ce lot n'inclut pas

Gates humaines comme primitive · boucle sur sous-tâches · rôles au-delà d'actor et
evaluator · état de livraison (commit, PR, changelog) · nouveaux kind d'artefacts ·
workflow review/research/release. L'état de livraison est délibérément absent :
`feature` s'arrête à `done` sans produire de PR — la livraison est un workflow
distinct, et l'ajouter mélangerait deux responsabilités.