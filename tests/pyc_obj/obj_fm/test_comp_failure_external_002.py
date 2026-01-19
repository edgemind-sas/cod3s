import pytest
import warnings
import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow


@pytest.fixture(autouse=True)
def run_around_tests():
    yield
    cod3s.terminate_session()


# --- Helpers ---


def is_state_active(automaton, state_name):
    return automaton.get_state_by_name(state_name)._bkd.isActive()


def assert_fireable(system, expected_names):
    fireable = set(tr._bkd.name() for tr in system.isimu_fireable_transitions())
    assert fireable == set(expected_names)


def fire_transition(system, name, date=None):
    if date is not None:
        system.isimu_set_transition(name, date=date)
    else:
        system.isimu_set_transition(name)
    system.isimu_step_forward()


# --- Tests ---


def test_external_effects_propagation():
    """Vérifie la propagation des effets dans les targets en mode external"""
    system = PycSystem(name="SysExternalEffects")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    # Add targets with initial values
    system.add_component(name="C1", cls="ObjFlow", flow_in_max=10.0)
    system.add_component(name="C2", cls="ObjFlow", flow_in_max=10.0)

    # Add ObjFM with effects
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1", "C2"],
        behaviour="external",
        failure_effects={"flow_in_max": 0.0},
        repair_effects={"flow_in_max": 10.0},
        failure_param=[0.1, 0.01],
        repair_param=[0.1, 0.1],
    )

    system.isimu_start()

    # Initial values
    assert system.comp["C1"].flow_in_max.value() == 10.0
    assert system.comp["C2"].flow_in_max.value() == 10.0

    # Trigger common failure
    fm_comp_name = "CX__frun"
    fire_transition(system, f"{fm_comp_name}.occ__cc_12", date=10)

    # Step 1: ObjFM failed, targets not yet. Values should be unchanged.
    assert system.comp["C1"].flow_in_max.value() == 10.0
    assert system.comp["C2"].flow_in_max.value() == 10.0

    # Step 2: Propagate to targets
    # Firing C1.occ will also fire C2.occ as they are both instantaneous and enabled
    fire_transition(system, "C1.occ", date=10)
    
    # Both failed -> both effects should be applied
    assert system.comp["C1"].flow_in_max.value() == 0.0
    assert system.comp["C2"].flow_in_max.value() == 0.0

    # Trigger repair of ObjFM
    fire_transition(system, f"{fm_comp_name}.rep__cc_12", date=20)
    # Values still 0 (targets still in failure)
    assert system.comp["C1"].flow_in_max.value() == 0.0
    assert system.comp["C2"].flow_in_max.value() == 0.0

    # Repair C1 (this also repairs C2 because they are both instantaneous and enabled)
    fire_transition(system, "C1.rep")
    assert system.comp["C1"].flow_in_max.value() == 10.0
    assert system.comp["C2"].flow_in_max.value() == 10.0

    system.isimu_stop()
