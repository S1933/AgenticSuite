# ADR 0006 : Contrat d'invocation des skills

- **Statut :** Acceptée
- **Date :** 2026-09-02
- **Remplace :** aucune
- **Précise :** ADR 0001 (architecture centrée workflow)

## Contexte

L'ADR 0001 et le README posent Agentic Suite comme un orchestrateur de workflows au-dessus du registre [`S1933/Skills`](https://github.com/S1933/Skills). La séparation est claire : « Skills répondent à *quelle capacité existe*. Agentic Suite répond à *quand elle est utilisée, par qui, et dans quel workflow*. »

Cette séparation est un schéma dans le README. Aucune pièce architecturale ne la fait respecter. Un état qui invoque une skill peut, en l'état actuel, soit modifier directement la session (annulant l'intégrité de l'ADR 0004), soit absorber le contenu de la skill dans le runtime (ce que le principe 7 de la philosophie interdit).

La présente ADR tranche le contrat d'invocation : ce qu'une skill peut faire, ce qu'elle ne peut pas faire, et comment elle est déclarée dans un état.

## Décision

### D1. Skills déclarées par état uniquement

Chaque état déclare les skills qu'il est habilité à invoquer sous une clé `skills:`, liste d'identifiants. Aucun niveau de déclaration supplémentaire (workflow, configuration). Une skill non listée dans `skills:` d'un état n'est pas invocable depuis cet état.

Le format par entrée :

```yaml
skills:
  - id: <skill_id>           # snake_case, référence une skill du registre S1933/Skills
    use_when: <prose libre>  # condition non normative d'invocation
```

`use_when` est de la prose libre. Le runtime ne l'évalue pas — il la rend disponible à l'acteur pour décision. Une skill listée sans `use_when` est invocable sans condition particulière.

### D2. Une skill ne peut pas écrire dans la session

Une skill invoquée par un état **propose un contenu** à l'acteur : texte, fichier, structure de données. Elle ne peut pas :

- Écrire dans `sessions/<id>/session.jsonl`.
- Créer ou modifier un artefact dans `sessions/<id>/artifacts/`.
- Modifier le fichier de workflow.
- Modifier `config/` ou `~/.config/agentic/`.

Si une skill a besoin de produire un résultat persistant, elle le retourne à l'acteur sous forme de contenu, et l'acteur utilise les commandes CLI du runtime pour l'enregistrer. Toute modification de la session passe par le CLI — donc par la chaîne d'empreintes (ADR 0004 D3).

### D3. Une skill ne peut pas appeler une autre skill

Pas d'invocation chaînée. Si une skill veut composer avec une autre, elle le fait dans son implémentation interne, mais le runtime n'en sait rien et ne le valide pas. Cette restriction existe pour garder le runtime simple : tracer une invocation chaînée multiplierait les sources d'audit et brouillerait la garantie « toute modification de session passe par le CLI ».

### D4. Format d'invocation

Une invocation de skill est un événement de session typé `skill_invoked`, enregistré dans le journal de session (ADR 0004) avec :

| Champ | Type | Rôle |
|---|---|---|
| `seq` | entier | Numéro de séquence |
| `timestamp` | ISO 8601 UTC | Horodatage |
| `type` | enum | `skill_invoked` |
| `skill_id` | string | Identifiant de la skill invoquée |
| `state_id` | string | État depuis lequel la skill est invoquée |
| `role` | string | Rôle de l'agent (`actor` ou `evaluator`) |
| `input_summary` | string | Résumé court de l'entrée passée à la skill (≤ 200 caractères) |
| `output_summary` | string | Résumé court de la sortie retournée (≤ 200 caractères) |

`input_summary` et `output_summary` sont des résumés, pas les contenus. Un contenu volumineux est produit comme artefact (`produces:`), avec son propre cycle d'intégrité.

### D5. Déclaration non normative de l'usage

L'ADR ne définit pas quand une skill *doit* être invoquée. Ce choix relève de l'actor ou de l'evaluator selon l'état. `use_when` est une recommandation que l'agent peut suivre ou ignorer.

Conséquence : une skill peut être invoquée sans avoir été listée dans `skills:` si l'agent le décide seul. Une telle invocation est enregistrée comme `skill_invoked` mais le linter signale en warning post-exécution : « skill non déclarée par l'état ». Le runtime ne refuse pas l'invocation — il signale l'écart après coup.

### D6. Compatibilité avec le dépôt Skills

L'ADR n'impose aucune modification au dépôt [`S1933/Skills`](https://github.com/S1933/Skills). Une skill écrite conformément aux conventions existantes du dépôt est invocable sans adaptation. La présente ADR ajoute une couche côté Agentic Suite (déclaration, journalisation, garantie d'intégrité), pas une couche côté Skills.

Si une skill nécessite un format de retour incompatible avec D2 ou D4, c'est à la skill de s'adapter, pas au runtime de l'accommoder. Toute modification du dépôt Skills pour les besoins d'Agentic Suite doit être refusée par principe (cf. principe 7 : « une skill fait une seule chose bien, sans dépendre de l'orchestrateur qui l'appelle »).

## Précision sur ADR 0001

L'ADR 0001 dit qu'« Agentic Suite compose des skills ; il ne les possède pas ». La présente ADR précise ce que signifie « composer » : déclaration par état, invocation tracée, contenu retourné à l'acteur, aucune écriture directe en session. ADR 0001 reste valide ; son énoncé sur la composition est précisé ici.

## Conséquences

### Positives

- L'intégrité de session (ADR 0004) est préservée : toute écriture passe par le CLI, donc par la chaîne d'empreintes.
- Le dépôt `S1933/Skills` reste autonome et n'a pas besoin d'être modifié pour être consommé.
- Le runtime n'absorbe pas le contenu des skills : il reste un orchestrateur de workflows, pas une plateforme de plugins.
- La journalisation `skill_invoked` donne un audit complet des invocations, sans bruit sur les contenus.

### Négatives

- Le résumé `input_summary` / `output_summary` (≤ 200 caractères) est une perte d'information par rapport au contenu réel. Le contenu complet doit être produit comme artefact s'il doit être auditable.
- La règle « l'agent peut invoquer une skill non déclarée » peut produire des écarts silencieux. Le warning post-exécution est un filet de sécurité minimal.
- Une skill qui a réellement besoin d'écrire dans la session (par exemple un formatteur qui modifie le workflow) ne peut pas le faire sans passer par l'acteur, ce qui ajoute un aller-retour.

## Alternatives considérées

**Skills autorisées au niveau du workflow (liste blanche).** Rejeté : duplique la déclaration sans bénéfice clair. L'état reste le bon niveau.

**Une skill peut écrire dans la session si elle signe son écriture.** Rejeté : complique l'intégrité sans bénéfice ; le CLI est le seul chemin qui connaît la chaîne canonique.

**Une skill peut appeler une autre skill.** Rejeté : multiplie les sources d'audit ; le runtime ne peut pas garantir la garantie D2 au-delà d'un niveau d'indirection.

**Format de retour typé (au lieu de contenu libre).** Rejeté : impose une contrainte au dépôt Skills sans démonstration de besoin.

**L'invocation d'une skill non déclarée est refusée.** Rejeté : plus strict que nécessaire pour la v0. L'agent qui choisit d'invoquer une skill non déclarée est un signal faible mais récupérable (warning post-exécution), pas une faute à bloquer.

## Hors périmètre

- Définition du contenu des skills (vit dans le dépôt `S1933/Skills`).
- Mécanisme de découverte automatique de skills (le runtime charge la liste déclarée par l'état).
- Versionnage des skills (le runtime appelle l'id, sans notion de version).
- Invocation distante ou asynchrone de skills.

## Validation

Cette décision est considérée comme réussie lorsque :

1. Une skill invoquée retourne un contenu qui est ensuite produit comme artefact par l'acteur via le CLI.
2. Aucune écriture de skill ne contourne la chaîne d'empreintes du journal de session.
3. Une invocation d'une skill non déclarée par l'état est enregistrée comme `skill_invoked` et suivie d'un warning post-exécution consultable via `agentic log`.
4. Le dépôt `S1933/Skills` n'est pas modifié pour les besoins d'Agentic Suite.
5. Sur 10 sessions bugfix, au moins un état déclare et invoque effectivement une skill (sanity check : le mécanisme n'est pas mort).