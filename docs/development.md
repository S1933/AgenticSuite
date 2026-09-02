# Guide de développement

Comment installer, tester, et modifier Agentic Suite.

---

## Installation

Python ≥ 3.11.

```bash
git clone https://github.com/S1933/AgenticSuite.git
cd AgenticSuite

python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate

pip install -e ".[test]"
```

Vérification :

```bash
agentic --version                                # agentic 0.0.1.dev0
agentic lint workflows/v1/bugfix.yaml            # ok: ... 0 errors and 0 warnings
pytest -q                                        # 95 passed
```

Une seule dépendance d'exécution : `pyyaml`. L'extra `test` ajoute `pytest` et
`pytest-cov`.

---

## Tests

```bash
pytest                          # tout
pytest -m lint_rule             # règles de lint
pytest -m verification          # types de vérification
pytest -m refusal               # refus de schéma
pytest -m e2e                   # bout en bout
pytest tests/lint/test_R21_context_attainable.py -v
pytest --cov=agentic_suite --cov-report=term-missing
```

Marqueurs déclarés dans `pyproject.toml`, `--strict-markers` actif : un marqueur non
déclaré fait échouer la collecte.

| Marqueur | Portée |
|---|---|
| `lint_rule` | Règles individuelles (ADR 0003) |
| `verification` | Types de vérification (ADR 0003 D3) |
| `refusal` | Cas que le schéma doit rejeter |
| `e2e` | Bout en bout, dont « `bugfix.yaml` lint proprement » |

`filterwarnings = ["error", ...]` : tout avertissement Python devient une erreur, sauf les
`DeprecationWarning` de PyYAML. Un `DeprecationWarning` introduit par une modification fait
donc échouer la suite — c'est voulu.

### Organisation

```
tests/
├── conftest.py                     # minimal_workflow(), by_path()
├── lint/          test_R<n>_*.py    un fichier par règle ou paire de règles
├── verification/  test_<check>.py   un fichier par type de vérification
├── refusal/       test_refusals.py
└── e2e/           test_bugfix_lints_clean.py
```

`conftest.minimal_workflow(**overrides)` retourne un workflow **valide au regard des 18
règles**. Un test provoque une violation en surchargeant un champ, et vérifie que la règle
visée — et elle seule — se déclenche.

```python
from tests.conftest import minimal_workflow
from agentic_suite.lint import engine

def test_R5_rejects_unknown_check_type():
    wf = minimal_workflow()
    wf["states"][0]["checks"][0]["type"] = "http_200"
    messages = engine.lint(wf)
    assert any(m.rule_id == "R5" and m.severity == "error" for m in messages)
```

Deux conventions à respecter :

1. **Tester l'identifiant de règle, pas seulement la présence d'une erreur.** Un test qui
   vérifie `has_errors(...)` passe encore quand la règle visée disparaît et qu'une autre
   se déclenche par effet de bord.
2. **Tester aussi le cas passant.** Une règle qui refuse tout passe la moitié des tests.

Le test e2e `test_bugfix_lints_clean.py` verrouille `workflows/v1/bugfix.yaml` à zéro
erreur et zéro avertissement. Toucher au workflow de référence ou à une règle le fait
tomber en premier — c'est son rôle.

---

## Ajouter une règle de lint

1. **Trouver le paragraphe d'ADR.** Une règle fait respecter une décision écrite. Sans
   paragraphe à citer, c'est un avis de style : il n'entre pas dans le linter. Si la
   contrainte est justifiée mais non décidée, écrire l'ADR d'abord.

2. **Choisir le numéro.** Prendre le suivant après R21. R18 est pris ; R2 et R19 ne sont
   pas attribués mais restent réservés. Ne jamais réutiliser un numéro : les identifiants
   apparaissent dans les messages et dans l'historique. Voir le
   [catalogue](reference/lint-rules.md).

3. **Écrire le générateur** dans `src/agentic_suite/lint/rules.py` :

```python
def rule_R22_next_target_declared(workflow: dict):
    """ADR 0003 D5: next must reference a declared state."""
    declared = {sid for sid, _ in _iter_states(workflow)}
    for state_id, state in _iter_states(workflow):
        nxt = state.get("next")
        if isinstance(nxt, str) and nxt not in declared:
            yield error(
                "R22",
                f"states.{state_id}.next",
                f"next target '{nxt}' is not a declared state",
            )
```

   Contraintes : générateur, jamais de retour de liste ; aucune I/O ; `isinstance` avant
   chaque descente ; jamais de `raise` sur un YAML tordu ; message qui explique la règle,
   pas seulement la violation.

4. **Enregistrer** dans `ALL_RULES`, à sa place dans l'ordre numérique — c'est l'ordre
   d'affichage.

5. **Constante partagée** si la règle introduit un ensemble fermé : en haut du module, avec
   le commentaire d'ADR, importable par les tests.

6. **Test** dans `tests/lint/test_R22_*.py`, marqué `@pytest.mark.lint_rule`, avec au moins
   un cas passant et un cas refusé.

7. **Documenter** dans [`reference/lint-rules.md`](reference/lint-rules.md) : ligne dans la
   table de synthèse, section détaillée avec exemple. Mettre à jour la colonne « Vérifiée
   par » de [`reference/workflow-schema.md`](reference/workflow-schema.md) si la règle
   comble un trou listé en section 4.

8. **Vérifier `bugfix.yaml`.** `agentic lint workflows/v1/bugfix.yaml` doit rester propre.
   S'il ne l'est pas, soit le workflow de référence est en défaut — le corriger devient
   partie du même changement — soit la règle est trop stricte.

---

## Modifier le workflow de référence

`workflows/v1/bugfix.yaml` n'est pas un exemple : c'est la définition qui sera exécutée en
Phase 4, et le seul cas d'usage réel du schéma.

Avant de le modifier, vérifier dans l'ADR 0003 D10 si le changement est **cassant** —
renommer un id, ajouter un champ requis, resserrer une vérification, changer une cible de
transition, ou modifier le wording d'une `description` en font partie. Un changement
cassant impose un nouveau dossier `workflows/v2/`, jamais une modification sur place, parce
qu'une session en cours est épinglée à la version avec laquelle elle a démarré.

Un point tranché par le workflow mais laissé ouvert par les ADR va dans
[`workflows/v1/DECISIONS.md`](../workflows/v1/DECISIONS.md) comme convention `C<n>`, avec
le problème, la convention retenue, et son statut de ratification. Les conventions C1, C4,
C5 et C6 modifient le schéma et attendent toujours une ADR.

---

## Écrire une ADR

Les ADR sont numérotées et **immuables une fois acceptées**. Une décision qui change est
remplacée par une nouvelle ADR, jamais modifiée sur place. Une décision qui se complète est
*précisée* par une ADR ultérieure qui le déclare en tête.

Modèle et index : [`docs/adr/README.md`](adr/README.md).

Quand une ADR est requise :

- ajouter un type de vérification (règle de fermeture, ADR 0003 D3) ;
- ajouter une valeur à l'enum `kind` d'artefact (D8) ;
- ajouter un rôle au-delà de `actor` et `evaluator` (D9) ;
- ratifier une convention `C<n>` de `DECISIONS.md` ;
- tout mécanisme qui modifie le schéma.

Une ADR acceptée est ajoutée à la table de `docs/adr/README.md` avec son statut.

---

## Conventions de code

- Type hints partout, `from __future__ import annotations` en tête de module.
- Docstrings en anglais dans `src/`, documentation et YAML en français. C'est l'état actuel
  du dépôt ; s'y tenir tant qu'aucune décision ne l'a changé.
- Dataclasses gelées pour les valeurs (`LintMessage`, `CheckResult`).
- Pas de dépendance nouvelle sans nécessité démontrée. Le linter est écrit à la main plutôt
  qu'avec `pydantic` ou `jsonschema` pour une raison précise : chaque message doit expliquer
  la règle et citer son ADR.
- Aucun formateur ni linter Python n'est configuré dans le dépôt. Suivre le style existant.

---

## CI

`.github/workflows/ci.yml`, sur `push` et `pull_request` vers `main` :

```
matrice Python 3.11 / 3.12 / 3.13
  ├── pip install -e ".[test]"
  ├── pytest --strict-markers --tb=short
  └── agentic lint workflows/v1/bugfix.yaml
```

`fail-fast: false` : une version de Python qui casse n'annule pas les autres.

---

## Où en est le projet

Le travail est découpé en lots dans
[`docs/planning/plan-execution.md`](planning/plan-execution.md). Lot 0 (linter) est
terminé ; le chemin critique passe par les Lots 1, 2, 4 et 5.

Deux règles de conduite y sont posées et valent pour toute contribution : aucune
abstraction n'est introduite avant que trois sessions réelles ne l'aient réclamée, et le
workflow précède le runtime.

---

## Voir aussi

- [Architecture technique](architecture.md)
- [Référence du schéma de workflow](reference/workflow-schema.md)
- [Catalogue des règles de lint](reference/lint-rules.md)
- [Référence CLI](reference/cli.md)
