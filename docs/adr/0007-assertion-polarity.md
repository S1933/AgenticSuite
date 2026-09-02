# ADR 0007 : Polarité des assertions de transition

- **Statut :** Acceptée
- **Date :** 2026-09-02
- **Remplace :** aucune
- **Précise :** ADR 0003 D5 (transitions)

## Contexte

L'ADR 0003 D5 impose que `on_failure.when:` cite un `assertion.id` qui doit être **vrai** pour déclencher la transition d'échec. Une transition d'échec est donc déclenchée par une assertion vraie, ce qui pose une question de polarité : qu'est-ce qu'une assertion d'échec ?

Le `bugfix.yaml` provisoire (v1) a dû trancher sans ADR — convention C2 de `workflows/v1/DECISIONS.md`. La présente ADR ratifie et formalise ce que la convention établissait, et ferme un trou de garantie identifié par le plan d'exécution : « une assertion peut être vraie en citant un check en échec ».

Trois décisions sont nécessaires : où vit la distinction nominal/échec, comment le schéma empêche les noms d'assertions qui réintroduisent la négation, et comment garantir qu'une transition d'échec a une condition de sortie.

## Décision

### D1. La distinction nominal/échec vit dans le runtime, pas dans le schéma

Une assertion dans le schéma YAML est juste une assertion. Aucune clé `failure_assertion:` ou équivalent n'est ajoutée au schéma.

Le runtime applique la distinction suivante lors de l'évaluation d'une transition :
- Une assertion citée par un `on_failure.when:` de l'état est une **assertion d'échec**.
- Une assertion non citée par un `on_failure.when:` de l'état est une **assertion nominale**.
- Une même assertion ne peut pas être à la fois nominale et d'échec.

Cette classification est dérivée du graphe des transitions de l'état. Elle ne demande aucune information supplémentaire dans le YAML.

### D2. Ordre d'évaluation des transitions

À chaque tentative de sortie d'un état, le runtime évalue dans l'ordre suivant :

1. Les assertions d'échec, dans leur ordre de déclaration dans `assertions:`.
2. Si une assertion d'échec est vraie, sa transition d'échec est déclenchée. La transition nominale n'est pas tentée.
3. Si aucune assertion d'échec n'est vraie, la sortie vers `next:` exige que tous les `checks:` passent et que toutes les assertions nominales soient vraies.

Une transition vers `blocked` ou un `escape_state` est traitée comme une transition d'échec : elle n'a lieu que si une assertion d'échec le justifie (ou si un budget est dépassé, ce qui est un invariant de runtime, cf. ADR 0003 D6).

### D3. Contrainte structurelle sur les noms d'assertions

Le linter refuse les identifiants d'assertions qui réintroduisent la polarité déguisée. La règle de détection est :

Un identifiant d'assertion est refusé s'il correspond à la regex suivante :

```
^.*_(is_not|not_|does_not|cannot|fails|failed|invalid|wrong|broken)_.*$
```

Cette liste est volontairement non exhaustive — elle vise les patterns les plus courants. Le linter complète la détection par une heuristique de mot-clé : présence de `not`, `cannot`, `fails`, `invalid`, `wrong`, `broken` immédiatement après un séparateur `_`.

L'erreur de lint est explicite : « nom d'assertion à polarité déguisée ; reformuler positivement (ex. `report_is_not_a_bug` est correct — il nomme la condition constatée, pas la négation d'une assertion nominale) ».

### D4. Cohérence entre `on_failure` et assertions d'échec

Le schéma exige qu'au moins une assertion d'échec existe dans l'état pour chaque `on_failure.when:` cité. Plus précisément : pour chaque identifiant cité dans un `on_failure.when:`, il existe une assertion portant ce même `id` dans `assertions:`.

Cette contrainte est vérifiée au chargement du workflow. Elle ne s'applique pas aux transitions vers `escape_state` déclenchées par dépassement de budget (invariants, pas assertions).

### D5. Convention de nommage

Les assertions d'échec nomment la **condition constatée**, jamais la négation d'une assertion nominale.

| Interdit (négation d'une assertion nominale) | Correct (condition constatée) |
|---|---|
| `regression_is_not_verified` | `diagnosis_is_invalidated` |
| `root_cause_is_not_identified` | `no_root_cause_found` |
| `change_does_not_address_cause` | `implementation_invalidates_diagnosis` |
| `fix_is_not_implementable` | `fix_cannot_be_implemented` |

Le critère de distinction : l'assertion correcte est vraie **quand** la situation d'échec est constatée, indépendamment de toute autre assertion nominale. La négation d'une assertion nominale est vraie quand cette dernière est fausse — ce qui lie deux jugements et reproduit le pattern d'auto-justification que l'ADR 0002 combat.

## Précision sur ADR 0003

L'ADR 0003 D5 dit « le champ `when:` de `on_failure:` référence un `assertion.id` ». La présente ADR précise que cet `assertion.id` est implicitement classifié comme assertion d'échec par le runtime (D1), évalué en premier dans l'ordre de déclaration (D2), et assujetti à une contrainte de nommage (D3) et de cohérence (D4). ADR 0003 reste valide ; ses références aux transitions sont précisées ici, non corrigées.

## Conséquences

### Positives

- Le trou de garantie identifié au plan (« une assertion peut être vraie en citant un check en échec ») est fermé par construction : la polarité est dans la convention d'évaluation, pas dans un mécanisme ad hoc.
- Le schéma reste neutre sur la distinction nominal/échec, ce qui évite une nouvelle clé et respecte la règle de fermeture de l'ADR 0003 D3.
- La contrainte structurelle sur les noms empêche la réintroduction de la négation déguisée par inadvertance.
- La cohérence `on_failure` / assertion d'échec garantit que toute transition d'échec a une condition explicite.

### Négatives

- L'ordre d'évaluation « assertions d'échec d'abord » peut produire des transitions d'échec non souhaitées si l'auteur a mal classifié (par exemple une assertion d'échec qui se révèle vraie dans un cas nominal). Le remède est la rigueur du nommage (D5).
- La regex de détection de polarité (D3) n'est pas exhaustive ; des formulations nouvelles peuvent passer à travers. Le linter signale en warning ce qu'il ne peut pas classifier.
- Le runtime doit construire la liste des assertions d'échec à chaque évaluation, ce qui est un coût négligeable mais réel pour de longs états.

## Alternatives considérées

**Ajouter une clé `failure_assertion: true` dans le schéma.** Rejeté : modifie le schéma sans nécessité ; le runtime peut dériver la distinction du graphe de transitions (D1).

**Permettre la polarité mixte (noms négatifs autorisés).** Rejeté : rouvre la porte du langage d'expressions par la fenêtre, exactement le piège que la règle de fermeture cherche à éviter.

**Documenter le trou sans le fermer.** Rejeté : c'est la troisième option du plan d'exécution. Le plan laissait la décision ouverte ; la présente ADR tranche.

**Interdire tout `on_failure` sans budget dépensé.** Rejeté : confond le dépassement de budget (invariant de runtime, ADR 0003 D6) avec une transition d'échec logique (assertion d'échec vraie).

## Validation

Cette décision est considérée comme réussie lorsque :

1. Une assertion à polarité déguisée (ex. `regression_is_not_verified`) est refusée au chargement du workflow avec un message d'erreur explicite.
2. Une transition d'échec se déclenche avant une transition nominale quand son assertion d'échec est vraie.
3. Un `on_failure.when: X` sans assertion `id: X` dans le même état est refusé au chargement.
4. Sur 10 sessions bugfix, aucune transition d'échec n'est déclenchée par une assertion négative réintroduite par inadvertance.
5. Le linter signale (warning) les noms d'assertions qui matchent les patterns usuels de négation.