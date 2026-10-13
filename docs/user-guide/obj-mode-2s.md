# Generic Two-State Modes (ObjMode2S)

`ObjMode2S` is the generic two-state mode engine of COD3S: a component
with the logical states `occ` / `not_occ` where **each direction
independently carries an `exp`, `delay`, or `inst` law** (full 3×3
matrix). It is the engine behind the historical classes — `ObjFM`,
`ObjFMExp`, `ObjFMDelay`, `ObjFMInst`, and `ObjEvent` are thin
backward-compatible façades over it — and the recommended API for new
mixed-law models (exponential failure with deterministic repair,
per-demand recovery, probabilistic flips…).

Vocabulary (edge vs state): `occ_law` / `occ_cond` describe the **edge**
entering `occ` (`not_occ → occ`); `occ_effects` is the level clamp
maintained **while** in `occ`. The `not_occ_*` fields mirror this for
the return edge / resting state.

## Declaring a mode

```python
import cod3s
from cod3s import ObjMode2S

ObjMode2S(
    mode_name="wear",
    targets=["pump1"],
    occ_law={"cls": "exp", "rate": 1e-3},      # failure: exponential
    not_occ_law={"cls": "delay", "time": 8.0}, # repair: deterministic
    occ_effects={"working": False},
)
```

Laws are typed specs discriminated on `cls`:

| law | parameter | semantics |
|---|---|---|
| `exp` | `rate` | exponential occurrence (rate 0 = inactive, dropped with `drop_inactive_automata`) |
| `delay` | `time` | deterministic delay (time 0 is a valid delay) |
| `inst` | `prob` in [0, 1] | one Bernoulli draw per rising edge of the guard (see below) |

Each parameter accepts a scalar (single target) or a per-CC-order
vector (strict length == number of targets, explicit `0` for inactive
orders — no silent padding). Parameter variables are created as
`occ_rate` / `occ_time` / `occ_prob` and `not_occ_*` (+ the usual
`__{order}_o_{order_max}` CC suffix) and the laws are bound to them, so
runtime overrides via `mode.variable(...).setValue(...)` work.

Common-cause combinations, the three behaviours (`internal`,
`external`, `external_rep_indep`), state-based level clamps and
trans-based one-shot pulses all carry over from the ObjFM machinery
unchanged.

## The 3×3 matrix

| occ \ return | `exp` | `delay` | `inst` |
|---|---|---|---|
| `exp` | ✔ (≡ ObjFMExp) | ✔ | ✔ per-demand recovery |
| `delay` | ✔ | ✔ (≡ ObjFMDelay) | ✔ |
| `inst` | ✔ (≡ ObjFMInst) | ✔ | ✔ (livelock-guarded) |

All nine cells build with `behaviour="internal"`. Since 1.14.1 inst
laws also build with `external`/`external_rep_indep`: the external
condition machinery composes before the inst routing, exactly as the
`ObjFMInst` façade has always exercised it — each combination automaton
draws independently on a shared demand front. Remaining restrictions
(rejected with clear errors, liftable later): inst on the **return**
direction × CC order > 1; inst laws in self-hosted mode. Trans-based
effects on inst directions are accepted since 1.21.0 (see
[Held and one-shot effects](#held-and-one-shot-effects)).

## Unified `inst` semantics

A **rising edge** is the instant a condition switches from false to
true, as opposed to its **level** (being true over a duration).
PyCATSHOO `inst` laws fire by level, so the engine builds anti-Zeno
machinery that yields **exactly one draw per rising edge of the
composite guard** "armed state AND direction condition":

```
                      DRAW — inst law, guard: occ_cond (level)
                      │
   ┌───────────┐      ├── branch prob γ ────────────────►  ┌───────┐
   │  not_occ  │──────┤                                    │  occ  │
   │  (armed)  │      └── branch prob 1−γ ──┐              └───┬───┘
   └───────────┘                            ▼                  │
         ▲                           ┌──────────────┐          │  return law
         │      RE-ARM               │ not_occ_star │          │  (exp, delay
         └── inst p=1 ───────────────│   (parked)   │          │   or inst)
             guard: NOT occ_cond     └──────────────┘          ▼
             [masked from sequences]                    back to not_occ (armed)
```

1. **Draw**: as soon as the guard "armed state AND condition" holds,
   the draw fires — branch γ reaches the destination state, branch 1−γ
   reaches the `_star` parked micro-state.
2. **Parking**: no draw leaves the parked state; while the condition
   stays true the automaton waits there (anti-Zeno). Logically it is
   still in the source state — its level clamps stay applied.
3. **Re-arm**: when the condition falls, an `inst p=1` transition
   (masked from sequence monitoring) returns to the armed state.

Consequences:

- **One draw per demand**: a condition held over an interval produces a
  single draw at its rising edge.
- **Entry with the condition already true draws immediately** (the
  composite guard rises): a repair completing while the demand holds
  re-solicits the fresh equipment on the spot.
- **`cond ≡ True` degenerates to "immediately or never"**: one draw at
  state entry, and a failed draw parks forever (the condition never
  falls, no re-arm). This is on-entry probabilistic branching — no
  separate law variant needed.
- **Symmetric on the return direction**: `inst` on `occ → not_occ`
  models *per-demand recovery* — e.g. `not_occ_cond` = "maintenance
  crew on site", `prob` = probability the intervention succeeds; one
  crew visit = one attempt; a failed attempt parks in `occ_star` (still
  logically failed) until the crew leaves and a new one arrives. See
  `examples/objmode2s_demo/`.

`inst`/`inst` on both directions is allowed: a same-instant ping-pong
chain continues with probability `p_occ·p_ret` per cycle and terminates
almost surely. Only the certain livelock (probability 1 on both sides
with trivially-true conditions) is rejected at construction; prob 1 on
both sides with real conditions emits a warning.

### Certain draws (probability exactly 1)

A draw whose probability is exactly 1 at construction is built as a
**single-branch** inst to its destination: no parked state, no re-arm,
no parameter bound to the law. PyCATSHOO refuses a two-branch inst whose
parameter is 1, at start and at any later step (`Il y a plus d'un
paramètre égal à 1`), so before cod3s 1.17.1 such a mode could not be
simulated at all. The outcome is the one the two-branch form describes,
since its parked branch could never land, and the per-demand semantics
hold: returning to the armed state while the condition holds is itself
a rising edge, so the next demand draws (and lands) again.

Exactly 1, not "close to 1": a draw at 0.9999 keeps its parked branch.
Each common-cause order decides for itself (`prob: [1.0, 0.5]` gives a
certain order 1 and a random order 2).

The structure is fixed at construction. A runtime
`FailureModeParamOverride` that would move a draw across probability 1
(certain → anything else, or random → 1) is refused by name by the study
runner; set the probability in the mode definition instead.

## Size of a mode before building it

`ObjMode2S.footprint(n_targets, ...)` returns the automata and
transitions the constructor would create, without creating anything. It
takes the constructor's own law arguments (`occ_law`, `not_occ_law`,
optional `occ_param` / `not_occ_param`, `behaviour`,
`drop_inactive_automata`) with the number of targets in place of their
names. Use it to bound or announce the size of a model before
construction rather than re-deriving the count.

```python
fp = ObjMode2S.footprint(
    6,
    behaviour="external",
    occ_law={"cls": "exp", "rate": [1e-3, None, None, None, None, None]},
    not_occ_law={"cls": "exp", "rate": [0.1, None, None, None, None, None]},
)
fp.transitions          # 24: 6 combinations x 2, plus 6 mirrors x 2
fp.order(1).transitions  # 12
fp.mirror_transitions    # 12
```

The rules it applies, for `n` targets:

| Built | Count |
|---|---|
| automata of a kept order `k` | `C(n, k)`, one per combination |
| transitions per combination | 2, plus 1 re-arm per `inst` direction whose probability is not exactly 1 |
| dropped order (both directions inactive, `drop_inactive_automata` on) | 0 |
| mirror automata (`external`, `external_rep_indep`) | `n`, 2 transitions each |

It covers the native path (both laws given as `ModeLaw` specs), not the
self-hosted mode nor hook-driven façades, and it does not repeat the
constructor's refusals: count only a mode the constructor accepts.
`tests/pyc_obj/obj_mode2s/test_mode2s_footprint.py` compares it with
systems actually built, for the three behaviours and the three laws.

## Held and one-shot effects

A mode writes its targets in two ways:

* **held** effects (`occ_effects` / `not_occ_effects`): a level clamp
  re-applied on every fixpoint pass while the state is active;
* **one-shot** effects (`occ_effects_trans` / `not_occ_effects_trans`):
  written once, at the instant the target enters the state.

A variable may be held on one face and pulsed on the **other**. The
typical case is a clamp handed back at repair, on a variable that does
not reinitialise on its own:

```python
ObjMode2S(
    mode_name="cell",
    targets=["battery"],
    behaviour="external",
    occ_law={"cls": "delay", "time": 1.0},
    not_occ_law={"cls": "delay", "time": 2.0},
    occ_effects={"serve_rate": 0.0},             # held while failed
    not_occ_effects_trans={"serve_rate": 40.0},  # handed back once
)
```

Several such modes can clamp the same variable: the clamp stays while any
of them is in `occ`, and the nominal value comes back when the last one is
repaired (an earlier repair pulse is overwritten by the clamps still
held). The same model with a **held** repair effect never converges: the
held effects of a mode in `occ` and of a mode in `not_occ` fight within
one instant. Two modes holding **different** clamped values at the same
time are ill-posed whatever the repair effect.

A variable held and pulsed on the **same** face is refused at
construction: the clamp would overwrite the pulse.

In `external` and `external_rep_indep` the held effects live on the
mirror automaton each target hosts (`<mode>__occ` / `<mode>__not_occ`),
and so do the one-shot effects: a pulse fires when the target itself
changes state, after the mode automaton in `external` (`delay(0)`
follow), on the target's own repair in `external_rep_indep`. Before
1.20.0 the pulses were wired on the mode automaton, so a repair pulse
fired while the target still held its clamp and was lost, and
`external_rep_indep` refused one-shot effects.

### Several targets

Since 1.21.0 the validation counts how many built automata write a given
target's variable, not the number of targets:

* `external` / `external_rep_indep`: one writer per target, the mirror,
  which follows the OR of the combinations covering it. Every shape
  accepted for one target is accepted for several, whatever the CC
  orders.
* `internal`: each kept CC order `k` puts `C(n-1, k-1)` combination
  automata on every target. Order 1 alone (one mode applied to several
  instances) or order `n` alone is the single-target case. When the
  combinations overlap (two kept orders, or one order strictly between 1
  and `n`; an order is kept unless both its laws are inactive and
  `drop_inactive_automata` is on), the held effects are applied once per
  target, over the combinations covering it: the `occ_effects` values
  while at least one of them is in `occ`, the `not_occ_effects` values
  only while all of them are at rest. That is the single-target
  semantics, and the OR the `external` mirror follows. The hand-back
  pair above still converges, with the same reading: a repaired
  combination's pulse is overwritten by the clamp while another
  combination covering the target is still in `occ`, and the last repair
  hands the value back. One shape is refused, naming the variables:

| shape on one variable | why it is ill-posed |
|---|---|
| pulse on both faces (persistent-gate both-pulse) | a combination's repair clears it while another one is still in `occ` |

Before 1.23.0 each combination clamped the target on its own, so a
combination at rest kept asserting `not_occ_effects` on a target that
another combination had put in `occ`. A variable held on both faces with
different values never settled (cod3s#4, refused in 1.21.0 and 1.22.0),
a variable held only at rest stayed held instead of falling back to its
reinitialised value (cod3s#10), and a pulse entering `occ` on a variable
held at rest was overwritten (refused in 1.21.0 and 1.22.0). All three
now behave as with a single target.

The mode publishes that decision as `shared_target_clamps`, set before any
combination is built. A subclass that resolves its held effects itself
(`muscadet.ObjFailureMode` resolves flow-name patterns in
`_build_fm_automaton`) reads it there, hands the build hooks no held record
when it is true, and returns the records from
`_shared_target_clamp_effects(target_comp, target_name)` instead, so its
targets are clamped once over their covering combinations too.

### `inst` directions

Since 1.21.0 one-shot effects are accepted on a mode with an `inst`
direction, `ObjFMInst` included. A pulse on a timed edge (the repair of
a demand failure, typically) fires at each crossing. A pulse on a draw
edge fires only when the draw lands in the destination state: a failed
draw parks in the `_star` micro-state without a pulse, and the re-arm
transitions carry none, since the mode does not change logical state.

## Façade ↔ engine mapping

The historical classes keep their exact API; under the hood:

| façade | engine |
|---|---|
| `fm_name` | `mode_name` (`fm_name` kept as read alias) |
| `failure_state` / `repair_state` (`"occ"`/`"rep"`) | `occ_state` / `not_occ_state` (`"occ"`/`"not_occ"`) |
| `failure_cond` / `repair_cond` | `occ_cond` / `not_occ_cond` |
| `failure_effects(_trans)` / `repair_effects(_trans)` | `occ_effects(_trans)` / `not_occ_effects(_trans)` |
| `lambda` / `mu`, `ttf` / `ttr`, `gamma` variables | `occ_rate` / `not_occ_rate`, `occ_time` / `not_occ_time`, `occ_prob` |
| `set_occ_law_failure`, `get_failure_cond`, … hooks | `_direction_law_bkd`, `_direction_cond`, … template hooks |

!!! warning "Behaviour change: ObjFMInst repair effects during parking"
    A logical state's level clamps now also apply in its parked
    micro-state, since the mode is logically still in that state. For
    `ObjFMInst` this is a change: before the engine extraction, its
    `repair_effects` were clamped on the armed `rep` state only, not
    while parked in `not_occ` after a failed draw. A model that declares
    non-empty `repair_effects` on an `ObjFMInst` **and** lets another
    automaton write the same target variable will now see that write
    undone during the parked window. The documented convention is to
    leave `repair_effects` empty and rely on reinitialised variables
    (see CLAUDE.md), which keeps models unaffected.

!!! warning "ObjFMInst's `not_occ` is a *parked* state"
    In `ObjFMInst`, the state literally named `not_occ` is the
    **parked** micro-state of the occ direction (armed state = `rep`) —
    frozen historical grammar. Engine-native modes name the same thing
    `<not_occ_state>_star`, and their logical resting state `not_occ`.
    Do not read one grammar with the other's glasses.

## study.yaml wire format

`ObjMode2S` travels through the generic failure-mode spec
(`ObjFMGenericSpec`): `occ_law` / `not_occ_law` (and any `occ_*` /
`not_occ_*` field) ride as extra fields; `fm_name` and `failure_cond`
are accepted as wire aliases of `mode_name` / `occ_cond`:

```yaml
failure_modes:
  - cls: ObjMode2S
    fm_name: wear
    targets: [pump1]
    occ_law: {cls: exp, rate: 1.0e-3}
    not_occ_law: {cls: delay, time: 8.0}
    occ_effects: {working: false}
```

## Silent wrong-model channels (caveats)

All the known ways a study can run with a silently wrong model, in one
place:

- **The runner swallows construction errors** on the wire path (log +
  continue): a failed mode = a missing mode = optimistic figures. Set
  `simulation.strict_failure_modes: true` (recommended) to abort
  instead, or assert the count returned by `add_failure_modes`.
- **`drop_inactive_automata` runtime no-op**: a CC order declared with
  rate 0 builds no automaton — overriding its parameter variable at
  runtime changes nothing. Declare `drop_inactive_automata: false` for
  sensitivity studies over initially-zero orders.
- **inst/inst runtime override to prob 1/1**: the construction guard
  cannot see runtime overrides; a state where both conditions hold then
  livelocks — the symptom is a `stepForward` hang. Near 1/1, the
  same-instant chain length grows as `1/(1 − p_occ·p_ret)`.
- **`add_targets`** builds its target from positional fields — prefer
  the documented spec shapes.

## Structured conditions

`occ_cond` / `not_occ_cond` accept a bool, a Python callable (Python
API only), or a structured attr tree (wire-friendly) resolved per
target and ANDed across targets — the historical ObjFM shapes. String
condition names are rejected (never silently truthy). Self-hosted
modes (`targets=None`, the ObjEvent substrate) accept bool/callable
only.
