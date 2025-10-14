import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'Lib'))
from Lib import objFlow,composants

import pytest
from cod3s import terminate_session
from cod3s.pycatshoo.system import PycSystem, PycMCSimulationParam


@pytest.fixture(scope="module")
def the_system():
    system = PycSystem(name="Sys")

    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(
        name="C1",
        cls="ObjFlow",
        var_prod_default=True,
    )

    system.add_component(
        name="C2",
        cls="ObjFlow",
        logic="and",
    )

    system.connect("C1", "out", "C2", "in")

    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        failure_effects={"v_flow_out": 2, "flow_out_max": 2},
        failure_param=1 / 10,
        repair_param=0.1,
    )

    return system


def test_system(the_system):
    # Run simulation
    the_system.isimu_start()

    assert the_system.comp["C1"].v_flow_out.value() == 0
    assert the_system.comp["C1"].flow_out_max.value() == -1

    # Ensure transitions are valid before proceeding
    transitions = the_system.isimu_fireable_transitions()
    assert len(transitions) == 1
    assert transitions[0].end_time == float("inf")

    the_system.isimu_set_transition(0, date=10)
    trans_fired = the_system.isimu_step_forward()

    assert len(trans_fired) == 1

    transitions = the_system.isimu_fireable_transitions()

    assert the_system.currentTime() == 10

    the_system.isimu_set_transition(0)
    the_system.isimu_step_forward()

    assert the_system.currentTime() == 10
    assert the_system.comp["C1"].v_flow_out.value() == 2
    assert the_system.comp["C1"].flow_out_max.value() == 2

    the_system.isimu_stop()


def test_delete(the_system):
    the_system.deleteSys()
    terminate_session()

