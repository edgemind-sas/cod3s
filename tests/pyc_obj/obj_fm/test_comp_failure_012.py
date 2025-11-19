import pytest
import cod3s
from cod3s.pycatshoo.system import PycSystem
from pyc_obj.kb_test import ObjFlow 

"""
Test Suite: Component Failure Mode Dependencies

This test suite validates the behavior of failure mode components with conditional dependencies
between different components in a system. The test specifically focuses on:

1. **System Setup**: Creates a system with 3 flow components (C1, C2, C3) and failure modes
   - Common cause failure mode affecting C1 and C2 simultaneously
   - Dependent failure mode for C3 that only activates when C1 fails

2. **Failure Mode Dependencies**: Tests conditional failure activation where:
   - C3 failure mode is conditioned on C1's flow_available_out being False
   - This models cascading failure scenarios common in industrial systems

3. **Interactive Simulation**: Validates the interactive simulation capabilities by:
   - Manually triggering specific transitions
   - Verifying that dependent failure conditions are properly evaluated
   - Ensuring repair transitions restore the system to correct states

4. **State Consistency**: Confirms that:
   - Component states are correctly updated after transitions
   - Fireable transitions list reflects current system conditions
   - Dependent failures only become available when conditions are met
"""


@pytest.fixture(scope="module")
def the_system():
    system = cod3s.PycSystem(name="Sys")

    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(
        name="C1",
        cls="ObjFlow",
    )

    system.add_component(
        name="C2",
        cls="ObjFlow",
    )

    system.add_component(
        name="C3",
        cls="ObjFlow",
    )

    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1", "C2"],
        failure_effects={"flow_available_out": False},
        failure_param=[0.1, 0.1],
        repair_param=[0.1, 0.1],
    )

    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C3"],
        failure_cond=[[{"obj": "C1", "attr": "flow_available_out", "value": False}]],
        failure_effects={"flow_available_out": False},
        failure_param=[0.1],
        repair_param=[0.1],
    )

    return system


def test_system(the_system):
    # Run simulation
    # the_system.traceVariable("#.*", 2)
    the_system.isimu_start()

    assert the_system.comp["C1"].flow_available_out.value() is True
    assert the_system.comp["C2"].flow_available_out.value() is True

    # Ensure transitions are valid before proceeding
    transitions = the_system.isimu_fireable_transitions()

    the_system.isimu_set_transition("CX__frun.occ__cc_12")
    trans_fired = the_system.isimu_step_forward()

    assert "C3__frun.occ" in [
        tr._bkd.name() for tr in the_system.isimu_fireable_transitions()
    ]

    the_system.isimu_set_transition("CX__frun.rep__cc_12")
    the_system.isimu_step_forward()

    assert "C3__frun.occ" not in [
        tr._bkd.name() for tr in the_system.isimu_fireable_transitions()
    ]

    the_system.isimu_set_transition("CX__frun.occ__cc_2")
    trans_fired = the_system.isimu_step_forward()

    assert "C3__frun.occ" not in [
        tr._bkd.name() for tr in the_system.isimu_fireable_transitions()
    ]

    the_system.isimu_set_transition("CX__frun.rep__cc_2")
    the_system.isimu_step_forward()
    the_system.isimu_set_transition("CX__frun.occ__cc_1")
    the_system.isimu_step_forward()

    assert "C3__frun.occ" in [
        tr._bkd.name() for tr in the_system.isimu_fireable_transitions()
    ]

    the_system.isimu_set_transition("C3__frun.occ")
    trans_fired = the_system.isimu_step_forward()
    assert the_system.comp["C3"].flow_available_out.value() is False

    assert "C3__frun.rep" in [
        tr._bkd.name() for tr in the_system.isimu_fireable_transitions()
    ]

    the_system.isimu_stop()


def test_delete(the_system):
    the_system.deleteSys()
    cod3s.terminate_session()
