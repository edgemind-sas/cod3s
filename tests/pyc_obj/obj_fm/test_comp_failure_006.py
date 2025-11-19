import pytest
import cod3s
from cod3s.pycatshoo.system import PycSystem
from pyc_obj.kb_test import ObjFlow 
from pyc_obj.kb_test import ObjFlow2I1O

@pytest.fixture(scope="module")
def the_system():
    system = PycSystem(name="Sys")

    system.pdmp_manager = system.addPDMPManager("pdmp_manager")


    system.add_component(
        name="CA",
        cls="ObjFlow",
        flow_type="f1",
    )

    system.add_component(
        name="CB",
        cls="ObjFlow",
        flow_type="f2",
    )

    system.add_component(
        name="C1",
        cls="ObjFlow2I1O",
        flow_type_in1="f1",
        flow_type_in2="f2",
        flow_type_out="f3",
    )

    system.add_component(
        name="C2",
        cls="ObjFlow2I1O",
        flow_type_in1="f1",
        flow_type_in2="f2",
        flow_type_out="f3",
    )

    system.add_component(
        name="C3",
        cls="ObjFlow2I1O",
        flow_type_in1="f1",
        flow_type_in2="f2",
        flow_type_out="f3",
    )

    system.connect("CA", "f1_out", "C1", "f1_in")
    system.connect("CB", "f2_out", "C1", "f2_in")
    system.connect("CA", "f1_out", "C2", "f1_in")
    system.connect("CB", "f2_out", "C2", "f2_in")
    system.connect("CA", "f1_out", "C3", "f1_in")
    system.connect("CB", "f2_out", "C3", "f2_in")


    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["CA", "CB"],
        failure_effects={"v_flow_out": 1, "flow_available_out": False},
        failure_param=[0.1, 0.1],
        repair_param=[0.1, 0.1],
    )

    return system


def test_system(the_system):

    # Run simulation
    the_system.isimu_start()

    for cname in ["CA", "CB"]:
        assert the_system.comp[cname].v_flow_out.value() == 0
        assert the_system.comp[cname].flow_available_out.value() is True
    for cname in ["C1", "C2", "C3"]:
        assert the_system.comp[cname].v_flow_out.value() == 0
        assert the_system.comp[cname].flow_available_out.value() is True

    # Ensure transitions are valid before proceeding
    transitions = the_system.isimu_fireable_transitions()
    assert len(transitions) == 3
    assert transitions[0].end_time == float("inf")
    the_system.isimu_set_transition(0, date=10)
    trans_fired = the_system.isimu_step_forward()

    assert len(trans_fired) == 1

    tf = trans_fired[0]
    assert tf._bkd.distLaw().parameter(0) == 0.1
    assert tf._bkd.target(0).basename() == "occ__cc_1"
    assert tf._bkd.parent().name() == "CX__frun"
    assert the_system.comp["CA"].v_flow_out.value() == 1
    assert the_system.comp["CA"].flow_available_out.value() is False
    assert the_system.comp["CB"].v_flow_out.value() == 0 
    assert the_system.comp["CB"].flow_available_out.value() is True
    for cname in ["C1", "C2", "C3"]:
        assert the_system.comp[cname].v_flow_out.value() == 1


def test_delete(the_system):
    the_system.deleteSys()
    cod3s.terminate_session()

