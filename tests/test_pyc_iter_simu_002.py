import pytest
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

    return system


def test_system(the_system):
    # Run simulation
    the_system.isimu_start()

    # Ensure transitions are valid before proceeding
    transitions = the_system.isimu_fireable_transitions()
    the_system.isimu_set_transition(0, date=None, state_index=0)

    trans_fired = the_system.isimu_step_forward()

    assert len(trans_fired) == 1

    assert str(trans_fired[0].model_dump()) == str(
        {
            "cls": "PycTransition",
            "name": "toss",
            "source": "toss",
            "target": [{"state": "even", "prob": 0.6}, {"state": "odd", "prob": 0.4}],
            "occ_law": {"cls": "InstOccDistribution**", "probs": [0.6]},
            "end_time": 0.0,
            "condition": None,
            "comp_name": "Coin",
            "comp_classname": "PycComponent",
            "is_interruptible": True,
        }
    )

    transitions = the_system.isimu_fireable_transitions()

    assert len(transitions) == 1

    assert str(transitions[0].model_dump()) == str(
        {
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
    )


def test_delete(the_system):
    the_system.deleteSys()
