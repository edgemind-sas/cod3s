from .core import ObjCOD3S
from .kb import KB, ComponentInstance
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Union, Literal, get_args
from colored import fg, bg, attr as colored_attr
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
            f"  {fg('white')}KB{colored_attr('reset')}: {self.kb.name}"
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
        Vérifie la compatibilité d'une instance KB avec ce système.

        Args:
            kb (KB): Instance de la base de connaissances à vérifier

        Raises:
            ValueError: Si la KB n'est pas compatible (nom ou version)
        """
        # Vérifier que le nom de la KB correspond
        if kb.name != self.kb_name:
            raise ValueError(
                f"La KB '{kb.name}' ne correspond pas à la KB attendue '{self.kb_name}'"
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
                elif operator == "~=":  # Compatible release (PEP 440)
                    is_compatible = (
                        kb_version >= required_version
                        and kb_version.release[0] == required_version.release[0]
                    )

                if not is_compatible:
                    raise ValueError(
                        f"La version de la KB '{kb.version}' n'est pas compatible avec la version requise '{self.kb_version}'"
                    )

    def create_instance(self, kb, template_name, instance_name, **kwargs):
        """
        Crée une instance de composant à partir d'un template dans la KB et l'ajoute au système.

        Args:
            kb (KB): Instance de la base de connaissances
            template_name (str): Nom du template de composant à instancier
            instance_name (str): Nom à donner à l'instance créée
            **kwargs: Paramètres supplémentaires à passer à la méthode create_instance du template

        Returns:
            ComponentInstance: L'instance de composant créée

        Raises:
            ValueError: Si la KB n'est pas compatible ou si le template n'existe pas
        """
        # Vérifier que la KB est compatible
        self.check_kb(kb)

        # Rechercher le template dans la KB
        if template_name not in kb.component_templates:
            raise ValueError(
                f"Le template '{template_name}' n'existe pas dans la KB '{kb.name}'"
            )

        template = kb.component_templates[template_name]

        # Créer l'instance à partir du template
        instance = template.create_instance(instance_name, **kwargs)

        # Stocker l'instance dans le dictionnaire des composants
        self.components[instance_name] = instance

        return instance
