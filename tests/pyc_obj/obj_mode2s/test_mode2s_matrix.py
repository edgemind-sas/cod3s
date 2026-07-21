"""The 3x3 law matrix — construction sweep + deterministic isimu cycles.

Every cell of the (occ_law x not_occ_law) matrix must either construct
or reject with a clear error at construction — never build a silent
wrong model. At internal / order 1 all nine cells construct (the
restricted cells are inst x external behaviours and inst-return x CC,
locked by ``test_mode2s_inst.py``). Rejection cells are asserted
without ever simulating.

Also includes the isimu same-instant cascade regression (G11): an inst
branch submitted at an instant may create a new inst pending at the
same instant — the pending loop must re-surface it.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import ObjMode2S
from cod3s.pycatshoo.system import PycSystem


class Equipment(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


@pytest.fixture
def pyc_session():
    yield
    cod3s.terminate_session()


LAWS = {
    "exp": {"cls": "exp", "rate": 0.5},
    "delay": {"cls": "delay", "time": 2.0},
    "inst": {"cls": "inst", "prob": 0.5},
}


@pytest.mark.parametrize("occ_kind", ["exp", "delay", "inst"])
@pytest.mark.parametrize("ret_kind", ["exp", "delay", "inst"])
def test_matrix_cell_constructs(pyc_session, occ_kind, ret_kind):
    system = PycSystem(name=f"Matrix_{occ_kind}_{ret_kind}")
    Equipment("E1")
    eq = system.comp["E1"]
    # Non-trivial conds so the inst/inst prob-1 guard path is not
    # involved (probs are 0.5 anyway) and draws are drivable.
    mode = ObjMode2S(
        mode_name="m",
        targets=["E1"],
        occ_law=dict(LAWS[occ_kind]),
        not_occ_law=dict(LAWS[ret_kind]),
        occ_cond=lambda: eq.working.value() is True,
        not_occ_cond=lambda: eq.working.value() is not None,
    )
    aut = mode.automata_d["m"]
    expected_states = 2 + (occ_kind == "inst") + (ret_kind == "inst")
    assert len(aut.states) == expected_states
    # Param variables: one per direction, named by the law field.
    field = {"exp": "rate", "delay": "time", "inst": "prob"}
    assert sorted(v.basename() for v in mode.variables()) == sorted(
        [f"occ_{field[occ_kind]}", f"not_occ_{field[ret_kind]}"]
    )


def _fire(system, name, state_index=None, date=None):
    trs = system.isimu_fireable_transitions()
    idx = next(i for i, t in enumerate(trs) if t is not None and t.name == name)
    kwargs = {}
    if state_index is not None:
        kwargs["state_index"] = state_index
    if date is not None:
        kwargs["date"] = date
    system.isimu_set_transition(idx, **kwargs)
    return [t.name for t in system.isimu_step_forward()]


@pytest.mark.parametrize(
    "occ_kind,ret_kind",
    [
        ("exp", "delay"),
        ("delay", "exp"),
        ("exp", "inst"),
        ("delay", "inst"),
        ("inst", "delay"),
    ],
)
def test_mixed_combo_isimu_cycle(pyc_session, occ_kind, ret_kind):
    """One full occ -> not_occ cycle per new mixed combo."""
    system = PycSystem(name=f"Cycle_{occ_kind}_{ret_kind}")
    Equipment("E1")
    mode = ObjMode2S(
        mode_name="m",
        targets=["E1"],
        occ_law=dict(LAWS[occ_kind]),
        not_occ_law=dict(LAWS[ret_kind]),
        occ_effects={"working": False},
    )
    aut = mode.automata_d["m"]
    eq = system.comp["E1"]
    system.isimu_start()

    if occ_kind == "inst":
        fired = _fire(system, "occ", state_index=0)  # force the occ branch
    elif occ_kind == "exp":
        fired = _fire(system, "occ", date=1.0)
    else:  # delay: fireable at its deterministic date
        fired = _fire(system, "occ")
    assert fired == ["occ"]
    assert aut.get_state_by_name("occ")._bkd.isActive()
    assert eq.working.value() is False

    if ret_kind == "inst":
        fired = _fire(system, "not_occ", state_index=0)
    elif ret_kind == "exp":
        fired = _fire(system, "not_occ", date=3.0)
    else:
        fired = _fire(system, "not_occ")
    assert fired == ["not_occ"]
    assert aut.get_state_by_name("not_occ")._bkd.isActive()
    assert eq.working.value() is True
    system.isimu_stop()


def test_isimu_inst_inst_same_instant_cascade(pyc_session):
    """G11: submitting an inst branch that lands in a state whose OWN
    inst draw is enabled at the same instant must re-surface the new
    pending instead of losing it."""
    system = PycSystem(name="CascadeInstInst")
    Equipment("E1")
    mode = ObjMode2S(
        mode_name="flip",
        targets=["E1"],
        occ_law={"cls": "inst", "prob": 0.5},
        not_occ_law={"cls": "inst", "prob": 0.5},
        # Trivially-true conds are allowed at probs < 1 (a.s.
        # termination); this is the maximal ping-pong configuration.
    )
    aut = mode.automata_d["flip"]
    system.isimu_start()

    # t=0: the occ draw is pending.
    draws = [t for t in system.isimu_fireable_transitions() if t is not None]
    assert [t.name for t in draws] == ["occ"]

    # Land in occ -> the RETURN draw must appear at the same instant.
    _fire(system, "occ", state_index=0)
    assert system.currentTime() == 0.0
    draws = [t for t in system.isimu_fireable_transitions() if t is not None]
    assert [t.name for t in draws] == ["not_occ"]

    # Land back in not_occ -> the occ draw re-surfaces again (cascade).
    _fire(system, "not_occ", state_index=0)
    assert system.currentTime() == 0.0
    draws = [t for t in system.isimu_fireable_transitions() if t is not None]
    assert [t.name for t in draws] == ["occ"]

    # Break the chain: park on the occ side -> nothing fireable (the
    # trivially-true cond never falls, no re-arm — absorbed).
    _fire(system, "occ", state_index=1)
    assert aut.get_state_by_name("not_occ_star")._bkd.isActive()
    assert [t for t in system.isimu_fireable_transitions() if t is not None] == []
    system.isimu_stop()
