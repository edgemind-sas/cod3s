from .core import ObjCOD3S
from .utils import get_class_by_name
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Union, Literal, ClassVar, Type
import copy
from colored import fg, attr as colored_attr

"""
Knowledge Base (KB) management module for COD3S.

This module defines data structures to represent components,
their attributes and interfaces in a reusable knowledge base.
It provides classes for modeling component templates that can
be instantiated to build complex systems.
"""


class InterfaceTemplate(ObjCOD3S):
    """
    Model for defining a component interface template.

    An interface defines how a component can connect to other
    components in a system. It specifies connection constraints
    and associated metadata.
    """

    name: str = Field(..., description="Interface name / ID")
    port_type: Literal["input", "output"] = Field(..., description="Port type")
    label: Optional[str] = Field(None, description="Interface display name")
    description: Optional[str] = Field(None, description="Interface description")
    metadata: Optional[Dict[str, Union[str, List[str]]]] = Field(
        {}, description="Interface's metadata to store specific business/context data"
    )
    component_authorized: Optional[List[str]] = Field(
        [], description="List of authorized components to be connected"
    )

    def __repr__(self):
        """Return a concise string representation of the interface template."""
        return f"{fg('cyan')}{self.__class__.__name__}{colored_attr('reset')}: {fg('light_blue')}{self.name}{colored_attr('reset')} ({self.port_type})"

    def __str__(self):
        """Return a detailed string representation of the interface template."""
        components_auth = (
            ", ".join(self.component_authorized) if self.component_authorized else "Any"
        )
        return (
            f"{fg('cyan')}{self.__class__.__name__}{colored_attr('reset')}: {fg('light_blue')}{self.name}{colored_attr('reset')}\n"
            f"  {fg('white')}Type{colored_attr('reset')}: {fg('light_green')}{self.port_type}{colored_attr('reset')}\n"
            f"  {fg('white')}Label{colored_attr('reset')}: {self.label or self.name}\n"
            f"  {fg('white')}Description{colored_attr('reset')}: {self.description or 'N/A'}\n"
            f"  {fg('white')}Authorized Components{colored_attr('reset')}: {components_auth}"
        )


class AttributeTemplate(ObjCOD3S):
    """
    Model for defining a component attribute template.

    An attribute represents a property of a component with a specific type
    and default and current values. The type can be a primitive type
    (bool, int, float) or an enumeration (list of strings).

    Default values are automatically initialized based on the type:
    - bool: False
    - int: 0
    - float: 0.0
    - enum: first value in the list

    If value_current is not specified, it will be set to value_default.
    """

    name: Optional[str] = Field(None, description="Attribute name / ID")
    type: Union[Literal["bool", "int", "float"], List[str]] = Field(
        ..., description="Attribute type (bool, int, float or list of strings for enum)"
    )
    value_default: Optional[Any] = Field(
        None, description="Default value for the attribute"
    )
    value_current: Optional[Any] = Field(
        None, description="Current value of the attribute"
    )

    def __repr__(self):
        """Return a concise string representation of the attribute template."""
        type_str = self.type if isinstance(self.type, str) else "enum"
        return f"{fg('magenta')}Attribute{colored_attr('reset')}: {fg('light_magenta')}{self.name}{colored_attr('reset')} ({type_str})"

    def __str__(self):
        """Return a detailed string representation of the attribute template."""
        if isinstance(self.type, list):
            type_str = f"enum: [{', '.join(self.type)}]"
        else:
            type_str = self.type

        return (
            f"{fg('magenta')}Attribute Template{colored_attr('reset')}: {fg('light_magenta')}{self.name}{colored_attr('reset')}\n"
            f"  {fg('white')}Type{colored_attr('reset')}: {fg('light_green')}{type_str}{colored_attr('reset')}\n"
            f"  {fg('white')}Default Value{colored_attr('reset')}: {self.value_default}\n"
            f"  {fg('white')}Current Value{colored_attr('reset')}: {self.value_current or 'Not set'}"
        )

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, v):
        """
        Validates the attribute type.

        If the type is a string, it must be one of the allowed primitive types.
        If the type is a list (enumeration), it must contain unique strings.

        Args:
            v: The value to validate

        Returns:
            The validated value

        Raises:
            ValueError: If the type is not valid
        """
        if isinstance(v, str) and v not in ["bool", "int", "float"]:
            raise ValueError(f"String type must be one of: bool, int, float. Got: {v}")
        elif isinstance(v, list):
            if not all(isinstance(item, str) for item in v):
                raise ValueError("All items in enum list must be strings")
            if len(v) != len(set(v)):
                raise ValueError("Enum values must be unique")
            if len(v) == 0:
                raise ValueError("Enum list cannot be empty")
        return v

    @model_validator(mode="after")
    def validate_values(self):
        """
        Validates that default and current values are consistent with the type.
        Also initializes default values based on type if not provided.

        Checks that values respect the constraints of the specified type:
        - For primitive types: checks the corresponding Python type
        - For enumerations: checks that the value is in the list of possible values

        Initializes default values if not provided:
        - bool: False
        - int: 0
        - float: 0.0
        - enum: first value in the list

        Sets current value to default if not provided.

        Returns:
            The validated instance

        Raises:
            ValueError: If the values are not consistent with the type
        """
        # Set default value based on type if not provided
        if self.value_default is None:
            if isinstance(self.type, str):
                if self.type == "bool":
                    self.value_default = False
                elif self.type == "int":
                    self.value_default = 0
                elif self.type == "float":
                    self.value_default = 0.0
            elif isinstance(self.type, list) and len(self.type) > 0:
                self.value_default = self.type[0]

        # Set current value to default if not provided
        if self.value_current is None and self.value_default is not None:
            self.value_current = self.value_default

        if isinstance(self.type, str):
            # Validate for primitive types
            if self.type == "bool":
                if self.value_default is not None and not isinstance(
                    self.value_default, bool
                ):
                    raise ValueError(
                        f"Default value must be boolean for bool type, got: {type(self.value_default)}"
                    )
                if self.value_current is not None and not isinstance(
                    self.value_current, bool
                ):
                    raise ValueError(
                        f"Current value must be boolean for bool type, got: {type(self.value_current)}"
                    )
            elif self.type == "int":
                if self.value_default is not None and not isinstance(
                    self.value_default, int
                ):
                    raise ValueError(
                        f"Default value must be integer for int type, got: {type(self.value_default)}"
                    )
                if self.value_current is not None and not isinstance(
                    self.value_current, int
                ):
                    raise ValueError(
                        f"Current value must be integer for int type, got: {type(self.value_current)}"
                    )
            elif self.type == "float":
                if self.value_default is not None and not isinstance(
                    self.value_default, (int, float)
                ):
                    raise ValueError(
                        f"Default value must be numeric for float type, got: {type(self.value_default)}"
                    )
                if self.value_current is not None and not isinstance(
                    self.value_current, (int, float)
                ):
                    raise ValueError(
                        f"Current value must be numeric for float type, got: {type(self.value_current)}"
                    )
        else:
            # Validate for enum (list of strings)
            if self.value_default is not None and self.value_default not in self.type:
                raise ValueError(
                    f"Default value must be one of the enum values: {self.type}"
                )
            if self.value_current is not None and self.value_current not in self.type:
                raise ValueError(
                    f"Current value must be one of the enum values: {self.type}"
                )

        return self


class ComponentClass(ObjCOD3S):
    """
    Represents the specifications of a component.

    A component class defines the structure of a component type,
    including its attributes, interfaces, metadata, and other properties.
    These templates are used to instantiate concrete components
    in a system.
    """

    class_name: Optional[str] = Field(..., description="Component class name")
    class_name_bkd: Optional[Dict[str, str]] = Field(
        {"pycatshoo": "CComponent"},
        description="Class name used to instanciate the component with the backend analysis tool",
    )
    class_label: Optional[str] = Field(None, description="Component display name")
    class_description: Optional[str] = Field(None, description="Component description")
    groups: Optional[List[str]] = Field(None, description="Component template groups")
    attributes: Optional[Dict[str, AttributeTemplate]] = Field(
        None, description="Component groups"
    )
    interfaces: List[InterfaceTemplate] = Field(
        [], description="List of component interfaces"
    )
    metadata: Optional[Dict[str, Union[str, List[str]]]] = Field(
        {}, description="Component's metadata to store specific business/context data"
    )

    @property
    def interfaces_d(self):
        """
        Property that returns a dictionary of interfaces indexed by their names.

        Returns:
            Dict[str, InterfaceTemplate]: Dictionary mapping interface names to their objects
        """
        return {interface.name: interface for interface in self.interfaces}

    def __repr__(self):
        """Return a concise string representation of the component template."""
        return f"{fg('yellow')}{self.__class__.__name__}{colored_attr('reset')}: {fg('light_yellow')}{self.class_name}{colored_attr('reset')}"

    def __str__(self):
        """Return a detailed string representation of the component template."""
        attr_count = len(self.attributes) if self.attributes else 0
        intf_count = len(self.interfaces) if self.interfaces else 0
        groups_str = ", ".join(self.groups) if self.groups else "None"

        result = (
            f"{fg('yellow')}{self.__class__.__name__}{colored_attr('reset')}: {fg('light_yellow')}{self.class_name}{colored_attr('reset')}\n"
            f"  {fg('white')}Label{colored_attr('reset')}: {self.class_label}\n"
            f"  {fg('white')}Description{colored_attr('reset')}: {self.class_description or 'N/A'}\n"
            f"  {fg('white')}Backend Class{colored_attr('reset')}: {self.class_name_bkd or 'N/A'}\n"
            f"  {fg('white')}Groups{colored_attr('reset')}: {groups_str}"
        )

        if attr_count > 0:
            result += f"\n  {fg('magenta')}Attributes List ({attr_count}){colored_attr('reset')}:"
            for name, attribute in self.attributes.items():
                type_str = attribute.type if isinstance(attribute.type, str) else "enum"
                result += f"\n    - {fg('light_magenta')}{name}{colored_attr('reset')} ({type_str})"

        if intf_count > 0:
            result += f"\n  {fg('cyan')}Interfaces List ({intf_count}){colored_attr('reset')}:"
            for intf in self.interfaces:
                result += f"\n    - {fg('light_blue')}{intf.name}{colored_attr('reset')} ({intf.port_type})"

        return result

    def add_interface(self, interface, upsert=False):
        """
        Adds an interface to the component template.

        Args:
            interface (Union[InterfaceTemplate, dict]): The interface to add, either an InterfaceTemplate object
                                                        or a dictionary of specifications
            upsert (bool): If True, updates the interface if it already exists (same name and port_type)
                           If False, raises an error if an interface with the same name and port_type already exists

        Returns:
            InterfaceTemplate: The added interface

        Raises:
            ValueError: If an interface with the same name and port_type already exists and upsert=False
            TypeError: If the provided interface is neither an InterfaceTemplate nor a dictionary
        """
        # Convert the dictionary to InterfaceTemplate if necessary
        if isinstance(interface, dict):
            interface.setdefault("cls", "InterfaceTemplate")
            interface = ObjCOD3S.from_dict(interface)
        elif not isinstance(interface, InterfaceTemplate):
            raise TypeError(
                "The interface must be an InterfaceTemplate or a dictionary"
            )

        # Check if an interface with the same name and port_type already exists
        for i, existing_interface in enumerate(self.interfaces):
            if (
                existing_interface.name == interface.name
                and existing_interface.port_type == interface.port_type
            ):
                if upsert:
                    # Update the existing interface
                    self.interfaces[i] = interface
                    return interface
                else:
                    # Raise an error if upsert=False
                    raise ValueError(
                        f"An interface with the name '{interface.name}' and port_type '{interface.port_type}' already exists"
                    )
        # Add the new interface
        self.interfaces.append(interface)
        return interface

    def deepcopy(self):
        """
        Creates a deep copy of the component template.

        Returns:
            ComponentClass: A new component template with the same values but independent objects
        """
        # Create deep copies of attributes
        attributes_copy = {}
        if self.attributes:
            for attr_name, attr_template in self.attributes.items():
                attributes_copy[attr_name] = copy.deepcopy(attr_template)

        # Create deep copies of interfaces
        interfaces_copy = []
        if self.interfaces:
            for interface in self.interfaces:
                interfaces_copy.append(copy.deepcopy(interface))

        # Create a deep copy of metadata
        metadata_copy = copy.deepcopy(self.metadata) if self.metadata else {}

        # Create a new instance with the copies
        new_inst = self.__class__(
            class_name=self.class_name,
            class_name_bkd=copy.deepcopy(self.class_name_bkd),
            class_label=self.class_label,
            class_description=self.class_description,
            groups=copy.deepcopy(self.groups) if self.groups else None,
            attributes=attributes_copy,
            interfaces=interfaces_copy,
            metadata=metadata_copy,
        )
        return new_inst

    def create_instance(self, name, **kwargs):
        """
        Create a ComponentInstance based on this component template.

        Creates a new component instance with deep copies of all attributes and interfaces
        from the template. The current values of attributes in the new instance are
        initially set to None to avoid automatic initialization to default values.

        Args:
            name (str): Name of the component instance
            **kwargs: Additional parameters to override default values
                - label: Custom label for the instance
                - description: Custom description for the instance
                - init_parameters: Parameters to pass to the backend constructor
                - metadata: Custom metadata for the instance

        Returns:
            ComponentInstance: A new component instance based on this template
        """
        # Create a deep copy of the template
        template_copy = self.deepcopy()

        template_copy.metadata.update(kwargs.pop("metadata", {}))

        # __import__("ipdb").set_trace()

        instance_specs = dict(kwargs, **template_copy.model_dump())
        cls_instance = self.__class__.__name__.replace("Class", "Instance")

        instance_specs["cls"] = cls_instance
        instance_specs["name"] = name
        # cod3s_sub_classes = ObjCOD3S.get_subclasses_dict()

        # instance_class = cod3s_sub_classes.get(cls_instance, ComponentInstance)
        # instance = instance_class(name=name, **kwargs_bis)
        instance = ObjCOD3S.from_dict(instance_specs)

        # __import__("ipdb").set_trace()

        return instance


class ComponentInstance(ComponentClass):
    """
    Represents an instance of a component created from a template.

    A component instance is a concrete instantiation of a component template
    with specific values for its attributes. It inherits all properties from
    its template but can override them with instance-specific values.
    """

    name: str = Field(..., description="Component name")
    label: str = Field(None, description="Component label")
    description: str = Field(None, description="Component description")
    init_parameters: Optional[Dict[str, Any]] = Field(
        {}, description="Component parameters passed to component backend constructor"
    )

    def __repr__(self):
        """Return a concise string representation of the component instance."""
        return f"{fg('green')}{self.__class__.__name__}{colored_attr('reset')}: {fg('light_green')}{self.name}{colored_attr('reset')} (class: {self.class_name})"

    def __str__(self):
        """Return a detailed string representation of the component instance."""
        attr_count = len(self.attributes) if self.attributes else 0
        intf_count = len(self.interfaces) if self.interfaces else 0

        result = (
            f"{fg('green')}{self.__class__.__name__}{colored_attr('reset')}: {fg('light_green')}{self.name}{colored_attr('reset')}\n"
            f"  {fg('white')}Class{colored_attr('reset')}: {fg('yellow')}{self.class_name}{colored_attr('reset')}\n"
            f"  {fg('white')}Label{colored_attr('reset')}: {self.label or self.name}\n"
            f"  {fg('white')}Description{colored_attr('reset')}: {self.description or 'N/A'}"
        )

        if attr_count > 0:
            result += f"\n  {fg('magenta')}Attributes List ({attr_count}){colored_attr('reset')}:"
            for name, attribute in self.attributes.items():
                type_str = attribute.type if isinstance(attribute.type, str) else "enum"
                current_value = (
                    attribute.value_current
                    if attribute.value_current is not None
                    else "Unset"
                )
                default_value = (
                    attribute.value_default
                    if attribute.value_default is not None
                    else "None"
                )
                # If the current value is different from the default value, color it white
                if (
                    attribute.value_current is not None
                    and attribute.value_current != attribute.value_default
                ):
                    current_value_str = (
                        f"{fg('white')}{current_value}{colored_attr('reset')}"
                    )
                else:
                    current_value_str = current_value
                result += f"\n    - {fg('light_magenta')}{name}{colored_attr('reset')} ({type_str}) = {current_value_str} [default: {default_value}]"

        if intf_count > 0:
            result += f"\n  {fg('cyan')}Interfaces List ({intf_count}){colored_attr('reset')}:"
            for intf in self.interfaces:
                result += f"\n    - {fg('light_blue')}{intf.name}{colored_attr('reset')} ({intf.port_type})"

        if self.init_parameters:
            result += f"\n  {fg('white')}Init Parameters{colored_attr('reset')}: {self.init_parameters}"

        return result

    def to_bkd(self, bkd_name):
        """
        Dynamically calls the appropriate backend method based on the provided name.

        Args:
            bkd_name (str): Backend name (for example 'pycatshoo')

        Returns:
            Any: The result of the specific backend method

        Raises:
            AttributeError: If the corresponding backend method doesn't exist
        """
        method_name = f"to_bkd_{bkd_name}"
        if not hasattr(self, method_name):
            raise AttributeError(
                f"The method '{method_name}' doesn't exist. The backend '{bkd_name}' is not supported."
            )
        return getattr(self, method_name)()

    # def check_bkd_pycatshoo(self):
    #     try:
    #         import Pycatshoo as pyc

    #         return pyc
    #     except ImportError:
    #         raise ImportError(
    #             "The Pycatshoo package is not installed. Please install it to use this functionality."
    #         )

    def to_bkd_pycatshoo(self, **init_parameters):
        # pyc = self.check_bkd_pycatshoo()

        class_name = self.class_name_bkd.get("pycatshoo")
        if not class_name:
            raise ValueError("No pycatshoo backend class is specified in the template.")

        cls = get_class_by_name(class_name)

        # # Get the class from its name
        # if not hasattr(pyc, cls_name):
        #     raise ValueError(
        #         f"The class '{cls_name}' doesn't exist in the Pycatshoo package."
        #     )

        # cls = getattr(pyc, cls_name)

        init_parameters.update(**self.init_parameters)

        try:
            comp = cls(self.name, **init_parameters)
        except Exception as e:
            raise ValueError(
                f"Pycatshoo component instanciation failed: {e}. Please check if a PyCATSHOO system is instanciated ?"
            )

        # Instantiate the component with the initialization parameters
        return comp


class KB(ObjCOD3S):
    """
    A knowledge base (KB) contains a list of component classes.

    The knowledge base is the main container for storing and organizing
    component definitions that can be instantiated to build
    a model system. It provides a reusable catalog of components
    with their complete specifications.
    """

    component_class_type: ClassVar[Type[ComponentClass]] = ComponentClass

    name: str = Field(..., description="KB name/id")
    label: Optional[str] = Field(None, description="KB label to be displayed")

    description: Optional[str] = Field(None, description="KB long description")
    version: Optional[str] = Field(None, description="KB version")
    component_classes: Optional[Dict[str, ComponentClass]] = Field(
        {}, description="Dictionnary of component classes"
    )

    def __repr__(self):
        """Return a concise string representation of the knowledge base."""
        comp_count = len(self.component_classes) if self.component_classes else 0
        return f"{fg('blue')}KB{colored_attr('reset')}: {fg('light_blue')}{self.name}{colored_attr('reset')} ({comp_count} components)"

    def __str__(self):
        """Return a detailed string representation of the knowledge base."""
        comp_count = len(self.component_classes) if self.component_classes else 0

        result = (
            f"{fg('blue')}Knowledge Base{colored_attr('reset')}: {fg('light_blue')}{self.name}{colored_attr('reset')}\n"
            f"  {fg('white')}Label{colored_attr('reset')}: {self.label or self.name}\n"
            f"  {fg('white')}Description{colored_attr('reset')}: {self.description or 'N/A'}\n"
            f"  {fg('white')}Version{colored_attr('reset')}: {self.version or 'N/A'}"
        )

        if comp_count > 0:
            result += f"\n  {fg('yellow')}Components List ({comp_count}){colored_attr('reset')}:"
            for name, comp in self.component_classes.items():
                result += f"\n    - {fg('light_yellow')}{name}{colored_attr('reset')}"

        return result

    def add_component_class(self, component_class, upsert=False):
        """
        Adds a component template to the knowledge base.

        Args:
            component_class (Union[ComponentClass, dict]): The template to add, either a ComponentClass object
                                                                or a dictionary of specifications
            upsert (bool): If True, updates the template if it already exists (same name)
                           If False, raises an error if a template with the same name already exists

        Returns:
            ComponentClass: The added component template

        Raises:
            ValueError: If a template with the same name already exists and upsert=False
            TypeError: If the provided template is neither a ComponentClass nor a dictionary
        """
        # Convert the dictionary to ComponentClass if necessary
        if isinstance(component_class, dict):

            component_class.setdefault("cls", self.component_class_type)
            component_class = ObjCOD3S.from_dict(component_class)

        if not isinstance(component_class, self.component_class_type):
            raise TypeError("The template must be a ComponentClass or a dictionary")

        # Check if a template with the same name already exists
        if component_class.class_name in self.component_classes:
            if upsert:
                # Update the existing template
                self.component_classes[component_class.class_name] = component_class
            else:
                # Raise an error if upsert=False
                raise ValueError(
                    f"A class with the name '{component_class.class_name}' already exists"
                )
        else:
            # Add the new class
            self.component_classes[component_class.class_name] = component_class

        return component_class
