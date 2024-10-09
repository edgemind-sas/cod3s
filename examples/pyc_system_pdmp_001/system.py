import Pycatshoo as Pyc
import cod3s
from pathlib import Path
import os


class ObjFlow(cod3s.PycComponent):
    def __init__(
        self, name, flow_type="", flow_in_max=None, flow_out_max=None, **kwargs
    ):
        super().__init__(name, **kwargs)

        self.flow_type = flow_type
        self.flow_in_max = flow_in_max
        self.flow_out_max = flow_out_max

        # Fluid variables and references
        # self.r_is_fed_in = self.addReferencee("is_fed_in")
        # self.v_is_fed_out = self.addVariable("is_fed_out", Pyc.TVarType.t_bool, False)

        # self.v_is_open_in = self.addVariable("is_open_in", Pyc.TVarType.t_bool, True)
        # self.r_is_open_out = self.addReferencee("is_open_out")

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
        # self.addMessageBoxImport(f"{self.flow_prefix}in", self.r_is_fed_in, "is_fed")
        # self.addMessageBoxExport(
        #     f"{self.flow_prefix}in", self.v_is_open_in, "is_open"
        # )

        self.addMessageBox(f"{self.flow_prefix}out")
        self.addMessageBoxExport(f"{self.flow_prefix}out", self.v_flow_out, "flow")
        self.addMessageBoxImport(
            f"{self.flow_prefix}out", self.r_flow_demand_import, "flow_demand"
        )
        # self.addMessageBoxExport(
        #     f"{self.flow_prefix}out", self.v_is_fed_out, "is_fed"
        # )
        # self.addMessageBoxImport(
        #     f"{self.flow_prefix}out", self.r_is_open_out, "is_open"
        # )

        self.r_flow_demand_import.addSensitiveMethod("update_flow_demand")
        self.r_flow_in.addSensitiveMethod("update_flow")

        # self.addStartMethod("update_flow")
        self.addStartMethod("update_flow_demand")

    @property
    def flow_prefix(self):
        return f"{self.flow_type}_" if self.flow_type else ""

    def compute_iflow_demand(self):
        total_iflow_demand = self.r_flow_demand_import.sumValue(0)

        if (self.flow_out_max is not None) and (total_iflow_demand > self.flow_out_max):
            total_iflow_demand = self.flow_out_max

        if (self.flow_in_max is not None) and (total_iflow_demand > self.flow_in_max):
            total_iflow_demand = self.flow_in_max

        return total_iflow_demand

    def compute_iflow(self):
        total_iflow = self.r_flow_in.sumValue(0)

        if (self.flow_in_max is not None) and (total_iflow > self.flow_in_max):
            total_iflow = self.flow_in_max

        if (self.flow_out_max is not None) and (total_iflow > self.flow_out_max):
            total_iflow = self.flow_out_max

        return total_iflow

    def update_flow_demand(self):

        iflow_demand = self.compute_iflow_demand()

        if self.r_flow_in.cnctCount() > 0:
            if iflow_demand > 0:
                self.v_flow_demand_export.setValue(iflow_demand)
            else:
                self.v_flow_demand_export.setValue(0)

        else:
            self.v_flow_out.setValue(iflow_demand)

    def update_flow(self):

        iflow = self.compute_iflow()

        if self.r_flow_in.cnctCount() > 0:
            self.v_flow_out.setValue(iflow)


class Source(ObjFlow):
    pass


class Tank(ObjFlow):
    def __init__(self, name, capacity=1, content_ini=1, **kwargs):
        super().__init__(name, **kwargs)

        # Parameters
        self.p_capacity = self.addVariable("capacity", Pyc.TVarType.t_double, capacity)

        # Internal variables
        self.v_content = self.addVariable("content", Pyc.TVarType.t_double, content_ini)

        # States and automata
        self.add_automaton(
            name="content_status",
            states=["empty", "intermediate", "full"],
            transitions=[
                {
                    "name": "to_empty",
                    "source": "intermediate",
                    "target": "empty",
                    "condition": "is_empty",
                },
                {
                    "name": "to_full",
                    "source": "intermediate",
                    "target": "full",
                    "condition": "is_full",
                },
                {
                    "name": "empty_to_intermediate",
                    "source": "empty",
                    "target": "intermediate",
                    "condition": "is_intermediate",
                },
                {
                    "name": "full_to_intermediate",
                    "source": "full",
                    "target": "intermediate",
                    "condition": "is_intermediate",
                },
            ],
        )
        self.automata["content_status"].bkd.addSensitiveMethod("update_flow_demand")

        # self.automata["content_status"].bkd.addSensitiveMethod("update_content_status")
        self.set_content_status_init_state()

        self.addMessageBox(f"{self.flow_prefix}content")
        self.addMessageBoxExport(
            f"{self.flow_prefix}content", self.v_content, "content"
        )

        # PDMP
        self.system().pdmp_manager.addEquationMethod("compute_content", self)
        self.system().pdmp_manager.addODEVariable(self.v_content)

        for trans in self.automata["content_status"].transitions:
            self.system().pdmp_manager.addWatchedTransition(trans.bkd)

        # Start method
        # self.addStartMethod("init_content")
        # self.addStartMethod("init_states")

    def is_empty(self):
        return self.v_content.value() <= 0

    def is_full(self):
        return self.v_content.value() >= self.p_capacity.value()

    def is_intermediate(self):
        return not (self.is_empty() or self.is_full())

    def compute_content(self):
        # ct = self.system().currentTime()
        # print(f"ode_content | content({ct}) = {self.v_content.dValue()}")
        iFlow = self.r_flow_in.sumValue(0)
        oFlow = self.v_flow_out.value()

        # __import__("ipdb").set_trace()

        self.v_content.setDvdtODE(iFlow - oFlow)

    def set_content_status_init_state(self):
        a_content_status = self.automata["content_status"]

        if self.is_empty():
            state = "empty"
        elif self.is_full():
            state = "full"
        else:
            state = "intermediate"

        a_content_status.set_init_state(state)

    def update_flow_demand(self):

        if self.is_full():

            super().update_flow_demand()

        else:

            if not self.is_empty():
                iflow_demand = self.compute_iflow_demand()
                self.v_flow_out.setValue(iflow_demand)

            self.v_flow_demand_export.setValue(0)

    def update_flow(self):

        if self.is_empty():
            self.v_flow_out.setValue(0)
        elif self.is_full():
            super().update_flow()
        else:
            pass


# TODO !!!
class Pump(ObjFlow):
    def __init__(self, name, flow_prod=1, init_state="start", **kwargs):
        super().__init__(name, **kwargs)

        # self.flow_type = flow_type

        self.v_flow_prod = self.addVariable(
            "flow_prod", Pyc.TVarType.t_double, flow_prod
        )
        # self.v_flow_out = self.addVariable("flow_out", Pyc.TVarType.t_double, 0.0)
        # self.v_flow_in = self.addVariable("flow_in", Pyc.TVarType.t_double, 0.0)

        self.r_cmd = self.addReference("cmd")

        self.add_automaton(
            name="operation",
            states=["stop", "start"],
            init_state=init_state,
            transitions=[
                {
                    "name": "start",
                    "source": "stop",
                    "target": "start",
                    "condition": "start_required",
                },
                {
                    "name": "stop",
                    "source": "start",
                    "target": "stop",
                    "condition": "stop_required",
                },
            ],
        )
        # self.automata["operation"].bkd.addSensitiveMethod("update_flow")
        self.automata["operation"].bkd.addSensitiveMethod("update_flow_demand")

        self.addMessageBox("cmd")
        self.addMessageBoxImport("cmd", self.r_cmd, "signal")

        # self.addStartMethod("update_flow")

    @property
    def content_prefix(self):
        return f"{self.flow_type}_" if self.flow_type else ""

    def start_required(self):
        return (self.r_cmd.cnctCount() > 0) and cod3s.compute_reference_mean(
            self.r_cmd
        ) > 0

    def stop_required(self):
        return (self.r_cmd.cnctCount() > 0) and (not self.start_required())

    # def update_flow(self):

    #     total_iflow = self.r_flow_in.sumValue(0)

    #     if (self.flow_in_max is not None) and (total_iflow > self.flow_in_max):
    #         total_iflow = self.flow_in_max

    #     if (self.flow_out_max is not None) and (total_iflow > self.flow_out_max):
    #         total_iflow = self.flow_out_max

    #     if total_iflow > self.v_flow_prod:
    #         total_iflow = self.flow_out_max

    #     self.v_flow_out.setValue(total_iflow)

    def update_flow_demand(self):

        iflow_demand = self.compute_iflow_demand()

        if self.automata["operation"].get_active_state().name == "start":
            flow_prod = self.v_flow_prod.dValue()
            if iflow_demand > 0 and iflow_demand < flow_prod:
                self.v_flow_demand_export.setDValue(iflow_demand)
            else:
                self.v_flow_demand_export.setDValue(flow_prod)

            # self.v_flow_in.setDValue(self.p_flow_prod.dValue())
        else:
            self.v_flow_demand_export.setDValue(iflow_demand)
            # self.v_flow_out.setDValue(0)
            # self.v_flow_in.setDValue(0)


class Sensor(cod3s.PycComponent):
    def __init__(self, name, measure, obj_type="", **kwargs):
        super().__init__(name, **kwargs)

        self.obj_type = obj_type

        self.v_value_out = self.addVariable("value_out", Pyc.TVarType.t_double, 0.0)
        self.r_value_in = self.addReference("value_in")

        self.addMessageBox(f"{self.obj_prefix}in")
        self.addMessageBoxImport(f"{self.obj_prefix}in", self.r_value_in, measure)

        self.addMessageBox(f"{self.obj_prefix}out")
        self.addMessageBoxExport(f"{self.obj_prefix}out", self.v_value_out, "signal")

        self.system().pdmp_manager.addEquationMethod("compute_value_out", self)
        self.system().pdmp_manager.addExplicitVariable(self.v_value_out)

        self.addStartMethod("compute_value_out")

    @property
    def obj_prefix(self):
        return f"{self.obj_type}_" if self.obj_type else ""

    def compute_value_out(self):
        self.v_value_out.setValue(cod3s.compute_reference_mean(self.r_value_in))


class Automaton(cod3s.PycComponent):
    def __init__(self, name, active_threshold=None, inactive_threshold=None, **kwargs):
        super().__init__(name, **kwargs)

        # if isinstance(active_threshold, str):

        self.active_threshold, self.active_threshold_operator = cod3s.parse_inequality(
            active_threshold
        )
        self.inactive_threshold, self.inactive_threshold_operator = (
            cod3s.parse_inequality(inactive_threshold)
        )

        self.r_signal_in = self.addReference("signal_in")
        self.v_signal_out = self.addVariable("signal_out", Pyc.TVarType.t_int, -1)

        # States and automata
        self.add_automaton(
            name="activation",
            states=["inactive", "active"],
            transitions=[
                {
                    "name": "active",
                    "source": "inactive",
                    "target": "active",
                    "condition": "logic_active",
                },
                {
                    "name": "inactive",
                    "source": "active",
                    "target": "inactive",
                    "condition": "logic_inactive",
                },
            ],
        )

        self.addMessageBox("in")
        self.addMessageBoxImport("in", self.r_signal_in, "signal")

        self.addMessageBox("out")
        self.addMessageBoxExport("out", self.v_signal_out, "signal")

        self.system().pdmp_manager.addEquationMethod("compute_signal_out", self)
        self.system().pdmp_manager.addExplicitVariable(self.v_signal_out)
        self.system().pdmp_manager.addWatchedTransition(
            self.automata["activation"].get_transition_by_name("active").bkd
        )
        self.system().pdmp_manager.addWatchedTransition(
            self.automata["activation"].get_transition_by_name("inactive").bkd
        )

        self.addStartMethod("compute_signal_out")

        # self.system().pdmp_manager.addBoundaryCheckerMethod("automaton_logic", self)

    def logic_active(self):
        if self.active_threshold is None:
            if self.inactive_threshold is not None:
                return not self.logic_inactive()
            else:
                return False

        return self.active_threshold_operator(
            cod3s.compute_reference_mean(self.r_signal_in), self.active_threshold
        )

    def logic_inactive(self):
        if self.inactive_threshold is None:
            if self.active_threshold is not None:
                return not self.logic_active()
            else:
                return False

        return self.inactive_threshold_operator(
            cod3s.compute_reference_mean(self.r_signal_in), self.inactive_threshold
        )

    def compute_signal_out(self):
        if self.logic_active():
            self.v_signal_out.setValue(1)
        elif self.logic_inactive():
            self.v_signal_out.setValue(0)
        else:
            self.v_signal_out.setValue(-1)


class MySystem(cod3s.PycSystem):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)

        # steps = ["update_flow_demand", "update_flow"]
        # self.steps = {}
        # for step in steps:
        #     self.steps[step] = self.addStep(step)

        self.pdmp_manager = self.addPDMPManager("pdmp_manager")

        self.add_component(
            name="S1",
            cls="Source",
        )

        self.add_component(name="P1", cls="Pump", flow_prod=3)

        self.add_component(
            name="T1",
            cls="Tank",
            capacity=30,
            content_ini=15,
        )

        self.add_component(name="P2", cls="Pump", flow_prod=2)

        self.add_component(
            name="S2",
            cls="Source",
        )

        self.add_component(name="CT1", cls="Sensor", measure="content")
        self.add_component(
            name="AP1",
            cls="Automaton",
            active_threshold="< 30",
            inactive_threshold="> 0",
        )
        self.add_component(name="AP2", cls="Automaton", active_threshold="> 5")

        # self.T1 = Tank("T1", capacity=500, content_ini=450)
        # self.P1 = Pump("P1")
        # self.T2 = Tank("T2")
        # self.C1 = Capteur("C1")
        # self.C2 = Capteur("C2")
        # self.A1 = Automate("A1")
        # self.A2 = Automate("A2")

        self.connect("S1", "out", "P1", "in")
        self.connect("P1", "out", "T1", "in")

        self.connect("T1", "out", "P2", "in")

        self.connect("T1", "content", "CT1", "in")

        self.connect("CT1", "out", "AP1", "in")
        self.connect("CT1", "out", "AP2", "in")

        self.connect("AP1", "out", "P1", "cmd")
        self.connect("AP2", "out", "P2", "cmd")

        # self.connect("T1", "hydr_out", "P1", "hydr_in")
        # self.connect("P1", "hydr_out", "T2", "hydr_in")

        # self.connect("T1", "ctrl_hydr_out", "C1", "ctrl_hydr_in")
        # self.connect("C1", "ctrl_hydr_out", "A1", "ctrl_hydr_in")
        # self.connect("A1", "ctrl_hydr_out", "P1", "ctrl_hydr_in")

        # self.connect("T2", "ctrl_hydr_out", "C2", "ctrl_hydr_in")
        # self.connect("C2", "ctrl_hydr_out", "A2", "ctrl_hydr_in")
        # self.connect("A2", "ctrl_hydr_out", "P1", "ctrl_hydr_in")


if __name__ == "__main__":

    # Get the path of the current file
    current_file = Path(__file__).resolve()
    # Get the parent directory
    current_dir = current_file.parent
    print("PyCATSHOO Version : ", Pyc.ILogManager.glLogManager().version())

    system = MySystem("system")
    system_parameters_filename = os.path.join(current_dir, "system_param.xml")
    system.loadParameters(system_parameters_filename)

    system.add_indicator(
        component="S1",
        attr_type="VAR",
        attr_name="flow",
        stats=["mean"],
    )

    system.add_indicator(
        component="P1",
        attr_type="VAR",
        attr_name="flow",
        stats=["mean"],
    )

    system.add_indicator(
        component="P2",
        attr_type="VAR",
        attr_name="flow",
        stats=["mean"],
    )

    system.add_indicator(
        component="T1",
        attr_type="VAR",
        attr_name=".",
        stats=["mean"],
    )

    system.add_indicator(
        component="T1",
        attr_type="AUT",
        attr_name="content_status",
        stats=["mean"],
    )

    system.add_indicator(
        component="CT1",
        attr_type="VAR",
        attr_name="value_out$",
        stats=["mean"],
    )

    system.add_indicator(
        component="AP1",
        attr_type="VAR",
        attr_name="signal_out",
        stats=["mean"],
    )

    system.add_indicator(
        component="AP2",
        attr_type="VAR",
        attr_name="signal_out",
        stats=["mean"],
    )

    # System simulation
    # =================
    system.simulate(
        {
            "nb_runs": 1,
            "schedule": [{"start": 0, "end": 24, "nvalues": 25}],
        }
    )

    # __import__("ipdb").set_trace()

    fig_indics = system.indic_px_line(
        markers=True, title="System monitoring", facet_row="comp"
    )

    # Uncomment to save graphic on disk
    fig_indics_filename = os.path.join(current_dir, "system_indics.html")
    # fig_indics.write_image(fig_indics_filename)
    fig_indics.write_html(fig_indics_filename)
