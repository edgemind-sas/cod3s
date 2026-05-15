"""Tests for ObjFM behaviour='external_rep_indep' — repair_cond gating.

Validates that the user-provided repair_cond on the ObjFM is reused for the
target's self-repair transition, evaluated on that specific target.

Note: with non-deterministic laws (exp), `isimu_fireable_transitions` does NOT
filter by condition truth — it lists active transitions whose source state is
active. We test the gating effect with a *deterministic* law (ObjFMDelay) so
that the cond shows up in fireability filtering.
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
    the target is in occ (after the trigger)."""
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
    # Default repair_cond is True -> target.rep is fireable.
    assert "C1.rep" in fireable_names(system)

    system.isimu_stop()


def test_rep_indep_repair_cond_callable_evaluated_on_target():
    """A callable repair_cond is reused on the target's self-repair transition
    and evaluated on that specific target. With a deterministic law (delay),
    a False cond pushes the transition out of the fireable horizon."""
    # Use ObjFMDelay so the law is deterministic and `fireable` filtering
    # honours the cond via `endTime`.
    system = PycSystem(name="SysRepIndepCondCallable")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow", flow_in_max=10.0)
    fm_comp_name = "C1__frun"

    # Repair_cond gated on a target variable; closure captures the system.
    def repair_when_available():
        return system.comp["C1"].flow_available_out.value() is True

    system.add_component(
        cls="ObjFMDelay",
        fm_name="frun",
        targets=["C1"],
        behaviour="external_rep_indep",
        repair_cond=repair_when_available,
        failure_param=5.0,    # ttf_1
        repair_param=20.0,    # ttr_1
    )

    # Force the cond to False BEFORE starting the simulation. Since
    # flow_available_out is a system variable read by the closure, setting it
    # before isimu_start ensures the cond evaluates False at fireability check.
    system.comp["C1"].flow_available_out.setValue(False)

    system.isimu_start()

    # Drive the trigger cycle.
    fire(system, f"{fm_comp_name}.occ", date=10)
    fire(system, "C1.occ")

    # Cond is False -> with the deterministic delay law, the transition
    # endTime stays beyond the bound, so C1.rep is NOT fireable. This proves
    # the user-provided repair_cond is wired into the target's repair
    # transition (rather than the previous TODO `lambda: True`).
    assert "C1.rep" not in fireable_names(system)

    system.isimu_stop()
