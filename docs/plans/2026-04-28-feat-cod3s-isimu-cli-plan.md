---
title: feat — Add `cod3s-isimu` interactive simulator CLI (Textual TUI)
type: feat
date: 2026-04-28
brainstorm: docs/brainstorms/2026-04-28-cod3s-isimu-brainstorm.md
---

# `cod3s-isimu` — Interactive Simulator CLI (Textual TUI)

## Overview

Livrer un nouvel outil en ligne de commande `cod3s-isimu` qui ouvre une interface terminal full-screen (Textual TUI) pilotant pas-à-pas un `PycSystem` PyCATSHOO. L'utilisateur sélectionne manuellement les transitions à tirer, observe en direct l'évolution des composants/variables et l'historique horodaté. L'API moteur interactive (`isimu_*`) existe déjà sur `PycSystem` (`cod3s/pycatshoo/system.py:846-1107`) ; ce plan se concentre sur (1) une couche TUI propre et testable, (2) l'extraction de helpers de chargement YAML aujourd'hui enfouis dans `run_cod3s_study.py`, et (3) le nettoyage du code mort (`interactive_session.py` cassé + `.pyc` orphelin).

Cible MVP : 4 panels (`fireable transitions`, `components/variables` filtrables, `last-Δ`, `history grouped by t`), force-fire sur sélection, marqueur ★ "fires together", coloration neutre/orange/gras-rouge, step-backward, reset, export CSV/JSON, re-plan avancé.

---

## Problem Statement

### Ce qui ne marche pas / manque aujourd'hui

1. **Le hook `PycSystem.isimu_start_cli()` est cassé** (`cod3s/pycatshoo/system.py:870-883`) : il importe `from .isimu_cli import COD3SISimuCLI` mais le fichier `cod3s/pycatshoo/isimu_cli.py` est absent du repo (seul `cod3s/pycatshoo/__pycache__/isimu_cli.cpython-310.pyc` subsiste). Toute tentative d'usage interactif côté Python lève `ImportError`.
2. **`cod3s/pycatshoo/interactive_session.py` (163 lignes) est mort-vivant** : il appelle `PycComponent.from_bkd(...)` (ligne 150) et `comp.to_df()` (ligne 156) qui n'existent plus (`cod3s/pycatshoo/component.py:1924-1953` montre le code commenté). Ce module ne tourne pas et perturbe la lecture du code.
3. **Pas de point d'entrée CLI** : `pyproject.toml:45-46` ne déclare que `run-cod3s-study`. Aucun moyen pour un utilisateur final de lancer la simu interactive sans écrire un script Python ad-hoc.
4. **`run_cod3s_study.py` n'expose pas les helpers de chargement YAML** : `import_module_from_path` (`cod3s/scripts/run_cod3s_study.py:21-49`) et le bloc lignes 124-222 (lecture YAML → `system.add_components/connections/failure_modes/events`) ne sont pas factorisés. Tout outil voulant "charger un système COD3S à partir d'un YAML" doit dupliquer ce code.
5. **Bug subtil dans `PycSystem.isimu_start()`** (`cod3s/pycatshoo/system.py:846-857`) : la méthode appelle `self.startInteractive()` puis **immédiatement** `self.stepForward()`, et seulement *après* (ligne 857) crée une nouvelle `PycSequence()`. Conséquence : les transitions tirées au pas zéro (typiquement les `delay(0)` initiaux) **ne sont pas enregistrées** dans `isimu_sequence`. Le TUI doit corriger ou contourner.
6. **`PycTransition.end_time` n'est pas un horodatage de tir** mais l'`endTime` planifié vu à un moment donné ; il est muté lors du calcul de fireable (`cod3s/pycatshoo/system.py:931-933`). L'historique horodaté demandé par le brainstorm ("grouper par instant de déclenchement") nécessite donc de **capturer `system.currentTime()`** au moment du `step_forward()` côté CLI.
7. **`PycSequence` n'a pas d'export CSV/JSON** (`cod3s/pycatshoo/sequence.py:17-27`). Tout export doit être assemblé à la main (`pd.DataFrame([t.model_dump() for t in seq.transitions])`).
8. **Pas d'apprentissages institutionnels** : `docs/solutions/` n'existe pas. Toutes les contraintes (singleton C++ PyCATSHOO, `terminate_session()` obligatoire, Python 3.10.x strict) sont à respecter à partir du code et de la mémoire `project_python_version`.
9. **`mkdocs.yml` référence un dossier `docs/user-guide/` absent du disque** (`mkdocs.yml:51-58`). À créer pour héberger la doc du nouveau CLI.

### Pourquoi maintenant

- Les hooks `isimu_start_cli` et le code commenté `# system.isimu_start(...)` (`cod3s/scripts/run_cod3s_study.py:226-234`) prouvent que le besoin est connu de longue date mais n'a jamais abouti.
- Les modes `objfm` `external_rep_indep` qui viennent d'être livrés produisent des comportements non-triviaux (cycles pulse, plusieurs `delay(0)` chaînés) qu'il est devenu **très difficile à debugger sans un pas-à-pas** observable.
- Reprise de projet après ~3 mois d'inactivité ; un outil interactif raccourcira drastiquement la boucle de validation.

---

## Proposed Solution

### Architecture

1. **Nouveau sous-package `cod3s/pycatshoo/isimu/`** contenant la logique TUI séparée du moteur :
   - `app.py` — `class ISimuApp(textual.App)`, `BINDINGS`, layout grid 2×2.
   - `panels.py` — 4 widgets (`FireablePanel`, `ComponentsPanel`, `LastDeltaPanel`, `HistoryPanel`).
   - `state.py` — conteneur `reactive` consolidant `current_time, fireable, fired_last, history, var_snapshot_initial, var_snapshot_previous, var_snapshot_current`.
   - `engine.py` — wrapper synchrone autour de `PycSystem.isimu_*`, appelé via `@work(thread=True)` côté Textual ; ajoute la capture de `currentTime()` pour l'horodatage et corrige le bug de séquence non-initialisée.
   - `grouping.py` — calcul du marqueur ★ "fires together" (équivalence `endTime`).
   - `diff.py` — capture des snapshots variables (init / previous / current) sans créer de `PycVariable` pydantic — lit `var.basename()`, `var.value()`, `var.initValue()` directement sur le backend.
   - `export.py` — sérialisation CSV (long-format inspiré de `cod3s/pycatshoo/sequence.py:1054-1114`) + JSON (`pyc_seq.model_dump()`).
   - `styles.tcss` — feuille de style Textual (grid layout + classes `.changed`, `.differs-init`, `.fires-together`).
2. **Nouveau script `cod3s/scripts/run_cod3s_isimu.py`** — entry-point argparse, équivalent CLI de `run_cod3s_study.py` mais avec deux modes de chargement : `--model file.yaml` (réutilise le format actuel) **ou** `--factory mod:fn` (alternative pour systèmes programmatiques).
3. **Helper partagé `cod3s/scripts/_common.py`** — extraction de `import_module_from_path` et d'une nouvelle fonction `build_system_from_model(model_path, study_specs_path=None) -> PycSystem` factorisant le bloc enfoui dans `run_cod3s_study.py:124-222`. `run_cod3s_study.py` est ensuite refactoré pour utiliser ce helper (refactor non-destructif : tests existants continuent à passer).
4. **`cod3s/pycatshoo/system.py:870-883` `isimu_start_cli()`** est ré-orienté vers `cod3s.pycatshoo.isimu.app.run_isimu(self)` pour permettre un appel programmatique depuis un script Python (pas seulement le binaire CLI).
5. **Nettoyage** : suppression de `cod3s/pycatshoo/interactive_session.py` et du `.pyc` orphelin.
6. **Dépendance Textual en extra optionnel** : création de `[project.optional-dependencies]` dans `pyproject.toml` avec extra `isimu = ["textual>=8.2,<9", "pytest-asyncio>=0.23"]` (le second est rangé là car nécessaire **uniquement** pour tester le TUI). `pip install -e ".[isimu]"` active la fonctionnalité.

### Flux utilisateur principal

1. `cod3s-isimu --model examples/pyc_pdmp/model.yaml`
2. `_common.build_system_from_model(...)` → `PycSystem` peuplé.
3. `engine.start(system)` → `system.startInteractive()`, capture les variables initiales, **puis** crée la séquence, **puis** `system.stepForward()` (fixe le bug §5 du Problem Statement).
4. `ISimuApp(engine).run()` ouvre l'écran : 4 panels avec état initial.
5. Utilisateur navigue dans `FireablePanel` (DataTable) — sur curseur, calcul live du groupe ★ "fires together".
6. `[Enter]` → `engine.fire(transition)` dans un worker thread (UI ne gèle pas) :
   - capture `t_before = system.currentTime()`,
   - `fired = system.isimu_step_forward()` (renvoie déjà la liste des transitions tirées — `cod3s/pycatshoo/system.py:1017-1044`),
   - capture `t_after = system.currentTime()`,
   - capture nouveau snapshot variables,
   - calcule diff variables (init vs prev vs current),
   - push event `StepCompleted(t_after, fired, var_diff)` au main thread Textual.
7. Reactive updates → re-render des 4 panels avec coloration appropriée.
8. `[b]` step backward, `[r]` reset, `[e]` export, `[p]` re-plan, `[q]` quit (appelle `engine.stop()` qui fait `system.stopInteractive()` puis `terminate_session()` dans `App.on_unmount()`).

---

## Technical Approach

### Layout TCSS (cibles)

```css
/* cod3s/pycatshoo/isimu/styles.tcss */
Screen {
    layout: grid;
    grid-size: 2 2;
    grid-columns: 1fr 2fr;
    grid-rows: 1fr 1fr;
}
#panel-fireable    { row-span: 2; column-span: 1; border: round $accent; }
#panel-components  { row-span: 1; column-span: 1; border: round $secondary; }
#panel-last-delta  { row-span: 1; column-span: 1; border: round $warning; }
#panel-history     { column-span: 2; border: round $primary; }

.fires-together { background: $accent 30%; }
.changed        { color: $error; text-style: bold; }
.differs-init   { color: $warning; }
.unchanged      { color: $foreground 60%; }
```

(Le ratio panneau gauche / droit est ajustable ; `grid-rows: auto 1fr 1fr 1fr` est aussi une variante envisagée pour donner plus de place à l'historique — à finaliser au moment du polissage UI.)

### Bindings clavier (App level)

| Key | Action | Notes |
|-----|--------|-------|
| `enter` | `fire_selected` | sur `FireablePanel` (force-fire) |
| `b` | `step_backward` | sur tout focus |
| `r` | `reset_simulation` | redemande confirmation modale |
| `e` | `open_export_modal` | demande chemin |
| `p` | `open_replan_modal` | sur transition active sélectionnée |
| `f` | `focus_filter` | met le focus dans `Input` du panel components |
| `q`, `ctrl+c` | `quit` | déclenche `engine.stop()` |
| `?` | `show_help` | overlay d'aide |

### Calcul "fires-together" (`grouping.py`)

```python
# cod3s/pycatshoo/isimu/grouping.py
def group_fires_together(
    fireable: list[PycTransition | None],
    selected_idx: int,
    epsilon: float = 0.0,
) -> set[int]:
    """Indices in `fireable` that share end_time with fireable[selected_idx]."""
    pivot = fireable[selected_idx]
    if pivot is None:
        return set()
    target = pivot.end_time
    return {
        i for i, t in enumerate(fireable)
        if t is not None and abs(t.end_time - target) <= epsilon
    }
```

**Décision** : `epsilon = 0.0` (égalité stricte) en MVP. Justification : PyCATSHOO produit des `endTime` bit-identiques pour les `delay(0)` chaînés et les `delay(d)` partageant la même valeur ; les flottants approchés viendraient d'un calcul non déterministe que l'on n'observe pas pour le moment. `epsilon` est exposé en paramètre pour rendre une évolution future triviale.

### Capture de l'horodatage des transitions tirées (`engine.py`)

Le retour de `isimu_step_forward()` (`cod3s/pycatshoo/system.py:1017-1044`) fournit la liste des `PycTransition` tirées, mais leur champ `end_time` est l'`end_time` planifié au moment de la mise en séquence — pas le temps réel de tir. Donc :

```python
# cod3s/pycatshoo/isimu/engine.py
@dataclass
class FiredEvent:
    fired_at: float                # = system.currentTime() après stepForward
    transitions: list[PycTransition]

class ISimuEngine:
    def __init__(self, system: PycSystem):
        self.system = system
        self.history: list[FiredEvent] = []     # local copy, source of truth for TUI
        self.var_initial: dict[str, Any] = {}   # captured once at start()
        self.var_previous: dict[str, Any] = {}  # last snapshot before step
        self.var_current: dict[str, Any] = {}   # latest snapshot

    def start(self) -> None:
        self.system.startInteractive()                  # raw backend, pas isimu_start
        self.system.isimu_sequence = PycSequence()      # reset BEFORE first step
        self.var_initial = self._snapshot_vars()
        self.var_previous = dict(self.var_initial)
        # initial stepForward to flush instantaneous transitions
        self._step_forward_and_capture()

    def step_forward(self) -> FiredEvent:
        return self._step_forward_and_capture()

    def _step_forward_and_capture(self) -> FiredEvent:
        self.var_previous = dict(self.var_current or self.var_initial)
        fired = self.system.isimu_step_forward()
        t_after = self.system.currentTime()
        self.var_current = self._snapshot_vars()
        evt = FiredEvent(fired_at=t_after, transitions=fired)
        self.history.append(evt)
        return evt
```

**Effet de bord positif** : ce wrapper corrige le bug §5 du Problem Statement (la séquence est ré-initialisée *avant* le premier `stepForward`).

### Snapshot variables (`diff.py`)

```python
# cod3s/pycatshoo/isimu/diff.py
def snapshot_vars(system: PycSystem) -> dict[str, Any]:
    """{ 'comp_name.var_name': value, ... } across all components."""
    return {
        f"{comp_name}.{v.basename()}": v.value()
        for comp_name, comp in system.comp.items()
        for v in comp.variables()
    }

def snapshot_initials(system: PycSystem) -> dict[str, Any]:
    return {
        f"{comp_name}.{v.basename()}": v.initValue()
        for comp_name, comp in system.comp.items()
        for v in comp.variables()
    }
```

⚠️ **Limitation MVP** documentée : les variables continues (PDMP) évoluent entre transitions. On capture leur valeur juste avant et juste après chaque `stepForward()` ; on n'échantillonne pas pendant l'évolution continue. La doc du CLI mentionnera explicitement ce comportement.

### Export (`export.py`)

```python
# cod3s/pycatshoo/isimu/export.py
def export_csv(history: list[FiredEvent], path: Path) -> None:
    rows = [
        {
            "fired_at": evt.fired_at,
            "comp_name": tr.comp_name,
            "transition": tr.name,
            "source": tr.source,
            "target": tr.target if isinstance(tr.target, str) else json.dumps(tr.target),
            "occ_law": tr.occ_law.model_dump(),
        }
        for evt in history
        for tr in evt.transitions
    ]
    pd.DataFrame(rows).to_csv(path, index=False)

def export_json(history: list[FiredEvent], path: Path) -> None:
    payload = {
        "history": [
            {"fired_at": evt.fired_at, "transitions": [tr.model_dump() for tr in evt.transitions]}
            for evt in history
        ],
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
```

Inspiré du pattern `SequenceAnalyser.to_df_long()` (`cod3s/pycatshoo/sequence.py:1054-1114`).

### Worker thread pour appels PyCATSHOO bloquants

Tout call qui touche `self.system.*` est synchrone et peut bloquer la boucle Textual. On utilise `@work(thread=True, exclusive=True)` :

```python
# cod3s/pycatshoo/isimu/app.py (extrait)
@work(thread=True, exclusive=True)
def _do_fire(self, idx: int) -> None:
    fireable = self.engine.system.isimu_fireable_transitions()
    self.engine.system.isimu_set_transition(trans_id=idx)  # plan now
    evt = self.engine.step_forward()
    self.call_from_thread(self._on_step_completed, evt)

def action_fire_selected(self) -> None:
    idx = self.query_one("#panel-fireable", DataTable).cursor_row
    self._do_fire(idx)
```

`call_from_thread` est l'API Textual pour pousser une mise à jour reactive depuis un worker thread (https://textual.textualize.io/guide/workers/#thread-workers).

### Cleanup PyCATSHOO

```python
# cod3s/pycatshoo/isimu/app.py
def on_unmount(self) -> None:
    try:
        self.engine.system.stopInteractive()
    finally:
        from cod3s import terminate_session
        terminate_session()
```

⚠️ `terminate_session()` est obligatoire (`cod3s/core.py:7-13`) sinon le singleton C++ reste sale et un re-lancement échoue.

### Implementation Phases

#### Phase 1 — Bootstrap & extraction helpers (RED → GREEN)

**Objectif** : préparer le terrain sans toucher à la TUI. Tests d'unité pour les helpers extraits, sans dépendance Textual.

**Fichiers créés / modifiés** :

| Fichier | Action |
|---------|--------|
| `cod3s/scripts/_common.py` | **NEW** — `import_module_from_path()`, `build_system_from_model(model_path, study_specs_path=None) -> PycSystem` |
| `cod3s/scripts/run_cod3s_study.py` | **REFACTOR** — délègue à `_common.import_module_from_path` et `_common.build_system_from_model` ; conserve la signature `main()` et l'argparse |
| `cod3s/pycatshoo/interactive_session.py` | **DELETE** |
| `cod3s/pycatshoo/__pycache__/isimu_cli.cpython-310.pyc` | **DELETE** |
| `cod3s/.mypy_cache/.../isimu_cli.*` | **DELETE** (cache mypy à laisser regenerer si besoin) |
| `pyproject.toml` | **EDIT** — ajouter `[project.optional-dependencies]` avec `isimu = ["textual>=8.2,<9", "pytest-asyncio>=0.23", "pytest-textual-snapshot>=0.4"]` ; ajouter entry-point `cod3s-isimu = "cod3s.scripts.run_cod3s_isimu:main"` |
| `tests/scripts/__init__.py` | **NEW** (vide) |
| `tests/scripts/test_common_loader.py` | **NEW** — tests RED → GREEN sur `import_module_from_path` (cas nominal, fichier absent, fichier sans imports) et `build_system_from_model` (modèle minimal valide, modèle invalide, study_specs_path absent toléré) |

**Validation gate** :
```bash
pytest tests/scripts/ -v                # nouveaux tests passent
pytest tests/                           # rien de cassé sur l'existant
black --check cod3s/scripts/ tests/scripts/
flake8 cod3s/scripts/ tests/scripts/
```

#### Phase 2 — Engine isimu (RED → GREEN), sans TUI

**Objectif** : l'`ISimuEngine` qui wrappe `PycSystem` est entièrement testable sans Textual.

**Fichiers créés / modifiés** :

| Fichier | Action |
|---------|--------|
| `cod3s/pycatshoo/isimu/__init__.py` | **NEW** (`from .engine import ISimuEngine, FiredEvent`) |
| `cod3s/pycatshoo/isimu/engine.py` | **NEW** — `ISimuEngine`, `FiredEvent` (voir Architecture) |
| `cod3s/pycatshoo/isimu/grouping.py` | **NEW** — `group_fires_together()` |
| `cod3s/pycatshoo/isimu/diff.py` | **NEW** — `snapshot_vars()`, `snapshot_initials()` |
| `cod3s/pycatshoo/isimu/export.py` | **NEW** — `export_csv()`, `export_json()` |
| `tests/isimu/__init__.py` | **NEW** (vide) |
| `tests/isimu/conftest.py` | **NEW** — fixture `small_system` (scope module) qui construit un `PycSystem` à 2 composants 1 transition `delay(0)` + 1 transition `exp(λ)` ; teardown `terminate_session()` |
| `tests/isimu/test_engine.py` | **NEW** — RED tests : `start()` initialise correctement, `step_forward()` retourne un `FiredEvent`, l'horodatage matche `currentTime()`, le snapshot variables est mis à jour, l'historique s'allonge ; cas limite : système sans transition fireable |
| `tests/isimu/test_grouping.py` | **NEW** — tests purs : ★ groupe correctement les transitions de même `end_time`, gère les `None`, ignore les `selected_idx` invalides |
| `tests/isimu/test_diff.py` | **NEW** — tests : `snapshot_vars` énumère bien tous les composants/variables ; `snapshot_initials` lit `initValue()` |
| `tests/isimu/test_export.py` | **NEW** — tests : CSV produit a les colonnes attendues, JSON produit est ré-importable, séquence vide ne plante pas |

**Validation gate** :
```bash
pytest tests/isimu/ -v
pytest tests/                           # toujours green
black --check cod3s/pycatshoo/isimu/ tests/isimu/
flake8 cod3s/pycatshoo/isimu/ tests/isimu/
mypy cod3s/pycatshoo/isimu/
```

#### Phase 3 — Squelette Textual (RED → GREEN avec Pilot)

**Objectif** : une `App` qui ouvre les 4 panels, affiche l'état initial, répond aux bindings basiques (`q`). Pas de logique métier dynamique.

**Fichiers créés** :

| Fichier | Action |
|---------|--------|
| `cod3s/pycatshoo/isimu/app.py` | **NEW** — `class ISimuApp(textual.App)`, `compose()` rend les 4 panels, `BINDINGS` minimal (`q`, `?`), `on_unmount()` cleanup |
| `cod3s/pycatshoo/isimu/panels.py` | **NEW** — `FireablePanel(DataTable)`, `ComponentsPanel(Tree+Input)`, `LastDeltaPanel(RichLog)`, `HistoryPanel(RichLog)` ; signatures `update(state: ISimuState)` |
| `cod3s/pycatshoo/isimu/state.py` | **NEW** — `class ISimuState`, attributs reactive consolidés |
| `cod3s/pycatshoo/isimu/styles.tcss` | **NEW** — grid 2×2, classes de couleur |
| `tests/isimu/test_app_layout.py` | **NEW** — `async def test_app_starts(...)` avec `app.run_test()` + `Pilot` : vérifie que les 4 panels existent (`query_one`), que `[q]` quit proprement, que le titre s'affiche |
| `pyproject.toml` | **EDIT** — `[tool.pytest.ini_options]` `asyncio_mode = "auto"` |

**Validation gate** :
```bash
pip install -e ".[isimu]"
pytest tests/isimu/ -v                  # incluant test_app_layout.py
textual run --dev cod3s.pycatshoo.isimu.app:ISimuApp  # smoke test manuel
```

#### Phase 4 — Wiring engine ↔ TUI (interaction réelle)

**Objectif** : sélectionner une transition + Enter → fire → panels s'actualisent. Bindings `b` (back), `r` (reset).

**Fichiers modifiés** :

| Fichier | Action |
|---------|--------|
| `cod3s/pycatshoo/isimu/app.py` | `action_fire_selected`, `action_step_backward`, `action_reset` ; worker `@work(thread=True)` ; reactive watcher pour pousser le diff au panel `LastDeltaPanel` ; ajouts au panel `HistoryPanel` |
| `cod3s/pycatshoo/isimu/panels.py` | `FireablePanel.refresh_from_state()`, `ComponentsPanel.refresh_from_state()`, etc. |
| `cod3s/pycatshoo/isimu/engine.py` | Ajouter `step_backward()` (wrap `system.isimu_step_backward`) et `reset()` (`stopInteractive` + nouveau `start()`) |
| `tests/isimu/test_app_interaction.py` | **NEW** — `Pilot` scenarios : (1) press `down` `enter` sur fireable → la transition la plus précoce est tirée ; (2) press `b` → l'historique recule ; (3) press `r` → retour à t=0 |

**Validation gate** :
```bash
pytest tests/isimu/test_app_interaction.py -v
pytest tests/                            # rien cassé
```

#### Phase 5 — Highlights, filtre, coloration

**Objectif** : implémenter exactement le cahier des charges visuel du brainstorm.

**Fichiers modifiés** :

| Fichier | Action |
|---------|--------|
| `cod3s/pycatshoo/isimu/panels.py` | `FireablePanel.on_data_table_row_highlighted` → calcule le set `fires_together` et applique la classe CSS aux lignes correspondantes ; `ComponentsPanel.on_input_changed` → reconstruit l'arbre avec filtre substring case-insensitive ; chaque cellule de variable rend un `rich.text.Text` avec style conditionnel `unchanged`/`differs-init`/`changed` |
| `cod3s/pycatshoo/isimu/styles.tcss` | Polissage des classes |
| `tests/isimu/test_highlights.py` | **NEW** — `Pilot` scenarios : sélection sur transition X met en évidence Y et Z (même `end_time`) ; après une transition, la variable changée est en gras-rouge dans le tree |

**Validation gate** :
```bash
pytest tests/isimu/test_highlights.py -v
```

#### Phase 6 — Actions avancées (export, re-plan)

**Objectif** : completer le MVP.

**Fichiers modifiés** :

| Fichier | Action |
|---------|--------|
| `cod3s/pycatshoo/isimu/app.py` | `action_open_export_modal`, `action_open_replan_modal` ; `class ExportModal(ModalScreen)`, `class ReplanModal(ModalScreen)` |
| `cod3s/pycatshoo/isimu/engine.py` | `replan(trans_name: str, date: float)` → wrap `system.isimu_set_transition` |
| `tests/isimu/test_app_modals.py` | **NEW** — `Pilot` : ouvre la modale export, saisit un chemin, valide → fichier écrit ; ouvre la modale re-plan, saisit `t=5.0` sur transition X → la transition X est planifiée à 5.0 |

**Validation gate** :
```bash
pytest tests/isimu/ -v
```

#### Phase 7 — Entry-point, doc, finalisation

**Objectif** : livrer un binaire utilisable + doc.

**Fichiers créés / modifiés** :

| Fichier | Action |
|---------|--------|
| `cod3s/scripts/run_cod3s_isimu.py` | **NEW** — argparse `--model`, `--factory`, `--study-specs`, `--log-level` ; `main()` appelée par l'entry-point ; `--factory mod:fn` parse `module.path:function_name` puis `getattr(importlib.import_module(...), fn_name)()` |
| `cod3s/pycatshoo/system.py:870-883` | **EDIT** — réorienter `isimu_start_cli()` vers `from cod3s.pycatshoo.isimu.app import run_isimu; run_isimu(self)`. Garder le `try/except KeyboardInterrupt` qui appelle `isimu_stop` |
| `docs/user-guide/` | **NEW directory** |
| `docs/user-guide/interactive-simulation.md` | **NEW** — guide d'usage `cod3s-isimu` avec captures d'écran ASCII, exemples de raccourcis, mention de la limitation variables continues |
| `mkdocs.yml` | **EDIT** — ajouter la page sous `User Guide` (la section référencée mais absente est ainsi régularisée) |
| `tests/scripts/test_run_cod3s_isimu.py` | **NEW** — test argparse par subprocess (mode `--help`), test `--factory invalidmod:fn` lève une erreur claire |

**Validation gate** :
```bash
pip install -e ".[isimu]"
cod3s-isimu --help
pytest tests/                            # full green
mkdocs build --strict                    # pas de broken link
black --check . && isort --check . && flake8 .
mypy cod3s/
```

---

## Alternative Approaches Considered

### A. Cmd-style REPL (cmd.Cmd + Rich)

Réutiliser le pattern de l'orphelin `isimu_cli.pyc` : un prompt interactif `(cod3s-isimu) > ` avec commandes `fireable`, `step`, `vars --filter pump`. Sortie colorée Rich.

**Pourquoi rejeté** :
- Pas de panels simultanés. Chaque info est ré-affichée à la demande, ce qui invalide les highlights croisés (★ "fires together") et la coloration delta-aware.
- Le filtre live sur les variables devient un argument à retaper à chaque commande.
- L'expérience promise au brainstorm (4 panels, navigation curseur, mise en évidence dynamique) n'est pas atteignable.

### B. Web UI (Streamlit / Dash)

Application navigateur servie en local.

**Pourquoi rejeté** :
- Lourd en dépendances (flask, plotly), requiert un port libre, mauvaise UX en SSH/headless (cas standard pour les utilisateurs serveur).
- Ne respecte pas le cahier des charges "CLI".
- Sort du périmètre identifié au brainstorm.

### C. Greffon dans `run-cod3s-study` (pas de nouveau binaire)

Ajouter un drapeau `--interactive` au binaire existant.

**Pourquoi rejeté** :
- Mélange deux modes très différents (Monte-Carlo batch vs interactif step-by-step) dans le même point d'entrée.
- Couple le scope du nouveau code à celui de `run_cod3s_study.py` (déjà 460 lignes).
- Empêche un `pyproject.toml` extra propre — Textual deviendrait dep runtime obligatoire.

---

## Acceptance Criteria

### Functional Requirements

- [ ] Le binaire `cod3s-isimu --model <path>` ouvre un TUI Textual qui charge le système et affiche les 4 panels avec valeurs initiales.
- [ ] Le binaire `cod3s-isimu --factory <module>:<function>` charge un système retourné par cette fonction.
- [ ] Le panel **Fireable transitions** liste exactement `system.isimu_fireable_transitions()` filtré des `None`, classé par `end_time` croissant.
- [ ] Quand le curseur se pose sur une transition, **toutes les autres transitions de la liste partageant exactement le même `end_time` sont marquées ★ et stylées `.fires-together`**.
- [ ] `[Enter]` sur une transition appelle `isimu_set_transition(idx)` puis `isimu_step_forward()` ; l'instant de tir est `system.currentTime()` *après* l'appel.
- [ ] Le panel **Components/Variables** rend chaque variable comme `comp.var = current` (et `init → current` si différent).
- [ ] Coloration : variables changées au dernier pas → **gras + rouge** ; variables ≠ initial mais pas changées au dernier pas → orange ; sinon neutre dim.
- [ ] Le panel **Last-Δ** liste exactement les variables dont la valeur a changé au dernier `stepForward` (basé sur diff `var_previous` vs `var_current`).
- [ ] Le panel **History** affiche la liste anti-chronologique groupée par `fired_at` (un seul header par instant ; transitions co-tirées concaténées).
- [ ] Le filtre du panel components accepte une chaîne, filtre case-insensitive sur `comp.var`, met à jour l'arbre en moins de 100 ms pour ≤ 1000 variables.
- [ ] `[b]` annule la dernière transition (`isimu_step_backward(reset_planning=True)`), met à jour les 4 panels.
- [ ] `[r]` (avec confirmation modale) reset à t=0.
- [ ] `[e]` ouvre une modale, l'utilisateur saisit un chemin → fichiers `<path>.csv` et `<path>.json` produits avec l'historique horodaté.
- [ ] `[p]` sur une transition active permet de saisir un instant et appelle `setTransPlanning`.
- [ ] `[q]` ferme proprement (`isimu_stop` + `terminate_session`) sans laisser de processus PyCATSHOO en zombie.

### Non-Functional Requirements

- [ ] Pas d'I/O bloquant dans la boucle Textual : tout appel `system.*` passe par `@work(thread=True)`.
- [ ] L'app reste réactive (cursor déplaçable) pendant un `stepForward` lent.
- [ ] Tests TUI exécutés en CI sans X11 / sans terminal (`Pilot` headless).
- [ ] Aucun `print()` dans le code TUI (tous les logs passent par `TextualHandler` ou `self.log`).

### Quality Gates

- [ ] `pytest tests/` full green sur Python 3.10.x.
- [ ] `pytest tests/isimu/` couvre engine, grouping, diff, export, app layout, app interaction, highlights, modals.
- [ ] `black --check`, `isort --check`, `flake8` : zéro warning sur `cod3s/scripts/_common.py`, `cod3s/scripts/run_cod3s_isimu.py`, `cod3s/pycatshoo/isimu/`.
- [ ] `mypy cod3s/pycatshoo/isimu/` zéro erreur.
- [ ] `mkdocs build --strict` réussit (le dossier `docs/user-guide/` est présent et la nav cohérente).
- [ ] Aucune trace de `interactive_session.py` ou `isimu_cli.pyc` dans le repo.

---

## Success Metrics

### Avant
- Pas-à-pas interactif inaccessible côté CLI ; les utilisateurs reproduisent à la main `system.isimu_start(); system.isimu_show_fireable_transitions(); system.isimu_set_transition(...)` dans un REPL Python — friction élevée, pas de visualisation, pas d'historique horodaté.

### Après
- Une commande : `cod3s-isimu --model x.yaml` ouvre l'écran complet ; debug d'un scénario `external_rep_indep` (cycle pulse) passe de ~30 minutes à ~5 minutes.
- L'historique est horodaté et exportable → reproductibilité d'un scénario observé.

### Qualitatif
- Les bugs de chaînage de transitions `delay(0)` (ex. `objfm` external) deviennent **observables**. Un utilisateur peut filmer le pas-à-pas et le partager comme reproducer.
- Le code mort (`interactive_session.py`, `.pyc` orphelin) est nettoyé ; la documentation `docs/user-guide/` est créée et le `mkdocs.yml` est cohérent.

---

## Dependencies & Prerequisites

### Hard prerequisites (déjà satisfaits)
- API `PycSystem.isimu_*` complète (`cod3s/pycatshoo/system.py:846-1107`).
- `PycTransition` avec `model_dump()` et accès au backend `_bkd` (`cod3s/pycatshoo/automaton.py:375-525`).
- `PycSequence` minimal pour stocker les transitions (`cod3s/pycatshoo/sequence.py:17-27`).
- `terminate_session()` (`cod3s/core.py:7-13`).

### Soft dependencies
- L'extraction de `import_module_from_path` peut être faite indépendamment et profite à `run_cod3s_study.py` même sans `cod3s-isimu`.

### External
- **Textual** ≥ 8.2, < 9 (extra `[isimu]`) — pure Python, compatible 3.10.
- **pytest-asyncio** ≥ 0.23 (extra `[isimu]`) — requis pour `App.run_test()`.
- **pytest-textual-snapshot** ≥ 0.4 (extra `[isimu]`, optionnel) — pour tests visuels SVG (peut être différé).

---

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PyCATSHOO singleton C++ crashe quand on relance l'`App` deux fois dans le même processus de test | Moyen | Élevé | Fixture `scope="module"` partout dans `tests/isimu/`, `terminate_session()` dans `App.on_unmount()` ET dans le teardown des tests. |
| Textual API évolue de 8.x → 9.x pendant l'implémentation | Faible | Moyen | Pin `textual>=8.2,<9` dans l'extra ; lock via `uv.lock`. |
| Le retour `isimu_step_forward()` masque des transitions tirées par chaînage interne PyCATSHOO non listées | Faible | Moyen | Tests d'engine sur scénarios `delay(0)` chaînés (modèles `external_rep_indep`) qui servent déjà de cas test PyCATSHOO. |
| `comp.variables()` (backend) renvoie aussi des "variables internes" non destinées à l'utilisateur | Moyen | Faible | Filtrer en première implémentation sur `var.basename().startswith('_') is False` ; documenter et ajuster avec retour utilisateur. |
| Le filtre live devient lent sur 5000+ variables | Faible | Faible | Debounce via `@work(exclusive=True)` ; pagination v2. |
| Cleanup de `interactive_session.py` casse un import externe non détecté | Faible | Moyen | `grep -rn "interactive_session" .` avant suppression ; le fichier est cassé en l'état donc tout import était déjà broken. |
| Le bug `if not state_index` (`cod3s/pycatshoo/system.py:1103`) passe `0` quand l'utilisateur précise `0` | Hors scope | Faible | Documenter dans Future Considerations ; le MVP du CLI peut éviter de passer `0` explicitement. |

---

## Resource Requirements

### People
- 1 développeur Python (familier Textual ou prêt à apprendre).

### Time estimate (effort)
- Phase 1 (bootstrap + extraction) : 0.5 jour.
- Phase 2 (engine + utilitaires) : 1 jour.
- Phase 3 (squelette TUI) : 1 jour.
- Phase 4 (wiring engine ↔ TUI) : 1 jour.
- Phase 5 (highlights/filtre/coloration) : 1 jour.
- Phase 6 (modals export/re-plan) : 0.5 jour.
- Phase 7 (entry-point + doc + cleanup) : 0.5 jour.
- **Total** : ~5.5 jours-développeur. Ajouter 1-2 jours pour itérations de polissage UX.

### Compute
- Tests headless (`Pilot`) tournent en quelques secondes ; pas d'infra spéciale.

---

## Future Considerations

1. **Variables continues PDMP** : sampling pendant l'évolution continue (entre transitions) pour visualiser les trajectoires. Nécessite un timer Textual + lecture continue de `var.value()`. Hors scope MVP.
2. **Plot intégré** : un panel "graphes" (sparkline Rich ou plotext) montrant l'évolution d'une variable sélectionnée. v2.
3. **Breakpoints** : conditions `var > seuil` qui interrompent automatiquement le pas-à-pas. v2.
4. **Save / restore session** : sérialiser un état de simulation pour reprendre. PyCATSHOO ne le permet pas trivialement (état C++ opaque) ; demande une analyse séparée.
5. **Comparaison de séquences** : charger deux exports JSON et afficher leurs différences. v2.
6. **Mode batch dirigé** : scripter une séquence de transitions à appliquer (`--script trans1,trans2,...`) pour automatiser la reproduction de scénarios.
7. **Bug `if not state_index`** (`cod3s/pycatshoo/system.py:1103`) : à corriger en `if state_index is None` (changement minimal mais potentiellement breaking — séparer dans son propre PR).
8. **Hot-reload du modèle** : recharger le YAML sans quitter le TUI. v2.
9. **Migration `PycSequence` → `Sequence`** comme suggéré par le commentaire `cod3s/pycatshoo/sequence.py:13-16`. Hors scope.

---

## Documentation Plan

- [ ] `docs/user-guide/interactive-simulation.md` — guide utilisateur complet (lancer, raccourcis, exemples).
- [ ] Section "Examples" mise à jour : exemple d'usage `cod3s-isimu` sur `examples/pyc_system_pdmp_001/system.py`.
- [ ] `mkdocs.yml` régularisé : section `User Guide` pointe vers des fichiers existants.
- [ ] Docstrings Google-style sur `ISimuEngine`, `ISimuApp`, et helpers extraits — `mkdocstrings` les rend automatiquement disponibles via la nav `API Reference`.
- [ ] `README.md` ou `docs/index.md` : ajouter une mention "Interactive simulator" dans la liste des features.
- [ ] CHANGELOG (si présent) : entrée `feat: cod3s-isimu interactive TUI simulator`.

---

## References & Research

### Internal references
- API moteur isimu : `cod3s/pycatshoo/system.py:846-1107`.
- Bug séquence non-initialisée : `cod3s/pycatshoo/system.py:846-857`.
- `PycTransition` model : `cod3s/pycatshoo/automaton.py:375-525`.
- `PycVariable.from_bkd` : `cod3s/pycatshoo/component.py:19-37`.
- `comp.variables()` usage existant : `cod3s/pycatshoo/component.py:178, 313, 681`.
- `PycSequence` : `cod3s/pycatshoo/sequence.py:17-27`.
- Pattern long-DataFrame pour export : `cod3s/pycatshoo/sequence.py:1054-1114`.
- Argparse + YAML loader template : `cod3s/scripts/run_cod3s_study.py:21-49, 124-222`.
- Hook isimu_start_cli cassé : `cod3s/pycatshoo/system.py:870-883`.
- Code mort à supprimer : `cod3s/pycatshoo/interactive_session.py`.
- Pattern fixture pyc tests : `tests/pyc_obj/test_pyc_iter_simu_001.py:1-74`.
- Pattern subprocess test E2E : `tests/usecases/indus_4_0_Electrolyseur/utils.py:32-44`.
- Plan de référence (style/structure) : `docs/plans/2026-04-28-feat-objfm-external-rep-indep-pulse-model-plan.md`.
- Brainstorm associé : `docs/brainstorms/2026-04-28-cod3s-isimu-brainstorm.md`.

### External references
- Textual layout grid : https://textual.textualize.io/guide/layout/#grid-layout
- Textual reactive attributes : https://textual.textualize.io/guide/reactivity/
- Textual workers (thread mode pour PyCATSHOO sync) : https://textual.textualize.io/guide/workers/#thread-workers
- Textual testing avec Pilot : https://textual.textualize.io/guide/testing/
- Textual logging (`TextualHandler`) : https://textual.textualize.io/api/logging/
- Textual `DataTable` : https://textual.textualize.io/widgets/data_table/
- Textual `Tree` : https://textual.textualize.io/widgets/tree/
- Textual `Input.Changed` : https://textual.textualize.io/widgets/input/

### Related work
- Plan ObjFM external_rep_indep (gabarit suivi) : `docs/plans/2026-04-28-feat-objfm-external-rep-indep-pulse-model-plan.md`.
- Mémoire projet `project_python_version` (Python 3.10.18 only).
- Mémoire projet `project_cod3s_isimu` (résumé de cette initiative).

---

## Implementation Checklist (in order)

### Phase 1 — Bootstrap & extraction helpers
- [x] 1.1 — Créer `cod3s/scripts/_common.py` avec `import_module_from_path` et `build_system_from_model`.
- [x] 1.2 — Refactorer `cod3s/scripts/run_cod3s_study.py` pour utiliser `_common`.
- [x] 1.3 — Supprimer `cod3s/pycatshoo/interactive_session.py` et le `.pyc` orphelin.
- [x] 1.4 — Ajouter `[project.optional-dependencies]` dans `pyproject.toml`. (Entry-point `cod3s-isimu` reporté en Phase 7 pour ne pas déclarer un script inexistant.)
- [x] 1.5 — Tests `tests/scripts/test_common_loader.py` (11 tests).
- [x] 1.6 — GREEN : `pytest tests/scripts/` passe (11/11).
- [x] 1.7 — Validation gate Phase 1 : `pytest tests/` 207 passed, 26 skipped ; `black --check` clean ; `flake8` clean sur les fichiers nouveaux/modifiés (warnings pré-existants ignorés).

### Phase 2 — Engine isimu
- [ ] 2.1 — Créer arborescence `cod3s/pycatshoo/isimu/` (`__init__`, `engine`, `grouping`, `diff`, `export`).
- [ ] 2.2 — Tests RED `tests/isimu/test_engine.py`, `test_grouping.py`, `test_diff.py`, `test_export.py`.
- [ ] 2.3 — Implémenter `ISimuEngine.start/step_forward/step_backward/reset` ; corrige le bug séquence non-initialisée.
- [ ] 2.4 — Implémenter `group_fires_together`, `snapshot_vars`, `snapshot_initials`, `export_csv`, `export_json`.
- [ ] 2.5 — GREEN : `pytest tests/isimu/` passe.
- [ ] 2.6 — Validation gate Phase 2 : full pytest + lint + mypy.

### Phase 3 — Squelette Textual
- [ ] 3.1 — Créer `app.py`, `panels.py`, `state.py`, `styles.tcss`.
- [ ] 3.2 — `compose()` rend les 4 panels statiques avec données initiales.
- [ ] 3.3 — `BINDINGS` minimal (`q`, `?`).
- [ ] 3.4 — `on_unmount()` cleanup PyCATSHOO.
- [ ] 3.5 — Test `tests/isimu/test_app_layout.py` avec `App.run_test()`.
- [ ] 3.6 — Smoke test manuel `textual run --dev`.
- [ ] 3.7 — Validation gate Phase 3.

### Phase 4 — Wiring engine ↔ TUI
- [ ] 4.1 — `action_fire_selected` + worker thread.
- [ ] 4.2 — `action_step_backward`, `action_reset` (modale confirm).
- [ ] 4.3 — Reactive watchers déclenchent `panel.refresh_from_state()`.
- [ ] 4.4 — Tests `tests/isimu/test_app_interaction.py`.
- [ ] 4.5 — Validation gate Phase 4.

### Phase 5 — Highlights, filtre, coloration
- [ ] 5.1 — Highlight ★ "fires together" sur navigation curseur fireable.
- [ ] 5.2 — Filtre live `Input.Changed` sur `ComponentsPanel`.
- [ ] 5.3 — Coloration conditionnelle des cellules variables (3 classes).
- [ ] 5.4 — Tests `tests/isimu/test_highlights.py`.
- [ ] 5.5 — Validation gate Phase 5.

### Phase 6 — Actions avancées
- [ ] 6.1 — `ExportModal`, `action_open_export_modal`, écriture CSV+JSON.
- [ ] 6.2 — `ReplanModal`, `action_open_replan_modal`, `engine.replan(...)`.
- [ ] 6.3 — Tests `tests/isimu/test_app_modals.py`.
- [ ] 6.4 — Validation gate Phase 6.

### Phase 7 — Entry-point, doc, finalisation
- [ ] 7.1 — Créer `cod3s/scripts/run_cod3s_isimu.py` (argparse + main).
- [ ] 7.2 — Ré-orienter `PycSystem.isimu_start_cli()` vers `cod3s.pycatshoo.isimu.app.run_isimu`.
- [ ] 7.3 — Créer `docs/user-guide/interactive-simulation.md` + ajuster `mkdocs.yml`.
- [ ] 7.4 — `pip install -e ".[isimu]"` + `cod3s-isimu --help` smoke test.
- [ ] 7.5 — `mkdocs build --strict` zéro warning.
- [ ] 7.6 — Test `tests/scripts/test_run_cod3s_isimu.py` (subprocess `--help`).
- [ ] 7.7 — Validation gate finale : full pytest + lint + mypy + mkdocs.
- [ ] 7.8 — Bump version + commit propre + (optionnel) PR.
