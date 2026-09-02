# Référence du schéma de workflow

Référence complète des clés acceptées dans un fichier `workflows/v<N>/<id>.yaml`.

Ce document est **descriptif** : il décrit ce que le schéma exige (ADR 0003, précisions
ADR 0003-P, ADR 0007) et ce que le linter vérifie réellement aujourd'hui. En cas de
divergence entre une ADR et le code, la divergence est signalée explicitement. Les ADR
restent la source de la décision ; ce document est la source de l'usage.

Exemple de référence complet et lint-clean : [`workflows/v1/bugfix.yaml`](../../workflows/v1/bugfix.yaml).

---

## 1. Racine du workflow

```yaml
id: bugfix
version: 1
initial_state: discovery
max_transitions: 20

vocabularies: { ... }
escape_states: [ ... ]
escalate_when: [ ... ]
states: [ ... ]
```

| Clé | Type | Obligatoire | Défaut | Vérifiée par |
|---|---|---|---|---|
| `id` | string snake_case | oui (convention) | — | *non vérifiée* |
| `version` | entier | oui (convention) | — | *non vérifiée* |
| `initial_state` | string | **oui** | — | R20 |
| `max_transitions` | entier ≥ 1 | non | 20 | R12 |
| `vocabularies` | mapping | non | `{}` | R1 |
| `escape_states` | liste | non | `[]` | R9, R20 |
| `escalate_when` | liste | non | `[]` | R13 |
| `states` | liste | oui (convention) | — | *présence non vérifiée* |

`initial_state` doit désigner un `states[].id` déclaré, et **ne peut pas** être un
`escape_states[].id` (ADR 0003 P2, convention C5).

Le chargeur (`load_workflow`) exige seulement que la racine soit un mapping YAML. Toute
autre erreur est une erreur de lint, pas une erreur de chargement.

### 1.1 `vocabularies`

Énumérations factorisées au niveau du workflow, référencées par id depuis un champ de
contexte de type `enum` (ADR 0003 D1).

```yaml
vocabularies:
  impact_scope:
    - single_user
    - subset_of_users
    - all_users
    - unknown_extent
```

Un `context_fields[].vocabulary` qui ne correspond à aucune clé déclarée ici est une
erreur R1. Le contenu des listes n'est pas validé (les valeurs ne sont pas confrontées
aux données de session — il n'y a pas encore de runtime).

### 1.2 `escape_states`

États atteignables depuis n'importe quel état, déclarés une seule fois (ADR 0003 D5).

```yaml
escape_states:
  - id: blocked
    terminal: false
    description: >
      La session ne peut pas avancer et attend un humain.

  - id: abandoned
    terminal: true
    description: Aucun correctif n'a été livré.
```

| Champ | Type | Rôle |
|---|---|---|
| `id` | string | Cible autorisée pour `on_failure[].to` |
| `terminal` | booléen | `blocked` est reprenable, `abandoned` non |
| `description` | prose | Sémantique partagée par tous les workflows |

`blocked` et `abandoned` ont une sémantique fixe. Un workflow qui veut une nuance déclare
son propre état d'échappement local plutôt que de redéfinir celle de `blocked`.

`reclassified` est une exception : il est déclaré dans `states:` et n'est atteignable que
depuis `discovery` (R10).

### 1.3 `escalate_when`

Quatre déclencheurs d'escalade évalués par l'évaluateur à chaque transition (ADR 0003 D7).

```yaml
escalate_when:
  - id: irreversible_action
    nature: assertion
    description: L'action suivante est irréversible ou destructrice.
```

`nature` doit valoir `assertion` (R13). Le dépassement de budget n'est **pas** un
déclencheur d'escalade : c'est un invariant de runtime traité en D6, qui force `blocked`
sans passer par l'évaluateur.

---

## 2. État

```yaml
states:
  - id: investigation
    role: actor
    evaluated_by: evaluator
    max_attempts: 2
    description: >
      L'agent examine les preuves disponibles avant de proposer un correctif.

    context_fields: [ ... ]
    checks: [ ... ]
    assertions: [ ... ]
    produces: [ ... ]

    next: fix
    on_failure: [ ... ]
```

| Clé | Type | Obligatoire | Défaut | Vérifiée par |
|---|---|---|---|---|
| `id` | string snake_case | oui | — | *non vérifiée, mais un état sans `id` string est ignoré par toutes les règles* |
| `role` | `actor` \| `evaluator` | convention | `actor` | *non vérifiée* |
| `evaluated_by` | `actor` \| `evaluator` | **oui si non terminal** | `actor` (ADR) | R16 |
| `max_attempts` | entier ≥ 1 | non | 1 | R11 |
| `terminal` | booléen | non | `false` | — |
| `description` | prose | convention | — | — |
| `context_fields` | liste | non | `[]` | R1, R21 |
| `checks` | liste | non | `[]` | R3, R4, R5 |
| `assertions` | liste | non | `[]` | R6, R7, R17, R21 |
| `produces` | liste | non | `[]` | R14, R15 |
| `next` | string | convention | — | *cible non vérifiée* |
| `on_failure` | liste | non | `[]` | R8, R9, R10 |

Un état `terminal: true` est exempté de R3 et R16 ; il ne déclare typiquement que `id`,
`terminal` et `description`.

> **Divergence ADR ↔ code.** L'ADR 0003 D9 fixe `evaluated_by` à `actor` par défaut. La
> règle R16 exige qu'il soit **déclaré explicitement** sur tout état non terminal : le
> défaut n'est donc pas exploitable en pratique. `bugfix.yaml` déclare
> `evaluated_by: evaluator` partout (convention C3).

L'ordre des états dans la liste ne porte aucune sémantique. Le point d'entrée est
`initial_state`, la suite est portée par `next:` et `on_failure:`.

### 2.1 `context_fields`

Contexte que l'état doit avoir collecté avant de pouvoir être quitté (ADR 0003 D1).

```yaml
context_fields:
  - id: impact_scope
    type: enum
    vocabulary: impact_scope
    required: true
    description: Étendue de l'impact constaté.
```

| Champ | Type | Obligatoire | Notes |
|---|---|---|---|
| `id` | string snake_case | oui | Référencé par `context.<id>` |
| `type` | `text` \| `list` \| `boolean` \| `enum` | oui | *valeur non vérifiée par le linter* |
| `vocabulary` | string | oui si `type: enum` | Doit exister dans `vocabularies` (R1) |
| `required` | booléen | oui | `false` = enrichit sans bloquer la sortie |
| `description` | prose | oui | Contrat sémantique : le modifier est cassant (D10) |

**Portée** : l'espace de noms des champs de contexte est **la session**, pas l'état
(convention C6). Un état peut citer comme preuve un champ collecté par un état antérieur,
à condition que cet état soit sur un chemin menant jusqu'à lui — c'est ce que vérifie R21.

**Satisfaction d'un champ** : un champ porte une valeur non vide, ou est marqué inconnu
avec une raison. La marque d'inconnu est le dict `{"_unknown": true}` dans le code de
vérification (`check_context_fields_present`). Un champ vide sans raison est insatisfait.

### 2.2 `checks`

Conditions **déterministes**, évaluées par le runtime. Liste fermée de trois types
(ADR 0003 D3). Un quatrième type exige une nouvelle ADR.

```yaml
checks:
  - name: investigation_context_present
    type: context_fields_present
    fields: [evidence_examined, root_cause_hypothesis]
    max_unknown: 0

  - name: diagnosis_recorded
    type: artifact_exists
    id: diagnosis

  - name: unit_tests_pass
    type: command_exit_zero
    command_ref: run_tests
```

| Champ commun | Type | Notes |
|---|---|---|
| `name` | string snake_case | Unique dans l'état, référencé par `checks.<name>` (convention C1) |
| `type` | enum fermé | R5 |

Paramètres par type :

| `type` | Paramètres | Sémantique |
|---|---|---|
| `context_fields_present` | `fields` (liste), `max_unknown` (entier ≥ 0, défaut 0) | Passe si le nombre de champs inconnus ≤ `max_unknown` |
| `artifact_exists` | `id` (string) | Passe si l'artefact est présent et non nul dans la session |
| `command_exit_zero` | `command_ref` (`^[a-z][a-z0-9_]*$`, R4) | Passe si le code de sortie vaut 0 |

Il n'existe **aucun** check composite (`all_of`, `any_of`). Une condition combinée se
déclare comme plusieurs checks distincts, composés dans une assertion qui cite les
`checks.*` correspondants.

`command_ref` est un identifiant opaque. Sa résolution est définie par l'ADR 0005
(hiérarchie `<projet>/.agentic/commands.yaml` puis `~/.config/agentic/commands.yaml`) et
**n'est pas implémentée**. Le linter valide la forme ; à l'exécution, un ref non résolu
produira `command_ref_unresolved`.

Un état sans aucun check est autorisé mais produit un avertissement R3.

### 2.3 `assertions`

Conditions de **jugement**, évaluées par un agent sur la base de preuves enregistrées
(ADR 0003 D4).

```yaml
assertions:
  - id: root_cause_is_identified
    description: >
      Une cause racine plausible est rattachée au comportement observé par une
      chaîne d'explication vérifiable.
    evidence_from:
      - checks.investigation_context_present
      - artifacts.diagnosis
      - context.root_cause_hypothesis
```

| Champ | Type | Obligatoire | Vérifié par |
|---|---|---|---|
| `id` | string snake_case | oui | R17 (polarité) |
| `description` | prose | convention | — |
| `evidence_from` | liste non vide | **oui** | R6, R7, R21 |

**Espace de noms des preuves** — trois préfixes, et seulement trois :

| Référence | Cible |
|---|---|
| `context.<field_id>` | Un champ de contexte collecté dans la session |
| `artifacts.<artifact_id>` | Un artefact produit par un état |
| `checks.<check_name>` | Un check exécuté |

Une assertion ne peut pas citer une autre assertion comme preuve : citer un jugement pour
justifier un jugement est exactement le pattern que l'ADR 0002 combat. *Cette interdiction
n'est pas vérifiée par le linter aujourd'hui.*

**Artefact implicite** : un check `command_exit_zero` produit automatiquement l'artefact
`command_output_<check_name>` (stdout, stderr, code de sortie, horodatage), consommable
via `artifacts.command_output_<check_name>` (convention C4). C'est la seule exception à la
règle « tout artefact est déclaré dans `produces` ».

**Polarité** (ADR 0007, convention C2) — deux natures d'assertion cohabitent :

- **assertion nominale** : non citée par un `on_failure[].when` ; toutes doivent être
  vraies pour sortir vers `next`.
- **assertion d'échec** : citée par un `on_failure[].when` ; formulée **positivement**,
  vraie quand l'échec est constaté. Exclue de la conjonction de sortie nominale.

Ordre d'évaluation à chaque transition : les assertions d'échec d'abord, dans leur ordre
de déclaration, la première vraie déclenche sa transition. Sinon, sortie nominale si tous
les checks passent et toutes les assertions nominales sont vraies.

Nommer une assertion d'échec par la négation d'une assertion nominale
(`regression_is_not_verified`) est interdit et détecté par R17. On nomme la condition
constatée : `diagnosis_is_invalidated`, `fix_cannot_be_implemented`.

### 2.4 `produces`

Artefacts produits par l'état (ADR 0003 D8).

```yaml
produces:
  - id: diagnosis
    kind: diagnosis
    required: true
    description: Diagnostic concret, ou incertitude documentée.
```

| Champ | Type | Obligatoire | Vérifié par |
|---|---|---|---|
| `id` | string snake_case, **unique dans tout le workflow** | oui | R14 |
| `kind` | enum fermé | oui | R15 |
| `required` | booléen | oui | — |
| `description` | prose | convention | — |

`kind` ∈ `diagnosis`, `repro`, `patch`, `test_result`, `decision`, `note`. Ajouter une
valeur exige une nouvelle ADR.

Un artefact écrasé (par exemple `diagnosis` régénéré après un retour arrière) garde son
`id` ; le dernier enregistrement fait foi et invalide a posteriori toute transition
consommée sur la base de l'ancien. Le runtime snapshotte l'état des artefacts à chaque
transition pour détecter la rupture — **non implémenté**.

### 2.5 `next` et `on_failure`

```yaml
next: fix

on_failure:
  - to: discovery
    when: required_context_is_missing
  - to: blocked
    when: no_root_cause_found
```

| Champ | Contrainte | Vérifié par |
|---|---|---|
| `next` | Id d'un état déclaré | *non vérifié* |
| `on_failure[].to` | Id d'un état déclaré **ou** d'un `escape_states` | R9 |
| `on_failure[].when` | Id d'une assertion déclarée **dans le même état** | R8 (R18) |

`when` ne peut pas être une chaîne libre : ce serait rouvrir la porte au langage
d'expressions que le schéma refuse. Une transition d'échec a deux prérequis : l'assertion
citée est vraie **et** le budget le permet.

`reclassified` n'est atteignable que depuis `discovery` (R10).

---

## 3. Budgets

Deux budgets bornent l'autonomie (ADR 0003 D6) :

| Budget | Portée | Défaut | Règle |
|---|---|---|---|
| `max_attempts` | État | 1 | R11 |
| `max_transitions` | Workflow | 20 | R12 |

La première entrée dans un état compte comme tentative 1 : un état à `max_attempts: 1` ne
peut pas être revisité. Un dépassement force une transition vers `blocked` avec la raison
enregistrée, sans passer par l'évaluateur.

Les transitions **depuis** `blocked` (reprise humaine) ne consomment pas le budget ;
seules les transitions **vers** `blocked` comptent.

Aucun budget en tokens ou en coût n'existe en v0 : aucun runtime ne peut le mesurer, et le
déclarer donnerait une garantie fictive.

---

## 4. Ce que le schéma ne vérifie pas

Écarts connus entre le schéma décrit par les ADR et ce que le linter détecte
réellement. Les corriger relève du Lot 1 du plan d'exécution.

| Non vérifié | Conséquence |
|---|---|
| Présence et type de `id`, `version`, `states` à la racine | Un fichier tronqué passe partiellement |
| Valeur de `states[].role` | Un rôle inventé n'est pas signalé |
| Valeur de `context_fields[].type` | Un type hors des quatre autorisés passe |
| Unicité et présence de `checks[].name` | Deux checks homonymes rendent `checks.<name>` ambigu |
| Existence de la cible de `next:` | Un `next: typo` n'est détecté qu'à l'exécution |
| Atteignabilité d'un état terminal | Un workflow sans sortie passe le lint |
| Existence des références `artifacts.*` et `checks.*` dans `evidence_from` | Seul `context.*` est vérifié (R21) |
| Interdiction de citer une assertion comme preuve (D4) | Auto-justification non détectée |
| Exclusivité nominale / échec d'une assertion (C2 point 5) | Une assertion peut être les deux |
| Portée du regex de polarité R17 | `regression_not_verified` (sans `is`) n'est pas détecté |

---

## 5. Versionnage

Le dossier `workflows/v<N>/` **est** la version ; `version:` reste un entier, pas du
semver (ADR 0003 D10). Une session est épinglée à la version avec laquelle elle a démarré
et ne migre jamais ; si la version disparaît, la session passe à `blocked`.

**Cassant** : supprimer un état · renommer un id d'état, de champ ou d'artefact · ajouter
un champ de contexte requis · resserrer une vérification (`max_unknown` diminué, champ
ajouté à `fields`) · changer une cible de transition · modifier le wording d'une
`description` (les descriptions sont des contrats sémantiques).

**Non cassant** : ajouter un état optionnel · ajouter un artefact optionnel · desserrer un
budget · ajouter un état d'échappement · ajouter une assertion sans toucher aux
existantes.

---

## Voir aussi

- [Catalogue des règles de lint](lint-rules.md)
- [Référence CLI](cli.md)
- [ADR 0003 — Schéma déclaratif de workflow](../adr/0003-workflow-schema.md)
- [ADR 0007 — Polarité des assertions](../adr/0007-assertion-polarity.md)
- [Conventions v1 du workflow bugfix](../../workflows/v1/DECISIONS.md)
