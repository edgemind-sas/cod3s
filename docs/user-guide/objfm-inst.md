# On-Demand Failure Modes (ObjFMInst)

`ObjFMInst` models a failure **on solicitation**: whenever a demand
occurs, the component fails with probability `gamma` — one Bernoulli
draw per demand front, instantaneously. Typical use cases: a detector
missing an event, a generator failing to start, a switch failing to
commute. The repair transition stays governed by an **exponential**
law (`mu`), exactly like `ObjFMExp`.

This complements the time-based laws:

| Class        | Failure law                     | Repair law   |
|--------------|---------------------------------|--------------|
| `ObjFMExp`   | exponential (`lambda` per hour) | exponential  |
| `ObjFMDelay` | deterministic delay (`ttf`)     | delay        |
| `ObjFMInst`  | probability `gamma` per demand  | exponential  |

## Semantics

The demand is the inherited `failure_cond` — there is no extra field.
Each cc-combination automaton has **three states**:

```
                inst, guard = failure_cond
    rep ─────────────────────────────────────► occ      (prob gamma)
     ▲  └──────────────────────────────────► not_occ   (prob 1-gamma)
     │                                           │
     │  exp(mu), guard = repair_cond             │ inst p=1,
     └───────────────────────── occ ◄────────────┘ guard = NOT failure_cond
```

* **One front, one draw.** The `not_occ` state absorbs the demand
  front: while `failure_cond` stays true the automaton waits there (no
  re-draw). This is what prevents a Zeno loop — PyCATSHOO inst
  transitions fire *by level*, not by edge.
* **Same-instant re-arm.** The return `not_occ → rep` is an inst p=1
  transition (not a `delay(0)`): inst transitions drain before any
  timed transition of the same instant, so a demand that falls and
  rises at the same simulated date is re-armed and drawn, not missed.
  Two fronts at the same instant = two draws.
* **Re-fire after repair.** If the repair completes while the demand
  still holds, the automaton re-draws immediately (the repaired
  component is re-solicited). To model "one failed attempt per demand,
  no retry", set `mu = 0` — the mode then stays failed until the end
  of the sequence.

## Parameters and CCF

`failure_param = [gamma_1, ..., gamma_n]` — the probability of the
order-`k` common-cause event per solicitation, symmetric to the
`lambda_k` of `ObjFMExp`. `repair_param = [mu_1, ..., mu_n]`. The
2^N − 1 combination automata are generated unchanged (`__cc_` suffix
convention); on a shared demand front **each combination draws
independently**. Two distinct subsets may both fail on the same demand
(probability = product of their gammas, a second-order effect) — the
same independence structure as the exponential CCF processes.

## Python API

```python
system.add_component(
    cls="ObjFMInst",
    fm_name="fail_to_start",
    targets=["generator"],
    failure_cond=lambda: grid.grid_up.value() is False,  # the demand
    failure_effects={"failed": True},
    failure_param=0.3,   # gamma
    repair_param=0.5,    # mu (exponential)
)
```

Follow the reinitialised-variable convention for effects (declare the
target variable with `setReinitialized(True)` and only set
`failure_effects`; the resting value is restored on repair).

## study.yaml spec

```yaml
failure_modes:
  - cls: ObjFMInst
    fm_name: fail_to_start
    targets: [generator]
    failure_cond: [[{attr: grid_up, value: false}]]
    failure_effects: {failed: true}
    failure_param: 0.3      # gamma in [0, 1] (validated)
    repair_param: 0.5       # mu
```

`ObjFMInstSpec` is part of the discriminated `FailureModeSpec` union
(`cod3s.specs.study_yaml`) and registered in the study runner — no
`register_fm_class` call needed.

## Interactive simulation (cod3s-isimu)

Each demand front surfaces the draw as a **pending inst** transition:
the fireable panel switches to the tree picker (branches `occ` /
`not_occ` with their probabilities) and the operator submits choices
atomically with `s`. The deterministic re-arm (single-branch inst
p=1) is auto-resolved by the engine and never prompts.

Walkthrough example: `examples/objfm_inst_demo/` (grid + backup
generator).

## Sequence monitoring

Only the `occ` branch of the draw is recorded: the success branch and
the re-arm transition are masked out of monitoring via PyCATSHOO's
`setMonitoredOutStateMask`, so Monte-Carlo traces stay comparable with
`ObjFMExp` ones (`occ` / `rep` events only) and grouping cardinality
is unaffected by solicitations that fail nothing. The masks survive
`monitorTransition` patterns — the study runner re-applies them after
monitoring is configured (`reapply_monitor_masks` hook).
