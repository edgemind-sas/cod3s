"""Date-driven stepping: ``isimu_next_due``, the infinite-date guard, ``step_to``.

The interactive simulator has two stepping primitives and each is missing what
the other has. ``stepForward`` lands exactly on events and records them, but on
a model whose continuous variables are the only thing moving it has nothing to
advance towards and does not move at all. ``stepInteractive`` advances to any
date and integrates the PDMP, but it runs THROUGH the events in its span.

``isimu_step_to`` alternates between them. What is asserted here is that the
alternation keeps what each primitive is good at, and the one thing it cannot
recover: a watched threshold, whose date nothing knows in advance.

The model, on purpose small enough that every number below is exact:

    level' = rate,  level(0) = 0,  rate = 2
    P.throttle  defer(2.5)   -> rate 1          (a DATED event)
    T.alarm     level >= 7                      (a WATCHED threshold, at t=4.5)
    W.break     expo(0.05)                      (never auto-sampled: end = inf)
"""

from __future__ import annotations

import Pycatshoo as Pyc
import pytest

from cod3s import terminate_session
from cod3s.pycatshoo.component import PycComponent
from cod3s.pycatshoo.isimu.engine import ISimuEngine
from cod3s.pycatshoo.system import PycSystem

THROTTLE_DATE = 2.5
ALARM_LEVEL = 7.0
ALARM_DATE = 4.5  # 2*2.5 = 5, then +1 per unit -> 7 at t=4.5


class _StepToTank(PycComponent):
    """One ODE, one dated transition, one watched threshold, one expo law.

    A ``PycComponent`` rather than a bare ``Pyc.CComponent``: registering in
    ``system.comp`` is what puts its variables in reach of the engine's
    snapshot, and a snapshot that silently comes back empty would make the
    per-stop assertions below vacuous.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.p_delay = self.addVariable("delay", Pyc.TVarType.t_double, THROTTLE_DATE)
        self.p_lambda = self.addVariable("lambda", Pyc.TVarType.t_double, 0.05)
        self.v_rate = self.addVariable("rate", Pyc.TVarType.t_double, 2.0)
        self.v_level = self.addVariable("level", Pyc.TVarType.t_double, 0.0)

        self.a_pump = self.addAutomaton("pump")
        self.st_full = self.addState("pump", "FULL", 1)
        self.st_half = self.addState("pump", "HALF", 0)
        self.setInitState("FULL")
        tr = self.st_full.addTransition("throttle")
        tr.setDistLaw(Pyc.TLawType.defer, self.p_delay)
        tr.addTarget(self.st_half, Pyc.TTransType.trans)
        self.a_pump.addSensitiveMethod("update_rate")

        self.a_alarm = self.addAutomaton("alarm")
        self.st_low = self.addState("alarm", "LOW", 0)
        self.st_high = self.addState("alarm", "HIGH", 1)
        self.setInitState("LOW")
        tr_alarm = self.st_low.addTransition("reach_high")
        tr_alarm.setCondition(self.is_high)
        tr_alarm.addTarget(self.st_high, Pyc.TTransType.trans)

        self.a_wear = self.addAutomaton("wear")
        self.st_ok = self.addState("wear", "OK", 1)
        self.st_ko = self.addState("wear", "KO", 0)
        self.setInitState("OK")
        tr_wear = self.st_ok.addTransition("break")
        tr_wear.setDistLaw(Pyc.TLawType.expo, self.p_lambda)
        tr_wear.addTarget(self.st_ko, Pyc.TTransType.fault)

        mgr = self.system().PDMPManager("pdmp")
        mgr.addODEVariable(self.v_level)
        mgr.addEquationMethod("equation", self)
        mgr.addWatchedTransition(tr_alarm)

    def is_high(self) -> bool:
        return self.v_level.value() >= ALARM_LEVEL

    def update_rate(self) -> None:
        state = self.a_pump.currentState().name().split(".")[-1]
        self.v_rate.setValue(2.0 if state == "FULL" else 1.0)

    def equation(self) -> None:
        self.v_level.setDvdtODE(self.v_rate.value())


@pytest.fixture(scope="module")
def tank_system():
    """One PDMP system for the module: PyCATSHOO allows a single live one."""
    system = PycSystem(name="StepToTest")
    system.addPDMPManager("pdmp")
    tank = _StepToTank("T")
    system.tank = tank  # so tests can read the ODE variable back
    yield system
    system.isimu_stop()
    terminate_session()


@pytest.fixture()
def started(tank_system):
    """A fresh interactive session per test -- isimu_start is idempotent."""
    tank_system.isimu_start()
    return tank_system


# ----------------------------------------------------------------- next_due
def test_next_due_is_the_earliest_finite_end_time(started) -> None:
    # The expo law carries an infinite end-time and must not win the minimum.
    assert started.isimu_next_due() == pytest.approx(THROTTLE_DATE)


def test_next_due_is_none_when_every_end_time_is_infinite(started) -> None:
    started.isimu_step_to(THROTTLE_DATE)  # consume the only dated transition
    assert started.isimu_next_due() is None


# ------------------------------------------------------- the infinite guard
def test_step_forward_refuses_an_infinite_end_time(started) -> None:
    started.isimu_step_to(THROTTLE_DATE)
    assert started.isimu_next_due() is None
    before = started.currentTime()

    with pytest.warns(UserWarning, match="infinite"):
        fired = started.isimu_step_forward()

    # Refused, not run: the clock is untouched and nothing is reported fired.
    assert fired == []
    assert started.currentTime() == pytest.approx(before)


def test_step_to_advances_where_step_forward_refuses(started) -> None:
    started.isimu_step_to(THROTTLE_DATE)
    stops = started.isimu_step_to(THROTTLE_DATE + 1.0)

    assert [kind for kind, _, _ in stops] == ["grid"]
    assert started.currentTime() == pytest.approx(THROTTLE_DATE + 1.0)


# ------------------------------------------------------------------ step_to
def test_step_to_lands_exactly_on_a_dated_event_off_the_grid(started) -> None:
    # The grid point is 3.0; the event is due at 2.5, between two grid points.
    stops = started.isimu_step_to(3.0)

    kinds = [kind for kind, _, _ in stops]
    assert kinds == ["event", "grid"]

    (_, event_at, fired), (_, grid_at, _) = stops
    assert event_at == pytest.approx(THROTTLE_DATE)
    assert grid_at == pytest.approx(3.0)
    assert [trans.name for trans in fired] == ["throttle"]


def test_step_to_integrates_the_two_stretches_at_their_own_rate(started) -> None:
    started.isimu_step_to(3.0)
    # 2.5 units at rate 2, then 0.5 at rate 1.
    assert started.tank.v_level.value() == pytest.approx(2 * 2.5 + 1 * 0.5)


def test_step_to_records_the_event_in_the_sequence(started) -> None:
    started.isimu_step_to(3.0)

    names = [trans.name for trans in started.isimu_sequence.transitions]
    assert names == ["throttle"]


def test_step_to_is_grid_only_when_nothing_is_due(started) -> None:
    started.isimu_step_to(2.0)  # stops short of the event at 2.5

    assert started.currentTime() == pytest.approx(2.0)
    assert started.tank.v_level.value() == pytest.approx(4.0)


# ------------------------------------------------- observing AT each stop
def test_on_stop_observes_the_state_at_the_stop_not_at_the_end(started) -> None:
    """The returned list is complete when the call returns, so a caller
    reading the model in a loop over it sees the state at ``date`` for every
    row. ``on_stop`` is what makes a per-stop reading possible, and the two
    readings must differ here or the callback would be pointless.
    """
    at_stop = []
    started.isimu_step_to(
        3.0,
        on_stop=lambda kind, at, _: at_stop.append(
            (kind, started.tank.v_level.value())
        ),
    )
    after_the_call = started.tank.v_level.value()

    assert [kind for kind, _ in at_stop] == ["event", "grid"]
    # 2.5 units at rate 2 when the event lands, then 0.5 more at rate 1.
    assert at_stop[0][1] == pytest.approx(5.0)
    assert at_stop[1][1] == pytest.approx(5.5)
    # ... and reading after the call would have reported 5.5 for BOTH rows.
    assert after_the_call == pytest.approx(5.5)
    assert at_stop[0][1] != pytest.approx(after_the_call)


def test_engine_snapshots_each_stop_separately(tank_system) -> None:
    engine = ISimuEngine(tank_system)
    engine.start()

    events = engine.step_to(3.0)

    assert len(events) == 2
    # The event stop and the grid stop are different states of the model.
    assert events[0].vars_after["T.level"] != events[1].vars_after["T.level"]
    assert events[0].vars_after["T.level"] == pytest.approx(5.0)
    assert events[1].vars_after["T.level"] == pytest.approx(5.5)
    # Chained: what the grid stop came from is what the event stop reached.
    assert events[1].vars_before == events[0].vars_after


# --------------------------------------------- the limit that is not closed
def test_a_watched_threshold_is_crossed_without_a_stop(started) -> None:
    """A threshold has no date until its condition turns true, so step_to
    cannot land on it. It is crossed inside a span and only locatable between
    two grid points -- the documented residual, asserted so it stays visible.
    """
    started.isimu_step_to(4.0)
    assert started.tank.a_alarm.currentState().name().endswith("LOW")

    stops = started.isimu_step_to(5.0)  # the crossing is at 4.5, inside

    assert [kind for kind, _, _ in stops] == ["grid"]
    assert started.tank.a_alarm.currentState().name().endswith("HIGH")
    # Nothing was recorded for it: the bracket is all the caller gets.
    assert started.isimu_sequence.transitions[-1].name != "reach_high"


# ------------------------------------------------------------------- engine
def test_engine_step_to_records_one_event_per_stop(tank_system) -> None:
    engine = ISimuEngine(tank_system)
    engine.start()

    events = engine.step_to(3.0)

    assert [evt.kind for evt in events] == ["event", "grid"]
    assert events[0].fired_at == pytest.approx(THROTTLE_DATE)
    assert events[-1] is engine.history[-1]


def test_engine_can_step_forward_reports_the_guard(tank_system) -> None:
    engine = ISimuEngine(tank_system)
    engine.start()
    assert engine.can_step_forward is True

    engine.step_to(THROTTLE_DATE)
    assert engine.can_step_forward is False


def test_step_to_refuses_a_date_in_the_past(started) -> None:
    started.isimu_step_to(2.0)

    with pytest.raises(ValueError, match="already at"):
        started.isimu_step_to(1.0)

    # Refused before anything moved.
    assert started.currentTime() == pytest.approx(2.0)
