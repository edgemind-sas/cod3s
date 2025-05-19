import pytest
from cod3s.kb import InterfaceTemplate, AttributeTemplate, ComponentTemplate, KB
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
        with pytest.raises(ValueError) as excinfo:
            AttributeTemplate(name="test_invalid", type="invalid_type")
        assert "String type must be one of: bool, int, float" in str(excinfo.value)

    def test_empty_enum_list(self):
        """Test validation error for empty enum list."""
        with pytest.raises(ValidationError) as excinfo:
            AttributeTemplate(name="test_empty_enum", type=[])
        assert "Enum list cannot be empty" in str(excinfo.value)

    def test_non_unique_enum_values(self):
        """Test validation error for non-unique enum values."""
        with pytest.raises(ValidationError) as excinfo:
            AttributeTemplate(
                name="test_duplicate_enum", type=["option1", "option1", "option2"]
            )
        assert "Enum values must be unique" in str(excinfo.value)

    def test_non_string_enum_values(self):
        """Test validation error for non-string enum values."""
        with pytest.raises(ValueError) as excinfo:
            AttributeTemplate(
                name="test_non_string_enum", type=["option1", 123, "option2"]
            )
        assert "All items in enum list must be strings" in str(excinfo.value)

    def test_invalid_bool_value(self):
        """Test validation error for invalid boolean value."""
        with pytest.raises(ValidationError) as excinfo:
            AttributeTemplate(
                name="test_invalid_bool", type="bool", value_default="not_a_bool"
            )
        assert "Default value must be boolean for bool type" in str(excinfo.value)

    def test_invalid_int_value(self):
        """Test validation error for invalid integer value."""
        with pytest.raises(ValidationError) as excinfo:
            AttributeTemplate(
                name="test_invalid_int", type="int", value_default="not_an_int"
            )
        assert "Default value must be integer for int type" in str(excinfo.value)

    def test_invalid_float_value(self):
        """Test validation error for invalid float value."""
        with pytest.raises(ValidationError) as excinfo:
            AttributeTemplate(
                name="test_invalid_float", type="float", value_default="not_a_float"
            )
        assert "Default value must be numeric for float type" in str(excinfo.value)

    def test_invalid_enum_value(self):
        """Test validation error for invalid enum value."""
        with pytest.raises(ValidationError) as excinfo:
            AttributeTemplate(
                name="test_invalid_enum",
                type=["option1", "option2"],
                value_default="option3",
            )
        assert "Default value must be one of the enum values" in str(excinfo.value)

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


class TestComponentTemplate:
    def test_create_component_template(self):
        """Test the creation of a basic component template."""
        component = ComponentTemplate(name="test_component", label="Test Component")
        assert component.name == "test_component"
        assert component.label == "Test Component"
        assert component.description is None
        assert component.groups is None
        assert component.attributes is None
        assert component.interfaces == []
        assert component.metadata == {}

    def test_create_component_template_with_all_fields(self):
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
        component = ComponentTemplate(
            name="test_component",
            class_name_bkd="TestComponentBackend",
            label="Test Component",
            description="A test component",
            groups=["Group1", "Group2"],
            attributes={"attr1": attr1, "attr2": attr2},
            interfaces=[interface1, interface2],
            metadata={"key": "value", "tags": ["tag1", "tag2"]},
        )

        assert component.name == "test_component"
        assert component.class_name_bkd == "TestComponentBackend"
        assert component.label == "Test Component"
        assert component.description == "A test component"
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
        assert kb.component_templates == {}

    def test_create_kb_with_all_fields(self):
        """Test the creation of a knowledge base with all fields."""
        # Create a component template
        component = ComponentTemplate(name="test_component", label="Test Component")

        # Create KB
        kb = KB(
            name="test_kb",
            label="Test KB",
            description="A test knowledge base",
            version="1.0.0",
            component_templates={"test_component": component},
        )

        assert kb.name == "test_kb"
        assert kb.label == "Test KB"
        assert kb.description == "A test knowledge base"
        assert kb.version == "1.0.0"
        assert len(kb.component_templates) == 1
        assert kb.component_templates["test_component"].name == "test_component"
        assert kb.component_templates["test_component"].label == "Test Component"

    def test_add_component_template(self):
        """Test adding a component template to a knowledge base."""
        # Create KB
        kb = KB(name="test_kb")

        # Create component templates
        component1 = ComponentTemplate(name="component1", label="Component 1")
        component2 = ComponentTemplate(name="component2", label="Component 2")

        # Add components to KB
        kb.component_templates["component1"] = component1
        kb.component_templates["component2"] = component2

        assert len(kb.component_templates) == 2
        assert kb.component_templates["component1"].name == "component1"
        assert kb.component_templates["component1"].label == "Component 1"
        assert kb.component_templates["component2"].name == "component2"
        assert kb.component_templates["component2"].label == "Component 2"


class TestComponentInstance:
    def test_create_component_instance_from_template(self):
        """Test creating a component instance from a template."""
        # Create a component template
        template = ComponentTemplate(
            name="test_template", label="Test Template", description="A test template"
        )

        # Create an instance from the template
        instance = template.create_instance("test_instance")

        assert instance.name == "test_instance"
        assert instance.template == template
        assert instance.label == "Test Template"
        assert instance.description == "A test template"
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
        template = ComponentTemplate(
            name="test_template",
            label="Test Template",
            description="A test template",
            attributes={"attr1": attr1},
            interfaces=[interface1],
            metadata={"key": "value"},
        )

        # Create an instance with overrides
        instance = template.create_instance(
            "test_instance",
            label="Custom Label",
            description="Custom description",
            init_parameters={"param1": "value1"},
            metadata={"new_key": "new_value"},
        )

        assert instance.name == "test_instance"
        assert instance.template == template
        assert instance.label == "Custom Label"
        assert instance.description == "Custom description"
        assert instance.init_parameters == {"param1": "value1"}
        assert "attr1" in instance.attributes
        assert instance.attributes["attr1"].name == "attr1"
        assert instance.attributes["attr1"].type == "bool"
        assert len(instance.interfaces) == 1
        assert instance.interfaces[0].name == "interface1"
        assert instance.metadata == {"new_key": "new_value"}

    def test_component_instance_deep_copy(self):
        """Test that component instance gets deep copies of template objects."""
        # Create attributes
        attr1 = AttributeTemplate(
            name="attr1",
            type="bool",
            value_default=True,
            value_current=None,  # Explicitement None pour le test
        )

        # Create interfaces
        interface1 = InterfaceTemplate(
            name="interface1", port_type="input", label="Interface 1"
        )

        # Create a component template
        template = ComponentTemplate(
            name="test_template",
            label="Test Template",
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
