import Pycatshoo as pyc
import pydantic
import typing
import pandas as pd
import numpy as np
import plotly.express as px
from ..core import ObjCOD3S
import pkg_resources
installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
# ipdb is a debugger (pip install ipdb)
if 'ipdb' in installed_pkg:
    import ipdb  # noqa: F401


PandasDataFrame = typing.TypeVar('pd.core.dataframe')

class IndicatorModel(ObjCOD3S):
    name: str = pydantic.Field(None, description="Indicator short name")
    label: str = pydantic.Field(None, description="Indicator long name")
    description: str = pydantic.Field(
        "", description="Indicator description")
    unit: str = pydantic.Field("", description="Indicator unit")
    measure: str = pydantic.Field("value", description="measure to be computed : None, sojourn-time, etc.")
    stats: list = pydantic.Field([], description="Stats to be computed")
    instants: list = pydantic.Field([], description="Instant of computation")
    values: PandasDataFrame = pydantic.Field(
        None, description="Indicator estimates")
    metadata: dict = pydantic.Field(
        {}, description="Dictionary of metadata")
    bkd: typing.Any = pydantic.Field(None, description="Indicator backend handler")


    @pydantic.model_validator(mode='after')
    def cls_validator(cls, obj):
        if obj.label is None:
            obj.label = obj.name

        if obj.description is None:
            obj.description = obj.label

        return obj

    
class PycIndicator(IndicatorModel):

    def get_type(self):
        raise ValueError("Method get_type must be implemented")

    def get_expr(self):
        raise ValueError("Method get_expr must be implemented")


    def create_bkd(self, system_bkd):
        """ Create indicator backend"""
        raise NotImplementedError("methode create_bkd must be overloaded")
    
    def set_indicator(self, system_bkd):

        self.create_bkd(system_bkd)
        self.update_restitution()
        self.update_computation()
        
    
    def update_restitution(self):

        restitution = 0
        for stat in self.stats:
            if stat == "mean":
                restitution |= pyc.TIndicatorType.mean_values
            elif stat == "stddev":
                restitution |= pyc.TIndicatorType.std_dev
            else:
                raise ValueError(f"Stat {stat} not supported for Pycatshoo indicator restitution")

        self.bkd.setRestitutions(restitution)

    def update_computation(self):

        if self.measure == "value":
            computation = pyc.TComputationType.simple
        elif self.measure == "sojourn-time":
            computation = pyc.TComputationType.res_time
        elif self.measure == "nb-occurrences":
            computation = pyc.TComputationType.nb_visits
        elif self.measure == "had_value":
            computation = pyc.TComputationType.realized
        else:
            raise ValueError(f"Measure {self.measure} not supported for Pycatshoo indicator computaiton")

        self.bkd.setComputation(computation)

        
    def to_pyc_stats(self, stat_name):

        if stat_name == "mean":
            return self.bkd.means
        elif stat_name == "stddev":
            return self.bkd.stdDevs
        else:
            raise ValueError(f"Statistic {stat_name} not supported")
        

class PycFunIndicator(PycIndicator):
    fun: typing.Any = pydantic.Field(..., description="Indicator function")

    def create_bkd(self, system_bkd):
        self.bkd = system_bkd.addIndicator(
            self.name,
            self.fun)

    def update_values(self, system_bkd=None):

        if not(self.instants) and system_bkd:
            self.instants = list(system_bkd.instants())

        data_list = []
        for stat in self.stats:

            data_core = {
                "name": self.name,
                "label": self.label,
                "description": self.description,
                "type": "FUN",
                "measure": self.measure,
                "stat": stat,
                "instant": self.instants,
                "values": self.to_pyc_stats(stat)(),
                "unit": self.unit,
                }
            
            data_list.append(
                pd.DataFrame(dict(data_core,
                                  **self.metadata)))
            
        self.values = pd.concat(data_list, axis=0, ignore_index=True)


class PycVarIndicator(PycIndicator):
    component: str = pydantic.Field(..., description="Component name")
    var: str = pydantic.Field(..., description="Variable name")
    operator: str = pydantic.Field("==", description="Operator on variable")
    value_test: typing.Any = pydantic.Field(True, description="Value to be checked")
    
    def get_type(self):
        return "VAR"

    def get_comp_name(self):
        return f"{self.component}"

    def get_attr_name(self):
        return f"{self.var}"
    
    def get_expr(self):
        return f"{self.component}.{self.var}"


    @pydantic.model_validator(mode='after')
    def cls_validator(cls, obj):

        if obj.get('name') is None:
            obj['name'] = f"{obj['component']}.{obj['var']}"

        if obj.get('label') is None:
            obj['label'] = obj['name']

        if obj.get('description') is None:
            obj['description'] = obj['label']

        return obj

    def create_bkd(self, system_bkd):
        self.bkd = system_bkd.addIndicator(
            self.name,
            self.get_expr(),
            "VAR",
            self.operator,
            self.value_test)


    def update_values(self, system_bkd=None):

        if not (self.instants) and system_bkd:
            self.instants = list(system_bkd.instants())

        data_list = []
        for stat in self.stats:

            data_core = {
                "name": self.name,
                "label": self.label,
                "description": self.description,
                "comp": self.get_comp_name(),
                "attr": self.get_attr_name(),
                "operator": self.operator,
                "value_test": self.value_test,
                "type": self.get_type(),
                "measure": self.measure,
                "stat": stat,
                "instant": self.instants,
                "values": self.to_pyc_stats(stat)(),
                "unit": self.unit,
                }
            
            data_list.append(
                pd.DataFrame(dict(data_core,
                                  **self.metadata)))
            
        self.values = pd.concat(data_list, axis=0, ignore_index=True)


