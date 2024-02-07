import pydantic
import typing
import pkg_resources
from .core import ObjCOD3S
from .pycatshoo import PycSequence
from .utils import update_dict_deep, dict_diff
import importlib.util
import sys
import os
import re
import json
from datetime import datetime, timezone

installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
if 'ipdb' in installed_pkg:
    import ipdb  # noqa: F401

# Utility functions
# -----------------
def reverse_conn_in_viz_list(conn_viz: dict, conn_viz_list: list) -> bool:
    """Checks if the reverse of a given connection exists in the connection visualization list.

    This function iterates over the connection visualization list and compares each
    element to the provided connection visualization dictionary (`conn_viz`). It checks
    if a connection with reversed source and target components and ports is present in
    the list.

    Args:
        conn_viz (dict): A dictionary representing a single connection visualization with
                         keys 'comp_source', 'port_source', 'comp_target', 'port_target'.
        conn_viz_list (list): A list of dictionaries, each representing a connection
                              visualization.

    Returns:
        bool: True if a connection with the reverse source and target is in the list,
              otherwise False.

    Example:
        >>> reverse_conn_in_viz_list({'comp_source': 'A', 'port_source': 'out',
                                      'comp_target': 'B', 'port_target': 'in'}, 
                                     [{'comp_target': 'A', 'port_target': 'out',
                                       'comp_source': 'B', 'port_source': 'in'}])
        True
    """
    for existing_conn_viz in conn_viz_list:
        if (existing_conn_viz['comp_target'] == conn_viz['comp_source'] and
                existing_conn_viz['port_target'] == conn_viz['port_source'] and
                existing_conn_viz['comp_source'] == conn_viz['comp_target'] and
                existing_conn_viz['port_source'] == conn_viz['port_target']):
            return True
    return False


# Utility classes
# ===============

class RenamingSpecs(pydantic.BaseModel):
    """A Pydantic model that specifies renaming rules to apply to a document attribute.

    Attributes:
        attr (str): The attribute within the document to apply the renaming pattern.
        pattern (str): The regular expression pattern to match for renaming.
        replace (str): The replacement string to use when the pattern is matched.

    Methods:
        transform: Applies the renaming rule to a given document if the attribute
                   matches the renaming pattern.
    """

    attr: str = pydantic.Field(..., description="Attribute to rename")
    pattern: str = pydantic.Field(..., description="Pattern to rename")
    replace: str = pydantic.Field(..., description="Replace value")

    def transform(self, document):
        """Applies renaming transformation to the specified attribute within the document.

        Checks if the `attr` attribute exists and is a string within the given document.
        If true, it replaces occurrences of the `pattern` within the attribute's value
        with the `replace` value.

        Args:
            document (dict): The document containing the attribute to be transformed.

        Raises:
            KeyError: If the `attr` is not present in the document.
            re.error: If the `pattern` is not a valid regular expression.
        """
        attr_val = document.get(self.attr)
        if attr_val and isinstance(attr_val, str):
            document[self.attr] = re.sub(self.pattern, self.raplace, attr_val)


class StyleConditionSpecs(pydantic.BaseModel):
    """Defines a style condition with an expression to evaluate and a style to apply.

    Attributes:
        expr (str): A string representing a boolean expression to evaluate.
        style (dict): A dictionary representing styling information to be applied if the expression evaluates to True.

    Methods:
        check: Evaluates the boolean expression against a provided mapper and determines if the style should be applied.
    """

    expr: str = pydantic.Field(..., description="Boolean expression to evaluate")
    style: dict = pydantic.Field({}, description="Style to be applied")

    def check(self, mapper):
        """Determines if the style should be applied based on evaluating the expression.

        Evaluates the boolean `expr` attribute using the `mapper` dictionary to substitute
        values into variables in the expression. If the evaluation succeeds and the result
        is True, the style is applicable. If the expression evaluates to False or an
        exception occurs during evaluation, the style is not applicable.

        Args:
            mapper (dict): The dictionary containing values to be substituted into the expression.

        Returns:
            bool: True if the expression evaluates to True, otherwise False.

        Example:
            Assume `expr` is "mapper['size'] > 10" and `mapper` is {"size": 12},
            the check method will return True.
        """
        try:
            res = eval(self.expr.format(**{k: f"mapper['{k}']" for k in mapper.keys()}))
        except:
            res = False
            
        return res
        


class PortVizSpec(pydantic.BaseModel):
    """Specification for the visual representation of a port in the system's visualization.

    Attributes:
        name (str): A regular expression pattern that matches the name of the port.
                    Default is ".*", which matches any name.
        spot (str): Specifies the location of the port on the component. It could be a
                    label like 'left', 'right', 'top', 'bottom', or a custom identifier.
                    Default is None, implying no specific spot is defined.
        color (str): Defines the color used to represent the port. Colors are typically
                     specified in formats that are recognized by visualization tools such
                     as hexadecimal color codes. Default is None, meaning the color is
                     unspecified.
    """

    name: str = pydantic.Field(".*", description="Port name pattern")
    spot: str = pydantic.Field(None, description="Port spot")
    color: str = pydantic.Field(None, description="Port color")

    
class ComponentVizSpecs(pydantic.BaseModel):
    """Defines the visual representation specifications of system components.

    Attributes:
        name (str): Regular expression pattern that matches the name of the components.
                    Default is ".*" to match any component name.
        type (str): Regular expression pattern that matches the class type of the components.
                    Default is ".*" to match any component class.
        renaming (typing.List[RenamingSpecs]): List of RenamingSpecs instances which define
                                               how component attributes should be renamed.
        ports (typing.List[PortVizSpec]): List of PortVizSpec instances specifying the 
                                          visual representation of each port in a component.
        style (dict): A dictionary specifying styling attributes such as color or size for 
                      the visual representation of the component.
        conditions (typing.List[StyleConditionSpecs]): List of StyleConditionSpecs instances which define
                                                       the conditions under which certain styles should
                                                       be applied.

    Methods:
        apply_ports_specs: Applies the port visualization specifications to the ports of a given component.
    """
    name: str = pydantic.Field(".*", description="Component name pattern")

    type: str = pydantic.Field(".*", description="Component class regex")

    renaming: typing.List[RenamingSpecs] = \
        pydantic.Field([], description="Renamming specs")
    
    ports: typing.List[PortVizSpec] = \
        pydantic.Field([], description="Connection ports specification")
    style: dict = pydantic.Field({}, description="Styling")

    conditions: typing.List[StyleConditionSpecs] = \
        pydantic.Field([], description="Styling conditions")


    def apply_ports_specs(self, comp):
        """Applies visualization specifications to the ports of a component.

        Args:
            comp: The component object whose ports are to be visually specified.

        Returns:
            A list of dictionaries where each dictionary contains visual representation information
            for each port that matches the specified port visualization rules.
        """

        port_viz_list = []

        for mb in comp.messageBoxes():

            port_viz = {}
                
            port_name_cur = mb.basename()
            
            # Apply each port specifications to the matching port names.
            for port_specs in self.ports:
                is_match_name = re.search(port_specs.name, port_name_cur) \
                    if port_specs.name else True
                if is_match_name:

                    port_viz_cur = \
                        port_specs.dict(exclude={"name"})
                    port_viz_cur["name"] = port_name_cur
                    port_viz_cur = {k: v for k, v in port_viz_cur.items() if v}

                    port_viz.update(port_viz_cur)
                        
            if port_viz:
                port_viz_list.append(port_viz)

        return port_viz_list
    
# class ComponentViz(ObjCOD3S):

#     name: str = pydantic.Field(..., description="Component name")
    
#     class_name: str = pydantic.Field(..., description="Component class name")

#     ports: typing.Dict[str, str] = pydantic.Field({}, description="Connection ports position")

#     style_default: dict = pydantic.Field({}, description="Component class name")


class ConnectionVizSpecs(pydantic.BaseModel):
    """Specification for the visual representation of connections between components.

    This model defines the visualization specifications for connections including the naming
    patterns for source and target components and ports, the style to apply to the visualization,
    and whether or not to ignore the connection.

    Attributes:
        comp_source (str): Regular expression pattern that matches the name of the source components.
                           Default is ".*" to match any component name.
        port_source (str): Regular expression pattern that matches the name of the source component ports.
                           Default is ".*" to match any port name.
        comp_target (str): Regular expression pattern that matches the name of the target components.
                           Default is ".*" to match any component name.
        port_target (str): Regular expression pattern that matches the name of the target component ports.
                           Default is ".*" to match any port name.
        style (dict): A dictionary specifying style attributes such as color or width for the connection.
        ignore (bool): Indicates if the connection should be ignored in the visualization.
                       Default is False, meaning the connection is not ignored.
        renaming (typing.List[RenamingSpecs]): List of RenamingSpecs instances which define
                                               how the connection attributes should be renamed.
        conditions (typing.List[StyleConditionSpecs]): List of StyleConditionSpecs instances which define
                                                       the conditions under which certain styles should
                                                       be applied.

    """

    comp_source: str = pydantic.Field(".*", description="Source component name pattern")
    port_source: str = pydantic.Field(".*", description="Source component port name pattern")
    comp_target: str = pydantic.Field(".*", description="Target component name pattern")
    port_target: str = pydantic.Field(".*", description="Target component port name pattern")
    style: dict = pydantic.Field({}, description="Styling")
    ignore: bool = pydantic.Field(False, description="Indicatre if the connection must be ignored")

    renaming: typing.List[RenamingSpecs] = \
        pydantic.Field([], description="Renamming specs")
    conditions: typing.List[StyleConditionSpecs] = \
        pydantic.Field([], description="Styling conditions")

    
class COD3SVizSpecs(ObjCOD3S):
    """Defines the visualization specifications for components and connections in a COD3S system.

    This class includes methods for applying those specifications to given system components and connections,
    updating their visual representation accordingly.

    Attributes:
        components (typing.Dict[str, ComponentVizSpecs]): A dictionary where each key is an identifier
                                                          for a component visualization specifications and
                                                          the value is a `ComponentVizSpecs` instance.
        connections (typing.Dict[str, ConnectionVizSpecs]): A dictionary where each key is an identifier
                                                            for a connection visualization specifications and
                                                            the value is a `ConnectionVizSpecs` instance.

    Methods:
        apply_comp_specs: Processes and applies component visualization specifications to a given component.
        apply_connection_specs: Processes and applies connection visualization specifications to a given connection.
    """
    components: typing.Dict[str, ComponentVizSpecs] = \
        pydantic.Field({}, description="List of component viz specs")

    connections: typing.Dict[str, ConnectionVizSpecs] = \
        pydantic.Field({}, description="List of connections viz specs")


    def apply_comp_specs(self, comp):

        comp_viz = {
            "name": comp.name(),
            "class_name": comp.className(),
        }

        # Apply component specs and handles renaming and conditions.
        for comp_specs in self.components.values():
            is_match_name = re.search(comp_specs.name, comp.name()) \
                if comp_specs.name else True
            is_match_cls = re.search(comp_specs.type, comp.className()) \
                if comp_specs.type else True
            if is_match_name and is_match_cls:

                comp_specs_cur = \
                    comp_specs.dict(exclude={"name",
                                             "type",
                                             "renaming",
                                             "conditions",
                                             })
                comp_specs_cur = {k: v for k, v in comp_specs_cur.items() if v}
                comp_specs_cur.setdefault("style", {})
                #comp_specs_cur.pop("cls")

                if ports_spec := comp_specs.apply_ports_specs(comp):
                    comp_specs_cur["ports"] = ports_spec
    
                for renaming_inst in comp_specs.renaming:
                    renaming_inst.transform(comp_specs_cur)

                for cond in comp_specs.conditions:

                    if cond.check(mapper={"COMP": comp}):
                        comp_specs_cur["style"].update(cond.style)
                
                #comp_viz.update(comp_specs_cur)
                update_dict_deep(comp_viz, comp_specs_cur,
                                 key_attr="name")

                # if comp.basename() == "S":
                #     ipdb.set_trace()

        return comp_viz
   
    def apply_connection_specs(self,
                               comp_source,
                               port_source,
                               comp_target,
                               port_target):
        """Applies connection visualization specifications to a given connection.

        Args:
            comp_source: The source component of the connection.
            port_source: The source port of the connection.
            comp_target: The target component of the connection.
            port_target: The target port of the connection.

        Returns:
            A dictionary with the visualization specifications for the given connection or `None` if the
            connection is specified to be ignored.
        """

        comp_source_name = comp_source.basename()
        comp_target_name = comp_target.basename()
        port_source_name = port_source.basename()
        port_target_name = port_target.basename()

        conn_viz = {
            "comp_source": comp_source_name,
            "port_source": port_source_name,
            "comp_target": comp_target_name,
            "port_target": port_target_name,
        }

        # Apply connection specs and handles renaming.
        for conn_specs in self.connections.values():

            is_match_comp_source_name = re.search(conn_specs.comp_source,
                                                  comp_source_name) \
                if conn_specs.comp_source else True
            is_match_port_source_name = re.search(conn_specs.port_source,
                                                  port_source_name) \
                if conn_specs.port_source else True
            is_match_comp_target_name = re.search(conn_specs.comp_target,
                                                  comp_target_name) \
                if conn_specs.comp_target else True
            is_match_port_target_name = re.search(conn_specs.port_target,
                                                  port_target_name) \
                if conn_specs.port_target else True
            
            if is_match_comp_source_name and \
               is_match_port_source_name and \
               is_match_comp_target_name and \
               is_match_port_target_name:

                if conn_specs.ignore:
                    return None

                conn_viz_cur = \
                    conn_specs.dict(exclude={"comp_source",
                                             "port_source",
                                             "comp_target",
                                             "port_target",
                                             "conditions",
                                             "renaming"})
                conn_viz_cur = {k: v for k, v in conn_viz_cur.items() if v}
                conn_viz_cur.setdefault("style", {})

                for renaming_inst in conn_specs.renaming:
                    renaming_inst.transform(conn_viz_cur)

                for cond in conn_specs.conditions:
                    if cond.check(mapper={
                            "CS": comp_source,
                            "PS": port_source,
                            "CT": comp_target,
                            "PT": port_target}):
                        conn_viz_cur["style"].update(cond.style)

                conn_viz.update(conn_viz_cur)

        return conn_viz
                        
    
class COD3SProject(ObjCOD3S):
    """
    COD3SProject manages the state and visualization specifications of a COD3S project.

    Attributes:
        project_name (str): Name of the project.
        project_path (str): Filesystem path to the project.
        system_name (str): Name of the system within the project.
        system_filename (str): Filename of the system definition script.
        system_class_name (str): Name of the system's class.
        system_params (dict): Parameters for initializing the system.
        viz_specs_filename (str): Filename of the visualization specifications.
        viz_specs (COD3SVizSpecs): Visualization specifications object.
        system_viz_current (dict): Current state of system visualization.
        system (typing.Any): Instance of the system.
        front_cfg_filename (typing.Any): Configuration file for frontend interactions.
        front_cfg (dict): Loaded frontend configuration.
        ts_last_modification (float): Timestamp of the last modification in UTC.
        logger (typing.Any): Logging handler.

    Methods:
        read_front_cfg: Reads the frontend configuration from `front_cfg_filename` into `front_cfg`.
        write_front_cfg: Writes the `front_cfg` dictionary into the `front_cfg_filename` path as JSON.
        update_positions: Updates position data in `front_cfg` based on passed positions.
        get_system_viz: Retrieves the current state visualization of the system.
        get_system_viz_updates: Gives the updates between the current and new visualization states of the system.
    """

    project_name: str = pydantic.Field(..., description="Project name")

    project_path: str = pydantic.Field(".", description="Project path")    

    system_name: str = pydantic.Field(..., description="System name")

    system_filename: str = pydantic.Field(..., description="System filename")

    system_class_name: str = pydantic.Field(..., description="System class name")

    system_params: dict = pydantic.Field({}, description="System params")

    viz_specs_filename: str = pydantic.Field(None, description="The system object")
    
    viz_specs: COD3SVizSpecs = pydantic.Field(None, description="The system object")

    system_viz_current: dict = \
        pydantic.Field(None, description="System viz dictionnary current")
    
    system: typing.Any = pydantic.Field(None, description="The system object")

    front_cfg_filename: typing.Any = pydantic.Field(".front_cfg.json",
                                                    description="Front config filename")

    front_cfg: dict = pydantic.Field({}, description="Front configuration")
    
    ts_last_modification: float = \
        pydantic.Field(None, description="Last modification timestamp in UTC")

    logger: typing.Any = pydantic.Field(None, description="Logger")

    def __init__(self, **data: typing.Any):
        """Initializes the COD3SProject with provided data.

        This initialization ensures that the project path is included in the system
        path, dynamically imports the system module defined by
        `system_filename`, instantiates the system using the defined class name,
        loads visualization specifications, sets up the current system visualization,
        timestamps the last modification, and reads the frontend configuration.

        Args:
            data: Arbitrary keyword arguments that are passed to the parent class
                  and used for project initialization.

        Raises:
            ImportError: If the module or class specified for the system cannot be imported.
            FileNotFoundError: If the `viz_specs_filename` does not point to a valid file.
            Exception: If any other unforeseen error occurs during initialization.
        """
        super().__init__(**data)

        # Ensure the project path  is in the Python path
        sys.path.insert(0, os.path.dirname(self.project_path))

        # Dynamically import the system using specified filename and class name.
        system_module_name = self.system_filename.replace(".py", "")
        system_module_spec = \
            importlib.util.spec_from_file_location(
                system_module_name,
                self.system_filename)
        system_module = importlib.util.module_from_spec(system_module_spec)
        sys.modules[system_module_name] = system_module
        system_module_spec.loader.exec_module(system_module)
        system_class = getattr(system_module, self.system_class_name)

        # Create an instance of the system.
        self.system = system_class(self.system_name, **self.system_params)

        # Load visualization specifications, if provided.
        if self.viz_specs_filename:
            self.viz_specs = COD3SVizSpecs.from_yaml(self.viz_specs_filename,
                                                     add_cls=True)

        # Read the frontend configuration.
        self.read_front_cfg()

        # Set up the current visualization of the system.    
        self.system_viz_current = self.get_system_viz()

        # Update the timestamp of the last modification.
        self.update_ts_last_modification()

    def read_front_cfg(self):
        """Reads the frontend configuration from a JSON file.

        The configuration file location is determined by the `front_cfg_filename`
        attribute. If found, it loads the JSON content into the `front_cfg`
        attribute; otherwise, it initializes `front_cfg` with default values for
        positions, components, and connections.

        The default positions structure is set if the JSON file does not exist or
        does not contain the 'positions' key. The structure includes 'positions',
        'components', and 'connections' dictionaries.
        """
        front_cfg_filename = \
            os.path.join(self.project_path, self.front_cfg_filename)

        # Load existing configuration if the file is present.
        if os.path.isfile(front_cfg_filename):
            with open(front_cfg_filename, 'r') as f:
                self.front_cfg = json.load(f)

        # Ensure that 'positions', 'components', and 'connections' keys are set.
        self.front_cfg.setdefault("positions", {})
        self.front_cfg["positions"].setdefault("components", {})
        self.front_cfg["positions"].setdefault("connections", {})
        
    def write_front_cfg(self):
        """Writes the current frontend configuration to a JSON file.
        
        The file is saved to the path specified by combining the `front_cfg_filename` with
        the `project_path`. If the file already exists, it will be overwritten.
        
        Raises:
            FileNotFoundError: If the directory specified in `project_path` does not exist.
            IOError: If the file could not be written to for other reasons, such as permissions.
        """

        front_cfg_filename = \
            os.path.join(self.project_path, self.front_cfg_filename)

        with open(front_cfg_filename, 'w') as f:
            json.dump(self.front_cfg, f)

    def update_positions(self, positions):
        """Updates the position data for components within the frontend configuration.

        It processes the provided `positions` dictionary to update the location of each
        component in the `front_cfg`. Existing positions can be modified or new ones can be
        added.

        Args:
            positions (dict): A dictionary containing the updated positions data with
                              "components" as a key and a list of component positions, each
                              containing a component name and new x, y coordinates.

        For example:
            positions = {
                "components": [
                    {"comp_name": "component1", "x": 100, "y": 150},
                    {"comp_name": "component2", "x": 200, "y": 250},
                ]
            }

        This method modifies the `front_cfg` attribute in place.
        """

        # Update the components positions based on the input data
        for position in positions.get("components", {}):
            comp_name = position['comp_name']
            self.front_cfg["positions"]["components"][comp_name] = {
                "x": position['x'],
                "y": position['y'],
            }

            
    def update_ts_last_modification(self):
        """Updates the timestamp of the last modification to the current UTC time.

        This method sets `ts_last_modification` to the current timestamp in UTC.
        The timestamp is a float representing the time elapsed since the Unix
        epoch in seconds.
        """
        self.ts_last_modification = \
            datetime.now(timezone.utc).timestamp()
        
    def dict(self, **kwrds):

        exclude_list = ["system",
                        "interactive_simulation_sequence",
                        "viz_specs",
                        "front_cfg",
                        "logger",
                        ]
        if kwrds.get("exclude"):
            [kwrds["exclude"].add(attr) for attr in exclude_list]
        else:
            kwrds["exclude"] = set(exclude_list)
            
        return super().dict(**kwrds)

    def get_system_viz(self):
        """Retrieves the visualization data for all components and connections in the system.

        This method iterates over all the components and their connections in the system
        and applies the visualization specifications to them. If visualization
        specifications (`viz_specs`) are defined, they are applied to each component
        and connection to generate the visualization representation.

        Returns:
            A dictionary with two keys "components" and "connections", each containing
            lists of dictionaries representing the visual properties of system components
            and their connections, respectively, according to the visualization
            specifications.

        Note:
            It is assumed that visualization representations are only needed for
            components and connections with defined visualization specifications
            (`viz_specs`).
        """

        comp_viz_list = []
        for comp in self.system.components("#.*", "#.*"):

            # We include components with viz specs in the visualization.
            if self.viz_specs:
                comp_viz = self.viz_specs.apply_comp_specs(comp)
                comp_viz["position"] = \
                    self.front_cfg["positions"]["components"].get(comp.name(), {})
                
                comp_viz_list.append(comp_viz)

        conn_viz_list = []

        for comp_source_cur in self.system.components("#.*", "#.*"):
            for port_source_cur in comp_source_cur.messageBoxes():
                for cnx in range(port_source_cur.cnctCount()):

                    port_target_cur = port_source_cur.cnct(cnx)
                    comp_target_cur = port_target_cur.parent()

                    if self.viz_specs:
                        conn_viz = \
                            self.viz_specs.apply_connection_specs(
                                comp_source=comp_source_cur,
                                port_source=port_source_cur,
                                comp_target=comp_target_cur,
                                port_target=port_target_cur,
                            )
                        #conn_viz_cur.update(conn_viz_extra)
                        if conn_viz:
                            conn_viz_list.append(conn_viz)
            
        return {
            "components": comp_viz_list,
            "connections": conn_viz_list,
        }

    def get_system_viz_updates(self):
        """Calculates changes between the current and new system visualizations.

        This method gets the latest visualization data of the system and compares it 
        with the current visualization data to find any updates.

        Returns:
            A tuple containing two elements:
            1. A dictionary representing the updates between the current and new
               visualization data.
            2. The new visualization data as a dictionary.

        The `dict_diff` function is used to calculate the differences between the
        current and new visualization data.
        """
        system_viz_new = self.get_system_viz()
        viz_updates = \
            dict_diff(self.system_viz_current,
                      system_viz_new)
        
        return viz_updates, system_viz_new
