"""Phase 3 layout tests: the app mounts, every panel exists, ``q`` quits.

These tests do *not* exercise the engine. They run with ``engine=None`` so
the ``ISimuApp`` renders an empty :class:`ISimuState` — no PyCATSHOO required,
no singleton interaction, fast feedback for the layout / wiring."""

from __future__ import annotations

from cod3s.pycatshoo.isimu.app import ISimuApp
from cod3s.pycatshoo.isimu.panels import (
    ComponentsPanel,
    FireablePanel,
    HistoryPanel,
    LastDeltaPanel,
)
from cod3s.pycatshoo.isimu.state import ISimuState


async def test_app_mounts_with_no_engine() -> None:
    """The app must accept ``engine=None`` for headless rendering tests."""
    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.title == "cod3s-isimu"


async def test_app_renders_four_named_panels() -> None:
    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Each panel must be queryable by id and class.
        assert app.query_one("#panel-fireable", FireablePanel) is not None
        assert app.query_one("#panel-components", ComponentsPanel) is not None
        assert app.query_one("#panel-last-delta", LastDeltaPanel) is not None
        assert app.query_one("#panel-history", HistoryPanel) is not None


async def test_quit_binding_exits_cleanly() -> None:
    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
    # ``run_test`` returning normally means the app shut down without error.


async def test_components_panel_input_filter_exists() -> None:
    """The filter ``Input`` widget must be present and start empty."""
    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import Input

        filter_input = app.query_one("#components-filter", Input)
        assert filter_input.value == ""


async def test_fireable_panel_has_data_table() -> None:
    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import DataTable

        table = app.query_one("#fireable-table", DataTable)
        # Table is empty when no engine is attached, but the columns are set.
        assert table.row_count == 0
        # 6 columns: idx, comp, transition, src→tgt, end_time, ★
        assert len(table.columns) == 6


async def test_panels_render_synthetic_state_without_crashing() -> None:
    """Push a non-empty :class:`ISimuState` and confirm panels accept it.

    Keeps the PyCATSHOO backend out of the loop while still exercising the
    real ``refresh_from_state`` paths with realistic data shapes."""
    from types import SimpleNamespace

    fake_trans = SimpleNamespace(
        comp_name="A",
        name="fail",
        source="ok",
        target="ko",
        end_time=1.0,
    )
    fake_event = SimpleNamespace(
        fired_at=1.0,
        transitions=[fake_trans],
        vars_before={"A.flag": False},
        vars_after={"A.flag": True},
    )

    state = ISimuState(
        current_time=1.0,
        fireable=[fake_trans],
        history=[fake_event],
        var_initial={"A.flag": False},
        var_current={"A.flag": True},
        var_previous={"A.flag": False},
        last_fired_at=1.0,
        last_fired_transitions=[fake_trans],
    )

    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        for selector, cls in [
            ("#panel-fireable", FireablePanel),
            ("#panel-components", ComponentsPanel),
            ("#panel-last-delta", LastDeltaPanel),
            ("#panel-history", HistoryPanel),
        ]:
            app.query_one(selector, cls).refresh_from_state(state)
        await pilot.pause()

        from textual.widgets import DataTable

        table = app.query_one("#fireable-table", DataTable)
        assert table.row_count == 1
