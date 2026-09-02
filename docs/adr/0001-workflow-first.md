# ADR 0001 : Architecture centrée workflow

- **Statut :** Acceptée
- **Date :** 2026-09-02
- **Responsables de la décision :** mainteneurs d'Agentic Suite

## Contexte

Agentic Suite vise à fournir une méthode de travail complète pour développer du logiciel avec des agents IA.

L'écosystème environnant change rapidement :

- la qualité des modèles change,
- les fournisseurs changent,
- les limites d'abonnement changent,
- les harnais d'agents apparaissent et disparaissent,
- chaque outil a ses propres forces.

Construire le projet autour d'un seul agent, modèle, éditeur ou CLI rendrait l'architecture fragile.

Le dépôt Skills existant fournit déjà des primitives d'ingénierie réutilisables couvrant la découverte, la conception, l'implémentation, la qualité et la livraison.

Ce qui manque, c'est une couche supérieure qui décide comment ces primitives se composent en un processus d'ingénierie complet.

Le premier cas d'usage concret est la correction de bugs.

Les rapports de bug arrivent fréquemment avec un contexte insuffisant : un processus de bugfix utile ne peut donc pas commencer directement par une modification de code.

Le système a besoin d'un processus explicite pour :

1. acquérir du contexte,
2. investiguer le problème,
3. implémenter un correctif,
4. valider le résultat,
5. enregistrer la complétion.

## Décision

Agentic Suite adopte une **architecture centrée workflow**.

Le workflow est l'unité principale lancée par l'utilisateur.

Les agents, skills, fournisseurs et modèles se situent sous le workflow et servent son exécution.

La hiérarchie conceptuelle initiale est :

```text
Utilisateur
  ↓
Workflow
  ↓
Session
  ↓
État
  ↓
Rôle d'agent
  ↓
Skills
  ↓
Fournisseur / Modèle / Outils
```

## Définitions de workflow

Les workflows sont déclaratifs.

La représentation initiale est le YAML.

Une définition de workflow doit décrire :

- l'identité du workflow,
- sa version,
- ses états, ordonnés ou atteignables,
- le rôle responsable de chaque état,
- les responsabilités de chaque état,
- les artefacts attendus,
- les critères de sortie,
- les états terminaux.

Le runtime doit interpréter la définition de workflow plutôt que d'embarquer un comportement spécifique à un workflow directement dans le code.

## Sessions

Toute exécution de workflow crée une session persistante.

Une session doit avoir une identité stable et préserver assez d'informations pour être interrompue puis reprise.

Le modèle de session initial doit contenir :

- l'identifiant de session,
- l'identifiant du workflow,
- la version du workflow,
- l'état courant,
- le contexte collecté,
- l'historique des transitions,
- les artefacts produits,
- le statut.

La technologie de persistance n'est volontairement pas tranchée dans cette ADR.

## Machine à états

Un workflow progresse à travers des états explicites.

Le premier workflow `bugfix` utilisera approximativement :

```text
Discovery
  ↓
Investigation
  ↓
Fix
  ↓
Validation
  ↓
Done
```

Chaque état non terminal devra définir un contrat d'exécution.

Ce contrat peut contenir :

- des conditions d'entrée,
- des responsabilités,
- le contexte requis,
- les outils ou skills autorisés,
- les sorties attendues,
- les conditions de sortie.

## La découverte est un état de premier plan

Le premier état de `bugfix` est `discovery`.

Il existe parce qu'on ne peut pas supposer que le rapport de bug initial contient un contexte suffisant.

Pendant la découverte, le système interroge l'utilisateur de manière interactive.

Les questions sont posées une à la fois.

La question suivante peut dépendre des réponses précédentes.

La découverte ne se termine que lorsque le workflow dispose d'assez de contexte pour commencer l'investigation.

Les critères exacts de complétude seront affinés par l'usage réel.

## Transitions autonomes

Les transitions normales d'un workflow ne nécessitent pas d'approbation humaine explicite.

Un agent peut faire passer la session à l'état suivant lorsque les critères de sortie de l'état courant sont satisfaits.

C'est une **autonomie sous contrat**, pas une autonomie illimitée.

Les décisions produit, architecturales, de sécurité ou irréversibles peuvent malgré tout exiger une intervention humaine explicite lorsqu'un workflow ou un état le prévoit.

## Des rôles plutôt que des noms de modèles

Les définitions de workflow doivent faire référence à des rôles d'agent plutôt qu'à des modèles ou fournisseurs précis.

Exemples de rôles :

- `investigator`,
- `planner`,
- `implementer`,
- `reviewer`.

Le mappage rôle → fournisseur/modèle appartient à la configuration, en dehors de la définition de workflow.

Cela permet de changer de backend d'exécution sans changer le workflow.

## Les skills restent des primitives séparées

Agentic Suite consomme des skills réutilisables plutôt que d'absorber leur contenu dans le runtime.

Le dépôt Skills reste responsable du registre et de l'installation de skills d'ingénierie ciblées.

Agentic Suite est responsable de décider quand ces skills participent à un workflow.

Cela préserve une séparation nette :

```text
Dépôt Skills
  → capacités réutilisables

Agentic Suite
  → orchestration et cycle de vie
```

## Périmètre initial

La première implémentation supporte volontairement :

- un seul workflow : `bugfix`,
- un seul chemin d'exécution actif,
- du YAML déclaratif,
- des états explicites,
- des sessions persistantes,
- des transitions autonomes,
- des skills réutilisables.

Sont hors périmètre pour la première version :

- les workflows qui appellent d'autres workflows,
- les hiérarchies d'agents manager/worker,
- les agents parallèles à grande échelle,
- l'exécution distribuée,
- l'ordonnancement complexe,
- une interface graphique complète,
- l'optimisation automatique de fournisseur.

## Conséquences

### Positives

- Les workflows restent stables pendant que les modèles et fournisseurs changent.
- Le comportement d'un workflow devient inspectable et versionné.
- Les sessions peuvent être interrompues et reprises.
- Les agents gagnent de l'autonomie à l'intérieur de frontières explicites.
- Les skills existantes sont réutilisables sans transformer le dépôt Skills en framework d'orchestration.
- L'architecture peut évoluer vers plusieurs workflows sans redessiner le modèle mental de base.

### Négatives

- Un moteur de workflow et une persistance d'état doivent exister avant que le système soit utile.
- Les schémas déclaratifs impliquent un travail de conception et de validation.
- Certains comportements sont plus difficiles à exprimer en déclaratif qu'en code.
- L'indirection rôle/fournisseur ajoute de la configuration.
- Les critères de sortie doivent être conçus soigneusement, sinon les transitions autonomes deviennent peu fiables.

## Alternatives considérées

### Architecture centrée agent

L'utilisateur lance un agent, et l'agent décide comment mener toute la tâche.

Rejetée : le processus devient dépendant du comportement de l'agent et devient plus difficile à observer, reprendre, tester et réutiliser.

### Architecture centrée fournisseur

Le projet s'organise autour de Codex, Claude Code, OpenCode, Cursor ou d'un outil précis.

Rejetée : les fournisseurs et les abonnements changent trop vite.

### Architecture centrée skill

Les workflows complexes sont implémentés directement comme de grosses skills d'orchestration.

Rejetée comme architecture principale : les skills doivent rester des primitives réutilisables et ne doivent pas porter le cycle de vie persistant d'un workflow ni l'état applicatif.

### Workflows codés en dur

Chaque workflow est implémenté directement dans le code applicatif.

Rejetée par défaut : le comportement d'un workflow doit être inspectable, éditable et versionné indépendamment du runtime.

## Validation

Cette décision sera considérée réussie lorsqu'Agentic Suite pourra exécuter une vraie session `bugfix` qui :

1. part d'un rapport de bug incomplet,
2. mène une découverte interactive,
3. persiste le contexte collecté,
4. avance vers l'investigation sans manipulation manuelle de l'état,
5. enregistre un diagnostic,
6. exécute un correctif,
7. valide le résultat,
8. atteint `done`,
9. peut être interrompue et reprise en cours de route.

## Décisions à suivre

De futures ADR pourront définir :

- le schéma YAML des workflows,
- le format de persistance des sessions,
- la configuration des rôles et capacités,
- les adaptateurs de fournisseurs,
- les contrats d'invocation de skills,
- les frontières d'approbation humaine,
- l'architecture de l'interface.
