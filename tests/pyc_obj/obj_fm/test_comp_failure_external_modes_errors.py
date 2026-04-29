"""Error-case tests for ObjFM behaviour modes.

Covers invalid behaviour values, name conflicts on target automata, and
the order-1 inactive-law trap for external_rep_indep.
"""
import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow  # noqa: F401  used via add_component(cls=...)


@pytest.fixture(autouse=True)
def run_around_tests():
    yield
    cod3s.terminate_session()


def test_behaviour_invalid_raises():
    """An unknown behaviour value must raise ValueError listing valid options."""
    system = PycSystem(name="SysInvalidBehaviour")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")
    with pytest.raises(ValueError, match="behaviour"):
        system.add_component(
            cls="ObjFMExp",
            fm_name="frun",
            targets=["C1"],
            behaviour="bogus_mode",
            failure_param=0.1,
            repair_param=0.1,
        )


def test_external_name_conflict_raises():
    """If a target already has an automaton with the same name as the FM,
    creation must raise ValueError."""
    system = PycSystem(name="SysExternalConflict")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")
    # Pre-create an automaton named "frun" on C1 to provoke the conflict.
    system.comp["C1"].add_aut2st(
        name="frun",
        st1="rep",
        st2="occ",
        init_st2=False,
        occ_law_12={"cls": "delay", "time": 0},
        occ_law_21={"cls": "delay", "time": 0},
    )

    with pytest.raises(ValueError, match="frun"):
        system.add_component(
            cls="ObjFMExp",
            fm_name="frun",
            targets=["C1"],
            behaviour="external",
            failure_param=0.1,
            repair_param=0.1,
        )


def test_external_rep_indep_name_conflict_raises():
    """Same conflict check for external_rep_indep."""
    system = PycSystem(name="SysRepIndepConflict")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")
    system.comp["C1"].add_aut2st(
        name="frun",
        st1="rep",
        st2="occ",
        init_st2=False,
        occ_law_12={"cls": "delay", "time": 0},
        occ_law_21={"cls": "delay", "time": 0},
    )

    with pytest.raises(ValueError, match="frun"):
        system.add_component(
            cls="ObjFMExp",
            fm_name="frun",
            targets=["C1"],
            behaviour="external_rep_indep",
            failure_param=0.1,
            repair_param=0.1,
        )


def test_external_rep_indep_drop_inactive_order1_raises():
    """When order 1 has lambda=0 and drop_inactive_automata=True, the order-1
    repair params would be unavailable; external_rep_indep must raise a clear
    error rather than crash on None access."""
    system = PycSystem(name="SysRepIndepNoOrder1")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")
    system.add_component(name="C2", cls="ObjFlow")

    # Order-1 inactive (lambda=0), order-2 active. With drop_inactive_automata
    # active, the order-1 automata are not created and repair_var_params_order1
    # is set but its repair law would be inactive — the implementation should
    # detect this and raise a clear error.
    with pytest.raises(ValueError, match="order"):
        system.add_component(
            cls="ObjFMExp",
            fm_name="frun",
            targets=["C1", "C2"],
            behaviour="external_rep_indep",
            failure_param=[0.0, 0.05],  # order-1 inactive
            repair_param=[0.0, 0.5],    # order-1 repair inactive
        )
