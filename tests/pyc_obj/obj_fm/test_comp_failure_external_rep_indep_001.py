"""Tests for ObjFM behaviour='external_rep_indep' — creation and structure.

Validates the basic scaffolding produced by the ObjFM constructor in
external_rep_indep mode: target automaton, control variable, no warning.
"""
import warnings

import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow  # noqa: F401  used via add_component(cls=...)

@pytest.fixture(autouse=True)
def run_around_tests():
    yield
    cod3s.terminate_session()



def test_rep_indep_creates_target_automaton():
    """The ObjFM creates an automaton named fm_name in each target."""
    system = PycSystem(name="SysRepIndepStruct1")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        behaviour="external_rep_indep",
        failure_param=0.1,
        repair_param=0.1,
    )

    assert "frun" in system.comp["C1"].automata_d


def test_rep_indep_creates_ctrl_vars():
    """The ObjFM creates ctrl_{fm}_{tgt} variables, init False."""
    system = PycSystem(name="SysRepIndepStruct2")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")
    system.add_component(name="C2", cls="ObjFlow")
    fm = system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1", "C2"],
        behaviour="external_rep_indep",
        failure_param=[0.1, 0.05],
        repair_param=[0.1, 0.1],
    )

    assert "C1" in fm.ctrl_vars
    assert "C2" in fm.ctrl_vars
    assert fm.ctrl_vars["C1"].value() is False
    assert fm.ctrl_vars["C2"].value() is False


def test_rep_indep_no_warning_on_effects():
    """No warning is emitted when failure_effects/repair_effects are provided."""
    system = PycSystem(name="SysRepIndepStruct3")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow", flow_in_max=10.0)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
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

    user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
    assert user_warnings == [], f"Unexpected warnings: {[str(w.message) for w in user_warnings]}"
