"""Tests for ObjFM behaviour='external_rep_indep' — ObjFMDelay compatibility.

Validates that the pulse model also works for ObjFMDelay, where the target's
self-repair law is delay(ttr_1) instead of exp(mu_1).
"""
import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow  # noqa: F401  used via add_component(cls=...)


@pytest.fixture(autouse=True)
def run_around_tests():
    yield
    cod3s.terminate_session()


def is_state_active(automaton, state_name):
    return automaton.get_state_by_name(state_name)._bkd.isActive()


def fire(system, name, date=None):
    if date is not None:
        system.isimu_set_transition(name, date=date)
    else:
        system.isimu_set_transition(name)
    system.isimu_step_forward()


def test_rep_indep_objfmdelay_uses_delay_law():
    """With ObjFMDelay, target.rep uses the order-1 delay law (ttr_1)."""
    system = PycSystem(name="SysRepIndepDelay")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow", flow_in_max=10.0)
    fm_comp_name = "C1__frun"
    system.add_component(
        cls="ObjFMDelay",
        fm_name="frun",
        targets=["C1"],
        behaviour="external_rep_indep",
        failure_effects={"flow_in_max": 0.0},
        repair_effects={"flow_in_max": 10.0},
        failure_param=5.0,    # ttf_1 = 5
        repair_param=20.0,    # ttr_1 = 20
    )

    system.isimu_start()
    target_aut = system.comp["C1"].automata_d["frun"]

    # Drive the pulse at date 10.
    fire(system, f"{fm_comp_name}.occ", date=10)
    fire(system, "C1.occ")
    assert is_state_active(target_aut, "occ")
    assert system.comp["C1"].flow_in_max.value() == 0.0

    # Fire C1.rep without forcing a date — should land at 10 + ttr_1 = 30
    # (delay law).
    fire(system, "C1.rep")
    assert is_state_active(target_aut, "rep")
    assert system.comp["C1"].flow_in_max.value() == 10.0
    assert system.currentTime() == pytest.approx(30.0)

    system.isimu_stop()
