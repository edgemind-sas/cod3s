"""Tests for ObjFM behaviour='external_rep_indep' — pulse dynamics, single target.

Validates the pulse model: ObjFM transitions occ -> rep instantly (delay 0,
no condition) after triggering. The target then evolves independently with
its own repair law (order-1 of the ObjFM).

Note: in isimu mode, firing a transition without a date advances the simulator
to the next event time and processes ALL delay(0) transitions at that time.
This means firing one delay(0) typically chains other fireable delay(0)
transitions in the same step. The pulse model relies on this chaining: after
firing ObjFM.occ, the next step naturally fires both target.occ AND ObjFM.rep
(both delay(0)).
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


def fireable_names(system):
    return {tr._bkd.name() for tr in system.isimu_fireable_transitions()}


def fire(system, name, date=None):
    if date is not None:
        system.isimu_set_transition(name, date=date)
    else:
        system.isimu_set_transition(name)
    system.isimu_step_forward()


def test_rep_indep_pulse_single_target():
    """ObjFM occ fires, then target.occ + ObjFM.rep chain (delay 0) in the
    next step. After the chain, ObjFM is back in rep, target in occ, ctrl_var
    stays True (no reset on ObjFM.rep in pulse mode)."""
    system = PycSystem(name="SysRepIndepPulse1")
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

    fm_aut = system.comp[fm_comp_name].automata_d["frun"]
    target_aut = system.comp["C1"].automata_d["frun"]
    ctrl = system.comp[fm_comp_name].ctrl_vars["C1"]

    # Initial state.
    assert fireable_names(system) == {f"{fm_comp_name}.occ"}
    assert ctrl.value() is False
    assert is_state_active(fm_aut, "rep")
    assert is_state_active(target_aut, "rep")

    # Fire ObjFM.occ at explicit date.
    fire(system, f"{fm_comp_name}.occ", date=10)
    assert ctrl.value() is True
    assert is_state_active(fm_aut, "occ")
    # Target hasn't transitioned yet (we stopped at the explicit date=10).
    assert is_state_active(target_aut, "rep")

    # Both target.occ AND ObjFM.rep are fireable now (both delay 0).
    after_occ = fireable_names(system)
    assert "C1.occ" in after_occ
    assert f"{fm_comp_name}.rep" in after_occ

    # Fire target.occ. The simulator will chain ObjFM.rep (delay 0) in the
    # same step since both are fireable at this time.
    fire(system, "C1.occ")
    # Target reached occ, failure_effects applied.
    assert is_state_active(target_aut, "occ")
    assert system.comp["C1"].flow_in_max.value() == 0.0
    # ObjFM auto-pulsed back to rep.
    assert is_state_active(fm_aut, "rep")
    # ctrl_var STAYS True (no effect on it from ObjFM.rep — pulse model).
    assert ctrl.value() is True, (
        "In external_rep_indep, ObjFM.rep must NOT touch ctrl_var "
        "(target owns its repair lifecycle)."
    )

    # Now ObjFM.occ is NOT fireable (target still in occ — augmented failure_cond).
    after_pulse = fireable_names(system)
    assert f"{fm_comp_name}.occ" not in after_pulse
    # Target.rep IS fireable (its own mu_1 law).
    assert "C1.rep" in after_pulse

    system.isimu_stop()


def test_rep_indep_target_repair_resets_ctrl():
    """When the target self-repairs, it resets its ctrl_var via the dedicated
    sensitive method on the target's automaton, and the ObjFM becomes ready
    to fire a new failure cycle."""
    system = PycSystem(name="SysRepIndepPulse2")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow", flow_in_max=10.0)
    fm_comp_name = "C1__frun"
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        behaviour="external_rep_indep",
        failure_effects={"flow_in_max": 0.0},
        repair_effects={"flow_in_max": 10.0},
        failure_param=0.1,
        repair_param=0.1,
    )

    system.isimu_start()

    target_aut = system.comp["C1"].automata_d["frun"]
    ctrl = system.comp[fm_comp_name].ctrl_vars["C1"]

    # Drive a full pulse: ObjFM.occ -> chain to C1.occ + ObjFM.rep.
    fire(system, f"{fm_comp_name}.occ", date=10)
    fire(system, "C1.occ")
    assert is_state_active(target_aut, "occ")
    assert ctrl.value() is True
    assert system.comp["C1"].flow_in_max.value() == 0.0

    # Fire the target's repair transition.
    fire(system, "C1.rep")
    assert is_state_active(target_aut, "rep")
    assert ctrl.value() is False, (
        "Target.rep must reset its ctrl_var to False so that the ObjFM "
        "can fire a new occurrence."
    )
    assert system.comp["C1"].flow_in_max.value() == 10.0

    # ObjFM should now be ready for a new occurrence.
    assert f"{fm_comp_name}.occ" in fireable_names(system)

    system.isimu_stop()
