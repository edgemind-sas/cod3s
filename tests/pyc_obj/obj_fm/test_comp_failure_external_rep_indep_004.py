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
    transitions to the failure state (delay-0 chain in the same step as the
    ObjFM occurrence)."""
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

    # Trigger: ObjFM.occ at date=10 -> chain to C1.occ + ObjFM.rep.
    fire(system, f"{fm_comp_name}.occ", date=10)
    fire(system, "C1.frun__occ")
    # After the chain, target.frun is in occ, failure_effects applied.
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
        repair_effects={"flow_in_max": 7.5},  # specific to verify it ran
        failure_param=0.1,
        repair_param=0.1,
    )

    system.isimu_start()

    # Drive the trigger cycle.
    fire(system, f"{fm_comp_name}.occ", date=10)
    fire(system, "C1.frun__occ")
    assert system.comp["C1"].flow_in_max.value() == 0.0

    # Fire target.rep -> repair_effects applied.
    fire(system, "C1.frun__rep")
    assert system.comp["C1"].flow_in_max.value() == 7.5

    system.isimu_stop()
