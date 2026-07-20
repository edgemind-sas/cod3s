# Multi-State Degradation Modes (ObjDegMode)

`ObjDegMode` generalises the two-state `ObjFM*` failure modes into a
**linear degradation chain**: a healthy state followed by an ordered
list of degraded states (e.g. `sain -> O -> X1 -> X2`). Progression goes
through every state in order; the last state is absorbing except for
repair; every repair jumps straight back to the healthy state (full
renewal), with one law and one optional condition per departure state.

Typical use case: graded physical degradation (crack growth, wear)
where each level carries its own effects, progression rates and repair
policy — previously emulated with chains of ObjFM conditioned on each
other.

## Declaring a mode

The API is **state-centric**: each `DegState` groups everything about
one degraded state — its entry (law, local condition, one-shot pulse),
its stay (state effects) and its repair.

```python
import cod3s
from cod3s import DegState, ObjDegMode

ObjDegMode(
    fm_name="Fissure",
    targets=["R1", "R2"],
    occ_cond=[{"attr": "in_exploitation", "value": True}],  # global gate
    states=[
        DegState(
            "O",
            # First state: EXP ONLY. A list = lambda_k vector per common
            # cause order (len == number of targets, strict).
            occ_law={"cls": "exp", "rate": [0.15, 0.05]},
            rep_law={"cls": "exp", "rate": 0.4},
        ),
        DegState(
            "X1",
            occ_law={"cls": "exp", "rate": 0.08},
            effects={"in_service": False},          # state clamp
            occ_effects_trans={"alarm": True},      # one-shot pulse
            rep_law={"cls": "exp", "rate": 0.2},
            rep_cond=[{"attr": "crew_available", "value": True}],
        ),
        DegState(
            "X2",
            occ_law={"cls": "delay", "time": 20.0},
            effects={"in_service": False},
            rep_law={"cls": "delay", "time": 10.0},
        ),
    ],
)
```

Key rules (enforced at construction, fail-fast):

* the **first state's entry law is exponential only**. Deterministic
  delays are rejected there: two combinations eligible at the exact
  same date both fire in one PyCATSHOO batch without guard
  re-evaluation, so the common-cause entry relies on same-date ties
  having probability zero (true for exp, false for delay). Deeper
  progressions and repairs accept `exp` or `delay`;
* a `lambda_k` list must have **exactly one rate per common-cause
  order** (`len == len(targets)`); a scalar means "order 1 only". Use
  `0` to deactivate an order explicitly — there is no silent padding;
* `rep_law=None` (default) = no repair edge from that state. A mode
  with no repair at all is a valid **run-to-failure** model;
* state names are ASCII without `.` nor `__` (they appear in event
  names); each state declares its **full** effect set (no cumulative
  inheritance from previous states); the healthy state carries no
  effects;
* a variable cannot be driven by both a state clamp (`effects`) and a
  pulse (`occ/rep_effects_trans`) — the clamp would silently overwrite
  the pulse.

## Semantics

**Common cause on the first transition only.** The mode builds a
carrier component (`<targets>__<fm_name>`) hosting one trigger automaton
per active combination (2^N−1 for N targets). An order-k fire moves the
k targets of the combination from healthy to the first degraded state
**at the same simulated instant**. A combination is only fireable when
**all its targets are healthy** and the global `occ_cond` (AND the first
state's local condition) holds — the whole entry gating happens once, at
carrier fire time. Beyond the first state, progression and repair are
strictly individual.

**Conditions.** The global `occ_cond` gates the entry (carrier side) and
every deeper progression, never the repairs (each repair has its own
`rep_cond`). Conditions accept `bool`, a Python callable, or the
structured tree used by ObjFM (list of lists of
`{"attr", "value", "ope", "obj"?}` — outer OR, inner AND, resolved on
each target by default).

**Effects.** `effects` are level clamps re-applied while the state is
active (self-healing). When the state is left, the clamp simply stops:
on a bare variable nothing rewrites the value (it keeps the clamped
value in a continuous Monte-Carlo run, and falls back to its init value
after an isimu replay). A release pulse on the **same** variable is
rejected at construction (clamp/pulse overlap): derive the observable
from `<fm_name>_level`, or use a recomputed (flow) variable whose
fixpoint computation provides the release. `occ/rep_effects_trans`
pulses are for **distinct** notification variables (persistent gates).

**Interruptibility.** Transitions are interruptible (ObjFM default): a
`delay` progression whose guard drops and comes back **restarts from
zero** (exp is memoryless, delay is not) — mind blinking guards on
delay-based ageing.

**Level variable.** Each target exposes `<fm_name>_level`
(`t_int`, 0 = healthy ... K), maintained by the automaton — use it for
indicators (`add_indicator_var`) and inter-component conditions
(`{"attr": "Fissure_level", "ope": ">=", "value": 2}`).

## Event grammar (sequences)

| Event | Meaning |
|---|---|
| `<carrier>.occ_<state1>__cc_<i>_<j>` | CC fire; order = number of 1-based, `_`-separated indices |
| `<target>.<fm_name>__occ_<state>` | individual progression (arrival state) |
| `<target>.<fm_name>__rep_<state>` | repair (departure state) |

The carrier re-arm edge is silenced with a monitor mask and never
appears in sequences. `reapply_monitor_masks()` is re-invoked by the
study runner after `monitorTransition` (same hook as `ObjFMInst`).

## study.yaml wire format

`ObjDegMode` is registered in the study-runner failure-mode registry and
travels through `ObjFMGenericSpec` (`states` and `occ_cond` are carried
as extra fields — no dedicated spec class needed):

```yaml
failure_modes:
  - cls: ObjDegMode
    fm_name: Fissure
    targets: [R1, R2]
    occ_cond:
      - attr: in_exploitation
        value: true
    states:
      - name: O
        occ_law: {cls: exp, rate: [0.15, 0.05]}
        rep_law: {cls: exp, rate: 0.4}
      - name: X1
        occ_law: {cls: exp, rate: 0.08}
        effects: {in_service: false}
        rep_law: {cls: exp, rate: 0.2}
```

Wire notes:

* conditions must be structured trees (callables are Python-API only);
* `failure_cond` is accepted as a wire alias of `occ_cond`;
* two-state `ObjFM` fields (`failure_effects`, `repair_state`, ...) are
  rejected with a clear error when set to anything but their defaults —
  never silently ignored;
* the runner **swallows construction errors** (log + continue): check
  the count returned by `add_failure_modes` when driving it directly.

Parameters are exposed as carrier variables for runtime overrides:
`lambda_<state1>__<k>_o_<N>` (per CC order; bare `lambda_<state1>` for a
single target), then `lambda_/ttf_<state>` per progression and
`mu_/ttr_<state>` per repair.

!!! warning "Overrides and deactivated CC orders"
    With `drop_inactive_automata` (default `true`), a CC order declared
    with rate `0` builds **no combination automaton**: overriding its
    `lambda_<state1>__<k>_o_<N>` variable at runtime is then a silent
    no-op. For sensitivity studies over initially-zero orders, set
    `drop_inactive_automata: false` in the spec.

!!! warning "Sequence filtering (known limitation)"
    `filter_objfm_in_sequences` / the `SequenceAnalyser` auto-discovery
    only collapse `ObjFM` occ/rep cycles: `ObjDegMode` degradation and
    repair transients are **not** collapsed yet. A repairable mode under
    wildcard monitoring will inflate the sequence set with reversible
    transients — restrict `monitor_patterns`, or post-process, until the
    multi-state cycle filter lands (downstream chantier).

## Full example

See `examples/objdegmode_demo/objdegmode_demo.py` (two rails, graded
crack `O -> X1 -> X2` with an order-2 common cause and per-level
repairs).
