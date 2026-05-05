# Brainstorm — Transitions instantanées (branchements probabilistes)

**Date** : 2026-05-05
**Sujet** : Finalisation du support des **transitions instantanées** (`InstOccDistribution`) dans cod3s : modélisation, exécution Pycatshoo, et exploitation depuis le simulateur interactif `cod3s-isimu`.
**Contexte** : Les fondations existent côté `cod3s/pycatshoo/automaton.py` (classe `InstOccDistribution`, modèle de cible polymorphe `target: str | List[StateProbModel]`, sérialisation/désérialisation). Le support est partiel : un commentaire `# NOT WORKING: PARAMETERS DOES NOT SEEMED TO BE ASSIGNED…` (ligne 441) signale un doute sur l'assignation des probabilités côté Pycatshoo, l'iSimu n'expose pas du tout les branchements (cible affichée `[…]`, `ReplanModal` ne demande qu'une date), et il n'y a aucun helper haut-niveau pour déclarer un branchement avec effets-par-cible. Cette session vise à cadrer les trois axes (backend, iSimu, DSL) avant écriture du plan.

---

## What We're Building

Trois axes coordonnés autour d'une **transition instantanée à branchement probabiliste**.

### Sémantique cible

Une transition inst = **un source state**, **une condition (garde)**, **N branches**.
- Quand la garde est vraie, le moteur Pycatshoo échantillonne **une seule** branche selon les probabilités.
- Le tirage et l'effet ont lieu **à l'instant courant** : le temps n'avance pas.
- Une branche = `{target_state, prob, effects?}`. **Pas de nom de branche** — l'identifiant naturel est le target state (Pycatshoo identifie une branche par son target index, qui = ordre d'ajout de l'addTarget).
- **Contrainte structurelle** : les target states sont **distincts** au sein d'une transition (sinon l'arbre dépliable iSimu et la trace de séquence seraient ambigus).
- Les effets-par-branche sont appliqués via le **state-entry** du target (réutilise le pattern `effects_st1`/`effects_st2` de `add_aut2st`). Pas besoin de `ITransition.addSensitiveMethod(target_idx)`.

### Phasage du moteur

Pycatshoo résout les transitions inst **avant** les temporisées, à chaque instant `t` où des inst pendantes existent. À `t` donné, plusieurs inst issues de composants/automates différents peuvent être pendantes simultanément (e.g. `valve.failure_check` ∥ `breaker.trip_check`). Le moteur les drain toutes en cascade avant de revenir aux temporisées. Conséquence forte sur l'iSimu : pas de "résolution une-par-une" possible côté API simulateur — il faut soumettre **tous** les choix de branche en bloc, puis laisser Pycatshoo exécuter.

### Phase 1 — Backend

- **Audit** du chemin `update_bkd → InstOccDistribution.to_bkd → law.setParameter(prob, idx)` : confirmer via un **round-trip déterministe** (set puis read-back de `law.parameter(idx)`, `nbParam()`, `targetCount()` et `from_bkd().probs`) que les `N-1` premières probas sont bien transmises et que Pycatshoo calcule la dernière en complément. Lever ou justifier le commentaire "NOT WORKING". Pas de test statistique : on n'a pas à re-vérifier le RNG de Pycatshoo.
- **Modèle de données stabilisé** : `BranchModel` pydantic = `{target: str, prob: float | None, effects: dict, effects_format: str = "dict"}`. Validation : sum(prob) ≤ 1 ; les `prob=None` se partagent le complément ; targets uniques.
- **Wiring d'effets state-entry** : à la création d'une transition inst, cod3s pose, sur chaque target state cité, une sensitive method d'entrée qui applique les `effects` de la branche correspondante. Si plusieurs branches dans des transitions distinctes citent le même target avec des effets différents, c'est une erreur de modélisation à signaler.

### Phase 2 — iSimu (TUI)

- **Détection** : à chaque `step_forward`, cod3s vérifie si des inst sont pendantes via Pycatshoo. Si oui → bascule du panneau "fireable" vers un mode "inst pending".
- **Affichage** : arbre à 2 niveaux dans un panneau dédié.
  - Niveau 1 (transition pendante) : `comp.aut.transition` + nb de branches + marqueur `!` si déterministe (1 seule branche, p=1).
  - Niveau 2 (branche) : `→ target_state` + `prob` ; sélection par défaut = branche de proba max ; toggle clavier pour changer.
- **Soumission atomique** : touche dédiée (e.g. `s` pour "submit") → cod3s appelle `setTransPlanning(...)` une fois par inst pendante avec le `state_index` choisi, puis `step_forward`. Le panneau temporisé reprend la main une fois toutes les inst résolues.
- **Pas de date** : pas de `ReplanModal` pour les inst (le temps n'avance pas).
- **Trace** : la sequence existante (`comp.aut.transition` + target via `firedState()`) suffit ; pas de champ "branch_name" à ajouter.

### Phase 3 — DSL haut-niveau

- Helper `add_inst_branch(...)` sur `PycComponent`, calqué sur `add_aut2st` :
  ```python
  comp.add_inst_branch(
      automaton="aut_valve",
      name="failure_check",
      source="valve_open",
      condition=lambda: comp.demand.value(),
      branches=[
          {"target": "panne_severe", "prob": 0.05,
           "effects": {"severity": 3, "panne_type": 1}},
          {"target": "panne_legere", "prob": 0.10,
           "effects": {"severity": 1, "panne_type": 2}},
          {"target": "ok"},  # complément 0.85 implicite, pas d'effets
      ],
  )
  ```
- Le helper crée la transition inst + enregistre les sensitive methods state-entry pour chaque branche avec effets non-vide.
- Doit être combinable avec `add_aut2st` (les target states peuvent être déclarés au préalable ou créés à la volée par le helper si non existants).

### Exemples & tests d'intégration

- **Round-trip déterministe** (`tests/pyc_obj/test_inst_001_roundtrip.py`) : 2 et 4 branches, vérifie `law.parameter(idx)`, `nbParam()`, `targetCount()` et `from_bkd().probs` après `to_bkd`. Pas de simulation, pas de χ².
- **Branchement multi-issue** (`tests/pyc_obj/test_inst_002_multi_branch.py`) : 4 branches dont une à proba complément, vérification des effets state-entry.
- **iSimu inst pending** (`tests/isimu/test_inst_panel.py`) : injection d'un système avec 2 inst pendantes simultanément, vérification de l'arbre, des défauts, et de la soumission atomique.
- **Exemple `examples/inst_branching_demo/`** : un cas d'usage type "demande d'ouverture vanne → 3 types de panne ou ok" avec instructions de pilotage iSimu (touches Enter / `b` / `s`) dans la docstring.

---

## Why This Approach

### Pourquoi finir le support des transitions inst maintenant ?
- Les bases existent, sont à 80%, et sont coincées par un commentaire "NOT WORKING" qui empêche de les utiliser sereinement.
- Le cas d'usage "branchement probabiliste à un instant donné" est central pour modéliser : tirage de type de panne, choix d'aiguillage, succès/échec d'opération conditionnelle, etc. Tout ce qui n'est pas une transition temporisée mais reste à des moments contraints.
- L'iSimu vient d'être stabilisé pour les transitions temporisées (cod3s-isimu 1.x) : c'est la fenêtre naturelle pour ajouter le support inst sans risquer de mélanger les chantiers.

### Pourquoi un identifiant de branche = target state (et non un name) ?
- Pycatshoo identifie une branche par son target index ; aucun champ "branch name" natif. Aligner cod3s sur ce modèle évite une couche de mapping inutile.
- L'utilisateur déclare déjà un target state nommé : le réutiliser comme identifiant de branche est cohérent avec ce que la sequence existante affiche (`comp.aut.transition → target_state`).
- Si deux branches doivent porter des effets différents, l'utilisateur crée deux states distincts (e.g. `panne_severe` vs `panne_legere`). C'est explicite, lisible, et cohérent avec `add_aut2st`.

### Pourquoi des effets via state-entry (et non via `addSensitiveMethod` sur la transition) ?
- L'API Pycatshoo `ITransition.addSensitiveMethod(name, cb, target_idx)` existe (signature 4-args), mais elle est plus obscure et redondante dès lors qu'on impose des targets distincts.
- Le pattern state-entry est déjà éprouvé dans `add_aut2st` : pas de mécanisme nouveau à inventer, pas de risque de divergence entre transitions inst et transitions temporisées qui partagent un même target.
- Si dans le futur deux branches doivent vraiment partager un target avec des effets différents, on ré-évaluera ; mais l'usage majoritaire (panne_1 / panne_2 / panne_3) est mieux servi par des states distincts.

### Pourquoi une UX "soumission atomique" en iSimu ?
- Contrainte technique Pycatshoo : à `t` donné, l'API ne permet pas de résoudre une inst, observer les conséquences, puis résoudre la suivante — toutes les inst pendantes sont drainées dans un seul `stepForward`.
- L'arbre dépliable avec sélection par défaut "branche max-proba" rend l'usage par défaut indolore (Enter pour soumettre les défauts), tout en permettant l'investigation déterministe (changer un choix avant de soumettre).
- Le marqueur `!` pour les branches déterministes (p=1) signale visuellement que le tirage n'a pas de degré de liberté, pour ne pas biaiser l'attention de l'utilisateur sur des choix inexistants.

---

## Key Decisions

| # | Décision | Rationale |
|---|----------|-----------|
| 1 | Une transition inst = 1 source + 1 condition (guard) + N branches. | Aligné avec la primitive Pycatshoo et avec le mental model utilisateur ("quand la garde est vraie, on tire"). |
| 2 | Une branche = `{target: str, prob: float \| None, effects: dict}`. **Pas de nom propre.** | L'identifiant naturel est le target state (déjà visible dans la sequence). Pycatshoo n'a pas de "branch name" natif. |
| 3 | Les target states **doivent être distincts** au sein d'une transition. | Évite l'ambiguïté dans l'arbre dépliable iSimu et dans la trace ; cohérent avec le pattern `add_aut2st`. |
| 4 | Les effets-par-branche sont appliqués via une **sensitive method state-entry** sur chaque target. | Réutilise un mécanisme éprouvé (`add_aut2st`), pas besoin d'introduire `ITransition.addSensitiveMethod(target_idx)`. |
| 5 | `to_bkd` envoie les `N-1` premières probas via `law.setParameter(p, i)` ; la dernière est calculée par Pycatshoo en complément. | Conforme à l'API Pycatshoo observée ; comportement actuel du code (à valider via round-trip déterministe `setParameter` ↔ `parameter`). |
| 6 | iSimu : les inst pendantes prennent la main sur le panneau temporisé tant qu'il en reste. | Reflète le phasage Pycatshoo (les inst se résolvent avant les temporisées). |
| 7 | iSimu : arbre dépliable, défaut = branche max-proba, marqueur `!` si déterministe (p=1), soumission atomique. | UX explicite et investigable, sans charge cognitive sur le cas commun. |
| 8 | iSimu : pas de `ReplanModal` (date) pour les inst — le temps n'avance pas. | Respecte la sémantique inst. |
| 9 | DSL : helper `comp.add_inst_branch(...)` analogue à `add_aut2st`, accepte `branches=[{target, prob, effects}]`. | Cohérent avec l'API existante ; un appel = une transition complète. |
| 10 | Phasage strict : Phase 1 (backend + audit round-trip + tests fonctionnels) → Phase 2 (iSimu) → Phase 3 (DSL helper + exemple), TDD-first à chaque phase. | Demande explicite ; permet un audit honnête de l'état actuel avant d'élargir la surface. |

---

## Open Questions

À traiter dans le plan d'implémentation :

1. **Audit `update_bkd`** : est-ce que le commentaire "NOT WORKING" décrit un vrai bug aujourd'hui, ou une préoccupation périmée ?
   - Premier RED test = round-trip déterministe : crée la transition avec `probs=[0.7, 0.3]`, lit `law.parameter(0)`, `law.nbParam()`, `targetCount()`, et `from_bkd().probs`. Aucune simulation.
   - Si vert d'office → suppression du commentaire dans le commit Phase 1.
   - Si rouge → investigation `setParameter` (mauvais index ? signature ? type ?). Le round-trip pointe directement la valeur fausse.

2. **Wiring effets state-entry et ré-entrée** : si le target state peut être atteint par plusieurs transitions (inst + temporisée), la sensitive method state-entry s'applique-t-elle uniformément ? Ou risque-t-elle de polluer le contexte d'une transition temporisée qui ne devrait pas appliquer les effets ?
   - Hypothèse : on associe les effets au **state**, pas à la transition source. Si l'utilisateur veut des effets distincts selon la transition source, il doit créer des states distincts. À documenter explicitement dans le helper.

3. **Détection iSimu des inst pendantes** : quelle API Pycatshoo expose les inst pendantes à `t` ?
   - Si `isimu_fireable_transitions` les retourne déjà avec `end_time == currentTime()` et un `occ_law` de type inst, on peut filtrer côté cod3s.
   - Sinon, exposer un `isimu_fireable_inst_transitions()` dédié.

4. **Ordre de soumission atomique** : si plusieurs inst pendantes sont issues du même composant, l'ordre dans lequel cod3s appelle `setTransPlanning` matérialise-t-il un ordre de tirage observable ?
   - À vérifier expérimentalement ; si oui, documenter ; sinon, l'ordre est purement présentationnel.

5. **`add_inst_branch` et création à la volée des target states** : si un target state cité dans `branches` n'existe pas dans l'automate, le helper le crée-t-il automatiquement ou exige-t-il qu'il soit pré-déclaré ?
   - Cohérence à viser avec `add_aut2st` (qui crée les 2 states automatiquement).
   - Tendance : exiger une déclaration préalable des states (l'utilisateur a souvent un automate à 3+ states avec ses propres règles d'entrée/sortie).

6. **Effets sur le source state quand on quitte** : pas envisagé pour l'instant. À écarter explicitement (YAGNI) sauf demande utilisateur.

---

## Next Steps

- [ ] Écrire le plan d'implémentation associé (`docs/plans/2026-05-05-feat-inst-transitions-plan.md`).
- [ ] Démarrer Phase 1 par un test round-trip déterministe (RED) sur le passage des probas à Pycatshoo.
- [ ] Lever ou justifier le commentaire "NOT WORKING" dans `automaton.py`.
- [ ] Ajouter la validation pydantic des contraintes (targets distincts, sum probs).
- [ ] Phase 2 : maquette du panneau "inst pending" iSimu (arbre, défauts, marqueur `!`).
- [ ] Phase 3 : `add_inst_branch` + exemple `examples/inst_branching_demo/`.
- [ ] Mettre à jour la doc utilisateur (`docs/user-guide/`) avec un section "Branchements probabilistes".
