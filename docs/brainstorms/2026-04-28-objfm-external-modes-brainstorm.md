# Brainstorm — Modes `external` et `external_rep_indep` de `ObjFM`

**Date** : 2026-04-28
**Sujet** : Finalisation sémantique et comportementale des modes `external` et `external_rep_indep` du paramètre `behaviour` de `ObjFM`.
**Contexte** : Reprise après ~3 mois d'inactivité sur le projet. La spec `FEAT_OBJFM_SPECS.md` (2026-01-15) a été partiellement implémentée (commits `59fc27d`, `721414c`, WIP `0513249`) avec 4 tests pour `external` et 0 test pour `external_rep_indep`. Le code contient un `TODO` explicite sur la condition de réparation des targets en `external_rep_indep`. Plusieurs divergences spec/code ont été constatées.

---

## What We're Building

Trois modes de comportement pour `ObjFM` paramétrés par `behaviour` :

### 1. `internal` (par défaut, inchangé)
Comportement historique. Les automates de défaillance vivent dans l'`ObjFM`, qui applique directement `failure_effects` / `repair_effects` sur les variables des targets.

### 2. `external` (sémantique arrêtée)
- L'`ObjFM` conserve ses automates `frun__cc_X` (combos d'ordre N, mécanisme inchangé).
- L'`ObjFM` crée en plus, **dans chaque target**, un automate `{fm_name}` à 2 états (`{repair_state}` / `{failure_state}`) avec transitions instantanées (`delay(0)`).
- Une variable booléenne `ctrl_{fm_name}_{target_name}` par target sert de canal de synchronisation.
- **Verrouillage mutuel** : l'ObjFM ne peut tirer occ que si tous les targets de la combo sont en rep ; il ne peut tirer rep que si tous sont en occ. Symétriquement, le target ne tire occ que si `ctrl == True`, rep que si `ctrl == False`.
- **`failure_effects` / `repair_effects` appliqués sur l'automate du target** (et non plus sur l'ObjFM). Validé par les tests 002/003/004.

### 3. `external_rep_indep` (sémantique nouvellement clarifiée)
- Mêmes automates ObjFM et target qu'en `external`, mais le couplage est **transitoire** : l'ObjFM agit comme un **déclencheur impulsionnel**.
- **Cycle ObjFM** :
  - `rep → occ` : selon la loi normale (ex: `exp(λ)`), conditionnée par `failure_cond` originale + "tous targets de la combo en rep". Effet : `ctrl_var := True` pour les targets concernés.
  - `occ → rep` : `delay(0)` **sans condition**. Pas d'effet sur les ctrl_vars. L'ObjFM se "réinitialise" instantanément après avoir transmis la défaillance.
- **Cycle target** :
  - `rep → occ` : `delay(0)` conditionné par `ctrl == True`. Effet : applique `failure_effects` du FM.
  - `occ → rep` : **loi de l'ordre 1** de l'ObjFM (`exp(μ_1)` ou `delay(ttr_1)`), conditionnée par la `repair_cond` originale de l'ObjFM évaluée sur le target courant. Effet : applique `repair_effects` + `ctrl_var := False`.

---

## Why This Approach

### Pourquoi un mode `external` ?
- **Visibilité locale** : l'état de défaillance est observable directement dans le composant (`comp.automata_d["frun"].get_state_by_name("occ")._bkd.isActive()`), utile pour les indicateurs et l'analyse de séquences.
- **Découplage** : un target sait s'il est failed sans interroger l'ObjFM.
- **Cohérence avec les outils d'analyse** : sequences/SequenceAnalyser tracent les transitions visibles, donc avoir l'état au niveau target enrichit la trace.

### Pourquoi un mode `external_rep_indep` ?
- **Modélisation de réparations indépendantes** : équipes de maintenance locales, interventions parallèles, taux de réparation propres à chaque équipement.
- **Réalisme des analyses de disponibilité** : permet une réparation stochastique distincte de l'évènement déclencheur.
- **Causes communes asymétriques** : un évènement initial peut faire tomber plusieurs équipements, mais leur réparation suit chacune sa propre dynamique.

### Pourquoi le modèle "pulse" pour `external_rep_indep` ?
- L'ObjFM en `external` reste verrouillé en `occ` tant que les targets ne sont pas réparés ensemble. Avec des réparations indépendantes, ce verrouillage n'a plus de sens.
- En faisant l'ObjFM "pulser" (occ → rep instantané), on libère sa dynamique : il peut tirer un nouveau combo dès que les targets concernés sont à nouveau dispos.
- Sémantique épurée : ObjFM = générateur d'évènements, target = porteur d'état persistant.

---

## Key Decisions

| # | Décision | Rationale |
|---|----------|-----------|
| 1 | `external` garde un verrouillage mutuel ObjFM/target. | Permet une analyse séquentielle propre (chaque transition visible). |
| 2 | `external_rep_indep` adopte un **modèle pulse** : ObjFM transite occ→rep en `delay(0)` sans condition après avoir déclenché. | Découple proprement les dynamiques de défaillance et de réparation. |
| 3 | `failure_cond` étendue identique aux deux modes : `failure_cond_originale AND tous_targets_de_la_combo_en_rep`. | Empêche les déclenchements redondants. |
| 4 | **`failure_effects` et `repair_effects` toujours appliqués via l'automate du target** (pas l'ObjFM). | Comportement actuel du code, déjà testé (002/003/004). La spec d'origine ("ignorés avec warning") est obsolète. |
| 5 | En `external_rep_indep`, la **loi de réparation du target = loi d'ordre 1** (μ_1 ou ttr_1) quelle que soit la combo qui a déclenché. | Loi de réparation locale intrinsèque au composant, indépendante de la cause. |
| 6 | En `external_rep_indep`, la **condition de réparation du target = `repair_cond` originale de l'ObjFM** évaluée sur le target courant. | Cohérent avec internal/external. Résout le `TODO` ligne 1516. |
| 7 | Effet de la transition `target.rep` en `external_rep_indep` : applique `repair_effects` + remet `ctrl_var = False` pour autoriser une nouvelle défaillance. | Mécanisme de "retour à la disponibilité" piloté par le target. |
| 8 | Pas de warnings sur `failure_effects` / `repair_effects` (commit 721414c). La spec doit être corrigée. | Décision implicite ratifiée par le commit ; alignement spec à faire. |

---

## Open Questions

À traiter dans la phase de plan d'implémentation :

1. **Mécanisme de mise à jour des `ctrl_vars`** :
   - Le code actuel utilise une **sensitive method** qui calcule `ctrl_var = OR(automates_impactants en occ)`. Cela fonctionne pour `external`.
   - Pour `external_rep_indep` (modèle pulse), ce mécanisme tombe en défaut : l'ObjFM repasse en rep instantanément, la sensitive method recalcule, ctrl_var redescend à False avant que le target ait propagé.
   - **Approche pressentie (A)** : remplacer la sensitive method par des **effets directs sur les transitions** (cohérent dans les deux modes external et external_rep_indep). Risque de régression sur `external` à valider.

2. **Périmètre de tests `external_rep_indep`** (à définir avant implémentation, TDD-first) :
   - Création des automates target + ctrl_vars.
   - Cycle pulse sur un target unique.
   - Cycle pulse avec combo d'ordre 2 (cc_12).
   - Réparation indépendante : C1 répare avant C2, vérifier que la combo cc_12 ne se redéclenche pas tant que C2 n'est pas en rep.
   - Vérification de la loi μ_1 utilisée pour tous les ordres.
   - Vérification de la `repair_cond` originale appliquée localement.
   - Compatibilité ObjFMDelay (loi `delay(ttr_1)`).
   - Tests d'erreur : `behaviour` invalide, conflit de nom d'automate.

3. **Mise à jour de la spec `FEAT_OBJFM_SPECS.md`** :
   - Section "external" : retirer la mention "failure_effects ignorés avec warning", remplacer par "appliqués via l'automate du target".
   - Section "external_rep_indep" : préciser le modèle pulse et les conditions/lois exactes pour les transitions ObjFM et target.
   - Tableau récapitulatif à ajuster.

4. **Backward compatibility** :
   - `internal` (défaut) inchangé : aucun risque.
   - `external` actuellement en service via 4 tests : à ne pas casser. Si on bascule sur l'approche A (effets de transition au lieu de sensitive method), valider en relançant la suite complète.

5. **WIP commit `0513249` (`print(fm)`)** :
   - Déjà nettoyé dans le commit en cours de préparation.

---

## Next Steps

- [ ] Décider de l'approche technique pour les ctrl_vars (A/B/C) — ouvert pour le plan.
- [ ] Rédiger les tests `test_comp_failure_external_rep_indep_*` (TDD).
- [ ] Implémenter / corriger `_create_target_automaton` et la logique de transition ObjFM en `external_rep_indep`.
- [ ] Mettre à jour `FEAT_OBJFM_SPECS.md`.
- [ ] Valider la non-régression sur `external` (tests 001-004).
- [ ] Bump version + commit propre.
