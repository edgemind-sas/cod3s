"""``cod3s-isimu`` Textual application.

The ``ISimuApp`` orchestrates the four panels (see :mod:`panels`) and forwards
key bindings to the underlying :class:`ISimuEngine`. This module is loaded
lazily by the entry-point script so that ``cod3s.pycatshoo.isimu`` stays
importable in environments where Textual itself fails to import (e.g.
embedded Python builds without a TTY backend).

Two ways to advance the clock, and they answer different questions:

* picking a transition and firing it -- "what happens next, and when?";
* **playback** (``space``), which repeats ``engine.step_to`` on a grid -- "what
  do the continuous variables DO between the events?". A model whose
  continuous variables are the only thing moving has no transition to pick, so
  before playback existed there was nothing to press and the session sat at
  t=0.

Playback carries three independent settings, and conflating any two of them
gives a wrong reading:

===================  ============================  ==================
Setting              What it changes               Bound by
===================  ============================  ==================
observation step     simulated time per tick       the model's time unit
wall-clock period    real seconds between ticks    how fast a step computes
integration knobs    how finely the ODEs are run   accuracy vs cost
===================  ============================  ==================
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header

from cod3s.version import __version__ as COD3S_VERSION
from cod3s.pycatshoo.isimu.engine import ISimuEngine
from cod3s.pycatshoo.isimu.export import export_csv, export_json
from cod3s.pycatshoo.isimu.modals import (
    ExportModal,
    IntegrationModal,
    ObservationStepModal,
    ReplanModal,
)
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
    TITLE = f"cod3s-isimu v{COD3S_VERSION}"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("b", "step_backward", "Back"),
        Binding("r", "reset", "Reset"),
        Binding("e", "export", "Export"),
        Binding("space", "toggle_play", "Play/Pause"),
        Binding("plus", "faster", "Faster", show=False),
        Binding("equals_sign", "faster", "Faster", show=False),
        Binding("minus", "slower", "Slower", show=False),
        Binding("d", "set_observation_step", "Step"),
        Binding("i", "set_integration", "Integration", show=False),
        Binding("?", "help", "Help"),
    ]

    #: Simulated time one playback tick advances. Not the integration step.
    DEFAULT_OBSERVATION_STEP = 1.0
    #: Real seconds between two playback ticks.
    DEFAULT_WALL_PERIOD = 0.2
    WALL_PERIOD_MIN = 0.01
    WALL_PERIOD_MAX = 5.0
    # NOTE: ``p`` (re-plan) is bound at the FireablePanel level so it is
    # only active when the inner DataTable has focus. The panel posts a
    # FireablePanel.ReplanRequested message that this App handles below.

    def __init__(self, engine: Optional[ISimuEngine] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._engine = engine
        self.observation_step = self.DEFAULT_OBSERVATION_STEP
        self.wall_period = self.DEFAULT_WALL_PERIOD
        self._play_timer: Optional[Any] = None
        # A tick that is still running must not be joined by the next one: the
        # engine call is a blocking C++ one and two of them on one system is
        # not something PyCATSHOO tolerates. The timer skips instead of
        # queueing, so a slow model plays slower rather than falling behind.
        self._stepping = False

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
        self.pause()
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

    # -- Playback ------------------------------------------------------
    @property
    def is_playing(self) -> bool:
        return self._play_timer is not None

    def action_toggle_play(self) -> None:
        """Start or stop advancing the clock on the observation grid."""
        if self._engine is None:
            return
        if self.is_playing:
            self.pause()
        else:
            self._play_timer = self.set_interval(self.wall_period, self._play_tick)
        self.refresh_status()

    def pause(self) -> None:
        """Stop playback. Safe to call when not playing."""
        if self._play_timer is not None:
            self._play_timer.stop()
            self._play_timer = None

    def action_faster(self) -> None:
        self._set_wall_period(self.wall_period / 2)

    def action_slower(self) -> None:
        self._set_wall_period(self.wall_period * 2)

    def _set_wall_period(self, period: float) -> None:
        self.wall_period = max(self.WALL_PERIOD_MIN, min(self.WALL_PERIOD_MAX, period))
        if self.is_playing:
            # A Textual timer's interval is fixed at creation, so the running
            # one is replaced rather than adjusted.
            self.pause()
            self._play_timer = self.set_interval(self.wall_period, self._play_tick)
        self.refresh_status()

    def _play_tick(self) -> None:
        if self._engine is None or self._stepping:
            return
        self._stepping = True
        self._play_worker()

    def action_set_observation_step(self) -> None:
        def _on_step(step: Optional[float]) -> None:
            if step is None:
                return
            self.observation_step = step
            self.refresh_status()

        self.push_screen(
            ObservationStepModal(default_step=self.observation_step), _on_step
        )

    def action_set_integration(self) -> None:
        if self._engine is None:
            return
        self.push_screen(IntegrationModal(), self._on_integration)

    def _on_integration(self, knobs: Optional[dict]) -> None:
        """Apply the PDMP knobs, or say why they could not be applied.

        A purely discrete model has no PDMP manager at all, and silently
        accepting knobs there would report a setting that governs nothing.
        """
        if not knobs or self._engine is None:
            return
        manager = self._engine.system.currentPDMPManager()
        if manager is None:
            self.notify(
                "No PDMP manager on this system: nothing is integrated, so "
                "these knobs would govern nothing.",
                severity="warning",
            )
            return
        applied = []
        if knobs.get("dt_max") is not None:
            manager.setDtMax(knobs["dt_max"])
            applied.append(f"dtMax={knobs['dt_max']:g}")
        if knobs.get("dt_cond") is not None:
            manager.setDtCond(knobs["dt_cond"])
            applied.append(f"dtCond={knobs['dt_cond']:g}")
        self.notify(f"Integration: {', '.join(applied)}", severity="information")

    def action_step_backward(self) -> None:
        if self._engine is None:
            return
        self.pause()
        # ``stepBackward`` walks the SEQUENCE, and a playback grid point is not
        # in it -- the engine has no record to walk back to, so it lands at the
        # start of the session and reports nothing retired. Refusing beats
        # silently throwing the run away.
        if any(getattr(evt, "kind", "event") == "grid" for evt in self._engine.history):
            self.notify(
                "Step back is not available after playback: a grid point is "
                "not a recorded transition, and stepping back would return to "
                "the start of the session. Use [r] to reset.",
                severity="warning",
            )
            return
        self._back_worker()

    def action_reset(self) -> None:
        if self._engine is None:
            return
        self.pause()
        self._reset_worker()

    def action_export(self) -> None:
        if self._engine is None:
            return
        self.push_screen(ExportModal(), self._on_export_path)

    def on_fireable_panel_replan_requested(
        self, message: FireablePanel.ReplanRequested
    ) -> None:
        """Handle ``p`` pressed on a fireable row.

        The :class:`FireablePanel` already resolved the cursor's transition,
        so we just open the date-only :class:`ReplanModal` with a title that
        identifies the transition, then forward the chosen date to the engine
        via ``_replan_worker``.
        """
        if self._engine is None:
            return
        idx = message.idx
        trans = message.trans
        title = f"Replan transition {trans.comp_name}.{trans.name}"
        default_date = float(self._engine.current_time)

        def _on_date(date: Optional[float]) -> None:
            if date is None or self._engine is None:
                return
            self._replan_worker(int(idx), float(date))

        self.push_screen(
            ReplanModal(title=title, default_date=default_date),
            _on_date,
        )

    def on_fireable_panel_inst_resolve_requested(
        self, message: FireablePanel.InstResolveRequested
    ) -> None:
        """Handle ``s`` pressed in inst pending mode.

        Forwards the per-transition branch choices to
        :meth:`ISimuEngine.resolve_inst` from a worker thread.
        """
        if self._engine is None:
            return
        self._resolve_inst_worker(dict(message.choices))

    # ------------------------------------------------------------------
    # Modal callbacks
    # ------------------------------------------------------------------
    def _on_export_path(self, path: Optional["Path"]) -> None:
        if path is None or self._engine is None:
            return
        self._export_worker(path)

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------
    @work(thread=True, exclusive=True, group="engine")
    def _fire_worker(self, idx: int) -> None:
        """Force-fire the transition at ``idx`` in the active list.

        The engine is invoked from a worker thread so a slow PyCATSHOO
        ``stepForward`` does not freeze the UI. Panel refresh is scheduled
        back on the main thread via ``call_from_thread``.

        If the planner refuses the replan (e.g. transition no longer active),
        the worker notifies the operator and bails out — it does NOT fall
        through to ``step_forward`` on whatever PyCATSHOO would pick.
        Symmetric with :meth:`_replan_worker` and :meth:`_resolve_inst_worker`,
        which also return after notifying. Previously the worker fell
        through silently, advancing time on a transition the operator did
        not choose.
        """
        engine = self._engine
        if engine is None:
            return
        try:
            engine.replan(trans_id=idx)
        except Exception as exc:
            self.call_from_thread(
                self.notify, f"Replan rejected: {exc}", severity="error"
            )
            self.call_from_thread(self.refresh_panels)
            return
        engine.step_forward()
        self.call_from_thread(self.refresh_panels)

    @work(thread=True, group="play")
    def _play_worker(self) -> None:
        """One playback tick: advance the grid by the observation step.

        Not ``exclusive``: cancelling a worker blocked in a C++ call does not
        interrupt it, so exclusivity would only hide the overlap. ``_stepping``
        is what serialises the ticks.
        """
        engine = self._engine
        if engine is None:
            self._stepping = False
            return
        try:
            engine.step_to(engine.current_time + self.observation_step)
        except Exception as exc:
            self.call_from_thread(self.pause)
            self.call_from_thread(
                self.notify, f"Playback stopped: {exc}", severity="error"
            )
        finally:
            self._stepping = False
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

    @work(thread=True, exclusive=True, group="export")
    def _export_worker(self, path: "Path") -> None:
        """Write the engine timeline to ``<path>.csv`` and ``<path>.json``."""
        engine = self._engine
        if engine is None:
            return
        csv_path = path.with_suffix(".csv")
        json_path = path.with_suffix(".json")
        export_csv(engine.history, csv_path)
        export_json(engine.history, json_path)
        self.call_from_thread(
            self.notify,
            f"Exported {csv_path.name} + {json_path.name}",
            severity="information",
        )

    @work(thread=True, exclusive=True, group="engine")
    def _replan_worker(self, idx: int, date: float) -> None:
        engine = self._engine
        if engine is None:
            return
        try:
            engine.replan(trans_id=idx, date=date)
        except Exception as exc:
            self.call_from_thread(
                self.notify, f"Replan failed: {exc}", severity="error"
            )
            return
        self.call_from_thread(self.refresh_panels)

    @work(thread=True, exclusive=True, group="engine")
    def _resolve_inst_worker(self, choices: dict) -> None:
        engine = self._engine
        if engine is None:
            return
        try:
            engine.resolve_inst(choices)
        except Exception as exc:
            self.call_from_thread(
                self.notify, f"Inst resolve failed: {exc}", severity="error"
            )
            return
        self.call_from_thread(self.refresh_panels)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def refresh_status(self) -> None:
        """Publish the clock and the playback settings in the header.

        The three settings live here together because they are read together:
        a reader who sees only the wall-clock speed cannot tell whether the
        run is coarse or slow.
        """
        if self._engine is None:
            self.sub_title = ""
            return
        state = "playing" if self.is_playing else "paused"
        self.sub_title = (
            f"t={self._engine.current_time:.4g}  "
            f"step={self.observation_step:g}  "
            f"every {self.wall_period:g}s  [{state}]"
        )

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
        self.refresh_status()


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
