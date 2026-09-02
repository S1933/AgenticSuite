# Catalogue des règles de lint

Le linter valide une définition de workflow contre le schéma de l'ADR 0003 et les
précisions ultérieures. Il ne valide pas une session, ni un runtime.

18 règles sont enregistrées dans `ALL_RULES` (`src/agentic_suite/lint/rules.py`). 17
émettent des **erreurs**, une seule un **avertissement**.

```bash
agentic lint workflows/v1/bugfix.yaml
agentic lint workflows/v1/bugfix.yaml --strict   # avertissement = erreur
```

Format d'un message :

```
[error] R5 at states.discovery.checks[0].type: check type 'foo' is not in the closed set [...]
 │       │                    │                 └── message
 │       │                    └── chemin pointé dans le workflow
 │       └── identifiant de règle
 └── sévérité
```

---

## Table de synthèse

| Règle | Sévérité | Ce qu'elle garantit | Source |
|---|---|---|---|
| [R1](#r1) | error | Un champ `enum` référence un vocabulaire déclaré | ADR 0003 D1 |
| [R3](#r3) | **warning** | Un état à assertions seules est signalé | ADR 0003 D2 |
| [R4](#r4) | error | `command_ref` respecte `^[a-z][a-z0-9_]*$` | ADR 0003 D3 |
| [R5](#r5) | error | `check.type` appartient à l'ensemble fermé | ADR 0003 D3 |
| [R6](#r6) | error | Toute assertion porte `evidence_from` | ADR 0003 D4 |
| [R7](#r7) | error | `evidence_from` n'est pas vide | ADR 0003 D4 |
| [R8](#r8) | error | `on_failure.when` cite une assertion locale | ADR 0003 D5 |
| [R9](#r9) | error | `on_failure.to` cite un état ou un état d'échappement déclaré | ADR 0003 D5 |
| [R10](#r10) | error | `reclassified` n'est atteignable que depuis `discovery` | ADR 0003 D5 |
| [R11](#r11) | error | `max_attempts` est un entier positif | ADR 0003 D6 |
| [R12](#r12) | error | `max_transitions` est un entier positif | ADR 0003 D6 |
| [R13](#r13) | error | Les `escalate_when` ont `nature: assertion` | ADR 0003 D7 |
| [R14](#r14) | error | Les ids d'artefact sont uniques dans tout le workflow | ADR 0003 D8 |
| [R15](#r15) | error | `kind` d'artefact appartient à l'enum fermé | ADR 0003 D8 |
| [R16](#r16) | error | Un état non terminal déclare `evaluated_by` | ADR 0003 D9 + P1 |
| [R17](#r17) | error | Un id d'assertion ne dissimule pas une négation | ADR 0007 D3 |
| [R20](#r20) | error | `initial_state` existe et n'est pas un état d'échappement | ADR 0003 P2 |
| [R21](#r21) | error | Une preuve `context.*` est atteignable depuis le chemin | ADR 0003 P3 |

**Numéros non attribués** : R2 et R19 n'existent ni dans le code ni dans les tests. Ils
restent réservés — ne pas les réutiliser pour une nouvelle règle, les identifiants
apparaissant dans les messages et dans l'historique.

**R18** est défini dans le code mais délègue entièrement à R8 et n'est pas enregistré dans
`ALL_RULES` : les messages portent l'identifiant `R8`. R18 existe pour que l'ADR 0007 D4
ait un point d'entrée nommé, pas parce qu'il ajoute une vérification.

---

## Détail des règles

### R1 — Vocabulaire référencé {#r1}

**Chemin** `states.<id>.context_fields[<i>].vocabulary` · **Sévérité** error

Un `context_field` de `type: enum` doit porter `vocabulary:` pointant sur une clé déclarée
dans le `vocabularies:` du workflow.

```yaml
# ✗ erreur
vocabularies:
  impact_scope: [single_user, all_users]
states:
  - id: discovery
    context_fields:
      - id: scope
        type: enum
        vocabulary: impact_scopes   # 's' de trop

# ✓ correct
        vocabulary: impact_scope
```

Un champ `enum` sans clé `vocabulary` est également en erreur (`vocabulary` valant `None`,
absent des vocabulaires déclarés).

---

### R3 — État sans check {#r3}

**Chemin** `states.<id>` · **Sévérité** warning

Un état non terminal qui déclare des assertions mais aucun check est signalé : la règle de
l'ADR 0002 — préférer une vérification quand la condition s'y réduit — n'est auditable que
si le déséquilibre est visible.

C'est le seul avertissement du linter. Il est légitime de le laisser en place après
examen, en justifiant par un commentaire dans le YAML. `--strict` le transforme en erreur,
ce que fait la CI sur les workflows censés être propres.

Un état `terminal: true` est exempté. Un état sans checks **et** sans assertions n'est pas
signalé (rien à équilibrer).

---

### R4 — Forme de `command_ref` {#r4}

**Chemin** `states.<id>.checks[<i>].command_ref` · **Sévérité** error

Sur un check `command_exit_zero`, `command_ref` doit être un identifiant plat conforme à
`^[a-z][a-z0-9_]*$`.

```yaml
# ✗ ./scripts/test.sh   → chemin
# ✗ ci/run_tests        → namespace
# ✗ Run_Tests           → majuscule
# ✓ run_tests
```

Le schéma valide la forme, pas l'existence. La résolution ref → argv appartient à
l'ADR 0005 et n'est pas implémentée. Un `command_ref` absent (`None`) n'est pas signalé par
R4 : seule une valeur string mal formée l'est.

---

### R5 — Type de check fermé {#r5}

**Chemin** `states.<id>.checks[<i>].type` · **Sévérité** error

`type` ∈ `artifact_exists`, `command_exit_zero`, `context_fields_present`. Un check sans
`type` déclenche aussi la règle.

Cette fermeture est le garde-fou central du schéma : c'est elle, et non la bonne volonté,
qui empêche la dérive vers un langage d'expressions. Toute condition qui ne rentre pas
dans ces trois types devient une assertion. Un quatrième type exige une nouvelle ADR
numérotée.

---

### R6 — Preuve obligatoire {#r6}

**Chemin** `states.<id>.assertions[<i>]` · **Sévérité** error

Toute assertion doit porter la clé `evidence_from`. Une assertion sans preuve est un défaut
de définition, pas une assertion faible.

---

### R7 — Preuve non vide {#r7}

**Chemin** `states.<id>.assertions[<i>].evidence_from` · **Sévérité** error

`evidence_from: []` est refusé au même titre qu'un champ absent. R6 et R7 sont séparées
pour que le message distingue « clé oubliée » de « liste vidée ».

---

### R8 — `on_failure.when` cite une assertion locale {#r8}

**Chemin** `states.<id>.on_failure[<i>].when` · **Sévérité** error

`when` doit correspondre à un `assertions[].id` déclaré **dans le même état**. Citer une
assertion d'un autre état, ou une chaîne libre, est refusé.

```yaml
# ✓
assertions:
  - id: no_root_cause_found
    evidence_from: [context.evidence_examined]
on_failure:
  - to: blocked
    when: no_root_cause_found
```

Corollaire : une assertion citée ici devient une **assertion d'échec** au sens de la
convention C2, donc exclue de la conjonction de sortie nominale, et doit être formulée
positivement (voir R17).

---

### R9 — Cible de transition déclarée {#r9}

**Chemin** `states.<id>.on_failure[<i>].to` · **Sévérité** error

`to` doit désigner soit un `states[].id`, soit un `escape_states[].id`. Une cible inventée
est refusée.

La cible de `next:` n'est **pas** vérifiée : un `next: typo` passe le lint. C'est un trou
connu, listé au Lot 1.

---

### R10 — `reclassified` réservé à `discovery` {#r10}

**Chemin** `states.<id>.on_failure[<i>].to` · **Sévérité** error

Seul `discovery` peut transiter vers `reclassified`. Constater en cours d'investigation
que le rapport n'est pas un bug impose de repasser par `discovery`.

C'est la seule règle du linter qui code en dur un nom d'état de `bugfix`. Elle devra être
généralisée ou déplacée quand un second workflow arrivera (Lot 7).

---

### R11 — `max_attempts` entier positif {#r11}

**Chemin** `states.<id>.max_attempts` · **Sévérité** error

Entier ≥ 1 quand la clé est présente. Absente, le défaut est 1 et la règle ne dit rien.
`0`, `-1`, `"2"` et `2.0` sont refusés.

Attention à YAML : `max_attempts: true` passe la vérification `isinstance(ma, int)` en
Python — `bool` est une sous-classe de `int`. Trou connu.

---

### R12 — `max_transitions` entier positif {#r12}

**Chemin** `max_transitions` (racine) · **Sévérité** error

Même contrainte que R11, au niveau du workflow. Défaut 20 quand la clé est absente.

---

### R13 — Nature des déclencheurs d'escalade {#r13}

**Chemin** `escalate_when[<i>].nature` · **Sévérité** error

Chaque entrée de `escalate_when` doit porter `nature: assertion`. Le message rappelle
pourquoi : `budget_exceeded` est un invariant de runtime (D6), pas un déclencheur
d'escalade, et n'a rien à faire dans cette liste.

---

### R14 — Unicité des ids d'artefact {#r14}

**Chemin** `states.<id>.produces[<i>].id` · **Sévérité** error

Un id d'artefact est unique dans **tout** le workflow, pas seulement dans l'état qui le
produit. Le message indique où l'id a été déclaré la première fois.

C'est ce qui rend `artifacts.<id>` non ambigu dans `evidence_from`, et ce qui permet à
`artifact_exists` de pointer sans qualifier l'état.

---

### R15 — `kind` d'artefact fermé {#r15}

**Chemin** `states.<id>.produces[<i>].kind` · **Sévérité** error

`kind` ∈ `decision`, `diagnosis`, `note`, `patch`, `repro`, `test_result`. Ajouter une
valeur exige une nouvelle ADR — parallélisme strict avec R5.

Un artefact sans `kind` déclenche la règle.

---

### R16 — `evaluated_by` sur les états non terminaux {#r16}

**Chemin** `states.<id>.evaluated_by` · **Sévérité** error

Tout état non terminal doit déclarer `evaluated_by` avec la valeur `actor` ou `evaluator`.
Les états `terminal: true` sont exemptés.

> L'ADR 0003 D9 annonce un défaut à `actor` ; R16 exige la déclaration explicite. Le défaut
> n'est donc pas utilisable, et l'écart est assumé (précision ADR 0003 P1) : rendre le
> choix de l'évaluateur visible état par état vaut mieux qu'un défaut silencieux sur une
> décision que l'ADR 0002 §4 traite comme structurante.

---

### R17 — Polarité des ids d'assertion {#r17}

**Chemin** `states.<id>.assertions[<i>].id` · **Sévérité** error

Un id d'assertion ne peut pas être la négation d'une autre assertion. Regex refusé :
`^.*_(is_not|not_|does_not)_.*$`.

```yaml
# ✗ regression_is_not_verified   → négation d'une assertion nominale
# ✓ diagnosis_is_invalidated     → nomme la condition constatée
# ✓ fix_cannot_be_implemented    → constat, pas négation
# ✓ validation_cannot_be_completed
```

`cannot_`, `fails_`, `failed_`, `invalid_` sont volontairement laissés passer : ils nomment
une condition observée, non la négation d'un autre énoncé (ADR 0007 D5).

**Limite connue** : le regex exige le segment `is_not`, `does_not` ou `not_` entre deux
underscores. `regression_not_verified` (sans `is`) n'est pas détecté.

---

### R20 — `initial_state` valide {#r20}

**Chemin** `initial_state` (racine) · **Sévérité** error

Trois cas d'erreur distincts, avec trois messages :

1. clé `initial_state` absente ;
2. valeur ne correspondant à aucun `states[].id` ;
3. valeur correspondant à un `escape_states[].id` — un workflow ne démarre pas dans un
   état d'échappement.

Convention C5. `bugfix` démarre en `discovery` ; l'état `Reported` du diagramme du README
n'existe pas dans la machine, le rapport initial est le champ de contexte
`original_report`.

---

### R21 — Atteignabilité des preuves de contexte {#r21}

**Chemin** `states.<id>.assertions[<i>].evidence_from[<j>]` · **Sévérité** error

Pour chaque preuve de la forme `context.<field_id>` citée par un état atteignable depuis
`initial_state`, la règle vérifie que :

1. le champ est déclaré par un état du workflow — sinon *« is not declared by any state »* ;
2. l'état citant est atteignable depuis l'état producteur — sinon *« unreachable from there
   to … »*.

L'atteignabilité est calculée sur le graphe orienté formé par `next:` et `on_failure[].to`,
depuis `initial_state`. Un état non atteignable est ignoré : ses assertions ne sont pas
vérifiées.

C'est la contre-partie de la convention C6, qui place l'espace de noms du contexte au
niveau de la session : sans cette règle, un état pourrait citer un champ qu'aucun chemin ne
collecte jamais.

**Portée limitée** : R21 ne vérifie que les preuves `context.*`. Les références
`artifacts.*` et `checks.*` ne sont pas confrontées aux `produces:` et `checks:` déclarés.

---

## Ajouter une règle

Voir [le guide de développement](../development.md#ajouter-une-règle-de-lint). En résumé :
une règle est un générateur `(workflow: dict) -> Iterable[LintMessage]`, tolérant aux
structures malformées, enregistré dans `ALL_RULES`, avec un test dédié dans
`tests/lint/test_R<n>_*.py`, et adossé à un paragraphe d'ADR cité dans sa docstring.

Une règle qui n'est adossée à aucune ADR est un avis de style, pas une règle de schéma :
elle ne rentre pas dans le linter.
