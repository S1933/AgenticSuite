# Philosophie

Agentic Suite ne cherche pas à construire l'agent de code autonome le plus intelligent.

Il cherche à construire une meilleure manière de travailler avec des agents.

Le projet considère les modèles, les harnais d'agents et les abonnements comme une infrastructure remplaçable. Ce qui dure, c'est le workflow d'ingénierie qui les entoure.

## 1. Le workflow d'abord

L'abstraction principale est le workflow.

L'utilisateur doit penser :

> Je lance un workflow de bugfix.

Et non :

> Je lance le modèle X dans l'outil Y avec le prompt Z.

Les agents sont des ressources d'exécution.

Les modèles sont des ressources d'exécution.

Les skills sont des primitives d'exécution.

Le workflow donne à ces ressources un but, un ordre et un contexte.

## 2. Le contexte fait partie du travail

Les agents reçoivent souvent des demandes incomplètes, ambiguës ou mal structurées.

Commencer l'implémentation immédiatement est donc une erreur.

Agentic Suite traite l'acquisition de contexte comme une phase de workflow à part entière.

Pour un bugfix, le workflow commence par la découverte.

L'agent interroge l'utilisateur une question à la fois, adapte la question suivante aux réponses précédentes, et continue jusqu'à ce que le problème soit suffisamment compris.

La qualité de l'exécution dépend de la qualité du contexte.

## 3. Demander avant de faire une hypothèse importante

Les agents sont bons en implémentation.

Ils sont moins fiables lorsqu'ils prennent silencieusement des décisions produit, architecturales, métier ou opérationnelles à la place du développeur.

Lorsqu'une décision change matériellement la solution, le système doit préférer une clarification explicite à une hypothèse cachée.

Cela ne signifie pas exiger une validation humaine à chaque transition.

Cela signifie distinguer :

- le contexte manquant qui doit être clarifié,
- les décisions d'exécution que l'agent peut prendre seul,
- les décisions de conception importantes qui appartiennent à l'humain.

## 4. Déclaratif plutôt qu'impératif

Un workflow doit être lisible sans lire le code du runtime.

Une définition de workflow doit décrire :

- ses états,
- ses responsabilités,
- ses rôles,
- ses critères de transition,
- ses artefacts attendus.

YAML est la représentation initiale parce qu'elle est lisible, diffable, portable, et facile à éditer aussi bien par un humain que par un agent.

Le runtime interprète le workflow.

Le workflow ne doit pas être embarqué dans le runtime.

## 5. Des rôles plutôt que des noms de modèles

Un workflow doit demander un `investigator`, un `implementer` ou un `reviewer`.

Il ne doit pas exiger un modèle commercial précis.

Les modèles changent vite.

Les tarifs changent vite.

Les abonnements changent vite.

Les fournisseurs disparaissent.

Un workflow stable doit survivre à tout cela.

Les modèles concrets appartiennent à la configuration.

Les responsabilités appartiennent aux workflows.

## 6. Des capacités plutôt que des fournisseurs

Un rôle peut exiger des capacités telles que :

- le raisonnement,
- l'édition de code,
- l'accès au dépôt,
- la recherche web,
- l'exécution d'outils,
- un contexte long,
- une latence faible,
- un coût faible.

Les capacités forment une couche intermédiaire entre les rôles d'un workflow et les fournisseurs.

Cela permet de réaffecter un rôle sans changer la sémantique du workflow.

## 7. Les skills sont des primitives, pas des workflows

Une skill doit faire une seule chose réutilisable, et bien.

Exemples :

- diagnostiquer un bug,
- relire du code,
- rédiger une spécification,
- créer des tickets,
- vérifier une complétion,
- utiliser un worktree,
- mener une revue de sécurité.

Les comportements de plus haut niveau appartiennent à Agentic Suite.

Agentic Suite compose des skills en workflows.

Cette séparation garde le registre de skills réutilisable et l'empêche de devenir un framework applicatif.

## 8. Un comportement répété doit devenir réutilisable

Un comportement répété en une étape peut devenir un raccourci, un préréglage ou une commande.

Un comportement répété en plusieurs étapes doit devenir un workflow.

Une logique d'exécution répétée et spécifique à un domaine peut devenir une skill.

L'objectif est de réduire la glue manuelle tout en gardant les abstractions compréhensibles.

## 9. Un état explicite vaut mieux qu'un comportement d'agent invisible

Un agent qui travaille longtemps ne doit pas ressembler à une boîte noire.

Un workflow doit montrer où il en est :

```text
Discovery → Investigation → Fix → Validation → Done
```

L'état apporte :

- de l'observabilité,
- de la reprise,
- du débogage,
- une automatisation prévisible,
- un meilleur modèle mental pour l'utilisateur.

L'utilisateur doit pouvoir comprendre ce que fait le système sans relire tout l'historique de conversation.

## 10. Les sessions sont persistantes

Une exécution de workflow est une session, pas un prompt jetable.

Une session doit préserver :

- le contexte,
- les décisions,
- l'historique,
- les artefacts,
- l'état courant.

Un développeur doit pouvoir s'arrêter et reprendre plus tard sans reconstruire tout le problème.

La persistance est donc une exigence de fond, même si l'implémentation initiale reste simple.

## 11. Transitions autonomes, contrats explicites

L'utilisateur ne doit pas avoir à approuver chaque transition normale.

Chaque état de workflow doit plutôt définir des critères de sortie clairs.

Si les critères sont satisfaits, l'agent peut avancer automatiquement.

Cela donne des frontières à l'autonomie.

L'objectif n'est pas une autonomie illimitée.

L'objectif est une **autonomie sous contrat**.

## 12. Vérification avant complétion

Un agent ne doit pas déclarer le succès parce qu'il a modifié du code.

La complétion exige des preuves.

Selon le workflow, ces preuves peuvent inclure :

- une reproduction qui ne échoue plus,
- des tests pertinents qui passent,
- des vérifications de régression,
- du lint ou de l'analyse statique,
- une revue,
- des contrôles de sécurité,
- des limitations documentées.

« Terminé » est un état de workflow assorti de critères, pas une phrase générée par un modèle.

## 13. Changer de perspective quand la revue compte

L'agent qui a implémenté un changement n'est pas automatiquement le meilleur relecteur de ce changement.

Pour un travail à risque moyen ou élevé, Agentic Suite doit permettre d'utiliser un autre rôle, un autre agent ou un autre modèle pour la revue.

La revue croisée entre modèles peut être utile, mais les boucles de revue récursives sont à éviter.

Plus de revue n'est pas automatiquement une meilleure revue.

## 14. Le parallélisme est une complexité optionnelle

Les agents multiples, les sous-agents, les worktrees et les architectures manager/worker sont puissants.

Ils sont aussi coûteux et complexes.

Agentic Suite ne doit introduire du parallélisme que là où il résout un problème démontré.

Une petite tâche doit rester petite.

Un workflow unique avec un seul chemin d'exécution actif est le bon point de départ.

## 15. Le contrôle humain se place au bon niveau

L'humain contrôle :

- l'intention,
- les arbitrages importants,
- l'architecture,
- la tolérance au risque,
- la responsabilité finale.

Le système prend en charge :

- l'exécution répétitive,
- la progression d'état,
- la préservation du contexte,
- la sélection des skills,
- les étapes de vérification,
- l'orchestration de routine.

Le but du système n'est pas de retirer le développeur.

Il est de lui permettre d'opérer à un niveau plus élevé.

## 16. Optimiser pour l'usage réel

Agentic Suite doit évoluer à partir de workflows réellement utilisés, pas d'exigences de plateforme imaginées.

La première implémentation ne supporte volontairement qu'un seul workflow : `bugfix`.

Le projet doit résister à l'ajout de :

- systèmes de plugins génériques,
- ordonnanceurs distribués,
- essaims multi-agents,
- interfaces complexes,
- schémas élaborés,

tant qu'un usage réel n'en démontre pas le besoin.

## 17. La portabilité est une fonctionnalité

Le projet doit rester utile même quand l'écosystème IA autour de lui change.

Un workflow créé aujourd'hui devrait idéalement rester compréhensible et adaptable plus tard.

Cela implique de préférer :

- le texte brut,
- le Markdown,
- le YAML,
- les contrats explicites,
- le stockage simple,
- les formats ouverts,
- les backends d'exécution interchangeables.

## 18. Le système doit rester compréhensible

L'ingénierie agentique devient vite un empilement d'agents qui pilotent des agents qui invoquent des skills qui lancent d'autres agents.

Agentic Suite doit résister aux indirections inutiles.

Un développeur doit pouvoir répondre à :

- Quel workflow tourne ?
- Quel état est actif ?
- Quel rôle est responsable ?
- Quelles skills sont utilisées ?
- Pourquoi le workflow peut-il avancer ?
- Quels artefacts ont été produits ?

Si ces questions deviennent difficiles, l'architecture est devenue trop complexe.

## Résumé

Agentic Suite suit cette hiérarchie :

```text
Intention humaine
    ↓
Workflow
    ↓
État
    ↓
Rôle d'agent
    ↓
Skills
    ↓
Fournisseur / Modèle / Outils
```

Les couches hautes doivent rester stables.

Les couches basses ont le droit de changer.

Cette séparation est le fondement du projet.
