"""``cod3s-seq`` Textual application.

The :class:`SeqTuiApp` orchestrates the three panels (see :mod:`panels`)
and translates key bindings into pipeline mutations on the current
:class:`SeqTuiState`. The app owns the live state and the
:class:`UndoStack`; panels are stateless renderers.

Key bindings
------------

* ``q``       — quit
* ``+``       — add a step (opens :class:`AddStepModal`)
* ``u`` / ``r`` — undo / redo
* ``s``       — save the current pipeline to a YAML file
* ``l``       — load a pipeline from a YAML file (replaces current)
* ``e``       — export the current analyser (modal: JSON cod3s / CSV / MD)

The compute-heavy steps (``compute_minimal_sequences`` on a 20k-sequence
analyser) are run in worker threads so the TUI stays reactive.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from cod3s.version import __version__ as COD3S_VERSION
from cod3s.pycatshoo.seq_tui.exporter import (
    export_csv,
    export_json_cod3s,
    export_markdown,
)
from cod3s.pycatshoo.seq_tui.modals import (
    AddStepModal,
    ExportFormat,
    ExportModal,
    LoadPipelineModal,
    SavePipelineModal,
    config_modal_for,
)
from cod3s.pycatshoo.seq_tui.panels import (
    DetailPanel,
    PipelinePanel,
    SequencesPanel,
)
from cod3s.pycatshoo.seq_tui.pipeline import Pipeline
from cod3s.pycatshoo.seq_tui.state import SeqTuiState, UndoStack

if TYPE_CHECKING:
    from cod3s.pycatshoo.seq_tui.pipeline import PipelineStep


class SeqTuiApp(App[None]):
    """Textual TUI driving a :class:`SequenceAnalyser` through a pipeline.

    Construction takes an optional ``initial_state``. When ``None``
    (used in scaffold-only tests) the panels render an empty state.
    """

    CSS_PATH = str(Path(__file__).parent / "styles.tcss")
    TITLE = f"cod3s-seq v{COD3S_VERSION}"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("plus", "add_step", "Add step"),
        Binding("u", "undo", "Undo"),
        Binding("r", "redo", "Redo"),
        Binding("s", "save_pipeline", "Save YAML"),
        Binding("l", "load_pipeline", "Load YAML"),
        Binding("e", "export", "Export"),
    ]

    def __init__(
        self,
        initial_state: Optional[SeqTuiState] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._state: Optional[SeqTuiState] = initial_state
        self._undo = UndoStack()

    # ------------------------------------------------------------------
    # State accessor (test hook)
    # ------------------------------------------------------------------
    @property
    def state(self) -> Optional[SeqTuiState]:
        return self._state

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield PipelinePanel(id="panel-pipeline")
        yield SequencesPanel(id="panel-sequences")
        yield DetailPanel(id="panel-detail")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_panels()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def refresh_panels(self) -> None:
        if self._state is None:
            return
        self.query_one("#panel-pipeline", PipelinePanel).refresh_from_state(self._state)
        self.query_one("#panel-sequences", SequencesPanel).refresh_from_state(
            self._state
        )
        self.query_one("#panel-detail", DetailPanel).refresh_from_state(self._state)

    # ------------------------------------------------------------------
    # Actions — pipeline mutation
    # ------------------------------------------------------------------
    def action_add_step(self) -> None:
        if self._state is None:
            return
        self.push_screen(AddStepModal(), self._on_step_op_chosen)

    def _on_step_op_chosen(self, op: Optional[str]) -> None:
        if op is None or self._state is None:
            return
        modal_cls = config_modal_for(op)
        if modal_cls is None:
            # No-param step → apply directly.
            from cod3s.pycatshoo.seq_tui.pipeline import STEP_CLASSES

            step = STEP_CLASSES[op]()
            self._apply_step_worker(step)
            return
        self.push_screen(modal_cls(), self._on_step_configured)

    def _on_step_configured(self, step: Optional["PipelineStep"]) -> None:
        if step is None:
            return
        self._apply_step_worker(step)

    @work(thread=True, exclusive=True, group="pipeline")
    def _apply_step_worker(self, step: "PipelineStep") -> None:
        """Apply ``step`` on the current state in a worker thread.

        The undo stack receives the pre-step state; the new state
        becomes ``self._state``. UI refresh is scheduled back on the
        main thread via :meth:`call_from_thread`.
        """
        if self._state is None:
            return
        try:
            new_state = self._state.with_step_applied(step)
        except Exception as exc:
            self.call_from_thread(
                self.notify, f"Step failed: {exc}", severity="error"
            )
            return
        self._undo.push(self._state)
        self._state = new_state
        self.call_from_thread(self.refresh_panels)
        delta = new_state.last_delta
        if delta is not None:
            sign = "+" if delta.d_sequences >= 0 else ""
            self.call_from_thread(
                self.notify,
                f"{delta.step_summary}: {sign}{delta.d_sequences} sigs, "
                f"Δw={delta.d_total_weight:+d}",
                severity="information",
            )

    # ------------------------------------------------------------------
    # Actions — undo / redo
    # ------------------------------------------------------------------
    def action_undo(self) -> None:
        if self._state is None:
            return
        restored = self._undo.undo(self._state)
        if restored is None:
            self.notify("Nothing to undo.", severity="warning")
            return
        self._state = restored
        self.refresh_panels()
        self.notify("Undo.", severity="information")

    def action_redo(self) -> None:
        if self._state is None:
            return
        restored = self._undo.redo(self._state)
        if restored is None:
            self.notify("Nothing to redo.", severity="warning")
            return
        self._state = restored
        self.refresh_panels()
        self.notify("Redo.", severity="information")

    # ------------------------------------------------------------------
    # Actions — save / load YAML
    # ------------------------------------------------------------------
    def action_save_pipeline(self) -> None:
        if self._state is None:
            return
        self.push_screen(SavePipelineModal(), self._on_save_path)

    def _on_save_path(self, path: Optional[Path]) -> None:
        if path is None or self._state is None:
            return
        try:
            self._state.pipeline.save_yaml(path)
        except Exception as exc:
            self.notify(f"Save failed: {exc}", severity="error")
            return
        self.notify(f"Pipeline saved to {path}.", severity="information")

    def action_load_pipeline(self) -> None:
        if self._state is None:
            return
        self.push_screen(LoadPipelineModal(), self._on_load_path)

    def _on_load_path(self, path: Optional[Path]) -> None:
        if path is None or self._state is None:
            return
        try:
            pipeline = Pipeline.load_yaml(path)
        except Exception as exc:
            self.notify(f"Load failed: {exc}", severity="error")
            return
        self._load_pipeline_worker(pipeline)

    @work(thread=True, exclusive=True, group="pipeline")
    def _load_pipeline_worker(self, pipeline: Pipeline) -> None:
        """Replace the current pipeline with ``pipeline`` and re-apply it.

        The reset is destructive: the undo stack receives the current
        state (so the user can undo back), then we rebuild from the
        original analyser and apply each step in order.
        """
        if self._state is None:
            return
        self._undo.push(self._state)
        # Roll back to the loader state (empty pipeline, original analyser).
        # We approximate "original" by undoing all the way; if the undo
        # stack doesn't reach back that far we keep the current analyser
        # and just queue the new steps on top.
        base = self._state
        while self._undo.can_undo:
            base = self._undo.undo(base) or base
        # Now ``base`` is the earliest state. Apply each step in order.
        try:
            for step in pipeline.steps:
                base = base.with_step_applied(step)
        except Exception as exc:
            self.call_from_thread(
                self.notify, f"Load apply failed: {exc}", severity="error"
            )
            return
        self._state = base
        self.call_from_thread(self.refresh_panels)
        self.call_from_thread(
            self.notify,
            f"Pipeline loaded ({len(pipeline.steps)} steps applied).",
            severity="information",
        )

    # ------------------------------------------------------------------
    # Actions — export
    # ------------------------------------------------------------------
    def action_export(self) -> None:
        if self._state is None:
            return
        self.push_screen(ExportModal(), self._on_export_choice)

    def _on_export_choice(
        self, choice: Optional[tuple[ExportFormat, Path]]
    ) -> None:
        if choice is None or self._state is None:
            return
        fmt, path = choice
        self._export_worker(fmt, path)

    @work(thread=True, exclusive=True, group="export")
    def _export_worker(self, fmt: ExportFormat, path: Path) -> None:
        if self._state is None:
            return
        # Work on a defensive copy so the analyser is not mutated.
        analyser = copy.deepcopy(self._state.analyser)
        try:
            if fmt == "json-cod3s":
                export_json_cod3s(analyser, path)
            elif fmt == "csv":
                export_csv(analyser, path)
            elif fmt == "markdown":
                export_markdown(analyser, path)
            else:  # pragma: no cover — guarded by Literal
                raise ValueError(f"Unknown export format: {fmt!r}")
        except Exception as exc:
            self.call_from_thread(
                self.notify, f"Export failed: {exc}", severity="error"
            )
            return
        self.call_from_thread(
            self.notify, f"Exported {fmt} → {path}.", severity="information"
        )

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------
    def on_sequences_panel_sequence_selected(
        self, message: SequencesPanel.SequenceSelected
    ) -> None:
        if self._state is None:
            return
        self._state = self._state.with_selection(message.original_idx)
        self.refresh_panels()


def run_seq_tui(state: SeqTuiState) -> None:
    """Entry-point used by ``cod3s-seq``.

    Wraps the loaded state in a :class:`SeqTuiApp` and runs the TUI.
    """
    SeqTuiApp(initial_state=state).run()
