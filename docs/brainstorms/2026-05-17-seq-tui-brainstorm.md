# Brainstorm — TUI d'analyse interactive des séquences PyCATSHOO

**Date** : 2026-05-17
**Sujet** : Nouvel outil TUI (`cod3s-seq`) pour charger des séquences post-Monte-Carlo, configurer interactivement le pipeline d'analyse (groupement, filtrage de cycles ObjFM, séquences minimales) et observer finement le comportement de chaque algorithme.
**Contexte** : La pipeline d'analyse des séquences vient d'être consolidée dans cod3s 1.4.0 (auto-discovery ObjFM, filter_objfm_cycles symétrique, ~2× speedup, equivalence tests). L'outil cible un workflow mixte R&D (debug des algos) + analyste sûreté (charger un dump, voir les minimales).

---

## What We're Building

Un binaire console `cod3s-seq` qui ouvre un TUI Textual permettant de :

1. **Charger** un dump de séquences depuis un fichier (XML PyCATSHOO ou JSON cod3s `sequences_all.json` / `sequences_minimal.json` produit par `run-cod3s-study`).
2. **Empiler** des opérations du pipeline sur la liste vivante de séquences : `group_sequences`, `filter_objfm_cycles`, `compute_minimal_sequences` plus les primitives low-level `rm_events_by_obj`, `rm_events_ordered_pattern`, `rename_events`.
3. **Observer** après chaque étape la liste résultante + un diff bref (nb de signatures, ∆ vs étape précédente, top sequences). Undo disponible (snapshot par étape).
4. **Inspecter** une séquence en détail (events un par un avec temps, target, poids, probabilité).
5. **Sauvegarder / charger** le pipeline configuré en YAML, et **exporter** les séquences résultantes en JSON cod3s + CSV / Markdown lisible.

---

## Why This Approach

### Décisions structurantes prises pendant le brainstorm

1. **Usage = R&D ∩ analyste sûreté.** Un seul outil sert les deux : ergonomie expert (jouer fin avec les params) **et** path simple (load → applique pipeline standard → export). Pas de mode séparé : la même surface fonctionne pour les deux populations.

2. **Source = post-mortem fichier uniquement.** Pas de simulation live depuis l'outil — l'utilisateur arrive avec un dump déjà produit. Deux formats supportés au MVP : **XML brut PyCATSHOO** (`sequences.xml` produit par `setResultFileName`) et **JSON cod3s** (`sequences_all.json` / `sequences_minimal.json` produit par `run-cod3s-study` via `_persist_sequence_analysis_artifacts`). Le format JSON cod3s a un `schema_version` et chaque séquence est `Sequence.model_dump(mode="json")` — la déserialisation est triviale via `ObjCOD3S.from_dict`.

3. **Mode d'observation = pipeline linéaire empilable.** Une seule liste vivante de séquences. Chaque étape est appliquée in-place sur la liste, et un snapshot est conservé pour permettre l'**undo**. À chaque étape on affiche un mini-diff : nombre de signatures avant/après, ∆, et éventuellement quelles signatures ont fusionné. Choix vs **branches parallèles** (split-pane raw/minimal) : le linéaire est plus simple à implémenter, l'undo couvre 80 % du besoin de comparaison, et l'export d'un état intermédiaire donne le besoin restant.

4. **Layout = 3 panneaux verticaux** (pattern proche de cod3s-isimu) :
   - **Gauche : Pipeline** — liste des étapes empilées avec leur résultat compact (e.g. `filter_objfm_cycles → 7 sigs ∆=-2406`). Curseur, `+` pour ajouter, `u` pour undo, `Enter` pour ré-configurer une étape.
   - **Milieu : Sequences** — DataTable des séquences courantes (signature compacte, weight, probability). Curseur, `/` pour filtrer textuel, `Enter` pour drill-down.
   - **Droite : Detail** — événements de la séquence sélectionnée, un par ligne (time, obj, attr, type), plus métadonnées (target_name, weight, probability, end_time).

5. **Opérations exposées = trio canonique + 3 low-level.** Le user peut empiler `group_sequences`, `filter_objfm_cycles` (avec ses params : `objfm_internal` / `objfm_external` / `failure_state` / `repair_state`), `compute_minimal_sequences`, plus `rm_events_by_obj`, `rm_events_ordered_pattern`, `rename_events`. Pas d'auto-discovery côté `filter_objfm_cycles` : la source étant un fichier, le `_system` n'est jamais attaché — l'utilisateur saisit les ObjFM names dans un modal.

6. **Persistance = save/load pipeline YAML + export résultats.** Pipeline YAML : liste d'étapes avec leurs params, sérialisable et partageable. Format proposé :
   ```yaml
   pipeline:
     - op: group_sequences
     - op: filter_objfm_cycles
       objfm_internal: [pump_X__def_pump]
       failure_state: occ
       repair_state: rep
     - op: compute_minimal_sequences
   ```
   Export résultats : reuse de `_persist_sequence_analysis_artifacts` pour générer `sequences_minimal.json` cod3s, plus CSV (pour Excel) et Markdown (pour rapport).

7. **Architecture = standalone.** Code dans `cod3s/pycatshoo/seq_tui/` parallèle à `isimu/`. Pas d'extension de cod3s-isimu (use cases trop différents : isimu pilote une simulation step-by-step en process ; seq_tui charge un dump post-mortem et y applique des règles d'analyse). Pas de refactor `tui_common` au MVP — on duplique ~100 LoC de patterns Textual (state snapshot, App scaffolding) en l'assumant.

---

## Key Decisions

| Décision | Choix | Pourquoi |
|---|---|---|
| Public cible | Mixte R&D + analyste | Une seule surface couvre les deux usages |
| Source de données | XML + JSON cod3s post-mortem | Pas besoin de simu live ; les dumps existent déjà |
| Auto-discovery ObjFM | **Non** dans le TUI | Le système n'est pas en mémoire (path post-mortem) |
| Modèle d'observation | Pipeline linéaire + undo | Plus simple que branches parallèles, couvre le besoin |
| Layout | 3 panneaux verticaux (pipeline / list / detail) | Pattern cod3s-isimu, lisible, expressif |
| Opérations MVP | 6 méthodes (trio + 3 low-level) | Surface complète, mode expert satisfait |
| Persistance | YAML pipeline + export JSON/CSV/MD | Réplicable, partageable, exploitable en aval |
| Architecture | Standalone `cod3s/pycatshoo/seq_tui/` | Domaine séparé, pas de pollution d'isimu |
| Binaire console | `cod3s-seq` | Cohérent avec `cod3s-isimu`, `run-cod3s-study` |

---

## Surface CLI envisagée

```bash
# Chargement direct d'un fichier
cod3s-seq sequences.xml
cod3s-seq sequences_all.json
cod3s-seq sequences_minimal.json

# Avec pipeline pré-configuré (auto-applique au load)
cod3s-seq --pipeline pipeline.yaml sequences.xml

# Format détecté via extension; option explicite si besoin
cod3s-seq --format xml sequences.xml
cod3s-seq --format json-cod3s sequences_minimal.json
```

À l'intérieur du TUI :
- `+` ouvre un menu d'ajout d'étape (modal listant les 6 opérations) → modal de paramétrage pour celles qui en ont
- `u` undo (revient à l'état avant la dernière étape)
- `r` redo
- `e` export
- `s` save pipeline YAML
- `l` load pipeline YAML
- `/` filtre textuel sur la liste de séquences
- `q` quit

---

## Cas d'usage cibles

### Cas 1 : Analyste sûreté reçoit `sequences_minimal.json` d'une étude

1. `cod3s-seq sequences_minimal.json` → liste déjà minimale s'affiche.
2. Parcourt les top-N séquences, drill-down sur les plus pesées.
3. Export Markdown pour son rapport.

### Cas 2 : Roland audite la pipeline sur un nouveau modèle

1. `cod3s-seq sequences.xml` → 5000 trajectoires brutes.
2. Empile `group_sequences` → 2413 signatures.
3. Empile `filter_objfm_cycles` avec les ObjFM names → 7 signatures, diff visible.
4. Empile `compute_minimal_sequences` → 4 minimales, vérifie la symétrie.
5. Undo → re-essaye avec un `failure_state="ko"` pour un futur ObjFM custom.
6. Save pipeline YAML pour rejouer sur d'autres XML.

### Cas 3 : Debug d'un cas pathologique

1. Charge `sequences.xml` d'un système complexe.
2. Au lieu de `filter_objfm_cycles`, empile `rm_events_ordered_pattern` avec un pattern regex custom pour expérimenter.
3. Compare avec la version standard via undo + ré-empile.
4. Si le pattern custom est gagnant, save YAML.

---

## Open Questions

1. **Renderer des temps moyennés vs liste de temps.** `group_sequences` moyenne les temps des events fusionnés. Le panneau détail affiche-t-il la moyenne (concis) ou la liste des temps individuels par event (volumineux mais informatif) ? **Reco : moyenne par défaut, toggle `t` pour voir la distribution.**

2. **Comparaison de deux étapes non-adjacentes.** L'undo couvre "voir l'état précédent". Mais si l'utilisateur veut comparer "post-group" vs "post-minimal" (3 étapes plus loin), il doit faire undo×3. **Reco : ajouter un raccourci `c` qui split temporairement l'écran avec l'état d'une étape antérieure choisie au curseur dans le panneau pipeline. À ajouter en v2 si demandé.**

3. **Limitation du panneau details quand events > 100.** Quelle stratégie : pagination, scroll, truncation ? **Reco : scroll natif Textual, pas de truncation arbitraire — sinon le user perd des events critiques.**

4. **Modal de paramétrage `filter_objfm_cycles`.** L'utilisateur doit saisir des listes de noms ObjFM. Comment ? Un champ texte multi-ligne où il écrit `["fm1", "fm2"]` ? Une UI sélection à cocher depuis les `obj` distincts dans la trace ? **Reco : champ texte au MVP, faciliter en v2 avec une checklist des `obj` détectés dans la trace.**

5. **JSON cod3s : déserialisation des `Sequence`.** Le format actuel produit par `study_runner` est `Sequence.model_dump(mode="json")` — donc `ObjCOD3S.from_dict` doit le reconstruire. Vérifier que le round-trip Sequence + SeqEvent fonctionne sans perte (cf. tests existants sur ObjCOD3S polymorphisme). **Probablement OK, à confirmer dans le plan d'implémentation.**

6. **Schéma YAML pipeline.** Au-delà du format proposé (liste d'`op` + params), faut-il anticiper des features futures (conditions, branchements, includes) ? **Reco : MVP simple liste d'op, pas de Turing-complétude.**

7. **Couplage à `_persist_sequence_analysis_artifacts`.** Pour produire le JSON cod3s à l'export, on peut soit appeler la fonction privée de `study_runner.py`, soit reproduire le format. **Reco : extraire/promouvoir `_persist_sequence_analysis_artifacts` en helper public dans `cod3s.pycatshoo.sequence` au passage, et l'utiliser des deux côtés.**

---

## Non-Goals (YAGNI)

- Pas de simulation live depuis l'outil (cf. cod3s-isimu pour ça).
- Pas de visualisation graphique (graphes d'arborescence, plots) — terminal seul.
- Pas de comparaison branches parallèles multiples au MVP (l'undo suffit).
- Pas de scripting embarqué (l'utilisateur compose le pipeline via YAML / TUI, pas via Python depuis l'outil).
- Pas de support multi-fichier (un seul fichier source par session).
- Pas d'édition manuelle de séquences individuelles (drop d'une seule trajectoire) — l'outil opère par règles.

---

## Acceptance Criteria du MVP

1. `cod3s-seq examples/ccf_sequence_asymmetry/results-ccf-demo/sequences.xml` charge 5000 séquences brutes.
2. L'utilisateur peut empiler interactivement les 3 opérations canoniques et voir le diff après chaque.
3. Les 3 opérations low-level sont accessibles via le même mécanisme.
4. Le pipeline canonique appliqué via le TUI produit le même résultat que la pipeline programmatique (sequences_minimal identiques, vérifiable par export JSON puis diff vs un dump de référence produit par `analyser.compute_minimal_sequences`).
5. Le pipeline configuré peut être sauvegardé en YAML, rechargé, et produit le même résultat.
6. Les séquences résultantes sont exportables en JSON cod3s, CSV, Markdown.
7. Undo fonctionne sur toute la profondeur du pipeline.

---

## Next Step

Passer en mode plan via `/workflows:plan` pour cadrer :
- Structure des fichiers (`cod3s/pycatshoo/seq_tui/{app,panels,state,modals,loader,exporter}.py`).
- Architecture du State snapshot et de l'undo stack.
- Phasing du MVP en commits atomiques (loader → state + panels → empilage d'étape → modaux paramétrage → undo → save/load YAML → export).
- Tests : unitaires pour loader / exporter, snapshots Textual pour les panneaux.
- Estimation effort : ~1.5-2 jours de dev solo.
