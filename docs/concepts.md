# Concepts

Ce fichier est la définition unique du vocabulaire du projet. Le README le résume ; les ADR décident du comportement de chaque concept.

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
    exit_when:
      - problem_is_understood
      - reproduction_context_is_sufficient
```

Cet extrait est illustratif et incomplet. Le schéma reste volontairement indécis tant que l'usage réel ne l'a pas contraint (voir ADR 0003, non encore écrite).

## Session

Une exécution d'un workflow, dotée d'une identité stable et de suffisamment d'informations enregistrées pour être interrompue puis reprise.

Une session contient : identifiant de session, identifiant et version du workflow, état courant, contexte fourni par l'utilisateur, contexte produit par les agents, historique des transitions, décisions, artefacts, horodatages, statut.

## État

Une phase significative d'un workflow. Le contrat d'un état peut définir des conditions d'entrée, des responsabilités, le contexte requis, les actions et skills autorisées, les artefacts attendus et les conditions de sortie.

## Critères de sortie

Les conditions qui autorisent une session à quitter un état. Chacun est soit une **vérification**, évaluée de manière déterministe par le runtime, soit une **assertion**, évaluée par un agent à partir de preuves enregistrées. Voir l'ADR 0002.

## Transition

Un passage enregistré d'un état à un autre. Les transitions peuvent aller vers l'avant, vers l'arrière ou vers un état d'échec, et sont toujours décomptées d'un budget. Voir l'ADR 0002.

## Rôle d'agent

La responsabilité demandée par un état, exprimée indépendamment de tout fournisseur : `investigator`, `planner`, `implementer`, `reviewer`, `researcher`.

## Capacité

Ce dont un rôle a besoin de la part d'un backend d'exécution : raisonnement, édition de code, accès au dépôt, recherche web, exécution d'outils, contexte long, latence faible, coût faible.

Les capacités sont la couche qui permet de réaffecter un rôle à un autre backend sans changer la sémantique du workflow.

## Fournisseur

Un backend d'exécution : harnais d'agent, environnement de développement, API ou outil adossé à un abonnement. Le choix du fournisseur appartient à la configuration, sous les workflows et les rôles.

## Skill

Une primitive d'ingénierie réutilisable qui fait une seule chose bien, maintenue dans le registre [`S1933/Skills`](https://github.com/S1933/Skills). Agentic Suite compose des skills ; il ne les possède pas.

## Artefact

Tout ce qu'un état produit et dont un état ultérieur ou un humain pourra avoir besoin : un diagnostic, une reproduction, un patch, un résultat de test, une décision consignée.
