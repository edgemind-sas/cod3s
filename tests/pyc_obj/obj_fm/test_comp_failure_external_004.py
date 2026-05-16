import pytest
import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow, ObjFlow2I1O

@pytest.fixture(autouse=True)
def run_around_tests():
    yield
    cod3s.terminate_session()



# --- Helpers ---


def is_state_active(automaton, state_name):
    return automaton.get_state_by_name(state_name)._bkd.isActive()


def assert_fireable(system, expected_names):
    """
    Asserts that the set of fireable transitions matches exactly the expected names.
    Useful to verify that conditions (like ObjFM waiting for targets) are respected.
    """
    fireable = set(tr._bkd.name() for tr in system.isimu_fireable_transitions())
    # We filter out internal pycatshoo transitions if any (usually none exposed this way)
    assert fireable == set(expected_names), f"Mismatch in fireable transitions. \nExpected: {expected_names}\nGot: {fireable}"

def fire_transition(system, name, date=None):
    if date is not None:
        system.isimu_set_transition(name, date=date)
    else:
        system.isimu_set_transition(name)
    system.isimu_step_forward()


# --- Test ---


def test_external_dependency_system():
    """
    Reproduction of test_comp_failure_004.py logic with external behaviour.
    System: CA, CB -> T1..T4.
    FM1: Targets CA, CB. External.
    FM2: Targets T1..T4. External.
    """
    system = PycSystem(name="SysExtDep")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="CA", cls="ObjFlow", flow_type="f1")
    system.add_component(name="CB", cls="ObjFlow", flow_type="f2")

    system.add_component(name="T1", cls="ObjFlow2I1O", flow_type_in1="f1", flow_type_in2="f2", flow_type_out="f3")
    system.add_component(name="T2", cls="ObjFlow2I1O", flow_type_in1="f1", flow_type_in2="f2", flow_type_out="f3")
    system.add_component(name="T3", cls="ObjFlow2I1O", flow_type_in1="f1", flow_type_in2="f2", flow_type_out="f3", logic="and")
    system.add_component(name="T4", cls="ObjFlow2I1O", flow_type_in1="f1", flow_type_in2="f2", flow_type_out="f3")

    system.connect("CA", "f1_out", "T1", "f1_in")
    system.connect("CA", "f1_out", "T2", "f1_in")
    system.connect("CB", "f2_out", "T3", "f2_in")
    system.connect("CB", "f2_out", "T4", "f2_in")

    # FM1: Targets CA, CB
    # Factorized name: CX__frun
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["CA", "CB"],
        behaviour="external",
        failure_effects={"v_flow_out": 2.0},
        # No repair effects
        failure_param=[0.1, 0.2],
        repair_param=[0.1, 0.1],
    )

    # FM2: Targets T1..T4
    # Factorized name: TXX__frun
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["T1", "T2", "T3", "T4"],
        target_name="TXX",
        behaviour="external",
        failure_effects={"v_flow_out": 1.0},
        # No repair effects
        failure_param=[0.1, 0.01, 0.001, 0.0001],
        repair_param=[0.0001, 0.001, 0.01, 0.1],
    )

    system.isimu_start()

    # Initial state
    assert system.comp["CA"].v_flow_out.value() == 0
    assert system.comp["CB"].v_flow_out.value() == 0
    assert system.comp["T1"].v_flow_out.value() == 0
    assert system.comp["T2"].v_flow_out.value() == 0
    assert system.comp["T3"].v_flow_out.value() == 0
    assert system.comp["T4"].v_flow_out.value() == 0

    # Verify Fireable Transitions
    # CX__frun: 3 combos (cc_1, cc_2, cc_12)
    # TXX__frun: 15 combos (4 order 1, 6 order 2, 4 order 3, 1 order 4) -> Total 18
    # 3 + 15 = 18 fireable transitions initially (all failures)
    # We verify some key ones
    fireable_init = {tr._bkd.name() for tr in system.isimu_fireable_transitions()}
    assert len(fireable_init) == 18
    assert "CX__frun.occ__cc_1" in fireable_init
    assert "TXX__frun.occ__cc_4" in fireable_init

    # Fire FM1 on CA (cc_1)
    fire_transition(system, "CX__frun.occ__cc_1", date=10)
    
    # Check intermediate state: ObjFM failed, CA not yet.
    # CX__frun repair (rep__cc_1) NOT fireable yet (waits for CA)
    # CA failure (CA.occ) IS fireable.
    fireable_step1 = {tr._bkd.name() for tr in system.isimu_fireable_transitions()}
    assert "CA.frun__occ" in fireable_step1
    assert "CX__frun.rep__cc_1" not in fireable_step1
    
    # Propagate to CA
    fire_transition(system, "CA.frun__occ", date=10)

    # CA should be 2.
    assert system.comp["CA"].v_flow_out.value() == 2
    assert system.comp["CB"].v_flow_out.value() == 0
    
    # Propagation to T components
    assert system.comp["T1"].v_flow_out.value() == 2
    assert system.comp["T2"].v_flow_out.value() == 2
    assert system.comp["T3"].v_flow_out.value() == 0
    assert system.comp["T4"].v_flow_out.value() == 0

    # Fire FM2 on T4 (cc_4)
    fire_transition(system, "TXX__frun.occ__cc_4")
    
    # Check intermediate state
    fireable_step2 = {tr._bkd.name() for tr in system.isimu_fireable_transitions()}
    assert "T4.frun__occ" in fireable_step2
    assert "TXX__frun.rep__cc_4" not in fireable_step2
    
    # Propagate to T4
    fire_transition(system, "T4.frun__occ")

    # T4 failure effect: v_flow_out = 1.
    assert system.comp["T4"].v_flow_out.value() == 1
    
    # Check others unchanged
    assert system.comp["T1"].v_flow_out.value() == 2
    assert system.comp["T2"].v_flow_out.value() == 2
    assert system.comp["T3"].v_flow_out.value() == 0

    # Repair CX__frun (cc_1)
    # Now that CA is in occ, ObjFM repair is fireable
    fireable_step3 = {tr._bkd.name() for tr in system.isimu_fireable_transitions()}
    assert "CX__frun.rep__cc_1" in fireable_step3
    
    fire_transition(system, "CX__frun.rep__cc_1")
    
    # Propagate repair to CA
    fireable_step4 = {tr._bkd.name() for tr in system.isimu_fireable_transitions()}
    assert "CA.frun__rep" in fireable_step4
    
    fire_transition(system, "CA.frun__rep")
    
    # No repair effects -> CA value stays 2!
    assert system.comp["CA"].v_flow_out.value() == 2
    assert system.comp["T1"].v_flow_out.value() == 2

    system.isimu_stop()
