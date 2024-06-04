import pytest
from cod3s.pycatshoo.system import PycSystem, PycMCSimulationParam

@pytest.fixture
def pyc_system():
    return PycSystem(name="TestSystem")

def test_pyc_system_initialization(pyc_system):
    assert pyc_system.name() == "TestSystem"
    assert pyc_system.indicators == {}
    assert pyc_system.comp == {}

def test_add_component(pyc_system):
    comp_specs = {"name": "TestComponent", "cls": "PycComponent"}
    component = pyc_system.add_component(**comp_specs)
    assert component is not None
    assert component.name() == "TestComponent"
    assert "TestComponent" in pyc_system.comp

def test_add_indicator_var(pyc_system):
    indic_specs = {
        "name": "TestIndicator",
        "component": "TestComponent",
        "var": "TestVar",
        "stats": ["mean"]
    }
    pyc_system.comp["TestComponent"] = None  # Mock component existence
    indicators = pyc_system.add_indicator_var(**indic_specs)
    assert len(indicators) == 1
    assert indicators[0].name == "TestIndicator_TestVar"
    assert "TestIndicator_TestVar" in pyc_system.indicators

def test_prepare_simu(pyc_system):
    simu_params = PycMCSimulationParam(nb_runs=10, schedule=[100])
    pyc_system.prepare_simu(simu_params)
    assert pyc_system.getTMax() == 100
    assert pyc_system.getNbSeqToSim() == 10

def test_simulate(pyc_system):
    simu_params = PycMCSimulationParam(nb_runs=10, schedule=[100])
    pyc_system.simulate(simu_params)
    assert pyc_system.getNbSeqToSim() == 10
