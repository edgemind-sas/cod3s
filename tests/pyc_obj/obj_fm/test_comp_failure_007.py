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
        name="T1",
        cls="ObjFlow2I1O",
        flow_type_in1="f1",
        flow_type_in2="f2",
        flow_type_out="f3",
        logic="and",
        var_prod_cond=[
        "f1",
        "f2",
        ],
    )

    system.add_component(
        name="T2",
        cls="ObjFlow2I1O",
        flow_type_in1="f1",
        flow_type_in2="f2",
        flow_type_out="f3",
        logic="and",
    )

    system.add_component(
        name="T3",
        cls="ObjFlow2I1O",
        flow_type_in1="f1",
        flow_type_in2="f2",
        flow_type_out="f3",
        logic="and",
    )

    system.add_component(
        name="T4",
        cls="ObjFlow2I1O",
        flow_type_in1="f1",
        flow_type_in2="f2",
        flow_type_out="f3",
    )

    system.connect("CA", "f1_out", "T1", "f1_in")
    system.connect("CB", "f2_out", "T1", "f2_in")
    system.connect("CA", "f1_out", "T2", "f1_in")
    system.connect("CB", "f2_out", "T2", "f2_in")
    system.connect("CA", "f1_out", "T3", "f1_in")

    system.connect("CA", "f1_out", "T4", "f1_in")
    system.connect("CB", "f2_out", "T4", "f2_in")


    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["CA", "CB"],
        failure_effects={"v_flow_out": 1, "flow_available_out": False},
        failure_param=[0.1, 0.1],
        repair_param=[0.1, 0.1],
    )

    failure_cond =[[{"obj": "CA", "attr": "flow_available_out", "value": True},
                    {"obj": "CB", "attr": "flow_available_out", "value": True}]]
    
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["T1", "T2", "T3", "T4"],
        target_name="TXX",
        failure_cond=failure_cond,
        failure_effects={"v_flow_out": 3, "flow_available_out": False},
        failure_param=[0.1, 0, 0, 0.0001],
        repair_param=[0.0001, 0.001, 0.01, 0.1],
    )

    return system


def test_system(the_system):

    # the_system.traceVariable(".", 3)
    # the_system.traceAutomaton(".", 1)

    assert "TXX__frun" in the_system.comp
    assert len(the_system.comp["TXX__frun"].automata_d) == 15

    # Run simulation
    the_system.isimu_start()

    for cname in ["CA", "CB"]:
        assert the_system.comp[cname].v_flow_out.value() == 0
        assert the_system.comp[cname].flow_available_out.value() is True

    for cname in ["T1", "T2", "T3", "T4"]:
        assert the_system.comp[cname].v_flow_out.value() == 0
        assert the_system.comp[cname].flow_available_out.value() is True

    # Ensure transitions are valid before proceeding
    transitions = the_system.isimu_fireable_transitions()
    assert len(transitions) == 8 

    the_system.isimu_set_transition("CX__frun.occ__cc_12")
    trans_fired = the_system.isimu_step_forward()

    assert len(trans_fired) == 1
    tf = trans_fired[0]
    assert tf.end_time == 0
    assert tf._bkd.distLaw().parameter(0) == 0.1
    assert tf._bkd.target(0).basename() == "occ__cc_12"
    assert tf._bkd.parent().name() == "CX__frun"
    for cname in ["CA", "CB"]:
        assert the_system.comp[cname].v_flow_out.value() == 1
        assert the_system.comp[cname].flow_available_out.value() is False

    for cname in ["T1", "T2", "T4"]:
        assert the_system.comp[cname].v_flow_out.value() == 2
        assert the_system.comp[cname].flow_available_out.value() is True
    assert the_system.comp["T3"].v_flow_out.value() == 1 # flux f2 no connect
    assert the_system.comp["T3"].flow_available_out.value() is True

    transitions = the_system.isimu_fireable_transitions()

    assert the_system.currentTime() == 0
    assert len(transitions) == 3 # TXX__frun unavailable ( CA.flow_available_out = False, CB.flow_available_out = False)
    the_system.isimu_set_transition("CX__frun.occ__cc_2")
    trans_fired = the_system.isimu_step_forward()

    transitions = the_system.isimu_fireable_transitions()

    assert len(transitions) == 3 # TXX__frun unavailable ( CA.flow_available_out = False, CB.flow_available_out = False)
    the_system.isimu_set_transition("CX__frun.rep__cc_12")
    trans_fired = the_system.isimu_step_forward()
    transitions = the_system.isimu_fireable_transitions()

    assert the_system.currentTime() == 0
    assert the_system.comp["CA"].v_flow_out.value() == 1
    assert the_system.comp["CA"].flow_available_out.value() is True
    assert the_system.comp["CB"].v_flow_out.value() == 1
    assert the_system.comp["CB"].flow_available_out.value() is False

    for cname in ["T1", "T2", "T4"]:
        assert the_system.comp[cname].v_flow_out.value() == 2
        assert the_system.comp[cname].flow_available_out.value() is True
    assert the_system.comp["T3"].v_flow_out.value() == 1 # flux f2 no connect
    assert the_system.comp["T3"].flow_available_out.value() is True



def test_delete(the_system):
    the_system.deleteSys()
    cod3s.terminate_session()

