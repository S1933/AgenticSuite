# Référence CLI

La commande `agentic` est installée par le point d'entrée `agentic_suite.cli:main` déclaré
dans `pyproject.toml`.

```bash
pip install -e .
agentic --version        # agentic 0.0.1.dev0
agentic --help
```

**Périmètre actuel (Lots 0-4) : `lint`, `start`, `status`, `resume`, `log` sont
implémentés.** Le README citait `run` à titre d'interface visée ; le nommage retenu est
`start` (ouvrir et exécuter une session). Liste figée par le test
`tests/e2e/test_architecture_doc.py` (les sous-commandes documentées ici doivent exister
dans le CLI).

---

## `agentic lint`

Valide une définition de workflow contre le schéma (ADR 0003 et suivantes).

```bash
agentic lint <workflow.yaml> [--strict]
```

| Argument | Rôle |
|---|---|
| `workflow` | Chemin du fichier YAML à valider (positionnel, obligatoire) |
| `--strict` | Traite les avertissements comme des erreurs |

### Sortie

Aucun problème :

```
$ agentic lint workflows/v1/bugfix.yaml
ok: workflows/v1/bugfix.yaml passes lint with 0 errors and 0 warnings
```

Problèmes détectés — une ligne par constat, sur `stdout`, dans l'ordre des règles de
`ALL_RULES` :

```
$ agentic lint workflows/v1/broken.yaml
[error] R20 at initial_state: initial_state 'triage' must match a declared state id
[warning] R3 at states.fix: state has assertions but no checks — verify none of the conditions could be reduced to a check
```

Erreur de chargement — sur `stderr` :

```
$ agentic lint workflows/v1/absent.yaml
error: cannot read workflow file 'workflows/v1/absent.yaml': [Errno 2] No such file or directory: ...
```

### Codes de sortie

| Code | Signification |
|---|---|
| `0` | Aucune erreur. Des avertissements peuvent être affichés (sauf si `--strict`) |
| `1` | Au moins une erreur, ou au moins un avertissement avec `--strict` |
| `2` | Échec de chargement : fichier illisible, YAML malformé, racine non-mapping. Aucune règle n'a tourné |

La distinction entre 1 et 2 est utile en CI : un `2` signale un problème de fichier ou de
chemin, pas un workflow invalide.

### Chargement vs lint

`load_workflow` (`src/agentic_suite/loader.py`) ne fait que trois choses : lire le fichier,
parser le YAML avec `yaml.safe_load`, vérifier que la racine est un mapping. Tout le reste
est du lint.

Conséquence : un fichier vide, une liste au premier niveau ou un YAML cassé produisent un
code 2 sans message de règle. Un fichier syntaxiquement valide mais sémantiquement vide
(`{}`) est chargé, puis linté — et échoue sur R20.

---

## `agentic start <workflow>`

Ouvre une session et exécute une tentative de l'état initial. L'évaluateur est injecté via `AGENTIC_EVALUATOR_CMD` (adapter model réel ou mock).

```bash
agentic start bugfix
# session bugfix-<id>
# transition: retry -> discovery (attempt 1 of 2)
```

## `agentic status <session>`

Affiche l'état courant et vérifie l'intégrité du journal (ADR 0004 D4). Code 3 si la session est corrompue.

## `agentic resume <session> <state>`

Reprend une session depuis `blocked` via un bloc `session_resumed` (ne consomme pas le budget).

## `agentic log <session>`

Affiche le journal bloc par bloc, avec les marqueurs `[INVALID]` (invalidation a posteriori, ADR 0004 D5).

---

## Utilisation en CI

Le workflow GitHub Actions (`.github/workflows/ci.yml`) exécute la suite de tests puis
lint la définition de référence, sur Python 3.11, 3.12 et 3.13 :

```yaml
- name: Run pytest
  run: pytest --strict-markers --tb=short

- name: Lint bugfix.yaml
  run: agentic lint workflows/v1/bugfix.yaml
```

`bugfix.yaml` est maintenu à zéro erreur **et** zéro avertissement ; le test
`tests/e2e/test_bugfix_lints_clean.py` verrouille cet état. Ajouter `--strict` à l'étape de
CI ne changerait donc rien aujourd'hui, mais protégerait contre une régression future en
avertissement.

---

## Usage programmatique

Les mêmes opérations sont accessibles depuis Python sans passer par la CLI :

```python
from agentic_suite.loader import LoadError, load_workflow
from agentic_suite.lint import engine

try:
    wf = load_workflow("workflows/v1/bugfix.yaml")
except LoadError as e:
    ...

messages = engine.lint(wf)          # list[LintMessage], ordre des règles
if engine.has_errors(messages):
    for m in messages:
        print(m.rule_id, m.severity, m.path, m.message)
```

`LintMessage` est une dataclass gelée à quatre champs — `rule_id`, `severity`, `path`,
`message` — dont le `__str__` produit la ligne affichée par la CLI. Voir
[l'architecture](../architecture.md) pour les frontières entre modules.

---

## Voir aussi

- [Catalogue des règles de lint](lint-rules.md)
- [Référence du schéma de workflow](workflow-schema.md)
- [Guide de développement](../development.md)
