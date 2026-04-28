"""Tests for :class:`ISimuEngine` against a real ``PycSystem`` fixture."""

from __future__ import annotations

from cod3s.pycatshoo.isimu.engine import FiredEvent, ISimuEngine
from cod3s.pycatshoo.isimu.grouping import group_fires_together


def test_start_initializes_history_and_initials(small_system) -> None:
    engine = ISimuEngine(small_system)
    evt = engine.start()

    assert isinstance(evt, FiredEvent)
    assert engine.history == [evt]
    # Initial snapshot captures the declared values.
    assert engine.var_initial == {
        "A.flag": False,
        "A.counter": 0,
        "B.flag": False,
        "B.counter": 0,
    }
    # Bootstrap step at t=0 fires no transition for our delay(1) model.
    assert evt.fired_at == 0.0
    assert evt.transitions == []


def test_fireable_after_start_lists_two_delay_transitions(small_system) -> None:
    engine = ISimuEngine(small_system)
    engine.start()

    fireable = engine.fireable()
    # Both deterministic delay(1.0) transitions are visible together.
    fireable_only = [t for t in fireable if t is not None]
    assert len(fireable_only) == 2
    end_times = {t.end_time for t in fireable_only}
    assert end_times == {1.0}


def test_fires_together_groups_share_end_time(small_system) -> None:
    engine = ISimuEngine(small_system)
    engine.start()

    fireable = engine.fireable()
    grouped = group_fires_together(fireable, selected_idx=0)
    # Both transitions share end_time=1.0 → they fire together.
    fireable_indices = {i for i, t in enumerate(fireable) if t is not None}
    assert grouped == fireable_indices


def test_step_forward_fires_both_transitions(small_system) -> None:
    engine = ISimuEngine(small_system)
    engine.start()

    evt = engine.step_forward()
    assert evt.fired_at == 1.0
    # Both delay(1) transitions fire together at t=1.0.
    assert len(evt.transitions) == 2
    fired_names = {(t.comp_name, t.name) for t in evt.transitions}
    assert fired_names == {("A", "fail"), ("B", "fail")}
    # History grew by exactly one event.
    assert len(engine.history) == 2


def test_var_previous_and_current_after_step(small_system) -> None:
    engine = ISimuEngine(small_system)
    engine.start()
    engine.step_forward()

    # Variables we declared (flag/counter) didn't change because the
    # automaton transitions had no `effect` clause; PyCATSHOO only mutated
    # the automaton state. var_previous and var_current must agree on those.
    assert engine.vars_current["A.flag"] is False
    assert engine.vars_current["B.flag"] is False
    # vars_previous is the snapshot at the entry of the last step.
    assert engine.vars_previous["A.counter"] == 0


def test_step_backward_undoes_last_event(small_system) -> None:
    engine = ISimuEngine(small_system)
    engine.start()
    engine.step_forward()
    assert len(engine.history) == 2

    retired = engine.step_backward()
    # The two delay(1) transitions are retired together.
    assert len(retired) == 2
    assert len(engine.history) == 1


def test_reset_returns_to_t_zero(small_system) -> None:
    engine = ISimuEngine(small_system)
    engine.start()
    engine.step_forward()
    assert engine.current_time == 1.0

    engine.reset()
    assert engine.current_time == 0.0
    assert len(engine.history) == 1  # the bootstrap event only


def test_engine_is_idempotent_across_starts(small_system) -> None:
    """Calling ``start()`` twice should reset state, not crash."""
    engine = ISimuEngine(small_system)
    engine.start()
    engine.step_forward()
    engine.start()  # restart from scratch

    assert engine.current_time == 0.0
    assert len(engine.history) == 1
