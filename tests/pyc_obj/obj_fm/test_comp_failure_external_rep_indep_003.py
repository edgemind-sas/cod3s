"""Tests for ObjFM behaviour='external_rep_indep' — multi-target combos.

Validates that combos of order > 1 trigger their respective targets, and that
each target then repairs INDEPENDENTLY according to the order-1 law of the
ObjFM. Partial repair must block re-firing of any combo that includes a still-
failed target, while combos limited to repaired targets remain available.

Note: in isimu mode, firing one delay(0) transition chains all other fireable
delay(0) transitions at the same time. So firing the ObjFM combo at date=t
followed by ANY of its target transitions causes the full trigger (all targets
+ ObjFM repair) to complete in a single step_forward.
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


def test_rep_indep_combo_order2_independent_repair():
    """cc_1_2 triggers C1 and C2 (and ObjFM auto-triggers); C1 self-repairs alone;
    ObjFM combos that include C2 are still blocked until C2 also repairs."""
    system = PycSystem(name="SysRepIndepO2Indep")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")
    system.add_component(name="C2", cls="ObjFlow")
    fm_comp_name = "CX__frun"
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1", "C2"],
        behaviour="external_rep_indep",
        failure_param=[0.1, 0.05],
        repair_param=[0.1, 0.5],  # mu_1 used for ALL target repairs
    )

    system.isimu_start()

    fm_aut = system.comp[fm_comp_name].automata_d[f"frun__cc_1_2"]
    c1_aut = system.comp["C1"].automata_d["frun"]
    c2_aut = system.comp["C2"].automata_d["frun"]
    fm = system.comp[fm_comp_name]

    # All three combos initially fireable (single, single, common-cause).
    initial = fireable_names(system)
    assert {f"{fm_comp_name}.occ__cc_1",
            f"{fm_comp_name}.occ__cc_2",
            f"{fm_comp_name}.occ__cc_1_2"} <= initial

    # Trigger common-cause failure (cc_1_2) at explicit date=10.
    fire(system, f"{fm_comp_name}.occ__cc_1_2", date=10)
    assert is_state_active(fm_aut, "occ__cc_1_2")
    assert fm.ctrl_vars["C1"].value() is True
    assert fm.ctrl_vars["C2"].value() is True

    # Fire any of the chained delay(0) transitions: the simulator processes
    # all fireable delay(0) at this date. After this single step:
    # - C1.frun.occ done, C2.frun.occ done, ObjFM.cc_1_2.rep done (auto-trigger).
    fire(system, "C1.frun__occ")
    assert is_state_active(c1_aut, "frun__occ")
    assert is_state_active(c2_aut, "frun__occ")
    # ObjFM has triggered back to rep.
    assert is_state_active(fm_aut, "rep__cc_1_2")
    # ctrl_vars stay True (target owns reset).
    assert fm.ctrl_vars["C1"].value() is True
    assert fm.ctrl_vars["C2"].value() is True

    # No combo can fire again while any target is still in occ.
    after_trigger = fireable_names(system)
    assert f"{fm_comp_name}.occ__cc_1" not in after_trigger
    assert f"{fm_comp_name}.occ__cc_2" not in after_trigger
    assert f"{fm_comp_name}.occ__cc_1_2" not in after_trigger
    # Target self-repairs are fireable (their own mu_1 law).
    assert "C1.frun__rep" in after_trigger
    assert "C2.frun__rep" in after_trigger

    # C1 self-repairs alone (with explicit date to avoid chaining C2.rep).
    fire(system, "C1.frun__rep", date=20)
    assert is_state_active(c1_aut, "frun__rep")
    assert is_state_active(c2_aut, "frun__occ")
    assert fm.ctrl_vars["C1"].value() is False
    assert fm.ctrl_vars["C2"].value() is True

    # cc_1 is now fireable (only C1 needed in rep), but cc_2 and cc_1_2 are not.
    after_c1_rep = fireable_names(system)
    assert f"{fm_comp_name}.occ__cc_1" in after_c1_rep
    assert f"{fm_comp_name}.occ__cc_2" not in after_c1_rep
    assert f"{fm_comp_name}.occ__cc_1_2" not in after_c1_rep

    # C2 finishes repairing.
    fire(system, "C2.frun__rep")
    assert is_state_active(c2_aut, "frun__rep")
    assert fm.ctrl_vars["C2"].value() is False

    # All combos fireable again.
    final = fireable_names(system)
    assert {f"{fm_comp_name}.occ__cc_1",
            f"{fm_comp_name}.occ__cc_2",
            f"{fm_comp_name}.occ__cc_1_2"} <= final

    system.isimu_stop()


def test_rep_indep_partial_state_blocks_higher_order_combo():
    """If only one target is in rep state, only the order-1 combo on that
    target should be fireable; higher-order combos involving the still-failed
    target stay blocked."""
    system = PycSystem(name="SysRepIndepO2Block")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")
    system.add_component(name="C2", cls="ObjFlow")
    fm_comp_name = "CX__frun"
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1", "C2"],
        behaviour="external_rep_indep",
        failure_param=[0.1, 0.05],
        repair_param=[0.1, 0.5],
    )

    system.isimu_start()

    # Trigger cc_2 (C2 only) — trigger chains C2.occ + ObjFM.cc_2.rep.
    fire(system, f"{fm_comp_name}.occ__cc_2", date=10)
    fire(system, "C2.frun__occ")

    # C2 in occ, C1 in rep.
    fireable = fireable_names(system)
    # cc_1 fireable (C1 still in rep), cc_2 NOT (C2 in occ), cc_1_2 NOT.
    assert f"{fm_comp_name}.occ__cc_1" in fireable
    assert f"{fm_comp_name}.occ__cc_2" not in fireable
    assert f"{fm_comp_name}.occ__cc_1_2" not in fireable
    # C2.rep is fireable (its own mu_1 law).
    assert "C2.frun__rep" in fireable

    system.isimu_stop()
