# ipdb is a debugger (pip install ipdb)

import pydantic
import typing
import pandas as pd
from ..core import ObjCOD3S
from .automaton import PycAutomaton, PycState
import Pycatshoo as pyc
import copy
import re
import colored
import textwrap


class PycVariable(ObjCOD3S):
    id: str = pydantic.Field(..., description="Variable id")
    name: str = pydantic.Field(None, description="Variable name")
    comp_name: str = pydantic.Field(None, description="Component name")
    value_init: typing.Any = pydantic.Field(None, description="Variable init value")
    value_current: typing.Any = pydantic.Field(None, description="Current value")
    bkd: typing.Any = pydantic.Field(None, description="Variable backend handler")

    @classmethod
    def from_bkd(basecls, bkd):
        return basecls(
            id=bkd.name(),
            name=bkd.basename(),
            comp_name=bkd.parent().name(),
            value_init=bkd.initValue(),
            value_current=bkd.value(),
            bkd=bkd,
        )


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
        """Return colored formatting for the class name stresentation."""
        return self.repr__class_name_fmt()

    def str__class_name(self):
        """Return the colored class name stresentation of the component."""
        return self.repr__class_name()

    def str__instance_name_fmt(self):
        """Return colored formatting for the instance name stresentation."""
        return self.repr__instance_name_fmt()

    def str__instance_name(self):
        """Return the colored instance name stresentation of the component."""
        return self.repr__instance_name()

    def str__variables_header(self):
        """Return colored formatting for the instance name stresentation."""
        return "Variables"

    def str__variables_header_fmt(self):
        """Return colored formatting for the instance name stresentation."""
        return f"{colored.attr('bold')}{colored.fg('steel_blue_3')}"

    def str__variables_name_fmt(self):
        """Return colored formatting for the instance name stresentation."""
        return f"{colored.fg('steel_blue')}"

    def str__variables_value_fmt(self):
        """Return colored formatting for the instance name stresentation."""
        return f"{colored.fg('white')}"

    def str__variables(self):
        """Return the colored instance name stresentation of the component."""
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
        """Return colored formatting for the instance name stresentation."""
        return f"{colored.attr('bold')}{colored.fg('cyan')}"

    def str__cnct_header(self):
        """Return colored formatting for the instance name stresentation."""
        return "Connections:"

    def str__cnct_name_fmt(self):
        """Return colored formatting for the instance name stresentation."""
        return f"{colored.fg('white')}"

    def str__cnct_no_cnct_fmt(self):
        """Return colored formatting for the instance name stresentation."""
        return ""

    def str__cnct_no_cnct(self):
        """Return colored formatting for the instance name stresentation."""
        return "no connection"

    def str__cnct_target_name_fmt(self):
        """Return colored formatting for the instance name stresentation."""
        return f"{colored.fg('wheat_1')}"

    def str__cnct_target_attr_fmt(self):
        """Return colored formatting for the instance name stresentation."""
        return f"{colored.fg('white')}"

    def str__cnct(self):
        """Return the colored instance name stresentation of the component."""
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
        """Return colored formatting for the instance name stresentation."""
        return f"{colored.attr('bold')}{colored.fg('cyan')}"

    def str__automata_header(self):
        """Return colored formatting for the instance name stresentation."""
        return "Automata"

    def str__automaton_name_fmt(self):
        """Return colored formatting for the instance name stresentation."""
        return f"{colored.fg('white')}"

    def str__automaton_state_fmt(self):
        """Return colored formatting for the instance name stresentation."""
        return f"{colored.fg('rosy_brown')}"

    def str__automaton(self, aut):
        aut_str = (
            f"{self.str__automaton_name_fmt()}{aut.basename()}{colored.attr('reset')}: "
            f"{self.str__automaton_state_fmt()}{aut.currentState().basename()}{colored.attr('reset')}"
        )
        #    __import__("ipdb").set_trace()

        return aut_str

    def str__automata(self):
        """Return the colored instance name stresentation of the component."""
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
        """Return a string stresentation showing class name and instance name."""
        return (
            f"{self.str__class_name()} {self.str__instance_name()}\n"
            f"{textwrap.indent(self.str__variables(), '  ')}\n\n"
            f"{textwrap.indent(self.str__cnct(), '  ')}\n\n"
            f"{textwrap.indent(self.str__automata(), '  ')}"
        )

    def describe(self):
        # comp = basecls(name=bkd.name(), bkd=bkd)
        # comp.variables = \
        #     [PycVariable.from_bkd(elt) for elt in self.getVariables()]
        # comp.states = \
        #     [PycState.from_bkd(elt) for elt in bkd.getStates()]
        # comp.automata = \
        #     [PycAutomaton.from_bkd(elt) for elt in bkd.getAutomata()]

        return {
            "name": self.name(),
            "cls": self.className(),
            "variables": [
                PycVariable.from_bkd(elt).dict(exclude={"bkd"})
                for elt in self.variables()
            ],
            "states": [
                PycState.from_bkd(elt).dict(exclude={"bkd"}) for elt in self.states()
            ],
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
        ...     st2="open",
        ...     effects_st2={"flow_rate": 100}
        ... )
        """

        st1_name = f"{name}_{st1}"
        # st1_name = f"{st1}"
        st2_name = f"{name}_{st2}"
        # st2_name = f"{st2}"

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
            aut.get_transition_by_name(trans_name_12).bkd.setCondition(cond_occ_12)

        elif isinstance(cond_occ_12, str):
            aut.get_transition_by_name(trans_name_12).bkd.setCondition(
                self.variable(cond_occ_12)
            )
        else:
            raise ValueError(
                f"Condition '{cond_occ_12}' for transition {trans_name_12} not supported"
            )

        # Effects
        st2_bkd = aut.get_state_by_name(st2_name).bkd
        #    var_value_list_12 = self.pat_to_var_value(*effects_12)
        if len(effects_st2) > 0:

            if effects_st2_format == "dict":

                def sensitive_method_st_2():
                    if st2_bkd.isActive():
                        [
                            # getattr(self, var).setValue(value)
                            self.variable(var).setValue(value)
                            for var, value in effects_st2.items()
                        ]

            elif effects_st2_format == "records":

                def sensitive_method_st_2():
                    if st2_bkd.isActive():
                        [
                            # getattr(self, var).setValue(value)
                            elt["var"].setValue(elt["value"])
                            for elt in effects_st2
                        ]

            else:
                raise ValueError(
                    f"effects_st_2_format {effects_st2_format} not supported"
                )
            # setattr(comp.bkd, method_name, sensitive_method)
            sensitive_method_name_st_2 = f"effect__{self.name()}_{name}_{trans_name_12}"
            aut.bkd.addSensitiveMethod(
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
            aut.get_transition_by_name(trans_name_21).bkd.setCondition(cond_occ_21)

        elif isinstance(cond_occ_21, str):
            aut.get_transition_by_name(trans_name_21).bkd.setCondition(
                self.variable(cond_occ_21)
            )
        else:
            raise ValueError(
                f"Condition '{cond_occ_21}' for transition {trans_name_21} not supported"
            )
        # Effects
        # __import__("ipdb").set_trace()

        st1_bkd = aut.get_state_by_name(st1_name).bkd
        # var_value_list_21 = self.pat_to_var_value(*effects_21)
        if len(effects_st1) > 0:
            if effects_st1_format == "dict":

                def sensitive_method_st_1():
                    if st1_bkd.isActive():
                        [
                            # getattr(self, var).setValue(value)
                            self.variable(var).setValue(value)
                            for var, value in effects_st1.items()
                        ]

            elif effects_st1_format == "records":

                def sensitive_method_st_1():
                    if st1_bkd.isActive():
                        [
                            # getattr(self, var).setValue(value)
                            elt["var"].setValue(elt["value"])
                            for elt in effects_st1
                        ]

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

            # setattr(comp.bkd, method_name, sensitive_method)
            sensitive_method_name_st_1 = f"effect__{self.name()}_{name}_{trans_name_21}"
            aut.bkd.addSensitiveMethod(
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
                    aut.get_transition_by_name(trans_name_12).bkd
                )
                pdmp_manager.addWatchedTransition(
                    aut.get_transition_by_name(trans_name_21).bkd
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
        tempo=0,
        event_aut_name="ev",
        occ_state_name="occ",
        not_occ_state_name="not_occ",
        **kwargs,
    ):
        super().__init__(name, **kwargs)

        # self.is_occurred = self.addVariable(
        #     "is_occurred", pyc.TVarType.t_bool, False
        # )

        if isinstance(cond, list):

            def cond_fun():
                return outer_logic(
                    [
                        inner_logic(
                            [
                                c_inner["var"].value() == c_inner["value"]
                                for c_inner in c_outer
                            ]
                        )
                        for c_outer in cond
                    ]
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
            occ_law_12={"cls": "delay", "time": tempo},
            occ_interruptible_12=True,
            trans_name_21_fmt="{st1}",
            cond_occ_21=lambda: not cond,
            occ_law_21={"cls": "delay", "time": 0},
            occ_interruptible_21=True,
        )


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
