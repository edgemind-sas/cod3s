import pydantic
import typing
import Pycatshoo as pyc
from ..core import ObjCOD3S

# ANSI color codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
WHITE_BOLD = "\033[1;37m"
RESET = "\033[0m"


class StateModel(ObjCOD3S):
    name: str = pydantic.Field(..., description="State name")
    bkd: typing.Any = pydantic.Field(None, description="Backend handler")


class PycState(StateModel):
    id: str = pydantic.Field(..., description="State id")
    comp_name: str = pydantic.Field(None, description="Parent component name")
    aut_name: str = pydantic.Field(None, description="Parent automaton name")
    is_active: bool = pydantic.Field(None, description="State is active ?")

    @classmethod
    def from_bkd(basecls, bkd):
        state = basecls(
            id=bkd.name(),
            name=bkd.basename(),
            comp_name=bkd.parent().name(),
            aut_name=bkd.automaton().basename(),
            is_active=bkd.isActive(),
            bkd=bkd,
        )

        # aut.transitions = [PycTransition.from_bkd(trans)
        #                    for trans in trans_list_bkd]

        return state


class OccurrenceDistributionModel(ObjCOD3S):
    is_occ_time_deterministic: bool = (
        True  # Indicates if occ time is govern by random distribution (must be overloaded
    )
    bkd: typing.Any = pydantic.Field(None, description="Backend handler")

    # TODO: IS IT STILL USEFULL ?
    @staticmethod
    def get_clsname(**specs):
        clsname = specs.pop("cls")
        clsname = clsname.capitalize() + "OccDistribution"

        return clsname

    def model_dump(self, **kwrds):
        exclude_list = [
            "bkd",
            "is_occ_time_deterministic",
        ]
        if kwrds.get("exclude"):
            [kwrds["exclude"].add(attr) for attr in exclude_list]
        else:
            kwrds["exclude"] = set(exclude_list)

        return super().model_dump(**kwrds)


class StateProbModel(pydantic.BaseModel):
    state: str = pydantic.Field(..., description="State name")
    prob: float = pydantic.Field(..., description="State probability")


class TransitionModel(ObjCOD3S):
    name: str = pydantic.Field(..., description="transition name")
    source: str = pydantic.Field(..., description="Source state name")
    target: str | typing.List[StateProbModel] = pydantic.Field(
        ..., description="Target state name"
    )
    occ_law: pydantic.SerializeAsAny[OccurrenceDistributionModel] = pydantic.Field(
        None, description="Occurrence distribution"
    )
    end_time: typing.Optional[float] = pydantic.Field(
        None, description="Transition end time"
    )
    condition: typing.Any = pydantic.Field(None, description="Transition condition")
    bkd: typing.Any = pydantic.Field(None, description="Backend handler")

    @staticmethod
    def sanitize_occ_law(occ_law_specs):
        if occ_law_specs is None:
            return occ_law_specs

        if not (isinstance(occ_law_specs, OccurrenceDistributionModel)):
            clsname = occ_law_specs.get("cls")
            if clsname:
                clsname = clsname.capitalize() + "OccDistribution"
                occ_law_specs["cls"] = clsname
            else:
                raise AttributeError(
                    "Missing attribute 'cls' in OccurrenceDistributionModel"
                )

            return OccurrenceDistributionModel.from_dict(occ_law_specs)
        else:
            return occ_law_specs

    @pydantic.model_validator(mode="before")
    def check_model(cls, values, **kwargs):
        target = values["target"]
        if isinstance(target, str):
            # This is a timed transition => Must check occ distribution
            if values.get("occ_law") is not None:
                values["occ_law"] = cls.sanitize_occ_law(values["occ_law"])
        else:
            # Case INST distribution
            probs_tot_tmp = sum([st.get("prob", 0) for st in target])
            states_no_prob = [st for st in target if "prob" not in st]
            nb_states_no_prob = len(states_no_prob)
            if nb_states_no_prob > 0:
                probs_comp = (1 - probs_tot_tmp) / nb_states_no_prob
                [st.setdefault("prob", probs_comp) for st in target]
            else:
                for st in target:
                    st["prob"] /= probs_tot_tmp

        return values

    def __repr__(self):
        """Returns a colorful string representation of the transition."""

        # Basic transition info
        result = f"{BLUE}{self.__class__.__name__}{RESET} '{self.name}': "

        # Source state
        result += f"{GREEN}{self.source}{RESET} → "

        # Target state(s)
        if isinstance(self.target, str):
            result += f"{GREEN}{self.target}{RESET}"
            if self.occ_law:
                result += f" {YELLOW}[{self.occ_law}]{RESET}"

        else:
            probs = [f"{st.state}({st.prob:.2f})" for st in self.target]
            result += f"{GREEN}[{' | '.join(probs)}]{RESET}"

        # Optional end time
        if self.end_time is not None:
            result += f" {YELLOW}@ {self.end_time}{RESET}"

        return result

    def __str__(self):
        """Returns a multi-line string representation of the transition."""
        lines = [
            f"{BLUE}{self.__class__.__name__}{RESET} '{self.name}'",
            f"├─ From: {GREEN}{self.source}{RESET}",
        ]

        # Target state(s)
        if isinstance(self.target, str):
            lines.append(f"├─ To:   {GREEN}{self.target}{RESET}")
            if self.occ_law:
                lines.append(f"├─ Law:  {YELLOW}{self.occ_law}{RESET}")
        else:
            lines.append("├─ To:")
            for st in self.target:
                lines.append(
                    f"│  ├─ {GREEN}{st.state}{RESET} ({YELLOW}{st.prob:.2f}{RESET})"
                )

        # Optional end time
        if self.end_time is not None:
            lines.append(f"└─ End:  {YELLOW}{self.end_time}{RESET}")
        else:
            lines[-1] = lines[-1].replace("├", "└")

        return "\n".join(lines)


# class TransitionTimeModel(TransitionModel):
#     target: str = pydantic.Field(..., description="Target state name")
#     occ_law: OccurrenceDistributionModel = pydantic.Field(
#         ..., description="Occurrence distribution"
#     )

#     @pydantic.field_validator("occ_law", mode="before")
#     def check_occ_law(cls, value, values, **kwargs):
#         if not (isinstance(value, OccurrenceDistributionModel)):
#             clsname = value.get("cls")
#             if clsname:
#                 clsname = clsname.capitalize() + "OccDistribution"
#                 value["cls"] = clsname
#             else:
#                 raise AttributeError(
#                     "Missing attribute 'cls' in OccurrenceDistributionModel"
#                 )

#             value = OccurrenceDistributionModel.from_dict(value)
#         return value


# class TransitionInstModel(TransitionModel):
#     target: typing.List[StateProbModel] = pydantic.Field(
#         ..., description="List of target states probability"
#     )


class AutomatonModel(ObjCOD3S):
    name: str = pydantic.Field(..., description="Automaton name")
    states: typing.List[StateModel] = pydantic.Field([], description="State list")
    init_state: str = pydantic.Field(None, description="Init state")
    transitions: typing.List[pydantic.SerializeAsAny[TransitionModel]] = pydantic.Field(
        [], description="Transition list"
    )
    bkd: typing.Any = pydantic.Field(None, description="Backend handler")

    @pydantic.field_validator("states", mode="before")
    def check_states(cls, value, values, **kwargs):
        states_new = []
        for state in value:
            state_new = {"name": state} if isinstance(state, str) else state
            states_new.append(state_new)
        return states_new

    @pydantic.model_validator(mode="after")
    def check_consistency(cls, values):
        states_name_list = [st.name for st in values.states]
        init_state = values.init_state

        if (init_state is not None) and (init_state not in states_name_list):
            raise ValueError(
                f"Init state '{init_state}' not in automaton states list {states_name_list}"
            )

        for trans in values.transitions:
            st_source = trans.source
            if st_source not in states_name_list:
                raise ValueError(
                    f"Transition '{trans.name}' source state '{st_source}' not in automaton states list {states_name_list}"
                )
            st_target = trans.target

            if isinstance(st_target, str):
                # transition is a timed transition
                if st_target not in states_name_list:
                    raise ValueError(
                        f"Transition '{trans.name}' target state '{st_target}' not in automaton states list {states_name_list}"
                    )
            else:
                # transition is an inst transition
                for st in st_target:
                    if st.state not in states_name_list:
                        raise ValueError(
                            f"Transition '{trans.name}' (INST) target state '{st.state}' not in automaton states list {states_name_list}"
                        )

        # pw1, pw2 = values.get('password1'), values.get('password2')
        # if pw1 is not None and pw2 is not None and pw1 != pw2:
        #     raise ValueError('passwords do not match')
        return values

    def get_state_by_name(self, state_name):
        for state in self.states:
            if state.name == state_name:
                return state

        raise ValueError(f"State {state_name} is not part of automaton {self.name}")

    def get_active_state(self):
        active_state_name = self.bkd.currentState().basename()
        state = self.get_state_by_name(active_state_name)

        return state

    def get_transition_by_name(self, name):
        for elt in self.transitions:
            if elt.name == name:
                return elt

        raise ValueError(f"Transition {name} is not part of automaton {self.name}")


class PycOccurrenceDistribution(OccurrenceDistributionModel):
    @classmethod
    def from_bkd(basecls, pyc_occ_law):
        if pyc_occ_law.name() == "delay":
            return DelayOccDistribution(time=pyc_occ_law.parameter(0), bkd=pyc_occ_law)
        elif pyc_occ_law.name() == "exp":
            return ExpOccDistribution(rate=pyc_occ_law.parameter(0), bkd=pyc_occ_law)
        elif pyc_occ_law.name() == "inst":
            if pyc_occ_law.nbParam() >= 1:
                probs = [pyc_occ_law.parameter(i) for i in range(pyc_occ_law.nbParam())]
            else:
                probs = [1]
            return InstOccDistribution(probs=probs, bkd=pyc_occ_law)
        else:
            raise ValueError(
                f"Pycatshoo distribution {pyc_occ_law.name()} is not supported by COD3S"
            )


class DelayOccDistribution(PycOccurrenceDistribution):
    is_occ_time_deterministic: bool = True

    time: typing.Any = pydantic.Field(
        0, description="Delay duration (could be a variable)"
    )

    def to_bkd(self, comp_bkd):
        return pyc.IDistLaw.newLaw(comp_bkd, pyc.TLawType.defer, self.time)

    def __str__(self):
        return f"delay({self.time})"


class ExpOccDistribution(PycOccurrenceDistribution):
    is_occ_time_deterministic: bool = False
    rate: typing.Any = pydantic.Field(
        0, description="Occurrence rate (could be a variable)"
    )

    def to_bkd(self, comp_bkd):
        return pyc.IDistLaw.newLaw(comp_bkd, pyc.TLawType.expo, self.rate)

    def __str__(self):
        return f"exp({self.rate})"


class InstOccDistribution(PycOccurrenceDistribution):
    is_occ_time_deterministic: bool = True

    probs: typing.List[typing.Any] = pydantic.Field(
        [], description="Occurrence probabilité (could be a variable)"
    )

    def to_bkd(self, comp_bkd):
        law = pyc.IDistLaw.newLaw(comp_bkd, pyc.TLawType.inst, 1)
        if len(self.probs) >= 2:
            [law.setParameter(pi, i) for i, pi in enumerate(self.probs[:-1])]
        return law

    def __str__(self):
        return f"inst({self.probs})"


# TO BE IMPLEMENTED
class UniformOccDistribution(PycOccurrenceDistribution):
    is_occ_time_deterministic: bool = False

    min: typing.Any = pydantic.Field(
        0, description="Occurrence min time (could be a variable)"
    )
    max: typing.Any = pydantic.Field(
        0, description="Occurrence max time (could be a variable)"
    )

    def to_bkd(self, comp_bkd):
        return pyc.IDistLaw.newLaw(comp_bkd, pyc.TLawType.uniforme, self.min, self.max)

    def __str__(self):
        return f"unif({self.min}, {self.max})"


class PycTransition(TransitionModel):
    comp_name: str = pydantic.Field(None, description="transition component name")
    comp_classname: str = pydantic.Field(
        None, description="transition component class name"
    )

    is_interruptible: bool = pydantic.Field(
        True,
        description="Indicates if the time to fire the transition is stopped when conditions are not met",
    )

    @classmethod
    def from_bkd(basecls, trans_bkd):
        trans_name = trans_bkd.basename()
        comp_name = trans_bkd.parent().name()
        comp_classname = trans_bkd.parent().className()
        is_interruptible = trans_bkd.interruptible()
        occ_law = PycOccurrenceDistribution.from_bkd(trans_bkd.distLaw())

        if occ_law.is_occ_time_deterministic:
            end_time = (
                trans_bkd.endTime() if trans_bkd.endTime() < float("inf") else None
            )
        else:
            end_time = float("inf")

        state_source_bkd = trans_bkd.startState()
        source = state_source_bkd.basename()

        if isinstance(occ_law, InstOccDistribution):
            target = []
            i = 0
            while tgt := trans_bkd.target(i):
                tgt_spec = {"state": tgt.basename()}
                if len(occ_law.probs) > i:
                    tgt_spec.update({"prob": occ_law.probs[i]})
                target.append(tgt_spec)
                i += 1
        else:
            state_target_bkd = trans_bkd.target(0)
            target = state_target_bkd.basename()

        return basecls(
            name=trans_name,
            comp_name=comp_name,
            comp_classname=comp_classname,
            source=source,
            target=target,
            occ_law=occ_law,
            end_time=end_time,
            is_interruptible=is_interruptible,
            bkd=trans_bkd,
        )

    def update_bkd(self, automaton):
        state_source = automaton.get_state_by_name(self.source)
        self.bkd = state_source.bkd.addTransition(self.name)
        self.bkd.setInterruptible(self.is_interruptible)
        if self.condition is not None:
            self.bkd.setCondition(self.condition)

        if isinstance(self.target, str):
            # The transition is a timed transition
            state_target = automaton.get_state_by_name(self.target)
            self.bkd.addTarget(state_target.bkd)
            if self.occ_law is not None:
                self.bkd.setDistLaw(self.occ_law.to_bkd(self.bkd.parent()))
        else:
            # The transition is an INST transition
            # NOT WORKING: PARAMETERS DOES NOT SEEMED TO BE ASSIGNED...
            probs = []
            for st in self.target:
                state_target = automaton.get_state_by_name(st.state)
                self.bkd.addTarget(state_target.bkd)
                probs.append(st.prob)

            occ_law = InstOccDistribution(probs=probs)
            self.bkd.setDistLaw(occ_law.to_bkd(self.bkd.parent()))

    def model_dump(self, **kwrds):
        exclude_list = [
            "bkd",
        ]
        if kwrds.get("exclude"):
            [kwrds["exclude"].add(attr) for attr in exclude_list]
        else:
            kwrds["exclude"] = set(exclude_list)

        return super().model_dump(**kwrds)

    def __eq__(self, other):
        return (self.comp_name == other.comp_name) and (self.name == other.name)

    def __repr__(self):
        """Returns a colorful string representation of the transition."""
        # Basic transition info with component name
        result = f"{BLUE}{self.__class__.__name__}{RESET} {WHITE_BOLD}{self.comp_name}.{self.name}{RESET}: "

        # Add condition if it exists
        if self.condition is not None:
            result += f"{YELLOW}[{self.condition}]{RESET} "

        # Source state
        result += f"{GREEN}{self.source}{RESET} → "

        # Target state(s)
        if isinstance(self.target, str):
            result += f"{GREEN}{self.target}{RESET}"
            if self.occ_law:
                result += f" {YELLOW}[{self.occ_law}]{RESET}"
            if self.is_interruptible:
                result += f" {YELLOW}[I]{RESET}"
        else:
            probs = [f"{st.state}({st.prob:.2f})" for st in self.target]
            result += f"{GREEN}[{' | '.join(probs)}]{RESET}"

        # Optional end time
        if self.end_time is not None:
            result += f" {YELLOW}@ {self.end_time}{RESET}"

        return result

    def __str__(self):
        """Returns a multi-line string representation of the transition."""
        lines = [
            f"{BLUE}{self.__class__.__name__}{RESET} {WHITE_BOLD}{self.comp_name}.{self.name}{RESET}",
        ]

        # Add condition if it exists
        if self.condition is not None:
            lines.append(f"├─ Condition: {YELLOW}{self.condition}{RESET}")

        lines.append(f"├─ From: {GREEN}{self.source}{RESET}")

        # Target state(s)
        if isinstance(self.target, str):
            lines.append(f"├─ To:   {GREEN}{self.target}{RESET}")
            if self.occ_law:
                lines.append(f"├─ Law:  {YELLOW}{self.occ_law}{RESET}")
            lines.append(f"├─ Interruptible: {YELLOW}{self.is_interruptible}{RESET}")
        else:
            lines.append("├─ To:")
            for st in self.target:
                lines.append(
                    f"│  ├─ {GREEN}{st.state}{RESET} ({YELLOW}{st.prob:.2f}{RESET})"
                )

        # Optional end time
        if self.end_time is not None:
            lines.append(f"└─ End:  {YELLOW}{self.end_time}{RESET}")
        else:
            lines[-1] = lines[-1].replace("├", "└")

        return "\n".join(lines)

    # def to_dict(self):

    #     selfd = self.dict(exclude={"bkd"})

    #     selfd["component"] = self.bkd.parent().name()
    #     selfd["occ_law"] = str(self.occ_law)
    #     selfd["occ_planned"] = str(self.bkd.endTime())
    #     #ipdb.set_trace()
    #     return selfd
    #     #selfd["occ_law"] = self.occ_law.str_short()


class PycAutomaton(AutomatonModel):
    # @pydantic.validator('states', pre=True)
    # def check_states(cls, value, values, **kwargs):
    #     ipdb.set_trace()
    #     value = [PycState(**v) for v in value]
    #     return value
    id: str = pydantic.Field(None, description="State id")
    comp_name: str = pydantic.Field(None, description="Parent component name")

    @pydantic.field_validator("transitions", mode="before")
    def check_transitions(cls, value, values, **kwargs):
        value = [PycTransition(**v) for v in value]
        return value

    def set_init_state(self, state):

        if isinstance(state, str):
            st = self.get_state_by_name(state).bkd
        else:
            st = state.bkd

        self.bkd.setInitState(st)

    def update_bkd(self, comp):
        self.bkd = comp.addAutomaton(self.name)
        for state_id, state in enumerate(self.states):
            state.bkd = self.bkd.addState(state.name, state_id)

        if self.init_state is None:
            self.bkd.setInitState(self.states[0].bkd)
        else:
            self.bkd.setInitState(self.get_state_by_name(self.init_state).bkd)

        [trans.update_bkd(automaton=self) for trans in self.transitions]

    @classmethod
    def from_bkd(basecls, bkd):
        aut = basecls(
            id=bkd.name(),
            name=bkd.basename(),
            comp_name=bkd.parent().name(),
            states=[PycState.from_bkd(state) for state in bkd.states()],
            init_state=bkd.initState().basename(),
            bkd=bkd,
        )
        # aut.states = [PycState.from_bkd(state)
        #               for state in bkd.states()]

        # ipdb.set_trace()
        # aut.transitions = [PycTransition.from_bkd(trans)
        #                    for trans in trans_list_bkd]

        return aut

    # name: str = pydantic.Field(..., description="Automaton name")
    # states: typing.List[StateModel] = \
    #     pydantic.Field([], description="State list")
    # transitions: typing.List[TransitionModel] = \
    #     pydantic.Field([], description="Transition list")
    # bkd: typing.Any = pydantic.Field(None, description="Backend handler")
