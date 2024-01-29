import pydantic
import typing
import pkg_resources
from .core import ObjCOD3S
from .utils import update_dict_deep, dict_diff
import importlib.util
import sys
import os
import re
from datetime import datetime, timezone

installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
if 'ipdb' in installed_pkg:
    import ipdb  # noqa: F401

# Utility functions
def reverse_conn_in_viz_list(conn_viz: dict, conn_viz_list: list) -> bool:
    for existing_conn_viz in conn_viz_list:
        if (existing_conn_viz['comp_target'] == conn_viz['comp_source'] and
                existing_conn_viz['port_target'] == conn_viz['port_source'] and
                existing_conn_viz['comp_source'] == conn_viz['comp_target'] and
                existing_conn_viz['port_source'] == conn_viz['port_target']):
            return True
    return False


class RenamingSpecs(pydantic.BaseModel):

    attr: str = pydantic.Field(..., description="Attribute to rename")
    pattern: str = pydantic.Field(..., description="Pattern to rename")
    replace: str = pydantic.Field(..., description="Replace value")

    def transform(self, document):

        attr_val = document.get(self.attr)
        if attr_val and isinstance(attr_val, str):
            document[self.attr] = re.sub(self.pattern, self.raplace, attr_val)


class StyleConditionSpecs(pydantic.BaseModel):

    expr: str = pydantic.Field(..., description="Boolean expression to evaluate")
    style: dict = pydantic.Field({}, description="Style to be applied")

    def check(self, mapper):
        try:
            res = eval(self.expr.format(**{k: f"mapper['{k}']" for k in mapper.keys()}))
        except:
            res = False
            
        return res
        


class PortVizSpec(pydantic.BaseModel):
    name: str = pydantic.Field(".*", description="Port name pattern")
    spot: str = pydantic.Field(None, description="Port spot")
    color: str = pydantic.Field(None, description="Port color")

    
class ComponentVizSpecs(pydantic.BaseModel):

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

        port_viz_list = []

        for mb in comp.messageBoxes():

            port_viz = {}
                
            port_name_cur = mb.basename()

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

    comp_source: str = pydantic.Field(".*", description="Source component name pattern")
    port_source: str = pydantic.Field(".*", description="Source component port name pattern")
    comp_target: str = pydantic.Field(".*", description="Target component name pattern")
    port_target: str = pydantic.Field(".*", description="Target component port name pattern")
    style: dict = pydantic.Field({}, description="Styling")
    ignore: bool = pydantic.Field(False, description="Indicatre if the connection must be ignored")

    renaming: typing.List[RenamingSpecs] = \
        pydantic.Field([], description="Renamming specs")

    
class COD3SVizSpecs(ObjCOD3S):

    components: typing.Dict[str, ComponentVizSpecs] = \
        pydantic.Field({}, description="List of component viz specs")

    connections: typing.Dict[str, ConnectionVizSpecs] = \
        pydantic.Field({}, description="List of connections viz specs")


    def apply_comp_specs(self, comp):

        comp_viz = {
            "name": comp.name(),
            "class_name": comp.className(),
        }

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
                                             "renaming"})
                conn_viz_cur = {k: v for k, v in conn_viz_cur.items() if v}

                for renaming_inst in conn_specs.renaming:
                    renaming_inst.transform(conn_viz_cur)

                conn_viz.update(conn_viz_cur)

        return conn_viz
                        

    
class COD3SProject(ObjCOD3S):

    project_name: str = pydantic.Field(..., description="Project name")

    project_path: str = pydantic.Field(".", description="Project path")    

    system_name: str = pydantic.Field(..., description="System name")

    system_filename: str = pydantic.Field(..., description="System filename")

    system_class_name: str = pydantic.Field(..., description="System class name")

    viz_specs_filename: str = pydantic.Field(None, description="The system object")
    
    viz_specs: COD3SVizSpecs = pydantic.Field(None, description="The system object")

    system_viz_default: dict = \
        pydantic.Field(None, description="System viz dictionnary by default")
    
    system: typing.Any = pydantic.Field(None, description="The system object")

    ts_last_modification: float = \
        pydantic.Field(None, description="Last modification timestamp in UTC")

    logger: typing.Any = pydantic.Field(None, description="Logger")

    def __init__(self, **data: typing.Any):
        super().__init__(**data)

        # Ensure the project path  is in the Python path
        sys.path.insert(0, os.path.dirname(self.project_path))

        system_module_name = self.system_filename.replace(".py", "")
        system_module_spec = \
            importlib.util.spec_from_file_location(
                system_module_name,
                self.system_filename)
        system_module = importlib.util.module_from_spec(system_module_spec)
        sys.modules[system_module_name] = system_module
        system_module_spec.loader.exec_module(system_module)
        system_class = getattr(system_module, self.system_class_name)
        self.system = system_class(self.system_name)
        
        if self.viz_specs_filename:
            self.viz_specs = COD3SVizSpecs.from_yaml(self.viz_specs_filename,
                                                     add_cls=True)

        self.system_viz_default = self.get_system_viz()
        
        self.update_ts_last_modification()
            

    def update_ts_last_modification(self):

        self.ts_last_modification = \
            datetime.now(timezone.utc).timestamp()
        
    def dict(self, **kwrds):

        exclude_list = ["system", "viz_specs", "logger"]
        if kwrds.get("exclude"):
            [kwrds["exclude"].add(attr) for attr in exclude_list]
        else:
            kwrds["exclude"] = set(exclude_list)
            
        return super().dict(**kwrds)

    def get_system_viz(self):
        
        comp_viz_list = []
        for comp in self.system.components("#.*", "#.*"):

            # Hypothesis, we represent only component with viz specs
            if self.viz_specs:
                comp_viz = self.viz_specs.apply_comp_specs(comp)
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
        return dict_diff(self.system_viz_default,
                         self.get_system_viz())
