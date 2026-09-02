# ADR 0002 : Critères de sortie et chemins d'échec

- **Statut :** Acceptée
- **Date :** 2026-09-02
- **Remplace :** aucune
- **Précise :** ADR 0001 (architecture centrée workflow)

## Contexte

L'ADR 0001 a posé l'autonomie sous contrat : un agent peut faire avancer une session lorsque les critères de sortie de l'état courant sont satisfaits. Elle n'a pas défini deux choses dont cette autonomie dépend.

**Comment un critère est évalué.** Des critères comme `problem_is_understood` sont des prédicats en langage naturel. Si l'agent qui a produit le travail décide aussi si le critère est rempli, le système reproduit le mode d'échec que rejette le principe 12 de la philosophie : déclarer le succès parce que du travail a eu lieu, et non parce qu'une preuve existe.

**Ce qui se passe quand un critère ne peut pas être satisfait.** La chaîne d'états `bugfix` de l'ADR 0001 n'avance que vers l'avant. Le travail réel sur un bug produit des issues que cette chaîne ne sait pas exprimer : le bug n'est pas reproductible, aucune cause racine n'est trouvée, le correctif ne survit pas à la validation, ou la découverte révèle que ce n'est pas un bug. Une machine à états sans chemin d'échec se bloque ou invente une manière d'avancer.

Ces deux manques touchent la même garantie. L'autonomie n'est acceptable que si avancer est vérifiable et si ne pas avancer est une issue légitime.

## Décision

### 1. Deux natures de critères de sortie

Tout critère de sortie est soit une **vérification** (*check*), soit une **assertion**.

Une **vérification** est déterministe et évaluée par le runtime, jamais par un agent. Exemples : un champ de contexte requis est présent et non vide, un artefact nommé existe, une commande sort avec le code 0.

Une **assertion** relève du jugement et est évaluée par un agent.

Un état ne peut pas s'appuyer sur une assertion lorsque la même condition est exprimable comme une vérification. La vérification est préférée partout où la condition se réduit à un fait.

### 2. Le contexte requis transforme le jugement en checklist

La plupart des critères de type découverte ne sont pas réellement des jugements. `problem_is_understood` est un prédicat dérivé d'un ensemble de champs à collecter.

Chaque état déclare les champs de contexte qu'il exige avant de pouvoir être quitté. Un champ peut être rempli par un « inconnu, et voici pourquoi » explicite, mais il ne peut pas rester vide. La vérification porte sur la présence des champs ; l'assertion, s'il en reste une, ne couvre que ce qui est réellement subjectif.

### 3. Une assertion exige une preuve

Une assertion ne peut être vraie qu'en s'appuyant sur quelque chose de déjà enregistré dans la session : un champ de contexte collecté, un artefact, une sortie de commande, un diagnostic.

Une assertion qui ne cite rien est fausse. Une affirmation produite au moment de l'évaluation n'est pas une preuve.

### 4. L'évaluateur n'est pas l'acteur

Les assertions sont évaluées dans une étape séparée dont l'entrée est l'enregistrement de session, pas la conversation de travail qui l'a produit.

Le workflow peut confier l'évaluation à un autre rôle. C'est obligatoire pour les états qui modifient le code, et optionnel ailleurs. C'est le raisonnement du principe 13 de la philosophie, appliqué aux transitions plutôt qu'à la revue de code.

### 5. Les états d'échec sont de premier plan

Les états suivants s'ajoutent au chemin nominal.

`blocked` — non terminal. La session ne peut pas avancer et attend un humain. Elle enregistre ce qui manque et ce qui la débloquerait. Une session bloquée est reprenable.

`abandoned` — terminal. Aucun correctif n'a été livré. Enregistre pourquoi, et ce qui a été appris.

`reclassified` — terminal pour ce workflow. La découverte a conclu que le rapport n'est pas un bug : comportement attendu, demande de fonctionnalité, ou cause externe. Enregistre la conclusion et les preuves.

### 6. Les transitions arrière sont légitimes et comptées

Un workflow peut déclarer des transitions arrière. Pour `bugfix`, au minimum :

- `validation → investigation` lorsqu'une vérification de régression ou de complétion échoue,
- `investigation → discovery` lorsque les preuves montrent qu'il manque du contexte requis.

Toute transition arrière incrémente un compteur de tentatives sur l'état cible.

### 7. Des budgets, pas des boucles

Un workflow déclare un nombre maximum de tentatives par état et un nombre maximum de transitions par session.

Dépasser l'un ou l'autre force une transition vers `blocked`. Le système ne boucle jamais silencieusement et n'abaisse jamais un critère pour le faire passer.

### 8. Escalade obligatoire

Quels que soient les critères, une session passe à `blocked` lorsque :

- un budget est dépassé,
- la prochaine action est irréversible ou destructive,
- le changement touche à la sécurité,
- l'agent identifie une décision produit, architecturale ou métier qui appartient à l'humain,
- le contexte collecté contient une contradiction que la session ne permet pas de trancher.

### 9. Toute transition est enregistrée

Une transition n'est valide que si la session enregistre : l'état d'origine, l'état cible, l'horodatage, les critères évalués, la nature de chacun (vérification ou assertion), les preuves référencées, le rôle évaluateur et le compteur de tentatives.

Une transition non enregistrée est invalide. C'est ce qui rend l'autonomie auditable plutôt que consentie sur parole.

## Conséquences

### Positives

- Avancer devient vérifiable au lieu d'être affirmé.
- Ne pas avancer devient une issue légitime et enregistrée, plutôt qu'un blocage muet ou une invention.
- Les budgets bornent le coût et la durée d'une session autonome.
- L'enregistrement des transitions offre une surface de débogage concrète quand un workflow se comporte mal.
- Les checklists de contexte requis rendent la découverte testable sans runtime.

### Négatives

- Les définitions de workflow deviennent plus verbeuses : champs, vérifications, budgets et transitions arrière doivent tous être écrits.
- Séparer l'évaluateur de l'acteur coûte un appel d'agent supplémentaire par transition.
- Décider quelles conditions se réduisent à des vérifications est un vrai travail de conception, état par état.
- Des champs requis mal choisis transformeront la découverte en formulaire au lieu d'un entretien.

## Alternatives considérées

**Approbation humaine à chaque transition.** Rejetée : elle supprime l'autonomie qui motive le projet et rend les sessions longues inutilisables.

**Auto-évaluation par l'agent seul.** Rejetée : c'est la conception implicite actuelle, et la raison d'être de cette ADR.

**Vérifications déterministes uniquement.** Rejetée : des conditions comme « une cause racine plausible est identifiée » ne se réduisent pas à une vérification sans perdre leur sens.

**Scores de confiance sur les critères.** Rejetée : la confiance rapportée par un modèle n'est pas calibrée, et un seuil numérique donnerait l'apparence de la rigueur sans la substance.

**Échec traité en texte libre à la fin d'une session.** Rejetée : l'échec doit être un état pour être reprenable, comptable et visible au même endroit que la progression.

## Validation

Cette décision sera considérée réussie lorsque, sur des sessions réelles :

1. un bug non reproductible se termine en `blocked` avec l'élément manquant explicité, sans qu'aucun correctif ne soit proposé,
2. une validation échouée renvoie la session en `investigation` avec un compteur incrémenté, plutôt qu'une seconde déclaration de succès,
3. un rapport qui s'avère ne pas être un bug se termine en `reclassified`,
4. le dépassement du budget de tentatives produit `blocked` plutôt que de nouvelles tentatives,
5. chaque changement d'état dans l'enregistrement de session porte ses preuves.

## Décisions à suivre

- ADR 0003 : schéma YAML des workflows, incluant la syntaxe des champs, vérifications, assertions, budgets et transitions.
- ADR 0004 : format de persistance des sessions et enregistrement des transitions.
- Une ADR ultérieure sur les contrats d'invocation de skills, dès qu'un état devra appeler une skill dans le cadre d'une vérification.
