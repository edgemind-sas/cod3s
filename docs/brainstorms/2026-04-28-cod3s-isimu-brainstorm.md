# Brainstorm — CLI `cod3s-isimu` (simulateur interactif TUI)

**Date** : 2026-04-28
**Sujet** : Conception d'un outil CLI `cod3s-isimu` permettant de piloter pas-à-pas une simulation `PycSystem` via une interface terminal full-screen (TUI), avec sélection manuelle des transitions, suivi des variables, historique horodaté et coloration des changements.
**Contexte** : `PycSystem` (`cod3s/pycatshoo/system.py:267`) expose déjà une API interactive complète (`isimu_start`, `isimu_stop`, `isimu_fireable_transitions`, `isimu_step_forward`, `isimu_step_backward`, `isimu_set_transition`). Un hook `isimu_start_cli()` (ligne 870) tente d'importer `from .isimu_cli import COD3SISimuCLI` mais le fichier `isimu_cli.py` est absent du repo — seul un `.pyc` orphelin subsiste. Un legacy `cod3s/pycatshoo/interactive_session.py` (basé sur `cmd.Cmd` + `colored`) est cassé (appelle `PycComponent.from_bkd` / `to_df` qui n'existent plus). L'API moteur est donc prête ; il manque l'UI.

---

## What We're Building

Un binaire `cod3s-isimu` (entry-point dans `pyproject.toml [project.scripts]`) lançant une **application Textual TUI** qui pilote la simulation pas-à-pas d'un `PycSystem`.

### Layout cible (4 panels)

```
┌─ Fireable transitions ──┐┌─ Components / Variables ─────────┐
│ [1] pump1.fail  d=12.3 ★││ filter: [pump_____________]      │
│ [2] pump2.fail  d=12.3 ★││ pump1                             │
│ [3] valve.open  d=∞     ││  ├─ working   true  → false     │ ← bold red (just changed)
│                         ││  ├─ flow      0.0   → 0.0       │
│ ★ = fires together      ││ pump2                             │
│                         ││  ├─ working   true                │ ← orange (≠ init)
└─────────────────────────┘└───────────────────────────────────┘
┌─ Last transition Δ ─────┐┌─ History (grouped by t) ─────────┐
│ pump1.working: T → F    ││ t=12.3 ▸ pump1.fail, pump2.fail  │
│ pump1.flow:    1.2 → 0  ││ t=0.0  ▸ <init>                  │
└─────────────────────────┘└───────────────────────────────────┘
status: t=12.3  step=1   [↵] fire  [b]ack  [r]eset  [e]xport  [q]uit
```

### Inputs
- `cod3s-isimu --model model.yaml` : réutilise le format YAML de `run-cod3s-study` (`imports:` + `system:` + `components:` + `connections:`).
- `cod3s-isimu --factory mymod:build_system` : alternative pour systèmes construits programmatiquement, où `build_system()` retourne un `PycSystem` peuplé.
- Options auxiliaires : `--log-level`, `--export-dir`.

### Sémantique d'interaction
- **Fire** : `[Enter]` sur une transition force-fire = `isimu_step_forward()` jusqu'à `endTime` de cette transition. Toutes les transitions de même `endTime` se déclenchent ensemble (comportement natif `stepForward`). C'est ce qui justifie le marqueur ★ "fires together".
- **Highlight prédictif** : quand le curseur se pose sur une transition, toutes les autres transitions de la liste partageant le même `endTime` (donc qui se déclencheraient avec elle) sont mises en évidence (★).
- **Step backward** : `[b]` → `isimu_step_backward(reset_planning=True)`.
- **Reset** : `[r]` → `isimu_stop()` + `isimu_start()`.
- **Re-plan (avancé)** : `[p]` ouvre une mini-modale pour `setTransPlanning(trans, t)` à un instant arbitraire. Pour explorer des scénarios non-naturels.
- **Export** : `[e]` sérialise `system.isimu_sequence` en CSV et JSON.
- **Quit** : `[q]` → `isimu_stop()` puis sortie.

### Coloration des variables
- Valeur courante == valeur initiale → couleur neutre (par ex. blanc dim).
- Valeur courante ≠ valeur initiale **et** non changée à la dernière transition → orange.
- Valeur changée à la dernière transition → **gras + rouge** (ou couleur d'accent), avec affichage `init → current`.

### Filtrage
- Champ texte au-dessus du panel "Components / Variables".
- Sémantique substring sur `f"{comp_name}.{var_name}"` (insensible à la casse, MVP). Vide = tout afficher.

### Historique
- Liste anti-chronologique (plus récent en haut) groupée par instant `t`. Chaque ligne : `t=<value>  ▸ <trans1>, <trans2>, ...`.
- Source : `system.isimu_sequence.transitions` (déjà alimenté par `isimu_step_forward`).

---

## Why This Approach

### Pourquoi un TUI Textual ?
- Le cahier des charges (4 panels simultanés, filtres live, mise en évidence sur navigation) cartographie naturellement sur un layout TUI réactif.
- Textual offre les primitives nécessaires (`DataTable`, `Input`, `Tree`, `Static`, bindings clavier, theming) sans réinventer la roue.
- Pas de dépendance navigateur ; fonctionne en SSH/headless ; cohérent avec la culture CLI du projet.
- Rich (sous-jacent à Textual) gère déjà le rendu coloré dont `automaton.py:__repr__` utilise déjà des codes ANSI — alignement naturel.

### Pourquoi double mode YAML + factory ?
- YAML = continuité avec `run-cod3s-study`, mêmes fichiers réutilisables, pas de friction pour les utilisateurs existants.
- Factory = échappatoire pour les systèmes complexes ou paramétrés à la volée (génération programmatique). Implémentation triviale (un `importlib` + `getattr`).

### Pourquoi force-fire (et non re-planification systématique) ?
- C'est le comportement **naturel** de PyCATSHOO : sélectionner = avancer le temps, le moteur fire ce qui doit l'être.
- La re-planification arbitraire est un cas de niche (exploration de scénarios "what-if") → mode avancé via raccourci dédié, pas comportement par défaut.

### Pourquoi inclure step-backward/reset/export dès le MVP ?
- `isimu_step_backward` et `isimu_stop`/`isimu_start` sont déjà implémentés sur `PycSystem` → coût marginal quasi-nul.
- L'export utilise `PycSequence` qui collecte déjà les transitions → c'est principalement de la sérialisation.

---

## Key Decisions

| # | Décision | Rationale |
|---|----------|-----------|
| 1 | UI = **Textual TUI** (pas Cmd/Rich-only, pas web). | Layout multi-panels avec filtres live et highlights dynamiques. Cohérent CLI/SSH. |
| 2 | Loading = **YAML (par défaut) + factory Python (option)**. | Continuité avec `run-cod3s-study` ; échappatoire pour systèmes programmatiques. |
| 3 | **Force-fire** sur sélection : avancer le simulateur jusqu'à `endTime` de la transition choisie ; toutes les transitions de même `endTime` se déclenchent ensemble. | Comportement natif PyCATSHOO ; explique et justifie le marqueur ★ "fires together". |
| 4 | Marqueur ★ calculé en groupant les transitions fireable par `endTime` égal (à un epsilon près). | Donne immédiatement à l'utilisateur la clé causale "qui part avec qui". |
| 5 | Coloration variables : neutre = init, orange = ≠ init, **gras+rouge** = changée à la dernière transition. | Reproduit fidèlement la spec utilisateur ; les deux états (≠ init, just-changed) sont orthogonaux. |
| 6 | Filtre = substring case-insensitive sur `comp.var` (MVP). | Simple, suffisant. Glob/regex en v2 si besoin. |
| 7 | Historique groupé par `t` (instant de déclenchement). | Reflète la sémantique PDMP : plusieurs transitions à un même `t` constituent un "événement composite". |
| 8 | Step backward, reset, export CSV/JSON, re-plan **inclus dans le MVP**. | API moteur déjà prête ; coût marginal faible. |
| 9 | Le legacy `cod3s/pycatshoo/interactive_session.py` (cassé) et le `.pyc` orphelin `isimu_cli.cpython-310.pyc` sont **supprimés** lors de l'implémentation. | Code mort, risque de confusion. Le hook `isimu_start_cli()` sera réorienté vers la nouvelle entrée TUI. |
| 10 | Le binaire `cod3s-isimu` se loge dans `cod3s/scripts/run_cod3s_isimu.py` (parallèle à `run_cod3s_study.py`). Le code Textual va dans un sous-package `cod3s/pycatshoo/isimu/` (app, panels, theming). | Sépare le wiring CLI de la logique TUI ; testable séparément. |
| 11 | `textual` ajouté en **dépendance optionnelle** `[project.optional-dependencies] isimu = ["textual>=0.50"]`. | N'alourdit pas l'install par défaut ; `pip install cod3s[isimu]` pour activer. |

---

## Open Questions

À traiter dans la phase de plan d'implémentation :

1. **Tolérance pour le regroupement "fires together"** :
   - Comparer les `endTime` à l'égalité stricte ? À un epsilon (et lequel) ?
   - PyCATSHOO peut-il avoir deux transitions planifiées à des `endTime` numériquement très proches mais non identiques ? Si oui, l'utilisateur s'attend probablement à ce qu'elles soient groupées.
   - **Pressenti** : égalité stricte d'abord ; epsilon configurable si retours utilisateurs.

2. **Modèle de rafraîchissement Textual** :
   - Re-render complet à chaque transition (simple, peut clignoter sur grands systèmes) vs widgets réactifs avec diff (plus performant).
   - **Pressenti** : commencer par re-render complet ; profiler sur un système réel avant d'optimiser.

3. **Détection des changements pour le panel "Last transition Δ"** :
   - Snapshot avant `isimu_step_forward()`, comparaison avec snapshot après → diff sur `(comp, var, value_before, value_after)`.
   - À implémenter côté TUI ou ajouter une méthode `isimu_step_forward_with_diff()` à `PycSystem` ?
   - **Pressenti** : côté TUI dans un premier temps ; remonter dans `PycSystem` si réutilisable.

4. **Variables continues (PDMP)** :
   - Les variables continues évoluent **entre** les transitions (ODEs). Une variable continue peut donc être ≠ init sans qu'aucune transition discrète ne l'ait "changée".
   - Comment gérer leur coloration et leur diff ? Snapshot avant/après transition uniquement ? Sampling pendant l'évolution continue ?
   - **Pressenti** : MVP = snapshot avant/après transition. Mention explicite dans la doc de la limitation.

5. **Énumération des variables d'un `PycComponent`** :
   - `PycComponent` n'a pas (plus) de méthode publique `to_df()`/`variables_list()` (le code est commenté `component.py:1924-1953`). Il faudra soit ré-exposer, soit interroger directement le backend `pyc.CComponent` (`variables()`, `messageBoxes()`, ...).
   - **Pressenti** : ajouter une méthode utilitaire propre à `PycComponent` (ou un helper dans le module isimu) qui retourne la liste des `PycVariable.from_bkd(v)`.

6. **Robustesse aux gros systèmes** :
   - Combien de composants × variables avant que la TUI rame ? Pagination du panel central ? Tree expansible (replier les composants) ?
   - **Pressenti** : `Tree` widget Textual avec composants repliables ; pas de pagination en MVP.

7. **Tests** :
   - Comment tester une app Textual ? `textual` fournit `App.run_test()` / `Pilot` pour scénarios automatisés.
   - Le moteur `isimu_*` peut être testé sans la TUI, séparément.
   - **Pressenti** : tests unitaires sur les helpers (groupement par `endTime`, calcul de diff, formatting) ; un ou deux tests d'intégration `Pilot` pour les raccourcis principaux.

8. **Compatibilité `--study-specs`** :
   - Le YAML de `run-cod3s-study` accepte aussi un `--study-specs` (failure_modes, events, indicators). En mode interactif, les indicateurs n'ont pas de sens (pas de stats Monte-Carlo) mais les `failure_modes` / `events` doivent être appliqués à la construction du système.
   - **Pressenti** : accepter `--study-specs` en option et appliquer uniquement `add_failure_modes` / `add_events` (skip indicators / targets).

9. **Sort de `isimu_start_cli()` sur `PycSystem`** :
   - Garder le hook (et le réorienter vers la nouvelle TUI) ou le supprimer au profit du seul binaire `cod3s-isimu` ?
   - **Pressenti** : le réorienter vers `cod3s.pycatshoo.isimu.app:run_isimu(system)` pour permettre un appel programmatique depuis un script Python.

---

## Next Steps

- [ ] Valider la portée du MVP avec l'utilisateur (ce document).
- [ ] Lancer `/workflows:plan` pour produire le plan d'implémentation détaillé.
- [ ] Trancher les open questions 1, 4, 8 dans le plan.
- [ ] Définir les tests d'acceptation MVP (scénarios `Pilot` + tests unitaires).
- [ ] Implémenter le squelette Textual + binding sur `PycSystem.isimu_*`.
- [ ] Supprimer `interactive_session.py` et le `.pyc` orphelin.
- [ ] Mettre à jour `pyproject.toml` (entry-point + extras `[isimu]`).
- [ ] Documenter dans `docs/` (page MkDocs dédiée).
