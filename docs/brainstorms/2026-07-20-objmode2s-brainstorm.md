---
date: 2026-07-20
topic: objmode2s-generic-two-state-mode
---

# ObjMode2S — Generic Two-State Mode Primitive

## What We're Building

`ObjMode2S` is a generic two-state mode component with logical states `occ` / `not_occ`,
where **each direction** (`not_occ → occ` and `occ → not_occ`) can independently carry
any occurrence law among `exp`, `delay`, and `inst` (full 3×3 law matrix). It is intended
to become the **new standard engine** behind the current mode-like objects: the engine
vocabulary is strictly generic (`occ` / `not_occ`; no reference to failure/repair in the
implementation), and the existing classes are kept as thin backward-compatibility
façades configuring the engine:

- `ObjFMExp` → `ObjMode2S` with `exp` / `exp`
- `ObjFMDelay` → `ObjMode2S` with `delay` / `delay`
- `ObjFMInst` → `ObjMode2S` with `inst` / `exp`
- `ObjEvent` → `ObjMode2S` façade as well (in scope now)

Everything else is carried over unchanged: state-based (level clamp) and trans-based
(one-shot pulse) effects with their current validation rules, common-cause support
(per-order parameter vectors, 2^N−1 combination automata, `drop_inactive_automata`),
and the three behaviours (`internal`, `external`, `external_rep_indep`).

**Hard acceptance criterion:** every test currently passing for `ObjFM`, `ObjFMExp`,
`ObjFMDelay`, `ObjFMInst`, and `ObjEvent` must pass with `ObjMode2S` configured to
reproduce them. The façade architecture makes this hold **by construction**: existing
suites keep exercising the façades, which delegate to the engine.

## Why This Approach

Alternatives considered for the ObjFM* relationship: (a) sibling class with a sampled
parity suite (the `ObjDegMode` precedent), (b) sibling class with existing suites
parametrized to run against both, (c) rebase — `ObjMode2S` becomes the engine and
existing classes become façades. Option (c) was chosen: it is the only one where parity
is exhaustive and drift-proof, and it matches the ambition of making `ObjMode2S` the
standard rather than one more mode class. The extraction of `fm_wiring.py` (1.12.x) and
the `ObjDegMode` hardening/lock patterns (1.13.0) pave the way.

For the `inst` law, a strict 2-state automaton would be Zeno (inst fires by level, not
edge). The engine therefore keeps a **logical** 2-state contract and auto-inserts the
parking micro-state + `inst p=1` re-arm (the proven `ObjFMInst` mechanics) whenever a
direction carries an `inst` law, masked from sequence monitoring.

## Key Decisions

- **Full 3×3 law matrix**: `exp` / `delay` / `inst` freely combinable per direction.
  This opens new semantics (e.g. `inst` on the return edge = per-demand instantaneous
  recovery) that must be specified and locked, not just allowed.
- **Logical 2 states, auto parking for `inst`**: user contract and event grammar stay
  two-state; anti-Zeno parking micro-states (suffixed `_star`: `not_occ_star`,
  `occ_star`) are an engine implementation detail, masked from sequences (monitor-mask
  precedent from `ObjFMInst`).
- **Unified per-edge `inst` semantics (locked)**: a single rule for any `inst` law, on
  either direction — see "Unified inst semantics" below. On-entry probabilistic
  branching is NOT a separate mode: it is the degenerate case `cond ≡ True`.
- **Engine is failure-agnostic**: only `occ` / `not_occ` vocabulary in `ObjMode2S`
  (fields, states, transitions, docs). Failure/repair wording lives exclusively in the
  `ObjFM*` façades, which map `failure_*` → `occ_*` and `repair_*` → `not_occ_*`.
- **ObjFM*, ObjEvent kept as façades**: no deprecation in this chantier; they remain the
  documented backward-compatible entry points and the carriers of the existing tests.
- **ObjEvent in scope now**: including parity of the occ/not_occ cycle filtering in
  minimal sequences (`SequenceAnalyser` auto-discovery must recognize the new layout).
- **Flat symmetric API**: `occ_law`, `occ_cond`, `occ_effects`, `occ_effects_trans`,
  `occ_param` (per CC order) / same for `not_occ_*`. Laws declared through a typed
  discriminated union (`exp` / `delay` / `inst`), extending the `DegLaw` precedent.
- **Effects semantics unchanged**: state-based clamps and trans-based pulses keep their
  current wiring (`fm_wiring`) and their current validation rules (level+trans same-var
  rejection; CCF / `external_rep_indep` / inst-draw trans-effect restrictions carry over
  as-is — lifting them is out of scope).
- **CC support unchanged**: per-order parameter vectors on the `occ` direction,
  combination automata, `drop_inactive_automata`, factorized target names.
- **Wire format via `ObjFMGenericSpec`**: runner registry entry + generic spec transport
  (the `ObjDegMode` precedent); no dedicated pydantic spec class in this chantier.
- **`inst`/`inst` on both directions is allowed**: same-instant ping-pong (draw
  succeeds → arrival with the opposite condition already true → immediate return draw)
  continues with probability γ_occ·γ_ret per cycle, so it terminates almost surely as
  soon as one side is < 1. Construction rejects only the certain livelock (probability
  1 on both sides); a seeded MC test locks termination.
- **Engine-native parameter names = direction prefix + law field**: `occ_rate` (exp),
  `occ_time` (delay), `occ_prob` (inst) and `not_occ_rate` / `not_occ_time` /
  `not_occ_prob`; per-order CC suffixes unchanged (`__{k}_o_{N}`). Façades override
  with the historical names (`lambda`/`mu`, `ttf`/`ttr`, `gamma`).
- **Statistical locks for new combos**: one non-circular analytical lock (CTMC closed
  form on a mixed combo, e.g. exp/inst) + seeded MC on 2–3 representative combos
  (inst on the return direction, delay/inst, inst/inst termination); the remaining
  combos are locked deterministically via isimu sequences.
- **Delivered as one block**: engine + all façades (`ObjFMExp`/`Delay`/`Inst`,
  `ObjEvent`) validated and merged together in a single release — no intermediate
  merge milestones.

## Unified `inst` Semantics (locked 2026-07-20)

Vocabulary: a **rising edge** ("front montant") is the instant a condition switches
from false to true, as opposed to its **level** (the condition *being* true over a
duration). PyCATSHOO `inst` laws fire by level, so a naive 2-state automaton would
re-draw forever after a failed draw (Zeno). The engine mechanics below turn the
level-triggered law into **exactly one draw per rising edge of the composite guard**
"in the armed state AND direction condition true".

When a direction carries an `inst` law, its source logical state is split into an
**armed** micro-state and a **parked** micro-state suffixed `_star` (`not_occ_star`
when `inst` is on `not_occ → occ`, `occ_star` when it is on `occ → not_occ`):

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

Three rules, one per arrow:

1. **Draw**: as soon as the guard "armed state AND condition" is true, the draw fires —
   branch γ reaches the destination logical state, branch 1−γ reaches the `_star`
   parked micro-state.
2. **Parking**: no draw transition leaves the `_star` state; while the condition stays
   true the automaton waits there (anti-Zeno). Logically it is still in the source
   state.
3. **Re-arm**: when the condition falls back to false, an `inst p=1` transition
   (masked from sequence monitoring) returns to the armed micro-state.

Consequences, all locked by discussion:

- **One draw per demand**: a condition that stays true over an interval produces a
  single draw at its rising edge (scenario: grid down 10→12, one start attempt at 10).
- **Entry with condition already true draws immediately**: the guard is composite —
  arriving in the armed state while the condition already holds is a rising edge of
  the guard (scenario: repair completes while the demand still holds → the fresh
  equipment is re-solicited on the spot). This matches current `ObjFMInst` behaviour.
- **`cond ≡ True` degenerates to "immediately or never"**: one single draw at state
  entry, no re-arm ever — this is exactly on-entry probabilistic branching, hence no
  separate law variant is needed.
- **Symmetric on the return direction**: `inst` on `occ → not_occ` models *per-demand
  recovery* (e.g. `not_occ_cond` = "maintenance crew on site", γ_ret = probability the
  intervention succeeds; one crew visit = one attempt; failed attempt parks in
  `occ_star` until the crew leaves and a new one arrives). Same rule, mirrored.

## Open Questions

- **Semantics of the remaining mixed combos** (planning must specify them): `delay`
  mixed with `inst`; interaction of each combo with the three behaviours and with CC
  orders k>1 (per-order `prob` vector on the return direction?).
- **State-name defaults**: engine defaults to `occ` / `not_occ`; `ObjFM` façades must
  reproduce `occ` / `rep` (configurable state names, as today) so the event grammar of
  existing studies is untouched.
- **`ObjFMInst` internals migration**: `reapply_monitor_masks`, `_NEVER_MATCH_MASK`,
  gamma re-binding to parameter variables — these move into the engine; check the runner
  duck-typing hook still finds them.
- **Statistical locks for new combos**: which mixed combinations get MC and/or
  analytical locks (CTMC closed form where available), following the `ObjDegMode`
  precedent of at least one non-circular lock.
- **`ObjDegMode` convergence**: an `ObjMode2S` is conceptually an `ObjDegMode` with one
  degraded state (plus inst support). Do we eventually rebase one on the other? Out of
  scope here; note for a future chantier.

## Next Steps

→ `/workflows:plan` for implementation details (engine extraction strategy, façade
rewiring order, test gates per phase).
