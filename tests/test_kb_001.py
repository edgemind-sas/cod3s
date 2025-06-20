import pytest
from cod3s.kb import InterfaceTemplate, AttributeTemplate, ComponentClass, KB
from pydantic import ValidationError


class TestInterfaceTemplate:
    def test_create_interface_template(self):
        """Test the creation of a basic interface template."""
        interface = InterfaceTemplate(
            name="test_interface", port_type="input", label="Test Interface"
        )
        assert interface.label == "Test Interface"
        assert interface.name == "test_interface"
        assert interface.port_type == "input"
        assert interface.description is None
        assert interface.metadata == {}
        assert interface.component_authorized == []

    def test_create_interface_template_with_all_fields(self):
        """Test the creation of an interface template with all fields."""
        interface = InterfaceTemplate(
            name="test_interface",
            port_type="output",
            label="Test Interface",
            description="A test interface",
            metadata={"key": "value", "tags": ["tag1", "tag2"]},
            component_authorized=["ComponentA", "ComponentB"],
        )
        assert interface.name == "test_interface"
        assert interface.label == "Test Interface"
        assert interface.description == "A test interface"
        assert interface.metadata == {"key": "value", "tags": ["tag1", "tag2"]}
        assert interface.component_authorized == ["ComponentA", "ComponentB"]


class TestAttributeTemplate:
    def test_create_bool_attribute(self):
        """Test the creation of a boolean attribute."""
        attr = AttributeTemplate(
            name="test_bool", type="bool", value_default=True, value_current=False
        )
        assert attr.name == "test_bool"
        assert attr.type == "bool"
        assert attr.value_default is True
        assert attr.value_current is False

    def test_create_int_attribute(self):
        """Test the creation of an integer attribute."""
        attr = AttributeTemplate(
            name="test_int", type="int", value_default=10, value_current=20
        )
        assert attr.name == "test_int"
        assert attr.type == "int"
        assert attr.value_default == 10
        assert attr.value_current == 20

    def test_create_float_attribute(self):
        """Test the creation of a float attribute."""
        attr = AttributeTemplate(
            name="test_float", type="float", value_default=10.5, value_current=20.5
        )
        assert attr.name == "test_float"
        assert attr.type == "float"
        assert attr.value_default == 10.5
        assert attr.value_current == 20.5

    def test_create_enum_attribute(self):
        """Test the creation of an enum attribute."""
        attr = AttributeTemplate(
            name="test_enum",
            type=["option1", "option2", "option3"],
            value_default="option1",
            value_current="option2",
        )
        assert attr.name == "test_enum"
        assert attr.type == ["option1", "option2", "option3"]
        assert attr.value_default == "option1"
        assert attr.value_current == "option2"

    def test_invalid_type_string(self):
        """Test validation error for invalid type string."""
        with pytest.raises(ValueError):
            AttributeTemplate(name="test_invalid", type="invalid_type")

    def test_empty_enum_list(self):
        """Test validation error for empty enum list."""
        with pytest.raises(ValidationError):
            AttributeTemplate(name="test_empty_enum", type=[])

    def test_non_unique_enum_values(self):
        """Test validation error for non-unique enum values."""
        with pytest.raises(ValidationError):
            AttributeTemplate(
                name="test_duplicate_enum", type=["option1", "option1", "option2"]
            )

    def test_non_string_enum_values(self):
        """Test validation error for non-string enum values."""
        with pytest.raises(ValueError):
            AttributeTemplate(
                name="test_non_string_enum", type=["option1", 123, "option2"]
            )

    def test_invalid_bool_value(self):
        """Test validation error for invalid boolean value."""
        with pytest.raises(ValidationError):
            AttributeTemplate(
                name="test_invalid_bool", type="bool", value_default="not_a_bool"
            )

    def test_invalid_int_value(self):
        """Test validation error for invalid integer value."""
        with pytest.raises(ValidationError):
            AttributeTemplate(
                name="test_invalid_int", type="int", value_default="not_an_int"
            )

    def test_invalid_float_value(self):
        """Test validation error for invalid float value."""
        with pytest.raises(ValidationError):
            AttributeTemplate(
                name="test_invalid_float", type="float", value_default="not_a_float"
            )

    def test_invalid_enum_value(self):
        """Test validation error for invalid enum value."""
        with pytest.raises(ValidationError):
            AttributeTemplate(
                name="test_invalid_enum",
                type=["option1", "option2"],
                value_default="option3",
            )

    def test_default_value_initialization_bool(self):
        """Test automatic initialization of default value for bool type."""
        attr = AttributeTemplate(name="test_bool", type="bool")
        assert attr.value_default is False
        assert attr.value_current is False

    def test_default_value_initialization_int(self):
        """Test automatic initialization of default value for int type."""
        attr = AttributeTemplate(name="test_int", type="int")
        assert attr.value_default == 0
        assert attr.value_current == 0

    def test_default_value_initialization_float(self):
        """Test automatic initialization of default value for float type."""
        attr = AttributeTemplate(name="test_float", type="float")
        assert attr.value_default == 0.0
        assert attr.value_current == 0.0

    def test_default_value_initialization_enum(self):
        """Test automatic initialization of default value for enum type."""
        attr = AttributeTemplate(
            name="test_enum", type=["option1", "option2", "option3"]
        )
        assert attr.value_default == "option1"
        assert attr.value_current == "option1"

    def test_current_value_initialization(self):
        """Test automatic initialization of current value based on default value."""
        attr = AttributeTemplate(name="test_attr", type="int", value_default=42)
        assert attr.value_current == 42


class TestComponentClass:
    def test_create_component_class(self):
        """Test the creation of a basic component template."""
        component = ComponentClass(
            class_name="test_component", class_label="Test Component"
        )
        assert component.class_name == "test_component"
        assert component.class_label == "Test Component"
        assert component.class_description is None
        assert component.groups is None
        assert component.attributes is None
        assert component.interfaces == []
        assert component.metadata == {}

    def test_create_component_class_with_all_fields(self):
        """Test the creation of a component template with all fields."""
        # Create attributes
        attr1 = AttributeTemplate(name="attr1", type="bool", value_default=True)
        attr2 = AttributeTemplate(
            name="attr2", type=["option1", "option2"], value_default="option1"
        )

        # Create interfaces
        interface1 = InterfaceTemplate(
            name="interface1",
            port_type="input",
            label="Interface 1",
            component_authorized=["ComponentA"],
        )
        interface2 = InterfaceTemplate(
            name="interface2",
            port_type="output",
            label="Interface 2",
            component_authorized=["ComponentB", "ComponentC"],
        )

        # Create component
        component = ComponentClass(
            class_name="test_component",
            class_name_bkd={"pycatshoo": "TestComponentBackend"},
            class_label="Test Component",
            class_description="A test component",
            groups=["Group1", "Group2"],
            attributes={"attr1": attr1, "attr2": attr2},
            interfaces=[interface1, interface2],
            metadata={"key": "value", "tags": ["tag1", "tag2"]},
        )

        assert component.class_name == "test_component"
        assert component.class_name_bkd == {"pycatshoo": "TestComponentBackend"}
        assert component.class_label == "Test Component"
        assert component.class_description == "A test component"
        assert component.groups == ["Group1", "Group2"]

        # Check attributes
        assert len(component.attributes) == 2
        assert component.attributes["attr1"].name == "attr1"
        assert component.attributes["attr1"].type == "bool"
        assert component.attributes["attr2"].name == "attr2"
        assert component.attributes["attr2"].type == ["option1", "option2"]

        # Check interfaces
        assert len(component.interfaces) == 2
        assert component.interfaces[0].name == "interface1"
        assert component.interfaces[0].label == "Interface 1"
        assert component.interfaces[1].name == "interface2"
        assert component.interfaces[1].label == "Interface 2"

        # Check metadata
        assert component.metadata == {"key": "value", "tags": ["tag1", "tag2"]}


class TestKB:
    def test_create_kb(self):
        """Test the creation of a basic knowledge base."""
        kb = KB(name="test_kb")
        assert kb.name == "test_kb"
        assert kb.label is None
        assert kb.description is None
        assert kb.version is None
        assert kb.component_classes == {}

    def test_create_kb_with_all_fields(self):
        """Test the creation of a knowledge base with all fields."""
        # Create a component template
        component = ComponentClass(
            class_name="test_component", class_label="Test Component"
        )

        # Create KB
        kb = KB(
            name="test_kb",
            label="Test KB",
            description="A test knowledge base",
            version="1.0.0",
            component_classes={"test_component": component},
        )

        assert kb.name == "test_kb"
        assert kb.label == "Test KB"
        assert kb.description == "A test knowledge base"
        assert kb.version == "1.0.0"
        assert len(kb.component_classes) == 1
        assert kb.component_classes["test_component"].class_label == "Test Component"

    def test_add_component_class(self):
        """Test adding a component template to a knowledge base."""
        # Create KB
        kb = KB(name="test_kb")

        # Create component templates
        component1 = ComponentClass(class_name="component1", class_label="Component 1")
        component2 = ComponentClass(class_name="component2", class_label="Component 2")

        # Add components to KB using the new method
        kb.add_component_class(component1)
        kb.add_component_class(component2)

        assert len(kb.component_classes) == 2
        assert kb.component_classes["component1"].class_name == "component1"
        assert kb.component_classes["component1"].class_label == "Component 1"
        assert kb.component_classes["component2"].class_name == "component2"
        assert kb.component_classes["component2"].class_label == "Component 2"

    def test_add_component_class_with_dict(self):
        """Test adding a component template using a dictionary."""
        # Create KB
        kb = KB(name="test_kb")

        # Add a component template using a dictionary
        template_dict = {
            "class_name": "dict_template",
            "class_label": "Dictionary Template",
            "class_description": "A template created from a dictionary",
        }

        added_template = kb.add_component_class(template_dict)

        # Check that the template was added correctly
        assert len(kb.component_classes) == 1
        assert kb.component_classes["dict_template"].class_name == "dict_template"
        assert (
            kb.component_classes["dict_template"].class_label == "Dictionary Template"
        )
        assert (
            kb.component_classes["dict_template"].class_description
            == "A template created from a dictionary"
        )
        assert added_template == kb.component_classes["dict_template"]

    def test_add_component_class_duplicate_error(self):
        """Test that adding a duplicate template raises an error when upsert=False."""
        # Create KB with a template
        kb = KB(name="test_kb")
        template = ComponentClass(
            class_name="test_template", class_label="Test Template"
        )
        kb.add_component_class(template)

        # Try to add a template with the same name
        duplicate_template = ComponentClass(
            class_name="test_template", class_label="Duplicate Template"
        )

        # Check that an error is raised
        with pytest.raises(ValueError):
            kb.add_component_class(duplicate_template, upsert=False)

    def test_add_component_class_upsert(self):
        """Test updating an existing template when upsert=True."""
        # Create KB with a template
        kb = KB(name="test_kb")
        template = ComponentClass(
            class_name="test_template", class_label="Test Template"
        )
        kb.add_component_class(template)

        # Create an updated version of the template
        updated_template = ComponentClass(
            class_name="test_template",
            class_label="Updated Template",
            class_description="Updated description",
        )

        # Update the template
        result = kb.add_component_class(updated_template, upsert=True)

        # Check that the template was updated
        assert len(kb.component_classes) == 1
        assert kb.component_classes["test_template"].class_name == "test_template"
        assert kb.component_classes["test_template"].class_label == "Updated Template"
        assert (
            kb.component_classes["test_template"].class_description
            == "Updated description"
        )
        assert result == updated_template

    def test_add_component_class_invalid_type(self):
        """Test that adding a template with an invalid type raises an error."""
        # Create KB
        kb = KB(name="test_kb")

        # Try to add a template with an invalid type
        with pytest.raises(TypeError):
            kb.add_component_class("not_a_template")


class TestComponentInstance:
    def test_create_component_instance_from_template(self):
        """Test creating a component instance from a template."""
        # Create a component template
        template = ComponentClass(
            class_name="test_template",
            class_label="Test Template",
            class_description="A test template",
        )

        # Create an instance from the template
        instance = template.create_instance("test_instance")

        assert instance.class_label == "Test Template"
        assert instance.class_description == "A test template"
        assert instance.attributes == {}
        assert instance.interfaces == []
        assert instance.init_parameters == {}
        assert instance.metadata == {}

    def test_create_component_instance_with_overrides(self):
        """Test creating a component instance with overridden values."""
        # Create attributes
        attr1 = AttributeTemplate(name="attr1", type="bool", value_default=True)

        # Create interfaces
        interface1 = InterfaceTemplate(
            name="interface1", port_type="input", label="Interface 1"
        )

        # Create a component template
        template = ComponentClass(
            class_name="test_template",
            class_label="Template label",
            class_description="A test template",
            attributes={"attr1": attr1},
            interfaces=[interface1],
            metadata={"key": "value"},
        )

        # Create an instance with overrides
        instance = template.create_instance(
            "test_instance",
            label="Instance label",
            description="Custom description",
            init_parameters={"param1": "value1"},
            metadata={"new_key": "new_value"},
        )

        assert instance.name == "test_instance"
        assert instance.class_label == "Template label"
        assert instance.label == "Instance label"
        assert instance.class_description == "A test template"
        assert instance.description == "Custom description"
        assert instance.init_parameters == {"param1": "value1"}
        assert "attr1" in instance.attributes
        assert instance.attributes["attr1"].name == "attr1"
        assert instance.attributes["attr1"].type == "bool"
        assert len(instance.interfaces) == 1
        assert instance.interfaces[0].name == "interface1"
        assert instance.metadata == {"key": "value", "new_key": "new_value"}

    def test_component_instance_deep_copy(self):
        """Test that component instance gets deep copies of template objects."""
        # Create attributes
        attr1 = AttributeTemplate(
            name="attr1",
            type="bool",
            value_default=True,
            value_current=True,  # Explicitement True pour le test
        )

        # Create interfaces
        interface1 = InterfaceTemplate(
            name="interface1", port_type="input", label="Interface 1"
        )

        # Create a component template
        template = ComponentClass(
            class_name="test_template",
            class_label="Test Template",
            attributes={"attr1": attr1},
            interfaces=[interface1],
        )

        # Create an instance
        instance = template.create_instance("test_instance")

        # Modify the instance's attribute and interface
        instance.attributes["attr1"].value_current = False
        instance.interfaces[0].description = "Modified description"

        # Check that the template's objects weren't modified
        assert template.attributes["attr1"].value_current is True
        assert template.interfaces[0].description is None

    def test_interfaces_d_property(self):
        """Test the interfaces_d property of ComponentClass."""
        # Create interfaces
        interface1 = InterfaceTemplate(
            name="interface1", port_type="input", label="Interface 1"
        )
        interface2 = InterfaceTemplate(
            name="interface2", port_type="output", label="Interface 2"
        )

        # Create a component template with interfaces
        template = ComponentClass(
            class_name="test_template",
            class_label="Test Template",
            interfaces=[interface1, interface2],
        )

        # Test the interfaces_d property
        interfaces_dict = template.interfaces_d

        assert len(interfaces_dict) == 2
        assert "interface1" in interfaces_dict
        assert "interface2" in interfaces_dict
        assert interfaces_dict["interface1"] == interface1
        assert interfaces_dict["interface2"] == interface2

    def test_add_interface_with_object(self):
        """Test adding an interface using an InterfaceTemplate object."""
        # Create a component template
        template = ComponentClass(
            class_name="test_template",
            class_label="Test Template",
        )

        # Create an interface
        interface = InterfaceTemplate(
            name="test_interface", port_type="input", label="Test Interface"
        )

        # Add the interface to the template
        added_interface = template.add_interface(interface)

        # Check that the interface was added
        assert len(template.interfaces) == 1
        assert template.interfaces[0] == interface
        assert added_interface == interface

    def test_add_interface_with_dict(self):
        """Test adding an interface using a dictionary of specifications."""
        # Create a component template
        template = ComponentClass(
            class_name="test_template",
            class_label="Test Template",
        )

        # Add an interface using a dictionary
        interface_dict = {
            "name": "test_interface",
            "port_type": "output",
            "label": "Test Interface",
            "description": "A test interface",
        }

        added_interface = template.add_interface(interface_dict)

        # Check that the interface was added
        assert len(template.interfaces) == 1
        assert template.interfaces[0].name == "test_interface"
        assert template.interfaces[0].port_type == "output"
        assert template.interfaces[0].label == "Test Interface"
        assert template.interfaces[0].description == "A test interface"
        assert added_interface == template.interfaces[0]

    def test_add_interface_duplicate_error(self):
        """Test that adding a duplicate interface raises an error when upsert=False."""
        # Create a component template with an interface
        interface = InterfaceTemplate(
            name="test_interface", port_type="input", label="Test Interface"
        )

        template = ComponentClass(
            class_name="test_template",
            class_label="Test Template",
            interfaces=[interface],
        )

        # Try to add an interface with the same name and port_type
        duplicate_interface = InterfaceTemplate(
            name="test_interface", port_type="input", label="Duplicate Interface"
        )

        # Check that an error is raised
        with pytest.raises(ValueError):
            template.add_interface(duplicate_interface, upsert=False)

    def test_add_interface_upsert(self):
        """Test updating an existing interface when upsert=True."""
        # Create a component template with an interface
        interface = InterfaceTemplate(
            name="test_interface", port_type="input", label="Test Interface"
        )

        template = ComponentClass(
            class_name="test_template",
            class_label="Test Template",
            interfaces=[interface],
        )

        # Create an updated version of the interface
        updated_interface = InterfaceTemplate(
            name="test_interface",
            port_type="input",
            label="Updated Interface",
            description="Updated description",
        )

        # Update the interface
        result = template.add_interface(updated_interface, upsert=True)

        # Check that the interface was updated
        assert len(template.interfaces) == 1
        assert template.interfaces[0].name == "test_interface"
        assert template.interfaces[0].port_type == "input"
        assert template.interfaces[0].label == "Updated Interface"
        assert template.interfaces[0].description == "Updated description"
        assert result == updated_interface

    def test_add_interface_different_port_type(self):
        """Test adding an interface with the same name but different port_type."""
        # Create a component template with an interface
        interface = InterfaceTemplate(
            name="test_interface", port_type="input", label="Input Interface"
        )

        template = ComponentClass(
            class_name="test_template",
            class_label="Test Template",
            interfaces=[interface],
        )

        # Add an interface with the same name but different port_type
        output_interface = InterfaceTemplate(
            name="test_interface", port_type="output", label="Output Interface"
        )

        # This should succeed because the port_type is different
        template.add_interface(output_interface)

        # Check that both interfaces were added
        assert len(template.interfaces) == 2
        assert template.interfaces[0].name == "test_interface"
        assert template.interfaces[0].port_type == "input"
        assert template.interfaces[1].name == "test_interface"
        assert template.interfaces[1].port_type == "output"

    def test_add_interface_invalid_type(self):
        """Test that adding an interface with an invalid type raises an error."""
        # Create a component template
        template = ComponentClass(
            class_name="test_template",
            class_label="Test Template",
        )

        # Try to add an interface with an invalid type
        with pytest.raises(TypeError):
            template.add_interface("not_an_interface")
