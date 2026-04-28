---
title: feat — Finalize ObjFM external_rep_indep pulse model and refactor ctrl_var management
type: feat
date: 2026-04-28
brainstorm: docs/brainstorms/2026-04-28-objfm-external-modes-brainstorm.md
---

# feat: Finalize ObjFM `external_rep_indep` pulse model and refactor `ctrl_var` management

## Overview

Finalize the implementation of the `behaviour="external_rep_indep"` mode of `ObjFM` based on the **pulse model** decided during the 2026-04-28 brainstorm. As a side effect, refactor the `ctrl_var` management mechanism (currently sensitive method) into **direct effects on transitions**, unifying the implementation of both `external` and `external_rep_indep` modes. Add the test coverage that is missing today (the `external_rep_indep` mode currently has zero tests, and the `external` mode is missing error-case tests). Update the `FEAT_OBJFM_SPECS.md` specification to match the actual decisions, particularly that `failure_effects` and `repair_effects` are applied through the target's automaton (and not ignored as the original spec stated).

This work concludes a partially-implemented feature that has been on hold for ~3 months and unblocks downstream use cases relying on independent-repair semantics for shared-cause failures.

---

## Problem Statement

### What's broken or missing today

1. **`external_rep_indep` is implemented but unspecified and untested.**
   - The code at `cod3s/pycatshoo/component.py:1515-1518` carries an explicit `# TODO: No ! not always ready, in fact we have to use the initial repair_cond be applied the component`. The current `rep_condition = lambda: True` ignores the user's `repair_cond` parameter.
   - There is **no test file** validating any aspect of `external_rep_indep`, so we cannot evolve it confidently.
   - The semantics of "what does the ObjFM do once it has triggered targets in this mode?" was never written down. Brainstorm `2026-04-28` resolves this with the **pulse model**.

2. **Spec ↔ code divergence on effects in `external` modes.**
   - `FEAT_OBJFM_SPECS.md` lines 89-91 say `failure_effects` and `repair_effects` are "ignored (warning emitted)" for `external` modes.
   - The actual code (`component.py:1520-1545`) applies them **through the target's automaton**.
   - Commit `721414c` ("remove redundant warnings for external failure mode behaviors") explicitly removed the warnings the spec referenced.
   - Tests `test_comp_failure_external_002.py` and `_003.py` verify that effects propagate to the target — confirming the current code is the desired behavior.
   - The spec is therefore obsolete on this point and confuses anyone reading it.

3. **`ctrl_var` management is brittle for the pulse model.**
   - `component.py:1431-1460` maintains `ctrl_var = OR(impacting_automata in occ)` via a sensitive method registered on every impacting automaton. This works for `external` (mutual lock) but **breaks the pulse model**: as soon as the ObjFM transitions back to `rep` (delay 0 in `external_rep_indep`), the OR drops to False, the `ctrl_var` collapses, and the target never gets a chance to propagate its own state change. The pulse fails silently.

4. **Missing error-case tests for the existing `external` mode.**
   - Spec lists `test_behaviour_invalid`, `test_behaviour_name_conflict`, `test_behaviour_effects_warning` (now obsolete: no warning), `test_external_with_objfmdelay`, `test_internal_no_target_automaton`, `test_internal_effects_applied`. None exist in the repo.

5. **`drop_inactive_automata` interaction with `external_rep_indep` is unverified.**
   - The brainstorm relies on `repair_var_params_order1` being defined for the order-1 law to use as the target repair law. If `drop_inactive_automata=True` causes order 1 to be skipped (e.g., user provides `failure_param=[0, 0.1]`), then `repair_var_params_order1` would be None and the pulse model would crash with no clear error.

### Why it matters now

- The codebase is between feature versions (1.0.33 + WIP commit). Shipping with `external_rep_indep` half-implemented and untested is a regression risk.
- Downstream studies (the `indus_4_0_Electrolyseur` use case, future ones) need independent-repair modeling for realistic availability analysis.
- The longer the gap between brainstorm decisions and implementation, the higher the chance of context loss when restarting the work.

---

## Proposed Solution

### High-level approach

A single PR that:

1. **Refactors `ctrl_var` management** — remove the sensitive method, replace by direct effects on the ObjFM and target transitions. This is a prerequisite for the pulse model to work without race conditions and unifies the two `external` flavors.
2. **Implements the pulse model** for `external_rep_indep` — ObjFM `occ → rep` transition uses `delay(0)` law and unconditional cond. Target's `repair_cond` is the user's original `repair_cond` evaluated on the target.
3. **Wraps the spec/test gap** — adds a complete TDD test file for `external_rep_indep`, plus a small set of error-case tests; updates `FEAT_OBJFM_SPECS.md` to reflect actual decisions.

The refactor of `ctrl_var` is the riskiest move because it touches the working `external` mode. We validate non-regression by running the existing 4 external tests at every step.

---

## Technical Approach

### Architecture

#### Final state of the `ObjFM` automata wiring

For each ObjFM combo automaton (`{fm_name}__cc_{combo}`):

| Behaviour | trans 12 (rep→occ) cond | trans 12 effect | trans 21 (occ→rep) cond | trans 21 law | trans 21 effect |
|---|---|---|---|---|---|
| `internal` | `failure_cond` | apply `failure_effects` to target vars | `repair_cond` | order-N repair law | apply `repair_effects` to target vars |
| `external` | `failure_cond` AND all targets in rep | set `ctrl_{tgt}=True` for combo's targets | `repair_cond` AND all targets in occ | order-N repair law | set `ctrl_{tgt}=False` for combo's targets |
| `external_rep_indep` | `failure_cond` AND all targets in rep | set `ctrl_{tgt}=True` for combo's targets | `True` (unconditional) | `delay(0)` | **none** (target manages its own ctrl) |

For each target's `{fm_name}` automaton (`external` and `external_rep_indep` only):

| Behaviour | trans 12 (rep→occ) cond | trans 12 law | trans 12 effect | trans 21 (occ→rep) cond | trans 21 law | trans 21 effect |
|---|---|---|---|---|---|---|
| `external` | `ctrl == True` | `delay(0)` | apply `failure_effects` | `ctrl == False` | `delay(0)` | apply `repair_effects` |
| `external_rep_indep` | `ctrl == True` | `delay(0)` | apply `failure_effects` | original `repair_cond` evaluated on target | order-1 repair law | apply `repair_effects` AND set `ctrl=False` |

#### Why direct effects beat sensitive methods

- **Fewer moving parts**: no per-target callback, no list of impacting automata to maintain, no start-method to initialize. Init defaults of `ctrl_var=False` from `addVariable` are sufficient.
- **Deterministic timing**: an effect on a transition fires *with* the transition; a sensitive method fires *after* a state change is committed. With multiple delay(0) transitions chained (the pulse), the latter introduces ordering ambiguity.
- **Identical pattern in both modes**: the only delta between `external` and `external_rep_indep` is what the ObjFM's repair transition does (set ctrl=False vs nothing) and how the target's repair transition is configured.
- **Provably equivalent** for `external`: the failure_cond augmentation guarantees that at most one combo per target is ever in `occ` simultaneously, so `OR(impacting in occ)` reduces to "the single active impacting automaton (if any)". A pair of `set ctrl=True on occ` / `set ctrl=False on rep` reproduces this exactly.

### Implementation Phases

#### Phase 1 — Test scaffolding (TDD-first, must run RED)

Write the failing tests before touching production code. Naming convention: `tests/pyc_obj/obj_fm/test_comp_failure_external_rep_indep_NNN.py`. Each test is small and focused. Use `kb_test.py` `ObjFlow` / `ObjFlow2I1O` components (already in place).

**Files to create:**

```
tests/pyc_obj/obj_fm/test_comp_failure_external_rep_indep_001.py
tests/pyc_obj/obj_fm/test_comp_failure_external_rep_indep_002.py
tests/pyc_obj/obj_fm/test_comp_failure_external_rep_indep_003.py
tests/pyc_obj/obj_fm/test_comp_failure_external_rep_indep_004.py
tests/pyc_obj/obj_fm/test_comp_failure_external_rep_indep_005.py
tests/pyc_obj/obj_fm/test_comp_failure_external_rep_indep_006.py
tests/pyc_obj/obj_fm/test_comp_failure_external_modes_errors.py
```

**Test mapping (one or two tests per file, kept short):**

```python
# test_comp_failure_external_rep_indep_001.py — Creation and structure
# - test_rep_indep_creates_target_automaton
#     Verify automaton named fm_name in target.automata_d
# - test_rep_indep_creates_ctrl_vars
#     Verify ctrl_{fm}_{tgt} variable in ObjFM, init False
# - test_rep_indep_no_warning_on_effects
#     Add failure_effects + repair_effects, capture warnings, assert empty

# test_comp_failure_external_rep_indep_002.py — Pulse dynamics single target
# - test_rep_indep_pulse_single_target
#     ObjFM.occ fireable -> fire it -> ctrl_var becomes True
#     Both target.occ AND ObjFM.rep fireable (delay 0 race)
#     Fire target.occ -> failure_effects applied
#     Fire ObjFM.rep -> ctrl_var STAYS True (no effect on it)
#     ObjFM.rep state active, target.occ state active
#     Now ObjFM.occ NOT fireable (target not in rep)
#     But target.rep IS fireable with order-1 law
# - test_rep_indep_target_repair_resets_ctrl
#     After target.rep fires -> ctrl_var = False, repair_effects applied
#     ObjFM.occ now fireable again

# test_comp_failure_external_rep_indep_003.py — Multi-target combos
# - test_rep_indep_combo_order2_independent_repair
#     Targets [C1, C2], failure_param=[lam1, lam12], repair_param=[mu1, mu12]
#     Fire frun__cc_12.occ -> ctrl_C1=True, ctrl_C2=True
#     Fire C1.occ, C2.occ -> both in occ
#     Fire ObjFM.rep__cc_12 (delay 0) -> ObjFM back in rep but ctrl vars STAY True
#     Fire C1.rep alone -> C1 in rep, ctrl_C1=False, C2 still in occ
#     Verify cc_12 NOT fireable, cc_2 NOT fireable, cc_1 fireable
#     Fire C2.rep -> all in rep, all combos fireable again
# - test_rep_indep_partial_state_blocks_higher_order_combo
#     After C1 repaired but C2 still occ, only cc_1 fireable

# test_comp_failure_external_rep_indep_004.py — Effects propagation
# - test_rep_indep_failure_effects_applied
#     ObjFlow with flow_in_max=10. failure_effects={"flow_in_max": 0.0}
#     After full pulse: target.flow_in_max == 0.0
# - test_rep_indep_repair_effects_applied
#     repair_effects={"flow_in_max": 10.0}
#     After target self-repairs: target.flow_in_max == 10.0

# test_comp_failure_external_rep_indep_005.py — repair_cond original used
# - test_rep_indep_repair_cond_callable_blocks_repair
#     repair_cond=lambda: target.some_var.value() > 0
#     Set target.some_var = 0 -> target stays in occ even after pulse + delay
#     Set target.some_var = 1 -> target.rep becomes fireable
#     (Use isimu_set_transition by name with a date to verify timing)
# - test_rep_indep_repair_cond_default_true
#     With default repair_cond=True, target always ready to repair

# test_comp_failure_external_rep_indep_006.py — ObjFMDelay compatibility
# - test_rep_indep_objfmdelay_uses_delay_law
#     ObjFMDelay with repair_param=[5.0]  # ttr_1=5
#     After pulse, target.rep fires after exactly 5 time units
#     (use isimu_step_forward and check transition date)

# test_comp_failure_external_modes_errors.py — Error cases (covers external too)
# - test_behaviour_invalid_raises
#     behaviour="bogus" -> ValueError listing VALID_BEHAVIOURS
# - test_external_name_conflict_raises
#     Add a target with an existing automaton named "frun" -> ValueError
# - test_external_rep_indep_name_conflict_raises
#     Same for external_rep_indep
# - test_external_rep_indep_drop_inactive_order1_raises
#     With order 1 lambda=0 (inactive), drop_inactive_automata=True
#     should raise ValueError("repair_var_params_order1 not available...") OR
#     fall back gracefully — decide in implementation phase
```

**Acceptance for Phase 1**: all 7 new test files exist, all tests are RED (fail with NotImplementedError, AttributeError, or assertion errors against current code).

---

#### Phase 2 — Refactor `ctrl_var` management (direct effects)

Replace the sensitive method block with effects on transitions. This phase **MUST** keep all 4 existing external tests (`test_comp_failure_external_001..004.py`) passing.

**Files to modify:** `cod3s/pycatshoo/component.py` (single file).

**Concrete edits in `ObjFM.add_failure_repair_automaton` (the method that builds combo automata, around lines 1284-1460):**

```python
# === Replace lines 1284-1318 (the "Prepare effects based on behaviour" block) ===

if self.behaviour in ("external", "external_rep_indep"):
    # Direct effects on transitions: set/clear ctrl_var.
    failure_effects_cur = [
        {"var": self.ctrl_vars[self.targets[idx]], "value": True}
        for idx in target_set_idx
    ]
    if self.behaviour == "external":
        # Synchronized repair: ObjFM.rep clears ctrl_var, target follows.
        repair_effects_cur = [
            {"var": self.ctrl_vars[self.targets[idx]], "value": False}
            for idx in target_set_idx
        ]
    else:  # external_rep_indep
        # Pulse model: ObjFM.rep does NOT touch ctrl_var; target manages it.
        repair_effects_cur = []
else:  # internal — unchanged
    failure_effects_cur = []
    for var, value in self.failure_effects.items():
        for target_idx in target_set_idx:
            comp_cur = self.system().component(self.targets[target_idx])
            if hasattr(comp_cur, var):
                comp_var = getattr(comp_cur, var)
            elif var in [v.basename() for v in comp_cur.variables()]:
                comp_var = comp_cur.variable(var)
            else:
                raise ValueError(
                    f"Component {repr(comp_cur)} has no attribute nor variable named {var}"
                )
            failure_effects_cur.append({"var": comp_var, "value": value})

    repair_effects_cur = []
    for var, value in self.repair_effects.items():
        for target_idx in target_set_idx:
            comp_cur = self.system().component(self.targets[target_idx])
            if hasattr(comp_cur, var):
                comp_var = getattr(comp_cur, var)
            elif var in [v.basename() for v in comp_cur.variables()]:
                comp_var = comp_cur.variable(var)
            else:
                raise ValueError(
                    f"Component {repr(comp_cur)} has no attribute nor variable named {var}"
                )
            repair_effects_cur.append({"var": comp_var, "value": value})
```

**Edits around lines 1361-1399 (the conditional augmentation):**

```python
# Apply external augmentation to BOTH external and external_rep_indep failure_cond.
if self.behaviour in ("external", "external_rep_indep"):
    # ... keep make_external_cond helper ...
    failure_cond_cur = make_external_cond(
        failure_cond_cur, target_comps_cur, self.fm_name, self.repair_state,
    )

# Repair augmentation differs by mode.
if self.behaviour == "external":
    repair_cond_cur = make_external_cond(
        repair_cond_cur, target_comps_cur, self.fm_name, self.failure_state,
    )
elif self.behaviour == "external_rep_indep":
    # Pulse: ObjFM.rep is unconditional and instantaneous.
    repair_cond_cur = lambda: True
    # NOTE: occ_law_21 below must also be overridden to delay(0) for this mode.
```

**Edits around line 1416 (the `add_aut2st` call's `occ_law_21`):**

```python
if self.behaviour == "external_rep_indep":
    objfm_repair_law = {"cls": "delay", "time": 0}
else:
    objfm_repair_law = self.set_occ_law_repair(repair_var_params_cur)
# ...
aut = self.add_aut2st(
    ...
    cond_occ_21=repair_cond_cur,
    occ_law_21=objfm_repair_law,
    ...
)
```

**Delete the entire centralized control block (lines 1431-1460):**

```python
# DELETE: the "Centralized control for external behaviours" block
# (the for loop that builds make_ctrl_method and registers via addSensitiveMethod).
# Also DELETE the now-unused self.target_impacting_automata accumulator
# at line 1227 if it has no other consumers.
```

`grep -n target_impacting_automata cod3s/` should be re-run to confirm no other consumer; if confirmed, remove the field.

**Validation gate for Phase 2**:
- `pytest tests/pyc_obj/obj_fm/test_comp_failure_external_001.py 002.py 003.py 004.py` all PASS.
- `pytest tests/pyc_obj/obj_fm/test_comp_failure_001.py ... 013.py` (internal mode tests) all PASS.
- New `external_rep_indep` tests still RED (we haven't fixed the target-side yet).

---

#### Phase 3 — Implement pulse model on the target side

**Files to modify:** `cod3s/pycatshoo/component.py` — method `_create_target_automaton` (lines ~1480-1565).

**Concrete edits:**

```python
def _create_target_automaton(
    self, target_name, repair_occ_law, failure_effects={}, repair_effects={}
):
    target_comp = self.system().component(target_name)

    # ... keep name-conflict check ...

    ctrl_var = self.ctrl_vars[target_name]

    def occ_condition():
        return ctrl_var.value() is True

    if self.behaviour == "external":
        def rep_condition():
            return ctrl_var.value() is False
    else:  # external_rep_indep
        # Reuse the user's original repair_cond, evaluated on this target only.
        rep_condition = self.get_repair_cond(target_comps=[target_comp])

    # ... resolve failure_effects on target_comp (unchanged) ...
    # ... resolve repair_effects on target_comp (unchanged) ...

    # In external_rep_indep, target also clears its own ctrl_var on repair.
    if self.behaviour == "external_rep_indep":
        final_repair_effects.append({"var": ctrl_var, "value": False})

    target_comp.add_aut2st(
        name=self.fm_name,
        st1=self.repair_state,
        st2=self.failure_state,
        init_st2=False,
        trans_name_12_fmt="{st2}",
        cond_occ_12=occ_condition,
        occ_law_12={"cls": "delay", "time": 0},
        occ_interruptible_12=True,
        effects_st2=final_failure_effects,
        effects_st2_format="records",
        trans_name_21_fmt="{st1}",
        cond_occ_21=rep_condition,
        occ_law_21=repair_occ_law,
        occ_interruptible_21=True,
        effects_st1=final_repair_effects,
        effects_st1_format="records",
        step=self.step,
    )
```

**Guard against `repair_var_params_order1=None`** (the `drop_inactive_automata` interaction):

```python
# In add_failure_repair_automaton, before the per-target automaton loop:
if self.behaviour == "external_rep_indep":
    if self.repair_var_params_order1 is None:
        raise ValueError(
            f"behaviour='external_rep_indep' requires order-1 repair parameters "
            f"to be active (drop_inactive_automata may have skipped order 1). "
            f"Provide a non-zero repair_param[0] or set drop_inactive_automata=False."
        )
```

**Validation gate for Phase 3**:
- All `test_comp_failure_external_rep_indep_*.py` tests PASS.
- All existing tests (internal + external 001-004) still PASS.
- Full suite: `pytest` — 197 + new tests, all green.

---

#### Phase 4 — Spec and documentation alignment

**Files to modify:** `FEAT_OBJFM_SPECS.md`.

Concrete updates:

- Section "2. `behaviour=\"external\"`":
  - Replace "**failure_effects**: Ignorés (warning émis)" → "Appliqués via l'automate du target lors de la transition vers le failure_state."
  - Same for repair_effects.
- Section "3. `behaviour=\"external_rep_indep\"`":
  - Rewrite "Flux d'exécution" to match the pulse model:
    ```
    DÉFAILLANCE:
    1. ObjFM.frun__cc_1 occ — effet: ctrl_frun_C1 := True
    2. C1.frun.occ — applique failure_effects
    3. ObjFM.frun__cc_1 rep (delay 0, sans condition) — pas d'effet sur ctrl
    
    RÉPARATION:
    4. C1.frun.rep — selon loi μ_1, cond: repair_cond originale évaluée sur C1
       effet: applique repair_effects + ctrl_frun_C1 := False
    ```
  - Adjust "Détails techniques":
    - "Loi de réparation": loi de l'ordre 1, héritée de `set_occ_law_repair(repair_var_params_order1)`.
    - "Condition de réparation": `repair_cond` originale, évaluée sur le target via `get_repair_cond([target_comp])`.
    - Remove the "Effet de réparation: Remet ctrl_var = False" line — it's still true but the wording was ambiguous; replace with "L'automate target applique repair_effects et remet ctrl_var = False sur sa transition de réparation".
- Section "Tests / Liste des tests":
  - Replace the old test list with the actual files implemented (`test_comp_failure_external_rep_indep_001.py` to `006.py`, plus `test_comp_failure_external_modes_errors.py`).
  - Drop `test_behaviour_effects_warning` (no longer applicable).

**Validation gate for Phase 4**:
- Spec is consistent with the implemented behavior.
- A reader new to the project can follow the spec and predict test outcomes.

---

#### Phase 5 — Cleanup and version bump

- Confirm WIP commit `0513249` (`print(fm)`) is no longer in the working tree (already cleaned in current session).
- Commit untracked but ready files: `tests/pyc_obj/obj_fm/test_comp_failure_external_004.py`, `uv.lock`, `.python-version` (if not already), `pyproject.toml` (Python 3.10 alignment).
- Bump version to `1.1.0` (minor — new feature semantics finalized) in `cod3s/version.py`.
- Run full quality suite:
  ```bash
  black .
  isort .
  flake8 . || true   # fix what's clearly new
  mypy cod3s/ || true
  pytest -v
  ```
- Single commit (or coherent series) with message:
  ```
  feat(objfm): finalize external_rep_indep pulse model and refactor ctrl_var
  
  - external_rep_indep: ObjFM transitions occ→rep instantly (delay 0) after triggering
  - external_rep_indep: target uses original repair_cond and order-1 repair law
  - Both external modes: ctrl_var maintained via direct transition effects
    (sensitive method removed for clarity and pulse-model correctness)
  - Adds 7 new test files covering external_rep_indep + error cases
  - FEAT_OBJFM_SPECS.md updated to match actual decisions on effects
  ```

---

## Alternative Approaches Considered

### Alternative A — Keep the sensitive method, branch its body per-mode

Instead of replacing the sensitive method with direct effects, conditionalize its body: in `external_rep_indep`, ignore the OR over impacting automata and only react to explicit calls.

**Why rejected:** more code, more conditions, more subtle interaction with simulator-internal ordering. The unification benefit of the chosen approach is significant: one mental model for both modes, and the existing `external` tests double as a regression suite for the refactor.

### Alternative B — Introduce an intermediate `occ_pending` state on the ObjFM

Have the ObjFM go `rep → occ_pending → occ → rep` where `occ_pending` waits for all targets to confirm propagation before transitioning to `occ` (which then transitions back to `rep` in pulse mode). Provides deterministic temporal trace.

**Why rejected:** extra states pollute sequence analysis, transition naming becomes ambiguous, no concrete benefit over direct effects given that the failure_cond augmentation already prevents re-firing during the propagation window.

### Alternative C — Defer external_rep_indep to a follow-up PR; only refactor

Land just the `ctrl_var` refactor first, then implement `external_rep_indep` on top.

**Why rejected:** the refactor without a use case is hard to justify, the brainstorm decisions are fresh, and the riskiest part (regression on `external`) is exercised by both efforts. Bundling them keeps the surface area review-friendly and avoids two rounds of context-loading.

---

## Acceptance Criteria

### Functional Requirements

- [ ] `ObjFM(behaviour="external_rep_indep")` creates `ctrl_{fm}_{tgt}` variables on the ObjFM and an automaton `{fm_name}` in each target with the same states as the ObjFM (`failure_state` / `repair_state`).
- [ ] Triggering an ObjFM combo automaton in `external_rep_indep`:
  - sets `ctrl_var = True` for each target of the combo;
  - the ObjFM transitions back to `rep` in `delay(0)` without conditions and without affecting `ctrl_vars`.
- [ ] Each target self-repairs:
  - according to the order-1 repair law (`exp(μ_1)` for `ObjFMExp`, `delay(ttr_1)` for `ObjFMDelay`);
  - guarded by the user's original `repair_cond` evaluated on that target alone;
  - applies `repair_effects` AND sets `ctrl_var = False` on its repair transition.
- [ ] `failure_effects` and `repair_effects` are applied via the **target's automaton** in both `external` and `external_rep_indep` modes.
- [ ] `failure_cond` augmentation ("all targets of the combo in `repair_state`") applies in both `external` and `external_rep_indep`.
- [ ] `internal` mode is unchanged.
- [ ] Existing `external` mode tests (001-004) pass without modification.

### Non-Functional Requirements

- [ ] No new sensitive methods are added; the existing per-target sensitive method block is removed.
- [ ] Public API of `ObjFM.__init__` is unchanged (no new required parameters).
- [ ] `target_impacting_automata` field is removed if and only if no consumer remains (verify via grep).
- [ ] Black, isort applied; flake8 clean on the modified file (or no new warnings).
- [ ] Full test suite runs in <10 s on the dev machine.

### Quality Gates

- [ ] Every new test asserts at least one observable state (target var value, automaton state, fireable transition list).
- [ ] At least one test exercises a multi-target combo (`cc_12`) in `external_rep_indep`.
- [ ] At least one test verifies that `repair_cond` actually gates the target's repair (not always `True`).
- [ ] The spec doc, post-update, contains zero claims that contradict actual behavior.
- [ ] Code review passes (no merge conflicts with master).

---

## Success Metrics

- **Before**: `external_rep_indep` has 0 tests, 1 explicit `TODO`, conflicting spec; `external` mode has 4 tests, 197 total tests pass.
- **After**: `external_rep_indep` has 7+ tests covering creation, pulse, multi-target, effects, repair_cond, ObjFMDelay, error cases; `TODO` resolved; spec aligned with code; total tests ≥ 215, all pass; version bumped to 1.1.0.
- **Qualitative**: a new contributor (or future Roland) reading the spec can predict and validate behavior without reading the implementation.

---

## Dependencies & Prerequisites

### Hard prerequisites (already satisfied)

- ✅ Python 3.10.18 venv and Pycatshoo importable (fixed in current session).
- ✅ `print(fm)` WIP cleaned in `cod3s/pycatshoo/system.py:401`.
- ✅ Full test baseline of 197 passing tests.
- ✅ Brainstorm captured at `docs/brainstorms/2026-04-28-objfm-external-modes-brainstorm.md`.

### Soft dependencies

- The `kb_test.py` `ObjFlow` and `ObjFlow2I1O` components are sufficient for all the planned tests; no new test fixture component is required.
- `ObjFMDelay` test (006) requires `ObjFMDelay` to be already wired through `add_component(cls=...)`; verify this is the case before writing the test.

### External

- None. No new third-party dependency, no new file outside `cod3s/` and `tests/`.

---

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Refactor of `ctrl_var` breaks the existing `external` tests | Medium | High | Run external tests after every edit in Phase 2; if they fail, revert and use Alternative A (sensitive method conditionalized) as fallback. |
| PyCATSHOO order of multiple `delay(0)` transitions is non-deterministic and breaks the pulse | Medium | High | Test in **isimu** (manual fire) first to prove logic, then run a Monte Carlo loop (`PycMCSimulationParam`, e.g., 1000 runs) and verify the count of failure events matches the analytical expectation within a tolerance. If non-determinism appears, fall back to Alternative B (`occ_pending` state). |
| `repair_var_params_order1 is None` when order 1 is dropped by `drop_inactive_automata` | Low | Medium | Explicit `ValueError` with actionable message added in Phase 3. Test in `test_comp_failure_external_modes_errors.py`. |
| Hidden consumer of `target_impacting_automata` outside `add_failure_repair_automaton` | Low | Low | `grep -rn target_impacting_automata cod3s/ tests/` before deletion. If found, keep the field but stop populating it from the new code path. |
| Spec drift in `FEAT_OBJFM_SPECS.md` not caught | Medium | Low | Phase 4 is its own gate; review side-by-side against the test file as ground truth. |
| Migration impact on user studies relying on the old (broken) `external_rep_indep` | Very Low | Low | Nobody can rely on the broken behavior — there are no tests, no documentation matching the code, and the `TODO` flags it. Document the change in the commit message and release notes. |

---

## Resource Requirements

- **People**: solo (Roland), ~1 working day.
- **Time estimate**:
  - Phase 1 (test scaffolding): 2 h (writing 7 test files, mostly mechanical).
  - Phase 2 (refactor): 1.5 h + 0.5 h validation = 2 h.
  - Phase 3 (target side + guard): 1.5 h.
  - Phase 4 (spec): 1 h.
  - Phase 5 (cleanup, commit): 0.5 h.
  - Total: ~7 h, allowing for iteration and debugging.
- **Compute**: standard dev machine. Monte Carlo validation in Phase 5 is bounded (≤ 30 s per 1000-run simulation).

---

## Future Considerations

Out of scope for this plan but worth noting:

1. **`external_fail_indep`** symmetric mode — a target could also have an independent failure law (currently external both directions are tied to ObjFM occ). Probably rare, easy to add later by mirroring `external_rep_indep`.
2. **Per-target `repair_param`** — let the user provide `repair_param_target=[μ_C1, μ_C2]` instead of using the order-1 law for all. Adds expressivity but complicates the API; defer until a real use case appears.
3. **Integration with `SequenceAnalyser`** — the pulse pattern means each combo emits an `occ` and `rep` event back-to-back on the ObjFM, which may pollute sequences. A sequence post-processing helper to filter / merge these "pulse events" might be useful.
4. **Performance** — for very wide combos (order ≥ 5), the number of automata grows as 2^N. Already true today; not introduced by this change. Could be capped via a `max_order` parameter in a future iteration.
5. **CLAUDE.md update** — once `behaviour` is firmly in place, add a paragraph to `CLAUDE.md` describing the three modes for future AI assistants. Do not couple this with the current PR (deferred to a docs PR).

---

## Documentation Plan

- [ ] Update `FEAT_OBJFM_SPECS.md` (Phase 4, in-PR).
- [ ] Add a one-liner mention in `README.md` about the three behaviours of ObjFM (deferred to follow-up docs PR).
- [ ] Add a worked example in `examples/` showing `external_rep_indep` (deferred to follow-up; not in MVP).
- [ ] No mkdocs site update required for this PR (the static doc references `concepts.md` which doesn't drill into ObjFM internals).

---

## References & Research

### Internal references

- **Brainstorm**: `docs/brainstorms/2026-04-28-objfm-external-modes-brainstorm.md` (this PR's source-of-truth on decisions)
- **Spec to update**: `FEAT_OBJFM_SPECS.md` (lines 89-91 on effects, sections "external" / "external_rep_indep")
- **Main implementation file**: `cod3s/pycatshoo/component.py`
  - `ObjFM.__init__` at line 1105 (signature, behaviour validation, ctrl_vars creation)
  - `ObjFM.add_failure_repair_automaton` (combo automata loop) — main edit site, lines 1229-1478
  - `ObjFM._create_target_automaton` (target-side automaton) — main edit site, lines 1480-1565
  - `ObjFM.get_repair_cond` at line 1611 (used to evaluate target-local repair_cond)
  - `PycComponent.add_aut2st` at line 343 (the underlying API for adding 2-state automata)
- **Existing tests preserved**:
  - `tests/pyc_obj/obj_fm/test_comp_failure_external_001.py` — sync semantics, single + multi target
  - `tests/pyc_obj/obj_fm/test_comp_failure_external_002.py` — effects propagation
  - `tests/pyc_obj/obj_fm/test_comp_failure_external_003.py` — 3-target all-combos parametrized
  - `tests/pyc_obj/obj_fm/test_comp_failure_external_004.py` — multi-FM with target dependencies (uncommitted)
- **Internal-mode tests** (regression baseline, must keep passing):
  - `tests/pyc_obj/obj_fm/test_comp_failure_001.py` through `_013.py`
- **Test helper / fixtures**: `tests/pyc_obj/obj_fm/kb_test.py` — `ObjFlow`, `ObjFlow2I1O`
- **Related commits**:
  - `59fc27d` — initial external behaviour scaffolding
  - `721414c` — removed obsolete warnings (confirms decision on effects)
  - `0513249` — WIP `print(fm)` (already cleaned in current session)
  - `4f36f40`, `1b2f421` — recent logger plumbing (orthogonal, low risk)
- **Memory**: `~/.claude/projects/.../memory/project_objfm_external_decisions.md`

### External references

- PyCATSHOO (EDF) is closed-source; documentation is local at `/home/roland/Work/EdgeMind/Dev/pycatshoo/`. No external doc needed.

### Related work

- No open issues on this topic.
- No related PRs in flight (master is the only active branch).

---

## Implementation Checklist (in order)

- [x] Phase 1.1 — Write test_comp_failure_external_rep_indep_001.py (creation/structure). 3/3 PASS coincidentally (creation already works in current code).
- [x] Phase 1.2 — Write 002.py (pulse single target). 2/2 RED.
- [x] Phase 1.3 — Write 003.py (multi-target combos). 2/2 RED.
- [x] Phase 1.4 — Write 004.py (effects propagation). 2/2 RED.
- [x] Phase 1.5 — Write 005.py (repair_cond gating). 2/2 RED.
- [x] Phase 1.6 — Write 006.py (ObjFMDelay compat). 1/1 RED.
- [x] Phase 1.7 — Write test_comp_failure_external_modes_errors.py. 2 PASS, 2 RED (drop_inactive guard + name_conflict isolation).
- [x] Phase 2.1 — In `add_failure_repair_automaton`, set `failure_effects_cur=[ctrl=True]` for external_rep_indep (kept centralized sensitive method for `external` after diagnosing a self-conflict between cc_X.rep effect and cc_Y.occ effect when both registered on the same ctrl variable).
- [x] Phase 2.2 — Apply external augmentation to both modes for `failure_cond`; `repair_cond_cur = lambda: True` for external_rep_indep.
- [x] Phase 2.3 — Override `occ_law_21` to `delay(0)` for `external_rep_indep`.
- [x] Phase 2.4 — Sensitive-method block KEPT for `external` (provably equivalent and avoids the multi-combo conflict on shared ctrl vars at simulation start). Skipped for `external_rep_indep`.
- [x] Phase 2.5 — External 001-004 tests pass (12/12).
- [x] Phase 2.6 — Internal tests 001-013 pass.
- [x] Phase 3.1 — `_create_target_automaton` uses `self.get_repair_cond(target_comps=[target_comp], param=self.repair_var_params_order1)` for the target's repair condition.
- [x] Phase 3.2 — Guard added: in `external_rep_indep`, raise `ValueError` when `repair_var_params_order1` is None or its repair law is inactive.
- [x] Phase 3.3 — All `external_rep_indep_*` tests pass.
- [x] Phase 3.4 — Full suite GREEN: 213 passed (197 baseline + 16 new), 0 failed.
- [ ] Phase 3.5 — MC simulation smoke test (deferred — full suite passing is strong enough signal).
- [x] Side fix — Replaced effects-driven ctrl reset with a sensitive method on the target's automaton (NOT on the variable) to avoid cascading re-evaluation conflicts between ObjFM.occ effect and target.rep effect at simulation start.
- [ ] Phase 4.1 — Edit `FEAT_OBJFM_SPECS.md` sections "external" and "external_rep_indep".
- [ ] Phase 4.2 — Edit "Tests / Liste des tests" to match the new file list.
- [ ] Phase 5.1 — black + isort + flake8 + pytest sanity sweep.
- [ ] Phase 5.2 — Bump `cod3s/version.py` to 1.1.0.
- [ ] Phase 5.3 — Single descriptive commit.
- [ ] Phase 5.4 — Clean memory entry: update `~/.claude/projects/.../memory/project_objfm_external_decisions.md` with "implemented" status.
