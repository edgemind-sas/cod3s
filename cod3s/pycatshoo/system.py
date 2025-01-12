import Pycatshoo as pyc
import pydantic
import numpy as np
import pandas as pd
import plotly.express as px
import typing
import itertools
import warnings
import re
from .indicator import (
    PycAttrIndicator,
    PycVarIndicator,
    PycSTIndicator,
    PycFunIndicator,
)
from .automaton import PycTransition
from .sequence import PycSequence
from .component import PycComponent
from .common import get_pyc_attr_list_name, get_pyc_simu_mode


class InstantLinearRange(pydantic.BaseModel):
    """Linear Range"""

    start: float = pydantic.Field(..., description="Range start")
    end: float = pydantic.Field(..., description="Range end")
    nvalues: int = pydantic.Field(..., description="Range nb values")

    def get_instants_list(self):
        if self.nvalues <= 1:
            return [self.end]
        else:
            return list(np.linspace(self.start, self.end, self.nvalues))


class MCSimulationParam(pydantic.BaseModel):
    nb_runs: int = pydantic.Field(1, description="Number of simulation to run")
    schedule: typing.List[typing.Union[InstantLinearRange, float]] = pydantic.Field(
        [100], description="Measure instant"
    )
    time_unit: typing.Optional[str] = pydantic.Field(
        None, description="Simulation time unit"
    )
    seed: typing.Any = pydantic.Field(None, description="Seed of the simulator")

    def get_instants_list(self):
        instants = []
        for sched in self.schedule:
            if isinstance(sched, InstantLinearRange):
                instants.extend(sched.get_instants_list())
            else:
                instants.append(sched)

        return sorted(instants)


class PycMCSimulationParam(MCSimulationParam):
    pass


class PycSystem(pyc.CSystem):
    def __init__(self, name):
        super().__init__(name)

        self.indicators = {}
        self.isimu_sequence = PycSequence()
        # REMINDER: comp dictionnary is populated by PycComponent register method at init
        self.comp = {}

    def add_component(self, **comp_specs):
        comp_name = comp_specs.get("name")

        if comp_name in self.comp:
            warnings.warn(f"Component {comp_name} already exists", UserWarning)
            return None
        else:
            # if "SPF" in comp_name:
            #     ipdb.set_trace()
            comp_new = PycComponent.from_dict(**comp_specs)
            # self.comp[comp_new.name()] = comp_new
            return comp_new

    def get_components(self, pattern="^.*$"):
        return {k: v for k, v in self.comp.items() if re.search(f"^({pattern})$", k)}

    def add_indicator(self, **indic_specs):

        # indic_name = indic_specs.pop("name", None)
        # indic_name_pattern = indic_specs.pop("name_pattern", None)

        comp_pat = indic_specs.pop("component", ".*")
        attr_name_pat = indic_specs.pop("attr_name", ".*")
        attr_type = indic_specs.pop("attr_type")
        # measure_name = indic_specs.get("measure", "")

        pyc_attr_list_name = get_pyc_attr_list_name(attr_type)

        indic_added_list = []
        for comp in self.components("#" + comp_pat, "#.*"):

            attr_list = [
                attr.basename()
                for attr in getattr(comp, pyc_attr_list_name)()
                if re.search(attr_name_pat, attr.basename())
            ]

            for attr in attr_list:
                # if indic_name:
                #     indic_name_cur = f"{indic_name}_{attr}"
                # else:
                #     if indic_name_pattern:
                #         if measure_name:
                #             indic_name_pattern = "{component}_{attr_name}_{measure}"
                #         else:
                #             indic_name_pattern = "{component}_{attr_name}"

                indic = PycAttrIndicator(
                    # name=indic_name_cur,
                    # name_pattern=indic_name_pattern,
                    component=comp.basename(),
                    attr_type=attr_type,
                    attr_name=attr,
                    **indic_specs,
                )

                # if "MES" in comp_pat:
                #     ipdb.set_trace()

                self.indicators[indic.name] = indic

                indic_added_list.append(indic)

        return indic_added_list

    def add_indicator_var(self, **indic_specs):
        stats = indic_specs.pop("stats", ["mean"])
        comp_pat = indic_specs.pop("component", ".*")
        var_pat = indic_specs.pop("var", ".*")
        indic_name = indic_specs.pop("name", "")
        measure_name = indic_specs.get("measure", "")

        indic_added_list = []
        for comp in self.components("#" + comp_pat, "#.*"):
            var_list = [
                var.basename()
                for var in comp.variables()
                if re.search(var_pat, var.basename())
            ]

            for var in var_list:
                if indic_name:
                    indic_name_cur = f"{indic_name}_{var}"
                else:
                    indic_name_cur = f"{comp.basename()}_{var}"

                if measure_name:
                    indic_name_cur += f"_{measure_name}"

                indic = PycVarIndicator(
                    name=indic_name_cur,
                    component=comp.basename(),
                    var=var,
                    stats=stats,
                    **indic_specs,
                )

                # if "MES" in comp_pat:
                #     ipdb.set_trace()

                self.indicators[indic_name_cur] = indic

                indic_added_list.append(indic)

        return indic_added_list

    def add_indicator_state(self, **indic_specs):
        stats = indic_specs.pop("stats", ["mean"])
        comp_pat = indic_specs.pop("component", ".*")
        state_pat = indic_specs.pop("state", ".*")
        indic_name = indic_specs.pop("name", "")
        measure_name = indic_specs.get("measure", "")

        indic_added_list = []
        for comp in self.components("#" + comp_pat, "#.*"):
            state_list = [
                state.basename()
                for state in comp.states()
                if re.search(state_pat, state.basename())
            ]

            for state in state_list:
                if indic_name:
                    indic_name_cur = f"{indic_name}_{state}"
                else:
                    indic_name_cur = f"{comp.basename()}_{state}"

                if measure_name:
                    indic_name_cur += f"_{measure_name}"

                indic = PycSTIndicator(
                    name=indic_name_cur,
                    component=comp.basename(),
                    state=state,
                    stats=stats,
                    **indic_specs,
                )

                # if "MES" in comp_pat:
                #     ipdb.set_trace()

                self.indicators[indic_name_cur] = indic

                indic_added_list.append(indic)

        return indic_added_list

    def prepare_simu(self, simu_params: PycMCSimulationParam):
        # self.run_before_hook()
        # simu_params = PycMCSimulationParam(**params)

        # Set instants
        instants_list = simu_params.get_instants_list()

        # Prepare indicators
        for indic_name, indic in self.indicators.items():
            indic.instants = instants_list
            indic.set_indicator(self)
            # indic.bkd = \
            #     self.addIndicator(indic.name,
            #                       indic.get_expr(),
            #                       indic.get_type())
            # indic.update_restitution()

        # Simulator configuration
        self.setTMax(instants_list[-1])

        for instant in instants_list:
            self.addInstant(instant)

        if simu_params.seed is not None:
            self.setRNGSeed(simu_params.seed)

        if simu_params.nb_runs is not None:
            self.setNbSeqToSim(simu_params.nb_runs)

    def simulate(self, simu_params: PycMCSimulationParam):
        if isinstance(simu_params, dict):
            simu_params = PycMCSimulationParam(**simu_params)

        self.prepare_simu(simu_params)

        super().simulate()

        self.postproc_simu()

    def postproc_simu(self):
        for indic in self.indicators.values():
            indic.update_values()

        # self.run_after_hook()

    def get_simulation_mode(self):
        return get_pyc_simu_mode(self.simuMode())

    def indic_metadata_names(self):
        metadata_df = pd.DataFrame(
            [indic.metadata for indic in self.indicators.values()]
        )
        return list(metadata_df.columns)

    #     return [indic.metadata.keys() for indic in self.indicators.values()],
    # axis=0, ignore_index=True)

    def indic_to_frame(self):
        if len(self.indicators) == 0:
            return None
        else:
            return pd.concat(
                [indic.values for indic in self.indicators.values()],
                axis=0,
                ignore_index=True,
            )

    def indic_px_line(
        self,
        x="instant",
        y="values",
        color="name",
        markers=True,
        layout={},
        **px_conf,
    ):
        indic_df = self.indic_to_frame()

        if indic_df is None:
            return None

        idx_stat_sel = indic_df["stat"].isin(["mean"])

        indic_sel_df = indic_df.loc[idx_stat_sel]

        fig = px.line(indic_sel_df, x=x, y=y, color=color, markers=markers, **px_conf)
        fig.update_layout(**layout)

        return fig

    def isimu_start(self, **kwargs):
        self.startInteractive()
        self.stepForward()

        self.isimu_sequence = PycSequence()

    def isimu_stop(self, **kwargs):
        self.stopInteractive()

        self.isimu_sequence = PycSequence()

    def isimu_active_transitions(self, **kwargs):
        return [PycTransition.from_bkd(trans) for trans in self.activeTransitions()]

        # end_time_bound = min([trans["bkd"].endTime()
        #                       for trans in trans_list])

        # for i, trans in enumerate(trans_list_bkd):
        #     # trans_cur = dict(
        #     #     trans_id=i,
        #     #     # comp_name=trans.parent().name(),
        #     #     # comp_classname=trans.parent().className(),
        #     #     # end_time=trans.endTime() if trans.endTime() < float("inf") else None,
        #     #     **PycTransition.from_bkd(trans).dict(exclude=exclude),
        #     # )

        #     trans_cur = PycTransition.from_bkd(trans)

        #     if trans.endTime() < end_time_bound:
        #         end_time_bound = trans.endTime()

        #     trans_list.append(trans_cur)

        # return trans_list, end_time_bound

    def isimu_fireable_transitions(self, **kwargs):
        trans_list = self.isimu_active_transitions()
        if not trans_list:
            return []

        end_time_bound = min([trans.bkd.endTime() for trans in trans_list])

        trans_list_fireable = []
        for trans in trans_list:
            # if trans["occ_law"]["cls"] == "ExpOccDistribution":
            #     trans["end_time"] = self.currentTime()

            # if trans["comp_name"] == "S":
            #     ipdb.set_trace()
            if trans.end_time is None:
                trans.end_time = 0.0
                if self.currentTime() != end_time_bound:
                    trans_list_fireable.append(trans)
                    continue
            elif trans.end_time <= end_time_bound:
                trans_list_fireable.append(trans)
                continue

            trans_list_fireable.append(None)

        return trans_list_fireable

    def isimu_step_backward(self):
        self.stepBackward()

        trans_fireable = [trans for trans in self.isimu_fireable_transitions() if trans]

        trans_removed = []
        for trans_f in trans_fireable:
            i = len(self.isimu_sequence.transitions) - 1
            while i >= 0:
                trans_s_cur = self.isimu_sequence.transitions[i]
                if trans_s_cur == trans_f:
                    trans_rem = self.isimu_sequence.transitions.pop(i)
                    trans_removed.append(trans_rem)
                    break
                i -= 1

        return trans_removed

    def isimu_step_forward(self):
        trans_fireable = self.isimu_fireable_transitions()

        trans_fired = [
            trans
            for trans in trans_fireable
            if (trans and (trans.end_time is not None))
        ]

        self.isimu_sequence.transitions.extend(trans_fired)

        self.stepForward()

        return trans_fired

    def isimu_set_transition(
        self, trans_id=None, date=None, state_index=None, **kwargs
    ):
        if trans_id is None:
            return self.isimu_step_forward()

        trans_list = self.isimu_active_transitions()
        selected_transition = trans_list[trans_id]
        # for trans in trans_list:

        #     if trans["trans_id"] == trans_id:
        #         selected_transition = trans
        #         break

        if not selected_transition:
            raise IndexError(f"Incorrect transition id {trans_id}")

        if not date:
            date = (
                selected_transition.end_time
                if selected_transition.end_time
                else self.currentTime()
            )

        if not state_index:
            state_index = 0

        self.setTransPlanning(selected_transition.bkd, date, state_index)

        self.updatePlanningInt()

        # return self.step_forward()
