"""
Autor : LE GARREC Helene
Date : 2025-08-21
Description : Test for testing describe method
"""

import pytest
from cod3s import terminate_session
from cod3s.pycatshoo.system import PycSystem
from cod3s.pycatshoo.component import PycComponent
from cod3s.pycatshoo.automaton import PycAutomaton, PycTransition
import Pycatshoo as pyc


def test_component():
    system = PycSystem(name="System")
    comp_specs = {"name": "name_component", "cls": "PycComponent"}
    comp = system.add_component(**comp_specs)
    comp.addVariable("var_bool", pyc.TVarType.t_bool, True)
    comp.addVariable("var_int", pyc.TVarType.t_int, 2)

    assert comp is not None
    assert "name_component" in system.comp

    # Check results : description of a pycComponent instance
    expected_dict = {
                    "name": "name_component",
                    "label": "name_component",
                    "cls" : "PycComponent",
                    "description": "name_component",
                    "variables" : ['var_bool', 'var_int'],
                    "automatons" : {}
    } 
    print("expected_dict")
    print(expected_dict)
    print ("\n           ")
    print("comp.describe()")
    print(comp.describe())
    assert comp.describe() == expected_dict
    terminate_session()
