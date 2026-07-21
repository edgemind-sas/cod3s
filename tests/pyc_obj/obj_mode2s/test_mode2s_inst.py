"""Generic inst machinery — native ObjMode2S, both directions.

Locks the unified per-edge inst semantics of the brainstorm
(2026-07-20): one draw per rising edge of the composite guard, `_star`
parked micro-states, `inst p=1` re-arm, masks, and the return-direction
scenario D (*per-demand recovery*: one repair attempt per maintenance
crew visit). Timed directions must build no inst machinery at all.
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
        self.crew = self.addVariable("crew", Pyc.TVarType.t_bool, False)


@pytest.fixture
def pyc_session():
    yield
    cod3s.terminate_session()


def _fireable(system):
    return [t for t in system.isimu_fireable_transitions() if t is not None]


def _fire(system, name, comp_name=None, state_index=None, date=None):
    trs = system.isimu_fireable_transitions()
    idx = next(
        i
        for i, t in enumerate(trs)
        if t is not None
        and t.name == name
        and (comp_name is None or t.comp_name == comp_name)
    )
    kwargs = {}
    if state_index is not None:
        kwargs["state_index"] = state_index
    if date is not None:
        kwargs["date"] = date
    system.isimu_set_transition(idx, **kwargs)
    return [t.name for t in system.isimu_step_forward()]


def test_native_inst_occ_grammar_and_masks(pyc_session):
    """Native inst on the occ direction: `_star` parked state, masks,
    re-arm, prob re-binding — the generic mirror of ObjFMInst."""
    system = PycSystem(name="InstOccGrammar")
    Equipment("E1")
    mode = ObjMode2S(
        mode_name="miss",
        targets=["E1"],
        occ_law={"cls": "inst", "prob": 0.3},
        not_occ_law={"cls": "exp", "rate": 0.5},
        occ_cond=lambda: system.comp["E1"].crew.value() is True,
    )
    aut = mode.automata_d["miss"]
    assert {st.name for st in aut.states} == {"not_occ", "occ", "not_occ_star"}
    assert aut.init_state == "not_occ"
    draw = aut.get_transition_by_name("occ")
    assert draw.source == "not_occ"
    assert [b.state for b in draw.target] == ["occ", "not_occ_star"]
    assert draw.target[0].prob == pytest.approx(0.3)
    rearm = aut.get_transition_by_name("not_occ_star")
    assert rearm.source == "not_occ_star"
    assert rearm.target == "not_occ"
    # Masks: draw records only the occ branch; re-arm silenced.
    assert draw._bkd.monitoredOutStateMask() == "#occ$"
    assert rearm._bkd.monitoredOutStateMask() == "#$^"
    mode.reapply_monitor_masks()
    assert draw._bkd.monitoredOutStateMask() == "#occ$"
    # Native param variable, law re-bound for runtime overrides.
    assert "occ_prob" in [v.basename() for v in mode.variables()]


def test_timed_directions_build_no_inst_machinery(pyc_session):
    """exp/delay directions never get `_star` states nor re-arm."""
    system = PycSystem(name="InstNone")
    Equipment("E1")
    mode = ObjMode2S(
        mode_name="wear",
        targets=["E1"],
        occ_law={"cls": "exp", "rate": 0.1},
        not_occ_law={"cls": "delay", "time": 5},
    )
    aut = mode.automata_d["wear"]
    assert {st.name for st in aut.states} == {"not_occ", "occ"}
    assert len(aut.transitions) == 2


def test_return_direction_per_demand_recovery(pyc_session):
    """Scenario D (brainstorm): inst on the RETURN direction = one
    repair attempt per crew visit, parking in occ_star, re-arm on crew
    departure, and occ clamps still active while parked (G4)."""
    system = PycSystem(name="InstReturn")
    Equipment("E1")
    eq = system.comp["E1"]
    mode = ObjMode2S(
        mode_name="fix",
        targets=["E1"],
        occ_law={"cls": "delay", "time": 2.0},
        not_occ_law={"cls": "inst", "prob": 0.8},
        not_occ_cond=lambda: eq.crew.value() is True,
        occ_effects={"working": False},
    )
    aut = mode.automata_d["fix"]
    assert {st.name for st in aut.states} == {"not_occ", "occ", "occ_star"}

    system.isimu_start()
    # Failure at t=2 (deterministic delay).
    assert _fire(system, "occ", comp_name="E1__fix") == ["occ"]
    assert eq.working.value() is False

    # No crew -> no repair attempt fireable.
    assert _fireable(system) == []

    # Crew arrives (manual toggle + scheduler refresh): the return draw
    # is pending with branches [not_occ (0.8), occ_star (0.2)].
    eq.crew.setValue(True)
    system.isimu_step_forward()
    draws = _fireable(system)
    assert len(draws) == 1
    assert draws[0].name == "not_occ"
    assert [b.state for b in draws[0].target] == ["not_occ", "occ_star"]
    assert draws[0].target[0].prob == pytest.approx(0.8)

    # Attempt FAILS (parked branch): logically still occ — the clamp
    # keeps working=False (G4 composite predicate), and no re-draw
    # while the crew stays (anti-Zeno).
    _fire(system, "not_occ", state_index=1)
    assert aut.get_state_by_name("occ_star")._bkd.isActive()
    assert eq.working.value() is False
    assert _fireable(system) == []

    # Crew leaves -> deterministic re-arm (masked, inst p=1).
    eq.crew.setValue(False)
    system.isimu_step_forward()  # scheduler refresh
    fired = [t.name for t in system.isimu_step_forward()]
    assert fired == ["occ_star"]
    assert aut.get_state_by_name("occ")._bkd.isActive()

    # New crew visit = new attempt; this one SUCCEEDS.
    eq.crew.setValue(True)
    system.isimu_step_forward()
    _fire(system, "not_occ", state_index=0)
    assert aut.get_state_by_name("not_occ")._bkd.isActive()
    assert eq.working.value() is True
    system.isimu_stop()


def test_cond_true_is_immediately_or_never(pyc_session):
    """cond ≡ True degenerates to on-entry branching: one draw at t=0,
    a failed draw parks forever (no re-arm — the condition never
    falls)."""
    system = PycSystem(name="InstImmediate")
    Equipment("E1")
    mode = ObjMode2S(
        mode_name="boot",
        targets=["E1"],
        occ_law={"cls": "inst", "prob": 0.3},
        not_occ_law={"cls": "exp", "rate": 0.5},
    )
    aut = mode.automata_d["boot"]
    system.isimu_start()
    draws = _fireable(system)
    assert len(draws) == 1 and draws[0].name == "occ"
    _fire(system, "occ", state_index=1)  # failed draw -> parked
    assert aut.get_state_by_name("not_occ_star")._bkd.isActive()
    # cond never falls -> never re-armed, nothing ever fireable again.
    assert _fireable(system) == []
    system.isimu_stop()


def test_inst_inst_allowed_and_guarded(pyc_session):
    """inst/inst builds 4 states; the certain livelock (prob 1 both
    sides + trivially-true conds) is rejected; prob 1 both sides with
    real conditions only warns."""
    system = PycSystem(name="InstInst")
    Equipment("E1")
    eq = system.comp["E1"]
    mode = ObjMode2S(
        mode_name="flip",
        targets=["E1"],
        occ_law={"cls": "inst", "prob": 0.5},
        not_occ_law={"cls": "inst", "prob": 0.5},
        occ_cond=lambda: eq.crew.value() is True,
        not_occ_cond=lambda: eq.crew.value() is False,
    )
    aut = mode.automata_d["flip"]
    assert {st.name for st in aut.states} == {
        "not_occ",
        "occ",
        "not_occ_star",
        "occ_star",
    }

    with pytest.raises(ValueError, match="livelock"):
        ObjMode2S(
            mode_name="dead",
            targets=["E1"],
            occ_law={"cls": "inst", "prob": 1},
            not_occ_law={"cls": "inst", "prob": 1},
        )

    with pytest.warns(UserWarning, match="inst/inst"):
        ObjMode2S(
            mode_name="risky",
            targets=["E1"],
            occ_law={"cls": "inst", "prob": 1},
            not_occ_law={"cls": "inst", "prob": 1},
            occ_cond=lambda: eq.crew.value() is True,
            not_occ_cond=lambda: eq.crew.value() is False,
        )


class TestNativeInstGuards:
    def test_inst_rejected_with_external_behaviours(self, pyc_session):
        system = PycSystem(name="InstExtGuard")
        for n in ("E1", "E2"):
            Equipment(n)
        with pytest.raises(ValueError, match="internal"):
            ObjMode2S(
                mode_name="miss",
                targets=["E1", "E2"],
                behaviour="external",
                occ_law={"cls": "inst", "prob": [0.3, 0.1]},
                not_occ_law={"cls": "exp", "rate": [0.5, 0.5]},
            )

    def test_inst_return_rejected_with_cc(self, pyc_session):
        system = PycSystem(name="InstRetCCGuard")
        for n in ("E1", "E2"):
            Equipment(n)
        with pytest.raises(ValueError, match="return direction"):
            ObjMode2S(
                mode_name="fix",
                targets=["E1", "E2"],
                occ_law={"cls": "exp", "rate": [0.1, 0.05]},
                not_occ_law={"cls": "inst", "prob": [0.8, 0.8]},
            )

    def test_trans_effects_rejected_on_inst_direction(self, pyc_session):
        system = PycSystem(name="InstTransGuard")
        Equipment("E1")
        with pytest.raises(ValueError, match="inst"):
            ObjMode2S(
                mode_name="miss",
                targets=["E1"],
                occ_law={"cls": "inst", "prob": 0.3},
                not_occ_law={"cls": "exp", "rate": 0.5},
                occ_effects_trans={"working": False},
            )

    def test_native_inst_cc_occ_side_allowed(self, pyc_session):
        """occ-side inst with CC mirrors ObjFMInst (per-order probs)."""
        system = PycSystem(name="InstCCNative")
        for n in ("E1", "E2"):
            Equipment(n)
        mode = ObjMode2S(
            mode_name="miss",
            targets=["E1", "E2"],
            occ_law={"cls": "inst", "prob": [0.3, 0.1]},
            not_occ_law={"cls": "exp", "rate": [0.5, 0.5]},
        )
        assert sorted(mode.automata_d) == [
            "miss__cc_1",
            "miss__cc_1_2",
            "miss__cc_2",
        ]
        aut = mode.automata_d["miss__cc_1_2"]
        assert {st.name for st in aut.states} == {
            "not_occ__cc_1_2",
            "occ__cc_1_2",
            "not_occ_star__cc_1_2",
        }
        draw = aut.get_transition_by_name("occ__cc_1_2")
        assert draw._bkd.monitoredOutStateMask() == "#occ__cc_1_2$"
        assert sorted(v.basename() for v in mode.variables()) == [
            "not_occ_rate__1_o_2",
            "not_occ_rate__2_o_2",
            "occ_prob__1_o_2",
            "occ_prob__2_o_2",
        ]
