import pytest
from cod3s.kb import (
    ComponentTemplate,
    KB,
    InterfaceTemplate,
)

from cod3s.system import Connection, System
from pydantic import ValidationError


class TestConnection:
    def test_create_connection(self):
        """Test the creation of a basic connection."""
        connection = Connection(
            component_source="source_component",
            interface_source="output_interface",
            component_target="target_component",
            interface_target="input_interface",
        )
        assert connection.component_source == "source_component"
        assert connection.interface_source == "output_interface"
        assert connection.component_target == "target_component"
        assert connection.interface_target == "input_interface"
        assert connection.init_parameters == {}
        assert connection.metadata == {}

    def test_create_connection_with_all_fields(self):
        """Test the creation of a connection with all fields."""
        connection = Connection(
            component_source="source_component",
            interface_source="output_interface",
            component_target="target_component",
            interface_target="input_interface",
            init_parameters={"protocol": "mqtt", "qos": 1},
            metadata={"created_by": "test", "priority": "high"},
        )
        assert connection.component_source == "source_component"
        assert connection.interface_source == "output_interface"
        assert connection.component_target == "target_component"
        assert connection.interface_target == "input_interface"
        assert connection.init_parameters == {"protocol": "mqtt", "qos": 1}
        assert connection.metadata == {"created_by": "test", "priority": "high"}


class TestSystem:
    def test_create_system(self):
        """Test the creation of a basic system."""
        # Créer une KB
        kb = KB(name="test_kb")

        # Créer un système
        system = System(name="test_system", kb_name=kb.name)

        assert system.name == "test_system"
        assert system.kb_name == kb.name
        assert system.label is None
        assert system.description is None
        assert system.version is None
        assert system.components == {}
        assert system.connections == {}
        assert system.metadata == {}

    def test_create_system_with_all_fields(self):
        """Test the creation of a system with all fields."""
        # Créer une KB avec un template de composant
        template = ComponentTemplate(name="test_template", label="Test Template")
        kb = KB(name="test_kb", component_templates={"test_template": template})

        # Créer une instance de composant
        instance = template.create_instance("test_instance")

        # Créer une connexion
        connection = Connection(
            component_source="test_instance",
            interface_source="output",
            component_target="other_instance",
            interface_target="input",
        )

        # Créer un système avec tous les champs
        system = System(
            name="test_system",
            kb_name=kb.name,
            label="Test System",
            description="A test system",
            version="1.0.0",
            components={"test_instance": instance},
            connections={"test_connection": connection},
            metadata={"domain": "test", "tags": ["tag1", "tag2"]},
        )

        assert system.name == "test_system"
        assert system.kb_name == kb.name
        assert system.label == "Test System"
        assert system.description == "A test system"
        assert system.version == "1.0.0"
        assert len(system.components) == 1
        assert system.components["test_instance"] == instance
        assert len(system.connections) == 1
        assert system.connections["test_connection"] == connection
        assert system.metadata == {"domain": "test", "tags": ["tag1", "tag2"]}

    def test_add_component(self):
        """Test adding a component to a system."""
        # Créer une KB avec un template
        template = ComponentTemplate(name="test_template", label="Test Template")
        kb = KB(name="test_kb", component_templates={"test_template": template})

        # Créer un système
        system = System(name="test_system", kb_name=kb.name)

        # Créer et ajouter des instances de composants
        instance1 = template.create_instance("instance1")
        instance2 = template.create_instance("instance2")

        system.components["instance1"] = instance1
        system.components["instance2"] = instance2

        assert len(system.components) == 2
        assert system.components["instance1"] == instance1
        assert system.components["instance2"] == instance2

    def test_add_connection(self):
        """Test adding a connection to a system."""
        # Créer une KB
        kb = KB(name="test_kb")

        # Créer un système
        system = System(name="test_system", kb_name=kb.name)

        # Créer et ajouter des connexions
        connection1 = Connection(
            component_source="comp1",
            interface_source="out1",
            component_target="comp2",
            interface_target="in1",
        )

        connection2 = Connection(
            component_source="comp2",
            interface_source="out1",
            component_target="comp3",
            interface_target="in1",
        )

        system.connections["conn1"] = connection1
        system.connections["conn2"] = connection2

        assert len(system.connections) == 2
        assert system.connections["conn1"] == connection1
        assert system.connections["conn2"] == connection2

    def test_add_component(self):
        """Test the create_instance method to create a component instance."""
        # Créer une KB avec un template
        template = ComponentTemplate(name="test_template", label="Test Template")
        kb = KB(name="test_kb", component_templates={"test_template": template})

        # Créer un système
        system = System(name="test_system", kb_name="test_kb", kb_version="1.0.0")

        # Créer une instance avec la méthode add_component
        instance = system.add_component(
            kb=kb,
            template_name="test_template",
            instance_name="test_instance",
            label="Custom Label",
            description="Custom description",
        )

        # Vérifier que l'instance a été créée correctement
        assert instance.name == "test_instance"
        assert instance.template == template
        assert instance.label == "Custom Label"
        assert instance.description == "Custom description"

        # Vérifier que l'instance a été ajoutée au système
        assert len(system.components) == 1
        assert "test_instance" in system.components
        assert system.components["test_instance"] == instance

    def test_check_kb(self):
        """Test the check_kb method."""
        # Créer une KB
        kb = KB(name="test_kb", version="1.0.0")

        # Créer un système avec version compatible
        system = System(name="test_system", kb_name="test_kb", kb_version=">=0.9.0")

        # Vérifier que la vérification passe
        system.check_kb(kb)

        # Créer un système avec version incompatible
        system_incompatible = System(
            name="test_system", kb_name="test_kb", kb_version=">2.0.0"
        )

        # Vérifier que l'erreur est levée
        with pytest.raises(ValueError):
            system_incompatible.check_kb(kb)

    def test_add_component_kb_mismatch(self):
        """Test that add_component raises an error if the KB doesn't match."""
        # Créer une KB avec un nom différent
        kb = KB(name="wrong_kb")

        # Créer un système
        system = System(name="test_system", kb_name="test_kb", kb_version="1.0.0")

        # Vérifier que l'erreur est levée
        with pytest.raises(ValueError):
            system.add_component(
                kb=kb, template_name="test_template", instance_name="test_instance"
            )

    def test_add_component_template_not_found(self):
        """Test that add_component raises an error if the template doesn't exist."""
        # Créer une KB sans template
        kb = KB(name="test_kb")

        # Créer un système
        system = System(name="test_system", kb_name="test_kb", kb_version="1.0.0")

        # Vérifier que l'erreur est levée
        with pytest.raises(ValueError):
            system.add_component(
                kb=kb,
                template_name="nonexistent_template",
                instance_name="test_instance",
            )

    def test_system_kb_version_compatibility(self):
        """Test different forms of KB version compatibility."""
        # Créer des KBs avec différentes versions
        kb_100 = KB(name="test_kb", version="1.0.0")
        kb_110 = KB(name="test_kb", version="1.1.0")
        kb_200 = KB(name="test_kb", version="2.0.0")

        # Test avec égalité exacte
        system_exact = System(
            name="test_system", kb_name="test_kb", kb_version="==1.0.0"
        )
        system_exact.check_kb(kb_100)
        with pytest.raises(ValueError):
            system_exact.check_kb(kb_110)

        # Test avec supérieur ou égal
        system_ge = System(name="test_system", kb_name="test_kb", kb_version=">=1.0.0")
        system_ge.check_kb(kb_100)
        system_ge.check_kb(kb_110)
        system_ge.check_kb(kb_200)

        # Test avec inférieur
        system_lt = System(name="test_system", kb_name="test_kb", kb_version="<2.0.0")
        system_lt.check_kb(kb_100)
        system_lt.check_kb(kb_110)
        with pytest.raises(ValueError):
            system_lt.check_kb(kb_200)

    def test_system_repr_and_str(self):
        """Test the __repr__ and __str__ methods of the System class."""
        # Créer un système simple
        system = System(name="test_system", kb_name="test_kb")

        # Vérifier que __repr__ renvoie une chaîne non vide
        repr_str = repr(system)
        assert "System" in repr_str
        assert "test_system" in repr_str

        # Vérifier que __str__ renvoie une chaîne plus détaillée
        str_output = str(system)
        assert "System" in str_output
        assert "test_system" in str_output
        assert "KB" in str_output
        assert "test_kb" in str_output

    def test_system_with_components_and_connections(self):
        """Test a complete system with components and connections."""
        # Créer une KB avec un template
        template = ComponentTemplate(name="test_template", label="Test Template")
        kb = KB(name="test_kb", component_templates={"test_template": template})

        # Créer un système
        system = System(name="test_system", kb_name="test_kb")

        # Ajouter des composants
        system.add_component(kb, "test_template", "comp1")
        system.add_component(kb, "test_template", "comp2")

        # Ajouter une connexion
        connection = Connection(
            component_source="comp1",
            interface_source="output1",
            component_target="comp2",
            interface_target="input1",
        )
        system.connections["conn1"] = connection

        # Verifications
        assert len(system.components) == 2
        assert "comp1" in system.components
        assert "comp2" in system.components
        assert len(system.connections) == 1
        assert "conn1" in system.connections

        # Verify that the string representation contains information about components and connections
        str_output = str(system)
        assert "Components List (2)" in str_output
        assert "Connections List (1)" in str_output

    def test_drop_component(self):
        """Test dropping a component from the system."""
        # Créer une KB avec un template
        template = ComponentTemplate(name="test_template", label="Test Template")
        kb = KB(name="test_kb", component_templates={"test_template": template})

        # Créer un système
        system = System(name="test_system", kb_name="test_kb")

        # Ajouter des composants
        system.add_component(kb, "test_template", "comp1")
        system.add_component(kb, "test_template", "comp2")

        # Vérifier que les composants sont présents
        assert len(system.components) == 2
        assert "comp1" in system.components
        assert "comp2" in system.components

        # Supprimer un composant
        dropped_component = system.drop_component("comp1")

        # Vérifier que le composant a été supprimé
        assert len(system.components) == 1
        assert "comp1" not in system.components
        assert "comp2" in system.components

        # Vérifier que le composant retourné est correct
        assert dropped_component.name == "comp1"
        assert dropped_component.template == template

    def test_drop_component_nonexistent(self):
        """Test dropping a non-existent component from the system."""
        # Créer un système
        system = System(name="test_system", kb_name="test_kb")

        # Tenter de supprimer un composant inexistant
        with pytest.raises(KeyError):
            system.drop_component("nonexistent_component")

    def test_drop_component_and_readd(self):
        """Test dropping a component and then adding it back to the system."""
        # Créer une KB avec un template
        template = ComponentTemplate(name="test_template", label="Test Template")
        kb = KB(name="test_kb", component_templates={"test_template": template})

        # Créer un système
        system = System(name="test_system", kb_name="test_kb")

        # Ajouter un composant
        system.add_component(kb, "test_template", "comp1", label="Original Label")

        # Supprimer le composant
        dropped_component = system.drop_component("comp1")

        # Vérifier que le système ne contient plus le composant
        assert len(system.components) == 0

        # Modifier le composant supprimé
        dropped_component.label = "Modified Label"

        # Réajouter le composant au système
        system.components["comp1"] = dropped_component

        # Vérifier que le composant a été réajouté avec les modifications
        assert len(system.components) == 1
        assert "comp1" in system.components
        assert system.components["comp1"].label == "Modified Label"
        
    def test_connect_components(self):
        """Test connecting two components in the system."""
        # Créer une KB avec un template
        template = ComponentTemplate(name="test_template", label="Test Template")
        
        # Ajouter des interfaces au template
        output_interface = InterfaceTemplate(
            name="output1", port_type="output", label="Output Interface"
        )
        input_interface = InterfaceTemplate(
            name="input1", port_type="input", label="Input Interface"
        )
        
        template.add_interface(output_interface)
        template.add_interface(input_interface)
        
        kb = KB(name="test_kb", component_templates={"test_template": template})
        
        # Créer un système
        system = System(name="test_system", kb_name="test_kb")
        
        # Ajouter des composants
        system.add_component(kb, "test_template", "comp1")
        system.add_component(kb, "test_template", "comp2")
        
        # Connecter les composants
        connection = system.connect("comp1", "output1", "comp2", "input1")
        
        # Vérifier que la connexion a été créée
        assert len(system.connections) == 1
        assert "comp1_output1_to_comp2_input1" in system.connections
        assert system.connections["comp1_output1_to_comp2_input1"] == connection
        assert connection.component_source == "comp1"
        assert connection.interface_source == "output1"
        assert connection.component_target == "comp2"
        assert connection.interface_target == "input1"
        
    def test_connect_with_parameters(self):
        """Test connecting components with additional parameters."""
        # Créer une KB avec un template
        template = ComponentTemplate(name="test_template", label="Test Template")
        
        # Ajouter des interfaces au template
        output_interface = InterfaceTemplate(
            name="output1", port_type="output", label="Output Interface"
        )
        input_interface = InterfaceTemplate(
            name="input1", port_type="input", label="Input Interface"
        )
        
        template.add_interface(output_interface)
        template.add_interface(input_interface)
        
        kb = KB(name="test_kb", component_templates={"test_template": template})
        
        # Créer un système
        system = System(name="test_system", kb_name="test_kb")
        
        # Ajouter des composants
        system.add_component(kb, "test_template", "comp1")
        system.add_component(kb, "test_template", "comp2")
        
        # Connecter les composants avec des paramètres supplémentaires
        connection = system.connect(
            "comp1", "output1", "comp2", "input1",
            init_parameters={"protocol": "mqtt", "qos": 1},
            metadata={"created_by": "test", "priority": "high"}
        )
        
        # Vérifier que la connexion a été créée avec les paramètres
        assert connection.init_parameters == {"protocol": "mqtt", "qos": 1}
        assert connection.metadata == {"created_by": "test", "priority": "high"}
        
    def test_connect_nonexistent_component(self):
        """Test that connecting with a nonexistent component raises an error."""
        # Créer une KB avec un template
        template = ComponentTemplate(name="test_template", label="Test Template")
        kb = KB(name="test_kb", component_templates={"test_template": template})
        
        # Créer un système
        system = System(name="test_system", kb_name="test_kb")
        
        # Ajouter un composant
        system.add_component(kb, "test_template", "comp1")
        
        # Tenter de connecter avec un composant inexistant
        with pytest.raises(KeyError):
            system.connect("comp1", "output1", "nonexistent", "input1")
        
    def test_connect_nonexistent_interface(self):
        """Test that connecting with a nonexistent interface raises an error."""
        # Créer une KB avec un template
        template = ComponentTemplate(name="test_template", label="Test Template")
        kb = KB(name="test_kb", component_templates={"test_template": template})
        
        # Créer un système
        system = System(name="test_system", kb_name="test_kb")
        
        # Ajouter des composants
        system.add_component(kb, "test_template", "comp1")
        system.add_component(kb, "test_template", "comp2")
        
        # Tenter de connecter avec une interface inexistante
        with pytest.raises(ValueError):
            system.connect("comp1", "nonexistent", "comp2", "input1")
        
    def test_connect_incompatible_port_types(self):
        """Test that connecting with incompatible port types raises an error."""
        # Créer une KB avec un template
        template = ComponentTemplate(name="test_template", label="Test Template")
        
        # Ajouter des interfaces au template
        input_interface1 = InterfaceTemplate(
            name="input1", port_type="input", label="Input Interface 1"
        )
        input_interface2 = InterfaceTemplate(
            name="input2", port_type="input", label="Input Interface 2"
        )
        
        template.add_interface(input_interface1)
        template.add_interface(input_interface2)
        
        kb = KB(name="test_kb", component_templates={"test_template": template})
        
        # Créer un système
        system = System(name="test_system", kb_name="test_kb")
        
        # Ajouter des composants
        system.add_component(kb, "test_template", "comp1")
        system.add_component(kb, "test_template", "comp2")
        
        # Tenter de connecter avec des types de ports incompatibles
        with pytest.raises(ValueError):
            system.connect("comp1", "input1", "comp2", "input2")
