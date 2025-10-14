import pytest
import cod3s
from cod3s.pycatshoo.system import PycSystem
from bk_ObjFlow import ObjFlow


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
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1", "C2"],
        failure_effects={"flow_in_max": 3, "flow_available_out": False},
        failure_param=[0.1, 0.1],
        # repair_effects={"flow_in_max": -1},
        repair_param=[0.1, 0.1],
    )

    return system


def test_system(the_system):
    # Run simulation
    # the_system.traceVariable("#.*", 2)
    the_system.isimu_start()

    assert the_system.comp["C1"].flow_in_max.value() == -1
    assert the_system.comp["C1"].flow_available_out.value() is True
    assert the_system.comp["C2"].flow_in_max.value() == -1
    assert the_system.comp["C2"].flow_available_out.value() is True

    # Ensure transitions are valid before proceeding
    transitions = the_system.isimu_fireable_transitions()
    assert len(transitions) == 3
    assert transitions[0].end_time == float("inf")

    # __import__("ipdb").set_trace()

    the_system.isimu_set_transition(0, date=10)
    trans_fired = the_system.isimu_step_forward()

    assert len(trans_fired) == 1
    tf = trans_fired[0]
    assert tf._bkd.distLaw().parameter(0) == 0.1
    assert tf._bkd.target(0).basename() == "occ__cc_1"
    assert tf._bkd.parent().name() == "CX__frun"
    assert the_system.comp["C1"].flow_in_max.value() == 3
    assert the_system.comp["C1"].flow_available_out.value() is False
    assert the_system.comp["C2"].flow_in_max.value() == -1
    assert the_system.comp["C2"].flow_available_out.value() is True

    transitions = the_system.isimu_fireable_transitions()

    assert the_system.currentTime() == 10
    the_system.isimu_set_transition(2)
    trans_fired = the_system.isimu_step_forward()
    assert len(trans_fired) == 1
    assert the_system.currentTime() == 10
    assert trans_fired[0]._bkd.distLaw().parameter(0) == 0.1
    assert trans_fired[0]._bkd.target(0).basename() == "occ__cc_2"
    assert trans_fired[0]._bkd.parent().name() == "CX__frun"

    assert the_system.comp["C1"].flow_in_max.value() == 3
    assert the_system.comp["C1"].flow_available_out.value() is False
    assert the_system.comp["C2"].flow_in_max.value() == 3
    assert the_system.comp["C2"].flow_available_out.value() is False

    the_system.isimu_stop()


def test_delete(the_system):
    the_system.deleteSys()
    cod3s.terminate_session()
