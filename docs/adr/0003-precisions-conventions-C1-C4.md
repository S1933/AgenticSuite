# ADR 0003 — Précision : ratification des conventions C1 et C4

- **Statut :** Acceptée
- **Date :** 2026-09-02
- **Remplace :** aucune
- **Précise :** ADR 0003 D3 (vocabulaire des vérifications) et D8 (artefacts)

## Contexte

Les ADR 0003, 0007 et les précisions sur l'évaluateur/état initial/portée ont ratifié
les conventions C2, C3, C5, C6 de `workflows/v1/DECISIONS.md`. Deux conventions restent
provisoires alors que le code et le workflow les encodent déjà :

- **C1** — les vérifications portent un `name`, pas un `id`. Encodé dans
  `runner.py` (`chk.get("name")`), `engine.py` (`_all_checks_pass`) et les fichiers
  `bugfix.yaml` / `feature.yaml` (tous les checks ont `name:`).
- **C4** — l'artefact implicite de sortie de commande s'écrit
  `command_output_<check_name>`. Encodé dans `runner.py` (construction de l'`aid`) et
  cité par les assertions de validation de `bugfix.yaml` (`artifacts.command_output_unit_tests_pass`).

`feature.yaml` va réutiliser ces deux conventions une seconde fois. Les ratifier après
le second workflow reviendrait à entériner ce qui existe déjà — la ratification précède
donc l'écriture du second workflow (règle de fermeture de l'ADR 0003 : un mécanisme
modifiant le schéma exige une ADR avant le code).

## Décision

### P1. Les vérifications portent un `name` (ratification de C1)

**Précision.** Chaque vérification d'un état porte un champ `name:`, snake_case,
unique dans l'état, et est référencée par `checks.<name>`. L'identifiant `id` est
réservé aux artefacts (ADR 0003 D8) et aux champs de contexte (D1) — les réutiliser
pour les vérifications provoquerait une collision de clé dans le même objet YAML.

Ce que cette ratification ne change pas : le vocabulaire fermé de D3, la forme de
`command_ref`, ni la règle de composition. Elle fige seulement le nom du champ
référencé par D4 (`checks.<check_name>`).

### P2. L'artefact implicite de sortie de commande est `command_output_<check_name>` (ratification de C4)

**Précision.** L'ADR 0003 D3 écrit `command_output<check_id>` sans séparateur.
Appliqué littéralement, `command_output` + `unit_tests_pass` donne
`command_outputunit_tests_pass`, illisible et hors snake_case. Le runtime produit
l'artefact sous le nom `command_output_<check_name>` (snake_case avec séparateur).
Le référencement suit D4 : `artifacts.command_output_unit_tests_pass`.

La création de cet artefact est un effet de bord du check `command_exit_zero`
(ADR 0003 D3 « sortie de commande ») : le runtime l'enregistre dans le journal de
session au même titre qu'un artefact produit, avec son propre cycle d'intégrité
(ADR 0004 D6).

## Conséquences

### Positives

- Le second workflow (`feature`) réutilise des conventions ratifiées, pas des
  conventions provisoires.
- `checks.<name>` et `artifacts.command_output_<check_name>` ont un statut ADR et un
  point de vérité unique (cette précision).
- Aucun changement de code : C1 et C4 étaient déjà encodées et testées ; la présente
  ADR les officialise.

### Négatives

- Rien : la ratification ne crée aucun mécanisme nouveau, elle fige l'existant.

## Alternatives considérées

**Attendre la ratification après le troisième workflow.** Rejeté : le second workflow
enracine la convention une seconde fois ; ratifier après revient à décrire plutôt qu'à
décider.

**Utiliser `id` pour les vérifications (annuler C1).** Rejeté : casserait
`runner.py`, `engine.py` et les deux workflows, avec collision de clé dans les objets
YAML mixtes.

**Écrire `command_output_<check_id>` avec le `name`.** Rejeté : la référence citée par
les assertions doit être stable et lisible ; le `name` du check est déjà l'identifiant
de référencement de D4.

## Validation

Cette décision est considérée comme réussie lorsque :

1. `bugfix.yaml` et `feature.yaml` passent le lint avec 0 erreur et 0 avertissement.
2. Une assertion de validation cite `artifacts.command_output_<check_name>` et le
   check correspondant, et le lint n'émet aucun message sur cette forme.
3. Le runtime produit bien l'artefact implicite sous ce nom lors d'un
   `command_exit_zero` (couvert par le test d'orchestrateur existant).