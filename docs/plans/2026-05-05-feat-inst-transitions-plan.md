---
title: feat — Probabilistic instantaneous transitions (inst branching) end-to-end support
type: feat
date: 2026-05-05
brainstorm: docs/brainstorms/2026-05-05-inst-transitions-brainstorm.md
---

# feat: End-to-end support for probabilistic instantaneous transitions

## Overview

Finalize the support of **instantaneous transitions with probabilistic branching** in cod3s. Today the data model exists (`InstOccDistribution`, polymorphic `target: str | List[StateProbModel]`), but it carries a `# NOT WORKING: PARAMETERS DOES NOT SEEMED TO BE ASSIGNED…` warning, has no parameter round-trip validation, no per-branch effects mechanism, no exposure in `cod3s-isimu` (targets show as `[…]`, no branch picker), and no high-level helper for declaring a branching with effects-per-outcome. This plan covers three sequential phases: backend audit + per-branch effects (Phase 1), iSimu UX with atomic resolution of pending inst transitions (Phase 2), and a high-level DSL helper plus an example (Phase 3). Each phase ships its own tests in TDD-first style and must remain green for the prior phases.

The work concludes a half-implemented feature that has been latent in the codebase and unblocks modelling patterns where a system enters a state and a probabilistic choice must be resolved instantly (failure types, switching outcomes, conditional success/failure of operations).

---

## Problem Statement

### What's broken or missing today

1. **Backend validation gap.** `cod3s/pycatshoo/automaton.py:347-351` writes `N-1` probabilities to the Pycatshoo `inst` law via `law.setParameter(prob, i)` and lets the engine compute the last as the complement. A comment on line 441 of the same file (`# NOT WORKING: PARAMETERS DOES NOT SEEMED TO BE ASSIGNED...`) signals doubt that this round-trip actually works. No existing test verifies that the empirical sampling frequencies match the declared probabilities.

2. **No per-branch effects mechanism.** `add_aut2st` declares effects via `effects_st1`/`effects_st2` (state entry sensitive methods), but inst branching has no equivalent — users must hand-roll a state and its sensitive method for each outcome.

3. **iSimu blind to branching.** `cod3s/pycatshoo/isimu/panels.py:157` displays `[…]` for inst transitions. `ReplanModal` only asks for a date (irrelevant for inst). `transition_to_indexed_dict` does explode `target` lists into per-branch dicts (`system.py:88-91`) but the TUI never exploits this. The user can't see branches, can't see probabilities, can't pick.

4. **Atomic resolution unsupported.** Pycatshoo resolves all pending inst transitions at instant `t` before any timed transition. When several inst transitions are pending at the same `t`, the user must submit the branch choices for all of them in a single batch, then let the engine drain. The current iSimu has no notion of this batch step.

5. **No high-level DSL.** Users today must write the full inst transition by hand:
   ```python
   automaton.transitions.append({
       "name": "branch", "source": "S",
       "target": [{"state": "S1", "prob": 0.6}, {"state": "S2"}],
   })
   ```
   And then attach effects via custom sensitive methods. There is no `add_inst_branch(...)` analogous to `add_aut2st`.

6. **No documentation, no example.** The feature has zero coverage in `docs/user-guide/` and zero example in `examples/` — even though `test_pyc_iter_simu_002.py` exercises a basic coin-toss, it is invisible to users discovering the library.

### Why it matters now

- The codebase is between feature versions (parent `cod3s` 1.1.1, isimu stabilized) — natural window to add the inst support without colliding with other ongoing chantiers.
- Several future use cases (failure-type tirage, ObjFM extensions for multi-severity faults, switching outcomes in industrial scenarios) are blocked by this support.
- The `# NOT WORKING` comment is a visible smell that erodes trust in the codebase; auditing and resolving it is overdue.

---

## Proposed Solution

### High-level approach

A **3-phase plan** mirroring the brainstorm structure, executed in strict order with TDD-first methodology and a green-bar discipline at each phase boundary.

1. **Phase 1 — Backend audit + per-branch effects.** Audit `to_bkd`/`update_bkd` for inst via a deterministic round-trip test, drop the `NOT WORKING` comment if the audit is clean (or fix if not). Introduce a `BranchModel` pydantic, add validation (distinct targets, sum prob ≤ 1), and provide a `register_branch_effects(...)` low-level utility on `PycComponent` that wires state-entry sensitive methods for each branch's effects.
2. **Phase 2 — iSimu UX for inst pending.** Detect pending inst transitions in the engine layer, surface them as a separate "inst pending" mode in the fireable panel (or a dedicated panel — to be decided in implementation), foldable tree with default = max-prob branch and `!` marker for deterministic branches, atomic submission via a new key binding (e.g. `s`).
3. **Phase 3 — DSL helper + example.** Add `comp.add_inst_branch(...)` on `PycComponent`, document it, and ship a runnable example `examples/inst_branching_demo/` with iSimu instructions.

The riskiest phase is **Phase 2**: it touches the live `cod3s-isimu` UX. We mitigate by keeping Phase 1 strictly additive (no UI change) and by writing isimu tests for Phase 2 before any UI code.

### Constraints

- **Phase order is strict** per user request: 1 → 2 → 3, never overlapping.
- **TDD-first** at each phase: write the failing test, see it red, implement, see it green, refactor.
- **No regression** on existing inst transition behavior (`test_pyc_iter_simu_002.py`, `test_pyc_system_002.py`, `test_pyc_iter_simu_003.py` must stay green throughout).
- **Solo project — no PRs.** Roland merges to master himself when validated. No `gh pr create` to be proposed.
- **Branches must have distinct target states** within a transition (decided in brainstorm, key decision #3). Validation enforced in `BranchModel`.

### Backwards compatibility

- The data model `target: str | List[StateProbModel]` is preserved; `BranchModel` is an internal alias / refinement of `StateProbModel` (or replaces it cleanly with `model_validator` migration).
- Existing tests using inst transitions (coin-toss, etc.) continue to pass.
- `ReplanModal` keeps its current behaviour for timed transitions; the new "inst pending" mode is additive.

---

## Technical Approach

### Architecture

#### Phase 1 — Backend

**1.1. Audit via deterministic round-trip RED test**

A new test `tests/pyc_obj/test_inst_001_roundtrip.py` builds a 2-branch transition with `probs=[0.7, 0.3]` (deliberately asymmetric to detect off-by-one or swapped-index bugs), then **without running any simulation** asserts:

- `law.nbParam() == 1` (Pycatshoo stores `N-1` probs, complement implicit).
- `law.parameter(0) == 0.7` (the value sent via `setParameter(0.7, 0)` is actually held).
- `trans._bkd.targetCount() == 2` and `trans._bkd.target(0).basename() == "<expected_state_0>"` etc. (target ordering preserved).
- `PycOccurrenceDistribution.from_bkd(law).probs == [0.7]` (round-trip through `from_bkd` matches what `to_bkd` wrote).

A second test does the same with 4 branches `[0.5, 0.2, 0.2, 0.1]` to verify multi-branch parameter passing (`law.nbParam() == 3`, `parameter(0..2) == 0.5, 0.2, 0.2`).

This audits exactly what the `# NOT WORKING` comment doubts (parameter assignment) **without** depending on Pycatshoo's RNG, without statistical noise, and in milliseconds.

If RED: investigate `to_bkd` (which `setParameter` overload is called? does `IDistLaw.parameter(idx)` round-trip the value? is the `:-1` slice correct?) and the `addTarget` ordering. Fix root cause.

If GREEN: drop the `# NOT WORKING` comment in the same Phase 1 commit.

**1.2. `BranchModel` pydantic + validation**

In `cod3s/pycatshoo/automaton.py`, refine `StateProbModel` (or introduce `BranchModel` as a successor) with the brainstorm-decided shape:
```python
class BranchModel(pydantic.BaseModel):
    target: str = pydantic.Field(..., description="Target state name")
    prob: float | None = pydantic.Field(
        None, description="Branch probability (None = complement-share)"
    )
    effects: dict = pydantic.Field(
        default_factory=dict,
        description="Per-branch effects applied on target state entry",
    )
    effects_format: typing.Literal["dict", "records"] = pydantic.Field(
        "dict", description="Format of effects dict"
    )
```
And in `TransitionModel.check_model`:
- Validate `target` field: when it's a list, sum of explicit probs ≤ 1 (with float tolerance), `None` probs share the complement equally, **all `target_state` values are distinct**.
- Raise `ValueError` with a clear message if duplicates are found.

Migration: keep `StateProbModel` as an alias if used elsewhere (tests, sequence analyser). Field `prob: float` → `prob: float | None` to support `None`-share.

**1.3. `register_branch_effects` low-level utility**

In `cod3s/pycatshoo/component.py`, add a method:
```python
def register_branch_effects(
    self, automaton, transition_name, branches: list[BranchModel]
):
    """Wire state-entry sensitive methods for each branch's effects."""
    for branch in branches:
        if not branch.effects:
            continue
        target_state = automaton.get_state_by_name(branch.target)
        # Build & register the per-branch sensitive method:
        method_name = f"branch_eff__{automaton.name}__{transition_name}__{branch.target}"
        callback = self._make_effects_callback(branch.effects, branch.effects_format)
        target_state._bkd.addSensitiveMethod(method_name, callback)
```
The internal `_make_effects_callback` reuses the dict/records dispatch logic already present in `add_aut2st` (lines 495-540 of `component.py`). Effects are applied unconditionally on state entry — if a target is reachable both by an inst branch with effects and by a regular timed transition with no effects, the user must split states (decided in brainstorm key decision #3 + open question 2).

**1.4. Tests Phase 1**

| Test file | Purpose |
|---|---|
| `tests/pyc_obj/test_inst_001_roundtrip.py` | Deterministic round-trip: probs sent via `to_bkd` are correctly held by Pycatshoo and recoverable via `from_bkd` (2- and 4-branch cases). Audits `# NOT WORKING`. |
| `tests/pyc_obj/test_inst_002_branch_effects.py` | Each branch applies its own effects on target entry; verify post-firing variable values via deterministic seed + single run. |
| `tests/pyc_obj/test_inst_003_validation.py` | Pydantic raises on duplicate targets, on sum > 1, accepts mixed `prob=None`. |
| `tests/pyc_obj/test_inst_004_complement.py` | A 4-branch with 2 explicit probs and 2 `None` correctly distributes the residual 1 - sum (verified via `law.parameter(idx)` round-trip). |
| `tests/pyc_obj/test_inst_005_no_regression.py` | Re-runs the legacy coin-toss tests with the new validation in place; no behaviour change. |

#### Phase 2 — iSimu (TUI)

**2.1. Engine layer — pending inst detection**

In `cod3s/pycatshoo/system.py`:
- Add `isimu_pending_inst()` returning the list of `PycTransition` objects whose `occ_law` is an `InstOccDistribution` and whose `end_time == currentTime()` (i.e. fireable now).
- `isimu_step_forward` keeps current behaviour but exposes a new state flag (`has_pending_inst`) to the UI layer.
- Add `isimu_resolve_inst(choices: dict[trans_id, state_index])` that batches `setTransPlanning` calls for each provided choice, then triggers `stepForward`.

**2.2. State layer — `ISimuState`**

In `cod3s/pycatshoo/isimu/state.py`:
- Add a field `pending_inst: list[PycTransition]` populated alongside `fireable`.
- Update the engine wrapper (`engine.py`) to invoke `isimu_pending_inst()` on every refresh.

**2.3. UI layer — new panel mode**

In `cod3s/pycatshoo/isimu/panels.py`:
- When `state.pending_inst` is non-empty, the **fireable panel** switches to "inst pending" mode (alternative: split into a new `InstPendingPanel` widget — decision deferred to implementation, keep one widget if possible to avoid layout churn).
- Layout: a Textual `Tree` widget. Root nodes = transitions (1 per pending inst), labeled `comp.aut.transition (k branches)` plus `!` if `k == 1`. Children = branches, labeled `→ target_state (p=0.NN)`.
- Each transition node tracks a "selected branch" state. Default = max-prob branch (or only branch if `!`).
- Keyboard: arrow up/down navigate ; space/enter on a branch selects it as the choice for its parent transition ; new key `s` submits all choices.

**2.4. Modal flow**

- No `ReplanModal` for inst (decided in brainstorm key decision #8).
- A confirmation in the footer/help banner displays "Inst pending — press `s` to submit, navigate with arrows, space/enter to override branch".

**2.5. Tests Phase 2**

| Test file | Purpose |
|---|---|
| `tests/isimu/test_inst_panel_001_detection.py` | A system with a 2-branch inst pending → `state.pending_inst` non-empty, `state.fireable` empty (or filtered). |
| `tests/isimu/test_inst_panel_002_tree_layout.py` | Mount the panel, snapshot the tree layout (root + branches with probas). |
| `tests/isimu/test_inst_panel_003_default_selection.py` | Default-selected child = max-prob branch ; `!` marker present when `len(branches) == 1`. |
| `tests/isimu/test_inst_panel_004_atomic_submit.py` | Two simultaneous pending inst transitions ; user navigates, changes one choice, submits → verify both `setTransPlanning` calls and the post-step state. |
| `tests/isimu/test_inst_panel_005_after_step.py` | After atomic submit, panel reverts to "fireable timed" mode ; sequence trace contains the fired branches with correct target states. |

#### Phase 3 — DSL helper + example

**3.1. `add_inst_branch` on `PycComponent`**

```python
def add_inst_branch(
    self,
    automaton: str,
    name: str,
    source: str,
    branches: list[dict | BranchModel],
    condition=True,
    is_interruptible: bool = True,
):
    """Add an instantaneous probabilistic branching transition.

    Parameters
    ----------
    automaton : str
        Name of the existing automaton (states must be pre-declared).
    name : str
        Name of the new transition.
    source : str
        Source state name within the automaton.
    branches : list[dict | BranchModel]
        Branches with target/prob/effects.
    condition : bool | str | callable
        Guard condition controlling when the branching is fireable.
    is_interruptible : bool
        Standard interruptible flag (see add_aut2st).

    Raises
    ------
    ValueError if targets aren't distinct, if a target state is missing,
    or if probs sum > 1 + eps.
    """
```
Implementation:
1. Resolve the automaton object from `self.automata_d[automaton]`.
2. Build `BranchModel` instances for each entry in `branches`.
3. Construct a `PycTransition` with `target=[{"state": b.target, "prob": b.prob} for b in branches]`.
4. Append to `automaton.transitions` and call `automaton.update_bkd(self)` (incremental — to be confirmed) or rebuild as appropriate.
5. Call `register_branch_effects(automaton, name, branches)` from Phase 1.

**3.2. Example**

`examples/inst_branching_demo/inst_branching_demo.py`:
- A single `PycComponent` `valve` with an automaton at 4 states: `closed`, `opening`, `panne_severe`, `panne_legere`.
- A timed transition `closed → opening` (delay 5).
- An inst branching `opening → {panne_severe, panne_legere, closed}` with `[0.05, 0.15, 0.80]` and per-branch effects (`severity` variable).
- A factory function `build_system()` for use with `cod3s-isimu --factory`.
- A docstring walking through the user interaction (`Enter` to fire the timed transition, panel switches to inst pending, `s` to accept defaults, observe the sequence).

**3.3. Documentation**

`docs/user-guide/inst-branching.md`:
- Concept overview.
- Code example.
- iSimu walk-through with screenshots (text-based).
- Limitations (distinct targets, no replanning of date).

**3.4. Tests Phase 3**

| Test file | Purpose |
|---|---|
| `tests/pyc_obj/test_add_inst_branch_001_basic.py` | Helper creates the transition and effects ; equivalent to Phase 1 test 002 but via the helper. |
| `tests/pyc_obj/test_add_inst_branch_002_validation.py` | Helper raises on missing target state, non-existent automaton, etc. |
| `tests/scripts/test_run_cod3s_isimu_inst_demo.py` | The example factory `inst_branching_demo:build_system` boots correctly under `cod3s-isimu --headless` (smoke test). |

---

## Phasing & TDD discipline

### Phase 1 — Backend (estimated 0.5–1 day)

1. **RED**: Commit `tests/pyc_obj/test_inst_001_roundtrip.py` (and 002–005). Run pytest, observe the round-trip test (and any others) failing or revealing what's broken in `update_bkd`/`to_bkd`.
2. **AUDIT**: If RED, investigate. Most likely outcomes: bug in `setParameter` index, wrong `addTarget` order, or pydantic field migration needed.
3. **GREEN**: Fix the smallest thing that turns the tests green. Drop `# NOT WORKING` comment.
4. **REFACTOR**: Add `BranchModel`, validation, and `register_branch_effects`. Re-run all tests including the legacy `test_pyc_iter_simu_002` to confirm no regression.
5. **COMMIT**: `test(inst): RED tests for inst transitions backend` then `feat(inst): per-branch effects + validation`.

### Phase 2 — iSimu (estimated 1–1.5 days)

1. **RED**: Commit `tests/isimu/test_inst_panel_*` (5 tests). Run pytest with the snapshot tests using Textual Pilot. Observe failures.
2. **GREEN engine layer**: implement `isimu_pending_inst()` and `isimu_resolve_inst(...)`. Unit tests 001 & 004 turn green.
3. **GREEN UI layer**: implement the panel mode switch, the Tree, the keyboard handlers. Tests 002, 003, 005 turn green.
4. **MANUAL VALIDATION**: launch `cod3s-isimu --factory examples/objfm_demo:build_system` (or a quick fixture) to confirm timed transitions still work normally with no regressions.
5. **COMMIT**: `test(isimu): RED tests for inst panel` then `feat(isimu): inst pending panel + atomic submission`.

### Phase 3 — DSL helper + example (estimated 0.5 day)

1. **RED**: Commit `test_add_inst_branch_*` and the example file (with a smoke test).
2. **GREEN**: Implement `add_inst_branch`, fill the example and docs.
3. **COMMIT**: `test(dsl): RED tests for add_inst_branch` then `feat(dsl): add_inst_branch helper + example + user guide`.

### Final checkpoint

- All 200+ existing tests still pass.
- New tests (≈12) pass.
- `mkdocs build` succeeds with the new user-guide page.
- Manual run of `examples/inst_branching_demo/` under `cod3s-isimu` validates the end-to-end UX.
- Bump `cod3s` version (1.1.1 → 1.2.0 — minor bump, new feature) and the `cod3s-isimu` version per CLAUDE.md rule (`+0.1.0` for "new panel/modal/engine API").

---

## Branch & versioning

- **Branch**: `feat/inst-transitions` from `master`.
- **Per-phase commit**: 1 RED commit + 1 GREEN/refactor commit per phase = 6 commits + final docs/version bump = 7–8 commits total.
- **Version bumps**:
  - Parent `cod3s` 1.1.1 → 1.2.0 (new public API: `add_inst_branch`, `BranchModel`).
  - `cod3s-isimu` `+0.1.0` (new panel + engine API, decided rule per CLAUDE.md).
- **Spec / docs**: `docs/user-guide/inst-branching.md` new ; CLAUDE.md examples section augmented with `inst_branching_demo`.

---

## Risks & mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Audit reveals a real Pycatshoo binding bug in `to_bkd` | Medium | Medium | First Phase 1 test is a deterministic round-trip on `law.parameter(idx)` and `targetCount` ; if it goes red, the failure pinpoints exactly which value is wrong. Mitigation = `setParameter` overload check + Pycatshoo official examples comparison. |
| iSimu Tree widget less ergonomic than expected | Low | Low | Fallback: per-branch rows in the existing DataTable (option B from brainstorm discussion). Decision deferred to implementation if tree feels heavy. |
| Atomic submission ordering produces non-deterministic behaviour | Low | Medium | Document ordering rule (insertion order = transition discovery order). If Pycatshoo behaviour depends on order, expose explicit priority in `BranchModel` or transition. |
| Effects state-entry mechanism conflicts with existing `add_aut2st` effects on the same state | Low | Medium | Document the rule "one effects clause per state". Add a runtime warning when registering a duplicate sensitive method on the same state. |
| Phase 2 Textual snapshot tests are flaky | Medium | Low | Use Textual Pilot's deterministic API ; avoid time-based assertions ; keep snapshots small and version-pinned. |

---

## Open questions for plan execution

1. **`isimu_pending_inst` API shape**: should it return `PycTransition` objects (rich, with branches and probas) or a flatter dict? Decision during Phase 2.
2. **`BranchModel` vs `StateProbModel`**: replace or alias? Decision during Phase 1 based on usage outside `automaton.py` (sequence analyser, etc.).
3. **`add_inst_branch` and existing `add_aut2st` integration**: should we expose the source state's exit-effects as well? Defer to YAGNI unless requested.
4. **Snapshot of empty branches**: what if user passes `branches=[]`? Reject in validator (no point).
5. **Re-entry into the same source state**: does the inst transition fire again immediately if the guard is still true? Pycatshoo behaviour to be observed during Phase 1 audit ; document either way.

---

## Definition of Done

- [ ] Phase 1: 5 new backend tests green ; `# NOT WORKING` comment removed or replaced by a justified note ; `BranchModel` + validation + `register_branch_effects` shipped.
- [ ] Phase 2: 5 new isimu tests green ; pending inst panel + atomic submission live ; manual validation on an existing example confirms timed flow unchanged.
- [ ] Phase 3: `add_inst_branch` shipped ; `examples/inst_branching_demo/` runnable ; `docs/user-guide/inst-branching.md` published ; smoke test green.
- [ ] All pre-existing tests still green.
- [ ] `mkdocs build` succeeds.
- [ ] Versions bumped (parent + isimu).
- [ ] Branch merged to master locally by Roland (no PR).
