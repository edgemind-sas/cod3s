"""Tests for ObjFM behaviour='external_rep_indep' — pulse dynamics, single target.

Validates the pulse model: ObjFM transitions occ -> rep instantly (delay 0,
no condition) after triggering, so the target then evolves independently with
its own repair law (order-1 of the ObjFM).
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
    """ObjFM occ -> ctrl=True; target.occ propagates; ObjFM auto-pulses to rep
    without resetting ctrl; target stays in occ until its own repair law fires.
    """
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

    # Initial state: only ObjFM occ is fireable.
    assert fireable_names(system) == {f"{fm_comp_name}.occ"}
    assert ctrl.value() is False
    assert is_state_active(fm_aut, "rep")
    assert is_state_active(target_aut, "rep")

    # Fire ObjFM occ -> ctrl_C1 should become True via direct effect.
    fire(system, f"{fm_comp_name}.occ", date=10)
    assert ctrl.value() is True
    assert is_state_active(fm_aut, "occ")

    # Pulse model: BOTH C1.occ AND ObjFM.rep should be fireable now.
    # ObjFM.rep has cond=True and law=delay(0).
    after_occ = fireable_names(system)
    assert "C1.occ" in after_occ
    assert f"{fm_comp_name}.rep" in after_occ

    # Fire the target's failure transition -> applies failure_effects.
    fire(system, "C1.occ")
    assert is_state_active(target_aut, "occ")
    assert system.comp["C1"].flow_in_max.value() == 0.0
    # ctrl_var must STILL be True (target manages its own ctrl reset).
    assert ctrl.value() is True

    # ObjFM.rep is still fireable (sans condition, delay 0).
    assert f"{fm_comp_name}.rep" in fireable_names(system)

    # Fire ObjFM.rep -> ObjFM goes back to rep BUT ctrl_var stays True.
    fire(system, f"{fm_comp_name}.rep")
    assert is_state_active(fm_aut, "rep")
    assert is_state_active(target_aut, "occ")
    assert ctrl.value() is True, (
        "In external_rep_indep, ObjFM.rep must NOT touch ctrl_var "
        "(target owns its repair lifecycle)."
    )

    # ObjFM.occ must NOT be fireable while target is still in occ.
    after_pulse = fireable_names(system)
    assert f"{fm_comp_name}.occ" not in after_pulse
    # Target.rep IS fireable (its own mu_1 law).
    assert "C1.rep" in after_pulse

    system.isimu_stop()


def test_rep_indep_target_repair_resets_ctrl():
    """When the target self-repairs, it resets its ctrl_var and the ObjFM
    becomes ready to fire a new failure cycle."""
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

    # Drive a full pulse: ObjFM.occ -> C1.occ -> ObjFM.rep (auto-pulse).
    fire(system, f"{fm_comp_name}.occ", date=10)
    fire(system, "C1.occ")
    fire(system, f"{fm_comp_name}.rep")
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
