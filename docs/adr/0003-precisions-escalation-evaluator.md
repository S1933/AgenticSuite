# ADR 0003 — Précision : évaluation des triggers d'escalade sur les états à évaluateur `actor`

- **Statut :** Acceptée
- **Date :** 2026-09-02
- **Remplace :** aucune
- **Précise :** ADR 0003 D7 (déclencheurs d'escalade) et D9 (évaluateur)

## Contexte

L'ADR 0003 D7 déclare que les quatre triggers d'escalade (`irreversible_action`,
`security_relevant_change`, `human_decision_required`, `context_contradiction`)
sont « évalués par l'évaluateur à chaque transition », et que « l'ADR 0002 §4
interdit que l'acteur soit juge de ces triggers ».

L'ADR 0003 D9 fixe pourtant le **défaut** `evaluated_by: actor`, et la précision
P1 du fichier `0003-precisions-evaluator-initial-state-context-scope.md`
maintient ce défaut comme valide, en prévoyant explicitement un assouplissement
futur : « retirer `evaluated_by` de `discovery` est le premier assouplissement à
envisager ».

Il y a donc une zone grise : sur un état qui n'annonce pas `evaluated_by:
evaluator` (défaut `actor`), **qui évalue les triggers d'escalade** ? Si c'est
l'acteur, la promesse de D7 (« jamais l'acteur ») et de l'ADR 0002 §4 est
invalidée de fait sur ces états. Si c'est un évaluateur, il faut le dire, car
cela coûte un appel d'agent supplémentaire même sur les états à évaluateur
`actor` — un coût que le workflow doit pouvoir anticiper.

`bugfix.yaml` v1 ne rencontre pas le problème aujourd'hui (C3 impose
`evaluated_by: evaluator` sur tous les états non terminaux), mais l'ADR doit
trancher pour les workflows futurs et pour l'assouplissement P1 déjà anticipé.

## Décision

### P4. Les triggers d'escalade sont toujours évalués par un évaluateur distinct de l'acteur

**Précision.** `evaluated_by:` ne couvre que l'évaluation des assertions de
sortie **de l'état**. Les triggers d'escalade déclarés dans `escalate_when:`
sont, eux, **toujours** évalués par un évaluateur différent de l'acteur de
l'état, quelle que soit la valeur de `evaluated_by`.

En particulier, sur un état à `evaluated_by: actor` (défaut D9 ou
assouplissement P1) :

1. Les assertions de sortie de l'état sont évaluées par l'acteur, comme le
   déclare `evaluated_by`.
2. Les quatre triggers d'escalade sont évalués par un évaluateur distinct, à
   chaque transition, dans les mêmes conditions que sur un état à
   `evaluated_by: evaluator`.
3. L'acteur n'est jamais juge des triggers d'escalade, même quand il est juge
   des assertions de sortie.

**Justification.** L'ADR 0002 §4 ne distingue pas les états : l'interdiction
« l'acteur n'est pas juge » porte sur l'auto-déclaration des escalades. Un
trigger d'escalade est précisément le cas où l'acteur annoncerait qu'il faut le
stopper ou le surveiller — l'auto-évaluation y serait la plus biaisée. Rendre
cette garantie dépendante de `evaluated_by` créerait un contournement trivial :
déclarer un état en `actor` pour neutraliser les escalades.

**Coût assumé.** Un appel d'évaluateur par transition sur les états à
`evaluated_by: actor`, en plus de l'évaluation des assertions par l'acteur.
C'est le prix de la garantie D7 ; il ne peut pas être économisé en changeant
`evaluated_by`. Ce coût doit figurer dans la décision d'assouplissement P1 : un
état en `actor` n'économise pas l'appel d'évaluateur — il n'économise que
l'évaluation des assertions.

**Limite.** Les triggers d'escalade sont des jugements (D7 « point
d'honnêteté ») : cette précision garantit *qui* juge, pas que le jugement est
fiable. La seule barrière mécanique reste le budget (ADR 0003 D6).

## Conséquences

### Positives

- La garantie « l'acteur n'est jamais juge des escalades » devient
  inconditionnelle, quelle que soit la valeur de `evaluated_by`.
- L'assouplissement P1 (retirer `evaluated_by` d'un état) garde l'évaluateur
  sur les escalades : le workflow peut anticiper le coût réel.
- Le runtime a une règle d'appel simple : les assertions ont l'évaluateur de
  `evaluated_by`, les triggers d'escalade ont toujours un évaluateur distinct.

### Négatives

- Sur un état `actor`, le runtime doit quand même résoudre un évaluateur pour
  les escalades : le workflow doit pouvoir nommer cet évaluateur. L'ADR 0005
  (rôles, capacités, fournisseurs) devra garantir qu'un rôle évaluateur est
  toujours résolvable, indépendamment des états.

## Alternatives considérées

**Étendre `evaluated_by` aux escalades (acteur juge tout).** Rejeté : détruit
la garantie D7 sur les états `actor` et réintroduit l'auto-justification que
l'ADR 0002 §4 combat.

**Interdire `evaluated_by: actor` totalement.** Rejeté : contredit la lettre de
D9 (défaut `actor`) et l'engagé de P1. La présente précision garde le défaut et
borne seulement la portée de `evaluated_by`.

## Validation

Cette décision est considérée comme réussie lorsque :

1. Le test d'invariant D9 (évaluateur distinct de l'acteur) couvre aussi les
   triggers d'escalade sur un état à `evaluated_by: actor`.
2. Un workflow qui déclare `evaluated_by: actor` sans pouvoir résoudre un
   évaluateur (ADR 0005) est refusé au chargement, pas au milieu d'une session.
3. `bugfix.yaml` v1 (déjà `evaluated_by: evaluator` partout) passe le lint sans
   modification.