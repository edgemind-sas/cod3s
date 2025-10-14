import Pycatshoo as Pyc
import cod3s
from pathlib import Path
import os


class ObjFlow(cod3s.PycComponent):
    def __init__(self, name, flow_type="", flow_in_max=-1, flow_out_max=-1, **kwargs):
        super().__init__(name, **kwargs)

        # Global Parameters
        self.flow_type = flow_type
        self.flow_in_max = self.addVariable(
            "flow_in_max", Pyc.TVarType.t_double, flow_in_max
        )
        self.flow_out_max = self.addVariable(
            "flow_out_max", Pyc.TVarType.t_double, flow_out_max
        )

        self.flow_available_out = self.addVariable(
            "flow_available_out", Pyc.TVarType.t_bool, True
        )
        self.flow_available_out.setReinitialized(True)

        # Fluid variables and references
        self.r_flow_in = self.addReference("flow_in")
        self.v_flow_demand_export = self.addVariable(
            "flow_demand_export", Pyc.TVarType.t_double, 0
        )
        self.v_flow_out = self.addVariable("flow_out", Pyc.TVarType.t_double, 0)
        self.r_flow_demand_import = self.addReference("flow_demand_import")

        # Fluid propagation message boxes
        self.addMessageBox(f"{self.flow_prefix}in")
        self.addMessageBoxImport(f"{self.flow_prefix}in", self.r_flow_in, "flow")
        self.addMessageBoxExport(
            f"{self.flow_prefix}in", self.v_flow_demand_export, "flow_demand"
        )

        self.addMessageBox(f"{self.flow_prefix}out")
        self.addMessageBoxExport(f"{self.flow_prefix}out", self.v_flow_out, "flow")
        self.addMessageBoxImport(
            f"{self.flow_prefix}out", self.r_flow_demand_import, "flow_demand"
        )

        # Sensitive and Start Method
        self.r_flow_demand_import.addSensitiveMethod("update_flow_demand")
        self.r_flow_in.addSensitiveMethod("update_flow")

        self.addStartMethod("update_flow")
        self.addStartMethod("update_flow_demand")

        # PDMP Manager
        self.system().pdmp_manager.addEquationMethod("compute_flow", self)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_out)

        self.system().pdmp_manager.addEquationMethod("compute_demand", self)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_demand_export)

        self.addStartMethod("compute_flow")
        self.addStartMethod("compute_demand")

    @property
    def flow_prefix(self):
        return f"{self.flow_type}_" if self.flow_type else ""

    def compute_flow(self):
        self.update_flow()

    def compute_demand(self):
        self.update_flow_demand()

    def compute_iflow_demand(self):
        total_iflow_demand = self.r_flow_demand_import.sumValue(0)

        if (self.flow_out_max.value() >= 0) and (
            total_iflow_demand > self.flow_out_max.value()
        ):
            total_iflow_demand = self.flow_out_max.value()

        if (self.flow_in_max.value() >= 0) and (
            total_iflow_demand > self.flow_in_max.value()
        ):
            total_iflow_demand = self.flow_in_max.value()

        if total_iflow_demand < 0 and self.flow_in_max.value() > 0:
            total_iflow_demand = self.flow_in_max.value()

        return total_iflow_demand

    def compute_iflow(self):
        total_iflow = self.r_flow_in.sumValue(0)

        if (self.flow_in_max.value() >= 0) and (total_iflow > self.flow_in_max.value()):
            total_iflow = self.flow_in_max.value()

        if (self.flow_out_max.value() >= 0) and (
            total_iflow > self.flow_out_max.value()
        ):
            total_iflow = self.flow_out_max.value()

        return total_iflow

    def update_flow_demand(self):
        if self.r_flow_in.cnctCount() > 0:
            iflow_demand = self.compute_iflow_demand()
            if iflow_demand > 0:
                self.v_flow_demand_export.setValue(iflow_demand)
            else:
                self.v_flow_demand_export.setValue(0)

    def update_flow(self):
        if self.r_flow_in.cnctCount() > 0:
            iflow = self.compute_iflow()
            self.v_flow_out.setValue(iflow)


class ObjFlow2I1O(cod3s.PycComponent):
    def __init__(
        self,
        name,
        flow_type_in1,
        flow_type_in2,
        flow_type_out,
        flow_in_max=-1,
        flow_out_max=-1,
        **kwargs,
    ):
        super().__init__(name, **kwargs)

        # Global Parameters
        self.flow_in_max = self.addVariable(
            "flow_in_max", Pyc.TVarType.t_double, flow_in_max
        )
        self.flow_out_max = self.addVariable(
            "flow_out_max", Pyc.TVarType.t_double, flow_out_max
        )

        # Fluid variables and references
        self.r_flow_in1 = self.addReference("flow_in1")
        self.r_flow_in2 = self.addReference("flow_in2")
        self.v_flow_demand_export1 = self.addVariable(
            "flow_demand_export1", Pyc.TVarType.t_double, 0
        )
        self.v_flow_demand_export2 = self.addVariable(
            "flow_demand_export2", Pyc.TVarType.t_double, 0
        )
        self.v_flow_out = self.addVariable("flow_out", Pyc.TVarType.t_double, 0)
        self.r_flow_demand_import = self.addReference("flow_demand_import")

        # Fluid propagation message boxes
        self.addMessageBox(f"{self.flow_prefix(flow_type_in1)}in")
        self.addMessageBoxImport(
            f"{self.flow_prefix(flow_type_in1)}in", self.r_flow_in1, "flow"
        )
        self.addMessageBoxExport(
            f"{self.flow_prefix(flow_type_in1)}in",
            self.v_flow_demand_export1,
            "flow_demand",
        )

        self.addMessageBox(f"{self.flow_prefix(flow_type_in2)}in")
        self.addMessageBoxImport(
            f"{self.flow_prefix(flow_type_in2)}in", self.r_flow_in2, "flow"
        )
        self.addMessageBoxExport(
            f"{self.flow_prefix(flow_type_in2)}in",
            self.v_flow_demand_export2,
            "flow_demand",
        )

        self.addMessageBox(f"{self.flow_prefix(flow_type_out)}out")
        self.addMessageBoxExport(
            f"{self.flow_prefix(flow_type_out)}out", self.v_flow_out, "flow"
        )
        self.addMessageBoxImport(
            f"{self.flow_prefix(flow_type_out)}out",
            self.r_flow_demand_import,
            "flow_demand",
        )

        # Sensitive and Start Method
        self.r_flow_demand_import.addSensitiveMethod("update_flow_demand")
        self.r_flow_in1.addSensitiveMethod("update_flow")
        self.r_flow_in2.addSensitiveMethod("update_flow")

        self.addStartMethod("update_flow")
        self.addStartMethod("update_flow_demand")

        # PDMP Manager
        self.system().pdmp_manager.addEquationMethod("compute_flow", self)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_out)

        self.system().pdmp_manager.addEquationMethod("compute_demand", self)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_demand_export1)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_demand_export2)

        self.addStartMethod("compute_flow")
        self.addStartMethod("compute_demand")

    def flow_prefix(self, flow_type):
        return f"{flow_type}_" if flow_type else ""

    def compute_flow(self):
        self.update_flow()

    def compute_demand(self):
        self.update_flow_demand()

    def compute_iflow_demand(self):
        total_iflow_demand = self.r_flow_demand_import.sumValue(0)

        if (self.flow_out_max.value() >= 0) and (
            total_iflow_demand > self.flow_out_max.value()
        ):
            total_iflow_demand = self.flow_out_max.value()

        if (self.flow_in_max.value() >= 0) and (
            total_iflow_demand > self.flow_in_max.value()
        ):
            total_iflow_demand = self.flow_in_max.value()

        if total_iflow_demand < 0 and self.flow_in_max.value() > 0:
            total_iflow_demand = self.flow_in_max.value()

        return total_iflow_demand

    def compute_iflow(self):
        total_iflow = self.r_flow_in1.sumValue(0) + self.r_flow_in2.sumValue(0)

        if (self.flow_in_max.value() >= 0) and (total_iflow > self.flow_in_max.value()):
            total_iflow = self.flow_in_max.value()

        if (self.flow_out_max.value() >= 0) and (
            total_iflow > self.flow_out_max.value()
        ):
            total_iflow = self.flow_out_max.value()

        return total_iflow

    def update_flow_demand(self):
        iflow_demand = self.compute_iflow_demand()
        if iflow_demand > 0:
            if self.r_flow_in1.cnctCount() > 0:
                self.v_flow_demand_export1.setValue(iflow_demand)
            if self.r_flow_in2.cnctCount() > 0:
                self.v_flow_demand_export2.setValue(iflow_demand)
        else:
            self.v_flow_demand_export1.setValue(0)
            self.v_flow_demand_export2.setValue(0)

    def update_flow(self):
        if self.r_flow_in1.cnctCount() > 0 or self.r_flow_in2.cnctCount() > 0:
            iflow = self.compute_iflow()
            iflow_demand = self.compute_iflow_demand()
            if iflow_demand > 0:
                iflow = min(iflow, iflow_demand)
            self.v_flow_out.setValue(iflow)


class ObjFlowI2O(cod3s.PycComponent):
    def __init__(self, name, flow_type="", flow_in_max=-1, flow_out_max=-1, **kwargs):
        super().__init__(name, **kwargs)

        # Global Parameters
        self.flow_type = flow_type
        self.flow_in_max = self.addVariable(
            "flow_in_max", Pyc.TVarType.t_double, flow_in_max
        )
        self.flow_out_max = self.addVariable(
            "flow_out_max", Pyc.TVarType.t_double, flow_out_max
        )

        # Fluid variables and references
        self.r_flow_in = self.addReference("flow_in")
        self.v_flow_demand_export = self.addVariable(
            "flow_demand_export", Pyc.TVarType.t_double, 0
        )

        self.v_flow_out1 = self.addVariable("flow_out1", Pyc.TVarType.t_double, 0)
        self.v_flow_out2 = self.addVariable("flow_out2", Pyc.TVarType.t_double, 0)

        self.r_flow_demand_import1 = self.addReference("flow_demand_import1")
        self.r_flow_demand_import2 = self.addReference("flow_demand_import2")

        # Fluid propagation message boxes
        self.addMessageBox(f"{self.flow_prefix}in")
        self.addMessageBoxImport(f"{self.flow_prefix}in", self.r_flow_in, "flow")
        self.addMessageBoxExport(
            f"{self.flow_prefix}in", self.v_flow_demand_export, "flow_demand"
        )

        self.addMessageBox(f"{self.flow_prefix}out1")
        self.addMessageBoxExport(f"{self.flow_prefix}out1", self.v_flow_out1, "flow")
        self.addMessageBoxImport(
            f"{self.flow_prefix}out1", self.r_flow_demand_import1, "flow_demand"
        )

        self.addMessageBox(f"{self.flow_prefix}out2")
        self.addMessageBoxExport(f"{self.flow_prefix}out2", self.v_flow_out2, "flow")
        self.addMessageBoxImport(
            f"{self.flow_prefix}out2", self.r_flow_demand_import2, "flow_demand"
        )

        # Sensitive and Start Method
        self.r_flow_demand_import1.addSensitiveMethod("update_flow_demand")
        self.r_flow_demand_import2.addSensitiveMethod("update_flow_demand")
        self.r_flow_in.addSensitiveMethod("update_flow")

        self.addStartMethod("update_flow")
        self.addStartMethod("update_flow_demand")

        # PDMP Manager
        self.system().pdmp_manager.addEquationMethod("compute_flow", self)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_out1)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_out2)

        self.system().pdmp_manager.addEquationMethod("compute_demand", self)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_demand_export)

        self.addStartMethod("compute_flow")
        self.addStartMethod("compute_demand")

    @property
    def flow_prefix(self):
        return f"{self.flow_type}_" if self.flow_type else ""

    def compute_flow(self):
        self.update_flow()

    def compute_demand(self):
        self.update_flow_demand()

    def compute_iflow_demand(self):
        total_iflow_demand = self.r_flow_demand_import1.sumValue(
            0
        ) + self.r_flow_demand_import2.sumValue(0)

        if (self.flow_out_max.value() >= 0) and (
            total_iflow_demand > self.flow_out_max.value()
        ):
            total_iflow_demand = self.flow_out_max.value()

        if (self.flow_in_max.value() >= 0) and (
            total_iflow_demand > self.flow_in_max.value()
        ):
            total_iflow_demand = self.flow_in_max.value()

        if total_iflow_demand < 0 and self.flow_in_max.value() > 0:
            total_iflow_demand = self.flow_in_max.value()

        return total_iflow_demand

    def compute_iflow(self):
        total_iflow = self.r_flow_in.sumValue(0)

        if (self.flow_in_max.value() >= 0) and (total_iflow > self.flow_in_max.value()):
            total_iflow = self.flow_in_max.value()

        if (self.flow_out_max.value() >= 0) and (
            total_iflow > self.flow_out_max.value()
        ):
            total_iflow = self.flow_out_max.value()

        return total_iflow

    def update_flow_demand(self):
        if self.r_flow_in.cnctCount() > 0:
            iflow_demand = self.compute_iflow_demand()
            if iflow_demand > 0:
                self.v_flow_demand_export.setValue(iflow_demand)
            else:
                self.v_flow_demand_export.setValue(0)

    def update_flow(self):
        if self.r_flow_in.cnctCount() > 0:
            iflow = self.compute_iflow()

            demand1 = self.r_flow_demand_import1.sumValue(0)
            demand2 = self.r_flow_demand_import2.sumValue(0)

            value1 = demand1
            value2 = demand2
            if iflow < demand1 + demand2 and demand1 + demand2 > 0:
                percent_value1 = demand1 / (demand1 + demand2)
                percent_value2 = demand2 / (demand1 + demand2)
                value1 = percent_value1 * iflow
                value2 = percent_value2 * iflow

            self.v_flow_out1.setValue(value1)
            self.v_flow_out2.setValue(value2)


class ObjFlowNINO(cod3s.PycComponent):
    def __init__(
        self,
        name,
        flow_types,
        flow_in_max=-1,
        flow_out_max=-1,
        **kwargs,
    ):
        super().__init__(name, **kwargs)

        # Global Parameters
        self.flow_types = flow_types
        self.flow_in_max = self.addVariable(
            "flow_in_max", Pyc.TVarType.t_double, flow_in_max
        )
        self.flow_out_max = self.addVariable(
            "flow_out_max", Pyc.TVarType.t_double, flow_out_max
        )

        self.flow_available_out = self.addVariable(
            "flow_available_out", Pyc.TVarType.t_bool, True
        )
        self.flow_available_out.setReinitialized(True)

        self.r_flow_in_dict = {}
        self.v_flow_demand_export_dict = {}
        self.v_flow_out_dict = {}
        self.r_flow_demand_import_dict = {}

        # PDMP Manager
        self.system().pdmp_manager.addEquationMethod("compute_flow", self)
        self.system().pdmp_manager.addEquationMethod("compute_demand", self)

        # Fluid variables and references
        for flow_type in flow_types:
            r_flow_in = self.addReference(f"flow_{flow_type}_in")
            v_flow_demand_export = self.addVariable(
                f"flow_{flow_type}_demand_export", Pyc.TVarType.t_double, 0
            )

            v_flow_out = self.addVariable(
                f"flow_{flow_type}_out", Pyc.TVarType.t_double, 0
            )
            r_flow_demand_import = self.addReference(f"flow_{flow_type}_demand_import")

            self.r_flow_in_dict[flow_type] = r_flow_in
            self.v_flow_demand_export_dict[flow_type] = v_flow_demand_export
            self.v_flow_out_dict[flow_type] = v_flow_out
            self.r_flow_demand_import_dict[flow_type] = r_flow_demand_import

            # Fluid propagation message boxes
            self.addMessageBox(f"{self.flow_prefix(flow_type)}in")
            self.addMessageBoxImport(
                f"{self.flow_prefix(flow_type)}in", r_flow_in, "flow"
            )
            self.addMessageBoxExport(
                f"{self.flow_prefix(flow_type)}in",
                v_flow_demand_export,
                "flow_demand",
            )

            self.addMessageBox(f"{self.flow_prefix(flow_type)}out")
            self.addMessageBoxExport(
                f"{self.flow_prefix(flow_type)}out", v_flow_out, "flow"
            )
            self.addMessageBoxImport(
                f"{self.flow_prefix(flow_type)}out",
                r_flow_demand_import,
                "flow_demand",
            )

            # Sensitive and Start Method
            r_flow_demand_import.addSensitiveMethod("update_flow_demand")
            r_flow_in.addSensitiveMethod("update_flow")

            # PDMP Manager
            self.system().pdmp_manager.addExplicitVariable(v_flow_out)
            self.system().pdmp_manager.addExplicitVariable(v_flow_demand_export)

        self.addStartMethod("update_flow")
        self.addStartMethod("update_flow_demand")

        self.addStartMethod("compute_flow")
        self.addStartMethod("compute_demand")

    def flow_prefix(self, flow_type):
        return f"{flow_type}_" if flow_type else ""

    def compute_flow(self):
        self.update_flow()

    def compute_demand(self):
        self.update_flow_demand()

    def compute_iflow_demand(self, flow_type):
        total_iflow_demand = self.r_flow_demand_import_dict[flow_type].sumValue(0)

        if (self.flow_out_max.value() >= 0) and (
            total_iflow_demand > self.flow_out_max.value()
        ):
            total_iflow_demand = self.flow_out_max.value()

        if (self.flow_in_max.value() >= 0) and (
            total_iflow_demand > self.flow_in_max.value()
        ):
            total_iflow_demand = self.flow_in_max.value()

        if total_iflow_demand < 0 and self.flow_in_max.value() > 0:
            total_iflow_demand = self.flow_in_max.value()

        return total_iflow_demand

    def compute_iflow(self, flow_type):
        total_iflow = self.r_flow_in_dict[flow_type].sumValue(0)

        if (self.flow_in_max.value() >= 0) and (total_iflow > self.flow_in_max.value()):
            total_iflow = self.flow_in_max.value()

        if (self.flow_out_max.value() >= 0) and (
            total_iflow > self.flow_out_max.value()
        ):
            total_iflow = self.flow_out_max.value()

        return total_iflow

    def update_flow_demand(self):
        for flow_type in self.flow_types:
            iflow_demand = self.compute_iflow_demand(flow_type)
            if iflow_demand > 0:
                if self.r_flow_in_dict[flow_type].cnctCount() > 0:
                    self.v_flow_demand_export_dict[flow_type].setValue(iflow_demand)
            else:
                self.v_flow_demand_export_dict[flow_type].setValue(0)

    def update_flow(self):
        for flow_type in self.flow_types:
            iflow = self.compute_iflow(flow_type)
            iflow_demand = self.compute_iflow_demand(flow_type)
            if self.r_flow_in_dict[flow_type].cnctCount() > 0:
                if iflow_demand > 0:
                    iflow = min(iflow, iflow_demand)
                self.v_flow_out_dict[flow_type].setValue(iflow)


def add_atm2states(
    component,
    name,
    st1="absent",
    st2="present",
    init_st2=False,
    cond_occ_12=True,
    occ_law_12={"cls": "delay", "time": 0},
    occ_interruptible_12=True,
    effects_12={},
    cond_occ_21=True,
    occ_law_21={"cls": "delay", "time": 0},
    occ_interruptible_21=True,
    effects_21={},
    step=None,
):
    """
    Adds a two-state automaton to the component.

    Parameters
    ----------
    name : str
        The name of the automaton.
    st1 : str, optional
        The name of the first state (default is "absent").
    st2 : str, optional
        The name of the second state (default is "present").
    init_st2 : bool, optional
        Indicates if the initial state is the second state (default is False).
    cond_occ_12 : bool or str, optional
        The condition for the transition from the first state to the second state (default is True).
    occ_law_12 : dict, optional
        The occurrence law for the transition from the first state to the second state (default is {"cls": "delay", "time": 0}).
    occ_interruptible_12 : bool, optional
        Indicates if the transition from the first state to the second state is interruptible (default is True).
    effects_12 : list of tuples, optional
        The effects of the transition from the first state to the second state (default is []).
    cond_occ_21 : bool or str, optional
        The condition for the transition from the second state to the first state (default is True).
    occ_law_21 : dict, optional
        The occurrence law for the transition from the second state to the first state (default is {"cls": "delay", "time": 0}).
    occ_interruptible_21 : bool, optional
        Indicates if the transition from the second state to the first state is interruptible (default is True).
    effects_21 : list of tuples, optional
        The effects of the transition from the second state to the first state (default is []).
    """

    st1_name = f"{name}_{st1}"
    st2_name = f"{name}_{st2}"

    aut = cod3s.PycAutomaton(
        name=f"{component.name()}_{name}",
        states=[st1_name, st2_name],
        init_state=st2_name if init_st2 else st1_name,
        transitions=[
            {
                "name": f"{name}_{st1}_{st2}",
                "source": f"{st1_name}",
                "target": f"{st2_name}",
                "is_interruptible": occ_interruptible_12,
                "occ_law": occ_law_12,
            },
            {
                "name": f"{name}_{st2}_{st1}",
                "source": f"{st2_name}",
                "target": f"{st1_name}",
                "is_interruptible": occ_interruptible_21,
                "occ_law": occ_law_21,
            },
        ],
    )

    aut.update_bkd(component)

    # Jump 1 -> 2
    # -----------
    # Conditions
    trans_name_12 = f"{name}_{st1}_{st2}"
    if isinstance(cond_occ_12, bool):
        aut.get_transition_by_name(trans_name_12)._bkd.setCondition(cond_occ_12)

    elif isinstance(cond_occ_12, str):
        aut.get_transition_by_name(trans_name_12)._bkd.setCondition(
            component.variable(cond_occ_12)
        )
    else:
        raise ValueError(
            f"Condition '{cond_occ_12}' for transition {trans_name_12} not supported"
        )

    # Effects
    st2_bkd = aut.get_state_by_name(st2_name)._bkd
    #    var_value_list_12 = component.pat_to_var_value(*effects_12)
    if len(effects_12) > 0:

        def sensitive_method_12():
            if st2_bkd.isActive():
                [
                    getattr(component, var).setValue(value)
                    for var, value in effects_12.items()
                ]

        # setattr(comp._bkd, method_name, sensitive_method)
        method_name_12 = f"effect_{component.name()}_{trans_name_12}"
        aut._bkd.addSensitiveMethod(method_name_12, sensitive_method_12)
        [
            getattr(component, var).addSensitiveMethod(
                method_name_12, sensitive_method_12
            )
            for var, value in effects_12.items()
        ]

        if step:
            step.addMethod(component, method_name_12)

    # Jump 2 -> 1
    # -----------
    # Conditions
    trans_name_21 = f"{name}_{st2}_{st1}"
    if isinstance(cond_occ_21, bool):
        aut.get_transition_by_name(trans_name_21)._bkd.setCondition(cond_occ_21)

    elif isinstance(cond_occ_21, str):
        aut.get_transition_by_name(trans_name_21)._bkd.setCondition(
            component.variable(cond_occ_21)
        )
    else:
        raise ValueError(
            f"Condition '{cond_occ_21}' for transition {trans_name_21} not supported"
        )
    # Effects
    st1_bkd = aut.get_state_by_name(st1_name)._bkd
    # var_value_list_21 = component.pat_to_var_value(*effects_21)
    if len(effects_21) > 0:

        def sensitive_method_21():
            if st1_bkd.isActive():
                [
                    getattr(component, var).setValue(value)
                    for var, value in effects_21.items()
                ]

        # setattr(comp._bkd, method_name, sensitive_method)
        method_name_21 = f"effect_{component.name()}_{trans_name_21}"
        aut._bkd.addSensitiveMethod(method_name_21, sensitive_method_21)
        [
            getattr(component, var).addSensitiveMethod(
                method_name_21, sensitive_method_21
            )
            for var, value in effects_21.items()
        ]

        if step:
            step.addMethod(component, method_name_21)

    # Update automata dict
    # --------------------
    component.system().pdmp_manager.addWatchedTransition(
        aut.get_transition_by_name(trans_name_12)._bkd
    )
    component.system().pdmp_manager.addWatchedTransition(
        aut.get_transition_by_name(trans_name_21)._bkd
    )

    component.automata_d[aut.name] = aut
