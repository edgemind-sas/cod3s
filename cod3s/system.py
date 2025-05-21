from .core import ObjCOD3S
from .kb import ComponentInstance
from pydantic import Field
from typing import Optional, List, Dict, Any, Union
from colored import fg, attr as colored_attr
import semver
import re


class Connection(ObjCOD3S):
    component_source: Optional[str] = Field(..., description="Component source name")
    interface_source: Optional[str] = Field(
        ..., description="Component interface source name"
    )
    component_target: Optional[str] = Field(..., description="Component target name")
    interface_target: Optional[str] = Field(
        ..., description="Component interface target name"
    )
    init_parameters: Optional[Dict[str, Any]] = Field(
        {}, description="Connection parameters passed to connection backend constructor"
    )
    metadata: Optional[Dict[str, Any]] = Field({}, description="Component metadata")

    def __repr__(self):
        """Return a concise string representation of the connection."""
        return f"{fg('orange_1')}Connection{colored_attr('reset')}: {fg('orange_3')}{self.component_source}.{self.interface_source}{colored_attr('reset')} → {fg('orange_3')}{self.component_target}.{self.interface_target}{colored_attr('reset')}"

    def __str__(self):
        """Return a detailed string representation of the connection."""
        result = f"{fg('orange_1')}Connection{colored_attr('reset')}: {fg('orange_3')}{self.component_source}.{self.interface_source}{colored_attr('reset')} → {fg('orange_3')}{self.component_target}.{self.interface_target}{colored_attr('reset')}"

        if self.init_parameters:
            result += f"\n  {fg('white')}Init Parameters{colored_attr('reset')}: {self.init_parameters}"

        if self.metadata:
            result += (
                f"\n  {fg('white')}Metadata{colored_attr('reset')}: {self.metadata}"
            )

        return result


class System(ObjCOD3S):

    name: str = Field(..., description="System name/id")
    kb_name: str = Field(..., description="Knowledge base class name")
    kb_version: Optional[str] = Field(
        None, description="Knowledge base version compatibility"
    )
    label: Optional[str] = Field(None, description="System label to be displayed")

    description: Optional[str] = Field(None, description="System long description")
    version: Optional[str] = Field(None, description="System version")

    components: Optional[Dict[str, ComponentInstance]] = Field(
        {}, description="Component instances"
    )

    connections: Optional[Dict[str, Connection]] = Field(
        {}, description="Connection instances"
    )
    metadata: Optional[Dict[str, Union[str, List[str]]]] = Field(
        {}, description="Component metadata"
    )

    def __repr__(self):
        """Return a concise string representation of the system."""
        comp_count = len(self.components) if self.components else 0
        conn_count = len(self.connections) if self.connections else 0
        return f"{fg('blue')}System{colored_attr('reset')}: {fg('light_blue')}{self.name}{colored_attr('reset')} ({comp_count} components, {conn_count} connections)"

    def __str__(self):
        """Return a detailed string representation of the system."""
        comp_count = len(self.components) if self.components else 0
        conn_count = len(self.connections) if self.connections else 0

        result = (
            f"{fg('blue')}System{colored_attr('reset')}: {fg('light_blue')}{self.name}{colored_attr('reset')}\n"
            f"  {fg('white')}Label{colored_attr('reset')}: {self.label or self.name}\n"
            f"  {fg('white')}Description{colored_attr('reset')}: {self.description or 'N/A'}\n"
            f"  {fg('white')}Version{colored_attr('reset')}: {self.version or 'N/A'}\n"
            f"  {fg('white')}KB{colored_attr('reset')}: {self.kb_name} [{self.kb_version}]"
        )

        if comp_count > 0:
            result += f"\n  {fg('green')}Components List ({comp_count}){colored_attr('reset')}:"
            for name, comp in self.components.items():
                result += f"\n    - {fg('light_green')}{name}{colored_attr('reset')} (template: {comp.template.name})"

        if conn_count > 0:
            result += f"\n  {fg('orange_1')}Connections List ({conn_count}){colored_attr('reset')}:"
            for name, conn in self.connections.items():
                result += f"\n    - {fg('orange_3')}{conn.component_source}.{conn.interface_source}{colored_attr('reset')} → {fg('orange_3')}{conn.component_target}.{conn.interface_target}{colored_attr('reset')}"

        return result

    def check_kb(self, kb):
        """
        Check the compatibility of a KB instance with this system.

        Args:
            kb (KB): Knowledge base instance to check

        Raises:
            ValueError: If the KB is not compatible (name or version)
        """
        # Vérifier que le nom de la KB correspond
        if kb.name != self.kb_name:
            raise ValueError(
                f"The KB '{kb.name}' does not match the expected KB '{self.kb_name}'"
            )

        # Vérifier la version de la KB si une version est spécifiée
        if self.kb_version is not None and kb.version is not None:

            # Extraire l'opérateur et la version
            match = re.match(r"^([<>=!]=?|~=)?\s*(.+)$", self.kb_version)
            if match:
                operator, version_str = match.groups()
                operator = operator or "=="  # Par défaut, utiliser l'égalité stricte

                kb_version = semver.Version.parse(kb.version)
                required_version = semver.Version.parse(version_str)

                # Vérifier la compatibilité selon l'opérateur
                is_compatible = False
                if operator == "==":
                    is_compatible = kb_version == required_version
                elif operator == "!=":
                    is_compatible = kb_version != required_version
                elif operator == ">":
                    is_compatible = kb_version > required_version
                elif operator == ">=":
                    is_compatible = kb_version >= required_version
                elif operator == "<":
                    is_compatible = kb_version < required_version
                elif operator == "<=":
                    is_compatible = kb_version <= required_version

                if not is_compatible:
                    raise ValueError(
                        f"The KB version '{kb.version}' is not compatible with the required version '{self.kb_version}'"
                    )

    def add_component(self, kb, template_name, instance_name, **kwargs):
        """
        Creates a component instance from a template in the KB and adds it to the system.

        Args:
            kb (KB): Knowledge base instance
            template_name (str): Name of the component template to instantiate
            instance_name (str): Name to give to the created instance
            **kwargs: Additional parameters to pass to the template's create_instance method

        Returns:
            ComponentInstance: The created component instance

        Raises:
            ValueError: If the KB is not compatible or if the template doesn't exist
        """
        # Vérifier que la KB est compatible
        self.check_kb(kb)

        # Rechercher le template dans la KB
        if template_name not in kb.component_templates:
            raise ValueError(
                f"The template '{template_name}' doesn't exist in the KB '{kb.name}'"
            )

        template = kb.component_templates[template_name]

        # Créer l'instance à partir du template
        instance = template.create_instance(instance_name, **kwargs)

        # Stocker l'instance dans le dictionnaire des composants
        self.components[instance_name] = instance

        return instance

    def drop_component(self, component_name):
        """
        Removes a component from the system and returns it.

        Args:
            component_name (str): Name of the component to remove

        Returns:
            ComponentInstance: The instance of the removed component

        Raises:
            KeyError: If the component doesn't exist in the system
        """
        if component_name not in self.components:
            raise KeyError(
                f"The component '{component_name}' doesn't exist in the system"
            )

        # Get the component before removing it
        component = self.components[component_name]

        # Remove the component from the dictionary
        del self.components[component_name]

        return component

    def connect(self, component_source, interface_source, component_target, interface_target, **kwargs):
        """
        Creates a connection between two components in the system.
        
        Args:
            component_source (str): Name of the source component
            interface_source (str): Name of the source interface
            component_target (str): Name of the target component
            interface_target (str): Name of the target interface
            **kwargs: Additional parameters for the connection (init_parameters, metadata)
        
        Returns:
            Connection: The created connection
            
        Raises:
            KeyError: If one of the components doesn't exist in the system
            ValueError: If an interface doesn't exist in the corresponding component
                        or if the port types are not compatible
        """
        # Check that the components exist
        if component_source not in self.components:
            raise KeyError(f"The source component '{component_source}' doesn't exist in the system")
        if component_target not in self.components:
            raise KeyError(f"The target component '{component_target}' doesn't exist in the system")
        
        # Get the components
        source_comp = self.components[component_source]
        target_comp = self.components[component_target]
        
        # Check that the interfaces exist
        source_interface = None
        for intf in source_comp.interfaces:
            if intf.name == interface_source:
                source_interface = intf
                break
        
        if source_interface is None:
            raise ValueError(f"The interface '{interface_source}' doesn't exist in the component '{component_source}'")
        
        target_interface = None
        for intf in target_comp.interfaces:
            if intf.name == interface_target:
                target_interface = intf
                break
        
        if target_interface is None:
            raise ValueError(f"The interface '{interface_target}' doesn't exist in the component '{component_target}'")
        
        # Check the compatibility of port types
        if source_interface.port_type != "output":
            raise ValueError(f"The source interface '{interface_source}' must be of type 'output', but is of type '{source_interface.port_type}'")
        
        if target_interface.port_type != "input":
            raise ValueError(f"The target interface '{interface_target}' must be of type 'input', but is of type '{target_interface.port_type}'")
        
        # Create the connection
        connection = Connection(
            component_source=component_source,
            interface_source=interface_source,
            component_target=component_target,
            interface_target=interface_target,
            init_parameters=kwargs.get("init_parameters", {}),
            metadata=kwargs.get("metadata", {})
        )
        
        # Generate a unique name for the connection
        connection_name = f"{component_source}_{interface_source}_to_{component_target}_{interface_target}"
        
        # Add the connection to the system
        self.connections[connection_name] = connection
        
        return connection
