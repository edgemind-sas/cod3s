"""Playback: the second way the TUI advances the clock.

Firing a transition answers "what happens next"; playback answers "what do the
continuous variables do between the events". A model whose continuous
variables are the only thing moving offers no transition to fire, so before
playback there was nothing to press and the session sat at t=0.

These tests use a fake engine, like ``test_app_interaction``: what is asserted
is the WIRING -- which engine call a key produces, with which argument, and
what the app refuses -- not the physics, which ``test_step_to`` covers against
a real PyCATSHOO system.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from cod3s.pycatshoo.isimu.app import ISimuApp
from cod3s.pycatshoo.isimu.modals import IntegrationModal, ObservationStepModal


@dataclass
class PlayEvent:
    fired_at: float
    transitions: List[Any] = field(default_factory=list)
    vars_before: Dict[str, Any] = field(default_factory=dict)
    vars_after: Dict[str, Any] = field(default_factory=dict)
    kind: str = "event"


class FakePDMPManager:
    def __init__(self) -> None:
        self.dt_max: Optional[float] = None
        self.dt_cond: Optional[float] = None

    def setDtMax(self, value: float) -> None:  # noqa: N802 (engine spelling)
        self.dt_max = value

    def setDtCond(self, value: float) -> None:  # noqa: N802 (engine spelling)
        self.dt_cond = value


class FakeSystem:
    def __init__(self, manager: Optional[FakePDMPManager]) -> None:
        self._manager = manager

    def currentPDMPManager(self):  # noqa: N802 (engine spelling)
        return self._manager


class PlayEngine:
    """Engine fake whose ``step_to`` records the dates it was asked for."""

    def __init__(self, manager: Optional[FakePDMPManager] = None) -> None:
        self.calls: List[tuple] = []
        self.history: List[PlayEvent] = []
        self.var_initial: Dict[str, Any] = {"T.level": 0.0}
        self._t = 0.0
        self.system = FakeSystem(manager)
        self.raise_on_step = False

    @property
    def current_time(self) -> float:
        return self._t

    @property
    def vars_current(self) -> Dict[str, Any]:
        return self.history[-1].vars_after if self.history else dict(self.var_initial)

    @property
    def vars_previous(self) -> Dict[str, Any]:
        return self.history[-1].vars_before if self.history else dict(self.var_initial)

    def fireable(self) -> List[Any]:
        return []

    def active(self) -> List[Any]:
        return []

    def start(self):
        self.calls.append(("start",))
        self._t = 0.0
        self.history = [PlayEvent(fired_at=0.0)]
        return self.history[-1]

    def stop(self) -> None:
        self.calls.append(("stop",))

    def reset(self):
        self.calls.append(("reset",))
        return self.start()

    def step_to(self, date: float) -> List[PlayEvent]:
        self.calls.append(("step_to", date))
        if self.raise_on_step:
            raise RuntimeError("engine refused")
        self._t = date
        evt = PlayEvent(fired_at=date, kind="grid", vars_after={"T.level": date})
        self.history.append(evt)
        return [evt]

    def step_backward(self) -> List[Any]:
        self.calls.append(("step_backward",))
        return []


@pytest.fixture
def play_engine() -> PlayEngine:
    return PlayEngine()


async def _play_briefly(app, pilot, seconds: float = 0.2) -> None:
    await pilot.press("space")
    await pilot.pause()
    await asyncio.sleep(seconds)
    await pilot.pause()


# ---------------------------------------------------------------------------
# Play / pause
# ---------------------------------------------------------------------------
async def test_space_starts_playback_and_advances_by_the_observation_step(
    play_engine: PlayEngine,
) -> None:
    app = ISimuApp(engine=play_engine)
    app.wall_period = 0.05
    app.observation_step = 0.25

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.is_playing is False

        await _play_briefly(app, pilot, 0.2)
        assert app.is_playing is True

        dates = [call[1] for call in play_engine.calls if call[0] == "step_to"]
        assert dates, "playback produced no step"
        # Each tick advances by the observation step, from the previous date.
        assert dates[0] == pytest.approx(0.25)
        for previous, following in zip(dates, dates[1:]):
            assert following == pytest.approx(previous + 0.25)

        await pilot.press("space")
        await pilot.pause()
        assert app.is_playing is False


async def test_pausing_stops_producing_steps(play_engine: PlayEngine) -> None:
    app = ISimuApp(engine=play_engine)
    app.wall_period = 0.05

    async with app.run_test() as pilot:
        await _play_briefly(app, pilot, 0.15)
        await pilot.press("space")
        await pilot.pause()

        after_pause = len(play_engine.calls)
        await asyncio.sleep(0.15)
        await pilot.pause()

        assert len(play_engine.calls) == after_pause


# ---------------------------------------------------------------------------
# Wall-clock speed
# ---------------------------------------------------------------------------
async def test_speed_keys_halve_and_double_the_wall_period(
    play_engine: PlayEngine,
) -> None:
    app = ISimuApp(engine=play_engine)

    async with app.run_test() as pilot:
        await pilot.pause()
        start = app.wall_period

        await pilot.press("plus")
        assert app.wall_period == pytest.approx(start / 2)

        await pilot.press("minus")
        await pilot.press("minus")
        assert app.wall_period == pytest.approx(start * 2)


async def test_wall_period_is_clamped(play_engine: PlayEngine) -> None:
    app = ISimuApp(engine=play_engine)

    async with app.run_test() as pilot:
        await pilot.pause()
        for _ in range(12):
            await pilot.press("plus")
        assert app.wall_period == pytest.approx(app.WALL_PERIOD_MIN)

        for _ in range(12):
            await pilot.press("minus")
        assert app.wall_period == pytest.approx(app.WALL_PERIOD_MAX)


async def test_speed_change_while_playing_keeps_playing(
    play_engine: PlayEngine,
) -> None:
    app = ISimuApp(engine=play_engine)
    app.wall_period = 0.05

    async with app.run_test() as pilot:
        await _play_briefly(app, pilot, 0.1)
        await pilot.press("minus")
        await pilot.pause()

        # The timer is REPLACED, not adjusted: playback must survive that.
        assert app.is_playing is True
        assert app.wall_period == pytest.approx(0.1)
        await pilot.press("space")  # leave the app paused, so teardown is quick


# ---------------------------------------------------------------------------
# The observation step and the integration knobs are not the same thing
# ---------------------------------------------------------------------------
async def test_d_opens_the_observation_step_modal_and_applies_it(
    play_engine: PlayEngine,
) -> None:
    app = ISimuApp(engine=play_engine)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, ObservationStepModal)

        app.screen.dismiss(0.05)
        await pilot.pause()
        assert app.observation_step == pytest.approx(0.05)


async def test_observation_modal_rejects_a_non_positive_step(
    play_engine: PlayEngine,
) -> None:
    app = ISimuApp(engine=play_engine)

    async with app.run_test() as pilot:
        await pilot.pause()
        before = app.observation_step
        await pilot.press("d")
        await pilot.pause()

        # A step of zero freezes the clock and a negative one asks the engine
        # to go backwards, which it refuses: the modal cancels instead.
        app.screen.query_one("#observation-step").value = "0"
        app.screen._submit()
        await pilot.pause()

        assert app.observation_step == pytest.approx(before)


async def test_i_applies_the_pdmp_knobs_to_the_manager() -> None:
    manager = FakePDMPManager()
    engine = PlayEngine(manager=manager)
    app = ISimuApp(engine=engine)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, IntegrationModal)

        app.screen.dismiss({"dt_max": 0.01, "dt_cond": 1e-7})
        await pilot.pause()

        assert manager.dt_max == pytest.approx(0.01)
        assert manager.dt_cond == pytest.approx(1e-7)
        # The observation step is a different setting and must not follow.
        assert app.observation_step == pytest.approx(app.DEFAULT_OBSERVATION_STEP)


async def test_i_says_so_when_nothing_is_integrated() -> None:
    engine = PlayEngine(manager=None)
    app = ISimuApp(engine=engine)
    notes: List[tuple] = []

    async with app.run_test() as pilot:
        await pilot.pause()
        app.notify = lambda message, **kwargs: notes.append((message, kwargs))

        app._on_integration({"dt_max": 0.01, "dt_cond": None})
        await pilot.pause()

        # Accepting knobs on a system with no PDMP would report a setting that
        # governs nothing.
        assert notes and "No PDMP manager" in notes[0][0]


# ---------------------------------------------------------------------------
# What playback must refuse
# ---------------------------------------------------------------------------
async def test_step_back_is_refused_after_playback(play_engine: PlayEngine) -> None:
    app = ISimuApp(engine=play_engine)
    app.wall_period = 0.05
    notes: List[tuple] = []

    async with app.run_test() as pilot:
        await _play_briefly(app, pilot, 0.2)
        app.notify = lambda message, **kwargs: notes.append((message, kwargs))

        await pilot.press("b")
        await pilot.pause()

        # A grid point is not in the sequence, so stepping back would land at
        # the start of the session rather than at the previous grid point.
        assert ("step_backward",) not in play_engine.calls
        assert notes and "not available after playback" in notes[0][0]
        assert app.is_playing is False


async def test_a_failing_step_pauses_and_reports(play_engine: PlayEngine) -> None:
    app = ISimuApp(engine=play_engine)
    app.wall_period = 0.05
    notes: List[tuple] = []

    async with app.run_test() as pilot:
        await pilot.pause()
        app.notify = lambda message, **kwargs: notes.append((message, kwargs))
        play_engine.raise_on_step = True

        await _play_briefly(app, pilot, 0.2)

        assert app.is_playing is False
        assert notes and "Playback stopped" in notes[0][0]


async def test_reset_stops_playback(play_engine: PlayEngine) -> None:
    app = ISimuApp(engine=play_engine)
    app.wall_period = 0.05

    async with app.run_test() as pilot:
        await _play_briefly(app, pilot, 0.1)
        await pilot.press("r")
        await pilot.pause()

        assert app.is_playing is False


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
async def test_status_line_carries_the_three_settings(
    play_engine: PlayEngine,
) -> None:
    app = ISimuApp(engine=play_engine)
    app.observation_step = 0.5
    app.wall_period = 0.25

    async with app.run_test() as pilot:
        await pilot.pause()
        assert "step=0.5" in app.sub_title
        assert "every 0.25s" in app.sub_title
        assert "[paused]" in app.sub_title

        await pilot.press("space")
        await pilot.pause()
        assert "[playing]" in app.sub_title
        await pilot.press("space")
