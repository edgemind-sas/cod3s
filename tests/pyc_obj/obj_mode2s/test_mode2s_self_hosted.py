"""Native ObjMode2S self-hosted mode (``targets=None``) — the ObjEvent
substrate: one automaton on the component itself, no CC machinery, no
parameter variables, laws baked as literals (zero-overhead contract).
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import ObjMode2S
from cod3s.pycatshoo.system import PycSystem


class Box(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


@pytest.fixture
def pyc_session():
    yield
    cod3s.terminate_session()


def test_self_hosted_grammar_and_zero_overhead(pyc_session):
    system = PycSystem(name="SelfHosted")
    Box("box")
    box = system.comp["box"]
    mode = ObjMode2S(
        mode_name="alarm",
        targets=None,
        occ_law={"cls": "delay", "time": 2.0},
        not_occ_law={"cls": "delay", "time": 0},
        occ_cond=lambda: box.working.value() is False,
        not_occ_cond=lambda: box.working.value() is True,
    )
    # Named directly (no target prefix), single automaton = mode_name.
    assert mode.name() == "alarm"
    assert list(mode.automata_d) == ["alarm"]
    aut = mode.automata_d["alarm"]
    assert [st.name for st in aut.states] == ["not_occ", "occ"]
    assert aut.init_state == "not_occ"
    assert aut.get_transition_by_name("occ").occ_law.time == 2.0
    assert aut.get_transition_by_name("not_occ").occ_law.time == 0
    # Zero-overhead: no parameter variables.
    assert [v.basename() for v in mode.variables()] == []


def test_self_hosted_custom_aut_and_state_names(pyc_session):
    system = PycSystem(name="SelfHostedCustom")
    Box("box")
    mode = ObjMode2S(
        mode_name="alarm",
        targets=None,
        aut_name="ev",
        occ_state="up",
        not_occ_state="down",
        occ_law={"cls": "delay", "time": 0},
        not_occ_law={"cls": "delay", "time": 0},
        occ_cond=False,
    )
    assert list(mode.automata_d) == ["ev"]
    aut = mode.automata_d["ev"]
    assert [st.name for st in aut.states] == ["down", "up"]
    # Transitions named after their destination state (frozen grammar).
    assert aut.get_transition_by_name("up").source == "down"
    assert aut.get_transition_by_name("down").source == "up"


def test_self_hosted_behaviour_drives_cycle(pyc_session):
    """exp/delay self-hosted mode driven through isimu."""
    system = PycSystem(name="SelfHostedCycle")
    Box("box")
    box = system.comp["box"]
    cod3s.ObjFMDelay(
        fm_name="frun",
        targets=["box"],
        failure_param=2.0,
        repair_param=3.0,
        failure_effects={"working": False},
    )
    ObjMode2S(
        mode_name="watch",
        targets=None,
        occ_law={"cls": "delay", "time": 0},
        not_occ_law={"cls": "delay", "time": 0},
        occ_cond=lambda: box.working.value() is False,
        not_occ_cond=lambda: box.working.value() is True,
    )
    aut = system.comp["watch"].automata_d["watch"]

    def fire(name, comp_name):
        trs = system.isimu_fireable_transitions()
        idx = next(
            i
            for i, t in enumerate(trs)
            if t is not None and t.name == name and t.comp_name == comp_name
        )
        system.isimu_set_transition(idx)
        return [t.name for t in system.isimu_step_forward()]

    system.isimu_start()
    fire("occ", "box__frun")
    assert fire("occ", "watch") == ["occ"]
    assert aut.get_state_by_name("occ")._bkd.isActive()
    fire("rep", "box__frun")
    assert fire("not_occ", "watch") == ["not_occ"]
    assert aut.get_state_by_name("not_occ")._bkd.isActive()
    system.isimu_stop()


class TestSelfHostedValidation:
    def _kwargs(self, **overrides):
        base = dict(
            mode_name="alarm",
            targets=None,
            occ_law={"cls": "delay", "time": 0},
            not_occ_law={"cls": "delay", "time": 0},
            occ_cond=False,
        )
        base.update(overrides)
        return base

    def test_behaviour_rejected(self, pyc_session):
        system = PycSystem(name="SHValBehaviour")
        with pytest.raises(ValueError, match="behaviour"):
            ObjMode2S(**self._kwargs(behaviour="external"))

    def test_params_rejected(self, pyc_session):
        system = PycSystem(name="SHValParams")
        with pytest.raises(ValueError, match="zero-overhead"):
            ObjMode2S(**self._kwargs(occ_param=[0.1]))

    def test_effects_rejected(self, pyc_session):
        system = PycSystem(name="SHValEffects")
        with pytest.raises(ValueError, match="effects"):
            ObjMode2S(**self._kwargs(occ_effects={"working": False}))

    def test_inst_law_rejected(self, pyc_session):
        system = PycSystem(name="SHValInst")
        with pytest.raises(ValueError, match="inst"):
            ObjMode2S(**self._kwargs(occ_law={"cls": "inst", "prob": 0.5}))

    def test_law_vector_rejected(self, pyc_session):
        system = PycSystem(name="SHValVector")
        with pytest.raises(ValueError, match="scalar"):
            ObjMode2S(**self._kwargs(occ_law={"cls": "exp", "rate": [0.1, 0.2]}))

    def test_tree_cond_rejected(self, pyc_session):
        system = PycSystem(name="SHValTree")
        with pytest.raises(ValueError, match="callable"):
            ObjMode2S(
                **self._kwargs(
                    occ_cond=[[{"obj": "box", "attr": "working", "value": False}]]
                )
            )

    def test_aut_name_rejected_in_targeted_mode(self, pyc_session):
        system = PycSystem(name="SHValAutName")
        Box("box")
        with pytest.raises(ValueError, match="aut_name"):
            ObjMode2S(
                mode_name="wear",
                targets=["box"],
                aut_name="ev",
                occ_law={"cls": "exp", "rate": 0.1},
                not_occ_law={"cls": "exp", "rate": 0.2},
            )
