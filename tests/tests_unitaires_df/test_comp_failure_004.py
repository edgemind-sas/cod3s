import pytest
import cod3s
from cod3s.pycatshoo.system import PycSystem
from bk_ObjFlow import ObjFlow 


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
    )

    system.add_component(
        name="T2",
        cls="ObjFlow2I1O",
        flow_type_in1="f1",
        flow_type_in2="f2",
        flow_type_out="f3",
    )

    system.add_component(
        name="T3",
        cls="ObjFlow2I1O",
        flow_type_in1="f1",
        flow_type_in2="f2",
        flow_type_out="f3",
        logic="and"
    )

    system.add_component(
        name="T4",
        cls="ObjFlow2I1O",
        flow_type_in1="f1",
        flow_type_in2="f2",
        flow_type_out="f3",
    )

    system.connect("CA", "f1_out", "T1", "f1_in")
    system.connect("CA", "f1_out", "T2", "f1_in")

    system.connect("CB", "f2_out", "T3", "f2_in")
    system.connect("CB", "f2_out", "T4", "f2_in")

    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["CA", "CB"],
        failure_effects={"v_flow_out": 2},
        failure_param=[0.1, 0.2],
        repair_param=[0.1, 0.1],
    )

    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["T1", "T2", "T3", "T4"],
        target_name="TXX",
        failure_effects={"v_flow_out": 1},
        failure_param=[0.1, 0.01, 0.001, 0.0001],
        repair_param=[0.0001, 0.001, 0.01, 0.1],
    )

    return system


def test_system(the_system):

    assert "TXX__frun" in the_system.comp
    assert len(the_system.comp["TXX__frun"].automata_d) == 15

    # Run simulation
    the_system.isimu_start()

    assert the_system.comp["CA"].v_flow_out.value() == 0
    assert the_system.comp["CB"].v_flow_out.value() == 0
    assert the_system.comp["T1"].v_flow_out.value() == 0
    assert the_system.comp["T2"].v_flow_out.value() == 0
    assert the_system.comp["T3"].v_flow_out.value() == 0
    assert the_system.comp["T4"].v_flow_out.value() == 0

    # Ensure transitions are valid before proceeding
    transitions = the_system.isimu_fireable_transitions()
    assert len(transitions) == 18

    the_system.isimu_set_transition("CX__frun.occ__cc_1")
    trans_fired = the_system.isimu_step_forward()

    assert len(trans_fired) == 1
    tf = trans_fired[0]
    assert tf._bkd.distLaw().parameter(0) == 0.1
    assert tf._bkd.target(0).basename() == "occ__cc_1"
    assert tf._bkd.parent().name() == "CX__frun"
    assert the_system.comp["CA"].v_flow_out.value() == 2
    assert the_system.comp["CB"].v_flow_out.value() == 0

    transitions = the_system.isimu_fireable_transitions()

    assert the_system.currentTime() == 0
    assert len(transitions) == 18
    assert the_system.comp["T1"].v_flow_out.value() == 2
    assert the_system.comp["T2"].v_flow_out.value() == 2
    assert the_system.comp["T3"].v_flow_out.value() == 0
    assert the_system.comp["T4"].v_flow_out.value() == 0

    the_system.isimu_set_transition("TXX__frun.occ__cc_4")
    trans_fired = the_system.isimu_step_forward()
    transitions = the_system.isimu_fireable_transitions()
    assert len(transitions) == 18
    assert the_system.comp["T1"].v_flow_out.value() == 2
    assert the_system.comp["T2"].v_flow_out.value() == 2
    assert the_system.comp["T3"].v_flow_out.value() == 0
    assert the_system.comp["T4"].v_flow_out.value() == 1



def test_delete(the_system):
    the_system.deleteSys()
    cod3s.terminate_session()
