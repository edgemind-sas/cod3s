import Pycatshoo as pyc
import pydantic
import typing
import pandas as pd
import numpy as np
import plotly.express as px
import re
from ..core import ObjCOD3S
from .common import parse_quantile

PandasDataFrame = typing.TypeVar("pd.core.dataframe")


class IndicatorModel(ObjCOD3S):
    """
    A model representing an indicator in Pycatshoo.

    Attributes:
        name (str): Indicator short name.
        label (str): Indicator long name.
        description (str): Indicator description.
        unit (str): Indicator unit.
        measure (str): Measure to be computed.
        stats (list): Stats to be computed.
        instants (list): Instant of computation.
        values (PandasDataFrame): Indicator estimates.
        metadata (dict): Dictionary of metadata.
        bkd (typing.Any): Indicator backend handler.
    """

    name: str = pydantic.Field(None, description="Indicator short name")
    name_pattern: str = pydantic.Field(None, description="Indicator naming pattern")
    label: str = pydantic.Field(None, description="Indicator long name")
    description: str = pydantic.Field("", description="Indicator description")
    unit: str = pydantic.Field("", description="Indicator unit")
    measure: str = pydantic.Field(
        "value", description="measure to be computed : None, sojourn-time, etc."
    )
    stats: list = pydantic.Field([], description="Stats to be computed")
    instants: list = pydantic.Field([], description="Instant of computation")
    values: PandasDataFrame = pydantic.Field(None, description="Indicator estimates")
    metadata: dict = pydantic.Field({}, description="Dictionary of metadata")
    bkd: typing.Any = pydantic.Field(None, description="Indicator backend handler")

    @pydantic.model_validator(mode="after")
    def cls_validator(cls, obj):
        """
        Validate the class after initialization.

        Args:
            obj: The object to validate.

        Returns:
            The validated object.
        """
        if obj.label is None:
            obj.label = obj.name

        if obj.description is None:
            obj.description = obj.label

        return obj


class PycIndicator(IndicatorModel):
    """
    A class representing a Pycatshoo indicator.

    Methods:
        get_type: Abstract method to get the type of the indicator.
        get_expr: Abstract method to get the expression of the indicator.
        create_bkd: Abstract method to create the indicator backend.
        set_indicator: Sets the indicator in the system backend.
        update_restitution: Updates the restitution of the indicator.
        update_computation: Updates the computation of the indicator.
        to_pyc_stats: Converts the statistic name to Pycatshoo stats.
    """

    def get_type(self):
        """
        Abstract method to get the type of the indicator.

        Raises:
            ValueError: If the method is not implemented.
        """
        raise ValueError("Method get_type must be implemented")

    def get_expr(self):
        """
        Abstract method to get the expression of the indicator.

        Raises:
            ValueError: If the method is not implemented.
        """
        raise ValueError("Method get_expr must be implemented")

    def create_bkd(self, system_bkd):
        """
        Abstract method to create the indicator backend.

        Args:
            system_bkd: The system backend.

        Raises:
            NotImplementedError: If the method is not implemented.
        """
        raise NotImplementedError("methode create_bkd must be overloaded")

    def set_indicator(self, system_bkd):
        """
        Set the indicator in the system backend.

        Args:
            system_bkd: The system backend.
        """
        self.create_bkd(system_bkd)
        self.update_restitution()
        self.update_computation()

    def update_restitution(self):
        """Update the restitution of the indicator."""
        restitution = 0
        for stat in self.stats:
            if stat == "mean":
                restitution |= pyc.TIndicatorType.mean_values
            elif stat == "stddev":
                restitution |= pyc.TIndicatorType.std_dev
            elif stat.startswith("qle"):
                restitution |= pyc.TIndicatorType.quantile_le
                pct_list = parse_quantile(stat, return_pct=True)
                self.bkd.setPctQuantileLeValue(pct_list[0])
            elif re.match(r"P\d{1,2}$", stat) and 0 <= int(stat[1:]) <= 49:
                restitution |= pyc.TIndicatorType.quantile_le
                self.bkd.setPctQuantileLeValue(int(stat[1:]))
            elif stat.startswith("qgt"):
                restitution |= pyc.TIndicatorType.quantile_gt
                pct_list = parse_quantile(stat, return_pct=True)
                self.bkd.setPctQuantileGtValue(pct_list[0])
            elif re.match(r"P\d{1,3}$", stat) and 50 <= int(stat[1:]) <= 100:
                restitution |= pyc.TIndicatorType.quantile_gt
                self.bkd.setPctQuantileGtValue(100 - int(stat[1:]))

            elif stat == "all_values":
                restitution |= pyc.TIndicatorType.all_values
            else:
                raise ValueError(
                    f"Stat {stat} not supported for Pycatshoo indicator restitution"
                )

        self.bkd.setRestitutions(restitution)

    def update_computation(self):
        """Update the computation of the indicator."""
        if self.measure == "value":
            computation = pyc.TComputationType.simple
        elif self.measure == "sojourn-time":
            computation = pyc.TComputationType.res_time
        elif self.measure == "nb-occurrences":
            computation = pyc.TComputationType.nb_visits
        elif self.measure == "had_value":
            computation = pyc.TComputationType.realized
        else:
            raise ValueError(
                f"Measure {self.measure} not supported for Pycatshoo indicator computaiton"
            )

        self.bkd.setComputation(computation)

    def to_pyc_stats(self, stat_name):
        """
        Convert the statistic name to Pycatshoo stats.

        Args:
            stat_name (str): The name of the statistic.

        Returns:
            The corresponding Pycatshoo statistic.

        Raises:
            ValueError: If the statistic is not supported.
        """
        if stat_name == "mean":
            return self.bkd.means
        elif stat_name == "stddev":
            return self.bkd.stdDevs
        elif stat_name.startswith("qle") or (
            re.match(r"P\d{1,2}$", stat_name) and 0 <= int(stat_name[1:]) <= 49
        ):
            return self.bkd.quantilesLe
        elif stat_name.startswith("qgt") or (
            re.match(r"P\d{1,3}$", stat_name) and 50 <= int(stat_name[1:]) <= 100
        ):
            return self.bkd.quantilesGt
        elif stat_name == "all_values":
            return self.bkd.values
        else:
            raise ValueError(f"Statistic {stat_name} not supported")


class PycFunIndicator(PycIndicator):
    """
    A class representing a function-based indicator in Pycatshoo.

    Attributes:
        fun (typing.Any): Indicator function.

    Methods:
        create_bkd: Creates the indicator backend.
        update_values: Updates the values of the indicator.
    """

    fun: typing.Any = pydantic.Field(..., description="Indicator function")

    def create_bkd(self, system_bkd):
        """
        Create the indicator backend.

        Args:
            system_bkd: The system backend.
        """
        self.bkd = system_bkd.addIndicator(self.name, self.fun)

    def update_values(self, system_bkd=None):
        """
        Update the values of the indicator.

        Args:
            system_bkd: The system backend.
        """
        """
        Updates the values of the indicator.

        Args:
            system_bkd: The system backend.
        """
        if not (self.instants) and system_bkd:
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

            data_list.append(pd.DataFrame(dict(data_core, **self.metadata)))

        self.values = pd.concat(data_list, axis=0, ignore_index=True)


class PycAttrIndicator(PycIndicator):
    """
    A class representing a variable-based indicator in Pycatshoo.

    Attributes:
        component (str): Component name.
        var (str): Variable name.
        operator (str): Operator on variable.
        value_test (typing.Any): Value to be checked.

    Methods:
        get_type: Returns the type of the indicator.
        get_comp_name: Returns the component name.
        get_attr_name: Returns the attribute name.
        get_expr: Returns the expression of the indicator.
        create_bkd: Creates the indicator backend.
        update_values: Updates the values of the indicator.
    """

    component: str = pydantic.Field(..., description="Component name")
    attr_name: str = pydantic.Field(..., description="Attribute name")
    attr_type: str = pydantic.Field("VAR", description="Attribute type : VAR, ST, etc")
    operator: str = pydantic.Field("==", description="Operator on variable")
    value_test: typing.Any = pydantic.Field(None, description="Value to be checked")

    def get_comp_name(self):
        """
        Return the component name.

        Returns:
            str: The component name.
        """
        return f"{self.component}"

    def get_expr(self):
        """
        Return the expression of the indicator.

        Returns:
            str: The expression of the indicator.
        """
        return f"{self.component}.{self.attr_name}"

    @pydantic.model_validator(mode="before")
    def cls_validator(cls, obj):
        """
        Validate the class before initialization.

        Args:
            obj: The object to validate.

        Returns:
            The validated object.
        """
        if obj.get("name_pattern") is None:
            obj["name_pattern"] = "{component}_{attr_name}"
            if obj.get("measure"):
                obj["name_pattern"] += "_{measure}"

        if obj.get("name") is None:
            obj["name"] = obj["name_pattern"].format(**obj)

        if obj.get("label") is None:
            obj["label"] = obj["name"]

        if obj.get("description") is None:
            obj["description"] = obj["label"]

        return obj

    def create_bkd(self, system_bkd):
        """
        Create the indicator backend.

        Args:
            system_bkd: The system backend.
        """
        if self.value_test is None:
            # if self.attr_type == "AUT":
            self.bkd = system_bkd.addIndicator(
                self.name, self.get_expr(), self.attr_type
            )
        else:
            self.bkd = system_bkd.addIndicator(
                self.name,
                self.get_expr(),
                self.attr_type,
                self.operator,
                self.value_test,
            )

    def update_values(self, system_bkd=None):
        if not (self.instants) and system_bkd:
            self.instants = list(system_bkd.instants())

        data_list = []
        for stat in self.stats:
            if stat == "all_values":
                for i, inst in enumerate(self.instants):
                    values = pd.Series(self.to_pyc_stats(stat)(i))
                    print(i, inst, values.quantile(0.5))
                    raise ValueError("All values stat computation not implemented yet")
            data_core = {
                "name": self.name,
                "label": self.label,
                "description": self.description,
                "comp": self.get_comp_name(),
                "attr": self.attr_name,
                "operator": self.operator,
                "value_test": self.value_test,
                "type": self.attr_type,
                "measure": self.measure,
                "stat": stat,
                "instant": self.instants,
                "values": self.to_pyc_stats(stat)(),
                "unit": self.unit,
            }

            data_list.append(pd.DataFrame(dict(data_core, **self.metadata)))

        self.values = pd.concat(data_list, axis=0, ignore_index=True)


class PycVarIndicator(PycIndicator):
    """
    A class representing a variable-based indicator in Pycatshoo.

    Attributes:
        component (str): Component name.
        var (str): Variable name.
        operator (str): Operator on variable.
        value_test (typing.Any): Value to be checked.

    Methods:
        get_type: Returns the type of the indicator.
        get_comp_name: Returns the component name.
        get_attr_name: Returns the attribute name.
        get_expr: Returns the expression of the indicator.
        create_bkd: Creates the indicator backend.
        update_values: Updates the values of the indicator.
    """

    component: str = pydantic.Field(..., description="Component name")
    var: str = pydantic.Field(..., description="Variable name")
    operator: str = pydantic.Field("==", description="Operator on variable")
    value_test: typing.Any = pydantic.Field(None, description="Value to be checked")

    def get_type(self):
        """
        Return the type of the indicator.

        Returns:
            str: The type of the indicator.
        """
        return "VAR"

    def get_comp_name(self):
        """
        Return the component name.

        Returns:
            str: The component name.
        """
        return f"{self.component}"

    def get_attr_name(self):
        """
        Return the attribute name.

        Returns:
            str: The attribute name.
        """
        return f"{self.var}"

    def get_expr(self):
        """
        Return the expression of the indicator.

        Returns:
            str: The expression of the indicator.
        """
        return f"{self.component}.{self.var}"

    @pydantic.model_validator(mode="before")
    def cls_validator(cls, obj):
        """
        Validate the class before initialization.

        Args:
            obj: The object to validate.

        Returns:
            The validated object.
        """
        if obj.get("name") is None:
            obj["name"] = f"{obj['component']}.{obj['var']}"

        if obj.get("label") is None:
            obj["label"] = obj["name"]

        if obj.get("description") is None:
            obj["description"] = obj["label"]

        return obj

    def create_bkd(self, system_bkd):
        """
        Create the indicator backend.

        Args:
            system_bkd: The system backend.
        """
        if self.value_test is None:
            self.bkd = system_bkd.addIndicator(self.name, self.get_expr(), "VAR")
        else:
            self.bkd = system_bkd.addIndicator(
                self.name, self.get_expr(), "VAR", self.operator, self.value_test
            )

    def update_values(self, system_bkd=None):
        if not (self.instants) and system_bkd:
            self.instants = list(system_bkd.instants())

        data_list = []
        for stat in self.stats:
            data_core = {
                "name": self.name,
                "label": self.label,
                "description": self.description,
                "comp": self.get_comp_name(),  # TODO: COMP MUST BE DEPRECATED
                "component": self.get_comp_name(),
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

            data_list.append(pd.DataFrame(dict(data_core, **self.metadata)))

        self.values = pd.concat(data_list, axis=0, ignore_index=True)


class PycSTIndicator(PycIndicator):
    """
    A class representing a variable-based indicator in Pycatshoo.

    Attributes:
        component (str): Component name.
        var (str): Variable name.
        operator (str): Operator on variable.
        value_test (typing.Any): Value to be checked.

    Methods:
        get_type: Returns the type of the indicator.
        get_comp_name: Returns the component name.
        get_attr_name: Returns the attribute name.
        get_expr: Returns the expression of the indicator.
        create_bkd: Creates the indicator backend.
        update_values: Updates the values of the indicator.
    """

    component: str = pydantic.Field(..., description="Component name")
    state: str = pydantic.Field(..., description="State name")
    operator: str = pydantic.Field("==", description="Operator on state")
    value_test: typing.Any = pydantic.Field(True, description="Value to be checked")

    def get_type(self):
        """
        Return the type of the indicator.

        Returns:
            str: The type of the indicator.
        """
        return "ST"

    def get_comp_name(self):
        """
        Return the component name.

        Returns:
            str: The component name.
        """
        return f"{self.component}"

    def get_attr_name(self):
        """
        Return the attribute name.

        Returns:
            str: The attribute name.
        """
        return f"{self.state}"

    def get_expr(self):
        """
        Return the expression of the indicator.

        Returns:
            str: The expression of the indicator.
        """
        return f"{self.component}.{self.state}"

    @pydantic.model_validator(mode="before")
    def cls_validator(cls, obj):
        """
        Validate the class before initialization.

        Args:
            obj: The object to validate.

        Returns:
            The validated object.
        """
        if obj.get("name") is None:
            obj["name"] = f"{obj['component']}.{obj['state']}"

        if obj.get("label") is None:
            obj["label"] = obj["name"]

        if obj.get("description") is None:
            obj["description"] = obj["label"]

        return obj

    def create_bkd(self, system_bkd):
        """
        Create the indicator backend.

        Args:
            system_bkd: The system backend.
        """
        self.bkd = system_bkd.addIndicator(
            self.name, self.get_expr(), "ST", self.operator, self.value_test
        )

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

            data_list.append(pd.DataFrame(dict(data_core, **self.metadata)))

        self.values = pd.concat(data_list, axis=0, ignore_index=True)
