"""One-shot effects on several targets and on inst directions (cod3s#9).

Up to 1.20.0, ``ObjMode2S`` refused trans-based effects as soon as a mode
had two targets, and on any ``inst`` direction. Both refusals were broader
than what makes a shape ill-posed.

Several targets. What matters is how many built automata write a given
target's variable:

* ``external`` / ``external_rep_indep``: the effects live on each target's
  single mirror automaton, which follows the OR of the combinations
  covering the target. One writer per target, whatever the CC orders.
* ``internal``: each kept order ``k`` puts ``C(n-1, k-1)`` combination
  automata on every target. Order 1 alone (a mode applying to several
  sensor instances) or order ``n`` alone is the single-target case. When
  combinations overlap, the hand-back pair (held in ``occ``, pulsed
  entering ``not_occ``) still converges: a repaired combination's pulse is
  overwritten by the clamp of a combination still in ``occ``, the last
  repair hands the value back. Refused: the both-pulse persistent gate.
  The held effects of overlapping combinations are applied once per
  target (cod3s#10, see test_mode2s_ccf_level_clamp.py), so the shapes
  refused in 1.21.0 for them (a pulse entering ``occ`` on a variable held
  at rest, a variable held on both faces, cod3s#4) are accepted.

Inst directions. A pulse on a timed edge of a mode with an inst direction
is an ordinary edge callback. A pulse on a draw edge is guarded on the
destination state, so it fires only when the draw lands there.

The Monte-Carlo checks compare, on the same runs, a variable written by
the pulses with one held by the mode's clamp (``working``, reinitialised,
held ``False`` while the mode is logically in ``occ``): their means are
equal at every instant only if they agree on every trajectory.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem

NOMINAL = 40.0
CLAMPED = 0.0

#: Indicator means are single precision: far below one trajectory out of
#: the 300 of a check (3.3e-3), far above their rounding (3e-8).
TOL = 1e-6

#: Sampling instants of the Monte-Carlo agreement checks.
MC_SCHEDULE = [0.0, 0.7, 1.3, 2.2, 3.1, 4.6, 5.9, 7.4, 9.0, 11.3, 14.0]


# Component classes are resolved by name among the live subclasses of
# PycComponent, so their names must be unique across the test session
# (``Store`` already exists in test_mode2s_one_shot_handback.py).


class CcfInstStore(cod3s.PycComponent):
    """Target: persistent ``ceiling`` and ``gate``, reinitialised ``working``."""

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.ceiling = self.addVariable("ceiling", Pyc.TVarType.t_double, NOMINAL)
        self.ceiling.setReinitialized(False)
        self.gate = self.addVariable("gate", Pyc.TVarType.t_bool, False)
        self.gate.setReinitialized(False)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


class CcfInstDemander(cod3s.PycComponent):
    """Deterministic demand: on at 1, off at 1.5, on at 2.5, off at 3, ..."""

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.demand = self.addVariable("demand", Pyc.TVarType.t_bool, False)
        self.demand.setReinitialized(True)
        self.add_aut2st(
            name="cycle",
            st1="idle",
            st2="on",
            init_st2=False,
            trans_name_12_fmt="on",
            occ_law_12={"cls": "delay", "time": 1.0},
            trans_name_21_fmt="idle",
            occ_law_21={"cls": "delay", "time": 0.5},
            effects_st2={"demand": True},
        )


@pytest.fixture(autouse=True)
def _release_pycatshoo_singleton_per_test():
    yield
    cod3s.terminate_session()


def _system(name, targets=("A", "B"), demander=False):
    system = PycSystem(name=name)
    for target in targets:
        system.add_component(name=target, cls="CcfInstStore")
    if demander:
        system.add_component(name="D", cls="CcfInstDemander")
    return system


def _mode(targets, behaviour="internal", **fields):
    spec = dict(
        cls="ObjMode2S",
        mode_name="m",
        targets=list(targets),
        behaviour=behaviour,
        occ_state="occ",
        not_occ_state="rep",
    )
    spec.update(fields)
    return spec


def _exp(n, occ_rates, not_occ_rates):
    """Exponential laws, one rate per CC order (0 drops an order)."""
    assert len(occ_rates) == len(not_occ_rates) == n
    return dict(
        occ_law={"cls": "exp", "rate": list(occ_rates) if n > 1 else occ_rates[0]},
        not_occ_law={
            "cls": "exp",
            "rate": list(not_occ_rates) if n > 1 else not_occ_rates[0],
        },
    )


def _indicators(system, targets, var):
    return {
        target: system.add_indicator_var(
            component=target, var=var, stats=["mean"], name=f"{target}_{var}"
        )[0]
        for target in targets
    }


def _values(indicator):
    return indicator.values["values"].to_list()


def _assert_pulses_follow_the_clamp(system, targets, pulsed, nb_runs=300):
    """Simulate; per target, the pulsed variable agrees with ``working``.

    ``pulsed`` is ``"gate"`` (set entering occ, cleared entering rep) or
    ``"ceiling"`` (held at 0 in occ, handed back at 40). Also checks that
    the mode was both in and out of occ, so the agreement is not vacuous.
    """
    pulsed_ind = _indicators(system, targets, pulsed)
    working_ind = _indicators(system, targets, "working")
    system.simulate(
        PycMCSimulationParam(nb_runs=nb_runs, schedule=MC_SCHEDULE, seed=11)
    )
    for target in targets:
        p_occ = [1.0 - w for w in _values(working_ind[target])]
        if pulsed == "gate":
            from_pulses = _values(pulsed_ind[target])
        else:
            from_pulses = [1.0 - c / NOMINAL for c in _values(pulsed_ind[target])]
        assert from_pulses == pytest.approx(p_occ, abs=TOL), target
        assert any(0.0 < p < 1.0 for p in p_occ), target


BOTH_PULSE = dict(
    occ_effects_trans={"gate": True}, not_occ_effects_trans={"gate": False}
)
HANDBACK = dict(
    occ_effects={"ceiling": CLAMPED}, not_occ_effects_trans={"ceiling": NOMINAL}
)
#: The hand-back pair plus ``working`` held with it, for the agreement checks.
HANDBACK_WORKING = dict(
    occ_effects={"ceiling": CLAMPED, "working": False},
    not_occ_effects_trans={"ceiling": NOMINAL},
)


# ---------------------------------------------------------------------------
# Several targets: validation counts the combinations, not the targets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("effects", [BOTH_PULSE, HANDBACK], ids=["pulse", "handback"])
def test_order_one_alone_over_three_targets_is_accepted(effects):
    """Three sensor instances, only order 1 active: one writer per target."""
    system = _system("SysOrderOne", targets=("A", "B", "C"))
    mode = system.add_component(
        **_mode(("A", "B", "C"), **_exp(3, [0.3, 0, 0], [1.0, 0, 0]), **effects)
    )
    assert sorted(mode.automata_d) == ["m__cc_1", "m__cc_2", "m__cc_3"]


def test_last_order_alone_is_accepted():
    """Order n alone builds one combination covering every target once."""
    system = _system("SysOrderN")
    mode = system.add_component(
        **_mode(("A", "B"), **_exp(2, [0, 0.3], [0, 1.0]), **BOTH_PULSE)
    )
    assert sorted(mode.automata_d) == ["m__cc_1_2"]


def test_kept_inactive_orders_count_as_writers():
    """``drop_inactive_automata=False`` builds the inactive orders too."""
    system = _system("SysKeepInactive")
    with pytest.raises(ValueError, match="pulsed on both faces"):
        system.add_component(
            **_mode(
                ("A", "B"),
                **_exp(2, [0.3, 0], [1.0, 0]),
                drop_inactive_automata=False,
                **BOTH_PULSE,
            )
        )


def test_handback_over_overlapping_combinations_is_accepted():
    system = _system("SysOverlapHandback")
    mode = system.add_component(
        **_mode(("A", "B"), **_exp(2, [0.3, 0.2], [1.0, 0.5]), **HANDBACK)
    )
    assert sorted(mode.automata_d) == ["m__cc_1", "m__cc_1_2", "m__cc_2"]


@pytest.mark.parametrize("effects", [BOTH_PULSE, HANDBACK], ids=["pulse", "handback"])
@pytest.mark.parametrize("behaviour", ["external", "external_rep_indep"])
def test_external_behaviours_accept_overlapping_combinations(behaviour, effects):
    system = _system("SysOverlapExternal")
    system.add_component(
        **_mode(("A", "B"), behaviour, **_exp(2, [0.3, 0.2], [1.0, 0.5]), **effects)
    )


def test_both_pulse_over_overlapping_combinations_is_refused():
    system = _system("SysOverlapRefused", targets=("A", "B", "C"))
    with pytest.raises(ValueError, match=r"\['gate'\] are pulsed on both faces") as err:
        system.add_component(
            **_mode(
                ("A", "B", "C"),
                **_exp(3, [0.3, 0.2, 0.1], [1.0, 0.5, 0.5]),
                **BOTH_PULSE,
            )
        )
    # The message names what made the combinations overlap.
    assert "CC orders [1, 2, 3] kept): 4 combination automata write" in str(err.value)


def test_held_on_both_faces_with_the_same_value_is_accepted():
    """No contradiction, nothing to refuse."""
    system = _system("SysHeldSameValue")
    system.add_component(
        **_mode(
            ("A", "B"),
            **_exp(2, [0.3, 0.2], [1.0, 0.5]),
            occ_effects={"gate": True},
            not_occ_effects={"gate": True},
        )
    )


def test_facade_refuses_with_its_own_vocabulary():
    system = _system("SysFacadeOverlap")
    with pytest.raises(
        ValueError,
        match=r"pulsed on both faces \(failure_effects_trans and repair_effects_trans",
    ):
        system.add_component(
            cls="ObjFMExp",
            fm_name="f",
            targets=["A", "B"],
            failure_param=[0.3, 0.2],
            repair_param=[1.0, 0.5],
            failure_effects_trans={"gate": True},
            repair_effects_trans={"gate": False},
        )
    system.add_component(
        cls="ObjFMExp",
        fm_name="g",
        targets=["A", "B"],
        failure_param=[0.3, 0.2],
        repair_param=[1.0, 0.5],
        failure_effects={"ceiling": CLAMPED},
        repair_effects_trans={"ceiling": NOMINAL},
    )


# ---------------------------------------------------------------------------
# Several targets: behaviour
# ---------------------------------------------------------------------------


def test_internal_handback_waits_for_the_last_combination_covering_the_target():
    """Delay laws: order 1 fails at 2 and repairs after 2, order 2 fails at 3
    and repairs after 10.

    cc_1 / cc_2: occ 2, rep 4, occ 6, rep 8, occ 10, rep 12, occ 14.
    cc_1_2: occ 3, rep 13. The repair pulses of cc_1 at 4, 8 and 12 are
    overwritten by the clamp of cc_1_2, still in occ; its own repair at 13
    hands the value back; cc_1 clamps again at 14.
    """
    system = _system("SysCcfHandbackTimeline")
    system.add_component(
        **_mode(
            ("A", "B"),
            occ_law={"cls": "delay", "time": [2.0, 3.0]},
            not_occ_law={"cls": "delay", "time": [2.0, 10.0]},
            **HANDBACK,
        )
    )
    ceiling = _indicators(system, ("A", "B"), "ceiling")
    schedule = [0.0, 2.5, 3.5, 4.5, 12.5, 13.5, 14.5]
    system.simulate(PycMCSimulationParam(nb_runs=1, schedule=schedule, seed=1))
    expected = [NOMINAL, CLAMPED, CLAMPED, CLAMPED, CLAMPED, NOMINAL, CLAMPED]
    assert _values(ceiling["A"]) == expected
    assert _values(ceiling["B"]) == expected


def test_internal_handback_follows_the_clamp_over_overlapping_combinations():
    system = _system("SysCcfHandbackMC", targets=("A", "B", "C"))
    system.add_component(
        **_mode(
            ("A", "B", "C"),
            **_exp(3, [0.3, 0.2, 0.1], [1.0, 0.5, 0.4]),
            **HANDBACK_WORKING,
        )
    )
    _assert_pulses_follow_the_clamp(system, ("A", "B", "C"), "ceiling")


def test_internal_order_one_alone_pulses_follow_each_target():
    system = _system("SysOrderOneMC", targets=("A", "B", "C"))
    system.add_component(
        **_mode(
            ("A", "B", "C"),
            **_exp(3, [0.3, 0, 0], [1.0, 0, 0]),
            occ_effects={"working": False},
            **BOTH_PULSE,
        )
    )
    _assert_pulses_follow_the_clamp(system, ("A", "B", "C"), "gate")


@pytest.mark.parametrize("behaviour", ["external", "external_rep_indep"])
def test_external_both_pulse_gate_follows_the_mirror_over_combinations(behaviour):
    """The desynchronisation that justified the refusal does not happen."""
    system = _system("SysExtCcfMC", targets=("A", "B", "C"))
    system.add_component(
        **_mode(
            ("A", "B", "C"),
            behaviour,
            **_exp(3, [0.3, 0.2, 0.1], [1.0, 0.5, 0.4]),
            occ_effects={"working": False},
            **BOTH_PULSE,
        )
    )
    _assert_pulses_follow_the_clamp(system, ("A", "B", "C"), "gate")


@pytest.mark.parametrize("behaviour", ["external", "external_rep_indep"])
def test_external_handback_follows_the_mirror_over_combinations(behaviour):
    system = _system("SysExtCcfHandbackMC", targets=("A", "B", "C"))
    system.add_component(
        **_mode(
            ("A", "B", "C"),
            behaviour,
            **_exp(3, [0.3, 0.2, 0.1], [1.0, 0.5, 0.4]),
            **HANDBACK_WORKING,
        )
    )
    _assert_pulses_follow_the_clamp(system, ("A", "B", "C"), "ceiling")


# ---------------------------------------------------------------------------
# Inst directions
# ---------------------------------------------------------------------------


def _demand(system):
    demander = system.comp["D"]
    return lambda: demander.demand.value() is True


@pytest.mark.parametrize("behaviour", ["internal", "external", "external_rep_indep"])
def test_demand_failure_hands_the_value_back_at_its_timed_repair(behaviour):
    """Certain draw on each demand front, repaired after 1.

    Demand on at 1, 2.5, 4 (off at 1.5, 3, 4.5): occ 1, rep 2, occ 2.5,
    rep 3.5, occ 4. The pulse sits on the timed repair edge (on the target
    mirror in the external behaviours).
    """
    system = _system("SysInstHandback", targets=("A",), demander=True)
    system.add_component(
        **_mode(
            ("A",),
            behaviour,
            occ_law={"cls": "inst", "prob": 1.0},
            occ_cond=_demand(system),
            not_occ_law={"cls": "delay", "time": 1.0},
            **HANDBACK,
        )
    )
    ceiling = _indicators(system, ("A",), "ceiling")["A"]
    schedule = [0.0, 0.5, 1.2, 2.2, 2.7, 3.7, 4.2]
    system.simulate(PycMCSimulationParam(nb_runs=1, schedule=schedule, seed=1))
    assert _values(ceiling) == [
        NOMINAL,
        NOMINAL,
        CLAMPED,
        NOMINAL,
        CLAMPED,
        NOMINAL,
        CLAMPED,
    ]


@pytest.mark.parametrize("behaviour", ["internal", "external"])
def test_pulse_on_a_two_branch_occ_draw_fires_on_the_landed_branch(behaviour):
    """A failed draw parks in ``rep_star`` without setting the gate."""
    system = _system("SysInstOccDraw", targets=("A",), demander=True)
    system.add_component(
        **_mode(
            ("A",),
            behaviour,
            occ_law={"cls": "inst", "prob": 0.5},
            occ_cond=_demand(system),
            not_occ_law={"cls": "exp", "rate": 1.0},
            occ_effects={"working": False},
            **BOTH_PULSE,
        )
    )
    _assert_pulses_follow_the_clamp(system, ("A",), "gate")


def test_pulse_on_a_two_branch_return_draw_fires_on_the_landed_branch():
    """Return direction drawn on each demand front (a repair attempt per
    crew visit): a failed attempt parks in ``occ_star``, logically still in
    occ, without clearing the gate nor handing the ceiling back."""
    system = _system("SysInstReturnDraw", targets=("A",), demander=True)
    system.add_component(
        **_mode(
            ("A",),
            occ_law={"cls": "exp", "rate": 0.4},
            not_occ_law={"cls": "inst", "prob": 0.5},
            not_occ_cond=_demand(system),
            occ_effects={"working": False, "ceiling": CLAMPED},
            occ_effects_trans={"gate": True},
            not_occ_effects_trans={"gate": False, "ceiling": NOMINAL},
        )
    )
    gate = _indicators(system, ("A",), "gate")["A"]
    ceiling = _indicators(system, ("A",), "ceiling")["A"]
    working = _indicators(system, ("A",), "working")["A"]
    system.simulate(PycMCSimulationParam(nb_runs=300, schedule=MC_SCHEDULE, seed=5))
    p_occ = [1.0 - w for w in _values(working)]
    assert any(0.0 < p < 1.0 for p in p_occ)
    assert _values(gate) == pytest.approx(p_occ, abs=TOL)
    assert [1.0 - c / NOMINAL for c in _values(ceiling)] == pytest.approx(
        p_occ, abs=TOL
    )


def test_objfminst_hosts_one_shot_effects():
    """The façade's draw is the engine's: same guard, same agreement."""
    system = _system("SysObjFMInstPulses", targets=("A",), demander=True)
    system.add_component(
        cls="ObjFMInst",
        fm_name="m",
        targets=["A"],
        failure_cond=_demand(system),
        failure_param=0.5,
        repair_param=1.0,
        failure_effects={"working": False},
        failure_effects_trans={"gate": True},
        repair_effects_trans={"gate": False},
    )
    _assert_pulses_follow_the_clamp(system, ("A",), "gate")


def test_inst_occ_over_overlapping_combinations_keeps_the_coverage_rule():
    system = _system("SysInstOverlap")
    with pytest.raises(ValueError, match="pulsed on both faces"):
        system.add_component(
            **_mode(
                ("A", "B"),
                occ_law={"cls": "inst", "prob": [0.5, 0.2]},
                not_occ_law={"cls": "exp", "rate": [1.0, 0.5]},
                **BOTH_PULSE,
            )
        )
    system.add_component(
        **_mode(
            ("A", "B"),
            mode_name="m2",
            occ_law={"cls": "inst", "prob": [0.5, 0.2]},
            not_occ_law={"cls": "exp", "rate": [1.0, 0.5]},
            **HANDBACK,
        )
    )
