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
    """PyCATSHOO singleton — module-scoped so the test below sees the same
    system. Always release the singleton on teardown so subsequent test
    modules get a clean slate, regardless of which assertion (if any)
    failed inside the test."""
    system = PycSystem(name="CoinToss")

    # Create coin toss component
    coin_comp = system.add_component(name="Coin", cls="PycComponent")

    # Create automaton for coin toss
    toss_automaton = PycAutomaton(
        name="aut_toss",
        states=["odd", "even", "toss"],
        init_state="toss",
        transitions=[
            {
                "name": "toss",
                "source": "toss",
                "target": [
                    {"state": "even", "prob": 0.6},
                    {"state": "odd"},
                ],
            },
            {
                "name": "odd_toss",
                "source": "odd",
                "target": "toss",
                "is_interruptible": False,
                "occ_law": {"cls": "delay", "time": 5},
            },
            {
                "name": "even_toss",
                "source": "even",
                "target": "toss",
                "is_interruptible": False,
                "occ_law": {"cls": "delay", "time": 2},
            },
        ],
    )

    # Add automaton to coin_comp
    toss_automaton.update_bkd(coin_comp)

    yield system
    terminate_session()


def test_system(the_system):

    assert the_system.get_simulation_mode() == "stop"

    # Run simulation
    the_system.isimu_start()

    assert the_system.get_simulation_mode() == "interactive"

    # Ensure transitions are valid before proceeding
    transitions = the_system.isimu_fireable_transitions()

    the_system.isimu_set_transition(0, date=None, state_index=0)

    trans_fired = the_system.isimu_step_forward()
    assert len(trans_fired) == 1

    expected_dump = {
        "cls": "PycTransition",
        "name": "toss",
        "source": "toss",
        "target": [
            {
                "state": "even",
                "prob": 0.6,
                "effects": {},
                "effects_format": "dict",
            },
            {
                "state": "odd",
                "prob": 0.4,
                "effects": {},
                "effects_format": "dict",
            },
        ],
        "occ_law": {"cls": "InstOccDistribution", "probs": [0.6, 0.4]},
        "end_time": 0.0,
        "condition": None,
        "comp_name": "Coin",
        "comp_classname": "PycComponent",
        "is_interruptible": True,
    }

    assert trans_fired[0].model_dump() == expected_dump

    transitions = the_system.isimu_fireable_transitions()

    assert len(transitions) == 1

    expected_dump = {
        "cls": "PycTransition",
        "name": "even_toss",
        "source": "even",
        "target": "toss",
        "occ_law": {"cls": "DelayOccDistribution", "time": 2.0},
        "end_time": 2.0,
        "condition": None,
        "comp_name": "Coin",
        "comp_classname": "PycComponent",
        "is_interruptible": False,
    }

    assert transitions[0].model_dump() == expected_dump


