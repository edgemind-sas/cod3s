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

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

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
        Binding("?", "help", "Help"),
    ]

    def __init__(
        self, engine: Optional[ISimuEngine] = None, **kwargs: Any
    ) -> None:
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
