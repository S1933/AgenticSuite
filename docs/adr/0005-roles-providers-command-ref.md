# ADR 0005 : Rôles, fournisseurs et résolution de `command_ref`

- **Statut :** Acceptée
- **Date :** 2026-09-02
- **Remplace :** aucune
- **Précise :** ADR 0003 D3 (vocabulaire des vérifications), ADR 0003 D9 (évaluateur)

## Contexte

L'ADR 0003 fixe le vocabulaire des vérifications (3 types fermés, dont `command_exit_zero` avec un `command_ref` à la forme `^[a-z][a-z0-9_]*$`) et les rôles minimaux (`actor`, `evaluator`). Aucune des deux ADR ne définit **comment** un `command_ref` est résolu en commande exécutable, ni comment un rôle est lié à un fournisseur d'exécution.

Le `bugfix.yaml` v1 référence déjà `command_ref: run_tests` et `command_ref: run_lint`, non résolus tant que cette ADR n'existe pas.

La présente ADR ferme cette boucle en restant dans le périmètre strict : résolution rôle → fournisseur, résolution `command_ref` → commande, et rien d'autre. Pas de hiérarchies manager/worker, pas de plugins génériques, pas de scheduling, pas d'optimisation automatique. Le principe 16 de la philosophie l'interdit nommément.

## Décision

### D1. Rôles : schéma fermé

Les rôles `actor` et `evaluator` sont les seuls rôles existants. Ils sont déclarés dans le schéma, pas dans un fichier de configuration. Aucune clé `roles:` au niveau du workflow, aucun `config/roles.yaml`.

Un workflow qui tente de référencer un autre rôle est refusé au chargement.

### D2. Capacités implicites par rôle

Chaque rôle a un ensemble figé de capacités requises :

| Rôle | Capacités |
|---|---|
| `actor` | raisonnement, édition de code, exécution d'outils |
| `evaluator` | raisonnement, lecture seule (pas d'édition de code) |

Ces capacités ne sont pas déclarées explicitement dans le schéma. Elles sont la conséquence du nom du rôle. Une modification de l'ensemble des capacités d'un rôle exige une nouvelle ADR numérotée — règle de fermeture analogue à ADR 0003 D3.

### D3. Fournisseurs déclarés dans `config/providers.yaml`

Un fournisseur est un backend d'exécution backend (modèle, CLI, API) déclaré dans `config/providers.yaml` au niveau de la machine. Chaque fournisseur porte :

```yaml
providers:
  - id: <id_unique>            # snake_case
    kind: <kind>               # enum : model | cli | api
    capabilities:               # liste des capacités fournies
      - <capability>
    config:
      <paramètres spécifiques au kind>
```

Le champ `kind` est un enum fermé : `model`, `cli`, `api`. Ajouter une valeur exige une nouvelle ADR.

Un fournisseur ne peut être sollicité que pour un rôle dont les capacités requises sont incluses dans ses capacités fournies. `actor` requérant « édition de code », un fournisseur `kind: cli` qui ne fournit que « lecture seule » ne peut pas tenir `actor`.

### D4. Résolution rôle → fournisseur

La résolution d'un rôle en fournisseur se fait par défaut dans `config/role_assignments.yaml` au niveau de la machine :

```yaml
role_assignments:
  actor: <provider_id>
  evaluator: <provider_id>
```

Aucune autre source de résolution n'existe pour la v0. Le projet ne peut pas override les assignments de rôles — un workflow reste portable entre projets précisément parce que la résolution se fait au niveau machine.

Si `config/role_assignments.yaml` n'existe pas ou ne déclare pas un rôle, le chargement de la session échoue avec `role_assignment_missing: <role>`.

### D5. Résolution `command_ref` → commande

La résolution de `command_ref` se fait par une hiérarchie de fichiers `commands.yaml` :

| Niveau | Chemin | Usage |
|---|---|---|
| Projet | `<projet>/.agentic/commands.yaml` | Override par projet. Fait primer le projet sur la machine. |
| Machine | `~/.config/agentic/commands.yaml` | Définitions partagées entre projets |

Le projet prime. Si `run_tests` est défini dans le fichier projet, c'est cette définition qui est utilisée. Sinon, le runtime cherche dans le fichier machine. Si aucune définition n'est trouvée, le check échoue à l'exécution avec `command_ref_unresolved: <ref>`.

Chaque fichier `commands.yaml` porte :

```yaml
commands:
  <command_ref>:
    argv: [<arg1>, <arg2>, ...]   # argv, pas shell — pas d'interprétation
    cwd: <relative_path>          # optionnel, relatif à la racine du projet
    timeout_seconds: 60           # optionnel, défaut 60
```

Le format `argv` (liste d'arguments) est obligatoire. Aucune expression, aucun template, aucune substitution. Le runtime exécute la commande avec `argv[0]` comme exécutable et `argv[1:]` comme arguments, sans passer par un shell. C'est ce qui élimine la classe « injection de commande » et respecte le principe 17 (portabilité).

### D6. Chargement paresseux des fournisseurs

Le runtime charge un fournisseur seulement quand un état le sollicite. Aucun cache de fournisseur entre sessions. Une session = un cycle de chargement paresseux.

Conséquence : `evaluator` n'est chargé que si un état déclare `evaluated_by: evaluator` (tous les états non terminaux de `bugfix` v1). Une session qui n'évalue jamais ne consomme pas le fournisseur `evaluator`.

### D7. Ordre de résolution au démarrage d'une session

Au démarrage d'une session, le runtime charge dans l'ordre :

1. Le fichier de workflow (`workflows/v<N>/<id>.yaml`).
2. `config/role_assignments.yaml`.
3. Pour chaque rôle sollicité par le workflow, le fournisseur correspondant (chargement paresseux).
4. Pour chaque `command_ref` rencontré dans les checks, le fichier `commands.yaml` pertinent (projet puis machine).

Si une étape échoue, la session ne démarre pas et passe à `blocked` avec une raison explicite (`workflow_load_error`, `role_assignment_missing`, `provider_load_error`, `command_ref_unresolved`).

## Précisions sur ADR 0003

L'ADR 0003 D3 dit qu'un `command_ref` est un « identifiant plat conforme à `^[a-z][a-z0-9_]*$` » et que « la résolution de `command_ref` est définie dans une ADR ultérieure ». La présente ADR précise cette résolution (D5) et l'ordre de chargement (D7).

L'ADR 0003 D9 définit deux rôles minimaux (`actor`, `evaluator`). La présente ADR précise leur résolution en fournisseurs (D1, D3, D4) et leurs capacités implicites (D2).

ADR 0003 reste valide ; ses références à `command_ref` et aux rôles sont précisées ici, non corrigées.

## Conséquences

### Positives

- La portabilité entre projets est réelle : un `bugfix.yaml` v1 fonctionne sur deux projets Python avec des `commands.yaml` différents.
- Le format `argv` (pas shell) élimine la classe « injection de commande » et rend les `commands.yaml` auditables.
- Le chargement paresseux évite de payer pour `evaluator` sur des sessions qui n'en ont pas l'usage.
- La règle de fermeture sur `kind` (D3) et sur les capacités des rôles (D2) empêche la dérive vers un système de plugins.

### Négatives

- `role_assignments.yaml` est unique par machine : un développeur avec deux machines (bureau + portable) doit synchroniser. Pas de mécanisme de sync prévu.
- Le format `argv` interdit les substitutions et les templates — un test qui dépend d'une variable d'environnement doit passer par une couche supérieure (cf. ADR 0006 « contrat d'invocation des skills » pour ce qui pourra composer).
- La règle « le projet ne peut pas override les assignments de rôles » peut surprendre : un projet qui veut un autre fournisseur pour `evaluator` doit éditer la config machine, pas la config projet.

## Alternatives considérées

**Définition des rôles dans `config/roles.yaml`.** Rejeté : permet d'inventer des rôles à la demande (rôles non listés dans ADR 0003), ce qui rouvre la porte aux plugins génériques.

**Override des assignments de rôles par projet.** Rejeté : la portabilité exige que le même workflow s'exécute sans modification sur deux projets ; si chaque projet déclare ses propres assignments, on a deux exécutions sémantiquement différentes du même workflow.

**Format `command_ref` acceptant un template (`pytest {suite}`).** Rejeté : réintroduit la classe « substitution non contrôlée » et contredit le principe 17.

**Format `command_ref` en string shell (`"pytest -q"`).** Rejeté : argv est plus sûr et plus portable (pas de quoting, pas d'interprétation shell).

**Cache de fournisseurs entre sessions.** Rejeté pour la v0 : ajoute de la complexité sans bénéfice démontré. Reprise possible si le coût de chargement devient mesurable.

**Capacités déclarées par rôle dans un fichier de config.** Rejeté : sans Q4 (d) il faudrait un `roles.yaml`, contre Q1 (b). Les capacités sont figées par le nom du rôle.

**Système de plugins avec discovery automatique.** Rejeté nommément par le principe 16.

## Hors périmètre

- ADR 0006 — contrat d'invocation des skills.
- ADR 0008 (éventuelle) — sécurité opérationnelle, dont chiffrement des `commands.yaml` au repos.
- Mécanismes de hiérarchie manager/worker, scheduling, optimisation automatique de fournisseur (cf. principe 16).
- Synchronisation de configuration entre machines.

## Validation

Cette décision est considérée comme réussie lorsque :

1. Le même `bugfix.yaml` v1 s'exécute sur deux projets avec des `commands.yaml` différents sans modification du workflow.
2. Le même workflow s'exécute avec l'`actor` et l'`evaluator` sur deux fournisseurs distincts (par exemple un `kind: model` et un `kind: cli`).
3. Aucun nom de modèle ou de fournisseur n'apparaît dans `workflows/`.
4. Un `command_ref` non défini dans aucun `commands.yaml` échoue à l'exécution avec `command_ref_unresolved: <ref>`, jamais à la lecture.
5. Un `command_ref` défini dans `commands.yaml` projet prend le pas sur celui de `commands.yaml` machine.
6. Un workflow qui référence un rôle hors `actor` / `evaluator` est refusé au chargement avec un message explicite.