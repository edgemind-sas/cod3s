"""Tests for the three ``cod3s-seq`` panels.

The panels are pure renderers — they only read from a
:class:`SeqTuiState`. The tests therefore drive them via
``refresh_from_state(state)`` inside a Textual ``Pilot`` context
(needed because some widgets — ``DataTable``, ``ListView`` — require a
mounted Screen to be queryable).

A bare :class:`textual.app.App` is used as the host so the panels are
exercised in isolation, without dragging in :class:`SeqTuiApp`'s
bindings.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import DataTable, ListView

from cod3s.pycatshoo.seq_tui.panels import (
    DetailPanel,
    PipelinePanel,
    SequencesPanel,
)
from cod3s.pycatshoo.seq_tui.pipeline import GroupSequencesStep
from cod3s.pycatshoo.seq_tui.state import SeqTuiState


class _Host(App[None]):
    """Tiny host that mounts the three panels for testing."""

    def compose(self) -> ComposeResult:
        yield PipelinePanel(id="panel-pipeline")
        yield SequencesPanel(id="panel-sequences")
        yield DetailPanel(id="panel-detail")


# ---------------------------------------------------------------------------
# SequencesPanel
# ---------------------------------------------------------------------------


class TestSequencesPanel:
    async def test_sorts_by_weight_desc(self, sample_state):
        host = _Host()
        async with host.run_test() as pilot:
            await pilot.pause()
            panel = host.query_one("#panel-sequences", SequencesPanel)
            panel.refresh_from_state(sample_state)
            await pilot.pause()
            table = host.query_one("#sequences-table", DataTable)
            # 4 rows
            assert table.row_count == 4
            # First row corresponds to weight=7 (the highest).
            weights = [int(table.get_row_at(i)[1]) for i in range(table.row_count)]
            assert weights == sorted(weights, reverse=True)
            assert weights[0] == 7

    async def test_header_summarises_total(self, sample_state):
        host = _Host()
        async with host.run_test() as pilot:
            await pilot.pause()
            panel = host.query_one("#panel-sequences", SequencesPanel)
            panel.refresh_from_state(sample_state)
            await pilot.pause()
            from textual.widgets import Static

            header = host.query_one("#sequences-header", Static)
            # 4 signatures, total weight 13.
            text = str(header.render())
            assert "4 signatures" in text
            assert "13" in text


# ---------------------------------------------------------------------------
# DetailPanel
# ---------------------------------------------------------------------------


class TestDetailPanel:
    async def test_empty_when_no_selection(self, sample_state):
        host = _Host()
        async with host.run_test() as pilot:
            await pilot.pause()
            panel = host.query_one("#panel-detail", DetailPanel)
            panel.refresh_from_state(sample_state)
            await pilot.pause()
            from textual.widgets import Static

            header = host.query_one("#detail-header", Static)
            assert str(header.render()) == "Detail"

    async def test_renders_events_after_selection(self, sample_state):
        host = _Host()
        async with host.run_test() as pilot:
            await pilot.pause()
            panel = host.query_one("#panel-detail", DetailPanel)
            # Select the first sequence (2 events).
            panel.refresh_from_state(sample_state.with_selection(0))
            await pilot.pause()
            lv = host.query_one("#detail-list", ListView)
            assert len(lv.children) == 2  # 2 events listed

    async def test_handles_empty_sequence(self, sample_analyser):
        """A sequence with no events must be rendered with a placeholder."""
        from cod3s.pycatshoo.sequence import Sequence

        sample_analyser.sequences.append(
            Sequence(target_name="empty_target", weight=1, events=[])
        )
        state = SeqTuiState.from_initial(sample_analyser).with_selection(
            len(sample_analyser.sequences) - 1
        )
        host = _Host()
        async with host.run_test() as pilot:
            await pilot.pause()
            panel = host.query_one("#panel-detail", DetailPanel)
            panel.refresh_from_state(state)
            await pilot.pause()
            lv = host.query_one("#detail-list", ListView)
            # One placeholder ListItem.
            assert len(lv.children) == 1


# ---------------------------------------------------------------------------
# PipelinePanel
# ---------------------------------------------------------------------------


class TestPipelinePanel:
    async def test_empty_state(self, sample_state):
        host = _Host()
        async with host.run_test() as pilot:
            await pilot.pause()
            panel = host.query_one("#panel-pipeline", PipelinePanel)
            panel.refresh_from_state(sample_state)
            await pilot.pause()
            lv = host.query_one("#pipeline-list", ListView)
            # Placeholder ListItem when no steps.
            assert len(lv.children) == 1

    async def test_lists_applied_steps_with_delta(self, sample_state):
        new_state = sample_state.with_step_applied(GroupSequencesStep())
        host = _Host()
        async with host.run_test() as pilot:
            await pilot.pause()
            panel = host.query_one("#panel-pipeline", PipelinePanel)
            panel.refresh_from_state(new_state)
            await pilot.pause()
            lv = host.query_one("#pipeline-list", ListView)
            assert len(lv.children) == 1
            from textual.widgets import Static

            label = lv.children[0].query_one(Static)
            text = str(label.render())
            assert "group_sequences" in text
            # The last-step annotation is in brackets, format:
            # `[N → M séqs, Δ ±k]`. cf. 1.5.2 toast wording change.
            assert "séqs" in text
            assert "Δ" in text
            assert "→" in text
