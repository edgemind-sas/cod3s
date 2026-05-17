"""Textual panels for the ``cod3s-seq`` TUI.

Three panels, each a :class:`Container` subclass with a uniform
``refresh_from_state(state: SeqTuiState)`` API. The :class:`SeqTuiApp`
owns the active :class:`SeqTuiState` and broadcasts every mutation by
calling ``refresh_from_state`` on each panel.

Panels:

* :class:`PipelinePanel` (left) — list of applied steps with the delta
  (``-3 sigs``) annotation. Empty state when the pipeline is empty.
* :class:`SequencesPanel` (middle) — DataTable of sequences sorted by
  descending weight. Selecting a row posts
  :class:`SequencesPanel.SequenceSelected`.
* :class:`DetailPanel` (right) — full event list of the selected
  sequence, or a placeholder if no selection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.widgets import DataTable, ListItem, ListView, Static

if TYPE_CHECKING:
    from cod3s.pycatshoo.seq_tui.state import SeqTuiState


# ---------------------------------------------------------------------------
# Pipeline panel
# ---------------------------------------------------------------------------


class PipelinePanel(Container):
    """Left panel: ordered list of applied pipeline steps."""

    DEFAULT_CSS = """
    PipelinePanel {
        height: 1fr;
        width: 1fr;
    }
    PipelinePanel > ListView {
        height: 1fr;
    }
    PipelinePanel .header {
        text-style: bold;
        background: $primary 20%;
        padding: 0 1;
    }
    PipelinePanel .empty {
        color: $text-muted;
        padding: 1;
    }
    """

    class AddStepRequested(Message):
        """Bubbled when the user requests adding a step (``+``)."""

    def compose(self) -> ComposeResult:
        yield Static("Pipeline", classes="header")
        yield ListView(id="pipeline-list")

    def refresh_from_state(self, state: "SeqTuiState") -> None:
        list_view = self.query_one("#pipeline-list", ListView)
        list_view.clear()
        steps = list(state.pipeline.steps)
        if not steps:
            list_view.append(
                ListItem(Static("(empty — press + to add a step)", classes="empty"))
            )
            return
        delta = state.last_delta
        for i, step in enumerate(steps, start=1):
            label = f"{i}. {step.summary()}"
            # Tag the most recent step with the size delta.
            if delta is not None and i == len(steps):
                sign = "+" if delta.d_sequences >= 0 else ""
                label = f"{label}    [{sign}{delta.d_sequences} sigs]"
            list_view.append(ListItem(Static(label)))


# ---------------------------------------------------------------------------
# Sequences panel
# ---------------------------------------------------------------------------


class SequencesPanel(Container):
    """Middle panel: sequence table, sorted by weight desc."""

    DEFAULT_CSS = """
    SequencesPanel {
        height: 1fr;
        width: 2fr;
    }
    SequencesPanel > DataTable {
        height: 1fr;
    }
    SequencesPanel .header {
        text-style: bold;
        background: $secondary 20%;
        padding: 0 1;
    }
    """

    class SequenceSelected(Message):
        """Posted when a sequence row is selected.

        Carries the *original* index in
        ``state.analyser.sequences`` (not the sorted-table row index)
        so the detail panel can look it up cheaply.
        """

        def __init__(self, original_idx: int) -> None:
            super().__init__()
            self.original_idx = original_idx

    def compose(self) -> ComposeResult:
        yield Static("Sequences", classes="header", id="sequences-header")
        table = DataTable(id="sequences-table", cursor_type="row")
        table.add_columns("#", "weight", "proba", "target", "signature")
        yield table

    def refresh_from_state(self, state: "SeqTuiState") -> None:
        table = self.query_one("#sequences-table", DataTable)
        table.clear()
        # Map sorted-row index → original index for the SequenceSelected event.
        self._row_to_original: list[int] = []
        total = state.total_weight or 1
        for rank, (orig_idx, seq) in enumerate(state.sorted_sequences(), start=1):
            proba = seq.probability if seq.probability is not None else seq.weight / total
            signature = " → ".join(f"{e.obj}.{e.attr}" for e in seq.events) or "(empty)"
            target = seq.target_name or "—"
            # Truncate very long signatures so the table stays readable.
            if len(signature) > 80:
                signature = signature[:77] + "..."
            table.add_row(
                str(rank),
                str(seq.weight),
                f"{proba:.4f}",
                target,
                signature,
            )
            self._row_to_original.append(orig_idx)
        # Update header with summary
        header = self.query_one("#sequences-header", Static)
        header.update(
            f"Sequences ({len(state.analyser.sequences)} signatures, "
            f"total weight {state.total_weight})"
        )

    @on(DataTable.RowSelected, "#sequences-table")
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        row = event.cursor_row
        mapping = getattr(self, "_row_to_original", None) or []
        if 0 <= row < len(mapping):
            self.post_message(self.SequenceSelected(mapping[row]))


# ---------------------------------------------------------------------------
# Detail panel
# ---------------------------------------------------------------------------


class DetailPanel(Container):
    """Right panel: full detail of the selected sequence."""

    DEFAULT_CSS = """
    DetailPanel {
        height: 1fr;
        width: 1fr;
    }
    DetailPanel > ListView {
        height: 1fr;
    }
    DetailPanel .header {
        text-style: bold;
        background: $warning 20%;
        padding: 0 1;
    }
    DetailPanel .empty {
        color: $text-muted;
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Detail", classes="header", id="detail-header")
        yield ListView(id="detail-list")

    def refresh_from_state(self, state: "SeqTuiState") -> None:
        list_view = self.query_one("#detail-list", ListView)
        list_view.clear()
        header = self.query_one("#detail-header", Static)
        idx = state.selected_seq_idx
        if idx is None or idx >= len(state.analyser.sequences):
            header.update("Detail")
            list_view.append(
                ListItem(Static("(no sequence selected)", classes="empty"))
            )
            return
        seq = state.analyser.sequences[idx]
        proba = (
            seq.probability
            if seq.probability is not None
            else seq.weight / (state.total_weight or 1)
        )
        end_time = "—" if seq.end_time is None else f"{seq.end_time:.3f}"
        header.update(
            f"Detail — {seq.target_name or '—'}  weight={seq.weight}  "
            f"proba={proba:.4f}  end_time={end_time}"
        )
        if not seq.events:
            list_view.append(
                ListItem(
                    Static(
                        "(empty sequence — top event not reached)",
                        classes="empty",
                    )
                )
            )
            return
        for i, event in enumerate(seq.events, start=1):
            t = "—" if event.time is None else f"{event.time:>10.3f}"
            type_str = f"  [{event.type}]" if event.type else ""
            list_view.append(
                ListItem(Static(f"{i:>3}. t={t}  {event.obj}.{event.attr}{type_str}"))
            )
