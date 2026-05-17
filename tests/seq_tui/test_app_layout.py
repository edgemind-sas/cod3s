"""Tests that the ``cod3s-seq`` TUI mounts and the three panels render.

Like the isimu suite, these tests do not require PyCATSHOO — they
drive :class:`SeqTuiApp` with a synthetic :class:`SeqTuiState`, or
with ``initial_state=None`` for empty-render verification.
"""

from __future__ import annotations

from cod3s.pycatshoo.seq_tui.app import SeqTuiApp
from cod3s.pycatshoo.seq_tui.panels import (
    DetailPanel,
    PipelinePanel,
    SequencesPanel,
)


async def test_app_mounts_with_no_state() -> None:
    """The app must accept ``initial_state=None`` for headless tests."""
    app = SeqTuiApp(initial_state=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.title.startswith("cod3s-seq")
        assert "v" in app.title


async def test_app_renders_three_named_panels() -> None:
    app = SeqTuiApp(initial_state=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#panel-pipeline", PipelinePanel) is not None
        assert app.query_one("#panel-sequences", SequencesPanel) is not None
        assert app.query_one("#panel-detail", DetailPanel) is not None


async def test_quit_binding_exits_cleanly() -> None:
    app = SeqTuiApp(initial_state=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()


async def test_initial_state_populates_sequences_table(sample_state) -> None:
    app = SeqTuiApp(initial_state=sample_state)
    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import DataTable

        table = app.query_one("#sequences-table", DataTable)
        assert table.row_count == 4  # the 4 sample sequences


async def test_state_property_exposes_current_state(sample_state) -> None:
    app = SeqTuiApp(initial_state=sample_state)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.state is sample_state
