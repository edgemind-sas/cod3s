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
    automaton1 = PycAutomaton(
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

    automaton2 = PycAutomaton(
        name="aut_stop_start",
        states=["stop", "start"],
        init_state="stop",
        transitions=[
            {
                "name": "stop_start",
                "source": "stop",
                "target": "start",
                "is_interruptible": False,
                "occ_law": {"cls": "exp", "rate": 1 / 10},
            },
            {
                "name": "start_stop",
                "source": "start",
                "target": "stop",
                "is_interruptible": False,
                "occ_law": {"cls": "exp", "rate": 1 / 100},
            },
        ],
    )

    # Add automaton to coin_comp
    automaton1.update_bkd(comp)
    automaton2.update_bkd(comp)

    return system


def test_system(the_system):
    # Run simulation
    the_system.isimu_start()

    # Ensure transitions are valid before proceeding

    # the_system.isimu_show_fireable_transitions()

    fireable_trans = the_system.isimu_fireable_transitions()
    assert len(fireable_trans) == 2

    the_system.isimu_set_transition(0)
    trans_fired = the_system.isimu_step_forward()

    assert len(trans_fired) == 1

    expected_dump = {
        "cls": "PycTransition",
        "name": "ok_nok",
        "source": "ok",
        "target": "nok",
        "occ_law": {"cls": "ExpOccDistribution", "rate": 0.2},
        "end_time": 0.0,
        "condition": None,
        "comp_name": "C",
        "comp_classname": "PycComponent",
        "is_interruptible": False,
    }

    assert trans_fired[0].model_dump() == expected_dump

    the_system.isimu_step_backward()

    fireable_trans_after = the_system.isimu_fireable_transitions()
    assert str(fireable_trans) == str(fireable_trans_after)

    the_system.isimu_set_transition(1)
    trans_fired = the_system.isimu_step_forward()

    assert len(trans_fired) == 1

    expected_dump = {
        "cls": "PycTransition",
        "name": "stop_start",
        "source": "stop",
        "target": "start",
        "occ_law": {"cls": "ExpOccDistribution", "rate": 0.1},
        "end_time": 0.0,
        "condition": None,
        "comp_name": "C",
        "comp_classname": "PycComponent",
        "is_interruptible": False,
    }

    assert trans_fired[0].model_dump() == expected_dump


def test_delete(the_system):
    terminate_session()
