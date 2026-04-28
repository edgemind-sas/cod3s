"""Tests for ObjFM behaviour='external_rep_indep' — effects propagation.

Validates that failure_effects and repair_effects defined on the ObjFM are
applied to the target's variables via the target's automaton transitions
(not via the ObjFM directly).
"""
import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow  # noqa: F401  used via add_component(cls=...)


@pytest.fixture(autouse=True)
def run_around_tests():
    yield
    cod3s.terminate_session()


def fire(system, name, date=None):
    if date is not None:
        system.isimu_set_transition(name, date=date)
    else:
        system.isimu_set_transition(name)
    system.isimu_step_forward()


def test_rep_indep_failure_effects_applied():
    """failure_effects must be applied to the target when its automaton
    transitions to the failure state."""
    system = PycSystem(name="SysRepIndepFx1")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow", flow_in_max=10.0)
    fm_comp_name = "C1__frun"
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        behaviour="external_rep_indep",
        failure_effects={"flow_in_max": 0.0},
        failure_param=0.1,
        repair_param=0.1,
    )

    system.isimu_start()

    # Initial value untouched.
    assert system.comp["C1"].flow_in_max.value() == 10.0

    # Pulse: ObjFM.occ -> C1.occ -> ObjFM.rep (auto).
    fire(system, f"{fm_comp_name}.occ", date=10)
    fire(system, "C1.occ")
    # After C1.occ, the failure_effects on the target's automaton apply.
    assert system.comp["C1"].flow_in_max.value() == 0.0

    fire(system, f"{fm_comp_name}.rep")
    # ObjFM.rep does NOT touch target vars in pulse mode.
    assert system.comp["C1"].flow_in_max.value() == 0.0

    system.isimu_stop()


def test_rep_indep_repair_effects_applied():
    """repair_effects must be applied to the target when its automaton
    self-repairs back to the repair state."""
    system = PycSystem(name="SysRepIndepFx2")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow", flow_in_max=10.0)
    fm_comp_name = "C1__frun"
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        behaviour="external_rep_indep",
        failure_effects={"flow_in_max": 0.0},
        repair_effects={"flow_in_max": 7.5},  # different from initial to be specific
        failure_param=0.1,
        repair_param=0.1,
    )

    system.isimu_start()

    # Run a full cycle: failure -> auto-pulse -> repair.
    fire(system, f"{fm_comp_name}.occ", date=10)
    fire(system, "C1.occ")
    fire(system, f"{fm_comp_name}.rep")
    assert system.comp["C1"].flow_in_max.value() == 0.0
    fire(system, "C1.rep")
    # C1.rep applies repair_effects to the target.
    assert system.comp["C1"].flow_in_max.value() == 7.5

    system.isimu_stop()
