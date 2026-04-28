"""Tests for ObjFM behaviour='external_rep_indep' — repair_cond gating.

Validates that the user-provided repair_cond on the ObjFM is reused for the
target's self-repair transition, evaluated on that specific target.
"""
import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow  # noqa: F401  used via add_component(cls=...)


@pytest.fixture(autouse=True)
def run_around_tests():
    yield
    cod3s.terminate_session()


def fireable_names(system):
    return {tr._bkd.name() for tr in system.isimu_fireable_transitions()}


def fire(system, name, date=None):
    if date is not None:
        system.isimu_set_transition(name, date=date)
    else:
        system.isimu_set_transition(name)
    system.isimu_step_forward()


def test_rep_indep_repair_cond_default_true():
    """With default repair_cond=True, target.rep must be fireable as soon as
    the target is in occ (after the pulse)."""
    system = PycSystem(name="SysRepIndepCondDefault")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow", flow_in_max=10.0)
    fm_comp_name = "C1__frun"
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        behaviour="external_rep_indep",
        failure_param=0.1,
        repair_param=0.1,
    )

    system.isimu_start()

    fire(system, f"{fm_comp_name}.occ", date=10)
    fire(system, "C1.occ")
    fire(system, f"{fm_comp_name}.rep")

    # Default repair_cond is True -> target.rep is fireable immediately.
    assert "C1.rep" in fireable_names(system)
    system.isimu_stop()


def test_rep_indep_repair_cond_callable_blocks_repair():
    """With a callable repair_cond that depends on a target variable, the
    target's self-repair must be gated on that condition (evaluated on the
    target itself)."""
    system = PycSystem(name="SysRepIndepCondCallable")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow", flow_in_max=10.0)
    fm_comp_name = "C1__frun"

    # The user's repair_cond captures the system at construction time and
    # checks a target variable (flow_available_out). When False, no repair.
    def repair_when_available():
        return system.comp["C1"].flow_available_out.value() is True

    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        behaviour="external_rep_indep",
        repair_cond=repair_when_available,
        failure_param=0.1,
        repair_param=0.1,
    )

    system.isimu_start()

    # Drive the pulse.
    fire(system, f"{fm_comp_name}.occ", date=10)
    fire(system, "C1.occ")
    fire(system, f"{fm_comp_name}.rep")

    # Force flow_available_out to False -> target.rep must NOT be fireable.
    system.comp["C1"].flow_available_out.setValue(False)
    assert "C1.rep" not in fireable_names(system)

    # Restore flow_available_out -> target.rep becomes fireable.
    system.comp["C1"].flow_available_out.setValue(True)
    assert "C1.rep" in fireable_names(system)

    system.isimu_stop()
