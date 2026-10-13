"""Held effects of an internal mode whose CC combinations overlap.

With several targets and overlapping combinations (two kept orders, or
one order strictly between 1 and ``n``), several combination automata
cover the same target. Up to 1.22.0 each of them clamped the target's
variables on its own: a combination at rest kept asserting
``not_occ_effects`` while another one covering the same target was in
``occ``.

* cod3s#4: a variable held on both faces with different values made the
  two clamps fight, the run never returned (refused in 1.21.0).
* cod3s#10: a variable held only at rest stayed held while the target
  was in ``occ`` through a partial combination, where a single-target
  mode releases it to its reinitialised value.

The held effects are now applied once per target, over the OR of the
combinations covering it (as ``external`` already did): the ``occ``
values while at least one covering combination is in ``occ``, the
``not_occ`` values only while all of them are at rest. This is the
single-target semantics, whatever the overlap.

Delay laws give one deterministic timeline for the scenario tests:
order 1 fails at 2 and repairs after 2, order 2 fails at 3 and repairs
after 10. cc_1 / cc_2: occ 2, rep 4, occ 6, rep 8, occ 10, rep 12,
occ 14. cc_1_2: occ 3, rep 13. Sampled at the schedule below, target A
is covered by a combination in ``occ`` everywhere but at 0 and 13.5,
and at 2.5 only by the partial combination cc_1.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem

REST_LEVEL = 1

SCHEDULE = [0.0, 2.5, 3.5, 4.5, 12.5, 13.5, 14.5]
#: Target A (and B) covered by a combination in occ, per SCHEDULE instant.
IN_OCC = [False, True, True, True, True, False, True]

#: Indicator means are single precision: far below one trajectory out of
#: the 300 of a check (3.3e-3), far above their rounding (3e-8).
TOL = 1e-6
MC_SCHEDULE = [0.0, 0.7, 1.3, 2.2, 3.1, 4.6, 5.9, 7.4, 9.0, 11.3, 14.0]

# Guard: a non-converging fixpoint (cod3s#4) would otherwise hang the run.
pytestmark = pytest.mark.timeout(120)


class CcfClampStore(cod3s.PycComponent):
    """Target: reinitialised ``working`` / ``ok`` / ``level``, persistent ``gate``."""

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)
        self.ok = self.addVariable("ok", Pyc.TVarType.t_bool, True)
        self.ok.setReinitialized(True)
        self.level = self.addVariable("level", Pyc.TVarType.t_int, 0)
        self.level.setReinitialized(True)
        self.gate = self.addVariable("gate", Pyc.TVarType.t_bool, False)
        self.gate.setReinitialized(False)


@pytest.fixture(autouse=True)
def _release_pycatshoo_singleton_per_test():
    yield
    cod3s.terminate_session()


def _system(name, targets=("A", "B")):
    system = PycSystem(name=name)
    for target in targets:
        system.add_component(name=target, cls="CcfClampStore")
    return system


def _mode(targets, **fields):
    spec = dict(
        cls="ObjMode2S",
        mode_name="m",
        targets=list(targets),
        occ_state="occ",
        not_occ_state="rep",
    )
    spec.update(fields)
    return spec


def _timeline_mode(**effects):
    return _mode(
        ("A", "B"),
        occ_law={"cls": "delay", "time": [2.0, 3.0]},
        not_occ_law={"cls": "delay", "time": [2.0, 10.0]},
        **effects,
    )


def _indicators(system, targets, var):
    return {
        target: system.add_indicator_var(
            component=target, var=var, stats=["mean"], name=f"{target}_{var}"
        )[0]
        for target in targets
    }


def _values(indicator):
    return indicator.values["values"].to_list()


def _run_timeline(system, var):
    indicators = _indicators(system, ("A", "B"), var)
    system.simulate(PycMCSimulationParam(nb_runs=1, schedule=SCHEDULE, seed=1))
    return _values(indicators["A"]), _values(indicators["B"])


def test_value_held_at_rest_is_released_while_a_partial_combination_is_in_occ():
    """cod3s#10: ``level`` falls back to its reinitialised 0 in occ."""
    system = _system("SysRestOnly")
    system.add_component(
        **_timeline_mode(
            occ_effects={"working": False}, not_occ_effects={"level": REST_LEVEL}
        )
    )
    expected = [0.0 if occ else float(REST_LEVEL) for occ in IN_OCC]
    level_a, level_b = _run_timeline(system, "level")
    assert level_a == expected
    assert level_b == expected


def test_value_held_on_both_faces_follows_the_covering_combinations():
    """cod3s#4: the run returns, the occ value wins while any cover is in occ."""
    system = _system("SysHeldBoth")
    system.add_component(
        **_timeline_mode(
            occ_effects={"working": False}, not_occ_effects={"working": True}
        )
    )
    expected = [0.0 if occ else 1.0 for occ in IN_OCC]
    working_a, working_b = _run_timeline(system, "working")
    assert working_a == expected
    assert working_b == expected


def test_pulse_entering_occ_survives_a_value_held_at_rest():
    """The rest clamp no longer overwrites a pulse while a cover is in occ."""
    system = _system("SysPulseOccHeldRest")
    system.add_component(
        **_timeline_mode(
            occ_effects_trans={"gate": True}, not_occ_effects={"gate": False}
        )
    )
    expected = [1.0 if occ else 0.0 for occ in IN_OCC]
    gate_a, gate_b = _run_timeline(system, "gate")
    assert gate_a == expected
    assert gate_b == expected


def test_held_effects_agree_with_the_occ_clamp_over_overlapping_combinations():
    """Three targets, every CC order kept: three variables, one reading.

    ``ok`` is held only in occ (the single-target reference, untouched by
    the change), ``working`` on both faces, ``level`` only at rest. On
    every trajectory they all say the same thing iff the held effects
    follow the OR of the combinations covering each target.
    """
    targets = ("A", "B", "C")
    system = _system("SysClampAgreement", targets=targets)
    system.add_component(
        **_mode(
            targets,
            occ_law={"cls": "exp", "rate": [0.3, 0.2, 0.1]},
            not_occ_law={"cls": "exp", "rate": [1.0, 0.5, 0.4]},
            occ_effects={"ok": False, "working": False},
            not_occ_effects={"working": True, "level": REST_LEVEL},
        )
    )
    ok = _indicators(system, targets, "ok")
    working = _indicators(system, targets, "working")
    level = _indicators(system, targets, "level")
    system.simulate(PycMCSimulationParam(nb_runs=300, schedule=MC_SCHEDULE, seed=11))
    for target in targets:
        p_ok = _values(ok[target])
        assert _values(working[target]) == pytest.approx(p_ok, abs=TOL), target
        from_level = [v / REST_LEVEL for v in _values(level[target])]
        assert from_level == pytest.approx(p_ok, abs=TOL), target
        assert any(0.0 < p < 1.0 for p in p_ok), target


def test_facade_holds_its_effects_over_the_covering_combinations():
    """``ObjFMExp`` reaches the same engine path with its own vocabulary."""
    system = _system("SysFacadeClamp")
    system.add_component(
        cls="ObjFMExp",
        fm_name="f",
        targets=["A", "B"],
        failure_param=[0.3, 0.2],
        repair_param=[1.0, 0.5],
        failure_effects={"working": False},
        repair_effects={"working": True, "level": REST_LEVEL},
    )
    working = _indicators(system, ("A", "B"), "working")
    level = _indicators(system, ("A", "B"), "level")
    system.simulate(PycMCSimulationParam(nb_runs=300, schedule=MC_SCHEDULE, seed=5))
    for target in ("A", "B"):
        p_working = _values(working[target])
        from_level = [v / REST_LEVEL for v in _values(level[target])]
        assert from_level == pytest.approx(p_working, abs=TOL), target
        assert any(0.0 < p < 1.0 for p in p_working), target
