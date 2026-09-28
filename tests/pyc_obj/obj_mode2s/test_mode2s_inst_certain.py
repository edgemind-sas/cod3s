"""A certain inst draw (probability exactly 1) is built as a single branch.

The generic inst machinery builds every draw with two branches, the
destination and a parked complement. PyCATSHOO refuses a two-branch inst
whose parameter is 1, at start and at any later step ("Il y a plus d'un
paramètre égal à 1"), so before 1.17.1 an ObjMode2S with an inst law at
probability 1, in either direction, could not be simulated at all:
neither Monte-Carlo nor interactive, and the exception carried an empty
message. A "worst case" study (a start-up refusal that always happens) is
a legitimate model, not an edge case.

A certain draw is now a single-branch inst to its destination, with no
parked state, no re-arm and no parameter, which PyCATSHOO accepts and
which lands where the two-branch form would have. The structure being
decided at construction, the study runner refuses by name a runtime
override that would cross probability 1.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import ObjMode2S
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem
from cod3s.scripts.study_runner import _propagate_param_override_to_variables


class Equipment(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)
        self.demand = self.addVariable("demand", Pyc.TVarType.t_bool, True)


@pytest.fixture
def pyc_session():
    yield
    cod3s.terminate_session()


def fresh_system(name):
    cod3s.terminate_session()
    return PycSystem(name=name)


def _refusal(prob, **kwargs):
    """A start-up refusal gated on a held demand, no repair."""
    system = fresh_system(kwargs.pop("system_name", "InstCertain"))
    Equipment("E1")
    mode = ObjMode2S(
        mode_name="refusal",
        targets=["E1"],
        occ_law={"cls": "inst", "prob": prob},
        not_occ_law={"cls": "exp", "rate": 0.0},
        occ_cond=lambda: system.comp["E1"].demand.value() is True,
        occ_effects={"working": False},
        **kwargs,
    )
    return system, mode


def _fire_all_pending(system):
    """Drain the instant, pinning nothing: only certain draws may be pending."""
    fired = []
    for _ in range(5):
        pending = [t for t in system.isimu_fireable_transitions() if t is not None]
        if not pending:
            break
        system.isimu_set_transition(
            system.isimu_fireable_transitions().index(pending[0])
        )
        fired.extend(t.name for t in system.isimu_step_forward())
    return fired


class TestStructure:
    def test_a_certain_occurrence_is_a_single_branch_draw(self, pyc_session):
        _system, mode = _refusal(1.0)
        aut = mode.automata_d["refusal"]
        assert {st.name for st in aut.states} == {"not_occ", "occ"}
        draw = aut.get_transition_by_name("occ")
        assert draw.source == "not_occ"
        assert [b.state for b in draw.target] == ["occ"]
        assert draw._bkd.monitoredOutStateMask() == "#occ$"
        assert mode._inst_draw_kind == {"occ_prob": "certain"}

    def test_a_certain_return_is_a_single_branch_draw(self, pyc_session):
        cod3s.terminate_session()
        PycSystem(name="InstCertainReturn")
        Equipment("E1")
        mode = ObjMode2S(
            mode_name="fix",
            targets=["E1"],
            occ_law={"cls": "delay", "time": 2.0},
            not_occ_law={"cls": "inst", "prob": 1.0},
        )
        aut = mode.automata_d["fix"]
        assert {st.name for st in aut.states} == {"not_occ", "occ"}
        assert [b.state for b in aut.get_transition_by_name("not_occ").target] == [
            "not_occ"
        ]

    @pytest.mark.parametrize("prob", [0.9999, 0.3, 0.0])
    def test_any_other_probability_keeps_its_parked_branch(self, pyc_session, prob):
        """Exactly 1, not close to 1; and 0 is a draw that never fires."""
        _system, mode = _refusal(prob)
        aut = mode.automata_d["refusal"]
        assert {st.name for st in aut.states} == {"not_occ", "occ", "not_occ_star"}
        assert [b.state for b in aut.get_transition_by_name("occ").target] == [
            "occ",
            "not_occ_star",
        ]
        assert mode._inst_draw_kind == {"occ_prob": "random"}

    def test_each_common_cause_order_decides_for_itself(self, pyc_session):
        """Order 1 certain, order 2 random: one combination automaton each."""
        fresh_system("InstCertainCC")
        Equipment("E1")
        Equipment("E2")
        mode = ObjMode2S(
            mode_name="refusal",
            targets=["E1", "E2"],
            occ_law={"cls": "inst", "prob": [1.0, 0.5]},
            not_occ_law={"cls": "exp", "rate": [0.0, 0.0]},
        )
        # One parameter variable per order, shared by that order's combinations.
        assert sorted(mode._inst_draw_kind.values()) == ["certain", "random"]
        for name, aut in mode.automata_d.items():
            draw = next(
                t
                for t in aut.transitions
                if t.source.startswith("not_occ") and isinstance(t.target, list)
            )
            expected = 2 if name.endswith("cc_1_2") else 1
            assert len(draw.target) == expected, name


class TestItRuns:
    def test_the_interactive_session_starts_and_the_draw_lands(self, pyc_session):
        system, _mode = _refusal(1.0)
        system.isimu_start()
        try:
            fired = _fire_all_pending(system)
            assert "occ" in fired
            assert system.comp["E1"].working.value() is False
        finally:
            system.isimu_stop()

    def test_a_monte_carlo_run_completes_and_always_fails(self, pyc_session):
        system, _mode = _refusal(1.0, system_name="InstCertainMC")
        system.add_indicator_var(
            component="E1", var="working", stats=["mean"], name="up"
        )
        system.simulate(
            PycMCSimulationParam(nb_runs=50, schedule=[0.0, 5.0], seed=20260928)
        )
        assert float(system.indicators["up_working"].values["values"].iloc[-1]) == 0.0

    def test_the_livelock_guard_still_refuses_both_directions_at_one(self, pyc_session):
        """Certain in both directions with trivially true conditions is
        still a certain same-instant ping-pong."""
        cod3s.terminate_session()
        PycSystem(name="InstCertainLivelock")
        Equipment("E1")
        with pytest.raises(ValueError, match="livelock"):
            ObjMode2S(
                mode_name="pingpong",
                targets=["E1"],
                occ_law={"cls": "inst", "prob": 1.0},
                not_occ_law={"cls": "inst", "prob": 1.0},
            )


class TestRuntimeOverrideCannotCrossOne:
    def test_a_certain_draw_refuses_a_lower_probability(self, pyc_session):
        _system, mode = _refusal(1.0)
        with pytest.raises(ValueError, match="built as a certain draw"):
            _propagate_param_override_to_variables(mode, "occ", [0.5])
        assert mode.variable("occ_prob").value() == pytest.approx(1.0)

    def test_a_random_draw_refuses_probability_one(self, pyc_session):
        _system, mode = _refusal(0.5)
        with pytest.raises(ValueError, match="built as a random draw"):
            _propagate_param_override_to_variables(mode, "occ", [1.0])
        assert mode.variable("occ_prob").value() == pytest.approx(0.5)

    def test_an_override_that_stays_on_its_side_is_applied(self, pyc_session):
        _system, mode = _refusal(0.5)
        _propagate_param_override_to_variables(mode, "occ", [0.8])
        assert mode.variable("occ_prob").value() == pytest.approx(0.8)
