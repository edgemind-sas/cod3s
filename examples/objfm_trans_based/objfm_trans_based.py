"""Trans-based (one-shot edge) ObjFM effects, in pure cod3s.

This example demonstrates ``mode="trans_based"`` ObjFM effects: an effect
applied **once, at the instant a transition fires** (an edge callback),
as opposed to the state-clamped ``failure_effects`` that are re-asserted on
every fixpoint pass while the failure state is active (a level).

State (level) vs edge (pulse)
-----------------------------

============================  ==========================================
``failure_effects`` (level)   maintained while the occ state is active;
                              re-applied every step; the target variable
                              is usually ``setReinitialized(True)`` so it
                              springs back to its resting value on repair.
``failure_effects_trans``     written exactly once, on the rising edge of
(pulse)                       the occ transition; nothing re-asserts it
                              afterwards.
============================  ==========================================

The persistent gate
-------------------

A pulse only "sticks" on a **persistent** variable: one created with
``setReinitialized(False)`` so PyCATSHOO does *not* spring it back between
steps. The pulse writes it once; it holds that value intra-sequence until
another edge changes it. (The universal Monte-Carlo reset still clears it
between sequences — see the no-leak assertion in ``test_example.py``.)

Both-pulse
----------

Pairing a SET on the occ transition with a CLEAR on the rep transition
(``failure_effects_trans`` + ``repair_effects_trans``) keeps a persistent
gate **in phase with the failure state** without ever maintaining a level
on it. This matters: a maintained opposite-level clamp on the same variable
would write-war on every fixpoint pass (and cod3s now rejects declaring a
level and a pulse on the *same* variable, precisely to avoid the pulse being
silently overwritten). So a gate is driven by pulses only; a physical
level is clamped on a *distinct* variable.

The two behaviours shown here
-----------------------------

**INTERNAL** (``Equipment`` fails on its own automaton)
    A single ``Equipment`` carries a physical level ``degraded`` (clamped
    True while its own failure mode is active, auto-restored on repair) and
    a persistent gate ``fault_detected`` armed by the both-pulse of the
    *same* failure mode. Level and pulse ride the same automaton but touch
    distinct variables, so they coexist cleanly. ``fault_detected`` arms on
    the occ edge, **persists** across steps, and clears on the rep edge.

**EXTERNAL** (a separate Detector cross-writes the Equipment)
    An ``external`` ObjFM does not fail its target's own automaton: it lives
    on its **own carrier component**, auto-created by cod3s as
    ``Equipment__detector`` (the carrier holds the occ / rep automaton and
    is a genuinely separate component from ``Equipment``). Here it plays the
    role of a **Detector**. Its both-pulse writes a persistent gate
    ``inspection_gate`` on the *target* ``Equipment`` — the write crosses
    from one component to another. The detector's occ arms the Equipment's
    gate, the gate persists, and the detector's rep clears it. The gate is a
    variable **distinct** from the internal level ``degraded`` and from the
    internal gate ``fault_detected``: no level/pulse overlap, so the guard
    does not fire.

Everything below is pure cod3s (``PycComponent`` + ``ObjFMDelay``); no
muscadet dependency. Deterministic ``delay`` laws make the timeline exact so
the arm / persist / clear cycle is legible in the printed trace.

How to run
----------

::

    .venv/bin/python examples/objfm_trans_based/objfm_trans_based.py

What you should observe (deterministic timeline)
------------------------------------------------

Internal failure mode: ttf=10, ttr=8  → occ at 10 / 28, rep at 18 / 36.
Detector (external):   ttf=15, ttr=7  → occ at 15 / 37, rep at 22 / 44.

- ``fault_detected`` (internal pulse) arms at 10, **persists** through 12 /
  14 / 16, clears at 18; re-arms at 28.
- ``inspection_gate`` (external pulse) arms at 15, **persists** through 16 /
  20 (note: still armed at 20, *after* the internal gate already cleared at
  18 — the two gates are independent), clears at 22; re-arms at 37.
- Each persistent gate tracks its automaton's occ state exactly, with no
  level clamp on the gate itself — that is the both-pulse doing its job.
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem

# Deterministic failure / repair delays (arbitrary time units).
INTERNAL_TTF = 10  # Equipment fails on its own after 10.
INTERNAL_TTR = 8  # ... and is repaired 8 later.
DETECTOR_TTF = 15  # Detector trips after 15.
DETECTOR_TTR = 7  # ... and resets 7 later.

# Schedule of observation instants for the demo trace. Chosen to land the
# samples inside / outside each occ interval so persistence is visible.
DEMO_SCHEDULE = [0, 12, 14, 16, 20, 24, 30, 38, 40]


class Equipment(cod3s.PycComponent):
    """A piece of equipment with one physical level and two persistent gates.

    - ``degraded``: reinitialised (resting False) physical state — target of
      a *state-based* (level) effect, clamped True while the equipment's own
      failure mode is active, auto-restored to False on repair.
    - ``fault_detected``: persistent (``setReinitialized(False)``) gate —
      target of the internal failure mode's *both-pulse* (SET on occ, CLEAR
      on rep). Intra-sequence memory of "this equipment has an active fault".
    - ``inspection_gate``: persistent gate — target of the *external*
      Detector's both-pulse. Distinct from the two variables above, so no
      level/pulse overlap.
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        # Physical level (state-clamped, springs back on repair).
        self.degraded = self.addVariable("degraded", Pyc.TVarType.t_bool, False)
        self.degraded.setReinitialized(True)
        # Persistent gate armed by the equipment's OWN failure mode (internal).
        self.fault_detected = self.addVariable(
            "fault_detected", Pyc.TVarType.t_bool, False
        )
        self.fault_detected.setReinitialized(False)
        # Persistent gate armed by a SEPARATE Detector (external cross-write).
        self.inspection_gate = self.addVariable(
            "inspection_gate", Pyc.TVarType.t_bool, False
        )
        self.inspection_gate.setReinitialized(False)


def build_system(name: str = "ObjFMTransBasedDemo") -> PycSystem:
    """Build the two-behaviour trans-based showcase.

    Returns a ``PycSystem`` with:

    - one ``Equipment`` component;
    - an **internal** ``ObjFMDelay`` on the Equipment: a physical level clamp
      on ``degraded`` plus a both-pulse on the persistent gate
      ``fault_detected`` (same automaton, distinct variables);
    - an **external** ``ObjFMDelay`` (the Detector) targeting the Equipment:
      its carrier ``Equipment__detector`` is a separate component whose
      both-pulse cross-writes the Equipment's persistent gate
      ``inspection_gate``.
    """
    system = PycSystem(name=name)
    system.add_component(name="equipment", cls="Equipment")

    # INTERNAL: the equipment fails on its own automaton. Level clamp on the
    # physical `degraded`, both-pulse on the persistent `fault_detected` gate.
    system.add_component(
        cls="ObjFMDelay",
        fm_name="degradation",
        targets=["equipment"],
        behaviour="internal",
        failure_param=INTERNAL_TTF,
        repair_param=INTERNAL_TTR,
        failure_effects={"degraded": True},  # level: clamped while failed
        failure_effects_trans={"fault_detected": True},  # pulse: SET on occ
        repair_effects_trans={"fault_detected": False},  # pulse: CLEAR on rep
    )

    # EXTERNAL: a separate Detector (carrier `equipment__detector`) whose
    # both-pulse cross-writes the Equipment's `inspection_gate`. Pure pulse:
    # no level effect, so no level/pulse overlap with the internal mode.
    system.add_component(
        cls="ObjFMDelay",
        fm_name="detector",
        targets=["equipment"],
        behaviour="external",
        failure_param=DETECTOR_TTF,
        repair_param=DETECTOR_TTR,
        failure_effects_trans={"inspection_gate": True},  # pulse: SET on occ
        repair_effects_trans={"inspection_gate": False},  # pulse: CLEAR on rep
    )

    return system


def _series(indicator):
    """('instant' list, 'values' list) from a returned indicator object."""
    return (
        indicator.values["instant"].to_list(),
        indicator.values["values"].to_list(),
    )


def run_trace(schedule=None, seed: int = 42):
    """Run one deterministic sequence and return the aligned indicator trace.

    Returns ``(instants, columns)`` where ``columns`` is a dict mapping a
    human column label to its per-instant value list (0.0 / 1.0).
    """
    if schedule is None:
        schedule = DEMO_SCHEDULE

    system = build_system()

    # Automaton occ states (internal on the Equipment, external on the carrier).
    int_occ = system.add_indicator_state(
        component="equipment__degradation", state="occ", stats=["mean"], name="int_occ"
    )[0]
    det_occ = system.add_indicator_state(
        component="equipment__detector", state="occ", stats=["mean"], name="det_occ"
    )[0]
    # Variables (level + the two persistent gates), all on the Equipment.
    degraded = system.add_indicator_var(
        component="equipment", var="degraded", stats=["mean"], name="degraded"
    )[0]
    fault = system.add_indicator_var(
        component="equipment", var="fault_detected", stats=["mean"], name="fault"
    )[0]
    inspection = system.add_indicator_var(
        component="equipment", var="inspection_gate", stats=["mean"], name="inspection"
    )[0]

    system.simulate(PycMCSimulationParam(nb_runs=1, schedule=schedule, seed=seed))

    instants, _ = _series(int_occ)
    columns = {
        "internal.occ": _series(int_occ)[1],
        "degraded (level)": _series(degraded)[1],
        "fault_detected (pulse)": _series(fault)[1],
        "detector.occ": _series(det_occ)[1],
        "inspection_gate (pulse)": _series(inspection)[1],
    }
    return instants, columns


def main() -> int:
    instants, columns = run_trace()

    labels = list(columns.keys())
    print("=" * 78)
    print("Trans-based ObjFM effects — internal both-pulse + external cross-write")
    print("=" * 78)
    print(
        f"  internal mode : ttf={INTERNAL_TTF}, ttr={INTERNAL_TTR} "
        f"→ occ at 10 / 28, rep at 18 / 36"
    )
    print(
        f"  detector (ext): ttf={DETECTOR_TTF}, ttr={DETECTOR_TTR} "
        f"→ occ at 15 / 37, rep at 22 / 44"
    )
    print()

    # Header.
    head = f"{'t':>5}  " + "  ".join(f"{lab:>24}" for lab in labels)
    print(head)
    print("-" * len(head))
    for i, t in enumerate(instants):
        cells = "  ".join(f"{('ON' if columns[lab][i] else '.'):>24}" for lab in labels)
        print(f"{t:>5.0f}  {cells}")

    print()
    print("What to read in the table above:")
    print("  - fault_detected (internal pulse) arms at the internal occ (10),")
    print("    stays ON through t=12/14/16 (PERSISTENCE), clears at rep (18),")
    print("    re-arms at the next occ (28).")
    print("  - inspection_gate (external pulse) arms at the detector occ (15),")
    print("    stays ON through t=16/20 — still ON at 20 though the internal")
    print("    gate already cleared at 18 (the two gates are INDEPENDENT) —")
    print("    clears at the detector rep (22), re-arms at 37.")
    print("  - each persistent gate matches its automaton's occ column exactly:")
    print("    the both-pulse keeps the gate in phase with the failure state")
    print("    without any level clamp on the gate itself.")
    print("  - degraded (a level) tracks internal.occ too, but by re-assertion")
    print("    every step, not by an edge — the distinction the example is about.")

    cod3s.terminate_session()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
