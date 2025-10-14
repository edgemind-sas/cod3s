"""
Autor : LE GARREC Helene
Date : 2025-08-25
Description : Test for testing describe method
"""

import pytest
from cod3s import terminate_session
from cod3s.pycatshoo.system import PycSystem
from cod3s.pycatshoo.component import PycComponent
from cod3s.pycatshoo.automaton import PycAutomaton, PycTransition
import Pycatshoo as pyc


def test_component_withAutom():
    system = PycSystem(name="Sys")

    comp_specs = {"name": "name_component", "cls": "PycComponent"}
    comp = system.add_component(**comp_specs)
    comp.addVariable("var_double", pyc.TVarType.t_double, 0.5)

    comp.add_automaton(
        name="aut_test",
        states=["state1", "state2", "state3"],
        init_state="state2",
        transitions=[
            {
                "name": "state3",
                "source": "state3",
                "target": [
                    {"state": "state2"},
                    {"state": "state1", "prob": 0.5},
                ],
            },
            {
                "name": "state1_state3",
                "source": "state1",
                "target": "state3",
                "is_interruptible": False,
                "occ_law": {"cls": "delay", "time": 2},
            },
            {
                "name": "state2_state3",
                "source": "state2",
                "target": "state3",
                "is_interruptible": False,
                "occ_law": {"cls": "delay", "time": 6},
            },
        ],
    )

    assert comp is not None
    assert "name_component" in system.comp

    # Check results : description of a pycComponent instance
    expected_dict = {
        "name": "name_component",
        "label": "name_component",
        "cls": "PycComponent",
        "description": "name_component",
        "variables": ["var_double"],
        "automatons": {
            "aut_test": {
                "cls": "PycAutomaton",
                "name": "aut_test",
                "states": [
                    {
                        "cls": "StateModel",
                        "name": "state1",
                        # "bkd" : None
                    },
                    {
                        "cls": "StateModel",
                        "name": "state2",
                        # "bkd" : None
                    },
                    {
                        "cls": "StateModel",
                        "name": "state3",
                        # "bkd" : None
                    },
                ],
                "init_state": "state2",
                "transitions": [
                    {
                        "cls": "PycTransition",
                        "name": "state3",
                        "source": "state3",
                        "target": [
                            {"state": "state2", "prob": 0.5},
                            {"state": "state1", "prob": 0.5},
                        ],
                        "occ_law": None,
                        "end_time": None,
                        "condition": None,
                        "comp_name": None,
                        "comp_classname": None,
                        "is_interruptible": True,
                    },
                    {
                        "cls": "PycTransition",
                        "name": "state1_state3",
                        "source": "state1",
                        "target": "state3",
                        "occ_law": {"cls": "DelayOccDistribution", "time": 2},
                        "end_time": None,
                        "condition": None,
                        "comp_name": None,
                        "comp_classname": None,
                        "is_interruptible": False,
                    },
                    {
                        "cls": "PycTransition",
                        "name": "state2_state3",
                        "source": "state2",
                        "target": "state3",
                        "occ_law": {"cls": "DelayOccDistribution", "time": 6},
                        "end_time": None,
                        "condition": None,
                        "comp_name": None,
                        "comp_classname": None,
                        "is_interruptible": False,
                    },
                ],
                # "bkd": None,
                "id": None,
                "comp_name": None,
            },
        },
    }

    assert comp.describe() == expected_dict

    terminate_session()


def test_automaton():

    # Create automaton
    the_automaton = PycAutomaton(
        name="aut_ok_nok",
        states=["s_ok", "s_nok"],
        init_state="s_ok",
        transitions=[
            {
                "name": "ok_nok",
                "source": "s_ok",
                "target": "s_nok",
                "is_interruptible": False,
                "occ_law": {"cls": "exp", "rate": 1.0 / 5.0},
            },
            {
                "name": "nok_ok",
                "source": "s_nok",
                "target": "s_ok",
                "is_interruptible": False,
                "occ_law": {"cls": "exp", "rate": 1.0 / 2.0},
            },
        ],
    )

    # Check results : description of a pycAutomaton instance
    autom_dict = the_automaton.describe()
    expected_dict = {
        "cls": "PycAutomaton",
        "name": "aut_ok_nok",
        "states": [
            {
                "name": "s_ok",
                "cls": "StateModel",
                # "bkd" : None
            },
            {
                "name": "s_nok",
                "cls": "StateModel",
                # "bkd" : None
            },
        ],
        "init_state": "s_ok",
        "transitions": [
            {
                "cls": "PycTransition",
                "name": "ok_nok",
                "source": "s_ok",
                "target": "s_nok",
                "occ_law": {"cls": "ExpOccDistribution", "rate": 0.2},
                "end_time": None,
                "condition": None,
                "comp_name": None,
                "comp_classname": None,
                "is_interruptible": False,
            },
            {
                "cls": "PycTransition",
                "name": "nok_ok",
                "source": "s_nok",
                "target": "s_ok",
                "occ_law": {"cls": "ExpOccDistribution", "rate": 0.5},
                "end_time": None,
                "condition": None,
                "comp_name": None,
                "comp_classname": None,
                "is_interruptible": False,
            },
        ],
        # "bkd": None,
        "id": None,
        "comp_name": None,
    }

    assert autom_dict == expected_dict
    terminate_session()
