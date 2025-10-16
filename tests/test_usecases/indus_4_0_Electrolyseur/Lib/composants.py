import Pycatshoo as Pyc
import cod3s
from pathlib import Path
from objFlow import *
import os
import numpy as np
import statistics

from enum import Enum


class AutomatonCommand(Enum):
    MEAN = "mean"
    MEDIAN = "median"
    AND = "and"
    OR = "or"


class SensorStrategy(Enum):
    MEAN = "mean"
    SUM = "sum"


# Start and Stop Component
class StartStopComponent:
    def __init__(self, init_state="start", method="mean"):
        self.r_cmd = self.addReference("cmd")
        self.method = method

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

        self.automata_d["operation"]._bkd.addSensitiveMethod("update_flow_demand")
        self.automata_d["operation"]._bkd.addSensitiveMethod("update_flow")

        # Message Box
        self.addMessageBox("cmd")
        self.addMessageBoxImport("cmd", self.r_cmd, "signal")

    def start_required(self):
        if self.r_cmd.cnctCount() > 0:
            if self.method == AutomatonCommand.MEAN.value:
                return cod3s.compute_reference_mean(self.r_cmd) > 0
            elif self.method == AutomatonCommand.MEDIAN.value:
                return self.compute_reference_mediane(self.r_cmd) > 0
            elif self.method == AutomatonCommand.AND.value:
                for i in range(self.r_cmd.cnctCount()):
                    if self.r_cmd.value(i) < 0:
                        return False
                return True
            elif self.method == AutomatonCommand.OR.value:
                for i in range(self.r_cmd.cnctCount()):
                    if self.r_cmd.value(i) > 0:
                        return True
                return False
            return False
        else:
            return False

    def stop_required(self):
        if self.r_cmd.cnctCount() > 0:
            if self.method == AutomatonCommand.MEAN.value:
                return cod3s.compute_reference_mean(self.r_cmd) < 0
            elif self.method == AutomatonCommand.MEDIAN.value:
                return self.compute_reference_mediane(self.r_cmd) < 0
            elif self.method == AutomatonCommand.AND.value:
                for i in range(self.r_cmd.cnctCount()):
                    if self.r_cmd.value(i) < 0:
                        return True
                return False
            elif self.method == AutomatonCommand.OR.value:
                for i in range(self.r_cmd.cnctCount()):
                    if self.r_cmd.value(i) > 0:
                        return False
                return True
            return False
        else:
            return False

    def compute_reference_mediane(self, var_ref, default_value=0):
        if var_ref.cnctCount() == 1:
            return var_ref.value(0)
        elif var_ref.cnctCount() == 2:
            return (var_ref.value(0) + var_ref.value(1)) * 0.5
        elif var_ref.cnctCount() == 3:
            if var_ref.value(0) <= var_ref.value(1) <= var_ref.value(2):
                return var_ref.value(1)
            elif var_ref.value(0) <= var_ref.value(2) <= var_ref.value(1):
                return var_ref.value(2)
            elif var_ref.value(1) <= var_ref.value(0) <= var_ref.value(2):
                return var_ref.value(0)
            elif var_ref.value(1) <= var_ref.value(2) <= var_ref.value(0):
                return var_ref.value(2)
            elif var_ref.value(2) <= var_ref.value(0) <= var_ref.value(1):
                return var_ref.value(0)
            elif var_ref.value(2) <= var_ref.value(1) <= var_ref.value(0):
                return var_ref.value(1)
            else:
                raise ValueError("Cas Impossible")
        else:

            list_values = []
            for i in range(var_ref.cnctCount()):
                list_values.append(var_ref.value(i))

            # Get the mediane of the references
            mediane = statistics.median(list_values)
            return mediane


# Production continu d'un flux
class Source(ObjFlow):
    def __init__(self, name, flow_nominal=0, **kwargs):
        super().__init__(name, **kwargs)

        self.v_flow_prod = self.addVariable(
            "flow_prod", Pyc.TVarType.t_double, flow_nominal
        )
        self.v_flow_prod.setReinitialized(True)

        self.addMessageBox(f"{self.flow_prefix}prod")
        self.addMessageBoxExport(f"{self.flow_prefix}prod", self.v_flow_prod, "prod")

        self.v_flow_prod.addSensitiveMethod("update_flow_demand")
        self.v_flow_prod.addSensitiveMethod("update_flow")

    def update_flow_demand(self):
        self.update_flow()

    def update_flow(self):
        iflow_demand = self.compute_iflow_demand()
        flow_prod = self.v_flow_prod.value()
        self.v_flow_out.setValue(min(iflow_demand, flow_prod))


# Mise à jour du flux via le PDMP et le compute prod correspondant à une sinusoide
class SourceSinusoidale(Source):
    def __init__(
        self,
        name,
        amplitude=1,
        phase_shift=0,
        period=2 * np.pi,
        amplitude_offset=0.0,
        value_min=-float("inf"),
        value_max=float("inf"),
        **kwargs,
    ):
        super().__init__(name, **kwargs)

        self.amplitude = amplitude
        self.phase_shift = phase_shift
        self.period = period
        self.amplitude_offset = amplitude_offset
        self.value_min = value_min
        self.value_max = value_max

        # PDMP
        self.system().pdmp_manager.addEquationMethod("compute_prod", self)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_prod)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_out)

    def compute_prod(self):
        time_factor = (self.system().currentTime() - self.phase_shift) * (
            2 * np.pi / self.period
        )
        value = self.amplitude * np.sin(time_factor) + self.amplitude_offset

        self.v_flow_prod.setDValue(
            min(
                max(self.value_min, value * self.flow_available_out.value()),
                self.value_max,
            )
        )
        self.update_flow()


# Role repartir le flux en 2 en fonction des deux parametres percent_value1 et percent_value2. La somme des deux percent_values doit être inférieur à 1.
class DistribNode(ObjFlowI2O):
    def __init__(self, name, percent_value1=0, percent_value2=0, **kwargs):
        super().__init__(name, **kwargs)

        self.p_percent_value1 = self.addVariable(
            "percent_value1", Pyc.TVarType.t_double, percent_value1
        )
        self.p_percent_value2 = self.addVariable(
            "percent_value2", Pyc.TVarType.t_double, percent_value2
        )

    def update_flow(self):
        if self.r_flow_in.cnctCount() > 0:
            iflow = self.compute_iflow()

            demand1 = self.r_flow_demand_import1.sumValue(0)
            demand2 = self.r_flow_demand_import2.sumValue(0)

            value1 = demand1
            value2 = demand2
            if iflow < demand1 + demand2:
                percent_value1 = self.p_percent_value1.value()
                percent_value2 = self.p_percent_value2.value()
                if (
                    self.p_percent_value1.value() <= 0
                    and self.p_percent_value2.value() <= 0
                ):
                    percent_value1 = demand1 / (demand1 + demand2)
                    percent_value2 = demand2 / (demand1 + demand2)
                elif (
                    self.p_percent_value1.value() <= 0
                    and self.p_percent_value2.value() > 0
                ):
                    percent_value1 = 1 - self.p_percent_value2.value()
                elif (
                    self.p_percent_value1.value() > 0
                    and self.p_percent_value2.value() <= 0
                ):
                    percent_value2 = 1 - self.p_percent_value1.value()

                value1 = percent_value1 * iflow
                value2 = percent_value2 * iflow

            if value1 > demand1:
                value2 += value1 - demand1
            if value2 > demand2:
                value1 += value2 - demand2

            self.v_flow_out1.setValue(min(value1, demand1))
            self.v_flow_out2.setValue(min(value2, demand2))


# Le composant peut recevoir N type de flux différent.
# La variable content_total correspond à la somme de tout les types de flux mélangé dans la capacity. Ce content_total ne doit pas dépasser la capacity maximal du composant.
class CapacityMulti(ObjFlowNINO):
    def __init__(self, name, capacity=1, content_ini={}, **kwargs):

        super().__init__(name, **kwargs)

        if isinstance(content_ini, float):
            content_ini = {flow_type: content_ini for flow_type in self.flow_types}

        # Parameters
        self.p_capacity = self.addVariable("capacity", Pyc.TVarType.t_double, capacity)

        self.ready_to_release = self.addVariable(
            "ready_to_release", Pyc.TVarType.t_bool, True
        )

        # Internal variables
        self.v_content_total = self.addVariable(
            "content_total",
            Pyc.TVarType.t_double,
            sum([c for c in content_ini.values()]),
        )
        self.v_content_dict = {}
        for flow_type in self.flow_types:
            v_content = self.addVariable(
                f"{flow_type}_content",
                Pyc.TVarType.t_double,
                content_ini.get(flow_type, 0),
            )
            self.v_content_dict[flow_type] = v_content

        self.v_ratio_dict = {}
        for flow_type in self.flow_types:
            v_ratio = self.addVariable(f"{flow_type}_ratio", Pyc.TVarType.t_double, 0.0)
            self.v_ratio_dict[flow_type] = v_ratio

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
        self.automata_d["content_status"]._bkd.addSensitiveMethod("update_flow_demand")
        self.set_content_status_init_state()

        # Message Box
        self.addMessageBox("content_total")
        self.addMessageBoxExport("content_total", self.v_content_total, "content")
        for flow_type in self.flow_types:
            self.addMessageBox(f"{self.flow_prefix(flow_type)}content")
            self.addMessageBoxExport(
                f"{self.flow_prefix(flow_type)}content",
                self.v_content_dict[flow_type],
                "content",
            )

        for flow_type in self.flow_types:
            self.addMessageBox(f"{self.flow_prefix(flow_type)}ratio")
            self.addMessageBoxExport(
                f"{self.flow_prefix(flow_type)}ratio",
                self.v_ratio_dict[flow_type],
                "ratio",
            )

        # PDMP
        self.system().pdmp_manager.addEquationMethod("compute_content", self)
        self.system().pdmp_manager.addODEVariable(self.v_content_total)
        self.system().pdmp_manager.addExplicitVariable(self.v_content_total)
        for flow_type in self.flow_types:
            self.system().pdmp_manager.addODEVariable(self.v_content_dict[flow_type])
            self.system().pdmp_manager.addExplicitVariable(
                self.v_content_dict[flow_type]
            )
            self.system().pdmp_manager.addExplicitVariable(self.v_ratio_dict[flow_type])

        for trans in self.automata_d["content_status"].transitions:
            self.system().pdmp_manager.addWatchedTransition(trans._bkd)

        self.v_content_total.addSensitiveMethod("update_flow")

    def is_empty(self):
        return self.v_content_total.value() <= 0

    def is_full(self):
        return self.v_content_total.value() >= self.p_capacity.value()

    def is_intermediate(self):
        return not (self.is_empty() or self.is_full())

    def compute_content(self):
        iFlow_total = 0
        oFlow_total = 0

        for flow_type in self.flow_types:
            iFlow = self.r_flow_in_dict[flow_type].sumValue(0)
            oFlow = self.v_flow_out_dict[flow_type].value()

            iflow_demand = self.compute_iflow_demand(flow_type)
            if (
                self.is_empty()
                and self.ready_to_release.value()
                and (
                    iFlow <= iflow_demand
                    or (iflow_demand < 0 and iFlow <= self.flow_out_max.value())
                )
            ):
                self.v_content_dict[flow_type].setDvdtODE(0)
                self.v_content_dict[flow_type].setValue(0)
            elif self.is_full() and (
                (iflow_demand >= 0 and (iFlow >= oFlow or iFlow >= iflow_demand))
                or (iFlow >= self.flow_out_max.value())
            ):
                self.v_content_dict[flow_type].setDvdtODE(0)
            else:
                iFlow_total = iFlow_total + iFlow
                oFlow_total = oFlow_total + oFlow

                self.v_content_dict[flow_type].setDvdtODE(iFlow - oFlow)

            if self.v_content_dict[flow_type].value() > self.p_capacity.value():
                self.v_content_dict[flow_type].setValue(self.p_capacity.value())

        self.v_content_total.setDvdtODE(iFlow_total - oFlow_total)
        if self.is_empty():
            self.v_content_total.setValue(0)
        if self.is_full():
            self.v_content_total.setValue(self.p_capacity.value())

        self.update_ratio()

    def update_ratio(self):
        total_content = self.v_content_total.value()
        for flow_type in self.flow_types:
            if total_content == 0:
                self.v_ratio_dict[flow_type].setValue(0)
            else:
                flow_type_content = self.v_content_dict[flow_type].value()
                self.v_ratio_dict[flow_type].setValue(flow_type_content / total_content)

    def set_content_status_init_state(self):
        a_content_status = self.automata_d["content_status"]

        if self.is_empty():
            state = "empty"
        elif self.is_full():
            state = "full"
        else:
            state = "intermediate"

        a_content_status.set_init_state(state)

    def update_flow_demand(self):
        if self.is_full():
            if self.ready_to_release.value():
                for flow_type in self.flow_types:
                    iflow_demand = self.compute_iflow_demand(flow_type)
                    self.v_flow_demand_export_dict[flow_type].setValue(iflow_demand)
            else:
                for flow_type in self.flow_types:
                    self.v_flow_demand_export_dict[flow_type].setValue(0)
        else:
            for flow_type in self.flow_types:
                self.v_flow_demand_export_dict[flow_type].setValue(
                    self.flow_in_max.value()
                )

    def update_flow(self):
        total_value_to_export = 0
        if self.ready_to_release.value():
            for flow_type in self.flow_types:
                total_value_to_export = (
                    total_value_to_export + self.compute_iflow_demand(flow_type)
                )
        else:
            for flow_type in self.flow_types:
                self.v_flow_out_dict[flow_type].setValue(0)

        if total_value_to_export < 0 and self.flow_out_max.value() > 0:
            total_value_to_export = self.flow_out_max.value()

        for flow_type in self.flow_types:
            flow_type_ratio = 1
            if self.v_content_total.value() > 0:
                flow_type_ratio = (
                    self.v_content_dict[flow_type].value()
                    / self.v_content_total.value()
                )
            flow_type_ratio = max(0, min(1, flow_type_ratio))
            self.v_flow_out_dict[flow_type].setValue(
                total_value_to_export * flow_type_ratio
            )


class Tank(CapacityMulti):
    pass


class Battery(CapacityMulti, StartStopComponent):
    def __init__(
        self,
        name,
        flow_nominal=1,
        capacity=1,
        content_ini={},
        init_state="start",
        method=AutomatonCommand.MEAN.value,
        **kwargs,
    ):
        super().__init__(
            name,
            flow_nominal=flow_nominal,
            flow_in_max=flow_nominal,
            capacity=capacity,
            content_ini=content_ini,
            **kwargs,
        )
        StartStopComponent.__init__(self, init_state=init_state, method=method)

        if init_state == "stop":
            self.ready_to_release.setValue(False)

        # Automaton
        self.automata_d["operation"]._bkd.addSensitiveMethod("is_ready_to_release")

        # PDMP Manager
        self.system().pdmp_manager.addExplicitVariable(self.flow_in_max)

    def is_ready_to_release(self):
        if self.automata_d["operation"].get_active_state().name == "stop":
            self.ready_to_release.setValue(False)
        else:
            self.ready_to_release.setValue(True)


# Lorsque la pompe est en marche elle transfert toujours son flux nominal
class Pump(ObjFlow, StartStopComponent):
    def __init__(
        self,
        name,
        flow_nominal=1,
        init_state="start",
        method=AutomatonCommand.MEAN.value,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        StartStopComponent.__init__(self, init_state=init_state, method=method)

        # Variables
        self.p_flow_nominal = self.addVariable(
            "flow_nominal", Pyc.TVarType.t_double, flow_nominal
        )

        self.v_flow_prod = self.addVariable(
            "flow_prod", Pyc.TVarType.t_double, flow_nominal
        )

        self.v_prod_pct = self.addVariable("v_prod_pct", Pyc.TVarType.t_double, 1.0)
        self.v_prod_pct.setReinitialized(True)

        self.automata_d["operation"]._bkd.addSensitiveMethod("compute_prod")

        # PDMP Manager
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_prod)

    @property
    def content_prefix(self):
        return f"{self.flow_type}_" if self.flow_type else ""

    def compute_prod(self):
        if self.automata_d["operation"].get_active_state().name == "start":
            self.v_flow_prod.setValue(
                self.p_flow_nominal.value() * self.v_prod_pct.value()
            )
        else:
            self.v_flow_prod.setValue(0)

    def update_flow_demand(self):
        iflow_demand = self.compute_iflow_demand()
        self.compute_prod()

        flow_prod = self.v_flow_prod.value()
        if iflow_demand > 0 and iflow_demand < flow_prod:
            self.v_flow_demand_export.setDValue(iflow_demand)
        else:
            self.v_flow_demand_export.setDValue(flow_prod)

    def update_flow(self):
        self.compute_prod()
        self.v_flow_out.setDValue(self.v_flow_prod.value())


class Automaton(cod3s.PycComponent):
    def __init__(
        self,
        name,
        active_threshold=None,
        inactive_threshold=None,
        **kwargs,
    ):
        super().__init__(name, **kwargs)

        self.active_threshold, self.active_threshold_operator = cod3s.parse_inequality(
            active_threshold
        )
        self.inactive_threshold, self.inactive_threshold_operator = (
            cod3s.parse_inequality(inactive_threshold)
        )

        self.r_signal_in = self.addReference("signal_in")
        self.v_signal_out = self.addVariable("signal_out", Pyc.TVarType.t_int, 0)

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

        # PDMP
        self.system().pdmp_manager.addEquationMethod("compute_signal_out", self)
        self.system().pdmp_manager.addExplicitVariable(self.v_signal_out)
        self.system().pdmp_manager.addWatchedTransition(
            self.automata_d["activation"].get_transition_by_name("active")._bkd
        )
        self.system().pdmp_manager.addWatchedTransition(
            self.automata_d["activation"].get_transition_by_name("inactive")._bkd
        )

        # Disfunctional parameters
        self.v_threshold_available = self.addVariable(
            "threshold_available", Pyc.TVarType.t_bool, True
        )
        self.v_threshold_available.setReinitialized(True)
        self.v_threshold_available.addSensitiveMethod("compute_signal_out")

        self.v_active_forced = self.addVariable(
            "active_forced", Pyc.TVarType.t_bool, False
        )
        self.v_active_forced.setReinitialized(True)
        self.v_active_forced.addSensitiveMethod("compute_signal_out")

        self.v_inactive_forced = self.addVariable(
            "inactive_forced", Pyc.TVarType.t_bool, False
        )
        self.v_inactive_forced.setReinitialized(True)
        self.v_inactive_forced.addSensitiveMethod("compute_signal_out")

        # Message Box
        self.addMessageBox("in")
        self.addMessageBoxImport("in", self.r_signal_in, "signal")

        self.addMessageBox("out")
        self.addMessageBoxExport("out", self.v_signal_out, "signal")

        # Start Method
        self.addStartMethod("compute_signal_out")

    def compute_reference_mediane(self, var_ref, default_value=0):
        if var_ref.cnctCount() == 1:
            return var_ref.value(0)
        elif var_ref.cnctCount() == 2:
            return (var_ref.value(0) + var_ref.value(1)) * 0.5
        elif var_ref.cnctCount() == 3:
            if var_ref.value(0) <= var_ref.value(1) <= var_ref.value(2):
                return var_ref.value(1)
            elif var_ref.value(0) <= var_ref.value(2) <= var_ref.value(1):
                return var_ref.value(2)
            elif var_ref.value(1) <= var_ref.value(0) <= var_ref.value(2):
                return var_ref.value(0)
            elif var_ref.value(1) <= var_ref.value(2) <= var_ref.value(0):
                return var_ref.value(2)
            elif var_ref.value(2) <= var_ref.value(0) <= var_ref.value(1):
                return var_ref.value(0)
            elif var_ref.value(2) <= var_ref.value(1) <= var_ref.value(0):
                return var_ref.value(1)
            else:
                raise ValueError("Cas Impossible")
        else:

            list_values = []
            for i in range(var_ref.cnctCount()):
                list_values.append(var_ref.value(i))

            # Get the mediane of the references
            mediane = statistics.median(list_values)
            return mediane

    def logic_active(self):
        if self.active_threshold is None:
            return False
        elif self.r_signal_in.cnctCount() == 0:
            return False
        else:
            if self.v_active_forced.value():
                value = True
            elif self.v_inactive_forced.value():
                value = False
            elif self.v_threshold_available.value():
                value = self.active_threshold_operator(
                    self.compute_reference_mediane(self.r_signal_in),
                    self.active_threshold,
                )
            else:
                value = self.inactive_threshold_operator(
                    self.compute_reference_mediane(self.r_signal_in),
                    self.inactive_threshold,
                )
            return value

    def logic_inactive(self):
        if self.inactive_threshold is None:
            return False
        elif self.r_signal_in.cnctCount() == 0:
            return False
        else:
            if self.v_active_forced.value():
                value = False
            elif self.v_inactive_forced.value():
                value = True
            elif self.v_threshold_available.value():
                value = self.inactive_threshold_operator(
                    self.compute_reference_mediane(self.r_signal_in),
                    self.inactive_threshold,
                )
            else:
                value = self.active_threshold_operator(
                    self.compute_reference_mediane(self.r_signal_in),
                    self.active_threshold,
                )
            return value

    def compute_signal_out(self):
        if self.logic_active():
            self.v_signal_out.setValue(1)
        elif self.logic_inactive():
            self.v_signal_out.setValue(-1)
        else:
            self.v_signal_out.setValue(0)


# Stack:
# Le stack est un objet qui consomme 2 flux différents.
# L'ordre des flux n'est pas encore paramétrable
# La méthode "compute_iflow" doit être surchargée pour définir l'équation de production du flux de sortie en fonction des flux d'entrée.
class Stack(ObjFlow2I1O, StartStopComponent):
    def __init__(
        self,
        name,
        flow_H2_nominal=1,
        flow_O2_nominal=1,
        demand_H2O_nominal=9,
        demand_elec_nominal=50,
        power_pct_min=0,
        init_state="start",
        method=AutomatonCommand.AND.value,
        **kwargs,
    ):
        super().__init__(name, flow_H2_nominal=flow_H2_nominal, **kwargs)
        StartStopComponent.__init__(self, init_state=init_state, method=method)

        self.p_power_pct_min = self.addVariable(
            "power_pct_min", Pyc.TVarType.t_double, power_pct_min
        )
        self.p_flow_H2_nominal = self.addVariable(
            "flow_H2_nominal", Pyc.TVarType.t_double, flow_H2_nominal
        )
        self.p_flow_O2_nominal = self.addVariable(
            "flow_O2_nominal", Pyc.TVarType.t_double, flow_O2_nominal
        )
        self.p_demand_H2O_nominal = self.addVariable(
            "demand_H2O_nominal", Pyc.TVarType.t_double, demand_H2O_nominal
        )
        self.p_demand_elec_nominal = self.addVariable(
            "demand_elec_nominal", Pyc.TVarType.t_double, demand_elec_nominal
        )

        self.v_H2_local_leak_pct = self.addVariable(
            "H2_local_leak_pct", Pyc.TVarType.t_double, 0
        )
        self.v_H2_local_leak_pct.setReinitialized(True)

        self.v_H2_membrane_leak_pct = self.addVariable(
            "H2_membrane_leak_pct", Pyc.TVarType.t_double, 0
        )
        self.v_H2_membrane_leak_pct.setReinitialized(True)

        self.v_O2_membrane_leak_pct = self.addVariable(
            "O2_membrane_leak_pct", Pyc.TVarType.t_double, 0
        )
        self.v_O2_membrane_leak_pct.setReinitialized(True)

        self.v_O2_leak_pct = self.addVariable("O2_leak_pct", Pyc.TVarType.t_double, 0)
        self.v_O2_leak_pct.setReinitialized(True)

        self.v_H2O_leak_pct = self.addVariable("H2O_leak_pct", Pyc.TVarType.t_double, 0)
        self.v_H2O_leak_pct.setReinitialized(True)

        # O2 flow out
        self.v_flow_O2_out = self.addVariable("flow_O2_out", Pyc.TVarType.t_double, 0)
        # Leak variables and references
        self.v_flow_O2_membrane_leak = self.addVariable(
            "flow_O2_membrane_leak", Pyc.TVarType.t_double, 0
        )
        self.v_flow_O2_leak = self.addVariable("flow_O2_leak", Pyc.TVarType.t_double, 0)
        self.v_flow_H2_membrane_leak = self.addVariable(
            "flow_H2_membrane_leak", Pyc.TVarType.t_double, 0
        )
        self.v_flow_H2_local_leak = self.addVariable(
            "flow_H2_local_leak", Pyc.TVarType.t_double, 0
        )
        self.v_flow_H2O_leak = self.addVariable(
            "flow_H2O_leak", Pyc.TVarType.t_double, 0
        )

        self.addMessageBox("O2_out")
        self.addMessageBoxExport("O2_out", self.v_flow_O2_out, "flow")

        self.addMessageBox("H2_local_leak_out")
        self.addMessageBoxExport("H2_local_leak_out", self.v_flow_H2_local_leak, "flow")

        self.addMessageBox("H2_membrane_leak_out")
        self.addMessageBoxExport(
            "H2_membrane_leak_out", self.v_flow_H2_membrane_leak, "flow"
        )

        self.addMessageBox("O2_membrane_leak_out")
        self.addMessageBoxExport(
            "O2_membrane_leak_out", self.v_flow_O2_membrane_leak, "flow"
        )

        self.addMessageBox("O2_leak_out")
        self.addMessageBoxExport("O2_leak_out", self.v_flow_O2_leak, "flow")

        self.addMessageBox("H2O_leak_out")
        self.addMessageBoxExport("H2O_leak_out", self.v_flow_H2O_leak, "flow")

        # PDMP Manager
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_O2_out)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_H2_local_leak)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_H2_membrane_leak)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_O2_membrane_leak)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_O2_leak)
        self.system().pdmp_manager.addExplicitVariable(self.v_flow_H2O_leak)

    def compute_iflow(self):
        # Check minimum power required
        if (
            self.r_flow_in2.sumValue(0) / self.p_demand_elec_nominal.value()
            < self.p_power_pct_min.value()
        ):
            total_iflow = 0
        else:
            total_iflow = min(
                self.r_flow_in1.sumValue(0) / self.p_demand_H2O_nominal.value(),
                self.r_flow_in2.sumValue(0) / self.p_demand_elec_nominal.value(),
            )
            total_iflow = self.p_flow_H2_nominal.value() * total_iflow

        if (self.flow_out_max.value() >= 0) and (
            total_iflow > self.flow_out_max.value()
        ):
            total_iflow = self.flow_out_max.value()

        if self.automata_d["operation"].get_active_state().name == "start":
            return total_iflow
        else:
            return 0

    def update_flow_demand(self):
        if self.automata_d["operation"].get_active_state().name == "start":
            iflow_demand = self.compute_iflow_demand()

            if iflow_demand >= 0 and iflow_demand < self.p_flow_H2_nominal.value():
                self.v_flow_demand_export1.setDValue(
                    iflow_demand
                    * self.p_demand_H2O_nominal.value()
                    / self.p_flow_H2_nominal.value()
                )
                self.v_flow_demand_export2.setDValue(
                    iflow_demand
                    * self.p_demand_elec_nominal.value()
                    / self.p_flow_H2_nominal.value()
                )
            else:
                self.v_flow_demand_export1.setDValue(self.p_demand_H2O_nominal.value())
                self.v_flow_demand_export2.setDValue(self.p_demand_elec_nominal.value())
        else:
            self.v_flow_demand_export1.setDValue(0)
            self.v_flow_demand_export2.setDValue(0)

    def get_total_flow_out(self):
        if self.r_flow_in1.cnctCount() > 0 or self.r_flow_in2.cnctCount() > 0:
            iflow = self.compute_iflow()
            iflow_demand = self.compute_iflow_demand()
            if iflow_demand > 0:
                iflow = min(iflow, iflow_demand)
            return iflow
        return 0

    def update_flow(self):
        iflow = self.get_total_flow_out()
        H2_flow = iflow * (
            1
            - self.v_O2_membrane_leak_pct.value()
            - self.v_O2_leak_pct.value()
            - self.v_H2O_leak_pct.value()
        )
        self.v_flow_out.setValue(
            H2_flow
            * (
                1
                - self.v_H2_membrane_leak_pct.value()
                - self.v_H2_local_leak_pct.value()
            )
        )
        self.v_flow_H2_membrane_leak.setDValue(
            H2_flow * self.v_H2_membrane_leak_pct.value()
        )
        self.v_flow_H2_local_leak.setDValue(H2_flow * self.v_H2_local_leak_pct.value())

        self.v_flow_H2O_leak.setDValue(
            self.r_flow_in1.sumValue(0) * self.v_H2O_leak_pct.value()
        )

        ratio_nominal = H2_flow / self.p_flow_H2_nominal.value()
        O2_flow = ratio_nominal * self.p_flow_O2_nominal.value()
        self.v_flow_O2_out.setValue(
            O2_flow
            * (1 - self.v_O2_membrane_leak_pct.value() - self.v_O2_leak_pct.value())
        )

        self.v_flow_O2_membrane_leak.setDValue(
            O2_flow * self.v_O2_membrane_leak_pct.value()
        )
        self.v_flow_O2_leak.setDValue(O2_flow * self.v_O2_leak_pct.value())


# Le capteur transmet des données à un autre composant.
# Les données sont mise à jours via la méthode "compute_value_out" grâce au PDMP
class Sensor(cod3s.PycComponent):
    def __init__(self, name, measure, obj_type="", method="mean", **kwargs):
        super().__init__(name, **kwargs)
        self.method = method

        # Variables
        self.obj_type = obj_type

        self.v_value_out = self.addVariable("value_out", Pyc.TVarType.t_double, 0.0)
        self.r_value_in = self.addReference("value_in")

        # Failure
        self.v_forced_measure = self.addVariable(
            "forced_measure", Pyc.TVarType.t_bool, False
        )
        self.v_forced_measure.setReinitialized(True)
        self.v_value_forced = self.addVariable(
            "value_forced", Pyc.TVarType.t_double, 0.0
        )

        self.v_measure_blocked = self.addVariable(
            "measure_blocked", Pyc.TVarType.t_bool, False
        )
        self.v_measure_blocked.setReinitialized(True)
        self.v_last_measured_value = self.addVariable(
            "last_measured_value", Pyc.TVarType.t_double, 0.0
        )

        # Message Box
        self.addMessageBox(f"{self.obj_prefix}in")
        self.addMessageBoxImport(f"{self.obj_prefix}in", self.r_value_in, measure)

        self.addMessageBox(f"{self.obj_prefix}out")
        self.addMessageBoxExport(f"{self.obj_prefix}out", self.v_value_out, "signal")

        # PDMP Manager
        self.system().pdmp_manager.addEquationMethod("compute_value_out", self)
        self.system().pdmp_manager.addExplicitVariable(self.v_value_out)
        self.system().pdmp_manager.addExplicitVariable(self.v_last_measured_value)

        self.addStartMethod("compute_value_out")

    @property
    def obj_prefix(self):
        return f"{self.obj_type}_" if self.obj_type else ""

    def compute_value_out(self):
        if self.v_forced_measure.value():
            value = self.v_value_forced.value()
            self.v_value_out.setValue(value)
        elif self.v_measure_blocked.value():
            value = self.v_last_measured_value.value()
            self.v_value_out.setValue(value)
        else:
            if self.method == SensorStrategy.MEAN.value:
                value = cod3s.compute_reference_mean(self.r_value_in)
            elif self.method == SensorStrategy.SUM.value:
                value = self.r_value_in.sumValue(0)
            else:
                value = cod3s.compute_reference_mean(self.r_value_in)

            self.v_value_out.setValue(value)
            self.v_last_measured_value.setValue(value)


# Le consumer consomme toujours la même quantitée de flux
class Consumer(ObjFlow):
    def __init__(
        self,
        name,
        flow_nominal=0,
        **kwargs,
    ):
        super().__init__(name, **kwargs)

        self.p_flow_nominal = self.addVariable(
            "flow_nominal", Pyc.TVarType.t_double, flow_nominal
        )
        self.p_flow_nominal.setReinitialized(True)

        self.v_perf = self.addVariable("perf", Pyc.TVarType.t_double, 0)

        self.addMessageBox(f"{self.flow_prefix}consume")
        self.addMessageBoxExport(
            f"{self.flow_prefix}consume", self.p_flow_nominal, "consume"
        )

        # PDMP
        self.system().pdmp_manager.addExplicitVariable(self.p_flow_nominal)
        self.system().pdmp_manager.addExplicitVariable(self.v_perf)

        self.p_flow_nominal.addSensitiveMethod("update_flow_demand")
        self.p_flow_nominal.addSensitiveMethod("update_flow")

        self.flow_in_max.addSensitiveMethod("update_flow_demand")
        self.flow_in_max.addSensitiveMethod("update_flow")

    def update_flow_demand(self):
        value_to_demand = self.p_flow_nominal.value()
        if self.flow_in_max.value() > 0:
            value_to_demand = min(value_to_demand, self.flow_in_max.value())
        self.v_flow_demand_export.setDValue(value_to_demand)

    def update_flow(self):
        super().update_flow()

        if self.p_flow_nominal.value() > 0:
            self.v_perf.setDValue(self.v_flow_out.value() / self.p_flow_nominal.value())
        else:
            self.v_perf.setDValue(1)


# Le consumer sinusoidale fonctionne comme la source sinusoidale, mais c'est le flux_demand qui est mis à jour dans le PDMP
class ConsumerSinusoidale(Consumer):
    def __init__(
        self,
        name,
        flow_nominal=0,
        amplitude=1,
        phase_shift=0,
        period=2 * np.pi,
        amplitude_offset=0.0,
        value_min=-float("inf"),
        value_max=float("inf"),
        **kwargs,
    ):
        super().__init__(
            name,
            flow_nominal=flow_nominal,
            **kwargs,
        )

        self.amplitude = amplitude
        self.phase_shift = phase_shift
        self.period = period
        self.amplitude_offset = amplitude_offset
        self.value_min = value_min
        self.value_max = value_max

    # Override
    def compute_demand(self):
        time_factor = (
            (self.system().currentTime() - self.phase_shift) * np.pi / (self.period / 2)
        )
        value = -self.amplitude * np.sin(time_factor) + self.amplitude_offset

        self.p_flow_nominal.setDValue(min(max(self.value_min, value), self.value_max))
        self.update_flow_demand()

    def update_flow_demand(self):
        value_to_demand = self.p_flow_nominal.value()
        if self.flow_in_max.value() > 0:
            value_to_demand = min(value_to_demand, self.flow_in_max.value())
        self.v_flow_demand_export.setDValue(value_to_demand)


class SystemHybrid(cod3s.PycSystem):
    def __init__(self, name, **kwargs):

        super().__init__(name, **kwargs)

        self.pdmp_manager = self.addPDMPManager("pdmp_manager")

        # Step
        self.step_failure_propagation = self.addStep("failure_propagation")

    def add_failure_mode(self, failure_modes_list, logger=None):
        for fm in failure_modes_list:
            fm_name = fm.get("fm_name")

            # __import__("ipdb").set_trace()
            if fm.get("enabled") is False:
                if logger:
                    logger.info3(f"FM {fm_name} Ignored")
                continue

            fm_law = fm.pop("occ_law")
            fm["cls"] = f"ObjFM{fm_law.capitalize()}"

            self.add_component(**fm)

            if logger:
                logger.info2(f"Processing FM: {fm_name}")
