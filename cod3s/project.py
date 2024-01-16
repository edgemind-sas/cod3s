import pydantic
import typing
import pkg_resources
from .core import ObjCOD3S
import importlib.util
import sys
import os
import re

installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
if 'ipdb' in installed_pkg:
    import ipdb  # noqa: F401



class RenamingSpecs(pydantic.BaseModel):

    attr: str = pydantic.Field(..., description="Attribute to rename")
    pattern: str = pydantic.Field(..., description="Pattern to rename")
    replace: str = pydantic.Field(..., description="Replace value")

    def transform(self, document):

        attr_val = document.get(self.attr)
        if attr_val and isinstance(attr_val, str):
            document[self.attr] = re.sub(self.pattern, self.raplace, attr_val)
    

class ComponentVizSpecs(ObjCOD3S):

    name_pattern: str = pydantic.Field(".*", description="Component name regex")

    class_pattern: str = pydantic.Field(".*", description="Component class regex")

    renaming: typing.List[RenamingSpecs] = \
        pydantic.Field([], description="Renamming specs")
    
    ports: typing.Dict[str, str] = pydantic.Field({}, description="Connection ports position")

    style: dict = pydantic.Field({}, description="Styling")

    
            
    
# class ComponentViz(ObjCOD3S):

#     name: str = pydantic.Field(..., description="Component name")
    
#     class_name: str = pydantic.Field(..., description="Component class name")

#     ports: typing.Dict[str, str] = pydantic.Field({}, description="Connection ports position")

#     style_default: dict = pydantic.Field({}, description="Component class name")


class ConnectionVizSpecs(ObjCOD3S):

    name_pattern: str = pydantic.Field(".*", description="Connections name regex")
    style: dict = pydantic.Field({}, description="Styling")

    renaming: typing.List[RenamingSpecs] = \
        pydantic.Field([], description="Renamming specs")

    
class COD3SVizSpecs(ObjCOD3S):

    components: typing.Dict[str, ComponentVizSpecs] = \
        pydantic.Field({}, description="List of component viz specs")

    connections: typing.Dict[str, ConnectionVizSpecs] = \
        pydantic.Field({}, description="List of connections viz specs")


    def apply_comp_specs(self, comp):

        comp_viz = {}
        
        for comp_specs in self.components.values():
            if re.search(comp_specs.name_pattern, comp.name()) and \
               re.search(comp_specs.class_pattern, comp.className()):

                comp_specs_cur = \
                    comp_specs.dict(exclude={"name_pattern",
                                             "class_pattern",
                                             "renaming"})
                comp_specs_cur.pop("cls")

                for renaming_inst in comp_specs.renaming:
                    renaming_inst.transform(comp_specs_cur)
                
                comp_viz.update(comp_specs_cur)

        return comp_viz

    
    def apply_connection_specs(self, conn):

        conn_viz = {}
        for conn_specs in self.connections.values():
            
            if re.search(conn_specs.name_pattern, conn.basename()):

                conn_viz_cur = \
                    conn_specs.dict(exclude={"name_pattern",
                                             "renaming"})
                conn_viz_cur.pop("cls")

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

    system: typing.Any = pydantic.Field(None, description="The system object")

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

            comp_viz = {
                "name": comp.name(),
                "class_name": comp.className(),
            }

            if self.viz_specs:
                comp_viz_extra = self.viz_specs.apply_comp_specs(comp)
                comp_viz.update(comp_viz_extra)

            comp_viz_list.append(comp_viz)

        conn_viz_list = []

        for comp in self.system.components("#.*", "#.*"):
            for mb in comp.messageBoxes():
                for cnx in range(mb.cnctCount()):

                    conn_cur = mb.cnct(cnx)
                    comp_target = conn_cur.parent()

                    comp_source_name = comp.basename()
                    comp_target_name = comp_target.basename()

                    conn_viz_cur = {
                        "comp_source": comp_source_name,
                        "port_source": mb.basename(),
                        "comp_target": comp_target_name,
                        "port_target": conn_cur.basename(),
                    }

                    if self.viz_specs:
                        conn_viz_extra = \
                            self.viz_specs.apply_connection_specs(mb)
                        conn_viz_cur.update(conn_viz_extra)

                    conn_viz_list.append(conn_viz_cur)
            
        return {
            "components": comp_viz_list,
            "connections": conn_viz_list,
        }

            


            
