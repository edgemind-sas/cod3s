import pandas as pd
import typing
import pydantic
import pkg_resources
#from lxml import etree
import subprocess
import os
import pathlib
import sys
import math
import colored 

from ..core import ObjCOD3S
from .automaton import PycTransition
#from .component import PycComponent
from .system import PycSystem

installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
if 'ipdb' in installed_pkg:
    import ipdb  # noqa: 401

PandasDataFrame = typing.TypeVar('pd.core.dataframe')

PycSystemType = typing.TypeVar('PycSystem')

class PycInteractiveSession(ObjCOD3S):

    system: PycSystemType = pydantic.Field(
        None, description="System model")


    def report_system_name(self):
        header = \
            colored.stylize("System",
                            colored.fg("dodger_blue_2") +
                            colored.attr("bold")
                            )
        content = \
            colored.stylize(f"{self.system.name()}",
                            colored.fg("dodger_blue_2")
                            )
        
        report = f"{header} : {content}"

        return report


    def report_current_time(self):
        header = \
            colored.stylize("Current time",
                            colored.fg("deep_sky_blue_4b")
                            )
        content = \
            self.system.currentTime()

        report = f"{header} : {content}"

        return report

    def report_active_transitions(self):

        header = \
            colored.stylize("Active transitions",
                            colored.fg("dark_orange")
                            )
        
        content = \
            self.active_transitions_df().to_string() \
            if len(self.active_transitions_df()) > 0 else "No Transition"

        report = f"{header} :\n{content}"

        return report

    def report_components_status(self):

        header = \
            colored.stylize("Components status",
                            colored.fg("dark_orange")
                            )

        comp_df = self.components_status_df()
        content = comp_df.to_string() if len(comp_df) > 0 else "No component"

        report = f"{header} :\n{content}"

        return report

    
    def report_status(self):

        report_strlist = []

        sep_content = \
            colored.stylize("-"*80,
                            colored.fg("white") +
                            colored.attr("bold")
                            )
        report_strlist.append(f"{sep_content}")

        report_strlist.append(
            self.report_system_name()
        )

        report_strlist.append("")

        report_strlist.append(
            self.report_current_time()
        )

        report_strlist.append("")
        
        report_strlist.append(
            self.report_components_status()
        )

        report_strlist.append("")
        
        report_strlist.append(
            self.report_active_transitions()
        )

        report_strlist.append(f"{sep_content}")

        return "\n".join(report_strlist)
    
    def run_session(self, **kwargs):
                
        self.system.startInteractive()
        self.system.stepForward()

    def step_forward(self, **kwargs):
        self.system.updatePlanningInt()
        self.system.stepForward()

    def get_active_transitions(self, **kwargs):

        trans_list_bkd = self.system.getActiveTransitions()
        trans_list = \
            [PycTransition.from_bkd(trans)
             for trans in trans_list_bkd]
        return trans_list

    def active_transitions_df(self, **kwargs):

        trans_list = self.get_active_transitions()
        var_renaming = {
            "component": "Component",
            "name": "Transition",
            "source": "State source",
            "target": "State target",
            "occ_law": "Law",
            "occ_planned": "Planned occ.",
        }

        if trans_list:
            trans_df = \
                pd.DataFrame(
                    [tr.to_dict() for tr in trans_list])\
                  .rename(columns=var_renaming)[var_renaming.values()]
        else:
            trans_df = pd.DataFrame(columns=var_renaming.values())

        return trans_df

    def components_status_df(self, **kwargs):

        var_renaming = {
            "comp_name": "Component",
            "name": "Name",
            "type": "Type",
            "value_init": "Init. value",
            "value_current": "Current value",
        }
        
        comp_list = \
            [PycComponent.from_bkd(comp)
             for comp in self.system.getComponents("#.*", "#.*")]

        comp_df_list = []
        for comp in comp_list:
            comp_df_list.append(comp.to_df())

        if comp_df_list:
            comp_df = \
                pd.concat(comp_df_list, axis=0, ignore_index=True)
        else:
            comp_df = pd.DataFrame(columns=var_renaming.values())

        return comp_df.rename(columns=var_renaming)[var_renaming.values()]
