# ADR 0003 — Précisions : évaluateur explicite, état initial, portée des références

- **Statut :** Acceptée
- **Date :** 2026-09-02
- **Remplace :** aucune
- **Précise :** ADR 0003 (schéma déclaratif de workflow)

## Contexte

Le workflow `bugfix` v1 a dû trancher par convention provisoire (C3, C5, C6 de `workflows/v1/DECISIONS.md`) trois points que l'ADR 0003 laisse ouverts :

- **C3** — la contradiction interne entre ADR 0003 D9 (« défaut `actor`, `evaluator` obligatoire pour `fix` ») et la section « Alternatives considérées » de la même ADR (« évaluateur = acteur pour tous les états sauf `fix` rejeté »).
- **C5** — l'absence de toute indication sur l'état initial d'une session.
- **C6** — l'ambiguïté de l'espace de noms `context.<field_id>` (état ou session ?).

La présente ADR précise l'ADR 0003 sur ces trois points. Elle ne crée aucun nouveau mécanisme — elle comble des silences et tranche une contradiction interne.

## P1. Évaluateur explicite sur tous les états non terminaux (C3)

**Précision.** Pour les états non terminaux d'un workflow, `evaluated_by:` doit être déclaré explicitement. La valeur par défaut `actor` de l'ADR 0003 D9 reste valide mais n'est plus implicite — sa présence doit figurer dans le YAML.

**Justification.** L'ADR 0003 D9 fixe le défaut à `actor` mais rejette « évaluateur = acteur pour tous les états sauf `fix` » comme incohérent. La décision finale n'est pas tranchée : le défaut peut être `actor` ou `evaluator`, mais l'auteur du workflow doit faire le choix consciemment.

Pour `bugfix` v1, le choix est `evaluated_by: evaluator` sur les quatre états non terminaux (`discovery`, `investigation`, `fix`, `validation`). Ce choix reflète l'alignement avec le motif de rejet de l'alternative.

**Conséquence opérationnelle.** Un appel d'agent supplémentaire par transition sur tous les états, pas seulement sur `fix`. Coût déjà identifié comme conséquence négative de l'ADR 0002.

**Premier assouplissement à envisager.** Si le coût s'avère prohibitif en Phase 4, retirer `evaluated_by` de `discovery` est le candidat : c'est l'état le plus pauvre en jugement subjectif, sa sortie étant majoritairement portée par un check de complétude (`discovery_context_present`).

## P2. État initial déclaré au niveau du workflow (C5)

**Précision.** Le schéma déclare une clé `initial_state:` au niveau du workflow, obligatoire. Sa valeur est un `states[].id` qui n'est ni `terminal: true` ni déclaré comme `escape_state`.

**Justification.** `concepts.md` précise que « l'ordre des états dans la liste ne porte pas de sémantique ». Aucune ADR ne dit alors dans quel état une session démarre. Le runtime a besoin d'un point d'entrée non ambigu.

**Note.** L'état `Reported` du diagramme du README n'existe pas comme état du workflow. Le rapport initial est un champ de contexte de `discovery` (`original_report` dans `bugfix.yaml`), conservé brut pour permettre de détecter les glissements de sens entre le rapport et sa reformulation. Un état sans contrat propre n'a pas de raison d'exister dans la machine.

## P3. Portée des références de contexte (C6)

**Précision.** L'espace de noms `context.<field_id>` est **la session**, pas l'état. Un état peut citer comme preuve n'importe quel champ de contexte déjà collecté par un état antérieur de la même session.

**Justification.** `concepts.md` range le contexte utilisateur et le contexte produit par les agents dans la session, non dans l'état. Aligner la sémantique des preuves avec ce rangement évite une incohérence.

**Contrainte induite.** Le linter vérifie qu'un champ cité est *atteignable* : déclaré par un état situé sur au moins un chemin menant à l'état citant. Une preuve citée mais jamais collectée sur aucun chemin est un défaut de définition au même titre qu'une assertion sans preuve (cf. ADR 0003 D4).

## Conséquences

### Positives

- C3, C5, C6 cessent d'être des conventions provisoires ; le workflow `bugfix` v1 est conforme aux ADR 0003 + 0007 + présentes précisions.
- La contrainte d'atteignabilité (P3) ferme une classe d'erreurs de définition : citer une preuve qui ne peut pas exister dans la session considérée.

### Négatives

- `evaluated_by: evaluator` sur tous les états non terminaux coûte un appel d'agent supplémentaire par transition sur tous les workflows. Si le coût se révèle excessif, l'assouplissement est local et explicite (P1).
- La contrainte d'atteignabilité (P3) demande au linter de calculer le graphe des transitions et de vérifier pour chaque `evidence_from: context.<id>` que `<id>` est déclaré par au moins un état atteignable. Travail de linter réel, mais limité à la phase de chargement.

## Alternatives considérées

**Laisser C3, C5, C6 comme conventions provisoires ad vitam.** Rejeté : contredit la règle de fermeture de l'ADR 0003 (« ajouter un mécanisme modifiant le schéma exige une ADR »).

**Rendre `evaluated_by: evaluator` le nouveau défaut global.** Rejeté : modifie la décision de l'ADR 0003 D9 sans nécessité ; le schéma reste neutre et le choix conscient est préférable à un défaut arbitraire.

**Interdire totalement les transitions qui réutilisent un contexte d'un état antérieur.** Rejeté : empêche le pattern légitime où une décision d'état N s'appuie sur une investigation d'état M.

## Validation

Cette décision est considérée comme réussie lorsque :

1. Le linter refuse un workflow dont un état non terminal omet `evaluated_by:`.
2. Le linter refuse un workflow sans `initial_state:` ou avec un `initial_state:` invalide.
3. Le linter refuse une preuve `context.<field_id>` citée par un état qui ne peut pas atteindre l'état qui produit `<field_id>` sur aucun chemin de la session.
4. `bugfix.yaml` v1 passe le lint avec 0 erreur, 0 avertissement, sans modification de son contenu.