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
        ],
    )

    # Add automaton to coin_comp
    automaton.update_bkd(comp)

    # Add indicator for current state
    system.add_indicator(
        component="C",
        attr_type="ST",
        attr_name="nok",
        stats=["mean", "P25", "P75"],
        measure="sojourn-time",
    )

    system.add_indicator(
        name_pattern="{component}_st_{attr_name}_sj_stdev",
        component="C",
        attr_type="ST",
        attr_name="nok",
        stats=["stddev"],
        measure="sojourn-time",
    )

    return system


def test_system(the_system):
    # Run simulation
    schedule = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    simu_params = PycMCSimulationParam(
        nb_runs=10000,
        schedule=schedule,
        seed=56000,
        rng="yarn5",
        rng_bloc_size=1000,
    )
    the_system.simulate(simu_params)

    # Check results
    assert "C_st_nok_sj_stdev" in the_system.indicators.keys()

    assert "C_nok_sojourn-time" in the_system.indicators.keys()
    ind_val = the_system.indicators["C_nok_sojourn-time"]

    # Check that we have results for all scheduled times
    assert ind_val.instants == schedule
    assert ind_val.values["values"].to_list() == [
        0.09172133356332779,
        0.35074132680892944,
        0.7433022260665894,
        1.246079683303833,
        1.841827154159546,
        2.5133447647094727,
        3.244401454925537,
        4.0253190994262695,
        4.846054553985596,
        5.698519706726074,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.1645256131887436,
        1.1645256280899048,
        2.1645255088806152,
        3.1645255088806152,
        0.0,
        0.5600500702857971,
        1.5600500106811523,
        2.5600500106811523,
        3.5600500106811523,
        4.560050010681152,
        5.560050010681152,
        6.560050010681152,
        7.560050010681152,
        8.560050010681152,
    ]
    # for mean_value in results["values"]:
    #     assert ind_even_val["values"] == [
    #         0.45 <= mean_value <= 0.55
    #     ), f"Mean value {mean_value} is not close to 0.5"


def test_delete(the_system):
    the_system.deleteSys()
