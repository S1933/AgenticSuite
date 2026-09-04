# ADR 0003 — Précision : marqueur d'inconnu documenté dans le contexte

- **Statut :** Acceptée
- **Date :** 2026-09-02
- **Remplace :** aucune
- **Précise :** ADR 0003 D1 (champs de contexte)

## Contexte

L'ADR 0003 D1 dit qu'un champ est satisfait s'il porte une valeur non vide, **ou s'il est
marqué `inconnu` avec une raison explicite**. L'implémentation matérialise ce marqueur par
un dict `{"_unknown": true, "_reason": "<texte>"}` dans `verification/checks.py`, mais
cette forme n'est écrite nulle part : c'est une convention de code sans ADR.

Le second workflow (`feature`) va l'utiliser (champs `required: true` laissés inconnus
avec `max_unknown`). Avant que deux workflows s'appuient dessus, la forme exacte du
marqueur doit être ratifiée — et son invariant renforcé : un `_unknown` sans `_reason`
non vide n'est pas un inconnu documenté, c'est une valeur malformée qui ne satisfait pas
le champ.

## Décision

### P1. Forme du marqueur

Un champ de contexte marqué inconnu porte la valeur :

```yaml
field_id:
  _unknown: true
  _reason: "l'utilisateur n'a pas accès à l'environnement de production"
```

- `_unknown` doit être `true` (booléen strict).
- `_reason` est obligatoire et doit être une chaîne non vide. La raison est ce qui
  distingue un inconnu documenté d'un champ simplement absent (ADR 0003 D1).
- `_unknown: true` sans `_reason` non vide = valeur **malformée** : le check
  `context_fields_present` échoue avec un message nommant le champ et la raison manquante,
  et le champ n'est pas compté comme inconnu.

### P2. Comptage

Un champ portant le marqueur valide est compté dans les inconnus du check
(`max_unknown` de l'ADR 0003 D1 le borne). Il est traité exactement comme un champ
absent, à une différence près : sa raison est enregistrée dans le contexte, donc
auditable.

## Conséquences

### Positives

- La convention a un point de vérité unique et un invariant testé (raison obligatoire).
- Le `max_unknown` devient utilisable sans ambiguïté par les deux workflows : un inconnu
  s'écrit toujours `{"_unknown": true, "_reason": ...}`, jamais autrement.
- Les champs marqués inconnus restent présents dans le contexte (audit) au lieu de
  disparaître.

### Négatives

- Un dict `{"_unknown": true}` seul (raison oubliée) fait désormais échouer le check au
  lieu de compter silencieusement comme inconnu. C'est le comportement voulu, mais il
  peut surprendre un workflow écrit avant cette précision — aucun workflow actuel ne
  l'utilise.

## Alternatives considérées

**N'autoriser que l'absence de champ (pas de marqueur).** Rejeté : perd la raison, et
`max_unknown` de l'ADR 0003 D1 suppose des inconnus documentés, pas des trous muets.

**Marqueur string `"__unknown__"`.** Rejeté : une chaîne sentinelle peut être une valeur
légitime par accident ; le dict est structurellement non-ambigu.

## Validation

Cette décision est considérée comme réussie lorsque :

1. `check_context_fields_present` refuse `{"_unknown": true}` sans `_reason` non vide.
2. `{"_unknown": true, "_reason": "..."}` est compté dans `max_unknown` (testé).
3. Le workflow `feature` (qui déclare `max_unknown: 1` sur intake) peut utiliser le
   marqueur sans ni erreur de code ni erreur de schéma.