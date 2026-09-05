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

### Lot 1 — Fermer les trous de garantie ✅

**Intention :** rendre vraies les garanties que les ADR 0002 et 0003 affirment déjà.

**Tâches principales :**

1. Intégrité de session (ADR 0004 D3, D4, D5) — chaîage SHA-256, refus dur à la lecture, invalidation a posteriori.
2. Test d'invariant D9 — capturer la conversation de l'acteur, faire évaluer par l'évaluateur, vérifier que l'évaluateur n'a référencé aucun élément absent de l'enregistrement de session.
3. Isolation de processus de l'évaluateur — l'évaluateur reçoit le fichier de session et rien d'autre.
4. Précision de l'ADR 0003 D7 sur les états à évaluateur `actor`.

**Réalisé :**

- `src/agentic_suite/session.py` : journal JSONL append-only, chaînage SHA-256 (`prev_hash`), vérification d'intégrité à la lecture (`SessionIntegrityViolation` : hash, `prev_hash`, trou de `seq`, ligne tronquée), invalidation a posteriori (D5), comptage du budget excluant `session_resumed` (D8). 11 tests.
- `src/agentic_suite/evaluator.py` : `run_evaluator` (sous-processus à contexte frais, scratch dir, env minimal, copie du journal) et `verify_verdict_grounded` (invariant D9 sémantique). 5 tests avec évaluateur mock — la règle « CI n'appelle jamais un vrai modèle » s'applique à l'évaluateur comme aux providers.
- `docs/adr/0003-precisions-escalation-evaluator.md` (P4) : les triggers `escalate_when` sont toujours évalués par un évaluateur distinct de l'acteur, quelle que soit la valeur de `evaluated_by` ; `evaluated_by` ne couvre que les assertions de sortie de l'état.
- `docs/architecture.md` mis à jour (modules `session.py` et `evaluator.py`).

**Découvertes significatives :**

- La troncature d'un journal a deux formes que la chaîne de hash ne détecte pas seule : un bloc retiré du milieu laisse un trou de `seq` (vérifié), une ligne finale partielle est une troncature matérielle (vérifiée). Les deux sont refusées à la lecture.
- La garantie D9 a deux couches : l'isolation de processus (ce que le sous-processus *peut voir*) et l'ancrage sémantique (ce que son verdict *peut citer*). `verify_verdict_grounded` rend cette seconde couche testable sans runtime complet.
- P4 (escalade vs `actor`) ne change rien à `bugfix.yaml` v1 (C3 impose déjà `evaluated_by: evaluator` partout) mais borne le coût de l'assouplissement P1 : un état en `actor` n'économise pas l'appel d'évaluateur, il n'économise que l'évaluation des assertions.

**Dépendances :** aucune (le Lot 0 a posé les bases).

**Risque :** les tâches 1.2 et 1.3 sont les plus lourdes. Sans elles, la qualification « workflow validé » n'existe pas.

### Lot 2 — ADR 0005 : rôles, capacités, fournisseurs ✅

**Intention :** remplacer les rôles implicites par la couche de résolution.

**Tâches principales :**

1. Écrire `config/role_assignments.yaml`, `config/providers.yaml`.
2. Résolution `command_ref` par projet (`<projet>/.agentic/commands.yaml`).
3. Rejouer la session du Lot 1 avec deux fournisseurs distincts.

**Réalisé :**

- `src/agentic_suite/commands.py` : résolution `command_ref` (ADR 0005 D5) — hiérarchie projet `.agentic/commands.yaml` → machine `~/.config/agentic/commands.yaml`, le projet prime ; `argv` liste obligatoire, refus du format shell/template. Ref non résolu → `None` (échec à l'exécution, jamais à la lecture). 7 tests.
- `src/agentic_suite/providers.py` : rôles fermés (`actor`, `evaluator`) et capacités implicites (D2) ; `providers.yaml` (D3) avec validation du `kind` fermé ; `role_assignments.yaml` (D4) non overridable par projet. Erreurs explicites : `RoleAssignmentMissing`, `ProviderLoadError`, `ProviderCapabilityError`. 6 tests.
- `config/providers.yaml` + `config/role_assignments.yaml` : référence portable — `opencode_model` (kind model) pour `actor`, `evaluator_cli` (kind cli) pour `evaluator`, deux fournisseurs distincts (validation #2).
- `.agentic/commands.yaml` : `run_tests` (`pytest --strict-markers`) et `run_lint` (`agentic lint --strict`) — le projet consomme ses propres commandes.
- 4 tests e2e : résolution des deux rôles sur deux fournisseurs distincts, refus d'un `cli` read-only pour `actor`, résolution des refs projet, workflow sans nom de fournisseur (validation #3).

**Découvertes significatives :**

- La validation #3 (« aucun nom de fournisseur dans `workflows/` ») est testable directement par grep du workflow.
- `evaluator_cli` (lecture seule) ne peut PAS servir `actor` par construction de capacités : c'est le garde-fou D3 qui empêche un évaluateur relâché de faire le travail de l'acteur.
- Les fichiers `config/` du repo sont la référence portable ; le runtime lit `~/.config/agentic/` sur la machine — la copie réelle n'est pas encore installée (rien ne charge la config machine avant le Lot 4).

**Dépendances :** Lot 1.

**Risque :** dérive vers un système de plugins générique. Le principe 16 l'interdit.

### Lot 3 — ADR 0006 : contrat d'invocation des skills ✅

**Intention :** rendre réelle la séparation Skills / Agentic Suite.

**Réalisé :**

- Règle de lint R22 (ADR 0006 D1) : `skills:` déclaré par état, format `{id: snake_case, use_when?: prose}`, id unique par état, refus des entrées non-mapping. 6 tests.
- `src/agentic_suite/skills.py` : événement `skill_invoked` (D4) — bloc journal typé avec `skill_id`, `state_id`, `role`, `input_summary`/`output_summary` ≤ 200 chars, passé par la chaîne d'empreintes (ADR 0004) ; `undeclared_skill_ids` alimente le warning post-exécution D5 (l'invocation non déclarée est enregistrée, jamais refusée). 6 tests.

**Découvertes significatives :** le warning D5 a besoin d'une couche de lecture du journal post-exécution (`undeclared_skill_ids`), pas d'un refus au moment de l'appel — cohérent avec la philosophie D5 « le runtime ne refuse pas, il signale l'écart après coup ».

**Dépendances :** Lot 2.

### Lot 4 — Boucle agent ✅

**Intention :** arrêter de piloter le CLI à la main.

**Réalisé :**

- `src/agentic_suite/engine.py` : machine à états **pure** `advance(ctx, verdict) -> Transition`, sans I/O. Ordre d'évaluation ADR 0003 D5/D7 + C2 : escalade d'abord → assertions d'échec (ordre de déclaration) → sortie nominale (checks + assertions nominales toutes passées) → retry si `attempt < max_attempts`, sinon `blocked`. `max_transitions` force `blocked`. `insufficient_evidence` = échec. 12 tests, couverture complète de la table de transition.
- `src/agentic_suite/runner.py` : orchestrateur `run_attempt` — charge et vérifie le journal (D4), détermine l'état courant, exécute les checks déterministes (contexte/artefact/commande avec résolution `command_ref` ADR 0005), délègue les assertions **et** les triggers d'escalade à l'évaluateur isolé (D7/P4), compose le verdict, appelle l'engine, persiste la transition + artefacts `command_output_*`. 7 tests avec évaluateur mock (jamais de vrai modèle en CI).
- CLI étendu (Lot 4c) : `agentic start <workflow>`, `status <session>`, `resume <session> <state>`, `log <session>` — cycle complet ouvert → exécution → vérification d'intégrité → reprise depuis `blocked` (`session_resumed` ne consomme pas le budget). 6 tests e2e.
- 35 nouveaux tests au total : 163 verts, lint bugfix 0/0.

**Découvertes significatives :**

- `run_evaluator` devait accepter un env d'appoint pour scriptable les verdicts du mock sans casser l'isolation (les clés bloquées restent filtrées).
- Le fixture CLI a révélé que l'engine est sensible aux assertions d'échec par défaut : le mock doit les servir en `fail` par défaut, sinon tout état avec `on_failure` part en `blocked`.
- Le CLI attend un évaluateur injecté via `AGENTIC_EVALUATOR_CMD` — le câblage réel du provider (depuis `providers.yaml`) a été fait après le lot : `src/agentic_suite/providers/model_evaluator.py` + config machine `~/.config/agentic/{providers.yaml,opencode-go.key}`.
- **Smoke test réel validé** : une session `agentic start bugfix` avec l'évaluateur model (deepseek-v4-flash) a produit `retry -> discovery (attempt 1 of 2)` et le journal porte les 3 assertions de discovery jugées `insufficient_evidence` (contexte vide → charge de la preuve sur le worker, conforme ADR 0002). La CI n'appelle jamais un vrai modèle (5 tests mockés).
- **Trou de versionnage corrigé** : `.gitignore` ignorait `.agentic/` en entier — `commands.yaml` du Lot 2 n'a jamais été commité. Exception ajoutée (`!.agentic/commands.yaml`) + `git add -f`.

**Dépendances :** Lots 1, 2, 3.

### Lot 5 — Validation Phase 4 ⬜ (en cours)

**Intention :** le seul lot qui décide si le projet vaut quelque chose.

**Tâches principales :**

1. Dix sessions bugfix sur de vrais bugs, non choisis pour arranger le workflow.
2. Provoquer les sept scénarios de validation des ADR 0002 et 0003.
3. Mesurer le ratio de champs sortis inconnus (signal de découverte-formulaire).
4. Mesurer les refus par type (un refus jamais déclenché est un mécanisme mort).

**Dépendances :** Lot 4, acteur model (Lot 5.0), boucle run_session (Lot 5.1),
`agentic run` (Lot 5.2).

**Découvertes en cours :**

- **D5.1 — L'évaluateur ne voyait pas le contexte.** `run_evaluator` copiait
  uniquement `session.jsonl` dans le scratch ; les assertions citant
  `context.<id>` étaient jugées `insufficient_evidence` quoi qu'il arrive →
  discovery → blocked. Corrigé : `run_evaluator(session_dir=...)` copie aussi
  `context.json` + `artifacts/` (le contexte ET les artefacts SONT l'enregistrement
  de session, ADR 0001 — la conversation de travail reste exclue, D9 intact).
  **La première session réelle a révélé ce bug mieux que tout test unitaire.**
- **D5.2 — L'acteur refuse d'inventer.** Sans rapport initial semé, l'acteur LLM a
  marqué les 8 champs required de discovery comme `{"_unknown": true, _reason: "doit
  être collecté auprès de l'utilisateur"}` → le check discovery_context_present
  (max_unknown: 2) échoue → blocked. Comportement **exactement** conforme à
  l'ADR 0003 D1 et à l'ADR 0002 (« ne pas deviner »). `agentic run --context <file>`
  ajouté pour semer le rapport initial, comme le ferait un utilisateur.
- **D5.3 — Première session complète observée (bug réel de `scratch/sizes.py`).**
  `agentic run bugfix --context rapport.json` : discovery → investigation avec un
  **diagnostic LLM correct** (« la branche binary=False ne convertit pas »), contexte
  investigation complet — puis blocked sur investigation. Le mécanisme tourne de bout
  en bout ; le blocage vient d'un verdict évaluateur défavorable (faux négatif probable
  sur `root_cause_is_identified`, ou faux positif de `no_root_cause_found`). **F.4
  demande précisément de compter ces cas** ; la session #1 les a produits.
- **D5.4 — Faux positifs du juge sur les assertions C2 (mesure F.4, session #1).**
  Rejeu ciblé de l'évaluateur sur la session #1 avec les 3 assertions investigation +
  4 escalades : `root_cause_is_identified` → **pass** (bon) ; `no_root_cause_found` →
  fail (bon) ; escalades → `insufficient_evidence` (bon) ; mais
  **`required_context_is_missing` → pass à tort** : le contexte investigation est
  complet (`evidence_examined`, `root_cause_hypothesis`, `confidence_rationale` tous
  présents, `diagnosis.json` correct) et rien ne manque. Le juge LLM est
  **non-déterministe** : la volée et le rejeu divergent. **Un pass sur une assertion
  d'échec C2 envoie une session saine en blocked/discovery** — c'est le refus le plus
  coûteux à tort. À mesurer sur les sessions suivantes (variance) avant toute
  correction du prompt.
- **D5.6 — Cause racine du faux positif C2 : le juge ne recevait que les ids des
  critères.** `runner.py` envoyait `{"id", "kind"}` — ni description, ni
  `evidence_from`, ni la polarité C2. Le LLM inférait du nom de l'assertion
  (`required_context_is_missing…`) au lieu de constater les faits. Correction :
  chaque critère porte désormais le contrat complet (`description`,
  `evidence_from`, `nature: nominal|failure|escalation` — la nature *failure* est
  dérivée structurellement des `on_failure[].when`, pas d'un commentaire) et le
  prompt impose une **preuve asymétrique** : une assertion d'échec ne passe que sur
  constat factuel direct dans l'enregistrement, jamais par plausibilité du nom.
  Test verrouillé : `tests/session/test_C2_polarity_contract.py`. Effet secondaire
  à surveiller : juge plus strict, risque de faux négatifs sur les nominales.
- **D5.7 — Timeouts réseau tués par le subprocess.** `run_evaluator(timeout_s=60)`
  tuait le juge avant ses 3 retries LLM (120 s chacun) → `{"_error"}` → `fail` sur
  tout → blocked. Les flocons `httpx.ReadTimeout` n'étaient pas retentés (classe
  `Exception`, hors du catch). Corrections : appel LLM 90 s × 3 retries + catch
  large + subprocess 300 s (évaluateur et acteur). Sans ce fix, la correction C2
  était inmesurable.
- **D5.9 — Le runtime n'applique pas le patch → validation structurellement
  fausse.** La chaîne discovery → investigation → fix fonctionne (diagnostic
  LLM correct, verdicts C2 justes), mais l'état validation exécute
  `run_tests`/`run_lint` sur un arbre **inchangé** : l'acteur produit un
  artefact `patch`, personne ne l'applique. `unit_tests_pass` échoue donc
  toujours, le juge passe `validation_cannot_be_completed` à juste titre → tout
  se termine en blocked. Résolu par **ADR 0009** (check `artifact_applied`,
  4e type — D3 amendé) : le runtime matérialise le diff et l'exécute
  (`command_ref apply_patch`, cwd = project_root) **avant** les checks de
  validation. Prouvé e2e sur un vrai repo git (3 tests). À rejouer en session
  réelle quand l'API est stable (flocons réseau acteurs ce soir).
- **D5.8 — Correction C2 validée par session réelle (bugfix-dc3b8a49).** Avant la
  correction (sessions #1/#2) : blocked sur investigation, `required_context_is_missing`
  jugé pass à tort. Après : **discovery → investigation → fix**, avec des verdicts
  justes : `context_is_sufficient_to_investigate` pass, `required_context_is_missing`
  fail, `no_root_cause_found` fail, `root_cause_is_identified` pass, escalades fail.
  La session a atteint l'état fix — du jamais vu jusqu'ici. Le blockage final est un
  **échec réseau de l'acteur** (`evaluator: "actor"` dans le journal, 3 ReadTimeout en
  produisant le patch), pas un verdict du juge. Le juge corrigé est maintenant
  mesurable et ne bloque plus les sessions saines.

**Risque majeur :** choisir des bugs faciles pour faire passer les scénarios. Les bugs viennent du travail réel en cours, pas d'une liste établie pour le plan.

### Lot 6 — Interface ✅

**Intention :** rendre le système utilisable sans mémoriser le CLI.

**Réalisé :**
- `agentic` sans sous-commande ouvre un **menu interactif** (stdlib pur, aucune
  dépendance ajoutée — typer/rich de M0 différés, règle « 3 usages réels ») :
  liste les workflows (`workflows/v<N>/`) et les sessions (`sessions/`) avec
  état courant et intégrité du journal ; actions numérotées : workflow → `run`
  (boucle complète), session → reprendre / journal ; `0` quitte.
- `src/agentic_suite/ui.py` — `build_menu`, `render_menu`, `action_from_menu`
  purs et testés (marker `ui` déclaré) ; sessions corrompues marquées
  `[journal invalide]`, jamais fatales au menu.
- `cmd_menu` injecte `_prompt_action(input_fn=...)` — testable sans stdin réel.
- Architecture verrouillée par test : `ui` dans la liste PRESENT, cli.md
  documente le menu (le titre `agentic` sans mot-clé échappe au regex des
  sous-commandes, la liste reste stricte).
- 228 tests verts ; lint bugfix+feature 0/0.

**Découverte (constat) :** les 10 sessions de validation réelles (Lot 5)
s'accumulent dans le menu sans filtre. Une page/`--latest` attendra qu'une
session en termine (R2 : pas d'abstraction avant un besoin répété).

### Lot 7 — Deuxième workflow ✅

**Intention :** vérifier que le schéma généralise.

**Réalisé via le Lot F** (`docs/planning/plan-execution-feature.md`) : `feature.yaml` v1
écrit et lint-clean 0/0 ; 5 prédictions de lint enregistrées **avant** l'exécution et
vérifiées ; R10 généralisée (aucun nom d'état codé) ; R11/R12 refusent les booléens ;
`LintError` mort supprimé ; marqueur `{"_unknown": true, "_reason": ...}` ratifié par
précision ADR ; C1-C4 ratifiées.

**Condition d'entrée stricte :** dix sessions bugfix terminées et le Lot 5 clos.

## Chemin critique

```
Lot 0 (✅) → Lot 1 (✅) → Lot 2 (✅) → Lot 3 (✅) → Lot 4 (✅) → Lot 5
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