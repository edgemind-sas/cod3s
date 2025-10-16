import pytest
import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow 

@pytest.fixture(scope="module")
def the_system():
    system = PycSystem(name="Sys")

    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(
        name="CA",
        cls="ObjFlow",
        flow_in_max=2,
        v_flow_available=True,
    )

    system.add_component(
        name="CB",
        cls="ObjFlow",
        flow_in_max=2,
        v_flow_available=True,
    )

    system.add_component(
        cls="ObjFMExp",
        fm_name="frun_1",
        targets=["CA", "CB"],
        failure_effects={"flow_in_max": 1, "flow_available_out": False},
        failure_param=[0.1, 0.1],
        repair_param=[0.1, 0.1],
    )

    system.add_component(
        cls="ObjFMExp",
        fm_name="frun_2",
        targets=["CA", "CB"],
        failure_effects={"flow_in_max": 3},
        failure_param=[0.1, 0.1],
        repair_param=[0.1, 0.1],
    )

    return system


def test_system(the_system):

    assert "CX__frun_1" in the_system.comp
    assert len(the_system.comp["CX__frun_1"].automata()) == 3
    assert "CX__frun_2" in the_system.comp
    assert len(the_system.comp["CX__frun_2"].automata()) == 3

    # Run simulation
    the_system.isimu_start()

    assert the_system.comp["CA"].flow_in_max.value() == 2
    assert the_system.comp["CA"].flow_available_out.value() is True
    assert the_system.comp["CB"].flow_in_max.value() == 2
    assert the_system.comp["CB"].flow_available_out.value() is True

    # Ensure transitions are valid before proceeding
    transitions = the_system.isimu_fireable_transitions()
    assert len(transitions) == 6
    # __import__("ipdb").set_trace()
    the_system.isimu_set_transition("CX__frun_1.occ__cc_1")
    trans_fired = the_system.isimu_step_forward()
    assert len(trans_fired) == 1
    tf = trans_fired[0]
    assert tf._bkd.distLaw().parameter(0) == 0.1
    assert tf._bkd.target(0).basename() == "occ__cc_1"
    assert tf._bkd.parent().name() == "CX__frun_1"
    assert the_system.comp["CA"].flow_in_max.value() == 1
    assert the_system.comp["CA"].flow_available_out.value() is False
    assert the_system.comp["CB"].flow_in_max.value() == 2
    assert the_system.comp["CB"].flow_available_out.value() is True

    the_system.isimu_set_transition("CX__frun_2.occ__cc_2")
    trans_fired = the_system.isimu_step_forward()
    assert len(trans_fired) == 1
    tf = trans_fired[0]
    assert tf._bkd.distLaw().parameter(0) == 0.1
    assert tf._bkd.target(0).basename() == "occ__cc_2"
    assert tf._bkd.parent().name() == "CX__frun_2"
    assert the_system.comp["CA"].flow_in_max.value() == 1
    assert the_system.comp["CA"].flow_available_out.value() is False
    assert the_system.comp["CB"].flow_in_max.value() == 3
    assert the_system.comp["CB"].flow_available_out.value() is True

def test_delete(the_system):
    the_system.deleteSys()
    cod3s.terminate_session()

