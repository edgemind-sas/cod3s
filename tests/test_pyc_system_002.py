import pytest
from cod3s.pycatshoo.system import PycSystem, PycMCSimulationParam
from cod3s.pycatshoo.component import PycComponent
from cod3s.pycatshoo.automaton import (
    PycAutomaton,
    PycTransition,
    ExpOccDistribution,
    InstOccDistribution,
)
import Pycatshoo as pyc


@pytest.fixture(scope="module")
def coin_toss_system():
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
                # "target": "odd",
                # "is_interruptible": False,
                # "occ_law": {"cls": "delay", "time": 5},
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

    # Add indicator for current state
    system.add_indicator_state(
        name="CoinState", component="Coin", state="even|odd", stats=["mean"]
    )

    return system


def test_coin_toss_system(coin_toss_system):
    # Run simulation
    schedule = [1, 100]
    simu_params = PycMCSimulationParam(nb_runs=10000, schedule=schedule, seed=56000)
    coin_toss_system.simulate(simu_params)

    # Check results
    ind_even_val = coin_toss_system.indicators["CoinState_even"].values

    # Check that we have results for all scheduled times
    assert ind_even_val["instant"].to_list() == schedule

    for mean_value in results["values"]:
        assert ind_even_val["values"] == [
            0.45 <= mean_value <= 0.55
        ), f"Mean value {mean_value} is not close to 0.5"


def test_delete(coin_toss_system):
    coin_toss_system.deleteSys()
