import pytest
import cod3s
from cod3s.pycatshoo.system import PycSystem
from pyc_obj.kb_test import ObjFlow 
from pyc_obj.kb_test import ObjFlow2I1O

"""
Test Suite: Complex Failure Mode Dependencies with Multiple Conditions

This test suite validates the behavior of failure mode components with complex conditional 
dependencies involving multiple failure modes and attribute-based conditions. The test focuses on:

1. **System Setup**: Creates a system with 3 flow components (C1, C2, C3) and multiple failure modes:
   - Common cause failure mode affecting C1 and C2 simultaneously
   - Parameter modification failure mode for C3 (set_flow_out_max)
   - Dependent failure mode for C3 with compound conditions

2. **Complex Failure Conditions**: Tests multi-condition failure activation where:
   - C3's set_flow_out_max failure activates when flow_out_max != 2
   - C3's frun failure requires BOTH flow_out_max >= 2 AND C1's flow_available_out = False
   - This models realistic industrial scenarios with parameter thresholds and cascading failures

3. **Interactive Simulation Workflow**: Validates step-by-step simulation by:
   - Triggering common cause failure (C1, C2)
   - Activating parameter modification (C3 flow_out_max)
   - Verifying compound condition evaluation for dependent failures
   - Testing repair sequences and condition re-evaluation

4. **State and Parameter Consistency**: Confirms that:
   - Component parameters are correctly modified by failure effects
   - Compound conditions are properly evaluated after each state change
   - Fireable transitions reflect current system conditions accurately
   - Repair operations restore correct parameter values and availability states
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
        fm_name="set_flow_out_max",
        targets=["C3"],
        failure_cond=[
            [
                {"attr": "flow_out_max", "ope": "!=", "value": 2},
            ]
        ],
        failure_effects={"flow_out_max": 2},
        failure_param=[0.1],
        repair_param=[0.1],
        repair_cond=[
            [
                {"attr": "flow_out_max", "ope": "==", "value": 2},
            ]
        ],
        repair_effects={"flow_out_max": -1},
    )

    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C3"],
        failure_cond=[
            [
                {"attr": "flow_out_max", "ope": ">=", "value": 2},
                {"obj": "C1", "attr": "flow_available_out", "value": False},
            ]
        ],
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
    assert the_system.comp["C3"].flow_available_out.value() is True
    assert the_system.comp["C3"].flow_out_max.value() == -1

    # Ensure transitions are valid before proceeding
    transitions = the_system.isimu_fireable_transitions()

    the_system.isimu_set_transition("CX__frun.occ__cc_12")
    the_system.isimu_step_forward()

    assert "C3__frun.occ" not in [
        tr._bkd.name() for tr in the_system.isimu_fireable_transitions()
    ]

    the_system.isimu_set_transition("C3__set_flow_out_max.occ")
    the_system.isimu_step_forward()

    assert the_system.comp["C3"].flow_out_max.value() == 2
    assert "C3__frun.occ" in [
        tr._bkd.name() for tr in the_system.isimu_fireable_transitions()
    ]

    the_system.isimu_set_transition("CX__frun.rep__cc_12")
    the_system.isimu_step_forward()

    assert "C3__frun.occ" not in [
        tr._bkd.name() for tr in the_system.isimu_fireable_transitions()
    ]

    the_system.isimu_set_transition("CX__frun.occ__cc_1")
    the_system.isimu_step_forward()

    assert "C3__frun.occ" in [
        tr._bkd.name() for tr in the_system.isimu_fireable_transitions()
    ]

    the_system.isimu_set_transition("C3__frun.occ")
    the_system.isimu_step_forward()
    assert the_system.comp["C3"].flow_available_out.value() is False
    assert "C3__frun.rep" in [
        tr._bkd.name() for tr in the_system.isimu_fireable_transitions()
    ]

    the_system.isimu_set_transition("C3__frun.rep")
    the_system.isimu_step_forward()
    assert "C3__frun.occ" in [
        tr._bkd.name() for tr in the_system.isimu_fireable_transitions()
    ]

    the_system.isimu_set_transition("C3__set_flow_out_max.rep")
    the_system.isimu_step_forward()
    assert the_system.comp["C3"].flow_out_max.value() == -1
    assert "C3__frun.occ" not in [
        tr._bkd.name() for tr in the_system.isimu_fireable_transitions()
    ]

    the_system.isimu_stop()


def test_delete(the_system):
    the_system.deleteSys()
    cod3s.terminate_session()
