# ipdb is a debugger (pip install ipdb)

import pydantic
import typing
import warnings
from ..core import ObjCOD3S
from ..utils import get_operator_function
from .automaton import PycAutomaton, PycState
from .common import prepare_attr_tree, sanitize_cond_format
from .fm_wiring import FmWiringMixin, cc_comb_suffix, order_param_name
from .mode_law import parse_mode_law
import Pycatshoo as pyc
import copy
import re
import colored
import textwrap
import itertools
import builtins


class PycVariable(ObjCOD3S):
    id: str = pydantic.Field(..., description="Variable id")
    name: str = pydantic.Field(None, description="Variable name")
    comp_name: str = pydantic.Field(None, description="Component name")
    value_init: typing.Any = pydantic.Field(None, description="Variable init value")
    value_current: typing.Any = pydantic.Field(None, description="Current value")
    _bkd: typing.Any = pydantic.PrivateAttr(None)

    @classmethod
    def from_bkd(basecls, bkd):
        obj = basecls(
            id=bkd.name(),
            name=bkd.basename(),
            comp_name=bkd.parent().name(),
            value_init=bkd.initValue(),
            value_current=bkd.value(),
        )
        obj._bkd = bkd
        return obj


class PycComponent(pyc.CComponent):
    def __init__(self, name, label=None, description=None, metadata=None, **kwargs):
        super().__init__(name)

        self.label = name if label is None else label
        self.description = self.label if description is None else description
        self.automata_d = {}

        self.metadata = copy.deepcopy(metadata) if metadata is not None else {}

        # Register the component in comp dictionnary
        self.system().comp[name] = self

    @property
    def class_name_bkd(self):
        return self.__class__.__name__

    @classmethod
    def get_subclasses(cls, recursive=True):
        """Enumerates all subclasses of a given class.

        # Arguments
        cls: class. The class to enumerate subclasses for.
        recursive: bool (default: True). If True, recursively finds all sub-classes.

        # Return value
        A list of subclasses of `cls`.
        """
        sub = cls.__subclasses__()
        if recursive:
            for cls in sub:
                sub.extend(cls.get_subclasses(recursive))
        return sub

    @classmethod
    def from_dict(basecls, **specs):
        cls_sub_dict = {cls.__name__: cls for cls in basecls.get_subclasses()}
        cls_sub_dict[basecls.__name__] = basecls

        clsname = specs.pop("cls")
        cls = cls_sub_dict.get(clsname)
        if cls is None:
            raise ValueError(f"{clsname} is not a subclass of {basecls.__name__}")

        return cls(**specs)

    def repr__value_fmt(self, value, fallback_fmt=""):
        if isinstance(value, bool):
            return f"{colored.fg('green')}" if value else f"{colored.fg('hot_pink_1a')}"
        else:
            return fallback_fmt

    def str__value_fmt(self, value, fallback_fmt=""):
        return self.repr__value_fmt(value=value, fallback_fmt=fallback_fmt)

    def repr__class_name_fmt(self):
        """Return colored formatting for the class name representation."""
        return f"{colored.fg('yellow')}{colored.attr('bold')}"

    def repr__class_name(self):
        """Return the colored class name representation of the component."""
        return f"{self.repr__class_name_fmt()}{self.__class__.__name__}{colored.attr('reset')}"

    def repr__instance_name_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.fg('white')}"

    def repr__instance_name(self):
        """Return the colored instance name representation of the component."""
        return f"{self.repr__instance_name_fmt()}{self.name()}{colored.attr('reset')}"

    def repr__variables_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.fg('steel_blue')}"

    def repr__variables_count_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.fg('white')}"

    def repr__variables(self):
        """Return the colored instance name representation of the component."""
        return f"{self.repr__variables_fmt()}#var: {colored.attr('reset')}{self.repr__variables_count_fmt()}{len(self.variables())}{colored.attr('reset')}"

    def repr__cnct_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.fg('chartreuse_3a')}"

    def repr__cnct_count_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.fg('white')}"

    def repr__cnct(self):
        """Return the colored instance name representation of the component."""
        return f"{self.repr__cnct_fmt()}#cnct: {colored.attr('reset')}{self.repr__cnct_count_fmt()}{len(self.messageBoxes())}{colored.attr('reset')}"

    def __repr__(self):
        """Return a string representation showing class name and instance name."""
        return f"{self.repr__class_name()} {self.repr__instance_name()}: {self.repr__variables()} {self.repr__cnct()}"

    def str__class_name_fmt(self):
        """Return colored formatting for the class name representation."""
        return self.repr__class_name_fmt()

    def str__class_name(self):
        """Return the colored class name representation of the component."""
        return self.repr__class_name()

    def str__instance_name_fmt(self):
        """Return colored formatting for the instance name representation."""
        return self.repr__instance_name_fmt()

    def str__instance_name(self):
        """Return the colored instance name representation of the component."""
        return self.repr__instance_name()

    def str__variables_header(self):
        """Return colored formatting for the instance name representation."""
        return "Variables"

    def str__variables_header_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.attr('bold')}{colored.fg('steel_blue_3')}"

    def str__variables_name_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.fg('steel_blue')}"

    def str__variables_value_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.fg('white')}"

    def str__variables(self):
        """Return the colored instance name representation of the component."""
        lines = []
        # Add connection information if there are any connections
        lines.append(
            f"{self.str__variables_header_fmt()}{self.str__variables_header()}{colored.attr('reset')}"
        )
        for var in self.variables():
            var_value = var.value()
            var_str = (
                f"{self.str__variables_name_fmt()}{var.basename()}{colored.attr('reset')}: "
                f"{self.str__value_fmt(var_value, self.str__variables_value_fmt())}{var_value}{colored.attr('reset')}"
            )
            lines.append(textwrap.indent(var_str, "  "))

        return "\n".join(lines)

    def str__cnct_header_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.attr('bold')}{colored.fg('cyan')}"

    def str__cnct_header(self):
        """Return colored formatting for the instance name representation."""
        return "Connections:"

    def str__cnct_name_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.fg('white')}"

    def str__cnct_no_cnct_fmt(self):
        """Return colored formatting for the instance name representation."""
        return ""

    def str__cnct_no_cnct(self):
        """Return colored formatting for the instance name representation."""
        return "no connection"

    def str__cnct_target_name_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.fg('wheat_1')}"

    def str__cnct_target_attr_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.fg('white')}"

    def str__cnct(self):
        """Return the colored instance name representation of the component."""
        cnct_info = self.get_cnct_info()

        lines = []
        # Add connection information if there are any connections
        if cnct_info:
            lines.append(
                f"{self.str__cnct_header_fmt()}{self.str__cnct_header()}{colored.attr('reset')}"
            )
            for mb_name, info in cnct_info.items():
                count = info.get("count", 0)
                targets = info.get("targets", [])

                cnct_name = textwrap.indent(
                    f"{self.str__cnct_name_fmt()}{mb_name}{colored.attr('reset')}", "  "
                )

                if count > 0:
                    lines.append(cnct_name)
                    for target in targets:
                        cnct_specs_str = (
                            f"⟷  {self.str__cnct_target_name_fmt()}"
                            f"{target['obj']}{colored.attr('reset')}."
                            f"{self.str__cnct_target_attr_fmt()}{target['cnct']}{colored.attr('reset')}"
                        )
                        lines.append(textwrap.indent(cnct_specs_str, "    "))
                else:
                    cnct_specs_str = (
                        f"{cnct_name}: {self.str__cnct_no_cnct_fmt()}"
                        f"{self.str__cnct_no_cnct()}{colored.attr('reset')}"
                    )
                    lines.append(textwrap.indent(cnct_specs_str, "  "))

        return "\n".join(lines)

    def str__automata_header_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.attr('bold')}{colored.fg('cyan')}"

    def str__automata_header(self):
        """Return colored formatting for the instance name representation."""
        return "Automata"

    def str__automaton_name_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.fg('white')}"

    def str__automaton_state_fmt(self):
        """Return colored formatting for the instance name representation."""
        return f"{colored.fg('rosy_brown')}"

    def str__automaton(self, aut):
        aut_str = (
            f"{self.str__automaton_name_fmt()}{aut.basename()}{colored.attr('reset')}: "
            f"{self.str__automaton_state_fmt()}{aut.currentState().basename()}{colored.attr('reset')}"
        )
        #    __import__("ipdb").set_trace()

        return aut_str

    def str__automata(self):
        """Return the colored instance name representation of the component."""
        lines = []
        # Add connection information if there are any connections
        lines.append(
            f"{self.str__automata_header_fmt()}{self.str__automata_header()}{colored.attr('reset')}"
        )
        for aut in self.automata():
            aut_str = self.str__automaton(aut)
            lines.append(textwrap.indent(aut_str, "  "))

        return "\n".join(lines)

    def __str__(self):
        """Return a string representation showing class name and instance name."""
        return (
            f"{self.str__class_name()} {self.str__instance_name()}\n"
            f"{textwrap.indent(self.str__variables(), '  ')}\n\n"
            f"{textwrap.indent(self.str__cnct(), '  ')}\n\n"
            f"{textwrap.indent(self.str__automata(), '  ')}"
        )

    def describe(self):
        """Returns a dictionary from a component."""
        dict_autom = {}
        for automKey in self.automata_d:
            dic_temp = self.automata_d.get(automKey)
            pycautom = PycAutomaton.from_dict(dic_temp)
            dict_autom_temp = pycautom.describe()
            dict_autom[automKey] = dict_autom_temp

        return {
            "name": self.name(),
            "label": self.label,
            "cls": self.className(),
            "description": self.description,
            "variables": [var.basename() for var in self.variables()],
            "automatons": dict_autom,
        }

    def add_automaton(self, **aut_specs):

        aut = PycAutomaton(**aut_specs)
        aut.update_bkd(self)

        self.automata_d[aut.name] = aut

        return aut

    def register_branch_effects(self, automaton, transition_name, branches):
        """Wire state-entry sensitive methods for each inst-branch's effects.

        Parameters
        ----------
        automaton : PycAutomaton
            Automaton hosting the inst transition.
        transition_name : str
            Name of the inst transition (used to namespace the sensitive
            method names; only required to be unique per (automaton, branch)).
        branches : list[StateProbModel]
            The transition's `target` list. Each branch with a non-empty
            ``effects`` dict gets a sensitive method registered on its target
            state, applying the effects whenever the state becomes active.

        Notes
        -----
        Effects are bound to the *target state* (state-entry pattern, like
        ``add_aut2st``). Brainstorm 2026-05-05 key decisions #3 and #4: target
        states must be distinct within a transition, so this association is
        unambiguous.
        """
        for branch in branches:
            if not branch.effects:
                continue

            target_state_bkd = automaton.get_state_by_name(branch.state)._bkd
            method_name = (
                f"branch_eff__{automaton.name}__{transition_name}__{branch.state}"
            )

            if branch.effects_format == "dict":
                effects_dict = branch.effects

                def _make_callback(state_bkd, eff):
                    def _callback():
                        if state_bkd.isActive():
                            for var, value in eff.items():
                                v = self.variable(var)
                                if v.value() != value:
                                    v.setValue(value)

                    return _callback

                callback = _make_callback(target_state_bkd, effects_dict)

                automaton._bkd.addSensitiveMethod(method_name, callback)
                for var in effects_dict.keys():
                    self.variable(var).addSensitiveMethod(method_name, callback)
                self.addStartMethod(method_name, callback)

            elif branch.effects_format == "records":
                effects_records = branch.effects

                def _make_callback_records(state_bkd, eff):
                    def _callback():
                        if state_bkd.isActive():
                            for elt in eff:
                                if elt["var"].value() != elt["value"]:
                                    elt["var"].setValue(elt["value"])

                    return _callback

                callback = _make_callback_records(target_state_bkd, effects_records)

                automaton._bkd.addSensitiveMethod(method_name, callback)
                for elt in effects_records:
                    elt["var"].addSensitiveMethod(method_name, callback)
                self.addStartMethod(method_name, callback)

            else:
                raise ValueError(
                    f"Unsupported effects_format {branch.effects_format!r} for branch {branch.state}"
                )

    def add_aut2st(
        self,
        name,
        st1="absent",
        st2="present",
        init_st2=False,
        trans_name_12_fmt="{st1}_to_{st2}",
        cond_occ_12=True,
        occ_law_12=None,
        occ_interruptible_12=True,
        effects_st1=None,
        effects_st1_format="dict",
        trans_name_21_fmt="{st2}_to_{st1}",
        cond_occ_21=True,
        occ_law_21=None,
        occ_interruptible_21=True,
        effects_st2=None,
        effects_st2_format="dict",
        step=None,
        pdmp_managers=None,
    ):
        """
                Adds a two-state automaton to the component.

                This method creates an automaton with two states and bidirectional transitions
                between them. It allows for configurable conditions, occurrence laws, and
                effects for each state and transition.

                Parameters
                ----------
                name : str
                    The name of the automaton.
                st1 : str, optional
                    The name of the first state (default is "absent").
                st2 : str, optional
                    The name of the second state (default is "present").
                init_st2 : bool, optional
                    If True, the initial state is st2; otherwise st1 (default is False).
                trans_name_12_fmt : str, optional
                    Format string for the transition name from st1 to st2
                    (default is "{st1}_to_{st2}").
                cond_occ_12 : bool, str, or callable, optional
                    The condition for the transition from st1 to st2 (default is True).
                    Can be a boolean, variable name string, or callable.
                occ_law_12 : dict, optional
                    The occurrence law for the transition from st1 to st2
                    (default is {"cls": "delay", "time": 0}).
                occ_interruptible_12 : bool, optional
                    If True, the transition from st1 to st2 is interruptible (default is True).
                effects_st1 : dict or list, optional
                    Effects to apply when in state st1 (default is {}).
                    Format depends on effects_st1_format parameter.
                effects_st1_format : str, optional
                    Format of effects_st1: "dict" for {var: value} or "records" for
                    [{"var": var_obj, "value": value}] (default is "dict").
                trans_name_21_fmt : str, optional
                    Format string for the transition name from st2 to st1
                    (default is "{st2}_to_{st1}").
                cond_occ_21 : bool, str, or callable, optional
                    The condition for the transition from st2 to st1 (default is True).
                    Can be a boolean, variable name string, or callable.
                occ_law_21 : dict, optional
                    The occurrence law for the transition from st2 to st1
                    (default is {"cls": "delay", "time": 0}).
                occ_interruptible_21 : bool, optional
                    If True, the transition from st2 to st1 is interruptible (default is True).
                effects_st2 : dict or list, optional
                    Effects to apply when in state st2 (default is {}).
                    Format depends on effects_st2_format parameter.
                effects_st2_format : str, optional
                    Format of effects_st2: "dict" for {var: value} or "records" for
                    [{"var": var_obj, "value": value}] (default is "dict").
                step : object, optional
                    Step object to add the sensitive methods to (default is None).
                pdmp_managers : list or object, optional
                    PDMP manager(s) to watch the transitions (default is []).

                Returns
                -------
                PycAutomaton
                    The created automaton object.

                Raises
                ------
                ValueError
                    If unsupported condition types or effect formats are provided.

                Examples
                --------
                >>> # Simple two-state automaton
                >>> comp.add_aut2st("power", st1="off", st2="on")

                >>> # With variable effects
                >>> comp.add_aut2st(
                ...     "valve",
                ...     st1="closed",
        b        ...     st2="open",
                ...     effects_st2={"flow_rate": 100}
                ... )
        """

        # Normalise mutable-default sentinels: each ``None`` parameter
        # falls back to the matching empty collection / canonical value.
        if occ_law_12 is None:
            occ_law_12 = {"cls": "delay", "time": 0}
        if occ_law_21 is None:
            occ_law_21 = {"cls": "delay", "time": 0}
        if effects_st1 is None:
            effects_st1 = {}
        if effects_st2 is None:
            effects_st2 = {}
        if pdmp_managers is None:
            pdmp_managers = []

        # st1_name = st_name_fmt.format(name=name, st=st1)
        # st2_name = st_name_fmt.format(name=name, st=st2)
        st1_name = st1
        st2_name = st2

        trans_name_12 = trans_name_12_fmt.format(name=name, st1=st1, st2=st2)
        trans_name_21 = trans_name_21_fmt.format(name=name, st1=st1, st2=st2)

        aut = PycAutomaton(
            # name=f"{self.name()}_{name}",
            name=name,
            states=[st1_name, st2_name],
            init_state=st2_name if init_st2 else st1_name,
            transitions=[
                {
                    "name": trans_name_12,
                    "source": st1_name,
                    "target": st2_name,
                    "is_interruptible": occ_interruptible_12,
                    "occ_law": occ_law_12,
                },
                {
                    "name": trans_name_21,
                    "source": st2_name,
                    "target": st1_name,
                    "is_interruptible": occ_interruptible_21,
                    "occ_law": occ_law_21,
                },
            ],
        )

        aut.update_bkd(self)

        # Jump 1 -> 2
        # -----------
        # Conditions
        if isinstance(cond_occ_12, bool) or callable(cond_occ_12):
            aut.get_transition_by_name(trans_name_12)._bkd.setCondition(cond_occ_12)

        elif isinstance(cond_occ_12, str):
            aut.get_transition_by_name(trans_name_12)._bkd.setCondition(
                self.variable(cond_occ_12)
            )
        else:
            raise ValueError(
                f"Condition '{cond_occ_12}' for transition {trans_name_12} not supported"
            )

        # Effects
        st2_bkd = aut.get_state_by_name(st2_name)._bkd
        #    var_value_list_12 = self.pat_to_var_value(*effects_12)
        if len(effects_st2) > 0:

            if effects_st2_format == "dict":

                def sensitive_method_st_2():
                    if st2_bkd.isActive():
                        for var, value in effects_st2.items():
                            v = self.variable(var)
                            if v.value() != value:
                                v.setValue(value)

            elif effects_st2_format == "records":

                def sensitive_method_st_2():
                    if st2_bkd.isActive():
                        for elt in effects_st2:
                            # print(
                            #     f'{elt["var"].name()} [{elt["var"].value()}] -> {elt["value"]}'
                            # )
                            if elt["var"].value() != elt["value"]:
                                elt["var"].setValue(elt["value"])

            else:
                raise ValueError(
                    f"effects_st_2_format {effects_st2_format} not supported"
                )
            # setattr(comp._bkd, method_name, sensitive_method)
            sensitive_method_name_st_2 = f"effect__{self.name()}_{name}_{trans_name_12}"
            aut._bkd.addSensitiveMethod(
                sensitive_method_name_st_2, sensitive_method_st_2
            )
            if effects_st2_format == "dict":

                for var in effects_st2.keys():
                    # getattr(self, var).addSensitiveMethod(
                    #     method_name_12, sensitive_method_12
                    # )
                    self.variable(var).addSensitiveMethod(
                        sensitive_method_name_st_2, sensitive_method_st_2
                    )
            elif effects_st2_format == "records":

                for elt in effects_st2:
                    # getattr(self, var).addSensitiveMethod(
                    #     method_name_12, sensitive_method_12
                    # )
                    elt["var"].addSensitiveMethod(
                        sensitive_method_name_st_2, sensitive_method_st_2
                    )
            else:
                raise ValueError(
                    f"effects_st_2_format {effects_st2_format} not supported"
                )

            self.addStartMethod(sensitive_method_name_st_2, sensitive_method_st_2)
            if step:
                step.addMethod(self, sensitive_method_name_st_2)

        # Jump 2 -> 1
        # -----------
        # Conditions
        if isinstance(cond_occ_21, bool) or callable(cond_occ_21):
            aut.get_transition_by_name(trans_name_21)._bkd.setCondition(cond_occ_21)

        elif isinstance(cond_occ_21, str):
            aut.get_transition_by_name(trans_name_21)._bkd.setCondition(
                self.variable(cond_occ_21)
            )
        else:
            raise ValueError(
                f"Condition '{cond_occ_21}' for transition {trans_name_21} not supported"
            )
        # Effects
        # __import__("ipdb").set_trace()

        st1_bkd = aut.get_state_by_name(st1_name)._bkd
        # var_value_list_21 = self.pat_to_var_value(*effects_21)
        if len(effects_st1) > 0:
            if effects_st1_format == "dict":

                def sensitive_method_st_1():
                    if st1_bkd.isActive():
                        for var, value in effects_st1.items():
                            v = self.variable(var)
                            if v.value() != value:
                                v.setValue(value)

            elif effects_st1_format == "records":

                def sensitive_method_st_1():
                    if st1_bkd.isActive():
                        for elt in effects_st1:
                            if elt["var"].value() != elt["value"]:
                                elt["var"].setValue(elt["value"])

            else:
                raise ValueError(
                    f"effects_st_1_format {effects_st1_format} not supported"
                )

            # def sensitive_method_st_1():
            #     if st1_bkd.isActive():
            #         # if "T2_f3_fed_control" in effects_21.keys():
            #         #     __import__("ipdb").set_trace()

            #         [
            #             # getattr(self, var).setValue(value)
            #             self.variable(var).setValue(value)
            #             for var, value in effects_st_1.items()
            #         ]

            # setattr(comp._bkd, method_name, sensitive_method)
            sensitive_method_name_st_1 = f"effect__{self.name()}_{name}_{trans_name_21}"
            aut._bkd.addSensitiveMethod(
                sensitive_method_name_st_1, sensitive_method_st_1
            )

            if effects_st1_format == "dict":

                for var in effects_st1.keys():
                    # getattr(self, var).addSensitiveMethod(
                    #     method_name_12, sensitive_method_12
                    # )
                    self.variable(var).addSensitiveMethod(
                        sensitive_method_name_st_1, sensitive_method_st_1
                    )
            elif effects_st1_format == "records":

                for elt in effects_st1:
                    # getattr(self, var).addSensitiveMethod(
                    #     method_name_12, sensitive_method_12
                    # )
                    elt["var"].addSensitiveMethod(
                        sensitive_method_name_st_1, sensitive_method_st_1
                    )
            else:
                raise ValueError(
                    f"effects_st_1_format {effects_st1_format} not supported"
                )

            # for var, value in effects_st_1.items():
            #     # getattr(self, var).addSensitiveMethod(
            #     #     method_name_21, sensitive_method_21
            #     # )
            #     # print(var, method_name_21, sensitive_method_21)
            #     self.variable(var).addSensitiveMethod(
            #         sensitive_method_name_st_1, sensitive_method_st_1
            #     )

            self.addStartMethod(sensitive_method_name_st_1, sensitive_method_st_1)

            if step:
                step.addMethod(self, sensitive_method_name_st_1)

        # Update automata dict
        # --------------------
        if pdmp_managers:
            if not isinstance(pdmp_managers, list):
                pdmp_managers = [pdmp_managers]
            for pdmp_manager in pdmp_managers:
                pdmp_manager.addWatchedTransition(
                    aut.get_transition_by_name(trans_name_12)._bkd
                )
                pdmp_manager.addWatchedTransition(
                    aut.get_transition_by_name(trans_name_21)._bkd
                )

        self.automata_d[aut.name] = aut

        return aut

    def pat_to_var_value_list(self, *pat_value_list):
        """
        Converts pattern-value pairs to variable-value pairs.

        Parameters
        ----------
        *pat_value_list : list of tuples
            List of pattern-value pairs.

        Returns
        -------
        list of tuples
            List of variable-value pairs.
        """

        variables = self.variables()

        var_value_list = []

        for pat, value in pat_value_list:
            var_list = [
                (var, value) for var in variables if re.search(pat, var.basename())
            ]
            var_value_list.extend(var_list)

        return var_value_list

    def pat_to_var_value_dict(self, **pat_value_dict):
        """
        Converts pattern-value dictionary to variable-value dictionary.

        Parameters
        ----------
        **pat_value_dict : dict
            Dictionary of pattern-value pairs where keys are regex patterns
            and values are the values to assign to matching variables.

        Returns
        -------
        dict
            Dictionary of variable-value pairs where keys are variable objects
            and values are the assigned values.
        """

        variables = self.variables()

        var_value_dict = {}

        for pat, value in pat_value_dict.items():
            var_dict = {
                var: value for var in variables if re.search(pat, var.basename())
            }
            var_value_dict.update(var_dict)

        return var_value_dict

    def get_cnct_info(self):
        """
        Returns information on object connections.

        This method retrieves connection information for all message boxes
        of the component, including connection counts and target details.

        Returns:
            dict: Dictionary containing connection information for each message box,
                  with keys being connection names and values containing:
                  - count: Number of connections
                  - targets: List of target objects with their names and connections
        """
        cnct_info = {}
        for mb in self.messageBoxes():
            cnct_name = mb.basename()
            targets = []
            for cnt_i in range(mb.cnctCount()):
                cnct_cur = mb.cnct(cnt_i)
                targets.append(
                    {
                        "obj": cnct_cur.parent().name(),
                        "cnct": cnct_cur.basename(),
                    }
                )

            cnct_info[cnct_name] = {
                "count": mb.cnctCount(),
                "targets": targets,
            }

        return cnct_info


class ObjEvent(PycComponent):

    def __init__(
        self,
        name,
        cond,
        inner_logic=all,
        outer_logic=any,
        cond_operator="==",
        cond_value=True,
        tempo_occ=0,
        tempo_not_occ=0,
        event_aut_name="ev",
        occ_state_name="occ",
        not_occ_state_name="not_occ",
        **kwargs,
    ):
        super().__init__(name, **kwargs)

        # Expose the automaton names so post-mortem sequence tooling
        # (``SequenceAnalyser._discover_objevent_specs`` /
        # ``filter_objevent_cycles``) can rebuild the occ/not_occ
        # transition patterns by introspection rather than guessing.
        # NOTE: a monitored transition's ``basename()`` equals these
        # state names ONLY because the automaton below uses
        # ``trans_name_12_fmt="{st2}"`` / ``trans_name_21_fmt="{st1}"``.
        # Keep those formats in sync if you touch the filter.
        self.event_aut_name = event_aut_name
        self.occ_state_name = occ_state_name
        self.not_occ_state_name = not_occ_state_name

        cond = sanitize_cond_format(cond)

        if isinstance(inner_logic, str):
            inner_logic = getattr(builtins, inner_logic)
        if isinstance(outer_logic, str):
            outer_logic = getattr(builtins, outer_logic)

        cond_operator_fun = get_operator_function(cond_operator)

        if isinstance(cond, list):

            cond_bis = prepare_attr_tree(cond, system=self.system())

            def cond_fun():
                return cond_operator_fun(
                    outer_logic(
                        [
                            inner_logic(
                                [
                                    get_operator_function(c_inner.get("ope", "=="))(
                                        getattr(
                                            c_inner["attr"], c_inner["attr_val_name"]
                                        )(),
                                        c_inner["value"],
                                    )
                                    for c_inner in c_outer
                                ]
                            )
                            for c_outer in cond_bis
                        ]
                    ),
                    cond_value,
                )

        else:
            cond_fun = cond

        self.add_aut2st(
            name=event_aut_name,
            st1=not_occ_state_name,
            st2=occ_state_name,
            init_st2=False,
            trans_name_12_fmt="{st2}",
            cond_occ_12=cond_fun,
            occ_law_12={"cls": "delay", "time": tempo_occ},
            occ_interruptible_12=True,
            trans_name_21_fmt="{st1}",
            cond_occ_21=lambda: not cond_fun(),
            occ_law_21={"cls": "delay", "time": tempo_not_occ},
            occ_interruptible_21=True,
        )

    # def sanitize_cond_format(self, cond):

    #     if isinstance(cond, dict):
    #         cond = [[cond]]
    #     else:
    #         if isinstance(cond, list):
    #             if all([isinstance(c, list) for c in cond]):
    #                 if any(
    #                     [any([not isinstance(ci, dict) for ci in co]) for co in cond]
    #                 ):
    #                     raise ValueError(
    #                         "ObjEvent condition specification must be a list of list of dict"
    #                     )
    #             elif all([isinstance(c, dict) for c in cond]):
    #                 # Just add the second level of list
    #                 cond = [cond]
    #             else:
    #                 raise ValueError(
    #                     "ObjEvent condition specification must be a list of list of dict"
    #                 )

    #     return cond


# FailureModeBaseSpec fields with no native ObjMode2S meaning: accepted
# when they carry their BaseSpec default (the ObjFMGenericSpec wire path
# always emits defaults through ``model_dump``), rejected with a clear
# error on any explicit non-default value (never silently ignored).
# ``fm_name`` and ``failure_cond`` are FUNCTIONAL wire aliases instead
# (mode_name / occ_cond).
_MODE2S_BASESPEC_PASSTHROUGH_DEFAULTS: dict = {
    "failure_state": ("occ",),
    "repair_state": ("rep",),
    "failure_effects": (None, {}),
    "failure_effects_trans": (None, {}),
    "repair_cond": (None, True),
    "repair_effects": (None, {}),
    "repair_effects_trans": (None, {}),
    "failure_param_name": (None, [], ""),
    "repair_param_name": (None, [], ""),
    "failure_param": (None, []),
    "repair_param": (None, []),
}

# Identifier-like, regex-safe state names: they are interpolated into
# monitor masks and sequence-filter patterns.
_MODE2S_STATE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ObjMode2S(FmWiringMixin, PycComponent):
    """Generic two-state mode engine (logical states ``occ`` / ``not_occ``).

    ``ObjMode2S`` is the engine behind the mode-like components: it owns
    the common-cause combinatorics (one automaton per target
    combination), the three behaviours (``internal``, ``external``,
    ``external_rep_indep``), the effect wiring (state-based level clamps
    and trans-based one-shot pulses via :class:`FmWiringMixin`), and —
    since the ObjMode2S chantier — the per-direction occurrence laws
    declared through :mod:`cod3s.pycatshoo.mode_law` specs.

    Vocabulary note (edge vs state): ``occ_law`` / ``occ_cond`` are
    properties of the EDGE entering ``occ`` (``not_occ -> occ``), while
    ``occ_effects`` is the level clamp maintained WHILE in ``occ``; the
    ``not_occ_*`` fields mirror this for the return edge / state. This
    follows the historical ``failure_*`` convention of ``ObjFM``.

    The historical classes ``ObjFM`` / ``ObjFMExp`` / ``ObjFMDelay`` /
    ``ObjFMInst`` / ``ObjEvent`` are thin backward-compatible façades
    over this engine. The engine consumes laws, conditions and defaults
    exclusively through its template hooks (below); the ``ModeLaw``
    specs are merely the *default implementation* of those hooks, so a
    façade (or a third-party subclass through a façade) can keep
    providing arbitrary backend law dicts:

    * ``_default_direction_param_names(direction)`` -> list[str]
    * ``_default_direction_params(direction)`` -> list
    * ``_is_direction_law_active(direction, params)`` -> bool
    * ``_direction_law_bkd(direction, params)`` -> backend law dict
    * ``_direction_cond(direction, target_comps, param=None)`` -> callable
    * ``_validate_trans_effects()``
    * ``_build_mode_automaton(...)`` -> PycAutomaton
    * ``_build_target_automaton(...)`` (external behaviours)

    ``direction`` is ``"occ"`` (edge ``not_occ -> occ``) or
    ``"not_occ"`` (edge ``occ -> not_occ``).

    Engine code must never reference the façade classes or the
    failure/repair vocabulary — the façade layer owns that mapping.
    ``self.fm_name`` is kept as a plain read alias of ``mode_name`` for
    duck-typed tooling (sequence discovery, wiring labels).
    """

    VALID_BEHAVIOURS = ("internal", "external", "external_rep_indep")

    #: Native engine instances reject unknown constructor kwargs
    #: (silent-typo hardening). Façades restore the historical
    #: passthrough by turning this off.
    _engine_strict_kwargs = True

    #: Kwargs consumed by ``PycComponent.__init__`` and therefore always
    #: legitimate.
    _PYC_COMPONENT_KWARGS = ("label", "description", "metadata")

    def __init__(
        self,
        mode_name=None,
        *,
        targets=None,
        target_name=None,
        behaviour="internal",
        occ_state="occ",
        occ_law=None,
        occ_cond=True,
        occ_effects=None,
        occ_effects_trans=None,
        occ_param_name=None,
        occ_param=None,
        not_occ_state="not_occ",
        not_occ_law=None,
        not_occ_cond=True,
        not_occ_effects=None,
        not_occ_effects_trans=None,
        not_occ_param_name=None,
        not_occ_param=None,
        param_name_order_prefix="__{order}_o_{order_max}",
        trans_name_prefix="__cc_{target_comb_u}",
        trans_name_prefix_fun=None,
        drop_inactive_automata=True,
        cond_inner_logic=all,
        cond_outer_logic=any,
        step=None,
        fm_name=None,
        failure_cond=None,
        **kwargs,
    ):
        # ---- Wire aliases (ObjFMGenericSpec path: fm_cls(**spec_dict)) ----
        if fm_name is not None:
            if mode_name is not None and mode_name != fm_name:
                raise ValueError(
                    f"ObjMode2S: both mode_name={mode_name!r} and its wire "
                    f"alias fm_name={fm_name!r} are set — set exactly one."
                )
            mode_name = fm_name
        if not mode_name or not isinstance(mode_name, str):
            raise ValueError("ObjMode2S: mode_name must be a non-empty string.")
        if failure_cond is not None and failure_cond is not True:
            # Wire alias of occ_cond.
            if occ_cond is not True:
                raise ValueError(
                    f"Mode {mode_name!r}: both occ_cond and its wire alias "
                    f"failure_cond are set — set exactly one."
                )
            occ_cond = failure_cond

        # ---- BaseSpec compatibility table (never silently ignore) ----
        if self._engine_strict_kwargs:
            for key, accepted in _MODE2S_BASESPEC_PASSTHROUGH_DEFAULTS.items():
                if key in kwargs:
                    value = kwargs.pop(key)
                    if not any(value == acc for acc in accepted):
                        raise ValueError(
                            f"ObjMode2S {mode_name!r}: field {key!r}={value!r} "
                            f"belongs to the two-state ObjFM façade API and "
                            f"has no native meaning. Use the engine fields "
                            f"(occ_* / not_occ_*), or declare the mode with "
                            f"an ObjFM* class."
                        )
            unknown = [k for k in kwargs if k not in self._PYC_COMPONENT_KWARGS]
            if unknown:
                raise TypeError(
                    f"ObjMode2S got unexpected keyword argument(s) "
                    f"{sorted(unknown)}. Known extra kwargs: "
                    f"{list(self._PYC_COMPONENT_KWARGS)}. A typo here would "
                    f"otherwise silently build a wrong model."
                )

        # ---- State-name validation (mask / pattern safety) ----
        for label, st in (("occ_state", occ_state), ("not_occ_state", not_occ_state)):
            if not isinstance(st, str) or not _MODE2S_STATE_NAME_RE.match(st):
                raise ValueError(
                    f"Mode {mode_name!r}: {label}={st!r} is not a valid state "
                    f"name (identifier-like, regex-safe names only — they are "
                    f"interpolated into monitor masks and filter patterns)."
                )
        if occ_state == not_occ_state:
            raise ValueError(
                f"Mode {mode_name!r}: occ_state and not_occ_state must be "
                f"distinct, both are {occ_state!r}."
            )

        # Normalise mutable-default sentinels.
        if targets is None:
            targets = []
        if occ_effects is None:
            occ_effects = {}
        if occ_effects_trans is None:
            occ_effects_trans = {}
        if occ_param_name is None:
            occ_param_name = []
        if occ_param is None:
            occ_param = []
        if not_occ_effects is None:
            not_occ_effects = {}
        if not_occ_effects_trans is None:
            not_occ_effects_trans = {}
        if not_occ_param_name is None:
            not_occ_param_name = []
        if not_occ_param is None:
            not_occ_param = []

        self.mode_name = mode_name
        # Plain read alias for duck-typed tooling (sequence discovery,
        # FmWiringMixin labels). Documented legacy alias — do not use in
        # engine logic.
        self.fm_name = mode_name
        self.targets = [targets] if isinstance(targets, str) else targets
        if target_name is None and len(self.targets) == 1:
            target_name = self.targets[0]
        self.target_name = target_name or self._factorize_target_names(targets)

        comp_name = f"{self.target_name}__{self.mode_name}"

        super().__init__(comp_name, **kwargs)

        order_max = len(self.targets)

        if behaviour not in self.VALID_BEHAVIOURS:
            raise ValueError(
                f"behaviour must be one of {self.VALID_BEHAVIOURS}, got '{behaviour}'"
            )
        self.behaviour = behaviour

        # Per-direction law specs (ModeLaw | dict | None). None = the
        # law is provided by the template hooks (façade / subclass).
        self.occ_law = (
            parse_mode_law(occ_law, what="occ_law") if occ_law is not None else None
        )
        self.not_occ_law = (
            parse_mode_law(not_occ_law, what="not_occ_law")
            if not_occ_law is not None
            else None
        )

        # Create control variables for external behaviours
        self.ctrl_vars = {}
        if self.behaviour in ("external", "external_rep_indep"):
            for target_name_cur in self.targets:
                ctrl_var_name = f"ctrl_{self.mode_name}_{target_name_cur}"
                ctrl_var = self.addVariable(ctrl_var_name, pyc.TVarType.t_bool, False)
                self.ctrl_vars[target_name_cur] = ctrl_var

        self.occ_cond = copy.deepcopy(occ_cond)
        self.not_occ_cond = copy.deepcopy(not_occ_cond)

        self.occ_state = occ_state
        self.not_occ_state = not_occ_state

        if isinstance(step, str):
            step_name = step
            step = self.system().step(step_name)
            if step is None:
                raise ValueError(f"Step {step_name} does not exist in this system")
        self.step = step

        self.cond_inner_logic = cond_inner_logic
        self.cond_outer_logic = cond_outer_logic

        self.var_params = {}
        self.occ_effects = copy.deepcopy(occ_effects)
        self.not_occ_effects = copy.deepcopy(not_occ_effects)
        # Trans-based effects (mode="trans_based"): applied once at the
        # instant the occ / not_occ transition fires, via a
        # transition-edge sensitive method (see
        # ``_wire_transition_effects``), unlike the state-clamped
        # ``occ_effects`` / ``not_occ_effects``.
        self.occ_effects_trans = copy.deepcopy(occ_effects_trans)
        self.not_occ_effects_trans = copy.deepcopy(not_occ_effects_trans)
        self._validate_trans_effects()

        # Silent-failure hardening: resolve every effect against every
        # target BEFORE creating any variable or automaton, so a typo on
        # one target fails cleanly instead of leaving a half-built mode.
        self._dry_run_resolve_effects()

        self.occ_param_name = (
            [occ_param_name]
            if isinstance(occ_param_name, str)
            else copy.deepcopy(occ_param_name)
        )
        self.occ_param_name = self._default_direction_param_names("occ")

        self.not_occ_param_name = (
            [not_occ_param_name]
            if isinstance(not_occ_param_name, str)
            else copy.deepcopy(not_occ_param_name)
        )
        self.not_occ_param_name = self._default_direction_param_names("not_occ")

        self.param_name_order_prefix = param_name_order_prefix
        self.trans_name_prefix = trans_name_prefix
        self.trans_name_prefix_fun = trans_name_prefix_fun

        self.occ_param = (
            [occ_param] if not isinstance(occ_param, list) else copy.deepcopy(occ_param)
        )
        occ_param_diff = len(self.targets) - len(self.occ_param)
        if occ_param_diff > 0:
            self.occ_param = self._default_direction_params("occ")
        elif occ_param_diff < 0:
            raise ValueError(
                f"Mode of order {order_max} but you provide "
                f"{len(self.occ_param)} occ (failure) parameters: {self.occ_param}"
            )

        self.not_occ_param = (
            [not_occ_param]
            if not isinstance(not_occ_param, list)
            else copy.deepcopy(not_occ_param)
        )
        not_occ_param_diff = len(self.targets) - len(self.not_occ_param)
        if not_occ_param_diff > 0:
            self.not_occ_param = self._default_direction_params("not_occ")
        elif not_occ_param_diff < 0:
            raise ValueError(
                f"Mode of order {order_max} but you provide "
                f"{len(self.not_occ_param)} not_occ (repair) parameters: "
                f"{self.not_occ_param}"
            )

        # Store order 1 return-direction params for external_rep_indep
        self.not_occ_var_params_order1 = None

        # Track impacting automata for each target in external modes
        self.target_impacting_automata = {t: [] for t in self.targets}

        for order in range(1, order_max + 1):

            occ_var_params_cur = self._build_order_param_variables(
                "occ", order, order_max
            )
            not_occ_var_params_cur = self._build_order_param_variables(
                "not_occ", order, order_max
            )

            # Store order 1 params
            if order == 1:
                self.not_occ_var_params_order1 = not_occ_var_params_cur

            if (
                drop_inactive_automata
                and not self._is_direction_law_active("occ", occ_var_params_cur)
                and not self._is_direction_law_active("not_occ", not_occ_var_params_cur)
            ):
                continue

            for target_set_idx in itertools.combinations(range(order_max), order):

                # Prepare effects based on behaviour.
                # external: level (state) effects on the target are handled by
                #   the centralized ctrl_var sensitive method below (the mode's
                #   own transitions carry no direct level effects on ctrl_vars);
                #   trans-based one-shot effects DO apply, wired on the mode's
                #   OWN occ / not_occ transition and writing the target's
                #   persistent gate once per crossing (both-pulse
                #   inter-component), resolved against the targets exactly like
                #   the internal branch.
                # external_rep_indep: trigger model (mode.occ sets ctrl=True
                #   directly on the transition; mode.not_occ does NOT touch
                #   ctrl, the target owns the reset on its own return
                #   transition). Trans-based effects are rejected upfront for
                #   it (and for CCF) by ``_validate_trans_effects``, so those
                #   lists stay empty in the paths that never opt in.
                occ_effects_trans_cur = []
                not_occ_effects_trans_cur = []
                if self.behaviour == "external":
                    occ_effects_cur = []
                    not_occ_effects_cur = []
                elif self.behaviour == "external_rep_indep":
                    occ_effects_cur = [
                        {"var": self.ctrl_vars[self.targets[idx]], "value": True}
                        for idx in target_set_idx
                    ]
                    not_occ_effects_cur = []
                else:  # internal behaviour
                    occ_effects_cur = []
                    for var, value in self.occ_effects.items():
                        for target_idx in target_set_idx:
                            comp_cur = self.system().component(self.targets[target_idx])

                            if hasattr(comp_cur, var):
                                comp_var = getattr(comp_cur, var)
                            elif var in [v.basename() for v in comp_cur.variables()]:
                                comp_var = comp_cur.variable(var)
                            else:
                                raise ValueError(
                                    f"Component {repr(comp_cur)} has no attribute nor variable named {var}"
                                )
                            occ_effects_cur.append({"var": comp_var, "value": value})

                    not_occ_effects_cur = []
                    for var, value in self.not_occ_effects.items():
                        for target_idx in target_set_idx:
                            comp_cur = self.system().component(self.targets[target_idx])

                            if hasattr(comp_cur, var):
                                comp_var = getattr(comp_cur, var)
                            elif var in [v.basename() for v in comp_cur.variables()]:
                                comp_var = comp_cur.variable(var)
                            else:
                                raise ValueError(
                                    f"Component {repr(comp_cur)} has no attribute nor variable named {var}"
                                )
                            not_occ_effects_cur.append(
                                {"var": comp_var, "value": value}
                            )

                # Trans-based (one-shot edge) effects: resolved IDENTICALLY for
                # internal and external (var_name -> target variable), wired on
                # the mode's occ / not_occ transition edge by
                # ``_wire_transition_effects`` rather than on the state. For
                # external the pulse writes the TARGET's persistent gate,
                # coexisting with the level ctrl_var (both-pulse
                # inter-component). external_rep_indep keeps the trans dicts
                # empty via ``_validate_trans_effects``, so this loop is an
                # inert no-op there (empty dicts resolve to []).
                for target_idx in target_set_idx:
                    comp_cur = self.system().component(self.targets[target_idx])
                    occ_effects_trans_cur += self._resolve_target_effects(
                        comp_cur,
                        self.targets[target_idx],
                        self.occ_effects_trans,
                        kind="failure_effects_trans",
                    )
                    not_occ_effects_trans_cur += self._resolve_target_effects(
                        comp_cur,
                        self.targets[target_idx],
                        self.not_occ_effects_trans,
                        kind="repair_effects_trans",
                    )

                occ_state_name_cur = self.occ_state
                not_occ_state_name_cur = self.not_occ_state
                aut_name_cur = self.mode_name
                if order_max > 1:
                    trans_name_prefix_cur = cc_comb_suffix(
                        target_set_idx,
                        order_max,
                        trans_name_prefix=self.trans_name_prefix,
                        trans_name_prefix_fun=self.trans_name_prefix_fun,
                    )
                    aut_name_cur += trans_name_prefix_cur
                    occ_state_name_cur += trans_name_prefix_cur
                    not_occ_state_name_cur += trans_name_prefix_cur

                target_comps_cur = [
                    self.system().component(self.targets[idx]) for idx in target_set_idx
                ]

                occ_cond_cur = self._direction_cond(
                    "occ", target_comps=target_comps_cur, param=occ_var_params_cur
                )
                not_occ_cond_cur = self._direction_cond(
                    "not_occ",
                    target_comps=target_comps_cur,
                    param=not_occ_var_params_cur,
                )

                if self.behaviour in ("external", "external_rep_indep"):

                    def make_external_cond(
                        base_cond, targets, mode_name, required_state_name
                    ):
                        def cond():
                            # Check base condition
                            if not base_cond():
                                return False
                            # Check all targets are in required state
                            for t in targets:
                                if mode_name not in t.automata_d:
                                    return False
                                st = t.automata_d[mode_name].get_state_by_name(
                                    required_state_name
                                )
                                if not st._bkd.isActive():
                                    return False
                            return True

                        return cond

                    # Occ edge: targets must be in the not_occ (resting)
                    # state. The target automaton's state is name-prefixed
                    # since the multi-mode-per-target fix; mirror that here.
                    occ_cond_cur = make_external_cond(
                        occ_cond_cur,
                        target_comps_cur,
                        self.mode_name,
                        f"{self.mode_name}__{self.not_occ_state}",
                    )

                    if self.behaviour == "external":
                        # Return edge: targets must be in the occ state.
                        not_occ_cond_cur = make_external_cond(
                            not_occ_cond_cur,
                            target_comps_cur,
                            self.mode_name,
                            f"{self.mode_name}__{self.occ_state}",
                        )
                    # external_rep_indep: the mode's return edge is
                    # unconditional (trigger model — instantaneous
                    # delay(0), see the law override below).
                    else:
                        not_occ_cond_cur = _always_true

                # Mode return law: instantaneous in external_rep_indep
                # (trigger — the mode emits a one-shot signal then resets).
                if self.behaviour == "external_rep_indep":
                    mode_return_law = {"cls": "delay", "time": 0}
                else:
                    mode_return_law = self._direction_law_bkd(
                        "not_occ", not_occ_var_params_cur
                    )

                aut = self._build_mode_automaton(
                    aut_name=aut_name_cur,
                    not_occ_state_name=not_occ_state_name_cur,
                    occ_state_name=occ_state_name_cur,
                    occ_cond=occ_cond_cur,
                    not_occ_cond=not_occ_cond_cur,
                    occ_var_params=occ_var_params_cur,
                    not_occ_var_params=not_occ_var_params_cur,
                    occ_effects=occ_effects_cur,
                    not_occ_effects=not_occ_effects_cur,
                    not_occ_law=mode_return_law,
                    occ_effects_trans=occ_effects_trans_cur,
                    not_occ_effects_trans=not_occ_effects_trans_cur,
                )

                # Record impacting automata for centralized control
                if self.behaviour in ("external", "external_rep_indep"):
                    for idx in target_set_idx:
                        impacted_target = self.targets[idx]
                        self.target_impacting_automata[impacted_target].append(
                            (aut, occ_state_name_cur)
                        )

        # Centralized ctrl_var management for `external` only.
        # `external_rep_indep` does NOT use this: mode.occ sets ctrl=True via
        # a direct effect on the transition (trigger model), and target.rep
        # clears it via the target automaton's own return effect.
        # Re-introducing the OR-based sensitive method here would reset
        # ctrl_var as soon as the mode triggers back, breaking the model.
        if self.behaviour == "external":
            for (
                ctrl_target_name,
                impacting_info,
            ) in self.target_impacting_automata.items():
                ctrl_var = self.ctrl_vars[ctrl_target_name]

                def make_ctrl_method(cv, info_list):
                    def ctrl_method():
                        should_be_failed = any(
                            a.get_state_by_name(st_name)._bkd.isActive()
                            for a, st_name in info_list
                        )
                        if cv.value() != should_be_failed:
                            cv.setValue(should_be_failed)

                    return ctrl_method

                method = make_ctrl_method(ctrl_var, impacting_info)
                method_name = f"ctrl_sync__{self.name()}_{ctrl_target_name}"

                for aut, _ in impacting_info:
                    aut._bkd.addSensitiveMethod(method_name, method)

                self.addStartMethod(method_name, method)

        # In external_rep_indep, the target's self-return uses the order-1
        # return law. If that law is inactive the targets would never
        # return — which is almost certainly a config mistake. Raise a
        # clear error rather than silently produce a one-shot model.
        if self.behaviour == "external_rep_indep":
            if self.not_occ_var_params_order1 is None or not (
                self._is_direction_law_active("not_occ", self.not_occ_var_params_order1)
            ):
                raise ValueError(
                    f"behaviour='external_rep_indep' requires the order-1 "
                    f"return (repair) law to be active for mode "
                    f"'{self.mode_name}'. Provide a non-zero order-1 "
                    f"parameter (repair_param / not_occ_param)."
                )

        # Create automata in target components for external behaviours
        if self.behaviour in ("external", "external_rep_indep"):
            for target_name_cur in self.targets:
                # Create fresh dict each time to avoid mutation issues
                if self.behaviour == "external":
                    target_return_law = {"cls": "delay", "time": 0}
                else:  # external_rep_indep
                    target_return_law = self._direction_law_bkd(
                        "not_occ", self.not_occ_var_params_order1
                    )

                self._build_target_automaton(
                    target_name_cur,
                    target_return_law,
                    occ_effects=self.occ_effects,
                    not_occ_effects=self.not_occ_effects,
                )

    # ------------------------------------------------------------------
    # Template hooks — native (law-spec-driven) default implementations.
    # The façades override these to delegate to the historical
    # failure/repair-named hooks.
    # ------------------------------------------------------------------

    def _build_order_param_variables(self, direction, order, order_max):
        """Create the ``t_double`` parameter variables of ``direction``
        for one CC ``order`` and return them as ``{base_name: variable}``.

        Variables are created for every order — including orders whose
        automata are later dropped by ``drop_inactive_automata`` — so
        study indicators can always reference them.
        """
        param_names = (
            self.occ_param_name if direction == "occ" else self.not_occ_param_name
        )
        param_cur = (
            self.occ_param[order - 1]
            if direction == "occ"
            else self.not_occ_param[order - 1]
        )
        if not isinstance(param_cur, tuple):
            param_cur = (param_cur,)

        var_params_cur = {}
        for param_name_cur, param_value in zip(param_names, param_cur):
            param_var_name = order_param_name(
                param_name_cur,
                order,
                order_max,
                fmt=self.param_name_order_prefix,
            )
            var_param = self.addVariable(
                param_var_name, pyc.TVarType.t_double, param_value
            )
            var_params_cur.update({param_name_cur: var_param})
        return var_params_cur

    def _dry_run_resolve_effects(self):
        """Resolve all effect dicts against all targets (build nothing).

        Runs before any variable/automaton creation. Reuses the exact
        historical resolution code paths so the error messages stay
        identical — only earlier.
        """
        for tgt in self.targets:
            try:
                comp_cur = self.system().component(tgt)
            except Exception as exc:
                comp_cur = None
                cause = exc
            else:
                cause = None
            if comp_cur is None:
                raise ValueError(
                    f"Mode '{self.mode_name}': target component {tgt!r} not "
                    f"found in the system. Create the targets before the mode."
                ) from cause
            if self.behaviour == "internal":
                for effects in (self.occ_effects, self.not_occ_effects):
                    for var in effects:
                        if not (
                            hasattr(comp_cur, var)
                            or var in [v.basename() for v in comp_cur.variables()]
                        ):
                            raise ValueError(
                                f"Component {repr(comp_cur)} has no attribute nor variable named {var}"
                            )
            else:
                self._resolve_target_effects(
                    comp_cur, tgt, self.occ_effects, kind="failure_effects"
                )
                self._resolve_target_effects(
                    comp_cur, tgt, self.not_occ_effects, kind="repair_effects"
                )
            self._resolve_target_effects(
                comp_cur, tgt, self.occ_effects_trans, kind="failure_effects_trans"
            )
            self._resolve_target_effects(
                comp_cur, tgt, self.not_occ_effects_trans, kind="repair_effects_trans"
            )

    def _direction_law(self, direction):
        """Return the law spec of ``direction`` (may be None)."""
        return self.occ_law if direction == "occ" else self.not_occ_law

    def _require_direction_law(self, direction):
        law = self._direction_law(direction)
        if law is None:
            raise ValueError(
                f"Mode '{self.mode_name}': no "
                f"{'occ_law' if direction == 'occ' else 'not_occ_law'} "
                f"provided (and no subclass hook supplies one). Declare the "
                f"law with a ModeLaw spec, e.g. {{'cls': 'exp', 'rate': ...}}."
            )
        return law

    def _default_direction_param_names(self, direction):
        """Return the parameter variable base names of ``direction``.

        Called right after the user-provided names are normalised; the
        return value is assigned back. Native default: keep the provided
        names, or derive ``occ_<field>`` / ``not_occ_<field>`` from the
        law spec when none were provided.
        """
        current = self.occ_param_name if direction == "occ" else self.not_occ_param_name
        if current:
            return current
        law = self._direction_law(direction)
        if law is not None:
            return [f"{direction}_{law.param_field}"]
        return current

    def _default_direction_params(self, direction):
        """Return the per-order parameter values of ``direction``.

        Called only when fewer values than targets were provided
        (mirrors the historical padding hook call sites). Native rule:
        strict — the values come from the law spec vector, a scalar
        being only meaningful for a single-target mode; anything else
        must be explicit (no silent padding).
        """
        current = self.occ_param if direction == "occ" else self.not_occ_param
        law = self._direction_law(direction)
        order_max = len(self.targets)
        if law is not None and not any(current):
            values = law.values()
            if len(values) == order_max:
                return values
            if len(values) == 1 and order_max >= 1:
                if order_max == 1:
                    return values
                raise ValueError(
                    f"Mode '{self.mode_name}': "
                    f"{'occ_law' if direction == 'occ' else 'not_occ_law'} "
                    f"provides a scalar parameter but the mode has "
                    f"{order_max} targets. Provide the full per-order "
                    f"vector (explicit 0 for inactive orders — no silent "
                    f"padding)."
                )
            raise ValueError(
                f"Mode '{self.mode_name}': "
                f"{'occ_law' if direction == 'occ' else 'not_occ_law'} "
                f"vector has {len(values)} entries but the mode has "
                f"{order_max} targets (strict length, no silent padding)."
            )
        raise ValueError(
            f"Mode '{self.mode_name}': {len(current)} {direction} "
            f"parameter(s) provided for {order_max} targets, and no law "
            f"spec to derive the missing ones (no silent padding). "
            f"Provide {direction}_law or explicit {direction}_param values."
        )

    def _is_direction_law_active(self, direction, params):
        """Whether the ``direction`` law is active for one CC order.

        ``params`` is the ``{base_name: variable}`` dict of that order.
        Native rule: delegate to the law spec (exp active iff rate > 0;
        delay and inst always active). Without a law spec: active.
        """
        law = self._direction_law(direction)
        if law is None:
            return True
        param_names = (
            self.occ_param_name if direction == "occ" else self.not_occ_param_name
        )
        if not param_names:
            return True
        return law.is_active_value(params[param_names[0]].value())

    def _direction_law_bkd(self, direction, params):
        """Return the backend law dict of ``direction`` for one order."""
        law = self._require_direction_law(direction)
        param_names = (
            self.occ_param_name if direction == "occ" else self.not_occ_param_name
        )
        return law.to_bkd_law(params[param_names[0]])

    def _direction_cond(self, direction, target_comps, param=None, **kwrds):
        """Compile the ``direction`` condition into a zero-arg callable.

        Native semantics (shared by both directions — historically
        duplicated in ``get_failure_cond`` / ``get_repair_cond``):
        structured trees are resolved per target and ANDed across
        targets; callables pass through; other values are truthy
        constants.
        """
        cond_spec = self.occ_cond if direction == "occ" else self.not_occ_cond

        cond_sanitized = sanitize_cond_format(cond_spec)

        if isinstance(cond_spec, list):

            cond_bis_list = [
                prepare_attr_tree(
                    cond_sanitized,
                    obj_default=comp,
                    system=self.system(),
                )
                for comp in target_comps
            ]

            def direction_cond_fun():
                return all(
                    [
                        self.cond_outer_logic(
                            [
                                self.cond_inner_logic(
                                    [
                                        get_operator_function(c_inner.get("ope", "=="))(
                                            getattr(
                                                c_inner["attr"],
                                                c_inner["attr_val_name"],
                                            )(),
                                            c_inner["value"],
                                        )
                                        for c_inner in c_outer
                                    ]
                                )
                                for c_outer in cond_bis_cur
                            ]
                        )
                        for cond_bis_cur in cond_bis_list
                    ]
                )

            return direction_cond_fun

        if callable(cond_spec):
            return cond_spec

        def direction_cond_const():
            return cond_spec

        return direction_cond_const

    def _validate_trans_effects(self):
        """Reject trans-based effects on unsupported configurations.

        Native mirror of the historical validation (level+pulse overlap,
        behaviours without a symmetric edge pair, CCF order > 1) with
        engine vocabulary. The façades override this to keep the
        historical messages verbatim (they are pinned by tests).
        """
        if not (self.occ_effects_trans or self.not_occ_effects_trans):
            return
        level_vars = set(self.occ_effects) | set(self.not_occ_effects)
        trans_vars = set(self.occ_effects_trans) | set(self.not_occ_effects_trans)
        overlap = level_vars & trans_vars
        if overlap:
            raise ValueError(
                f"Mode {self.mode_name!r}: variables {sorted(overlap)} are "
                f"driven by BOTH state-based (occ_effects/not_occ_effects) "
                f"and trans-based (occ_effects_trans/not_occ_effects_trans) "
                f"effects. A level clamp and a one-shot pulse on the same "
                f"variable conflict (the pulse is silently overwritten). "
                f"Use distinct variables."
            )
        if self.behaviour not in ("internal", "external"):
            raise ValueError(
                f"Trans-based effects (occ_effects_trans / "
                f"not_occ_effects_trans) are only supported with "
                f"behaviour='internal' or behaviour='external' for mode "
                f"{self.mode_name!r}, got behaviour={self.behaviour!r}. "
                f"behaviour='external_rep_indep' is a trigger model with no "
                f"symmetric occ/not_occ edge pair to carry a both-pulse "
                f"one-shot effect."
            )
        if len(self.targets) > 1:
            raise ValueError(
                f"Trans-based effects (occ_effects_trans / "
                f"not_occ_effects_trans) are not supported with CCF order "
                f"> 1 (len(targets)={len(self.targets)}) for mode "
                f"{self.mode_name!r} (persistent-gate both-pulse desync "
                f"across combinations) — deferred."
            )

    # ------------------------------------------------------------------
    # Automaton builders
    # ------------------------------------------------------------------

    def _build_mode_automaton(
        self,
        aut_name,
        not_occ_state_name,
        occ_state_name,
        occ_cond,
        not_occ_cond,
        occ_var_params,
        not_occ_var_params,
        occ_effects,
        not_occ_effects,
        not_occ_law,
        occ_effects_trans=None,
        not_occ_effects_trans=None,
    ):
        """Build the automaton for one cc-combination of this mode.

        Extension hook: ``__init__`` calls this once per active
        cc-combination, after having resolved the combination-specific
        names, conditions, parameter variables, effects (records
        format) and return law. The default implementation builds the
        classic two-state occ / not_occ automaton via
        :meth:`add_aut2st`.

        The occ transition is named after the occ state
        (``trans_name_12_fmt="{st2}"``) and the return transition after
        the not_occ state (``trans_name_21_fmt="{st1}"``), so those two
        names are the trans-effect wiring targets below.
        """
        aut = self.add_aut2st(
            name=aut_name,
            st1=not_occ_state_name,
            st2=occ_state_name,
            init_st2=False,
            trans_name_12_fmt="{st2}",
            cond_occ_12=occ_cond,
            occ_law_12=self._direction_law_bkd("occ", occ_var_params),
            occ_interruptible_12=True,
            effects_st2=occ_effects,
            effects_st2_format="records",
            trans_name_21_fmt="{st1}",
            cond_occ_21=not_occ_cond,
            occ_law_21=not_occ_law,
            occ_interruptible_21=True,
            effects_st1=not_occ_effects,
            effects_st1_format="records",
            step=self.step,
        )
        # Trans-based effects: one-shot edge callbacks (no-op when empty).
        self._wire_transition_effects(
            aut,
            occ_state_name,
            occ_effects_trans,
            target_state=occ_state_name,
        )
        self._wire_transition_effects(aut, not_occ_state_name, not_occ_effects_trans)
        return aut

    def _build_target_automaton(
        self, target_name, return_occ_law, occ_effects=None, not_occ_effects=None
    ):
        """Create a synchronized automaton in the target component.

        Args:
            target_name: Name of the target component
            return_occ_law: Occurrence law for the return transition
                - {"cls": "delay", "time": 0} for external behaviour
                - the order-1 law dict for external_rep_indep behaviour
            occ_effects: Effects applied while in the occ state
            not_occ_effects: Effects applied while in the not_occ state
        """
        if occ_effects is None:
            occ_effects = {}
        if not_occ_effects is None:
            not_occ_effects = {}
        target_comp = self.system().component(target_name)

        # Check for name conflict
        existing_aut_names = [aut.basename() for aut in target_comp.automata()]
        if self.mode_name in existing_aut_names:
            raise ValueError(
                f"Target '{target_name}' already has an automaton named "
                f"'{self.mode_name}'. Cannot create external FM automaton."
            )

        ctrl_var = self.ctrl_vars[target_name]

        # Condition to transition to the occ state
        def occ_condition():
            return ctrl_var.value() is True

        # Condition for the return transition
        if self.behaviour == "external":
            # Synchronized with the mode
            def return_condition():
                return ctrl_var.value() is False

        else:  # external_rep_indep
            # Reuse the user's original return condition on this target
            # alone. We pass the order-1 params because the target's
            # return law is the order-1 law — keeps the cond and the law
            # referring to the same parameters.
            return_condition = self._direction_cond(
                "not_occ",
                target_comps=[target_comp],
                param=self.not_occ_var_params_order1,
            )

        final_occ_effects = self._resolve_target_effects(
            target_comp, target_name, occ_effects, kind="failure_effects"
        )
        final_not_occ_effects = self._resolve_target_effects(
            target_comp, target_name, not_occ_effects, kind="repair_effects"
        )

        # Prefix the state and transition names with the mode's name so
        # the target can host several modes in ``external`` /
        # ``external_rep_indep`` mode without colliding on the bare
        # ``occ`` / ``not_occ`` namespace. The resulting sequence trace
        # also disambiguates which mode fired the event (e.g.
        # ``C1.frun__occ`` instead of ``C1.occ``).
        st_not_occ_prefixed = f"{self.mode_name}__{self.not_occ_state}"
        st_occ_prefixed = f"{self.mode_name}__{self.occ_state}"
        target_aut = target_comp.add_aut2st(
            name=self.mode_name,
            st1=st_not_occ_prefixed,
            st2=st_occ_prefixed,
            init_st2=False,
            # ``st1`` / ``st2`` are already prefixed, so the bare ``{st2}``
            # / ``{st1}`` format yields the prefixed transition name.
            trans_name_12_fmt="{st2}",
            cond_occ_12=occ_condition,
            occ_law_12={"cls": "delay", "time": 0},  # Always instantaneous
            occ_interruptible_12=True,
            effects_st2=final_occ_effects,
            effects_st2_format="records",
            trans_name_21_fmt="{st1}",
            cond_occ_21=return_condition,
            occ_law_21=return_occ_law,
            occ_interruptible_21=True,
            effects_st1=final_not_occ_effects,
            effects_st1_format="records",
            step=self.step,
        )

        # In external_rep_indep, the mode does NOT reset ctrl_var on its
        # own return (trigger model). The target clears ctrl_var when its
        # automaton transitions back to the resting state. We use a
        # sensitive method on the target's automaton (NOT on the
        # variable) to avoid the cascading re-evaluation that would
        # happen if ctrl_var=False was placed in the state effects
        # (which registers the effect on the variable itself, creating a
        # conflict with the mode.occ effect at simulation start).
        if self.behaviour == "external_rep_indep":
            not_occ_state_bkd = target_aut.get_state_by_name(st_not_occ_prefixed)._bkd

            def reset_ctrl_on_target_return():
                if not_occ_state_bkd.isActive() and ctrl_var.value() is True:
                    ctrl_var.setValue(False)

            target_aut._bkd.addSensitiveMethod(
                f"reset_ctrl__{self.mode_name}__{target_name}",
                reset_ctrl_on_target_return,
            )

    @staticmethod
    def _factorize_target_names(
        targets: list[str],
        rep_char: str = "X",
        ignored_char: tuple = ("_",),
        concat_char: tuple = ("__",),
    ) -> str:
        """
        Creates a factorized name from a list of target component names.

        This utility method generates a compact representation of multiple
        target names by identifying common patterns and replacing differing
        characters with a placeholder. This is particularly useful for modes
        that affect multiple similar components.

        The algorithm works as follows:
        1. If targets have different lengths, concatenate with separator
        2. For same-length targets, compare character by character
        3. Keep common characters, replace differences with rep_char
        4. Ignore specified characters (like underscores) during comparison

        Parameters
        ----------
        targets : list[str]
            List of target component names to factorize
        rep_char : str, optional
            Character to use for differing positions (default: "X")
        ignored_char : tuple, optional
            Characters to ignore during comparison (default: ("_",))
        concat_char : tuple, optional
            Characters to use for concatenation when lengths differ
            (default: ("__",))

        Returns
        -------
        str
            Factorized name representing all targets

        Examples
        --------
        >>> _factorize_target_names(["pump1", "pump2", "pump3"])
        "pumpX"

        >>> _factorize_target_names(["motor_A1", "motor_B1"])
        "motor_X1"

        >>> _factorize_target_names(["component1", "very_long_name"])
        "component1__very_long_name"
        """
        if not targets:
            return ""
        if len(targets) == 1:
            return targets[0]

        first_len = len(targets[0])
        # If targets have different lengths, concatenate them
        if not all(len(t) == first_len for t in targets):
            return concat_char[0].join(targets)

        # Character-by-character comparison for same-length targets
        result_chars = []
        for i in range(first_len):
            ref_char = targets[0][i]

            # Skip ignored characters (keep them as-is)
            if ref_char in ignored_char:
                result_chars.append(ref_char)
                continue

            # Check if character is common across all targets
            is_common = all(t[i] == ref_char for t in targets)

            if is_common:
                result_chars.append(ref_char)
            else:
                result_chars.append(rep_char)

        return "".join(result_chars)


def _always_true():
    return True


class ObjFM(ObjMode2S):
    """
    A component that models failure modes affecting multiple target components.

    Backward-compatible façade over :class:`ObjMode2S`: the historical
    ``failure_*`` / ``repair_*`` vocabulary maps onto the engine's
    ``occ_*`` / ``not_occ_*`` fields, and the engine's template hooks
    delegate to the historical hook protocol (``set_occ_law_failure``,
    ``set_default_failure_param_name``, ``get_failure_cond``,
    ``_build_fm_automaton``, ...) so existing subclasses keep working
    unchanged.

    This class creates automata-based failure modes that can affect one or more
    target components simultaneously. It supports different orders of failure
    (affecting 1, 2, or more components at once) and allows customization of
    failure and repair conditions, parameters, and effects.

    The failure mode creates all possible combinations of target components up
    to the specified order and generates corresponding automata with failure
    and repair transitions. Each automaton is named using customizable prefixes
    to distinguish between different target combinations.

    Failure and Repair Conditions
    ----------------------------
    The failure_cond and repair_cond parameters support multiple formats for
    defining when transitions should occur:

    1. **Boolean values**: Simple True/False conditions
    2. **Callable functions**: Custom Python functions returning boolean values
    3. **Structured conditions**: Lists of dictionaries specifying
       attribute-based conditions

    For structured conditions, the format follows a nested list structure:
    - Outer list: OR logic between elements (controlled by cond_outer_logic)
    - Inner list: AND logic between elements (controlled by cond_inner_logic)
    - Dictionary elements: Individual attribute conditions

    Each dictionary must contain:
    - "attr": Attribute name (string) or attribute object
    - "value": Expected value for comparison
    - "ope": Comparison operator (optional, default: "==")
    - "obj": Component object reference (optional if obj_default is used)

    Attributes
    ----------
    fm_name : str
        The base name of the failure mode
    targets : list[str]
        List of target component names that can be affected by this failure mode
    target_name : str
        Factorized name representing all targets (auto-generated if not provided)
    failure_state : str
        Name of the failure state in the automaton (default: "occ")
    repair_state : str
        Name of the repair state in the automaton (default: "rep")
    failure_effects : dict
        Dictionary mapping flow names to their values when failure occurs
    repair_effects : dict
        Dictionary mapping flow names to their values when repair occurs
    failure_param_name : list[str]
        Names of the failure parameters (e.g., ["lambda"] for exponential)
    repair_param_name : list[str]
        Names of the repair parameters (e.g., ["mu"] for exponential)
    trans_name_prefix : str
        Template string for generating transition/automaton name suffixes
    trans_name_prefix_fun : callable, optional
        Custom function for generating transition/automaton name suffixes
    cond_inner_logic : callable, optional
        Logic function for combining inner condition elements (default: all)
    cond_outer_logic : callable, optional
        Logic function for combining outer condition elements (default: any)

    Examples
    --------
    Basic failure mode with default naming:

    >>> fm = ObjFM(
    ...     fm_name="common_cause",
    ...     targets=["pump1", "pump2"],
    ...     failure_effects={"flow": False},
    ...     repair_effects={"flow": True}
    ... )
    # Creates automata: "common_cause__cc_1_2", "common_cause__cc_1", "common_cause__cc_2"

    See the ObjMode2S engine docstring for the generic surface, and the
    historical examples in the user guide for condition shapes and
    naming customisation (trans_name_prefix / trans_name_prefix_fun).
    """

    #: Restore the historical constructor-kwargs passthrough.
    _engine_strict_kwargs = False

    #: Engine attribute -> historical alias, mirrored by
    #: ``_sync_legacy_aliases()`` at every bridge-hook boundary and at
    #: the end of ``__init__`` (post-construction surface: sequence
    #: auto-discovery and user code read the historical names).
    _GENERIC_TO_LEGACY = {
        "mode_name": "fm_name",
        "occ_state": "failure_state",
        "not_occ_state": "repair_state",
        "occ_cond": "failure_cond",
        "not_occ_cond": "repair_cond",
        "occ_effects": "failure_effects",
        "not_occ_effects": "repair_effects",
        "occ_effects_trans": "failure_effects_trans",
        "not_occ_effects_trans": "repair_effects_trans",
        "occ_param_name": "failure_param_name",
        "not_occ_param_name": "repair_param_name",
        "occ_param": "failure_param",
        "not_occ_param": "repair_param",
        "not_occ_var_params_order1": "repair_var_params_order1",
    }

    def __init__(
        self,
        fm_name,
        targets=None,
        target_name=None,
        behaviour="internal",
        failure_state="occ",
        failure_cond=True,
        failure_effects=None,
        failure_effects_trans=None,
        failure_param_name=None,
        failure_param=None,
        repair_state="rep",
        repair_cond=True,
        repair_effects=None,
        repair_effects_trans=None,
        repair_param_name=None,
        repair_param=None,
        param_name_order_prefix="__{order}_o_{order_max}",
        trans_name_prefix="__cc_{target_comb_u}",
        trans_name_prefix_fun=None,
        drop_inactive_automata=True,
        cond_inner_logic=all,
        cond_outer_logic=any,
        step=None,
        **kwargs,
    ):
        super().__init__(
            fm_name,
            # The engine reserves ``targets=None`` for its self-hosted
            # mode; the façade keeps the historical semantics where
            # ``None`` and ``[]`` are both the silent no-op.
            targets=[] if targets is None else targets,
            target_name=target_name,
            behaviour=behaviour,
            occ_state=failure_state,
            occ_cond=failure_cond,
            occ_effects=failure_effects,
            occ_effects_trans=failure_effects_trans,
            occ_param_name=failure_param_name,
            occ_param=failure_param,
            not_occ_state=repair_state,
            not_occ_cond=repair_cond,
            not_occ_effects=repair_effects,
            not_occ_effects_trans=repair_effects_trans,
            not_occ_param_name=repair_param_name,
            not_occ_param=repair_param,
            param_name_order_prefix=param_name_order_prefix,
            trans_name_prefix=trans_name_prefix,
            trans_name_prefix_fun=trans_name_prefix_fun,
            drop_inactive_automata=drop_inactive_automata,
            cond_inner_logic=cond_inner_logic,
            cond_outer_logic=cond_outer_logic,
            step=step,
            **kwargs,
        )
        self._sync_legacy_aliases()

    def _sync_legacy_aliases(self):
        """Mirror the generic engine attributes onto the historical
        names (only those already set — the engine initialises them
        progressively and the hook protocol pins what is visible at
        each hook)."""
        for generic, legacy in self._GENERIC_TO_LEGACY.items():
            try:
                setattr(self, legacy, getattr(self, generic))
            except AttributeError:
                pass

    # ------------------------------------------------------------------
    # Engine template hooks -> historical hook protocol bridges.
    # Every bridge starts by syncing the legacy aliases so the
    # historical hooks see the attributes they have always seen, and
    # returns/mirrors back the values legacy hooks mutate in place.
    # ------------------------------------------------------------------

    def _validate_trans_effects(self):
        self._sync_legacy_aliases()
        self._validate_trans_effects_supported()

    def _default_direction_param_names(self, direction):
        self._sync_legacy_aliases()
        if direction == "occ":
            self.set_default_failure_param_name()
            return self.failure_param_name
        self.set_default_repair_param_name()
        return self.repair_param_name

    def _default_direction_params(self, direction):
        self._sync_legacy_aliases()
        if direction == "occ":
            self.set_default_failure_param()
            return self.failure_param
        self.set_default_repair_param()
        return self.repair_param

    def _is_direction_law_active(self, direction, params):
        if direction == "occ":
            return self.is_occ_law_failure_active(params)
        return self.is_occ_law_repair_active(params)

    def _direction_law_bkd(self, direction, params):
        if direction == "occ":
            return self.set_occ_law_failure(params)
        return self.set_occ_law_repair(params)

    def _direction_cond(self, direction, target_comps, param=None, **kwrds):
        self._sync_legacy_aliases()
        if direction == "occ":
            return self.get_failure_cond(
                target_comps=target_comps, param=param, **kwrds
            )
        return self.get_repair_cond(target_comps=target_comps, param=param, **kwrds)

    def _build_mode_automaton(
        self,
        aut_name,
        not_occ_state_name,
        occ_state_name,
        occ_cond,
        not_occ_cond,
        occ_var_params,
        not_occ_var_params,
        occ_effects,
        not_occ_effects,
        not_occ_law,
        occ_effects_trans=None,
        not_occ_effects_trans=None,
    ):
        # Only forward the trans-effect kwargs when non-empty, so a
        # third-party ObjFM subclass that overrides _build_fm_automaton
        # with the pre-feature signature keeps working as long as it
        # never opts into trans effects (it would otherwise raise
        # TypeError on unexpected kwargs). With the CCF guard in
        # _validate_trans_effects_supported these lists are non-empty
        # only for single-target internal or external FMs.
        trans_kwargs = (
            {
                "failure_effects_trans": occ_effects_trans,
                "repair_effects_trans": not_occ_effects_trans,
            }
            if (occ_effects_trans or not_occ_effects_trans)
            else {}
        )
        return self._build_fm_automaton(
            aut_name=aut_name,
            repair_state_name=not_occ_state_name,
            failure_state_name=occ_state_name,
            failure_cond=occ_cond,
            repair_cond=not_occ_cond,
            failure_var_params=occ_var_params,
            repair_var_params=not_occ_var_params,
            failure_effects=occ_effects,
            repair_effects=not_occ_effects,
            repair_law=not_occ_law,
            **trans_kwargs,
        )

    def _build_target_automaton(
        self, target_name, return_occ_law, occ_effects=None, not_occ_effects=None
    ):
        self._sync_legacy_aliases()
        return self._create_target_automaton(
            target_name,
            return_occ_law,
            failure_effects=occ_effects,
            repair_effects=not_occ_effects,
        )

    # ------------------------------------------------------------------
    # Historical hook protocol (public extension surface — kept
    # verbatim; subclasses override these).
    # ------------------------------------------------------------------

    def _build_fm_automaton(
        self,
        aut_name,
        repair_state_name,
        failure_state_name,
        failure_cond,
        repair_cond,
        failure_var_params,
        repair_var_params,
        failure_effects,
        repair_effects,
        repair_law,
        failure_effects_trans=None,
        repair_effects_trans=None,
    ):
        """Build the automaton for one cc-combination of this failure mode.

        Extension hook: called once per active cc-combination, after the
        combination-specific names, conditions, parameter variables,
        effects (records format) and repair law are resolved. The
        default implementation builds the classic two-state occ/rep
        automaton (the exact behaviour of ``ObjFMExp`` / ``ObjFMDelay``)
        through the engine.

        Subclasses whose occurrence model does not fit a two-state
        single-target automaton (e.g. :class:`ObjFMInst` and its 3-state
        probabilistic-branching automaton) override this method. They
        must return the built :class:`PycAutomaton` (already registered
        in ``self.automata_d``) whose ``failure_state_name`` state is
        queryable by name — the external behaviours rely on it.

        ``failure_effects_trans`` / ``repair_effects_trans`` (records
        format) are trans-based (mode="trans_based") effects wired on
        the occ / rep transition edge — fired once per crossing —
        instead of clamped on the state.
        """
        # Qualified call: the engine implementation, not the façade
        # override above (a subclass overriding BOTH hooks must not
        # recurse).
        return ObjMode2S._build_mode_automaton(
            self,
            aut_name=aut_name,
            not_occ_state_name=repair_state_name,
            occ_state_name=failure_state_name,
            occ_cond=failure_cond,
            not_occ_cond=repair_cond,
            occ_var_params=failure_var_params,
            not_occ_var_params=repair_var_params,
            occ_effects=failure_effects,
            not_occ_effects=repair_effects,
            not_occ_law=repair_law,
            occ_effects_trans=failure_effects_trans,
            not_occ_effects_trans=repair_effects_trans,
        )

    def _validate_trans_effects_supported(self):
        """Reject trans-based effects on behaviours that cannot host a
        one-shot edge callback correctly.

        Supported: ``internal`` (edge callback on the FM's own occ / rep
        transition, target == carrier) and ``external`` (same edge callback,
        but writing the *target* component's persistent gate once per crossing,
        a both-pulse inter-component effect; the level effect stays with the
        centralised ``ctrl_vars`` sensitive method).

        Rejected:

        - Same variable driven by BOTH a level (state) effect and a
          trans-based (pulse) effect: the maintained level clamp re-applies
          on every fixpoint pass while the source state is active and silently
          overwrites the one-shot pulse (in external the target's state clamp
          is still active at the ObjFM rep instant, so a CLEAR pulse is lost
          and the gate stays stuck). Checked first, for BOTH behaviours, so
          internal and external share one semantics.
        - ``external_rep_indep``: trigger model whose repair is an
          instantaneous ``delay(0)`` with independent target self-repair, so
          it has no symmetric occ / rep edge pair to carry a both-pulse.
        - CCF (``len(targets) > 1``): the 2^N-1 combination automata share
          each target's persistent gate, so one combination's CLEAR on rep
          would reset the gate while another is still in occ on the same
          target (both-pulse desync across combinations).
        - ``ObjFMInst`` (overridden below): its draw transition wires branch
          effects through a start method that would fire the one-shot effect
          at t=0.
        """
        if not (self.failure_effects_trans or self.repair_effects_trans):
            return
        # A level clamp and a one-shot pulse on the SAME variable conflict: the
        # clamp wins (re-applied every fixpoint pass while its state is active)
        # and the pulse is silently overwritten. This produces a divergent,
        # undiagnosed result between internal and external, so reject it upfront
        # for every behaviour rather than let it slip through.
        level_vars = set(self.failure_effects) | set(self.repair_effects)
        trans_vars = set(self.failure_effects_trans) | set(self.repair_effects_trans)
        overlap = level_vars & trans_vars
        if overlap:
            raise ValueError(
                f"FM {self.fm_name!r}: variables {sorted(overlap)} are driven by "
                f"BOTH state-based (failure_effects/repair_effects) and "
                f"trans-based (failure_effects_trans/repair_effects_trans) "
                f"effects. A level clamp and a one-shot pulse on the same "
                f"variable conflict (the pulse is silently overwritten). Use "
                f"distinct variables."
            )
        if self.behaviour not in ("internal", "external"):
            raise ValueError(
                f"Trans-based effects (failure_effects_trans / "
                f"repair_effects_trans) are only supported with "
                f"behaviour='internal' or behaviour='external' for FM "
                f"{self.fm_name!r}, got behaviour={self.behaviour!r}. "
                f"behaviour='external_rep_indep' is a trigger model whose "
                f"repair is an instantaneous delay(0) with independent target "
                f"self-repair, so it has no symmetric occ/rep edge pair to "
                f"carry a both-pulse one-shot effect."
            )
        if len(self.targets) > 1:
            raise ValueError(
                f"Trans-based effects (failure_effects_trans / "
                f"repair_effects_trans) are not supported with CCF order > 1 "
                f"(len(targets)={len(self.targets)}) for FM {self.fm_name!r} "
                f"(persistent-gate both-pulse desync across combinations): "
                f"the 2^N-1 combination automata share each target's "
                f"persistent gate, so one combination's CLEAR on rep would "
                f"reset the gate while another combination is still in occ "
                f"on the same target — deferred (needs a cross-automaton "
                f"guard with its own MC-symmetry phase)."
            )

    def _create_target_automaton(
        self, target_name, repair_occ_law, failure_effects=None, repair_effects=None
    ):
        """Create a synchronized automaton in the target component.

        Extension hook (historical signature). Args:
            target_name: Name of the target component
            repair_occ_law: Occurrence law for the repair transition
                - {"cls": "delay", "time": 0} for external behaviour
                - {"cls": "exp", "rate": mu_var} for external_rep_indep
            failure_effects: Effects applied when failure occurs
            repair_effects: Effects applied when repair occurs
        """
        return ObjMode2S._build_target_automaton(
            self,
            target_name,
            repair_occ_law,
            occ_effects=failure_effects,
            not_occ_effects=repair_effects,
        )

    def get_failure_cond(self, target_comps, **kwrds):
        # Same compilation as the engine's generic direction condition
        # (the historical duplicated bodies were deduplicated there).
        return ObjMode2S._direction_cond(self, "occ", target_comps)

    def get_repair_cond(self, target_comps, **kwrds):
        return ObjMode2S._direction_cond(self, "not_occ", target_comps)

    # TO BE OVERLOADED IF NEEDED
    def set_default_failure_param_name(self):
        pass

    # TO BE OVERLOADED IF NEEDED
    def set_default_repair_param_name(self):
        pass

    def is_occ_law_failure_active(self, params):
        return True

    def is_occ_law_repair_active(self, params):
        return True


class ObjFMExp(ObjFM):

    def set_default_failure_param_name(self):
        if not self.failure_param_name:
            self.failure_param_name = ["lambda"]

    def set_default_repair_param_name(self):
        if not self.repair_param_name:
            self.repair_param_name = ["mu"]

    def set_default_failure_param(self):
        failure_param_diff = len(self.targets) - len(self.failure_param)
        if failure_param_diff > 0:
            self.failure_param += [(0,)] * failure_param_diff

    def set_default_repair_param(self):
        repair_param_diff = len(self.targets) - len(self.repair_param)
        if repair_param_diff > 0:
            self.repair_param += [(0,)] * repair_param_diff

    def is_occ_law_failure_active(self, params):
        return params[self.failure_param_name[0]].value() > 0

    def is_occ_law_repair_active(self, params):
        return params[self.repair_param_name[0]].value() > 0

    def set_occ_law_failure(self, params):
        return {"cls": "exp", "rate": params[self.failure_param_name[0]]}

    def set_occ_law_repair(self, params):
        return {"cls": "exp", "rate": params[self.repair_param_name[0]]}

    def get_failure_cond(self, target_comps, param, **kwrds):

        parent_failure_cond_fun = super().get_failure_cond(target_comps)

        def failure_cond_fun():
            return (
                param[self.failure_param_name[0]].bValue() and parent_failure_cond_fun()
            )

        return failure_cond_fun

    def get_repair_cond(self, target_comps, param, **kwrds):

        parent_repair_cond_fun = super().get_repair_cond(target_comps)

        def repair_cond_fun():
            return (
                param[self.repair_param_name[0]].bValue() and parent_repair_cond_fun()
            )

        return repair_cond_fun


class ObjFMDelay(ObjFM):

    def set_default_failure_param_name(self):
        if not self.failure_param_name:
            self.failure_param_name = ["ttf"]

    def set_default_repair_param_name(self):
        if not self.repair_param_name:
            self.repair_param_name = ["ttr"]

    def set_default_failure_param(self):
        failure_param_diff = len(self.targets) - len(self.failure_param)
        if failure_param_diff > 0:
            self.failure_param += [(0,)] * failure_param_diff

    def set_default_repair_param(self):
        repair_param_diff = len(self.targets) - len(self.repair_param)
        if repair_param_diff > 0:
            self.repair_param += [(0,)] * repair_param_diff

    def set_occ_law_failure(self, params):
        return {"cls": "delay", "time": params[self.failure_param_name[0]]}

    def set_occ_law_repair(self, params):
        return {"cls": "delay", "time": params[self.repair_param_name[0]]}


class ObjFMInst(ObjFM):
    """On-demand failure mode: one Bernoulli draw per demand front.

    Models a failure *on solicitation*: whenever the demand
    (``failure_cond``) becomes true, the mode fails with probability
    ``gamma`` — instantaneously, via a PyCATSHOO ``inst`` law with
    probabilistic branching. The repair transition stays governed by an
    **exponential** law (``mu``), exactly like ``ObjFMExp``.

    Automaton (3 states, per cc-combination)::

                     inst, guard = failure_cond
        rep ──────────────────────────────────────► occ      (prob gamma)
         ▲  └───────────────────────────────────► not_occ   (prob 1-gamma)
         │                                            │
         │   exp(mu), guard = repair_cond             │ inst p=1,
         └────────────────────────── occ ◄────────────┘ guard = NOT failure_cond

    Design (ADR 2026-07-05, cod3s-specs):

    * ``not_occ`` absorbs the demand front: while ``failure_cond`` stays
      true the automaton waits there (no re-draw — anti-Zeno). It
      returns to ``rep`` through an **inst p=1** transition guarded by
      ``NOT failure_cond``: inst transitions drain before any timed
      transition of the same instant, so a demand that falls and rises
      at the same simulated date is re-armed and drawn, not missed.
      One front = one draw.
    * If the repair completes while the demand still holds, the
      automaton re-draws immediately (the repaired component is
      re-solicited). Model "one failure per demand, never repaired
      within the demand" with ``mu = 0``.
    * CC combinations follow the ``ObjFM`` structure unchanged:
      ``failure_param = [gamma_1, ..., gamma_n]`` (probability of the
      order-k event on solicitation, symmetric to ``lambda_k``). Each
      combination automaton draws **independently** on a shared front;
      distinct subsets may both land in ``occ`` at the same instant
      (probability = product of gammas, second order) — same
      independence structure as the exp CCF processes.
    * Sequence monitoring: the draw transition is named after the
      failure state (``occ`` [+ ``__cc_`` suffix]) so recorded events
      match the ObjFMExp convention. The success branch and the re-arm
      transition are masked out of monitoring via
      ``setMonitoredOutStateMask`` — see :meth:`reapply_monitor_masks`.
    """

    #: Out-state mask that matches no state — used to fully silence the
    #: re-arm transition in the sequence monitoring ("#" prefix = regex,
    #: "$^" matches nothing).
    _NEVER_MATCH_MASK = "#$^"

    def __init__(self, *args, **kwargs):
        # Populated by _build_fm_automaton (called from super().__init__).
        self._monitor_masks = []
        super().__init__(*args, **kwargs)

    def set_default_failure_param_name(self):
        if not self.failure_param_name:
            self.failure_param_name = ["gamma"]

    def set_default_repair_param_name(self):
        if not self.repair_param_name:
            self.repair_param_name = ["mu"]

    def set_default_failure_param(self):
        failure_param_diff = len(self.targets) - len(self.failure_param)
        if failure_param_diff > 0:
            self.failure_param += [(0,)] * failure_param_diff

    def set_default_repair_param(self):
        repair_param_diff = len(self.targets) - len(self.repair_param)
        if repair_param_diff > 0:
            self.repair_param += [(0,)] * repair_param_diff

    def is_occ_law_failure_active(self, params):
        return params[self.failure_param_name[0]].value() > 0

    def is_occ_law_repair_active(self, params):
        return params[self.repair_param_name[0]].value() > 0

    def set_occ_law_failure(self, params):
        raise NotImplementedError(
            "ObjFMInst builds its draw transition directly in "
            "_build_fm_automaton (inst law + probabilistic branching); "
            "set_occ_law_failure has no meaning here."
        )

    def set_occ_law_repair(self, params):
        # Repair stays exponential — never inst (ADR decision).
        return {"cls": "exp", "rate": params[self.repair_param_name[0]]}

    def get_failure_cond(self, target_comps, param, **kwrds):
        parent_failure_cond_fun = super().get_failure_cond(target_comps)

        def failure_cond_fun():
            return (
                param[self.failure_param_name[0]].bValue() and parent_failure_cond_fun()
            )

        return failure_cond_fun

    def get_repair_cond(self, target_comps, param, **kwrds):
        parent_repair_cond_fun = super().get_repair_cond(target_comps)

        def repair_cond_fun():
            return (
                param[self.repair_param_name[0]].bValue() and parent_repair_cond_fun()
            )

        return repair_cond_fun

    def _validate_trans_effects_supported(self):
        """Reject trans-based effects for ObjFMInst (on-demand law).

        The inst draw transition wires its branch effects through a start
        method (fires at t=0), so a one-shot trans-based effect has no
        correct home here (MVP). Overrides ``ObjFM`` to reject regardless
        of ``behaviour``.
        """
        if self.failure_effects_trans or self.repair_effects_trans:
            raise ValueError(
                f"Trans-based effects (failure_effects_trans / "
                f"repair_effects_trans) are not supported for ObjFMInst "
                f"(on-demand law) for FM {self.fm_name!r}. The inst draw "
                f"transition wires its branch effects with a start method "
                f"that would fire the one-shot effect at t=0. Use "
                f"behaviour='internal' with an exp/delay law."
            )

    def _build_fm_automaton(
        self,
        aut_name,
        repair_state_name,
        failure_state_name,
        failure_cond,
        repair_cond,
        failure_var_params,
        repair_var_params,
        failure_effects,
        repair_effects,
        repair_law,
    ):
        # No trans-effect kwargs here: trans-based effects are rejected
        # upfront for ObjFMInst (_validate_trans_effects_supported), so the
        # shared call-site never forwards them (pre-feature signature kept,
        # which also exercises the subclass-compat path of that call-site).
        gamma_var = failure_var_params[self.failure_param_name[0]]
        not_occ_state_name = f"not_{failure_state_name}"
        # Transition names: the draw is named after the failure state
        # (sequence-trace convention shared with ObjFMExp: NAME == ST on
        # the failure branch); the repair after the repair state; the
        # re-arm after the not_occ state (its source) since naming it
        # "rep" would collide with the repair transition.
        draw_name = failure_state_name
        rearm_name = not_occ_state_name
        repair_name = repair_state_name

        aut = self.add_automaton(
            name=aut_name,
            states=[repair_state_name, failure_state_name, not_occ_state_name],
            init_state=repair_state_name,
            transitions=[
                {
                    "name": draw_name,
                    "source": repair_state_name,
                    # Model probs are display/serialization floats; the
                    # backend law parameter is re-bound to the gamma
                    # *variable* right after update_bkd (below) so that
                    # runtime parameter overrides keep working, exactly
                    # like ObjFMExp binds its law to the lambda variable.
                    "target": [
                        {
                            "state": failure_state_name,
                            "prob": float(gamma_var.value()),
                        },
                        # Complement branch (1 - gamma).
                        {"state": not_occ_state_name},
                    ],
                },
                {
                    "name": rearm_name,
                    "source": not_occ_state_name,
                    "target": repair_state_name,
                    # inst p=1 (single target): drains with priority over
                    # timed transitions at the same instant — a same-date
                    # fall-and-rise of the demand is re-armed and drawn
                    # instead of being missed (delay(0) would go through
                    # the timed queue where same-date ordering is
                    # arbitrary and the guard could cancel the return).
                    "occ_law": {"cls": "inst", "probs": [1]},
                },
                {
                    "name": repair_name,
                    "source": failure_state_name,
                    "target": repair_state_name,
                    "occ_law": repair_law,
                },
            ],
        )

        # Conditions (callables compiled by get_failure_cond/get_repair_cond).
        aut.get_transition_by_name(draw_name)._bkd.setCondition(failure_cond)
        aut.get_transition_by_name(repair_name)._bkd.setCondition(repair_cond)

        def rearm_cond():
            return not failure_cond()

        aut.get_transition_by_name(rearm_name)._bkd.setCondition(rearm_cond)

        # Re-bind the draw law's parameter to the gamma variable (the
        # PycAutomaton path baked the float value in).
        draw_bkd = aut.get_transition_by_name(draw_name)._bkd
        draw_bkd.distLaw().setParameter(gamma_var, 0)

        # State-entry effects (records format), mirroring add_aut2st.
        self._wire_state_effects(
            aut, failure_state_name, failure_effects, trans_name=draw_name
        )
        self._wire_state_effects(
            aut, repair_state_name, repair_effects, trans_name=repair_name
        )

        # Sequence-monitoring masks: only the occ branch of the draw is
        # recorded; the re-arm transition is fully silenced. Registered
        # for re-application because ``CSystem.monitorTransition`` (run
        # later, at study time) may reset per-transition masks.
        rearm_bkd = aut.get_transition_by_name(rearm_name)._bkd
        self._monitor_masks.append((draw_bkd, f"#{failure_state_name}$"))
        self._monitor_masks.append((rearm_bkd, self._NEVER_MATCH_MASK))
        self.reapply_monitor_masks()

        return aut

    # ``_wire_state_effects`` is inherited from ``FmWiringMixin``
    # (cod3s/pycatshoo/fm_wiring.py) — same pattern as ``add_aut2st``'s
    # records branch, hosted there because ``add_aut2st`` is structurally
    # two-state and cannot host the 3-state automaton.

    def reapply_monitor_masks(self):
        """(Re-)apply the out-state monitoring masks of this FM.

        Called at construction, and again by the study runner *after*
        ``monitorTransition`` patterns are applied — monitoring a
        transition may reset its out-state mask, and the masks are what
        keeps the success branch (``not_occ``) and the re-arm transition
        out of the recorded sequences.
        """
        for trans_bkd, mask in self._monitor_masks:
            trans_bkd.setMonitoredOutStateMask(mask)
