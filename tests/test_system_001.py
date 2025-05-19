import pytest
from cod3s.kb import (
    InterfaceTemplate,
    AttributeTemplate,
    ComponentTemplate,
    KB,
    ComponentInstance,
)
from cod3s.system import Connection, System
from pydantic import ValidationError


class TestConnection:
    def test_create_connection(self):
        """Test la création d'une connexion basique."""
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
        """Test la création d'une connexion avec tous les champs."""
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
        """Test la création d'un système basique."""
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
        """Test la création d'un système avec tous les champs."""
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
        """Test l'ajout d'un composant à un système."""
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
        """Test l'ajout d'une connexion à un système."""
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

    def test_create_instance(self):
        """Test la méthode create_instance pour créer une instance de composant."""
        # Créer une KB avec un template
        template = ComponentTemplate(name="test_template", label="Test Template")
        kb = KB(name="test_kb", component_templates={"test_template": template})

        # Créer un système
        system = System(name="test_system", kb_name="test_kb", kb_version="1.0.0")

        # Créer une instance avec la méthode create_instance
        instance = system.create_instance(
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
        """Test la méthode check_kb."""
        # Créer une KB
        kb = KB(name="test_kb", version="1.0.0")
        
        # Créer un système avec version compatible
        system = System(name="test_system", kb_name="test_kb", kb_version=">=0.9.0")
        
        # Vérifier que la vérification passe
        system.check_kb(kb)
        
        # Créer un système avec version incompatible
        system_incompatible = System(name="test_system", kb_name="test_kb", kb_version=">2.0.0")
        
        # Vérifier que l'erreur est levée
        with pytest.raises(ValueError) as excinfo:
            system_incompatible.check_kb(kb)
        
        assert "La version de la KB '1.0.0' n'est pas compatible avec la version requise '>2.0.0'" in str(
            excinfo.value
        )
    
    def test_create_instance_kb_mismatch(self):
        """Test que create_instance lève une erreur si la KB ne correspond pas."""
        # Créer une KB avec un nom différent
        kb = KB(name="wrong_kb")

        # Créer un système
        system = System(name="test_system", kb_name="test_kb", kb_version="1.0.0")

        # Vérifier que l'erreur est levée
        with pytest.raises(ValueError) as excinfo:
            system.create_instance(
                kb=kb, template_name="test_template", instance_name="test_instance"
            )

        assert "La KB 'wrong_kb' ne correspond pas à la KB attendue 'test_kb'" in str(
            excinfo.value
        )

    def test_create_instance_template_not_found(self):
        """Test que create_instance lève une erreur si le template n'existe pas."""
        # Créer une KB sans template
        kb = KB(name="test_kb")

        # Créer un système
        system = System(name="test_system", kb_name="test_kb", kb_version="1.0.0")

        # Vérifier que l'erreur est levée
        with pytest.raises(ValueError) as excinfo:
            system.create_instance(
                kb=kb,
                template_name="nonexistent_template",
                instance_name="test_instance",
            )

        assert (
            "Le template 'nonexistent_template' n'existe pas dans la KB 'test_kb'"
            in str(excinfo.value)
        )
