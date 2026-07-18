"""Non-regression tests for the ``objfm_trans_based`` example.

Exercises ``build_system`` end-to-end and asserts the both-pulse behaviour
for BOTH ObjFM behaviours the example shows:

- INTERNAL: the persistent gate ``fault_detected`` arms on the occ edge,
  persists across steps, clears on the rep edge, on the equipment's own
  automaton (level clamp on ``degraded`` coexisting on a distinct variable).
- EXTERNAL: the persistent gate ``inspection_gate`` is cross-written by a
  separate Detector carrier component, same both-pulse, across components.

Plus: persistence (survives intra-sequence), independence of the two gates,
the cross-component write (carrier holds no gate), and MC no-leak (the
persistent gate is reset between sequences).
"""

import pytest

import cod3s
from cod3s.pycatshoo.system import PycMCSimulationParam

from objfm_trans_based import DEMO_SCHEDULE, build_system, run_trace


@pytest.fixture(autouse=True)
def _release_pycatshoo_singleton_per_test():
    """PyCATSHOO is a process-level singleton — release it after each test."""
    yield
    cod3s.terminate_session()


def _series(indicator):
    return (
        indicator.values["instant"].to_list(),
        indicator.values["values"].to_list(),
    )


def test_deterministic_trace_matches_expected():
    """The whole deterministic timeline matches the documented trace.

    Schedule [0, 12, 14, 16, 20, 24, 30, 38, 40] with internal ttf=10/ttr=8
    (occ 10/28, rep 18/36) and detector ttf=15/ttr=7 (occ 15/37, rep 22/44).
    """
    instants, columns = run_trace(schedule=DEMO_SCHEDULE, seed=42)

    assert instants == [0.0, 12.0, 14.0, 16.0, 20.0, 24.0, 30.0, 38.0, 40.0]

    # Internal automaton occ + its two same-automaton effects (level + pulse).
    assert columns["internal.occ"] == [0, 1, 1, 1, 0, 0, 1, 0, 0]
    assert columns["degraded (level)"] == [0, 1, 1, 1, 0, 0, 1, 0, 0]
    assert columns["fault_detected (pulse)"] == [0, 1, 1, 1, 0, 0, 1, 0, 0]

    # External Detector automaton occ + the cross-written gate on the target.
    assert columns["detector.occ"] == [0, 0, 0, 1, 1, 0, 0, 1, 1]
    assert columns["inspection_gate (pulse)"] == [0, 0, 0, 1, 1, 0, 0, 1, 1]


def test_internal_both_pulse_arms_persists_clears():
    """Internal pulse: SET on occ, PERSISTS across steps, CLEAR on rep."""
    instants, columns = run_trace(schedule=[0, 12, 14, 16, 20], seed=42)
    fault = columns["fault_detected (pulse)"]

    # t=0 rest; occ at 10 arms it; it holds across 12 / 14 / 16 (persistence)
    # without being re-written between steps; rep at 18 clears it by t=20.
    assert fault == [0, 1, 1, 1, 0]
    # Persistence: three consecutive armed samples strictly between occ and rep.
    assert fault[1] == fault[2] == fault[3] == 1
    # Both-pulse keeps the gate exactly in phase with the occ state (no level).
    assert fault == columns["internal.occ"]


def test_external_both_pulse_crosses_components():
    """External pulse: a separate Detector carrier writes the target's gate.

    The occ / rep automaton lives on the auto-created carrier
    ``equipment__detector``; the both-pulse writes ``inspection_gate`` on the
    *target* ``equipment``. The carrier itself carries no such gate — proving
    the write crosses from one component to another.
    """
    system = build_system()

    # Structural: the gate lives on the target, not on the Detector carrier.
    carrier_vars = {
        v.basename() for v in system.comp["equipment__detector"].variables()
    }
    target_vars = {v.basename() for v in system.comp["equipment"].variables()}
    assert "inspection_gate" not in carrier_vars
    assert "inspection_gate" in target_vars

    det_occ = system.add_indicator_state(
        component="equipment__detector", state="occ", stats=["mean"], name="det_occ"
    )[0]
    gate = system.add_indicator_var(
        component="equipment", var="inspection_gate", stats=["mean"], name="gate"
    )[0]

    system.simulate(
        PycMCSimulationParam(nb_runs=1, schedule=[0, 12, 16, 20, 24], seed=42)
    )

    _, det_occ_vals = _series(det_occ)
    _, gate_vals = _series(gate)

    # Detector occ at 15, rep at 22 → occ interval covers 16 / 20.
    assert det_occ_vals == [0, 0, 1, 1, 0]
    # Cross-component both-pulse: gate armed on detector occ, persists to 20,
    # cleared by the detector rep at 22 → 0 at t=24. Tracks the carrier occ.
    assert gate_vals == [0, 0, 1, 1, 0]
    assert gate_vals == det_occ_vals


def test_two_gates_are_independent():
    """The internal and external gates move on their own schedules.

    At t=20 the internal gate has already cleared (internal rep at 18) while
    the external gate is still armed (detector rep only at 22) — proof the two
    persistent gates are driven independently.
    """
    instants, columns = run_trace(schedule=[0, 16, 20], seed=42)
    fault = columns["fault_detected (pulse)"]
    inspection = columns["inspection_gate (pulse)"]

    idx20 = instants.index(20.0)
    assert fault[idx20] == 0  # internal already cleared (rep at 18)
    assert inspection[idx20] == 1  # external still armed (rep at 22)


def test_mc_no_leak_between_sequences():
    """Persistent gates (setReinitialized(False)) are reset between sequences.

    Over many identical deterministic sequences, both gates get armed during
    each run (mean == 1.0 at an in-occ instant), yet the mean at t=0 is 0.0:
    the universal MC reset clears the persistent gate between sequences. A leak
    would carry the armed value over and push the t=0 mean above 0.
    """
    system = build_system()
    fault = system.add_indicator_var(
        component="equipment", var="fault_detected", stats=["mean"], name="fault"
    )[0]
    gate = system.add_indicator_var(
        component="equipment", var="inspection_gate", stats=["mean"], name="gate"
    )[0]

    # t=16 is inside both occ intervals (internal [10,18), detector [15,22)).
    system.simulate(PycMCSimulationParam(nb_runs=100, schedule=[0, 16], seed=7))

    instants, fault_vals = _series(fault)
    _, gate_vals = _series(gate)
    assert instants == [0.0, 16.0]

    # No leak: reset to 0 at the start of every sequence.
    assert fault_vals[0] == pytest.approx(0.0, abs=1e-9)
    assert gate_vals[0] == pytest.approx(0.0, abs=1e-9)
    # Armed during the run (deterministic → exactly 1.0 across all sequences).
    assert fault_vals[1] == pytest.approx(1.0, abs=1e-9)
    assert gate_vals[1] == pytest.approx(1.0, abs=1e-9)
