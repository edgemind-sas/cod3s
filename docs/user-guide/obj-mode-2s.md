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

All nine cells build with `behaviour="internal"`. Restrictions
(rejected with clear errors, liftable later): inst laws ×
`external`/`external_rep_indep`; inst on the **return** direction × CC
order > 1; trans-based effects on inst directions; inst laws in
self-hosted mode.

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
