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


def test_external_single_automaton_created():
    """Vérifie création automate dans target unique"""
    system = PycSystem(name="SysExternalSingle")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")

    fm = system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        behaviour="external",
        failure_param=0.1,
        repair_param=0.1,
    )

    # Check automaton creation in target
    assert "frun" in system.comp["C1"].automata_d

    # Check control variable creation in ObjFM
    assert "C1" in fm.ctrl_vars
    assert fm.ctrl_vars["C1"].value() == False


def test_external_single_synchronization():
    """Vérifie synchronisation défaillance/réparation"""

    system = PycSystem(name="SysExternalSync")

    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")

    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        behaviour="external",
        failure_param=0.1,
        repair_param=0.1,
    )

    system.isimu_start()

    assert_fireable(system, {"C1__frun.occ"})

    # Trigger failure
    fire_transition(system, "C1__frun.occ", date=10)

    # ObjFM state changed -> ctrl var True
    fm_aut = system.comp["C1__frun"].automata_d["frun"]
    assert is_state_active(fm_aut, "occ")
    assert system.comp["C1__frun"].ctrl_vars["C1"].value() == True

    # Check that ObjFM repair is NOT fireable (waits for target)
    assert_fireable(system, {"C1.occ"})

    # Propagate to target
    fire_transition(system, "C1.occ", date=10)

    target_aut = system.comp["C1"].automata_d["frun"]
    assert is_state_active(target_aut, "occ")

    # Now ObjFM repair is fireable
    assert_fireable(system, {"C1__frun.rep"})

    # Repair ObjFM
    fire_transition(system, "C1__frun.rep")

    # ObjFM state changed -> ctrl var False
    assert is_state_active(fm_aut, "rep")
    assert system.comp["C1__frun"].ctrl_vars["C1"].value() == False

    # Check that ObjFM failure is NOT fireable (waits for target repair)
    assert_fireable(system, {"C1.rep"})

    # Propagate to target
    fire_transition(system, "C1.rep")

    assert is_state_active(target_aut, "rep")

    # Back to initial state
    assert_fireable(system, {"C1__frun.occ"})

    system.isimu_stop()


def test_external_multi_synchronization():
    """Vérifie synchronisation avec 2 targets (défaillance commune)"""
    system = PycSystem(name="SysExternalMultiSync")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")
    system.add_component(name="C2", cls="ObjFlow")

    # Order 2 failure mode
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1", "C2"],
        behaviour="external",
        failure_param=[0.1, 0.01],  # Order 1, Order 2
        repair_param=[0.1, 0.1],
    )

    # system.traceVariable("#^.*$", 2)
    # system.traceTrans("#^.*$", 2)
    system.isimu_start()

    # Initial state: all rep.
    # Fireable: ObjFM failure transitions for cc_1, cc_2, cc_12.
    # Factorized name for C1, C2 is CX
    fm_comp_name = "CX__frun"

    expected_init = {
        f"{fm_comp_name}.occ__cc_1",
        f"{fm_comp_name}.occ__cc_2",
        f"{fm_comp_name}.occ__cc_12",
    }
    assert_fireable(system, expected_init)
    # Trigger common failure (cc_12)
    fire_transition(system, f"{fm_comp_name}.occ__cc_12", date=10)

    # ObjFM state changed -> ctrl vars True for both C1 and C2
    # ObjFM repair (rep__cc_12) not fireable yet (waits for targets).
    # Single failures (cc_1, cc_2) still fireable (independent).
    # Targets C1 and C2 can fail.
    expected_step1 = {
        f"{fm_comp_name}.occ__cc_1",
        f"{fm_comp_name}.occ__cc_2",
        "C1.occ",
        "C2.occ",
    }
    assert_fireable(system, expected_step1)

    # Fire C1 failure but it force also C2 failure
    fire_transition(system, "C1.occ")
    assert is_state_active(system.comp["C1"].automata_d["frun"], "occ")
    assert is_state_active(system.comp["C2"].automata_d["frun"], "occ")

    expected_step2 = {f"{fm_comp_name}.rep__cc_12"}
    assert_fireable(system, expected_step2)
    # Fire C2 failure
    fire_transition(system, f"{fm_comp_name}.rep__cc_12")
    # Both failed. ObjFM can repair cc_12.
    expected_step3 = {
        "C1.rep",
        "C2.rep",
    }
    assert_fireable(system, expected_step3)

    system.isimu_step_forward()

    assert_fireable(system, expected_init)
    # Trigger common failure (cc_12)
    fire_transition(system, f"{fm_comp_name}.occ__cc_2", date=15)

    assert_fireable(
        system,
        {
            "C2.occ",
            f"{fm_comp_name}.occ__cc_1",
            f"{fm_comp_name}.occ__cc_12",
        },
    )
    system.isimu_step_forward()

    assert_fireable(
        system,
        {
            f"{fm_comp_name}.occ__cc_1",
            f"{fm_comp_name}.rep__cc_2",
        },
    )

    fire_transition(system, f"{fm_comp_name}.occ__cc_1")
    assert_fireable(
        system,
        {
            "C1.occ",
            f"{fm_comp_name}.rep__cc_2",
        },
    )

    system.isimu_step_forward()
    assert_fireable(
        system,
        {
            f"{fm_comp_name}.rep__cc_1",
            f"{fm_comp_name}.rep__cc_2",
        },
    )

    fire_transition(system, f"{fm_comp_name}.rep__cc_1")
    system.isimu_step_forward()
    fire_transition(system, f"{fm_comp_name}.rep__cc_2")
    system.isimu_step_forward()
    assert_fireable(system, expected_init)

    system.isimu_stop()
