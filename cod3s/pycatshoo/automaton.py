import pkg_resources
import pydantic
import typing
import Pycatshoo as pyc
from ..core import ObjCOD3S

installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
if 'ipdb' in installed_pkg:
    import ipdb  # noqa: F401


class StateModel(ObjCOD3S):
    
    name: str = pydantic.Field(..., description="State name")
    bkd: typing.Any = pydantic.Field(None, description="Backend handler")

    
class PycState(StateModel):
    id: str = pydantic.Field(..., description="State id")
    comp_name: str = pydantic.Field(None, description="Parent component name")
    aut_name: str = pydantic.Field(None, description="Parent automaton name")

    @classmethod
    def from_bkd(basecls, bkd):
        state = basecls(
            id=bkd.name(),
            name=bkd.basename(),
            comp_name=bkd.parent().name(),
            aut_name=bkd.automaton().basename(),
            bkd=bkd,
        )

        # aut.transitions = [PycTransition.from_bkd(trans)
        #                    for trans in trans_list_bkd]
       
        return state


class OccurrenceDistributionModel(ObjCOD3S):
    #bkd: typing.Any = pydantic.Field(None, description="Backend handler")
    
    @staticmethod
    def get_clsname(**specs):
        clsname = specs.pop("dist")
        clsname = clsname.capitalize() + "OccDistribution"

        return clsname

class TransitionModel(ObjCOD3S):
    name: str = pydantic.Field(..., description="transition name")
    source: str = pydantic.Field(..., description="Source state name")
    target: str = pydantic.Field(..., description="Target state name")
    occ_law: OccurrenceDistributionModel = \
        pydantic.Field(..., description="Occurrence distribution")
    bkd: typing.Any = pydantic.Field(None, description="Backend handler")

    @pydantic.validator('occ_law', pre=True)
    def check_occ_law(cls, value, values, **kwargs):
        if not (isinstance(value, OccurrenceDistributionModel)):
            clsname = value.get("cls")
            if clsname:
                clsname = clsname.capitalize() + "OccDistribution"
                value["cls"] = clsname
            else:
                raise AttributeError("Missing attribute 'cls' in OccurrenceDistributionModel")

            value = OccurrenceDistributionModel.from_dict(value)
        return value


class AutomatonModel(ObjCOD3S):
    name: str = pydantic.Field(..., description="Automaton name")
    states: typing.List[StateModel] = \
        pydantic.Field([], description="State list")
    init_state: str = \
        pydantic.Field(None, description="Init state")
    transitions: typing.List[TransitionModel] = \
        pydantic.Field([], description="Transition list")
    bkd: typing.Any = pydantic.Field(None, description="Backend handler")

    @pydantic.validator('states', pre=True)
    def check_states(cls, value, values, **kwargs):
        states_new = []
        for state in value:
            state_new = {"name": state} if isinstance(state, str) \
                else state
            states_new.append(state_new)
        return states_new
    
    @pydantic.root_validator(pre=False)
    def check_consistency(cls, values):
        states_name_list = [st.name for st in values.get("states", [])]
        init_state = values.get("init_state")

        if not (init_state is None) and \
           not (init_state in states_name_list):
            raise ValueError(f"Init state '{init_state}' not in automaton states list {states_name_list}")
            
        for trans in values.get("transitions", []):
            st_source = trans.source
            if not (st_source in states_name_list):
                raise ValueError(f"Transition '{trans.name}' source state '{st_source}' not in automaton states list {states_name_list}")
            st_target = trans.target
            if not (st_target in states_name_list):
                raise ValueError(f"Transition '{trans.name}' target state '{st_target}' not in automaton states list {states_name_list}")

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
            return DelayOccDistribution(time=pyc_occ_law.parameter(0),
                                        bkd=pyc_occ_law)
        elif pyc_occ_law.name() == "exp":
            return ExpOccDistribution(rate=pyc_occ_law.parameter(0),
                                      bkd=pyc_occ_law)
        else:
            raise ValueError(f"Pycatshoo distribution {pyc_occ_law.name()} is not supported by COD3S")


class DelayOccDistribution(PycOccurrenceDistribution):
    time: typing.Any = pydantic.Field(0, description="Delay duration (could be a variable)")

    def to_bkd(self, comp_bkd):
        return pyc.IDistLaw.newLaw(
            comp_bkd, pyc.TLawType.defer, self.time)


    def __str__(self):
        return f"delay({self.time})"
    
class ExpOccDistribution(PycOccurrenceDistribution):
    rate: typing.Any = pydantic.Field(0, description="Occurrence rate (could be a variable)")

    def to_bkd(self, comp_bkd):
        return pyc.IDistLaw.newLaw(
            comp_bkd, pyc.TLawType.expo, self.rate)

    def __str__(self):
        return f"exp({self.rate})"

class PycTransition(TransitionModel):

    is_interruptible: bool = \
        pydantic.Field(True, description="Indicates if the time to fire the transition is stopped when conditions are not met")

    @classmethod
    def from_bkd(basecls, trans_bkd):

        trans_name = trans_bkd.basename()

        state_source_bkd = trans_bkd.startState()
        state_target_bkd = trans_bkd.target(0)

        occ_law = PycOccurrenceDistribution.from_bkd(trans_bkd.distLaw())

        return basecls(
            name=trans_name,
            source=state_source_bkd.basename(),
            target=state_target_bkd.basename(),
            occ_law=occ_law,
            is_interruptible=trans_bkd.interruptible(),
            bkd=trans_bkd)

    def update_bkd(self, automaton):
        state_source = automaton.get_state_by_name(self.source)
        self.bkd = \
            state_source.bkd.addTransition(self.name)
        self.bkd.setInterruptible(self.is_interruptible)
        
        state_target = automaton.get_state_by_name(self.target)
        self.bkd.addTarget(state_target.bkd)
        self.bkd.setDistLaw(self.occ_law.to_bkd(self.bkd.parent()))

    def to_dict(self):

        selfd = self.dict(exclude={"bkd"})

        selfd["component"] = self.bkd.parent().name()
        selfd["occ_law"] = str(self.occ_law)
        selfd["occ_planned"] = str(self.bkd.endTime())
        #ipdb.set_trace()
        return selfd
        #selfd["occ_law"] = self.occ_law.str_short()
        

class PycAutomaton(AutomatonModel):

    # @pydantic.validator('states', pre=True)
    # def check_states(cls, value, values, **kwargs):
    #     ipdb.set_trace()
    #     value = [PycState(**v) for v in value]
    #     return value
    id: str = pydantic.Field(None, description="State id")
    comp_name: str = pydantic.Field(None, description="Parent component name")

    
    @pydantic.validator('transitions', pre=True)
    def check_transitions(cls, value, values, **kwargs):
        value = [PycTransition(**v) for v in value]
        return value

    def update_bkd(self, comp):
        self.bkd = comp.addAutomaton(self.name)
        for state_id, state in enumerate(self.states):
            state.bkd = self.bkd.addState(state.name,
                                          state_id)

        if self.init_state is None:
            self.bkd.setInitState(self.states[0].bkd)
        else:
            self.bkd.setInitState(self.get_state_by_name(self.init_state).bkd)
            
        [trans.update_bkd(automaton=self)
         for trans in self.transitions]

    @classmethod
    def from_bkd(basecls, bkd):
        aut = basecls(
            id=bkd.name(),
            name=bkd.basename(),
            comp_name=bkd.parent().name(),
            states=[PycState.from_bkd(state)
                    for state in bkd.states()],
            init_state=bkd.initState().basename(),
            bkd=bkd)
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
