# Architecture technique

Description du code livré dans `src/agentic_suite/`, de ses frontières et de ce qui n'est
pas encore écrit. Pour le *pourquoi* des décisions, voir [`philosophy.md`](philosophy.md)
et les [ADR](adr/). Pour le vocabulaire, [`concepts.md`](concepts.md).

État au moment de la rédaction : **Lots 0 à 4 terminés** — linter (19 règles),
session journal JSONL chaîné, isolation évaluateur (invariant D9), résolution
`command_ref` et rôles → fournisseurs (ADR 0005), skills (ADR 0006), engine pur,
orchestrateur `run_attempt` et CLI `start/status/resume/log`. L'évaluateur model
réel (opencode-go) est branché via `AGENTIC_EVALUATOR_CMD` ; les sessions de
validation sur cas réels n'existent pas encore (Lot 5).

---

## 1. Vue d'ensemble

```
                 workflows/v1/bugfix.yaml
                            │
                            ▼
                    ┌───────────────┐
                    │  loader.py    │  lecture + YAML → dict
                    └───────┬───────┘  LoadError si illisible/malformé
                            │ dict
                            ▼
        ┌───────────────────────────────────────┐
        │           lint/engine.py              │
        │  lint(wf) → list[LintMessage]         │
        │      itère ALL_RULES dans l'ordre     │
        └───────────────────┬───────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
       lint/rules.py                lint/__init__.py
     18 règles pures            LintMessage, error(), warning()
              │
              ▼
        ┌───────────────┐
        │    cli.py     │  agrégation, affichage, code de sortie
        └───────────────┘


   ┌──────────────────────────────────────────────────────────┐
   │  verification/checks.py — pures, appelées par personne    │
   │  check_context_fields_present · check_artifact_exists     │
   │  check_command_exit_zero                                  │
   │  ↑ attend le runtime de la Phase 2 (Lot 4)                │
   └──────────────────────────────────────────────────────────┘
```

Deux chaînes existent aujourd'hui. La première — chargement, lint, affichage — est
complète et exercée par la CLI. La seconde — les fonctions de vérification — est écrite,
testée, et **n'a aucun appelant** : elle attend la boucle d'exécution.

---

## 2. Modules

### `agentic_suite/__init__.py`

Ne contient que `__version__ = "0.0.1.dev0"`, lu par `agentic --version`. Aucun import
transitif : importer le paquet ne charge ni PyYAML ni les règles.

### `agentic_suite/loader.py` — 47 lignes

```python
class LoadError(Exception): ...
def load_workflow(path: str | Path) -> dict: ...
```

Trois responsabilités, pas une de plus : lire le fichier en UTF-8, parser avec
`yaml.safe_load`, vérifier que la racine est un mapping. Les trois modes d'échec
(`OSError`, `yaml.YAMLError`, racine non-dict) sont convertis en `LoadError` avec un
message explicite.

Cette frontière est délibérée : **le chargeur ne connaît pas le schéma**. Un fichier YAML
vide de sens mais syntaxiquement correct est chargé sans broncher, puis rejeté par le
linter. C'est ce qui permet aux règles de recevoir toujours un `dict`, et donc de rester
des fonctions pures sans I/O.

`yaml.safe_load` et non `yaml.load` : pas d'instanciation d'objets Python arbitraires
depuis un fichier de workflow.

### `agentic_suite/lint/__init__.py` — 32 lignes

Le vocabulaire du linter.

```python
@dataclass(frozen=True)
class LintMessage:
    rule_id: str    # "R4"
    severity: str   # "error" | "warning"
    path: str       # "states.discovery.checks[0].command_ref"
    message: str
```

`__str__` produit `[severity] rule_id at path: message`, format unique affiché par la CLI.
Les constructeurs `error(...)` et `warning(...)` évitent de répéter `severity=` dans 18
fichiers de règles.

`LintError` est déclarée mais n'est levée nulle part : une règle qui ne peut pas conclure
n'échoue pas, elle n'émet rien. À supprimer ou à utiliser.

### `agentic_suite/lint/rules.py` — 476 lignes

Le cœur. Chaque règle est un **générateur pur** :

```python
def rule_R5_check_type_closed(workflow: dict) -> Iterable[LintMessage]:
    """ADR 0003 D3: check.type must be in the closed set."""
```

Quatre conventions tiennent le fichier :

1. **Docstring = référence d'ADR.** Chaque règle cite le paragraphe qu'elle fait respecter.
   Une règle sans ADR est un avis de style et n'a rien à faire ici.
2. **Tolérance aux structures malformées.** Chaque niveau vérifie `isinstance` avant de
   descendre. `_iter_states` ignore silencieusement une entrée qui n'est pas un dict avec
   un `id` string. Une règle ne lève jamais sur un YAML tordu : elle n'émet rien, et une
   autre règle signalera le vrai problème.
3. **Ensembles fermés en constantes de module.** `ALLOWED_CHECK_TYPES`, `ALLOWED_KINDS`,
   `ALLOWED_ROLES`, `COMMAND_REF_RE`, `POLARITY_NEGATION_RE` — un seul endroit à modifier
   quand une ADR élargit un vocabulaire, et les tests peuvent importer la constante plutôt
   que de dupliquer la liste.
4. **Helpers partagés** : `_iter_states`, `_assertions_by_id`, `_is_terminal`.

`ALL_RULES` en fin de fichier est le registre. L'ordre de cette liste est l'ordre
d'affichage des messages.

R21 est la seule règle non locale : elle construit le graphe de transitions
(`next` + `on_failure[].to`) et calcule l'atteignabilité par parcours en profondeur, une
fois par état cité. C'est du O(N·E) assumé pour la v0 — un workflow a une dizaine d'états.

### `agentic_suite/lint/engine.py` — 24 lignes

```python
def lint(workflow: dict) -> list[LintMessage]      # concatène ALL_RULES
def has_errors(messages) -> bool                   # any severity == "error"
```

Aucune logique propre : le moteur ne trie pas, ne dédoublonne pas, ne s'arrête pas à la
première erreur. Ajouter une règle ne demande jamais de toucher au moteur.

### `agentic_suite/verification/checks.py` — 100 lignes

Les trois types de vérification de l'ADR 0003 D3, en fonctions pures retournant
`CheckResult(passed: bool, detail: str)`.

```python
check_context_fields_present(definition: dict, context: dict) -> CheckResult
check_artifact_exists(definition: dict, artifacts: dict) -> CheckResult
check_command_exit_zero(definition: dict, command_output: dict | None) -> CheckResult
```

**Aucune I/O.** C'est l'invariant du module, répété dans les deux docstrings. Le runtime —
quand il existera — chargera le contexte, les artefacts, résoudra `command_ref` en argv,
exécutera le sous-processus, puis passera le résultat ici. La décision *passe / ne passe
pas* reste testable sans système de fichiers, sans processus, sans agent.

`check_command_exit_zero` reçoit `None` quand le `command_ref` n'a pas pu être résolu et
retourne `CheckResult(False, "command_ref unresolved")` — c'est le comportement annoncé par
l'ADR 0005 D5 côté schéma.

Trois notions d'« inconnu » sont acceptées par `check_context_fields_present` : valeur
`None`, chaîne vide, ou dict portant `{"_unknown": True}`. Cette dernière est la marque
d'inconnu documenté de l'ADR 0003 D1 ; c'est aussi le seul endroit du code où elle apparaît,
et elle n'est décrite par aucune ADR — un point à ratifier.

### `agentic_suite/session.py` — journal de session (ADR 0004)

Journal JSONL **append-only** par session. Chaque bloc porte le SHA-256 du bloc
précédent (`prev_hash`) : toute modification rétroactive casse la chaîne entière.
Le hash d'un bloc est calculé sur la représentation canonique (clés triées,
séparateurs compacts) **avant** insertion de `prev_hash`/`hash` (D3).

```python
canonical_bytes(obj) -> bytes            # JSON compact, clés triées
block_hash(block) -> str                 # SHA-256 hors prev_hash/hash
new_session(path, to_state, workflow_version) -> dict   # seq 0, prev_hash = 64 zéros
append_block(path, block) -> dict        # chaîne sur le dernier bloc
load_journal(path) -> list[dict]         # vérifie la chaîne, lève SessionIntegrityViolation
count_budget_transitions(blocks) -> int  # exclut session_resumed (D8)
```

`load_journal` refuse : hash mismatch, `prev_hash` brisé, trou de `seq`,
ligne JSON tronquée (D4). Aucune réparation automatique — la session passe à
`blocked` chez l'appelant. L'invalidation a posteriori (D5 / ADR 0003 D8.1)
marque `_invalid` les transitions dont `evidence` cite un artefact ensuite
écrasé.

### `agentic_suite/evaluator.py` — isolation de l'évaluateur (ADR 0003 D9)

L'évaluateur est un **sous-processus à contexte frais** : il reçoit une copie du
journal dans un répertoire scratch vide, un environnement minimal (PATH seul),
et les critères sur stdin. Le vrai répertoire de session, ses artefacts et la
conversation de travail sont physiquement inaccessibles (Lot 1.3).

```python
run_evaluator(session_path, criteria, command, timeout_s) -> EvaluationResult
verify_verdict_grounded(result, journal) -> list[str]   # violations D9
```

`verify_verdict_grounded` implémente l'invariant D9 sémantique : toute preuve
citée par un verdict doit exister dans l'enregistrement de session. Une preuve
absente est une violation — l'évaluateur n'a pu l'obtenir que de la
conversation de travail, ce que D9 interdit. C'est le test demandé par
l'ADR 0003 D9 (« le premier test de bout en bout de la Phase 4 vérifie cet
invariant »), rendu exécutable dès maintenant avec l'évaluateur mock.

### `agentic_suite/commands.py` — résolution `command_ref` (ADR 0005 D5)

Hiérarchie projet → machine : `.agentic/commands.yaml` (projet) prime sur
`~/.config/agentic/commands.yaml` (machine). Définition = liste `argv` —
jamais une chaîne shell, jamais de template ni de substitution. Un ref non
résolu retourne `None` : le check échoue à l'exécution
(`command_ref_unresolved`), jamais à la lecture.

```python
resolve_command_ref(project_root, ref, machine_home=None) -> dict | None
# -> {"argv": [...], "timeout_seconds": int, "cwd": str | None}
```

Définition présente mais malformée (pas d'`argv`, argv non-liste,
`timeout_seconds` invalide) → `CommandRefError`.

### `agentic_suite/providers/` — package fournisseurs (ADR 0005 D1-D4, D3)

`base.py` — rôles fermés (`actor`, `evaluator`), capacités implicites figées (D2).
Fournisseurs déclarés dans `config/providers.yaml` (machine), `kind` fermé
(`model | cli | api`). La résolution rôle → fournisseur se fait via
`role_assignments.yaml` (machine, non overridable par projet).

```python
resolve_role_provider(role, config_home) -> dict   # le provider résolu
# errors: RoleAssignmentMissing | ProviderLoadError | ProviderCapabilityError
```

Un fournisseur ne peut servir un rôle que si ses capacités couvrent les
capacités requises du rôle : `evaluator_cli` (lecture seule) ne peut pas
tenir `actor` (`code_editing`, `tool_execution` requis).

`model_evaluator.py` — le judge model réel (ADR 0003 D9), invoqué en
sous-processus par le runner via `AGENTIC_EVALUATOR_CMD`. Clé lue depuis
`~/.config/agentic/providers.yaml` (`api_key_file`), jamais par env
(l'isolation les strippe). Retry sur JSON malformé, échec dur après N.

### `agentic_suite/skills.py` — invocation de skills (ADR 0006 D4/D5)

L'invocation d'une skill est un bloc journal typé `skill_invoked`
(`skill_id`, `state_id`, `role`, résumés ≤ 200 chars), chaîné par
l'empreinte ADR 0004 comme n'importe quel bloc. Une skill ne peut pas
écrire en session (D2) ; elle retourne du contenu à l'acteur.

```python
record_skill_invocation(journal_path, skill_id, state_id, role,
                        input_summary, output_summary) -> dict
undeclared_skill_ids(journal, declared_skills) -> list[str]  # warning D5
```

### `agentic_suite/engine.py` — machine à états pure (Lot 4a)

`advance(ctx, verdict) -> Transition` sans I/O — le cœur décisionnel :
escalade d'abord (D7), puis assertions d'échec dans l'ordre (C2), puis
sortie nominale, puis retry/budget. `max_transitions` (D6) et
`max_attempts` forcent `blocked` ; `session_resumed` ne consomme pas le
budget (D8).

```python
advance({"workflow": wf, "state_id": s, "attempt": n,
         "transitions_used": m}, verdict) -> Transition(kind, to, reason)
```

### `agentic_suite/runner.py` — orchestrateur (Lot 4b)

`run_attempt` assemble tout : journal vérifié (D4) → état courant →
checks déterministes (avec résolution `command_ref` ADR 0005) →
évaluateur isolé (assertions + triggers d'escalade, D7/P4) → engine →
persistance de la transition et des artefacts `command_output_*`.

```python
run_attempt(session_path, session_dir, workflow, evaluator_cmd,
            evaluator_env=None, project_root=None, machine_home=None)
            -> RunResult(transition, journal)
```

Le CLI (`agentic start|status|resume|log`) branche l'orchestrateur ; un
évaluateur est injecté via `AGENTIC_EVALUATOR_CMD`. L'adapter réel :
`providers/model_evaluator.py` (separate-process judge, clé lue depuis
`~/.config/agentic/providers.yaml` — jamais par env, que l'isolation
strippe). `providers/base.py` porte la résolution rôle → fournisseur ;
`providers/__init__.py` ré-exporte pour la compat.

### `agentic_suite/session_loop.py` — boucle de session (Lot 5.1)

`run_session` exécute le workflow complet : acteur → persistance du travail
(contexte + artefacts hashés, ADR 0004 D6) → checks → évaluateur → engine →
transition, jusqu'à un état terminal, `blocked`, ou le budget/bornes.

```python
run_session(session_path, session_dir, workflow, actor_cmd, evaluator_cmd,
            actor_env=None, evaluator_env=None, project_root=None,
            machine_home=None, max_steps=40) -> SessionResult
```

L'acteur est aussi injecté : `providers/model_actor.py` (worker, produit
`{context, artifacts}` depuis le contrat d'état + snapshot lecture seule du
projet). Jamais de vrai modèle en CI (mocks scriptés).

### `agentic_suite/cli.py` — 68 lignes

`argparse`, une sous-commande, trois codes de sortie. Voir la [référence CLI](reference/cli.md).

`cmd_lint` est séparée de `main` pour être appelable depuis les tests sans construire
d'`argv`.

---

## 3. Frontières et invariants

Trois séparations structurent le code. Les casser reviendrait à défaire ce que les ADR
protègent.

| Frontière | Ce qu'elle garantit |
|---|---|
| **loader ⟂ schéma** | Le chargeur ignore le schéma ; les règles reçoivent toujours un `dict`. Une erreur de fichier (code 2) ne se confond jamais avec un workflow invalide (code 1) |
| **règles ⟂ I/O** | Une règle est une fonction pure `dict → messages`. Testable sans fichier, sans mock |
| **checks ⟂ exécution** | Les fonctions de vérification ne lisent pas, n'exécutent pas. Le runtime fournit les faits, elles jugent |

Un quatrième invariant est **structurel et non exprimable dans le code actuel** :
l'évaluateur opère exclusivement sur l'enregistrement de session, à l'exclusion de la
conversation de travail qui a produit l'état (ADR 0003 D9). Rien dans `src/` ne le fait
respecter aujourd'hui, parce qu'il n'y a ni session ni agent. L'ADR exige que le premier
test de bout en bout de la Phase 4 le vérifie, et considère la qualification « workflow
validé » comme invalide sans lui.

---

## 4. Ce qui n'existe pas

Ce que les ADR spécifient et que le code ne contient pas. Utile pour ne pas chercher un
module absent. La cohérence de cette liste avec le code est **verrouillée par le test
`tests/e2e/test_architecture_doc.py`** : chaque module déclaré absent ici doit lever
`ImportError`, et les sous-commandes documentées dans `reference/cli.md` doivent
correspondre aux sous-commandes réelles du CLI.

| Absent | Spécifié par | Prévu |
|---|---|---|
| Validation de schéma formelle au chargement (`pydantic`/`jsonschema` ou équivalent) — le loader lit, le lint valide | — | hors périmètre (les règles citent les ADR, un validateur générique perdurait le message) |
| Adaptateur `cli` réel pour un fournisseur `kind: cli` (agent non-LLM) — `agentic_suite.providers.cli` | ADR 0005 D3 | Lot 5 si besoin |
| Adaptateur `api` réel pour un fournisseur `kind: api` — `agentic_suite.providers.api` | ADR 0005 D3 | Lot 5 si besoin |
| Deuxième workflow (`feature` ou autre) — `workflows/v1/feature.yaml` | Lot 7 du plan | en cours (Lot F) |
| État de livraison (commit, PR, changelog) — le workflow s'arrête à `done` — `agentic_suite.release` | hors périmètre du v1 | ADR devant précéder |
| Gate humaine obligatoire comme primitive de schéma | friction constatée sur feature | ADR 0008 conditionnelle (Lot F.5) |

Les dossiers `agents/`, `commands/`, `hooks/` annoncés dans la version initiale du README
n'existent pas : ils seront créés quand un lot en aura besoin — la règle du projet étant de
n'introduire une abstraction qu'après trois usages réels qui la réclament. `config/`
existe (référence portable) et `workflows/v1/` contient `bugfix.yaml`.

---

## 5. Dépendances

| Dépendance | Usage |
|---|---|
| `pyyaml >= 6.0` | Unique dépendance d'exécution, utilisée uniquement dans `loader.py` |
| `pytest >= 8.0`, `pytest-cov >= 4.1` | Extra `test` |

Python ≥ 3.11 (`X | Y` dans les annotations, `from __future__ import annotations` partout
malgré tout). CI sur 3.11, 3.12, 3.13.

Aucun framework de validation de schéma (`pydantic`, `jsonschema`) : les règles sont
écrites à la main parce que chacune doit citer une ADR et produire un message qui explique
*pourquoi* la contrainte existe, pas seulement qu'elle est violée. Un validateur générique
produirait « `type` is not one of [...] » là où R5 explique la règle de fermeture.

---

## 6. Points de tension connus

À traiter, listés ici pour qu'ils ne se perdent pas.

- **`concepts.md` porte un exemple YAML obsolète**, signalé en tête de fichier
  (`exit_when:` remplacé par `checks:`/`assertions:`), et un `evaluated_by: investigator`
  non conforme à l'ADR 0003 D9.
- **ALLOWED_KINDS** : l'ensemble fermé de D8 est déclaré dans `rules.py` ; son contenu
  n'a été exercé que par `bugfix.yaml` (diagnosis, repro, patch, test_result, decision,
  note). `feature.yaml` n'utilise que note, decision, patch, test_result — aucun kind
  nouveau. Un quatrième workflow vérifiera l'ensemble plus largement.

Résolus (Lot F) :
- R10 (noms d'états codés en dur) généralisé — un terminal local cible d'un `on_failure`
  n'est atteignable que depuis `initial_state`.
- `LintError` (classe morte) supprimée.
- `isinstance(x, int)` acceptait les booléens dans R11/R12 — corrigé (`_is_positive_int`).
- `{"_unknown": True}` était une convention sans ADR — ratifiée (précision ADR) et
  renforcée : `_reason` non vide obligatoire.

---

## Voir aussi

- [Référence du schéma de workflow](reference/workflow-schema.md)
- [Catalogue des règles de lint](reference/lint-rules.md)
- [Référence CLI](reference/cli.md)
- [Guide de développement](development.md)
- [Plan d'exécution par lots](planning/plan-execution.md)
