import pytest
from cod3s import terminate_session
from cod3s.pycatshoo.system import PycSystem, PycMCSimulationParam
from cod3s.pycatshoo.component import PycComponent
from cod3s.pycatshoo.automaton import (
    PycAutomaton,
    PycTransition,
    ExpOccDistribution,
    InstOccDistribution,
)


@pytest.fixture(scope="module")
def the_system():
    system = PycSystem(name="Sys")

    # Create coin toss component
    comp = system.add_component(name="C", cls="PycComponent")

    # Create automaton for coin toss
    automaton = PycAutomaton(
        name="aut_ok_nok",
        states=["ok", "nok"],
        init_state="ok",
        transitions=[
            {
                "name": "ok_nok",
                "source": "ok",
                "target": "nok",
                "is_interruptible": False,
                "occ_law": {"cls": "exp", "rate": 1 / 5},
            },
            {
                "name": "nok_ok",
                "source": "nok",
                "target": "ok",
                "is_interruptible": False,
                "occ_law": {"cls": "exp", "rate": 1 / 1},
            },
        ],
    )

    # Add automaton to coin_comp
    automaton.update_bkd(comp)

    return system


def test_system(the_system):
    # Run simulation
    the_system.isimu_start()

    # Ensure transitions are valid before proceeding
    transitions = the_system.isimu_fireable_transitions()
    assert len(transitions) == 1
    # str(transitions[0].model_dump())
    # __import__("ipdb").set_trace()
    assert (
        str(transitions[0].model_dump())
        == "{'cls': 'PycTransition', 'name': 'ok_nok', 'source': 'ok', 'target': 'nok', 'occ_law': {'cls': 'ExpOccDistribution', 'rate': 0.2}, 'end_time': inf, 'condition': None, 'comp_name': 'C', 'comp_classname': 'PycComponent', 'is_interruptible': False}"
    )


def test_delete(the_system):
    terminate_session()
