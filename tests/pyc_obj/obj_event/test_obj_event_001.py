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
    )

    system.add_component(
        cls="ObjFMDelay",
        fm_name="frun",
        targets=["C1"],
        failure_effects={"flow_out_max": 2},
        failure_param=2,
    )

    # test avec attr + variable 
    # test cond avec liste de dict
    # attendu : liste de dict transforméee et liste de liste de dict 
    # test de l'operateur >=
    event_list = [
        {
            "name": "top_event1",  
            "cond" : [{"attr": "flow_out_max", "obj": "C1", "ope": ">=", "value": 2}],
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

    system.add_indicator(
        component="top_event1",
        attr_type="ST",
        attr_name="not_occ",
        stats=["mean"],
    )

    system.add_indicator(
        component="top_event1",
        attr_type="ST",
        attr_name="occ",
        stats=["mean"],
    )

    system.add_indicator(
        component="C1",
        attr_type="VAR",
        attr_name="flow_out_max",
        stats=["mean"],
    )

    return system


def test_system(the_system):

    assert "top_event1" in the_system.comp
    comp_event = the_system.comp["top_event1"]

    assert comp_event.name() == "top_event1"
    assert comp_event.className() == "ObjEvent"
    assert comp_event.metadata == {}
    automaton = comp_event.automata_d["ev"]
    assert len(automaton.transitions) == 2
    assert automaton.transitions[0].name == "occ"
    assert automaton.transitions[0].source == "not_occ"
    assert automaton.transitions[0].target == "occ"
    assert automaton.transitions[0].name == "not_occ"
    assert automaton.transitions[0].source == "occ"
    assert automaton.transitions[0].target == "not_occ"

    # Run simulation
    from cod3s.pycatshoo.system import PycMCSimulationParam
    schedule = [1, 2, 3, 4]
    simu_params = PycMCSimulationParam(
        nb_runs=1,
        schedule=schedule,
    )
    the_system.simulate(simu_params)

    # Check results
    assert "C1_flow_out_max" in the_system.indicators.keys()
    ind_C1= the_system.indicators["C1_flow_out_max"]
    val = ind_C1.values["values"].to_list()
    assert ind_C1.instants == schedule
    assert val[0] == -1
    assert val[1] == -1
    assert val[2] == 2
    assert val[3] == 2

    assert "top_event1_not_occ" in the_system.indicators.keys()
    ind_not_occ = the_system.indicators["top_event1_not_occ"]
    val = ind_not_occ.values["values"].to_list()
    assert ind_not_occ.instants == schedule
    assert val[0] == True
    assert val[1] == True
    assert val[2] == False
    assert val[3] == False

    assert "top_event1_occ" in the_system.indicators.keys()
    ind_occ = the_system.indicators["top_event1_occ"]
    val = ind_occ.values["values"].to_list()
    assert ind_occ.instants == schedule
    assert val[0] == False
    assert val[1] == False
    assert val[2] == True
    assert val[3] == True

def test_delete(the_system):
    the_system.deleteSys()
    cod3s.terminate_session()

