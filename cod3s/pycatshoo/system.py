import Pycatshoo as pyc
import pydantic
import numpy as np
import pandas as pd
import plotly.express as px
import typing
import pkg_resources
import itertools
import re
from .indicator import PycVarIndicator, PycFunIndicator
from .automaton import PycTransition
installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
if 'ipdb' in installed_pkg:
    import ipdb  # noqa: F401



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
    nb_runs: int = pydantic.Field(
        1, description="Number of simulation to run")
    schedule: typing.List[typing.Union[InstantLinearRange,float]] = pydantic.Field(
        [100], description="Measure instant")
    time_unit: str = pydantic.Field(
        None, description="Simulation time unit")
    seed: typing.Any = pydantic.Field(
        None, description="Seed of the simulator")

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

    def add_indicator_var(self, **indic_specs):
        
        stats = indic_specs.pop("stats", ["mean"])
        comp_pat = indic_specs.pop("component", ".*")
        var_pat = indic_specs.pop("var", ".*")
        indic_name = indic_specs.pop("name", "")
        measure_name = indic_specs.get("measure", "")

        indic_added_list = []
        for comp in self.components("#" + comp_pat, "#.*"):
            var_list = [var.basename() for var in comp.variables()
                        if re.search(var_pat, var.basename())]

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
                    **indic_specs)
                
                # if "MES" in comp_pat:
                #     ipdb.set_trace()

                self.indicators[indic_name_cur] = indic

                indic_added_list.append(indic)

        return indic_added_list
                

    def prepare_simu(self, **params):

        #self.run_before_hook()
        simu_params = PycMCSimulationParam(**params)
        
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

        if simu_params.seed:
            self.setRNGSeed(simu_params.seed)

        if simu_params.nb_runs:
            self.setNbSeqToSim(simu_params.nb_runs)

    def simulate(self, **simu_params):
        
        self.prepare_simu(**simu_params)

        super().simulate()

        self.postproc_simu()

    def postproc_simu(self):

        for indic in self.indicators.values():
            indic.update_values()

        #self.run_after_hook()

    def indic_metadata_names(self):
        metadata_df = pd.DataFrame([indic.metadata
                                    for indic in self.indicators.values()])
        return list(metadata_df.columns)
    #     return [indic.metadata.keys() for indic in self.indicators.values()],
    # axis=0, ignore_index=True)
    
    def indic_to_frame(self):

        if len(self.indicators) == 0:
            return None
        else:
            return pd.concat([indic.values for indic in self.indicators.values()],
                             axis=0, ignore_index=True)

    def indic_px_line(self,
                      x="instant",
                      y="values",
                      color="name",
                      markers=True,
                      layout={},
                      **px_conf):

        indic_df = self.indic_to_frame()

        if indic_df is None:
            return None

        idx_stat_sel = indic_df["stat"].isin(["mean"])

        indic_sel_df = indic_df.loc[idx_stat_sel]

        fig = px.line(indic_sel_df,
                      x=x, y=y,
                      color=color,
                      markers=markers,
                      **px_conf)

        fig.update_layout(**layout)

        return fig

    
    def active_transitions(self, exclude={"bkd"}, **kwargs):

        trans_list_bkd = self.activeTransitions()

        trans_list = []
        end_time_bound = float("inf")
        for i, trans in enumerate(trans_list_bkd):
            trans_cur = dict(
                trans_id=i,
                comp_name=trans.parent().name(),
                comp_classname=trans.parent().className(),
                end_time=trans.endTime() if trans.endTime() < float("inf") else None,
                **PycTransition.from_bkd(trans).dict(exclude=exclude),
            )
            if trans.endTime() < end_time_bound:
                end_time_bound = trans.endTime()

            trans_list.append(trans_cur)

        return trans_list, end_time_bound

    def fireable_transitions(self, **kwargs):

        trans_list, end_time_bound = self.active_transitions(exclude={})

        trans_list_fireable = []
        for trans in trans_list:

            # if trans["occ_law"]["cls"] == "ExpOccDistribution":
            #     trans["end_time"] = self.currentTime()

            # if trans["comp_name"] == "S":
            #     ipdb.set_trace()
            if trans["end_time"] is None:
                if self.currentTime() != end_time_bound:
                    trans_list_fireable.append(trans)          
            elif trans["end_time"] <= end_time_bound:
                trans_list_fireable.append(trans)

        return trans_list_fireable
    

    def set_transition(self, trans_id, date=None, state_index=None, **kwargs):

        trans_list, end_time_bound = self.active_transitions(exclude={})

        selected_transition = None
        for trans in trans_list:

            if trans["trans_id"] == trans_id:
                selected_transition = trans
                break

        if not selected_transition:
            raise IndexError(f"Incorrect transition id {trans_id}")
        
        if not date:
            date = selected_transition["end_time"] \
                if selected_transition["end_time"] else self.currentTime()
                
        if not state_index:
            state_index = 0

        self.setTransPlanning(selected_transition["bkd"], date, state_index)

        self.updatePlanningInt()
        self.stepForward()
