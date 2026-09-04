# Conventions de la v1 du workflow `bugfix`

Ce fichier recense les points que les ADR 0001 à 0004 laissent ouverts et que
`bugfix.yaml` a dû trancher pour être écrivable.

**Statut : ratifiées.** C2 a été ratifiée par l'ADR 0007, C3/C5/C6 par
`0003-precisions-evaluator-initial-state-context-scope.md`, et C1/C4 par
`0003-precisions-conventions-C1-C4.md`. Le workflow `feature` (Lot F) réutilise ces
conventions avec un statut ADR.

---

## C1 — Les vérifications portent un `name`, pas un `id`

**Problème.** Le tableau de l'ADR 0003 D3 ne déclare aucun identifiant pour une
vérification, mais la section « Composition » exige un « `id` propre » et D4
référence les preuves par `checks.<check_name>`. L'état `validation` a besoin de
deux `command_exit_zero` distincts (tests et lint) : sans identifiant, ils sont
inadressables.

**Convention.** Chaque vérification porte `name`, snake_case, unique dans
l'état, référencée par `checks.<name>`.

**Pourquoi `name` et pas `id`.** Le paramètre de `artifact_exists` s'appelle
déjà `id` (D3). Nommer l'identifiant de la vérification `id` provoquerait une
collision de clé dans le même objet YAML. `name` évite la collision et suit la
lettre de D4, qui écrit `check_name`.

---

## C2 — Polarité : les assertions d'échec sont des assertions positives

**Problème.** L'ADR 0003 D5 impose que `on_failure.when:` cite un `assertion.id`
qui doit être **vrai**. Une validation ratée ne peut donc pas réutiliser
`regression_is_verified` en négatif. Rien dans le schéma ne distingue par
ailleurs une assertion du chemin nominal d'une assertion de chemin d'échec.

**Convention.**

1. Toute assertion citée par un `on_failure.when:` de l'état est une
   **assertion d'échec**. Elle est formulée positivement : elle est vraie quand
   l'échec est constaté.
2. Une assertion d'échec est exclue de la conjonction de sortie nominale.
3. Une assertion non citée par un `on_failure.when:` est une **assertion
   nominale**.
4. Ordre d'évaluation à chaque transition : les assertions d'échec d'abord,
   dans leur ordre de déclaration ; la première vraie déclenche sa transition.
   Si aucune n'est vraie, la sortie vers `next:` exige que tous les checks
   passent et que toutes les assertions nominales soient vraies.
5. Une même assertion ne peut pas être à la fois nominale et d'échec.

**Convention de nommage.** Les assertions d'échec nomment la condition
constatée (`report_is_not_a_bug`, `diagnosis_is_invalidated`), jamais la
négation d'une assertion nominale (`regression_is_not_verified` est interdit —
c'est la polarité déguisée que D5 refuse).

**Risque assumé.** L'ADR 0007 « polarité des preuves » pourrait retenir un
mécanisme différent. Si c'est le cas, renommer ou reformuler ces assertions est
un changement cassant au sens de l'ADR 0003 D10.

---

## C3 — `evaluated_by: evaluator` sur tous les états

**Problème.** L'ADR 0003 D9 fixe le défaut à `actor` et rend `evaluator`
obligatoire pour `fix`. Mais la section « Alternatives considérées » de la même
ADR rejette explicitement l'arrangement « évaluateur = acteur pour tous les
états sauf `fix` », au motif que « le seuil est déjà arbitraire ; mieux vaut le
poser une fois et s'y tenir ». Décision et alternatives se contredisent.

**Convention.** `evaluated_by: evaluator` est déclaré explicitement sur les
quatre états non terminaux. C'est conforme à D9 (`fix` respecte son obligation,
les autres dévient d'un défaut, ce qui est permis) et cohérent avec le motif de
rejet de l'alternative.

**Coût.** Un appel d'agent supplémentaire par transition sur tous les états, et
non seulement sur `fix`. Conséquence négative déjà listée par l'ADR 0002. Si le
coût s'avère prohibitif en Phase 4, retirer `evaluated_by` de `discovery` est le
premier assouplissement à envisager : c'est l'état le plus pauvre en jugement,
sa sortie étant majoritairement portée par un check de complétude.

---

## C4 — Nom de l'artefact implicite de sortie de commande

**Problème.** L'ADR 0003 D3 écrit `command_output<check_id>` sans séparateur.
Appliqué littéralement, `command_output` + `unit_tests_pass` donne
`command_outputunit_tests_pass`, illisible et non conforme au snake_case exigé
pour les identifiants d'artefacts (D8).

**Convention.** `command_output_<check_name>`, par exemple
`command_output_unit_tests_pass`. Le référencement suit D4 :
`artifacts.command_output_unit_tests_pass`.

---

## C5 — État initial déclaré au niveau du workflow

**Problème.** `concepts.md` précise que « l'ordre des états dans la liste ne
porte pas de sémantique ». Aucune ADR ne dit alors dans quel état une session
démarre.

**Convention.** Clé `initial_state:` au niveau du workflow, obligatoire, valeur
égale à un `states[].id` non terminal et non déclaré comme `escape_state`.

**Note.** L'état `Reported` du diagramme du README n'existe pas comme état. Le
rapport initial est un champ de contexte de `discovery`
(`original_report`), conservé brut pour permettre de détecter les glissements de
sens entre le rapport et sa reformulation. Un état sans contrat propre n'a pas
de raison d'exister dans la machine.

---

## C6 — Portée des références de contexte

**Problème.** L'ADR 0003 D4 définit `context.<field_id>` sans dire si l'espace
de noms est l'état ou la session. `bugfix.yaml` en a besoin : l'assertion
`fix_cannot_be_implemented` cite `context.known_constraints`, champ collecté en
`discovery`.

**Convention.** L'espace de noms est **la session**. Un état peut citer comme
preuve n'importe quel champ de contexte déjà collecté par un état antérieur de
la même session. C'est cohérent avec `concepts.md`, qui range le contexte
utilisateur et le contexte produit par les agents dans la session, non dans
l'état.

**Contrainte induite.** Le linter doit vérifier qu'un champ cité est
*atteignable* : déclaré par un état situé sur au moins un chemin menant à
l'état citant. Une preuve citée mais jamais collectée est un défaut de
définition au même titre qu'une assertion sans preuve.

---

## Points laissés ouverts

- **`command_ref`** reste non résolu (ADR 0005). `bugfix.yaml` déclare
  `run_tests` et `run_lint` dans la forme validée par le schéma. L'état
  `validation` ne s'exécute pas de bout en bout avant l'ADR 0005.
- **`reclassified` depuis `investigation`.** L'ADR 0003 D5 restreint l'accès à
  `discovery`. Un rapport qui s'avère ne pas être un bug en cours
  d'investigation doit donc repasser par `discovery` via
  `required_context_is_missing`, ce qui consomme la seconde tentative de
  `discovery`. Comportement conforme mais peu naturel, à réexaminer sur usage
  réel.
- **Nommage des rôles.** `bugfix.yaml` s'en tient à `actor` et `evaluator`
  (ADR 0003 D9). Les rôles `investigator`, `implementer`, `reviewer` du README
  et de `concepts.md` ne sont pas utilisés : ils ne sont définis par aucune ADR
  et l'exemple de `concepts.md` (`evaluated_by: investigator`) n'est pas
  conforme à D9.

## Ce que `feature` (Lot F) a révélé

Le second workflow a servi de test de généricité. Constats consignés dans
`docs/planning/plan-execution-feature.md` §3-4 ; l'essentiel :

- **Polarité des assertions d'échec (L3).** La convention est confirmée par
  `feature` : un identifiant d'assertion d'échec peut être négatif
  (`plan_is_invalidated`, `implementation_cannot_proceed`,
  `design_is_invalidated`) — la regex de l'ADR 0007 ne refuse que les formes
  `is_not_` / `not_` / `does_not_` qui nient une assertion nominale. Les deux
  workflows utilisent la même convention ; rien à modifier.
- **Absence de primitive de gate.** `feature` a besoin d'une gate entre
  `design` et `implementation` (« approbation avant de construire »). Sans
  primitive de schéma, la gate est exprimée par un déclencheur d'escalade
  global (`public_interface_change`, `scope_expansion_beyond_intake`) qui force
  `blocked` — reprenable, `session_resumed` ne consomme pas le budget. Gate
  **conditionnelle**, pas obligatoire. Ratification conditionnelle : si trois
  sessions réelles confirment que la transition automatique design →
  implementation coûte trop, ADR 0008 (gates humaines). Sinon, ne rien écrire.
- **Absence de primitive de boucle.** Le découpage en sous-tâches vit dans
  l'artefact `implementation_plan` ; `implementation` est un seul état, et le
  respect du plan est une assertion. Rien à corriger tant que trois sessions
  réelles ne réclament pas une primitive.
- **R10 généralisée.** Les noms d'états codés en dur (`reclassified`,
  `discovery`) ont été remplacés par la contrainte réelle : un terminal local
  cible d'un `on_failure` n'est atteignable que depuis `initial_state`.
  `descoped` est ainsi protégé comme `reclassified` l'était.
