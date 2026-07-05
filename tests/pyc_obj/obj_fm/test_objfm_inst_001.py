"""ObjFMInst core semantics — interactive walkthrough.

Pins the design decisions of ADR 2026-07-05 (cod3s-specs,
``MBSA/ADR-2026-07-05-objfm-inst-on-demand-law.md``):

* one Bernoulli draw per demand front (anti-Zeno: the ``not_occ`` state
  absorbs the front, no re-draw while the demand holds),
* re-arm through an inst p=1 transition guarded by NOT failure_cond,
* repair stays exponential and is guarded by repair_cond,
* re-fire immediately after repair when the demand still holds,
* out-state monitoring masks (success branch + re-arm silenced).

Note on manual variable toggles: a bare ``setValue`` from Python does
not refresh PyCATSHOO's scheduler — conditions are re-evaluated at the
next ``stepForward``. Each toggle below is therefore followed by one
(empty-fired) step. In Monte-Carlo runs conditions change through
transitions and sensitive methods, so this artefact never shows up.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem


class InstEquipment001(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.demand = self.addVariable("demand", Pyc.TVarType.t_bool, False)
        self.failed = self.addVariable("failed", Pyc.TVarType.t_bool, False)
        self.failed.setReinitialized(True)


@pytest.fixture(scope="module")
def the_system():
    system = PycSystem(name="SysInst001")
    system.add_component(name="E1", cls="InstEquipment001")
    system.add_component(
        cls="ObjFMInst",
        fm_name="miss",
        targets=["E1"],
        failure_cond=lambda: system.comp["E1"].demand.value() is True,
        failure_effects={"failed": True},
        failure_param=0.3,
        repair_param=0.1,
    )
    yield system


def _active_states(aut):
    return {
        name
        for name in ("rep", "occ", "not_occ")
        if aut.get_state_by_name(name)._bkd.isActive()
    }


def _draw_index(system):
    fire = system.isimu_fireable_transitions()
    return next(
        i for i, t in enumerate(fire) if t is not None and t.name.startswith("occ")
    )


def test_full_demand_cycle(the_system):
    system = the_system
    eq = system.comp["E1"]
    fm_comp = system.comp["E1__miss"]
    aut = fm_comp.automata_d["miss"]

    system.isimu_start()

    # Initial: armed, nothing fireable (no demand).
    assert _active_states(aut) == {"rep"}
    assert [t for t in system.isimu_fireable_transitions() if t] == []

    # Demand front -> the draw is pending with the [occ, not_occ]
    # branches carrying [gamma, 1 - gamma].
    eq.demand.setValue(True)
    system.isimu_step_forward()
    fire = system.isimu_fireable_transitions()
    draws = [t for t in fire if t is not None]
    assert len(draws) == 1
    assert draws[0].name == "occ"
    assert [b.state for b in draws[0].target] == ["occ", "not_occ"]
    assert draws[0].target[0].prob == pytest.approx(0.3)
    assert draws[0].target[1].prob == pytest.approx(0.7)

    # Force the success branch (not_occ): no effect applied.
    system.isimu_set_transition(_draw_index(system), state_index=1)
    fired = [t.name for t in system.isimu_step_forward()]
    assert fired == ["occ"]
    assert _active_states(aut) == {"not_occ"}
    assert eq.failed.value() is False

    # Anti-Zeno: demand still true -> nothing fireable, no re-draw.
    assert [t for t in system.isimu_fireable_transitions() if t] == []

    # Demand falls -> the deterministic re-arm (inst p=1) fires on the
    # next step without any branch resolution.
    eq.demand.setValue(False)
    system.isimu_step_forward()  # scheduler refresh (manual toggle)
    fired = [t.name for t in system.isimu_step_forward()]
    assert fired == ["not_occ"]
    assert _active_states(aut) == {"rep"}

    # New front = new draw (one front, one draw). Force occ this time.
    eq.demand.setValue(True)
    system.isimu_step_forward()
    system.isimu_set_transition(_draw_index(system), state_index=0)
    fired = [t.name for t in system.isimu_step_forward()]
    assert fired == ["occ"]
    assert _active_states(aut) == {"occ"}
    assert eq.failed.value() is True

    # Repair: exponential (end_time = inf until replanned).
    fire = system.isimu_fireable_transitions()
    reps = [(i, t) for i, t in enumerate(fire) if t and t.name.startswith("rep")]
    assert len(reps) == 1
    assert reps[0][1].end_time == float("inf")
    system.isimu_set_transition(reps[0][0], date=5.0)
    fired = [t.name for t in system.isimu_step_forward()]
    assert fired == ["rep"]
    assert system.currentTime() == 5.0
    assert _active_states(aut) == {"rep"}
    # Reinitialized-variable convention: resting value restored.
    assert eq.failed.value() is False

    # Re-fire under maintained demand: the repaired mode is
    # re-solicited immediately (ADR decision, documented behaviour).
    fire = system.isimu_fireable_transitions()
    pending = [t for t in fire if t is not None]
    assert len(pending) == 1
    assert pending[0].name == "occ"
    assert isinstance(pending[0].target, list)

    system.isimu_stop()


def test_monitor_masks(the_system):
    """Success branch and re-arm are masked out of sequence monitoring."""
    aut = the_system.comp["E1__miss"].automata_d["miss"]
    assert aut.get_transition_by_name("occ")._bkd.monitoredOutStateMask() == "#occ$"
    assert aut.get_transition_by_name("not_occ")._bkd.monitoredOutStateMask() == "#$^"
    # reapply_monitor_masks is idempotent (the study runner calls it
    # after monitorTransition patterns).
    the_system.comp["E1__miss"].reapply_monitor_masks()
    assert aut.get_transition_by_name("occ")._bkd.monitoredOutStateMask() == "#occ$"
