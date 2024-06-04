import pytest
from cod3s.pycatshoo.system import PycSystem, PycMCSimulationParam
import Pycatshoo as pyc


@pytest.fixture(scope="module")
def pyc_system():
    return PycSystem(name="TestSystem")


def test_pyc_system_initialization(pyc_system):
    assert pyc_system.name() == "TestSystem"
    assert pyc_system.indicators == {}
    assert pyc_system.comp == {}


def test_add_component(pyc_system):
    comp_specs = {"name": "TestComponent", "cls": "PycComponent"}
    component = pyc_system.add_component(**comp_specs)
    component.addVariable("test_var", pyc.TVarType.t_bool, True)

    assert component is not None
    assert component.name() == "TestComponent"
    assert component.variable("test_var").basename() == "test_var"
    assert "TestComponent" in pyc_system.comp


def test_add_indicator_var(pyc_system):
    indic_specs = {
        "name": "TestIndicator",
        "component": "TestComponent",
        "var": "test_var",
        "stats": ["mean"],
    }
    indicators = pyc_system.add_indicator_var(**indic_specs)

    assert len(indicators) == 1
    assert indicators[0].name == "TestIndicator_test_var"
    assert "TestIndicator_test_var" in pyc_system.indicators


def test_simulate(pyc_system):
    schedule = [1, 50, 100]
    simu_params = PycMCSimulationParam(nb_runs=10, schedule=schedule)
    pyc_system.simulate(simu_params)
    assert (
        pyc_system.indicators["TestIndicator_test_var"].values["instant"].to_list()
        == schedule
    )
    assert pyc_system.indicators["TestIndicator_test_var"].values[
        "values"
    ].to_list() == [1] * len(schedule)
