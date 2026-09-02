# Concepts

Ce fichier est la définition unique du vocabulaire du projet. Le README le résume ; les ADR décident du comportement de chaque concept.

> **Mise à jour 2026-09-02.** Cet exemple YAML est désormais obsolète : la clé `exit_when:` a été remplacée par les deux clés `checks:` et `assertions:` par l'ADR 0003. Voir « Critères de sortie » ci-dessous pour la définition actuelle.

## Workflow

L'unité exécutable principale. Un workflow définit des états, le rôle responsable de chacun, les conditions de transition et les sorties attendues.

Workflows envisagés : `bugfix`, `feature`, `review`, `research`, `release`. Seul `bugfix` est dans le périmètre de la v0.

## Définition de workflow

La description déclarative d'un workflow, en YAML dans un premier temps. Elle décrit une intention et des contrats, pas une implémentation.

```yaml
id: bugfix
version: 1

states:
  - id: discovery
    role: investigator
    evaluated_by: investigator
    max_attempts: 1

    context_fields:
      - id: observed_behavior
        type: text
        required: true
        description: Ce que le système fait réellement.

    checks:
      - type: context_fields_present
        fields: [observed_behavior]
        max_unknown: 0

    assertions:
      - id: context_is_sufficient_to_investigate
        description: Le contexte collecté permet de commencer sans deviner.
        evidence_from:
          - context.observed_behavior
          - checks.context_fields_present
```

Cet extrait est illustratif et incomplet. Le schéma complet est défini par l'ADR 0003.

## Session

Une exécution d'un workflow, dotée d'une identité stable et de suffisamment d'informations enregistrées pour être interrompue puis reprise.

Une session contient : identifiant de session, identifiant et version du workflow, état courant, contexte fourni par l'utilisateur, contexte produit par les agents, historique des transitions, décisions, artefacts, horodatages, statut.

Une session est **épinglée à la version de workflow** avec laquelle elle a démarré et ne migre jamais. Si la version disparaît, la session passe à `blocked`.

## État

Une phase significative d'un workflow. Le contrat d'un état peut définir des conditions d'entrée, des responsabilités, le contexte requis, les actions et skills autorisées, les artefacts attendus, les checks, les assertions, les transitions et le budget de tentatives.

Chaque état déclare explicitement ses cibles de transition (`next:`, `on_failure:`). L'ordre des états dans la liste ne porte pas de sémantique.

## Critères de sortie

Les conditions qui autorisent une session à quitter un état. Chacun est soit une **vérification**, évaluée de manière déterministe par le runtime, soit une **assertion**, évaluée par un agent à partir de preuves enregistrées. Voir l'ADR 0002 pour le raisonnement.

### Vérifications

Liste fermée de trois types pour la v0 :

| Type | Paramètres |
|---|---|
| `context_fields_present` | `fields`, `max_unknown` |
| `artifact_exists` | `id` |
| `command_exit_zero` | `command_ref` |

Toute condition qui ne rentre pas dans ces trois types devient une assertion. Ajouter un quatrième type exige une nouvelle ADR.

### Assertions

Chaque assertion porte `evidence_from:`, liste non vide d'identifiants dans l'espace de noms stable :

- `context.<field_id>`
- `artifacts.<artifact_id>`
- `checks.<check_name>`

Une assertion sans preuve est un défaut de définition : le schéma la refuse au chargement.

### Évaluation

L'évaluateur est distinct de l'acteur pour tout état qui modifie le code (cf. `fix` dans `bugfix`). L'évaluateur opère exclusivement sur l'enregistrement de session, à l'exclusion de la conversation de travail.

## Transition

Un passage enregistré d'un état à un autre. Les transitions peuvent aller vers l'avant, vers l'arrière ou vers un état d'échec, et sont toujours décomptées d'un budget. Voir l'ADR 0002.

Les états d'échappement atteignables depuis n'importe où, `blocked` et `abandoned`, sont déclarés une fois au niveau du workflow sous `escape_states:`. `reclassified`, atteignable uniquement depuis `discovery`, est déclaré localement.

Le champ `when:` de `on_failure:` référence un `assertion.id`. Les conditions de transition sont des assertions à part entière, pas des chaînes libres.

### Budgets

Deux budgets bornent l'autonomie :

- `max_attempts` par état, défaut 1
- `max_transitions` au niveau du workflow, défaut 20

Dépassement → transition forcée vers `blocked`, raison enregistrée. Les reprises depuis `blocked` ne consomment pas le budget ; seules les transitions vers `blocked` comptent.

## Rôle d'agent

Deux rôles minimaux sont définis par le schéma :

- `actor` — exécute le travail de l'état
- `evaluator` — évalue les assertions

Tout autre rôle est défini dans une ADR ultérieure. La liste `investigator`, `planner`, `implementer`, `reviewer`, `researcher` précédemment citée n'est pas figée et reste indicative.

## Capacité

Ce dont un rôle a besoin de la part d'un backend d'exécution : raisonnement, édition de code, accès au dépôt, recherche web, exécution d'outils, contexte long, latence faible, coût faible.

Les capacités sont la couche qui permet de réaffecter un rôle à un autre backend sans changer la sémantique du workflow.

## Fournisseur

Un backend d'exécution : harnais d'agent, environnement de développement, API ou outil adossé à un abonnement. Le choix du fournisseur appartient à la configuration, sous les workflows et les rôles.

## Skill

Une primitive d'ingénierie réutilisable qui fait une seule chose bien, maintenue dans le registre [`S1933/Skills`](https://github.com/S1933/Skills). Agentic Suite compose des skills ; il ne les possède pas.

## Artefact

Tout ce qu'un état produit et dont un état ultérieur ou un humain pourra avoir besoin : un diagnostic, une reproduction, un patch, un résultat de test, une décision consignée.

Chaque artefact porte un `id` unique dans tout le workflow (pas seulement dans l'état qui le produit). Le `kind` est un enum fermé parmi `diagnosis`, `repro`, `patch`, `test_result`, `decision`, `note`. Ajouter une valeur exige une nouvelle ADR.

Un artefact écrasé invalide a posteriori toute assertion postérieure qui le référençait. Le runtime snapshotte l'état des artefacts à chaque transition.

Les checks de type `command_exit_zero` produisent automatiquement un artefact implicite `command_output<check_id>` (stdout, stderr, code de sortie, horodatage). Cet artefact est consommable via `artifacts.command_output<check_id>`.