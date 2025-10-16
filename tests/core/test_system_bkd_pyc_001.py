import pytest

from cod3s.pycatshoo.system import PycSystem, PycMCSimulationParam
import Pycatshoo as pyc
from cod3s.kb import (
    ComponentClass,
    KB,
    InterfaceTemplate,
)

from cod3s.system import Connection, System
from pydantic import ValidationError


@pytest.fixture(scope="module")
def kb_cod3s():
    """
    Fixture that creates a KB with 3 component templates:
    - Source: with a flow interface of type output
    - Block: with a flow input interface and a flow output interface
    - Consumer: with a flow interface of type input
    """
    # Create component templates
    source_template = ComponentClass(
        class_name="Source",
        class_label="Source Component",
        class_description="Component that generates flow",
        interfaces=[
            InterfaceTemplate(name="flow_out", port_type="output", label="Flow Output"),
        ],
    )

    block_template = ComponentClass(
        class_name="Block",
        class_label="Block Component",
        class_description="Component that processes flow",
        interfaces=[
            InterfaceTemplate(name="flow_in", port_type="input", label="Flow Input"),
            InterfaceTemplate(name="flow_out", port_type="output", label="Flow Output"),
        ],
    )

    consumer_template = ComponentClass(
        class_name="Consumer",
        class_label="Consumer Component",
        class_description="Component that consumes flow",
        interfaces=[
            InterfaceTemplate(name="flow_in", port_type="input", label="Flow Input"),
        ],
    )

    # Create the KB
    kb = KB(
        name="test_flow_kb",
        label="Test Flow KB",
        description="KB for testing flow components",
        version="1.0.0",
    )

    # Add component templates
    kb.add_component_class(source_template)
    kb.add_component_class(block_template)
    kb.add_component_class(consumer_template)

    return kb


# @pytest.fixture(scope="module")
# def pyc_system():
#     return PycSystem(name="TestSystem")


# def test_pyc_system_initialization(pyc_system):
#     assert pyc_system.name() == "TestSystem"
#     assert pyc_system.indicators == {}
#     assert pyc_system.comp == {}


# def test_add_component(pyc_system):
#     comp_specs = {"name": "TestComponent", "cls": "PycComponent"}
#     component = pyc_system.add_component(**comp_specs)
#     component.addVariable("test_var", pyc.TVarType.t_bool, True)

#     assert component is not None
#     assert component.name() == "TestComponent"
#     assert component.variable("test_var").basename() == "test_var"
#     assert "TestComponent" in pyc_system.comp


# def test_add_indicator_var(pyc_system):
#     indic_specs = {
#         "name": "TestIndicator",
#         "component": "TestComponent",
#         "var": "test_var",
#         "stats": ["mean"],
#     }
#     indicators = pyc_system.add_indicator_var(**indic_specs)

#     assert len(indicators) == 1
#     assert indicators[0].name == "TestIndicator_test_var"
#     assert "TestIndicator_test_var" in pyc_system.indicators


# def test_simulate(pyc_system):
#     schedule = [1, 50, 100]
#     simu_params = PycMCSimulationParam(nb_runs=10, schedule=schedule)
#     pyc_system.simulate(simu_params)
#     assert (
#         pyc_system.indicators["TestIndicator_test_var"].values["instant"].to_list()
#         == schedule
#     )
#     assert pyc_system.indicators["TestIndicator_test_var"].values[
#         "values"
#     ].to_list() == [1] * len(schedule)


def test_flow_system_creation(kb_cod3s):
    """Test the creation of a system with flow components and their connections."""
    # Create a system
    system = System(name="flow_system", kb_name="test_flow_kb")

    # Add components
    source = system.add_component(kb_cod3s, "Source", "source1")
    block = system.add_component(kb_cod3s, "Block", "block1")
    consumer = system.add_component(kb_cod3s, "Consumer", "consumer1")

    # Connect components
    source_to_block = system.connect("source1", "flow_out", "block1", "flow_in")
    block_to_consumer = system.connect("block1", "flow_out", "consumer1", "flow_in")

    # Verify that components have been added
    assert len(system.components) == 3
    assert "source1" in system.components
    assert "block1" in system.components
    assert "consumer1" in system.components

    # Verify that connections have been created
    assert len(system.connections) == 2
    assert "source1_flow_out_to_block1_flow_in" in system.connections
    assert "block1_flow_out_to_consumer1_flow_in" in system.connections

    # Verify connection details
    assert source_to_block.component_source == "source1"
    assert source_to_block.interface_source == "flow_out"
    assert source_to_block.component_target == "block1"
    assert source_to_block.interface_target == "flow_in"

    assert block_to_consumer.component_source == "block1"
    assert block_to_consumer.interface_source == "flow_out"
    assert block_to_consumer.component_target == "consumer1"
    assert block_to_consumer.interface_target == "flow_in"


@pytest.mark.skipif(
    pytest.importorskip("Pycatshoo", reason="Pycatshoo not installed") is None,
    reason="Pycatshoo module not installed",
)
def test_kb_to_bkd_pycatshoo(kb_cod3s):
    """Test the to_bkd_pycatshoo method of ComponentInstance."""
    # Create a system with components
    system = System(name="flow_system", kb_name="test_flow_kb")
    source = system.add_component(kb_cod3s, "Source", "source1")

    system = system.to_bkd_pycatshoo()

    assert str(system.__class__) == "<class 'Pycatshoo.CSystem'>"
    assert (
        str(system.component("source1").__class__) == "<class 'Pycatshoo.CComponent'>"
    )

    import Pycatshoo

    Pycatshoo.CSystem.terminate()

    # Verify that the component was created with the correct name
    # assert pyc_component.name() == "source1"


# def test_delete(pyc_system):

#     pyc_system.deleteSys()
