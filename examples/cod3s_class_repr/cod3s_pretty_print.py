#!/usr/bin/env python3
"""
Example script demonstrating the __repr__ and __str__ methods of COD3S classes.
This script creates instances of various COD3S classes and displays their string representations.
"""

import sys
import os

# Add the parent directory to the path so we can import cod3s
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from cod3s.kb import (
    InterfaceTemplate,
    AttributeTemplate,
    ComponentClass,
    ComponentInstance,
    KB,
)
from cod3s.system import Connection, System


def main():
    """Create and display string representations of COD3S classes."""
    print("\n=== COD3S Class Representations ===\n")

    # Create attribute templates
    print("Creating attribute templates...")
    bool_attr = AttributeTemplate(
        name="power_state", type="bool", value_default=True, value_current=False
    )

    int_attr = AttributeTemplate(
        name="temperature", type="int", value_default=25, value_current=30
    )

    enum_attr = AttributeTemplate(
        name="mode", type=["off", "standby", "active"], value_default="standby"
    )

    print(f"\n{repr(bool_attr)}")
    print(f"\n{bool_attr}")

    print(f"\n{repr(int_attr)}")
    print(f"\n{int_attr}")

    print(f"\n{repr(enum_attr)}")
    print(f"\n{enum_attr}")

    # Create interface templates
    print("\n\nCreating interface templates...")
    input_interface = InterfaceTemplate(
        name="power_input",
        port_type="input",
        label="Power Input",
        description="Power supply input interface",
        component_authorized=["PowerSupply", "Battery"],
    )

    output_interface = InterfaceTemplate(
        name="data_output",
        port_type="output",
        label="Data Output",
        description="Data transmission output interface",
    )

    print(f"\n{repr(input_interface)}")
    print(f"\n{input_interface}")

    print(f"\n{repr(output_interface)}")
    print(f"\n{output_interface}")

    # Create component template
    print("\n\nCreating component template...")
    component_class = ComponentClass(
        class_name="sensor",
        class_label="Temperature Sensor",
        class_description="A sensor that measures temperature",
        groups=["Sensors", "IoT"],
        attributes={
            "power_state": bool_attr,
            "temperature": int_attr,
            "mode": enum_attr,
        },
        interfaces=[input_interface, output_interface],
        metadata={"manufacturer": "SensorCorp", "model": "TS-2000"},
    )

    print(f"\n{repr(component_class)}")
    print(f"\n{component_class}")

    # Create component instance
    print("\n\nCreating component instance...")
    component_instance = component_class.create_instance(
        "living_room_sensor",
        label="Living Room Temperature Sensor",
        description="Temperature sensor located in the living room",
        init_parameters={"calibration": 1.02},
        metadata={"room": "R1"},
    )

    print(f"\n{repr(component_instance)}")
    print(f"\n{component_instance}")

    # Create knowledge base
    print("\n\nCreating knowledge base...")
    kb = KB(
        name="home_automation_kb",
        label="Home Automation Knowledge Base",
        description="Knowledge base for home automation components",
        version="1.0.0",
        component_classes={"sensor": component_class},
    )

    print(f"\n{repr(kb)}")
    print(f"\n{kb}")

    # Create connection
    print("\n\nCreating connection...")
    connection = Connection(
        component_source="living_room_sensor",
        interface_source="data_output",
        component_target="controller",
        interface_target="data_input",
        init_parameters={"protocol": "mqtt"},
    )

    print(f"\n{repr(connection)}")
    print(f"\n{connection}")

    # Create system
    print("\n\nCreating system...")
    system = System(
        name="home_automation_system",
        kb_name=kb.name,
        kb_version=">0.1.0",
        label="Home Automation System",
        description="A system for home automation",
        version="0.4.1",
        components={"living_room_sensor": component_instance},
        connections={"sensor_to_controller": connection},
    )

    print(f"\n{repr(system)}")
    print(f"\n{system}")


if __name__ == "__main__":
    main()
