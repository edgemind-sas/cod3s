"""``cod3s-isimu`` Textual application.

The ``ISimuApp`` orchestrates the four panels (see :mod:`panels`) and forwards
key bindings to the underlying :class:`ISimuEngine`. This module is loaded
lazily by the entry-point script so that ``cod3s.pycatshoo.isimu`` stays
importable when the optional ``[isimu]`` extra (which pulls in Textual) has
not been installed.

Phase 3 deliverable: the app mounts, renders the initial state of every
panel, and supports the basic ``[q]`` quit binding. Wiring the fire / step
back / reset / export / re-plan actions is Phase 4+ work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header

from cod3s.pycatshoo.isimu.engine import ISimuEngine
from cod3s.pycatshoo.isimu.panels import (
    ComponentsPanel,
    FireablePanel,
    HistoryPanel,
    LastDeltaPanel,
)
from cod3s.pycatshoo.isimu.state import ISimuState


class ISimuApp(App[None]):
    """Textual TUI driving an :class:`ISimuEngine`.

    Construction takes an optional ``engine``. When ``None`` (typical in
    tests/snapshot scenarios) the panels render an empty state. In production
    the entry-point passes a fully-built engine wrapping a populated
    ``PycSystem``.
    """

    CSS_PATH = str(Path(__file__).parent / "styles.tcss")
    TITLE = "cod3s-isimu"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("b", "step_backward", "Back"),
        Binding("r", "reset", "Reset"),
        Binding("?", "help", "Help"),
    ]

    def __init__(self, engine: Optional[ISimuEngine] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._engine = engine

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield FireablePanel(id="panel-fireable")
        yield ComponentsPanel(id="panel-components")
        yield LastDeltaPanel(id="panel-last-delta")
        yield HistoryPanel(id="panel-history")
        yield Footer()

    def on_mount(self) -> None:
        """Bootstrap the engine and push the initial state to every panel."""
        if self._engine is not None:
            self._engine.start()
        self.refresh_panels()

    def on_unmount(self) -> None:
        """Stop the simulator cleanly. ``terminate_session()`` is the
        responsibility of the caller (run_isimu) so tests can keep the
        PyCATSHOO singleton alive across multiple ``App`` instances."""
        if self._engine is not None:
            self._engine.stop()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_help(self) -> None:
        """Placeholder — a help overlay is added in Phase 4+."""
        # Until the help screen lands, surface the bindings list via the
        # built-in command palette.
        self.action_command_palette()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Fire the highlighted transition when the user presses Enter on a
        row of the fireable transitions table."""
        if self._engine is None:
            return
        if getattr(event.control, "id", None) != "fireable-table":
            return
        table = event.control
        if table.row_count == 0:
            return
        cursor_row = event.cursor_row
        if cursor_row < 0 or cursor_row >= table.row_count:
            return
        idx_str = table.get_row_at(cursor_row)[0]
        try:
            idx = int(idx_str)
        except (TypeError, ValueError):
            return
        self._fire_worker(idx)

    def action_step_backward(self) -> None:
        if self._engine is None:
            return
        self._back_worker()

    def action_reset(self) -> None:
        if self._engine is None:
            return
        self._reset_worker()

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------
    @work(thread=True, exclusive=True, group="engine")
    def _fire_worker(self, idx: int) -> None:
        """Force-fire the transition at ``idx`` in the active list.

        The engine is invoked from a worker thread so a slow PyCATSHOO
        ``stepForward`` does not freeze the UI. Panel refresh is scheduled
        back on the main thread via ``call_from_thread``.
        """
        engine = self._engine
        if engine is None:
            return
        try:
            engine.replan(trans_id=idx)
        except Exception:
            # Re-planning may fail (e.g. transition no longer active);
            # fall through to a plain step_forward.
            pass
        engine.step_forward()
        self.call_from_thread(self.refresh_panels)

    @work(thread=True, exclusive=True, group="engine")
    def _back_worker(self) -> None:
        engine = self._engine
        if engine is None:
            return
        engine.step_backward()
        self.call_from_thread(self.refresh_panels)

    @work(thread=True, exclusive=True, group="engine")
    def _reset_worker(self) -> None:
        engine = self._engine
        if engine is None:
            return
        engine.reset()
        self.call_from_thread(self.refresh_panels)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def refresh_panels(self) -> None:
        """Recompute :class:`ISimuState` and push it to every panel."""
        if self._engine is None:
            state = ISimuState()
        else:
            state = ISimuState.from_engine(self._engine)

        self.query_one("#panel-fireable", FireablePanel).refresh_from_state(state)
        self.query_one("#panel-components", ComponentsPanel).refresh_from_state(state)
        self.query_one("#panel-last-delta", LastDeltaPanel).refresh_from_state(state)
        self.query_one("#panel-history", HistoryPanel).refresh_from_state(state)


def run_isimu(system: Any) -> None:
    """Entry-point used by ``cod3s-isimu`` and by ``PycSystem.isimu_start_cli``.

    Wraps ``system`` in an :class:`ISimuEngine`, runs the TUI, and stops the
    engine on exit. Does *not* call ``terminate_session()``; the binary that
    invoked us decides whether the PyCATSHOO singleton outlives the TUI
    (e.g. for a follow-up ``isimu_start_cli`` call).
    """
    engine = ISimuEngine(system)
    app = ISimuApp(engine=engine)
    app.run()
