# ADR 0003 : Schéma déclaratif de workflow

- **Statut :** Acceptée
- **Date :** 2026-09-02
- **Remplace :** aucune
- **Précise :** ADR 0001 (architecture centrée workflow), ADR 0002 (critères de sortie et chemins d'échec)

## Contexte

L'ADR 0001 a posé l'autonomie sous contrat : un workflow avance quand ses critères de sortie sont satisfaits. L'ADR 0002 a précisé deux conditions que cette autonomie doit respecter pour rester acceptable : la vérifiabilité de l'avancement (vérifications vs assertions, preuves obligatoires, évaluateur distinct de l'acteur) et la légalité du non-avancement (états d'échec de première classe, transitions arrière, budgets, escalade).

Aucune des deux ADR ne définit le **schéma** par lequel ces mécanismes s'expriment. La présente ADR comble ce manque pour le workflow `bugfix` et fixe les règles de fermeture qui empêchent le schéma de dériver vers un langage d'expressions.

La règle de fermeture vaut pour cette ADR comme pour les précédentes : ajouter un mécanisme qui modifie le schéma exige une nouvelle ADR numérotée.

## Décision

### D1. Champs de contexte

Chaque état déclare le contexte qu'il doit avoir collecté avant de pouvoir être quitté.

Un champ de contexte porte :
- `id` — snake_case stable, clé de référencement
- `type` — parmi `text`, `list`, `boolean`, `enum`
- `required` — `true` ou `false`
- `description` — prose libre

Un champ est satisfait s'il porte une valeur non vide, ou s'il est marqué `inconnu` avec une raison explicite. Un champ vide sans raison est insatisfait.

L'état peut déclarer `max_unknown` pour borner le nombre de champs laissés inconnus. `max_unknown` transforme un prédicat de jugement en fait vérifiable : l'état sort avec N inconnues documentées, pas avec N champs vides.

Les énumérations sont déclarées au niveau du workflow dans une section `vocabularies:`, référencées par id depuis l'état. Cette factorisation évite la duplication entre états et garantit que la même étiquette porte le même sens dans tout le workflow.

`required: false` est autorisé pour les champs *nice-to-have* qui enrichissent le contexte sans bloquer la sortie. Un champ optionnel qui n'est jamais rempli n'a aucun effet sur les checks et n'a rien à faire dans `context_fields:` — il est toléré pour les cas où la présence ou l'absence est une information utile.

### D2. Séparation des vérifications et des assertions

Les critères de sortie d'un état sont répartis en deux clés distinctes : `checks:` et `assertions:`. La règle de l'ADR 0002 — préférer une vérification quand la condition s'y réduit — n'est auditable que si le déséquilibre est visible d'un coup d'œil.

Les deux natures n'ont pas le même évaluateur : les `checks` sont évalués par le runtime, les `assertions` par un agent. Grouper par nature, c'est grouper par chemin d'exécution.

Un état sans aucun check est autorisé mais déclenche un avertissement de lint explicite : « cet état n'a que des assertions, vérifier qu'aucune condition ne se réduit à un check ». L'auteur peut justifier par commentaire.

### D3. Vocabulaire des vérifications

Le vocabulaire des vérifications est un ensemble **fermé** de trois types pour la v0 :

| Type | Paramètres | Évaluateur |
|---|---|---|
| `context_fields_present` | `fields`, `max_unknown` | runtime |
| `artifact_exists` | `id` | runtime |
| `command_exit_zero` | `command_ref` | runtime |

**Règle de fermeture** : toute condition qui ne rentre pas dans ces trois types devient une assertion. Ajouter un quatrième type exige une nouvelle ADR numérotée. Cette règle, et non la bonne volonté, empêche le schéma de dériver vers un langage.

**Composition** : un état qui dépend de plusieurs conditions combinées (ex. « les tests unitaires **et** le lint passent ») les déclare comme checks distincts avec `id` propre, et compose le résultat dans une assertion qui cite les `checks.*` correspondants dans `evidence_from:`. Il n'existe pas de check composite `all_of:` / `any_of:`.

**Sortie de commande** : les checks de type `command_exit_zero` capturent automatiquement la sortie (stdout, stderr, code de sortie, horodatage) dans un artefact implicite `command_output<check_id>`, consommable via `artifacts.command_output<check_id>` dans une assertion. Cet artefact est une exception documentée à D8.

**Forme de `command_ref`** : identifiant plat conforme à `^[a-z][a-z0-9_]*$`. Pas de chemin absolu, pas de slash, pas de namespace dans le schéma. La résolution de `command_ref` est définie dans une ADR ultérieure ; le schéma valide la forme, le runtime lève « command_ref non résolu » à l'exécution.

### D4. Référencement des preuves par une assertion

Chaque assertion porte `evidence_from:`, liste non vide d'identifiants de preuves dans un espace de noms stable :

- `context.<field_id>` — un champ de contexte collecté
- `artifacts.<artifact_id>` — un artefact produit
- `checks.<check_name>` — un check exécuté

Une assertion sans `evidence_from` est un défaut de définition. Le schéma rend le champ obligatoire et ≥ 1. Liste vide `[]` est rejetée au même titre que champ absent.

Une assertion ne peut pas référencer une autre assertion comme preuve. Citer un jugement comme preuve d'un autre jugement reproduit le pattern d'auto-justification que l'ADR 0002 combat.

### D5. Transitions

Chaque état déclare explicitement ses cibles :
- `next:` — état suivant en cas de succès
- `on_failure:` — liste de cibles avec condition

Les états d'échappement atteignables depuis n'importe où, `blocked` et `abandoned`, sont déclarés une fois au niveau du workflow sous `escape_states:`. `reclassified`, atteignable uniquement depuis `discovery`, reste déclaré localement.

Les états d'échappement ont une **sémantique unique partagée** par tous les workflows. Un workflow qui veut une nuance (ex. « release gelée ») invente son propre état local et le déclare comme `escape_state` dans son `workflow.yaml`. Pas de géométrie variable.

Le champ `when:` de `on_failure:` référence un `assertion.id` déclaré dans l'état. Une chaîne libre n'est pas acceptée — elle rouvrirait la porte du langage d'expressions. La transition d'échec a deux prérequis : l'assertion citée est vraie **et** le budget le permet.

### D6. Budgets

Deux budgets sont déclarés :
- `max_attempts` par état, **défaut 1**. La première entrée dans l'état compte comme tentative 1.
- `max_transitions` au niveau du workflow, défaut 20.

Dépassement de l'un ou de l'autre → transition forcée vers `blocked`, avec la raison enregistrée.

**Règle de comptage des transitions** : `max_transitions` est total, mais les transitions *depuis* `blocked` (reprise humaine) ne consomment pas le budget. Seules les transitions *vers* `blocked` comptent. La suspension vers `blocked` est elle-même une transition qui consomme, ce qui empêche les boucles abusives sans étrangler les reprises longues.

Le compteur de tentatives par état commence à 1 à la première entrée. Un état au `max_attempts: 1` ne peut pas être revisité.

Aucun budget en tokens ou en coût n'est défini pour la v0. Aucun runtime ne peut le mesurer aujourd'hui, et le déclarer donnerait une garantie fictive. Reprise possible en Phase 3 quand les fournisseurs seront branchés.

### D7. Déclencheurs d'escalade

Quatre triggers d'escalade non-déterministes sont déclarés au niveau du workflow dans `escalate_when:` :

- `irreversible_action` — l'action suivante est irréversible ou destructrice
- `security_relevant_change` — la modification touche la sécurité
- `human_decision_required` — une décision produit/architecture/domaine relève de l'humain
- `context_contradiction` — le contexte collecté contient une contradiction non résolue

Chacun porte `nature: assertion` et est évalué par l'évaluateur à chaque transition. L'ADR 0002 §4 interdit que l'acteur soit juge de ces triggers (auto-déclaration = auto-justification).

**Point d'honnêteté** : les quatre triggers sont des jugements, pas des garanties dures. Les déclarer dans `escalate_when:` donne un point d'audit mais pas une barrière automatique. Le seul garde-fou mécanique est le budget (D6), ce qui rend D6 plus important qu'il n'y paraît.

Le dépassement de budget (`budget_exceeded`) **n'est pas** listé dans `escalate_when:`. C'est un invariant de runtime (D6), pas un trigger d'escalade. Le runtime le détecte et force la transition vers `blocked` sans passer par l'évaluateur.

### D8. Artefacts

Chaque état déclare ce qu'il produit dans `produces:`, avec par entrée :
- `id` — snake_case, **unique dans tout le workflow**
- `kind` — enum fermé parmi `diagnosis`, `repro`, `patch`, `test_result`, `decision`, `note`
- `description`
- `required` — `true` ou `false`

Le référencement se fait via `artifacts.<id>`, même espace de noms que D4. La vérification `artifact_exists` de D3 pointe sur ces identifiants.

**Versionnage d'artefact** : un artefact écrasé (par exemple `diagnosis` régénéré lors d'un retour arrière `validation → investigation`) reste identifié par son `id`. Le dernier enregistrement est le seul valide pour les futures références. Si une assertion postérieure a référencé cet artefact avant l'écrasement, la transition qui consomme cette assertion est invalidée a posteriori. Le runtime snapshotte l'état des artefacts à chaque transition pour pouvoir détecter la rupture.

**Extension du vocabulaire `kind`** : ajouter une valeur à l'enum exige une nouvelle ADR. Parallélisme strict avec la règle de fermeture de D3.

### D9. Évaluateur

Deux rôles minimaux sont définis :
- `actor` — exécute le travail de l'état
- `evaluator` — évalue les assertions

Chaque état déclare `evaluated_by:`, valeur par défaut `actor`. Pour l'état `fix`, `evaluated_by: evaluator` est **obligatoire** (différent du défaut) — conformément à l'ADR 0002 §4 qui exige un évaluateur distinct pour tout état modifiant le code.

Tout autre rôle est défini dans une ADR ultérieure.

**Invariant de runtime** : l'évaluateur opère exclusivement sur l'enregistrement de session, à l'exclusion de la conversation de travail qui a produit l'état. Cet invariant est non négociable et ne peut pas être exprimé en YAML.

L'ADR exige que le premier test de bout en bout de la Phase 4 vérifie cet invariant : capturer la conversation de travail de l'acteur, faire évaluer par l'évaluateur, vérifier que l'évaluateur n'a jamais référencé un élément absent de l'enregistrement de session. L'absence de ce test invalide la qualification « workflow validé ».

### D10. Versionnage

Le dossier `workflows/v<N>/<workflow>.yaml` est la version. `version:` reste un entier. Pas de semver — il n'y a pas encore de consommateur externe à qui signaler une compatibilité.

**Changements cassants** :
- supprimer un état
- renommer un `id` d'état, de champ de contexte ou d'artefact
- ajouter un champ de contexte requis
- resserrer une vérification (`max_unknown` diminué, nouveau champ dans `fields`)
- changer une cible de transition
- modifier le wording d'une description (les descriptions sont des contrats sémantiques)

**Changements non cassants** :
- ajouter un état optionnel
- ajouter un artefact optionnel
- desserrer un budget (`max_attempts` ou `max_transitions` augmenté)
- ajouter un état d'échappement
- ajouter une assertion (sans modifier les existantes)

**Règle de session** : une session est épinglée à la version de workflow avec laquelle elle a démarré et ne migre jamais. Si la version disparaît (dossier supprimé), les sessions en cours passent à `blocked`.

Supprimer un dossier = version disparue. Pas de mécanisme de release avant qu'un workflow ait réellement tourné.

## Précision sur ADR 0001

L'ADR 0001 mentionne la clé `exit_when:` à titre illustratif. Cette clé est **remplacée** par les deux clés `checks:` et `assertions:` de la présente ADR. ADR 0001 reste valide ; sa référence à `exit_when:` est précisée ici, non corrigée. Les ADR ne se corrigent pas, elles se précisent.

La présente précision devra être reportée dans `docs/concepts.md` lors d'une mise à jour ultérieure, avec mention explicite de l'ADR qui a opéré la précision.

## Hors périmètre

Sont explicitement **hors** du périmètre de cette ADR et traités dans des ADR ultérieures :

- **ADR 0004** : format de persistance des sessions et enregistrement des transitions.
- **ADR 0005** : configuration des rôles, capacités, fournisseurs, et résolution de `command_ref`.
- **ADR 0006** : contrat d'invocation des skills.

L'ADR 0003 se limite à dire que `command_ref` est un identifiant opaque résolu ailleurs. Aucun détail de configuration ne doit s'y glisser.

## Conséquences

### Positives

- Le schéma exprime les neuf mécanismes de l'ADR 0002 sans exception.
- La règle de fermeture de D3 et la liste fermée de D8 empêchent la dérive vers un langage.
- La séparation `checks` / `assertions` rend visible le ratio vérification/jugement, signal de design.
- L'espace de noms unique pour `evidence_from` (D4) et `produces` (D8) rend les références auditable.
- Le défaut `max_attempts: 1` rend visible toute revisite d'état, qui doit être justifiée.
- L'invariant de runtime D9 + son test Phase 4 garantissent que la séparation évaluateur/acteur ne se perd pas en implémentation.

### Négatives

- Workflow plus verbeux : champs, checks, assertions, preuves, budgets, transitions arrière ont tous à être écrits.
- Séparer évaluateur d'acteur coûte un appel d'agent supplémentaire par transition.
- Décider quelles conditions se réduisent à un check est un vrai travail de design par état.
- Un état mal conçu (zéro check malgré des conditions factuelles) ne sera arrêté que par le lint, pas par une erreur.
- L'invalidation a posteriori des transitions (D8) impose un DAG des dépendances assertion → artefact dans le runtime Phase 2.

## Alternatives considérées

**`exit_when:` unique avec attribut `kind`.** Rejeté : la règle de préférer les checks n'est pas visible d'un coup d'œil.

**Liste de types de vérifications plus large dès la v0.** Rejeté : élargir l'ensemble ouvert sans cas d'usage réel est du design spéculatif.

**`command_ref` validé sémantiquement (chemin de fichier).** Rejeté : lie le workflow à un projet. Casse le principe 17.

**Checks composites (`all_of`, `any_of`).** Rejeté : rouvre la porte du langage d'expressions par agrégation.

**Conditions `on_failure` en chaîne libre.** Rejeté : double système (D4 assertion citée / D5 string libre) incohérent et invérifiable.

**Évaluateur = acteur pour tous les états sauf `fix`.** Rejeté : pas de raison que `investigation` soit moins sensible qu'un autre. Le seuil est déjà arbitraire ; mieux vaut le poser une fois et s'y tenir.

**Budget en tokens ou en coût.** Rejeté pour la v0 : aucun runtime ne peut le mesurer. Reprise possible Phase 3.

**Versioning semver (`v1.2.3`).** Rejeté : pas de consommateur externe à qui signaler une compatibilité.

## Validation

Cette décision est considérée comme réussie lorsque, sur de vraies sessions en Phase 4 :

1. Un bug qui ne peut pas être reproduit se termine en `blocked` avec un champ manquant déclaré, sans fix proposé.
2. Une validation qui échoue renvoie la session à `investigation` avec compteur incrémenté, sans seconde déclaration de succès.
3. Un rapport qui s'avère ne pas être un bug se termine en `reclassified` via `on_failure: when: <assertion.id>`.
4. Le dépassement de budget produit `blocked` sans intervention de l'évaluateur (vérification automatique du runtime).
5. Chaque transition enregistrée porte ses preuves ; toute assertion sans preuve est rejetée au chargement du schéma.
6. Le test d'invariant D9 (évaluateur opère exclusivement sur l'enregistrement de session) est exécuté en bout en bout et passe.
7. Une assertion référençant un artefact écrasé invalide la transition consommatrice a posteriori.