"""Phase 4 wiring tests: keys trigger the right engine method calls.

These tests use a hand-rolled :class:`FakeEngine` instead of a real
PyCATSHOO ``PycSystem`` so they (a) run without the C++ singleton, (b) stay
fast (~ms per test instead of seconds), and (c) deterministically assert the
event flow App → engine.

The real engine wiring is exercised by ``tests/isimu/test_engine.py`` against
a small ``PycSystem`` fixture; the integration of the two layers is covered
by smoke tests using :func:`run_isimu` in later phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from cod3s.pycatshoo.isimu.app import ISimuApp


def _trans(comp: str, name: str, end_time: float = 1.0):
    """Stand-in for ``PycTransition`` matching the panels' read pattern."""
    return SimpleNamespace(
        comp_name=comp,
        comp_classname="PycComponent",
        name=name,
        source="ok",
        target="ko",
        end_time=end_time,
    )


@dataclass
class FakeEvent:
    fired_at: float
    transitions: List[Any] = field(default_factory=list)
    vars_before: Dict[str, Any] = field(default_factory=dict)
    vars_after: Dict[str, Any] = field(default_factory=dict)


class FakeEngine:
    """Drop-in replacement for :class:`ISimuEngine` recording every call."""

    def __init__(self) -> None:
        self.calls: List[tuple] = []
        self.history: List[FakeEvent] = []
        self.var_initial: Dict[str, Any] = {"A.flag": False}
        self._t = 0.0
        self._fireable: List[Any] = [_trans("A", "fail"), _trans("B", "fail")]

    # ---- properties consumed by ISimuState.from_engine ----
    @property
    def current_time(self) -> float:
        return self._t

    @property
    def vars_current(self) -> Dict[str, Any]:
        if not self.history:
            return dict(self.var_initial)
        return self.history[-1].vars_after

    @property
    def vars_previous(self) -> Dict[str, Any]:
        if not self.history:
            return dict(self.var_initial)
        return self.history[-1].vars_before

    def fireable(self) -> List[Any]:
        return list(self._fireable)

    def active(self) -> List[Any]:
        return list(self._fireable)

    # ---- lifecycle / actions ----
    def start(self):
        self.calls.append(("start",))
        self._t = 0.0
        self.history = [FakeEvent(fired_at=0.0)]
        return self.history[-1]

    def stop(self) -> None:
        self.calls.append(("stop",))

    def reset(self):
        self.calls.append(("reset",))
        return self.start()

    def step_forward(self):
        self.calls.append(("step_forward",))
        self._t += 1.0
        evt = FakeEvent(
            fired_at=self._t,
            transitions=list(self._fireable),
            vars_before=dict(self.var_initial),
            vars_after={"A.flag": True},
        )
        self.history.append(evt)
        # Once fired, both transitions are no longer fireable.
        self._fireable = []
        return evt

    def step_backward(self) -> List[Any]:
        self.calls.append(("step_backward",))
        if len(self.history) > 1:
            removed = self.history.pop()
            self._t = self.history[-1].fired_at
            self._fireable = list(removed.transitions)
            return list(removed.transitions)
        return []

    def replan(self, **kwargs):
        self.calls.append(("replan", kwargs))
        return None


@pytest.fixture
def fake_engine() -> FakeEngine:
    return FakeEngine()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


async def test_on_mount_starts_engine_and_renders(fake_engine: FakeEngine) -> None:
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()
        # ``start`` must have been called by ``on_mount``.
        assert ("start",) in fake_engine.calls

        from textual.widgets import DataTable

        table = app.query_one("#fireable-table", DataTable)
        assert table.row_count == 2  # two fake fireable transitions


async def test_unmount_stops_engine(fake_engine: FakeEngine) -> None:
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
    # ``stop`` is called exactly once on unmount.
    stop_calls = [c for c in fake_engine.calls if c == ("stop",)]
    assert len(stop_calls) == 1


# ---------------------------------------------------------------------------
# Fire (Enter on a fireable row)
# ---------------------------------------------------------------------------


async def test_fire_action_calls_replan_then_step_forward(
    fake_engine: FakeEngine,
) -> None:
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Focus the fireable table so Enter goes there.
        from textual.widgets import DataTable

        table = app.query_one("#fireable-table", DataTable)
        table.focus()
        await pilot.pause()

        # Press Enter on row 0; expect replan(0) then step_forward.
        await pilot.press("enter")
        # Allow the worker thread + call_from_thread to round-trip.
        for _ in range(10):
            await pilot.pause()
            if any(c[0] == "step_forward" for c in fake_engine.calls):
                break

        kinds = [c[0] for c in fake_engine.calls]
        assert "replan" in kinds
        assert "step_forward" in kinds
        assert kinds.index("replan") < kinds.index("step_forward")


async def test_fire_action_passes_row_index_to_replan(
    fake_engine: FakeEngine,
) -> None:
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()

        from textual.widgets import DataTable

        table = app.query_one("#fireable-table", DataTable)
        table.focus()
        # Move cursor to row 1 (the second transition).
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("enter")
        for _ in range(10):
            await pilot.pause()
            if any(c[0] == "replan" for c in fake_engine.calls):
                break

        replan_calls = [c for c in fake_engine.calls if c[0] == "replan"]
        assert replan_calls, "replan was not called"
        assert replan_calls[0][1] == {"trans_id": 1}


# ---------------------------------------------------------------------------
# Step backward
# ---------------------------------------------------------------------------


async def test_b_binding_calls_step_backward(fake_engine: FakeEngine) -> None:
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("b")
        for _ in range(10):
            await pilot.pause()
            if any(c == ("step_backward",) for c in fake_engine.calls):
                break
        assert ("step_backward",) in fake_engine.calls


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


async def test_r_binding_calls_reset(fake_engine: FakeEngine) -> None:
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("r")
        for _ in range(10):
            await pilot.pause()
            if any(c == ("reset",) for c in fake_engine.calls):
                break
        assert ("reset",) in fake_engine.calls


# ---------------------------------------------------------------------------
# Engine-less safety
# ---------------------------------------------------------------------------


async def test_actions_are_noops_when_engine_is_none() -> None:
    """Pressing fire/back/reset without an engine must not crash."""
    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("b")
        await pilot.press("r")
        await pilot.pause()
    # No exception means we're good — tested by run_test exiting cleanly.
