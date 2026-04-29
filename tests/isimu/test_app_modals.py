"""Phase 6 tests: export and re-plan modals end-to-end.

These tests use a :class:`FakeEngine` (same shape as ``test_app_interaction``)
so they run fast without PyCATSHOO. Modal interactions are driven via
``ModalScreen.dismiss(...)`` directly because button-clicking through Pilot
in Textual 8.x is brittle for compound layouts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from cod3s.pycatshoo.isimu.app import ISimuApp
from cod3s.pycatshoo.isimu.modals import ExportModal, ReplanModal


def _trans(comp: str, name: str, end_time: float = 1.0):
    return SimpleNamespace(
        comp_name=comp,
        comp_classname="PycComponent",
        name=name,
        source="ok",
        target="ko",
        end_time=end_time,
        model_dump=lambda: {
            "cls": "PycTransition",
            "comp_name": comp,
            "comp_classname": "PycComponent",
            "name": name,
            "source": "ok",
            "target": "ko",
            "occ_law": {"cls": "DelayOccDistribution", "time": end_time},
            "is_interruptible": False,
        },
    )


@dataclass
class FakeEvent:
    fired_at: float
    transitions: List[Any] = field(default_factory=list)
    vars_before: Dict[str, Any] = field(default_factory=dict)
    vars_after: Dict[str, Any] = field(default_factory=dict)


class FakeEngine:
    def __init__(self) -> None:
        self.calls: List[tuple] = []
        self.history: List[FakeEvent] = []
        self.var_initial: Dict[str, Any] = {}
        self._t = 0.0
        self._fireable = [_trans("A", "fail"), _trans("B", "fail")]

    @property
    def current_time(self) -> float:
        return self._t

    @property
    def vars_current(self) -> Dict[str, Any]:
        return {}

    @property
    def vars_previous(self) -> Dict[str, Any]:
        return {}

    def fireable(self):
        return list(self._fireable)

    def active(self):
        return list(self._fireable)

    def start(self):
        self.calls.append(("start",))
        evt = FakeEvent(fired_at=0.0)
        self.history = [evt]
        return evt

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
        )
        self.history.append(evt)
        return evt

    def step_backward(self):
        self.calls.append(("step_backward",))
        return []

    def replan(self, **kwargs):
        self.calls.append(("replan", kwargs))


@pytest.fixture
def fake_engine() -> FakeEngine:
    eng = FakeEngine()
    # Simulate one fired step so the export has rows.
    eng.start()
    eng.step_forward()
    return eng


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


async def test_e_binding_pushes_export_modal(fake_engine: FakeEngine) -> None:
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        # Top of the screen stack must now be the modal.
        assert isinstance(app.screen, ExportModal)


async def test_export_modal_writes_csv_and_json(
    fake_engine: FakeEngine, tmp_path: Path
) -> None:
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()
        # ``on_mount`` resets the engine history (start() rebuilds it). Take
        # one step so the history has a fireable event to export.
        fake_engine.step_forward()
        await pilot.press("e")
        await pilot.pause()

        # Programmatic dismiss with a real path.
        target = tmp_path / "history"
        modal = app.screen
        assert isinstance(modal, ExportModal)
        modal.dismiss(target)

        # Wait for the export worker + call_from_thread to finish.
        for _ in range(30):
            await pilot.pause()
            if (target.with_suffix(".csv")).exists():
                break

        csv_path = target.with_suffix(".csv")
        json_path = target.with_suffix(".json")
        assert csv_path.exists(), f"{csv_path} was not written"
        assert json_path.exists(), f"{json_path} was not written"

        # JSON contains the history we built (bootstrap + one fired step).
        payload = json.loads(json_path.read_text())
        last = payload["history"][-1]
        assert last["transitions"][0]["comp_name"] == "A"


async def test_export_cancelled_writes_nothing(
    fake_engine: FakeEngine, tmp_path: Path
) -> None:
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ExportModal)
        modal.dismiss(None)
        await pilot.pause()

    # No file should have appeared.
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# Re-plan
# ---------------------------------------------------------------------------


async def _focus_fireable(app, pilot):
    """Helper: ensure the fireable DataTable has focus before pressing ``p``.

    ``p`` is bound at the FireablePanel scope, so it only fires when that
    panel's DataTable has keyboard focus. The default focus may land on a
    different widget depending on the App layout, so we always focus
    explicitly in tests.
    """
    from textual.widgets import DataTable

    table = app.query_one("#fireable-table", DataTable)
    table.focus()
    await pilot.pause()


async def test_p_binding_pushes_replan_modal(fake_engine: FakeEngine) -> None:
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()
        await _focus_fireable(app, pilot)
        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app.screen, ReplanModal)


async def test_replan_modal_title_carries_transition_name(
    fake_engine: FakeEngine,
) -> None:
    """The modal title encodes ``Replan transition {comp}.{trans_name}``."""
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()
        await _focus_fireable(app, pilot)
        # Cursor is on row 0 = first fireable transition (A.fail).
        await pilot.press("p")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ReplanModal)
        # The title is set by the App from message.trans.{comp_name,name}.
        assert modal._title == "Replan transition A.fail"


async def test_replan_modal_dismiss_calls_engine_replan(
    fake_engine: FakeEngine,
) -> None:
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()
        await _focus_fireable(app, pilot)
        # Move cursor to row 1 (second fireable: B.fail) so the message
        # carries idx=1.
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("p")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, ReplanModal)
        # The simplified modal returns just a date (Optional[float]).
        modal.dismiss(12.5)

        for _ in range(30):
            await pilot.pause()
            if any(c[0] == "replan" for c in fake_engine.calls):
                break

        replan_calls = [c for c in fake_engine.calls if c[0] == "replan"]
        assert replan_calls, "engine.replan was not called"
        assert replan_calls[-1][1] == {"trans_id": 1, "date": 12.5}


async def test_replan_cancelled_does_not_call_engine(
    fake_engine: FakeEngine,
) -> None:
    app = ISimuApp(engine=fake_engine)
    async with app.run_test() as pilot:
        await pilot.pause()
        await _focus_fireable(app, pilot)
        await pilot.press("p")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ReplanModal)
        before = list(fake_engine.calls)
        modal.dismiss(None)
        await pilot.pause()
    # No new replan call.
    assert [c for c in fake_engine.calls if c[0] == "replan"] == [
        c for c in before if c[0] == "replan"
    ]


# ---------------------------------------------------------------------------
# Engine-less safety
# ---------------------------------------------------------------------------


async def test_e_and_p_are_noops_when_engine_is_none() -> None:
    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.press("p")
        await pilot.pause()
        # No modal should have been pushed; the active screen is the main one.
        from textual.screen import ModalScreen

        assert not isinstance(app.screen, ModalScreen)
