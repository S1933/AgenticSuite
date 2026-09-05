# ADR 0009 : Application des artefacts au repository de travail

- **Statut :** Acceptée
- **Date :** 2026-09-04
- **Précise :** ADR 0003 (D3 vocabulaire des vérifications), ADR 0005 (résolution command_ref)
- **Résout :** D5.9 (Lot 5) — l'état `fix` produit un artefact `patch`, mais le runtime ne l'applique jamais au filesystem : les checks de validation (`run_tests`, `run_lint`) exécutent un code inchangé et échouent structurellement. Une session ne peut pas atteindre `done`.

## Contexte

En session réelle (Lot 5), la chaîne `fix → validation` est observée : l'acteur
produit un diff correct dans l'esprit (« la branche décimale doit diviser par 1000
avec les unités KB/MB/GB »), mais rien ne l'applique. Les checks
`command_exit_zero` de l'état `validation` tournent sur le repository inchangé →
`unit_tests_pass` échoue toujours → le juge passe `validation_cannot_be_completed`
à juste titre → blocked. La garantie « *regression_is_verified* » est
structurellement fausse tant que le correctif n'est pas dans l'arbre de travail.

L'ADR 0003 D3 ferme le vocabulaire des vérifications à trois types ; la règle de
fermeture impose une ADR numérotée pour tout quatrième type. ADR 0008 est
réservée (gates humaines — Lot F.5 ; sécurité opérationnelle — ADR 0005) ; la
présente ADR est la 0009.

## Décision

### D1. Quatrième type de vérification : `artifact_applied`

Le vocabulaire des vérifications (ADR 0003 D3) est étendu d'un type :

| Type | Paramètres | Évaluateur |
|---|---|---|
| `artifact_applied` | `id`, `command_ref` | runtime |

- `id` — identifiant d'un artefact produit par la session (ici `kind: patch`,
  contenu = diff texte).
- `command_ref` — commande d'application, résolue comme `command_exit_zero`
  (hiérarchie projet > machine, ADR 0005 D5). L'argv résolu est **incomplet** :
  le runtime y ajoute en dernier argument le chemin absolu du fichier diff
  matérialisé.

**Exécution** : le runtime matérialise le contenu brut de l'artefact dans
`<session>/tmp/<id>.diff`, exécute `argv + [path_absolu]` avec **cwd = project_root**
(l'application vise le repository de travail, pas le dossier de session), et le
check passe si le code de sortie est 0.

**Effet de bord assumé et documenté** : l'application modifie l'arbre de travail.
C'est l'objectif d'un workflow bugfix (livrer le correctif avant de le valider).
Aucun rollback automatique n'est implémenté (cohérent ADR 0004 : la réparation
automatique reproduit le pattern d'auto-justification ; `git apply` est réversible
par l'outil de versionnement).

### D2. Ordre d'exécution dans un état

Les checks d'un état sont exécutés dans l'ordre du YAML. Un état `validation` qui
veut tester le correctif déclare `artifact_applied` **avant** les
`command_exit_zero` : l'application précède les commandes qui en dépendent. Le
workflow `bugfix` v1 inscrit ce check en tête de ses checks de validation.

### D3. Interaction avec la validation

`artifact_applied` échoué signifie soit un artefact absent (`id` inconnu), soit
une commande d'application en échec (diff non applicable au contexte de l'arbre).
L'échec est un fait de check (`checks.patch_applied`), consommable par les
assertions de l'état exactement comme les autres checks.

## Conséquences

- `src/agentic_suite/verification/checks.py` : `check_artifact_applied` (pure :
  définition, absence de `id`/`command_ref`).
- `src/agentic_suite/runner.py` : branche `artifact_applied` dans `_run_checks` —
  matérialisation du diff + exécution avec cwd=project_root.
- `lint/` : le type `artifact_applied` entre dans l'ensemble des types autorisés
  (règle sur les checks) et est soumis aux mêmes contraintes de forme
  (`id` présent, `command_ref` présent).
- `config/.agentic/commands.yaml` (référence) : commande `apply_patch` (ex.
  `git apply --whitespace=nowarn`).
- `workflows/v1/bugfix.yaml` : l'état `validation` déclare
  `patch_applied` (artifact_applied) avant `unit_tests_pass`.

## Alternatives rejetées

**Le runtime applique automatiquement le dernier artefact kind=patch.** Rejeté :
l'application devient implicite, non déclarée par le workflow, et magique —
violation de l'ADR 0001 (l'autonomie vit dans le workflow, pas dans le runtime).

**Étendre `command_exit_zero` avec un paramètre de patch.** Rejeté : deux
sémantiques dans un type (exécuter une commande vs appliquer un artefact puis
exécuter) rendent le check non composable et le lint moins lisible.

**L'acteur écrit directement dans l'arbre de travail.** Rejeté : l'acteur est un
processus isolé qui produit des artefacts (ADR 0003 D9), pas un mutateur du repo.
L'application est un fait de runtime vérifiable, pas une déclaration de l'acteur.

## Vérification

Un test d'échec retire le check du workflow : sans `patch_applied`, les checks
`unit_tests_pass`/`lint_passes` exécutent le code inchangé et la garantie
`regression_is_verified` redevient structurellement fausse (D5.9). Le test
e2e `test_patch_applied_before_validation` verrouille l'ordre.