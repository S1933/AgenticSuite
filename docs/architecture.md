# Architecture technique

Description du code livré dans `src/agentic_suite/`, de ses frontières et de ce qui n'est
pas encore écrit. Pour le *pourquoi* des décisions, voir [`philosophy.md`](philosophy.md)
et les [ADR](adr/). Pour le vocabulaire, [`concepts.md`](concepts.md).

État au moment de la rédaction : **Lot 0 terminé** — un linter de workflows et trois
fonctions de vérification pures. **Lot 1 partiel** — `session.py` (journal JSONL chaîné,
intégrité, budget) et `evaluator.py` (isolation de processus, invariant D9) sont écrits et
testés ; le runtime qui les appelle n'existe pas encore. L'intégration des agents n'existe pas.

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
module absent.

| Absent | Spécifié par | Prévu |
|---|---|---|
| Runtime : machine à états, boucle de transitions, budgets | ADR 0002, 0003 D6 | Lot 4 |
| Persistance de session : journal chaîné par hash, intégrité, invalidation a posteriori | ADR 0004 | Lot 4 |
| Résolution `command_ref` → argv (`commands.yaml` projet puis machine) | ADR 0005 D5 | Lot 2 |
| Configuration des rôles et fournisseurs (`config/role_assignments.yaml`, `config/providers.yaml`) | ADR 0005 D3-D4 | Lot 2 |
| Invocation de skills, événement `skill_invoked` | ADR 0006 | Lot 3 |
| Sous-commandes `run`, `resume`, `log` | README | Phase 2 |
| Snapshot des artefacts par transition | ADR 0003 D8, 0004 D5 | Lot 4 |
| Validation de schéma au chargement (`id`, `version`, `states` requis) | — | Lot 1 |

Les dossiers `workflows/`, `agents/`, `providers/`, `commands/`, `hooks/`, `config/`
annoncés dans la version initiale du README n'existent pas non plus, à l'exception de
`workflows/`. Ils seront créés quand un lot en aura besoin — la règle du projet étant de
n'introduire une abstraction qu'après trois usages réels qui la réclament.

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

- **R10 code en dur un nom d'état de `bugfix`** (`reclassified`, `discovery`). Le linter
  est censé être générique ; il ne l'est pas tout à fait. À généraliser avant le second
  workflow (Lot 7).
- **`LintError` n'est jamais levée.** Code mort.
- **`isinstance(x, int)` accepte les booléens** dans R11 et R12 : `max_attempts: true`
  passe la validation.
- **`verification/checks.py` n'a aucun appelant.** Le module est correct et testé, mais son
  contrat réel — la forme exacte du `definition` et du `context` que le runtime passera —
  ne sera confirmé qu'au Lot 4.
- **`{"_unknown": True}`** est une convention de code sans ADR.
- **`concepts.md` porte un exemple YAML obsolète**, signalé en tête de fichier
  (`exit_when:` remplacé par `checks:`/`assertions:`), et un `evaluated_by: investigator`
  non conforme à l'ADR 0003 D9.

---

## Voir aussi

- [Référence du schéma de workflow](reference/workflow-schema.md)
- [Catalogue des règles de lint](reference/lint-rules.md)
- [Référence CLI](reference/cli.md)
- [Guide de développement](development.md)
- [Plan d'exécution par lots](planning/plan-execution.md)
