# ipdb is a debugger (pip install ipdb)

import pydantic
import typing
import warnings
from ..core import ObjCOD3S
from ..utils import get_operator_function
from .automaton import PycAutomaton, PycState
from .common import prepare_attr_tree, sanitize_cond_format
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
    def __init__(self, name, label=None, description=None, metadata={}, **kwargs):
        super().__init__(name)

        self.label = name if label is None else label
        self.description = self.label if description is None else description
        self.automata_d = {}

        self.metadata = copy.deepcopy(metadata)

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

    def add_automaton_bis(self, name, states=[], init_state=None):

        aut = self.addAutomaton(name)
        states_dict = {}
        for idx, st_name in enumerate(states):
            st = aut.addState(st_name, idx)
            states_dict[st_name] = st

        if len(states) > 0 and init_state is None:
            aut.setInitState(states_dict[states[0]])
        else:
            aut.setInitState(states_dict[init_state])

        self.automata_d[name] = {"obj": aut, "states": states_dict}

        return aut

    def add_aut2st(
        self,
        name,
        st1="absent",
        st2="present",
        init_st2=False,
        trans_name_12_fmt="{st1}_to_{st2}",
        cond_occ_12=True,
        occ_law_12={"cls": "delay", "time": 0},
        occ_interruptible_12=True,
        effects_st1={},
        effects_st1_format="dict",
        trans_name_21_fmt="{st2}_to_{st1}",
        cond_occ_21=True,
        occ_law_21={"cls": "delay", "time": 0},
        occ_interruptible_21=True,
        effects_st2={},
        effects_st2_format="dict",
        step=None,
        pdmp_managers=[],
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


class ObjFM(PycComponent):
    """
    A component that models failure modes affecting multiple target components.

    This class creates automata-based failure modes that can affect one or more target
    components simultaneously. It supports different orders of failure (affecting 1, 2,
    or more components at once) and allows customization of failure and repair conditions,
    parameters, and effects.

    The failure mode creates all possible combinations of target components up to the
    specified order and generates corresponding automata with failure and repair transitions.
    Each automaton is named using customizable prefixes to distinguish between different
    target combinations.

    Failure and Repair Conditions
    ----------------------------
    The failure_cond and repair_cond parameters support multiple formats for defining
    when transitions should occur:

    1. **Boolean values**: Simple True/False conditions
    2. **Callable functions**: Custom Python functions returning boolean values
    3. **Structured conditions**: Lists of dictionaries specifying attribute-based conditions

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

    Parameters
    ----------
    fm_name : str
        The name of the failure mode
    targets : str or list[str]
        Target component(s) that can be affected by this failure mode
    target_name : str, optional
        Custom name for the target combination. If None, auto-generated from targets
    behaviour : str, optional
        The behaviour of the failure mode. One of "internal", "external", "external_rep_indep".
        (default: "internal")
    failure_state : str, optional
        Name of the failure state (default: "occ")
    failure_cond : bool, callable, or list, optional
        Condition that must be met for failure to occur (default: True)
    failure_effects : dict, optional
        Effects applied when failure occurs (default: {})
    failure_param_name : str or list[str], optional
        Names of failure parameters (default: [])
    failure_param : list, optional
        Values of failure parameters (default: [])
    repair_state : str, optional
        Name of the repair state (default: "rep")
    repair_cond : bool, callable, or list, optional
        Condition that must be met for repair to occur (default: True)
    repair_effects : dict, optional
        Effects applied when repair occurs (default: {})
    repair_param_name : str or list[str], optional
        Names of repair parameters (default: [])
    repair_param : list, optional
        Values of repair parameters (default: [])
    param_name_order_prefix : str, optional
        Template for parameter name suffixes (default: "__{order}_o_{order_max}")
    trans_name_prefix : str, optional
        Template for transition/automaton name suffixes (default: "__cc_{target_comb}")
        Available placeholders: {target_comb}, {target_binary}, {target_comb_u}, {order}, {order_max}
    trans_name_prefix_fun : callable, optional
        Custom function to generate transition/automaton name suffixes. Takes keyword arguments:
        target_set_idx, target_comb, target_binary, target_comb_u, order, order_max
    drop_inactive_automata : bool, optional
        Whether to skip creating automata with inactive occurrence laws (default: True)
    cond_inner_logic : callable, optional
        Logic function for inner condition combinations (default: all)
    cond_outer_logic : callable, optional
        Logic function for outer condition combinations (default: any)
    step : optional
        Step parameter for automaton transitions

    Methods
    -------
    get_failure_cond(target_comps, failure_param)
        Creates a failure condition function for the given target components
    get_repair_cond(target_comps, repair_param)
        Creates a repair condition function for the given target components
    set_default_failure_param_name()
        Sets default failure parameter names (to be overridden in subclasses)
    set_default_repair_param_name()
        Sets default repair parameter names (to be overridden in subclasses)
    _factorize_target_names(targets, rep_char="X", ignored_char=["_"], concat_char=["__"])
        Static method to create factorized names from target lists

    Examples
    --------
    Basic failure mode with default naming:

    >>> fm = ObjFM(
    ...     fm_name="common_cause",
    ...     targets=["pump1", "pump2"],
    ...     failure_effects={"flow": False},
    ...     repair_effects={"flow": True}
    ... )
    # Creates automata: "common_cause__cc_12", "common_cause__cc_1", "common_cause__cc_2"

    Using custom trans_name_prefix with binary representation:

    >>> fm = ObjFM(
    ...     fm_name="failure",
    ...     targets=["comp1", "comp2", "comp3"],
    ...     trans_name_prefix="__bin_{target_binary}",
    ...     failure_effects={"output": False}
    ... )
    # Creates automata like: "failure__bin_110", "failure__bin_101", etc.

    Using custom trans_name_prefix_fun for complex naming:

    >>> def custom_naming(target_set_idx, target_comb, target_binary, **kwargs):
    ...     return f"__custom_{len(target_set_idx)}of{kwargs['order_max']}_{target_binary}"
    ...
    >>> fm = ObjFM(
    ...     fm_name="advanced",
    ...     targets=["A", "B", "C"],
    ...     trans_name_prefix_fun=custom_naming,
    ...     failure_effects={"signal": False}
    ... )
    # Creates automata like: "advanced__custom_2of3_110", "advanced__custom_1of3_100", etc.

    Using underscore-separated target combinations:

    >>> fm = ObjFM(
    ...     fm_name="mode",
    ...     targets=["unit1", "unit2", "unit3"],
    ...     trans_name_prefix="__targets_{target_comb_u}",
    ...     failure_effects={"active": False}
    ... )
    # Creates automata like: "mode__targets_1_2", "mode__targets_2_3", etc.

    Failure condition examples:

    Simple boolean condition:
    >>> fm = ObjFM(
    ...     fm_name="simple_failure",
    ...     targets=["pump1"],
    ...     failure_cond=True,  # Always ready to fail
    ...     repair_cond=False   # Never repairs automatically
    ... )

    Custom function condition:
    >>> def custom_failure_condition():
    ...     return system_pressure > 100 and temperature < 50
    ...
    >>> fm = ObjFM(
    ...     fm_name="pressure_failure",
    ...     targets=["valve1"],
    ...     failure_cond=custom_failure_condition
    ... )

    Structured attribute-based conditions:
    >>> # Single condition: fail when pressure >= 100
    >>> fm = ObjFM(
    ...     fm_name="pressure_fm",
    ...     targets=["pump1"],
    ...     failure_cond=[{"attr": "pressure", "ope": ">=", "value": 100}]
    ... )

    >>> # Multiple conditions with AND logic: fail when pressure >= 100 AND temperature <= 50
    >>> fm = ObjFM(
    ...     fm_name="combined_fm",
    ...     targets=["pump1"],
    ...     failure_cond=[[
    ...         {"attr": "pressure", "ope": ">=", "value": 100},
    ...         {"attr": "temperature", "ope": "<=", "value": 50}
    ...     ]]
    ... )

    >>> # Multiple conditions with OR logic: fail when pressure >= 100 OR temperature <= 50
    >>> fm = ObjFM(
    ...     fm_name="either_fm",
    ...     targets=["pump1"],
    ...     failure_cond=[
    ...         [{"attr": "pressure", "ope": ">=", "value": 100}],
    ...         [{"attr": "temperature", "ope": "<=", "value": 50}]
    ...     ]
    ... )

    >>> # Complex nested conditions: (pressure >= 100 AND temp <= 50) OR (flow <= 0)
    >>> fm = ObjFM(
    ...     fm_name="complex_fm",
    ...     targets=["system1"],
    ...     failure_cond=[
    ...         [
    ...             {"attr": "pressure", "ope": ">=", "value": 100},
    ...             {"attr": "temperature", "ope": "<=", "value": 50}
    ...         ],
    ...         [{"attr": "flow", "ope": "<=", "value": 0}]
    ...     ]
    ... )

    >>> # Using explicit component references:
    >>> fm = ObjFM(
    ...     fm_name="multi_comp_fm",
    ...     targets=["pump1", "pump2"],
    ...     failure_cond=[
    ...         {"attr": "pressure", "obj": "sensor1", "ope": ">=", "value": 100}
    ...     ]
    ... )

    >>> # Custom logic functions:
    >>> fm = ObjFM(
    ...     fm_name="custom_logic_fm",
    ...     targets=["pump1"],
    ...     failure_cond=[[
    ...         {"attr": "sensor1", "ope": ">=", "value": 10},
    ...         {"attr": "sensor2", "ope": ">=", "value": 20}
    ...     ]],
    ...     cond_inner_logic=any,  # OR logic for inner conditions
    ...     cond_outer_logic=all   # AND logic for outer conditions
    ... )
    """

    VALID_BEHAVIOURS = ("internal", "external", "external_rep_indep")

    def __init__(
        self,
        fm_name,
        targets=[],
        target_name=None,
        behaviour="internal",
        failure_state="occ",
        failure_cond=True,
        failure_effects={},
        failure_param_name=[],
        failure_param=[],
        repair_state="rep",
        repair_cond=True,
        repair_effects={},
        repair_param_name=[],
        repair_param=[],
        param_name_order_prefix="__{order}_o_{order_max}",
        trans_name_prefix="__cc_{target_comb}",
        trans_name_prefix_fun=None,
        drop_inactive_automata=True,
        cond_inner_logic=all,
        cond_outer_logic=any,
        step=None,
        **kwargs,
    ):
        # __import__("ipdb").set_trace()

        self.fm_name = fm_name
        self.targets = [targets] if isinstance(targets, str) else targets
        if target_name is None and len(self.targets) == 1:
            target_name = self.targets[0]
        self.target_name = target_name or self._factorize_target_names(targets)

        comp_name = f"{self.target_name}__{self.fm_name}"

        super().__init__(comp_name, **kwargs)
        # if self.system().name() == "003":
        #     __import__("ipdb").set_trace()

        order_max = len(self.targets)

        if behaviour not in self.VALID_BEHAVIOURS:
            raise ValueError(
                f"behaviour must be one of {self.VALID_BEHAVIOURS}, got '{behaviour}'"
            )
        self.behaviour = behaviour

        # Create control variables for external behaviours
        self.ctrl_vars = {}
        if self.behaviour in ("external", "external_rep_indep"):
            for target_name_cur in self.targets:
                ctrl_var_name = f"ctrl_{self.fm_name}_{target_name_cur}"
                ctrl_var = self.addVariable(ctrl_var_name, pyc.TVarType.t_bool, False)
                self.ctrl_vars[target_name_cur] = ctrl_var

        self.failure_cond = copy.deepcopy(failure_cond)
        self.repair_cond = copy.deepcopy(repair_cond)

        self.failure_state = failure_state
        self.repair_state = repair_state

        if isinstance(step, str):
            step_name = step
            step = self.system().step(step_name)
            if step is None:
                raise ValueError(f"Step {step_name} does not exist in this system")
        self.step = step

        self.cond_inner_logic = cond_inner_logic
        self.cond_outer_logic = cond_inner_logic

        self.var_params = {}
        self.failure_effects = copy.deepcopy(failure_effects)
        self.repair_effects = copy.deepcopy(repair_effects)
        self.failure_param_name = (
            [failure_param_name]
            if isinstance(failure_param_name, str)
            else copy.deepcopy(failure_param_name)
        )
        self.set_default_failure_param_name()

        self.repair_param_name = (
            [repair_param_name]
            if isinstance(repair_param_name, str)
            else copy.deepcopy(repair_param_name)
        )
        self.set_default_repair_param_name()

        self.param_name_order_prefix = param_name_order_prefix
        self.trans_name_prefix = trans_name_prefix
        self.trans_name_prefix_fun = trans_name_prefix_fun

        self.failure_param = (
            [failure_param]
            if not isinstance(failure_param, list)
            else copy.deepcopy(failure_param)
        )
        failure_param_diff = len(self.targets) - len(self.failure_param)
        if failure_param_diff > 0:
            self.set_default_failure_param()
        elif failure_param_diff < 0:
            raise ValueError(
                f"Failure mode of order {order_max} but you provide {len(self.failure_param)} failure parameters: {self.failure_param}"
            )

        self.repair_param = (
            [repair_param]
            if not isinstance(repair_param, list)
            else copy.deepcopy(repair_param)
        )
        repair_param_diff = len(self.targets) - len(self.repair_param)
        if repair_param_diff > 0:
            self.set_default_repair_param()
        elif repair_param_diff < 0:
            raise ValueError(
                f"Failure mode of order {order_max} but you provide {len(self.repair_param)} repair parameters: {self.repair_param}"
            )

        # Store order 1 repair params for external_rep_indep behaviour
        self.repair_var_params_order1 = None

        # Track impacting automata for each target in external modes
        self.target_impacting_automata = {t: [] for t in self.targets}

        for order in range(1, order_max + 1):

            failure_param_cur = self.failure_param[order - 1]
            if not isinstance(failure_param_cur, tuple):
                failure_param_cur = (failure_param_cur,)

            failure_var_params_cur = {}
            for failure_param_name_cur, param_value in zip(
                self.failure_param_name, failure_param_cur
            ):
                failure_param_name_cur_tmp = failure_param_name_cur
                if order_max > 1:
                    failure_param_name_cur_tmp += self.param_name_order_prefix.format(
                        order=order, order_max=order_max
                    )

                failure_var_param = self.addVariable(
                    failure_param_name_cur_tmp, pyc.TVarType.t_double, param_value
                )
                failure_var_params_cur.update(
                    {failure_param_name_cur: failure_var_param}
                )

            repair_param_cur = self.repair_param[order - 1]
            if not isinstance(repair_param_cur, tuple):
                repair_param_cur = (repair_param_cur,)

            repair_var_params_cur = {}
            for repair_param_name_cur, param_value in zip(
                self.repair_param_name, repair_param_cur
            ):
                repair_param_name_cur_tmp = repair_param_name_cur
                if order_max > 1:
                    repair_param_name_cur_tmp += self.param_name_order_prefix.format(
                        order=order, order_max=order_max
                    )

                repair_var_param = self.addVariable(
                    repair_param_name_cur_tmp, pyc.TVarType.t_double, param_value
                )
                repair_var_params_cur.update({repair_param_name_cur: repair_var_param})

            # Store order 1 params
            if order == 1:
                self.repair_var_params_order1 = repair_var_params_cur

            if (
                drop_inactive_automata
                and not self.is_occ_law_failure_active(failure_var_params_cur)
                and not self.is_occ_law_repair_active(repair_var_params_cur)
            ):
                continue

            for target_set_idx in itertools.combinations(range(order_max), order):

                # Prepare effects based on behaviour
                if self.behaviour in ("external", "external_rep_indep"):
                    # Centralized management: automata don't set variables directly
                    failure_effects_cur = []
                    repair_effects_cur = []
                else:  # internal behaviour
                    failure_effects_cur = []
                    for var, value in self.failure_effects.items():
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
                            failure_effects_cur.append({"var": comp_var, "value": value})

                    repair_effects_cur = []
                    for var, value in self.repair_effects.items():
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
                            repair_effects_cur.append({"var": comp_var, "value": value})

                failure_state_name_cur = self.failure_state
                repair_state_name_cur = self.repair_state
                aut_name_cur = fm_name
                if order_max > 1:
                    target_comb = "".join([str(i + 1) for i in target_set_idx])
                    target_comb_u = "_".join([str(i + 1) for i in target_set_idx])
                    target_binary = "".join(
                        ["1" if i in target_set_idx else "0" for i in range(order_max)]
                    )
                    if callable(self.trans_name_prefix_fun):
                        trans_name_prefix_cur = self.trans_name_prefix_fun(
                            target_set_idx=target_set_idx,
                            target_comb=target_comb,
                            target_binary=target_binary,
                            target_comb_u=target_comb_u,
                            order=order,
                            order_max=order_max,
                        )
                    else:
                        trans_name_prefix_cur = self.trans_name_prefix.format(
                            target_comb=target_comb,
                            target_binary=target_binary,
                            target_comb_u=target_comb_u,
                            order=order,
                            order_max=order_max,
                        )
                    aut_name_cur += trans_name_prefix_cur
                    failure_state_name_cur += trans_name_prefix_cur
                    repair_state_name_cur += trans_name_prefix_cur

                target_comps_cur = [
                    self.system().component(self.targets[idx]) for idx in target_set_idx
                ]

                failure_cond_cur = self.get_failure_cond(
                    target_comps=target_comps_cur, param=failure_var_params_cur
                )
                repair_cond_cur = self.get_repair_cond(
                    target_comps=target_comps_cur, param=repair_var_params_cur
                )

                if self.behaviour == "external":

                    def make_external_cond(
                        base_cond, targets, fm_name, required_state_name
                    ):
                        def cond():
                            # Check base condition
                            if not base_cond():
                                return False
                            # Check all targets are in required state
                            for t in targets:
                                # We need to access the automaton safely
                                # At simulation time, automata_d should be populated
                                if fm_name not in t.automata_d:
                                    return False
                                st = t.automata_d[fm_name].get_state_by_name(
                                    required_state_name
                                )
                                if not st._bkd.isActive():
                                    return False
                            return True

                        return cond

                    # Failure: targets must be in repair state (available)
                    failure_cond_cur = make_external_cond(
                        failure_cond_cur,
                        target_comps_cur,
                        self.fm_name,
                        self.repair_state,
                    )

                    # Repair: targets must be in failure state (to be repaired)
                    repair_cond_cur = make_external_cond(
                        repair_cond_cur,
                        target_comps_cur,
                        self.fm_name,
                        self.failure_state,
                    )

                # if fm_name_cur == "frun__cc_134":
                # __import__("ipdb").set_trace()
                aut = self.add_aut2st(
                    name=aut_name_cur,
                    st1=repair_state_name_cur,
                    st2=failure_state_name_cur,
                    init_st2=False,
                    trans_name_12_fmt="{st2}",
                    cond_occ_12=failure_cond_cur,
                    occ_law_12=self.set_occ_law_failure(failure_var_params_cur),
                    occ_interruptible_12=True,
                    effects_st2=failure_effects_cur,
                    effects_st2_format="records",
                    trans_name_21_fmt="{st1}",
                    cond_occ_21=repair_cond_cur,
                    occ_law_21=self.set_occ_law_repair(repair_var_params_cur),
                    occ_interruptible_21=True,
                    effects_st1=repair_effects_cur,
                    effects_st1_format="records",
                    step=self.step,
                )

                # Record impacting automata for centralized control
                if self.behaviour in ("external", "external_rep_indep"):
                    for idx in target_set_idx:
                        target_name = self.targets[idx]
                        self.target_impacting_automata[target_name].append(
                            (aut, failure_state_name_cur)
                        )

        # Centralized control for external behaviours
        if self.behaviour in ("external", "external_rep_indep"):
            for (
                target_name,
                impacting_info,
            ) in self.target_impacting_automata.items():
                ctrl_var = self.ctrl_vars[target_name]

                # Create the centralized sensitive method for this target
                def make_ctrl_method(cv, info_list):
                    def ctrl_method():
                        # Determine if any impacting automaton is in failure state
                        should_be_failed = any(
                            a.get_state_by_name(st_name)._bkd.isActive()
                            for a, st_name in info_list
                        )
                        if cv.value() != should_be_failed:
                            cv.setValue(should_be_failed)

                    return ctrl_method

                method = make_ctrl_method(ctrl_var, impacting_info)
                method_name = f"ctrl_sync__{self.name()}_{target_name}"

                # Register to all impacting automata
                for aut, _ in impacting_info:
                    aut._bkd.addSensitiveMethod(method_name, method)

                # Also add as start method to initialize value
                self.addStartMethod(method_name, method)

        # Create automata in target components for external behaviours
        if self.behaviour in ("external", "external_rep_indep"):
            for target_name_cur in self.targets:
                # Create fresh dict each time to avoid mutation issues
                if self.behaviour == "external":
                    repair_occ_law = {"cls": "delay", "time": 0}
                else:  # external_rep_indep
                    repair_occ_law = self.set_occ_law_repair(
                        self.repair_var_params_order1
                    )

                self._create_target_automaton(
                    target_name_cur,
                    repair_occ_law,
                    failure_effects=self.failure_effects,
                    repair_effects=self.repair_effects,
                )

    def _create_target_automaton(
        self, target_name, repair_occ_law, failure_effects={}, repair_effects={}
    ):
        """Create a synchronized automaton in the target component.

        Args:
            target_name: Name of the target component
            repair_occ_law: Occurrence law for the repair transition
                - {"cls": "delay", "time": 0} for external behaviour
                - {"cls": "exp", "rate": mu_var} for external_rep_indep behaviour
            failure_effects: Effects to apply when failure occurs (dict of var_name: value)
            repair_effects: Effects to apply when repair occurs (dict of var_name: value)
        """
        target_comp = self.system().component(target_name)

        # Check for name conflict
        existing_aut_names = [aut.basename() for aut in target_comp.automata()]
        if self.fm_name in existing_aut_names:
            raise ValueError(
                f"Target '{target_name}' already has an automaton named '{self.fm_name}'. "
                f"Cannot create external FM automaton."
            )

        ctrl_var = self.ctrl_vars[target_name]

        # Condition to transition to failure state
        def occ_condition():
            return ctrl_var.value() is True

        # Condition for repair transition
        if self.behaviour == "external":
            # Synchronized with ObjFM
            def rep_condition():
                return ctrl_var.value() is False

        else:  # external_rep_indep
            # TODO: No ! not always ready, in fact we have to use the initial repair_cond be applied the component
            def rep_condition():
                return True

        # Resolve and Prepare failure effects
        final_failure_effects = []
        for var, value in failure_effects.items():
            if hasattr(target_comp, var):
                comp_var = getattr(target_comp, var)
            elif var in [v.basename() for v in target_comp.variables()]:
                comp_var = target_comp.variable(var)
            else:
                continue
            final_failure_effects.append({"var": comp_var, "value": value})

        # Resolve and Prepare repair effects
        final_repair_effects = []
        for var, value in repair_effects.items():
            if hasattr(target_comp, var):
                comp_var = getattr(target_comp, var)
            elif var in [v.basename() for v in target_comp.variables()]:
                comp_var = target_comp.variable(var)
            else:
                continue
            final_repair_effects.append({"var": comp_var, "value": value})

        # Effects when repairing (for external_rep_indep)
        if self.behaviour == "external_rep_indep":
            # Reset ctrl to False to allow new failure
            final_repair_effects.append({"var": ctrl_var, "value": False})

        target_comp.add_aut2st(
            name=self.fm_name,
            st1=self.repair_state,
            st2=self.failure_state,
            init_st2=False,
            trans_name_12_fmt="{st2}",
            cond_occ_12=occ_condition,
            occ_law_12={"cls": "delay", "time": 0},  # Always instantaneous
            occ_interruptible_12=True,
            effects_st2=final_failure_effects,
            effects_st2_format="records",
            trans_name_21_fmt="{st1}",
            cond_occ_21=rep_condition,
            occ_law_21=repair_occ_law,
            occ_interruptible_21=True,
            effects_st1=final_repair_effects,
            effects_st1_format="records",
            step=self.step,
        )

    def get_failure_cond(self, target_comps, **kwrds):

        cond = sanitize_cond_format(self.failure_cond)

        if isinstance(self.failure_cond, list):

            cond_bis_list = [
                prepare_attr_tree(cond, obj_default=comp, system=self.system())
                for comp in target_comps
            ]

            def failure_cond_fun():
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

        elif callable(self.failure_cond):
            failure_cond_fun = self.failure_cond
        else:

            def failure_cond_fun():
                return self.failure_cond

        return failure_cond_fun

    def get_repair_cond(self, target_comps, **kwrds):

        cond = sanitize_cond_format(self.repair_cond)

        if isinstance(self.repair_cond, list):

            cond_bis_list = [
                prepare_attr_tree(cond, obj_default=comp, system=self.system())
                for comp in target_comps
            ]

            def repair_cond_fun():
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

        elif callable(self.repair_cond):
            repair_cond_fun = self.repair_cond
        else:

            def repair_cond_fun():
                return self.repair_cond

        return repair_cond_fun

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

    @staticmethod
    def _factorize_target_names(
        targets: list[str], rep_char="X", ignored_char=["_"], concat_char=["__"]
    ) -> str:
        """
        Creates a factorized name from a list of target component names.

        This utility method generates a compact representation of multiple target
        names by identifying common patterns and replacing differing characters
        with a placeholder. This is particularly useful for failure modes that
        affect multiple similar components.

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
        ignored_char : list[str], optional
            Characters to ignore during comparison (default: ["_"])
        concat_char : list[str], optional
            Characters to use for concatenation when lengths differ (default: ["__"])

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


# class PycComponent(ObjCOD3S):

#     name: str = pydantic.Field(..., description="Component name")
#     variables: typing.List[PycVariable] = pydantic.Field([], description="Variable list")
#     states: typing.List[PycState] = pydantic.Field([], description="state list")
#     automata: typing.List[PycAutomaton] = pydantic.Field([], description="Automata list")
#     bkd: typing.Any = pydantic.Field(None, description="Component backend handler")

#     @pydantic.validator('states', pre=True)
#     def check_states(cls, value, values, **kwargs):
#         value = [PycState(**v) for v in value]
#         return value

#     @pydantic.validator('variables', pre=True)
#     def check_variables(cls, value, values, **kwargs):
#         value = [PycVariable.from_dict(**v) for v in value]
#         return value

#     # @pydantic.validator('automata', pre=True)
#     # def check_automata(cls, value, values, **kwargs):
#     #     value = [PycAutomaton(**v) for v in value]
#     #     return value

#     def get_automaton_by_name(self, name):

#         for elt in self.automata:
#             if elt.name == name:
#                 return elt

#         raise ValueError(f"Automaton {name} is not part of component {self.name}")

#     def get_variable_by_name(self, name):

#         for elt in self.variables:
#             if elt.name == name:
#                 return elt

#         raise ValueError(f"Variable {name} is not part of component {self.name}")


#     @classmethod
#     def from_bkd(basecls, bkd):

#         comp = basecls(name=bkd.name(), bkd=bkd)
#         comp.variables = \
#             [PycVariable.from_bkd(elt) for elt in bkd.getVariables()]
#         comp.states = \
#             [PycState.from_bkd(elt) for elt in bkd.getStates()]
#         comp.automata = \
#             [PycAutomaton.from_bkd(elt) for elt in bkd.getAutomata()]

#         return comp


#     def dict(self, **kwrds):


#     def to_df(self):

#         df_var = pd.DataFrame(
#             [var.dict(exclude={"bkd", "id"})
#              for var in self.variables])

#         df_var["type"] = "VAR"

#         aut_dict_list = []
#         for aut in self.automata:
#             aut_dict = \
#                 aut.dict(exclude={"bkd", "id",
#                                   "states", "transitions",
#                                   "init_state"})

#             aut_dict.update(
#                 value_init=aut.init_state,
#                 value_current=aut.get_active_state().name,
#             )

#             aut_dict_list.append(aut_dict)

#         df_aut = pd.DataFrame(aut_dict_list)
#         df_aut["type"] = "ST"

#         df = pd.concat([df_var, df_aut],
#                        axis=0, ignore_index=True)

#         return df
