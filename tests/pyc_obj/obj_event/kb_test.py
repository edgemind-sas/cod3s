from cod3s.pycatshoo.system import PycSystem
import cod3s
import Pycatshoo as Pyc

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
        iflow_demand = self.compute_iflow_demand()
        self.v_flow_demand_export.setValue(iflow_demand)

    def update_flow(self):
        iflow_demand = self.compute_iflow_demand()
        flow_out = self.compute_iflow()
        if iflow_demand >= 0:
            flow_out = min(iflow_demand, flow_out)
        self.v_flow_out.setValue(flow_out * self.flow_available_out.value())

