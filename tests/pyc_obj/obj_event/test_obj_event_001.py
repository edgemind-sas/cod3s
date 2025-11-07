import pytest
import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow 

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

    # test avec attr + variable + liste de dict
    # attendu : liste de dict transforméee et liste de liste de dict 
    # test de l'operateur <=
    event_list = [
        {
            "name": "top_event1",  
            "cond" : [{"attr": "flow_out_max", "obj": "C1", "ope": ">=", "value": 1.5}],
            "inner_logic" :all,
            "outer_logic":any,
            "tempo_occ" :0,
            "tempo_not_occ" : 0,
            "event_aut_name": "ev",
            "occ_state_name": "occ",
            "not_occ_state_name": "not_occ",
            "enabled": True
        }
    ]

    system.add_events(event_list)
    system.add_targets([{"name": "top_event1", "enabled": True}])  

    return system


def test_system(the_system):

    assert "top_event1" in the_system.comp
    comp_event = the_system.comp["top_event1"]

    assert comp_event.name() == "top_event1"
    assert comp_event.className() == "ObjEvent"
    assert comp_event.metadata == {}
    automaton = comp_event.automata_d["ev"]
    assert automaton.transitions[0].name == "occ"
    assert automaton.transitions[0].source == "not_occ"
    assert automaton.transitions[0].target == "occ"

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
    assert len(transitions) == 2

    the_system.isimu_set_transition(0)
    assert the_system.comp["C1"].v_flow_out.value() == 2
    assert the_system.comp["C1"].flow_out_max.value() == 2

    the_system.isimu_stop()


def test_delete(the_system):
    the_system.deleteSys()
    cod3s.terminate_session()

