# ADR 0004 : Persistance des sessions

- **Statut :** Acceptée
- **Date :** 2026-09-02
- **Remplace :** aucune
- **Précise :** ADR 0001 (architecture centrée workflow), ADR 0002 (critères de sortie et chemins d'échec), ADR 0003 (schéma déclaratif de workflow)

## Contexte

Les ADR 0001 à 0003 définissent ce qu'une session doit enregistrer (état d'origine, cible, horodatage, critères évalués, nature de chacun, preuves, évaluateur, compteur de tentatives, version du workflow). Aucune ne définit **comment** cette information est stockée, ni comment son intégrité est garantie.

Sans format de persistance explicite, l'ADR 0002 §9 (« une transition est seulement valide si la session enregistre… ») et l'ADR 0003 D8.1 (« écrasement d'artefact invalide a posteriori ») ne sont que des promesses sur papier. Une session que n'importe quel agent peut modifier hors du contrôle du runtime n'a aucune des garanties que les ADR affirment.

La présente ADR tranche le format, l'intégrité, l'invalidation et le couplage avec les artefacts.

## Décision

### D1. Structure du fichier de session

Un fichier de session est un **journal append-only** : chaque transition ajoute un nouveau bloc à la fin du fichier. Le fichier est le journal ; il n'existe pas de fichier d'état séparé.

L'état courant d'une session est dérivé : c'est l'état cible de la dernière transition valide du journal. Aucune duplication n'est tolérée.

Le fichier de session vit à `sessions/<session_id>/session.jsonl`, un fichier par session. Le répertoire `sessions/` est local à la machine (cf. `.gitignore`).

### D2. Format d'un bloc

Chaque bloc est un objet JSON sur une seule ligne (JSONL). Champs obligatoires :

| Champ | Type | Rôle |
|---|---|---|
| `seq` | entier | Numéro de séquence monotone, commence à 0 |
| `timestamp` | ISO 8601 UTC | Horodatage de l'écriture |
| `type` | enum | `transition`, `state_entry`, `artifact_produced`, `artifact_overwritten`, `session_opened`, `session_resumed` |
| `from_state` | string ou null | État d'origine (null pour `session_opened`) |
| `to_state` | string | État cible |
| `criteria_evaluated` | liste | Critères évalués pour permettre la transition |
| `evidence` | liste | Preuves référencées par chaque assertion (cf. ADR 0003 D4) |
| `evaluator` | string | Rôle ayant évalué les assertions |
| `attempt_counter` | objet | `{state_id: count}` au moment de la transition |
| `workflow_version` | entier | Version du workflow épinglée (cf. ADR 0003 D10) |
| `prev_hash` | chaîne hex | SHA-256 du bloc précédent |
| `hash` | chaîne hex | SHA-256 du bloc courant |

Les champs non applicables à un type donné sont omis. `transition` porte tous les champs ; `state_entry` omet `criteria_evaluated`, `evidence`, `evaluator` ; `artifact_produced` porte `artifact_id`, `artifact_path`, `artifact_hash`, `artifact_kind`.

### D3. Chaînage par hash

Chaque bloc contient le hash SHA-256 du bloc précédent (`prev_hash`). Le hash d'un bloc est calculé sur la **représentation canonique** du bloc (clés triées, pas d'espace, séparateurs minimaux) **avant** insertion de `prev_hash` et `hash` eux-mêmes.

Le bloc initial (`session_opened`, `seq=0`) a `prev_hash: "0" * 64` (64 zéros hexadécimaux).

Toute modification d'un bloc passé invalide tous les hash suivants. Détecter une altération ne demande qu'un parcours linéaire du journal.

### D4. Vérification d'intégrité

À chaque lecture par le CLI, le runtime recalcule l'empreinte du fichier complet en rejouant le calcul bloc par bloc. Si un hash ne correspond pas, la lecture échoue avec `session_integrity_violation`.

Trois causes possibles, trois traitements identiques :
- modification hors CLI par un humain ou un agent
- corruption disque
- bug d'écriture du CLI (très improbable, traçable par diff avec l'état précédent)

Aucun traitement automatique de réparation. La session passe à `blocked` avec `reason: session_integrity_violation` et toutes les transitions postérieures à la dernière entrée valide sont marquées `invalid`.

### D5. Invalidation a posteriori

Une transition est marquée `invalid` quand, après son enregistrement, l'une des conditions suivantes survient :

- **Artefact écrasé** (cf. ADR 0003 D8.1) : un `artifact_overwritten` remplace un artefact cité dans `evidence` d'une transition ultérieure. Les transitions postérieures à celle qui a écrasé sont marquées `invalid`.
- **Session compromise** : si l'intégrité du journal est violée, toutes les transitions postérieures à la dernière entrée intègre sont marquées `invalid`.

L'invalidation est **permanente** : une transition invalidée ne redevient jamais valide. Elle reste dans le journal pour traçabilité (cf. ADR 0002 §9) mais ne compte plus pour l'avancement de la session.

Les compteurs de tentatives ne sont **pas** décrémentés par une invalidation. Une transition invalidée reste comptée, parce qu'elle a eu lieu.

### D6. Artefacts

Les artefacts produits par les états sont stockés dans des fichiers externes au journal :

```
sessions/<session_id>/
├── session.jsonl          # le journal
└── artifacts/
    ├── <artifact_id>.json # contenu sérialisé
    └── …
```

Chaque bloc `artifact_produced` porte :
- `artifact_id` — l'id déclaré dans le workflow (cf. ADR 0003 D8)
- `artifact_path` — chemin relatif au répertoire de session
- `artifact_hash` — SHA-256 du fichier artefact au moment de la production
- `artifact_kind` — le `kind` de l'ADR 0003 D8

**Règle d'intégrité couplée** : le hash d'un bloc `artifact_produced` inclut le `artifact_hash` du fichier. Modifier l'artefact sans réécrire le bloc invalide la chaîne d'empreintes. Le bloc `artifact_overwritten` porte le même `artifact_id` et un nouveau `artifact_hash` ; il invalide les transitions ultérieures qui citaient l'ancien artefact (cf. D5).

### D7. Cycle de vie du compteur de tentatives

Le compteur `attempt_counter` est porté par chaque transition (cf. D2). L'incrémentation a lieu à l'**entrée** dans un état, pas à la transition qui y mène. Une transition `validation → investigation` incrémente le compteur `investigation` dans la transition *suivante* (celle qui quitte `investigation`).

Cela évite une double incrémentation dans le cas d'une transition immédiate vers `blocked` à l'entrée d'un état.

### D8. Reprise depuis `blocked`

Conformément à l'ADR 0003 D6.2, les transitions *depuis* `blocked` (reprise humaine) ne consomment pas le budget `max_transitions`. Le bloc `session_resumed` n'est pas une transition au sens du budget — il est typé séparément pour que le calcul du budget l'exclue.

Le bloc `session_resumed` porte `from_state: "blocked"`, `to_state: <état où reprendre>`, `resumed_at`, `resumed_by` (identité de l'humain ou du processus ayant repris). Aucun `criteria_evaluated` ni `evidence` : la décision est humaine et n'est pas un jugement de workflow.

### D9. Épinglage de version

Conformément à l'ADR 0003 D10.2, chaque bloc porte `workflow_version`. Le runtime vérifie à chaque ouverture de session que le dossier `workflows/v<N>/` référencé existe. Si la version disparaît, la session passe à `blocked` avec `reason: workflow_version_missing` (réouverture du cas D4 avec une raison distincte).

## Conséquences

### Positives

- L'intégrité de la session est garantie par construction, pas par discipline. Un agent qui écrit `state: done` directement dans le journal est détecté à la lecture suivante.
- L'invalidation a posteriori des transitions suite à écrasement d'artefact rend la promesse D8.1 de l'ADR 0003 testable.
- La distinction `transition` / `session_resumed` rend le budget `max_transitions` implémentable sans ambiguïté.
- Le format JSONL est lisible humain, parsable par les outils standard, et concaténable sans parsing préalable.

### Négatives

- Le re-calcul d'empreinte à chaque lecture est O(n) en nombre de blocs. Pour une session longue, c'est un coût réel. Mitigation : limiter le nombre de transitions par session via `max_transitions` (ADR 0003 D6).
- Le couplage artefact-bloc ajoute une règle métier implicite : tout code qui produit un artefact doit aussi écrire le bloc correspondant. Le CLI est le seul habilité à le faire — toute autre voie viole l'intégrité.
- L'invalidation permanente rend le journal « triste » au sens où il grandit avec des entrées invalidées. C'est le compromis pour la traçabilité.

## Alternatives considérées

**Une transition = une mutation du fichier JSON complet.** Rejeté : ré-écrire le fichier entier à chaque transition perd l'append-only et complique l'intégrité (deux écritures, un état intermédiaire incohérent).

**Journal dans un fichier séparé du fichier d'état.** Rejeté : duplication source de bugs de synchronisation. Le journal *est* le fichier.

**Signature HMAC au lieu de hash simple.** Rejeté pour la v0 : nécessite la gestion d'une clé hors session, sort du périmètre de la persistance. Report possible en ADR 0008 « sécurité opérationnelle » si le besoin émerge.

**Réparation automatique par rollback.** Rejeté : la réparation automatique reproduit le pattern d'auto-justification que combat l'ADR 0002. La décision de réparer appartient à l'humain.

**Marqueur `compromised` distinct de `blocked`.** Rejeté : ajoute un escape_state non prévu par ADR 0003 D5. L'invalidation des transitions postérieures suffit à signaler la perte de confiance sans multiplier les états.

## Hors périmètre

- **ADR 0005** : configuration des rôles, capacités, fournisseurs, et résolution de `command_ref`.
- **ADR 0006** : contrat d'invocation des skills.
- **ADR 0008 (éventuelle)** : sécurité opérationnelle, signature, chiffrement au repos.

## Validation

Cette décision est considérée comme réussie lorsque :

1. Une session éditée à la main (`state` modifié) passe à `blocked` avec `reason: session_integrity_violation` au prochain appel CLI.
2. Une session dont le journal est tronqué passe à `blocked` avec la même raison.
3. Un artefact écrasé après une transition qui le citait fait apparaître `invalid: true` sur les transitions postérieures dans `agentic log`.
4. Une session reprise depuis `blocked` (`session_resumed`) ne consomme pas le budget `max_transitions`.
5. La sérialisation canonique produit un hash identique après deux écritures successives du même bloc (test de stabilité).
6. La corruption d'un bloc en milieu de journal invalide tous les blocs suivants sans erreur silencieuse.

## Précision sur ADR 0003

L'ADR 0003 D8.1 mentionne « le runtime snapshotte l'état des artefacts à chaque transition pour pouvoir détecter la rupture ». La présente ADR précise que ce snapshot est implicite dans la chaîne d'empreintes (le hash du bloc `artifact_produced` capture l'état de l'artefact au moment de la production, et tout `artifact_overwritten` recalcule la chaîne). ADR 0003 reste valide ; sa référence à un « snapshot » est précisée ici, non corrigée.