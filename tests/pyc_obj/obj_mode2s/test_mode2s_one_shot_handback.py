"""One-shot hand-back of a variable clamped by a held occurrence effect.

cod3s#8. A mode that clamps a variable of its target (a discharge
ceiling, a controller endpoint) holds the clamped value while in ``occ``
(``occ_effects``) and hands the nominal value back once, at the repair
edge (``not_occ_effects_trans``). The variable is persistent
(``setReinitialized(False)``), so nothing else restores it.

Two properties are locked here:

* the declaration is accepted: the held effect and the pulse are on
  opposite faces, whereas a held effect and a pulse on the SAME face stay
  refused (the clamp would overwrite the pulse);
* in ``external`` and ``external_rep_indep`` the pulses are wired on the
  target's mirror automaton (``<fm>__occ`` / ``<fm>__rep``), so the
  repair pulse fires once the target has left ``<fm>__occ``. Wired on the
  mode automaton, it fired while the target's held clamp was still active
  and the value was never handed back, even with a single mode.

Two modes clamping one variable with staggered occurrence and repair then
converge: the clamp stays while any mode holds it, the nominal value comes
back when the last one is repaired. With a held repair effect instead,
the same model never returns (two held effects on opposite faces).
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem

NOMINAL = 40.0
CLAMPED = 0.0

#: Sampling instants of every timeline test (single run, delay laws).
SCHEDULE = [0.0, 0.5, 1.5, 2.5, 3.1, 3.5]


class Store(cod3s.PycComponent):
    """Target with a persistent ``ceiling`` (nominal 40) and a spare gate."""

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.ceiling = self.addVariable("ceiling", Pyc.TVarType.t_double, NOMINAL)
        self.ceiling.setReinitialized(False)
        self.gate = self.addVariable("gate", Pyc.TVarType.t_bool, False)
        self.gate.setReinitialized(False)


@pytest.fixture(autouse=True)
def _release_pycatshoo_singleton_per_test():
    yield
    cod3s.terminate_session()


def _clamp_mode(name, ttf, ttr, behaviour, **overrides):
    """Single-target delay mode: held clamp in occ, one-shot hand-back."""
    spec = dict(
        cls="ObjMode2S",
        mode_name=name,
        targets=["S"],
        behaviour=behaviour,
        occ_state="occ",
        not_occ_state="rep",
        occ_law={"cls": "delay", "time": ttf},
        not_occ_law={"cls": "delay", "time": ttr},
        occ_effects={"ceiling": CLAMPED},
        not_occ_effects_trans={"ceiling": NOMINAL},
    )
    spec.update(overrides)
    return spec


def _ceiling_timeline(modes, name):
    system = PycSystem(name=name)
    system.add_component(name="S", cls="Store")
    for spec in modes:
        system.add_component(**spec)
    ind = system.add_indicator_var(
        component="S", var="ceiling", stats=["mean"], name="ceiling"
    )[0]
    system.simulate(PycMCSimulationParam(nb_runs=1, schedule=SCHEDULE, seed=1))
    assert ind.values["instant"].to_list() == SCHEDULE
    return ind.values["values"].to_list()


# ---------------------------------------------------------------------------
# Validation: opposite faces accepted, same face refused
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("behaviour", ["internal", "external", "external_rep_indep"])
def test_held_occ_and_one_shot_repair_on_one_variable_is_accepted(behaviour):
    system = PycSystem(name="SysHandbackAccepted")
    system.add_component(name="S", cls="Store")
    mode = system.add_component(**_clamp_mode("m", 1.0, 2.0, behaviour))
    assert mode.occ_effects == {"ceiling": CLAMPED}
    assert mode.not_occ_effects_trans == {"ceiling": NOMINAL}


def test_held_repair_and_one_shot_occurrence_on_one_variable_is_accepted():
    """The symmetric opposite-face pair is accepted too."""
    system = PycSystem(name="SysHandbackSymmetric")
    system.add_component(name="S", cls="Store")
    system.add_component(
        **_clamp_mode(
            "m",
            1.0,
            2.0,
            "external",
            occ_effects={},
            not_occ_effects_trans={},
            not_occ_effects={"ceiling": NOMINAL},
            occ_effects_trans={"ceiling": CLAMPED},
        )
    )


@pytest.mark.parametrize(
    "held, pulsed",
    [
        ("occ_effects", "occ_effects_trans"),
        ("not_occ_effects", "not_occ_effects_trans"),
    ],
)
@pytest.mark.parametrize("behaviour", ["internal", "external", "external_rep_indep"])
def test_held_and_pulsed_on_the_same_face_is_refused(held, pulsed, behaviour):
    system = PycSystem(name="SysSameFaceRefused")
    system.add_component(name="S", cls="Store")
    spec = _clamp_mode("m", 1.0, 2.0, behaviour, occ_effects={})
    spec.pop("not_occ_effects_trans")
    spec.update({held: {"ceiling": CLAMPED}, pulsed: {"ceiling": NOMINAL}})
    with pytest.raises(ValueError, match="same face.*silently overwritten"):
        system.add_component(**spec)


@pytest.mark.parametrize(
    "held, pulsed",
    [
        ("failure_effects", "failure_effects_trans"),
        ("repair_effects", "repair_effects_trans"),
    ],
)
def test_facade_refuses_the_same_face_and_accepts_the_opposite_face(held, pulsed):
    system = PycSystem(name="SysFacadeFaces")
    system.add_component(name="S", cls="Store")
    with pytest.raises(ValueError, match="same face.*silently overwritten"):
        system.add_component(
            cls="ObjFMDelay",
            fm_name="same",
            targets=["S"],
            behaviour="external",
            failure_param=1.0,
            repair_param=2.0,
            **{held: {"ceiling": CLAMPED}, pulsed: {"ceiling": NOMINAL}},
        )
    system.add_component(
        cls="ObjFMDelay",
        fm_name="opposite",
        targets=["S"],
        behaviour="external",
        failure_param=1.0,
        repair_param=2.0,
        failure_effects={"ceiling": CLAMPED},
        repair_effects_trans={"ceiling": NOMINAL},
    )


# ---------------------------------------------------------------------------
# Wiring: external pulses live on the target mirror
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("behaviour", ["external", "external_rep_indep"])
def test_external_pulses_fire_on_the_target_mirror_transitions(behaviour):
    """Spies on the mirror edges see the pulse already applied."""
    system = PycSystem(name="SysMirrorWiring")
    system.add_component(name="S", cls="Store")
    mode = system.add_component(
        **_clamp_mode(
            "m",
            1.0,
            2.0,
            behaviour,
            occ_effects={},
            not_occ_effects_trans={"gate": False},
            occ_effects_trans={"gate": True},
        )
    )
    target = system.comp["S"]
    mirror = target.automata_d["m"]
    seen = []
    for trans in ("m__occ", "m__rep"):
        mirror.get_transition_by_name(trans)._bkd.addSensitiveMethod(
            f"spy_{trans}",
            lambda trans=trans: seen.append(
                (trans, round(system.currentTime(), 3), target.gate.value())
            ),
        )
    mode_rep_seen = []
    if behaviour == "external":
        # The mode automaton repairs first; the target follows by a delay(0)
        # transition. The gate must still be set when the MODE repairs:
        # the clearing pulse belongs to the mirror's repair edge.
        mode.automata_d["m"].get_transition_by_name("rep")._bkd.addSensitiveMethod(
            "spy_mode_rep", lambda: mode_rep_seen.append(target.gate.value())
        )

    system.simulate(PycMCSimulationParam(nb_runs=1, schedule=[0, 3.5], seed=1))

    # occ at 1, mirror rep at 3; mirror occ again at 4 > 3.5. Spies run
    # after the pulse (registration order), so they see its value.
    assert seen == [("m__occ", 1.0, True), ("m__rep", 3.0, False)]
    if behaviour == "external":
        assert mode_rep_seen == [True]


# ---------------------------------------------------------------------------
# Behaviour: the clamped value comes back
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("behaviour", ["internal", "external", "external_rep_indep"])
def test_one_mode_hands_the_value_back_at_repair(behaviour):
    """occ at 1, repaired at 3 (re-occurs at 4, after the last sample).

    Before cod3s#8 ``external`` stayed at 0 after the repair: the pulse
    fired on the mode automaton while the target's held clamp was still
    active, and ``external_rep_indep`` refused the declaration.
    """
    ceiling = _ceiling_timeline(
        [_clamp_mode("cell", 1.0, 2.0, behaviour)], name="SysOneModeHandback"
    )
    assert ceiling == [NOMINAL, NOMINAL, CLAMPED, CLAMPED, NOMINAL, NOMINAL]


@pytest.mark.parametrize("behaviour", ["internal", "external", "external_rep_indep"])
def test_two_modes_clamping_one_variable_with_staggered_occurrence_and_repair(
    behaviour,
):
    """A: occ 1, repaired 3. B: occ 2, repaired 3.25.

    The clamp holds from 1 while either mode holds it: A's repair pulse at
    3 is overwritten by B's held clamp, B's at 3.25 hands the nominal value
    back. Measured at about 2 s on the platform model of cod3s#8, against a
    60 s timeout with a held repair effect.
    """
    ceiling = _ceiling_timeline(
        [
            _clamp_mode("cell", 1.0, 2.0, behaviour),
            _clamp_mode("bms", 2.0, 1.25, behaviour),
        ],
        name="SysTwoModesHandback",
    )
    assert ceiling == [NOMINAL, NOMINAL, CLAMPED, CLAMPED, CLAMPED, NOMINAL]
