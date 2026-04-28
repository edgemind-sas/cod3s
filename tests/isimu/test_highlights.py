"""Phase 5 visual layer tests.

Covers:

* the ★ "fires together" marker on :class:`FireablePanel` reacting to
  cursor navigation,
* the live filter on :class:`ComponentsPanel` driven by ``Input.Changed``,
* the three-state coloring (unchanged / differs-init / changed) of variable
  cells in :class:`ComponentsPanel`.

All tests run with ``engine=None`` and push synthetic states; PyCATSHOO is
not loaded.
"""

from __future__ import annotations

from types import SimpleNamespace

from rich.text import Text
from textual.widgets import DataTable, Input, Tree

from cod3s.pycatshoo.isimu.app import ISimuApp
from cod3s.pycatshoo.isimu.panels import (
    ComponentsPanel,
    FireablePanel,
)
from cod3s.pycatshoo.isimu.state import ISimuState


def _trans(comp: str, name: str, end_time: float):
    return SimpleNamespace(
        comp_name=comp,
        comp_classname="PycComponent",
        name=name,
        source="ok",
        target="ko",
        end_time=end_time,
    )


def _star_at(table: DataTable, row: int) -> str:
    """Return the contents of the ★ column (last column) at ``row``."""
    star_col = len(table.columns) - 1
    cell = table.get_row_at(row)[star_col]
    return cell if isinstance(cell, str) else str(cell)


# ---------------------------------------------------------------------------
# ★ "fires together"
# ---------------------------------------------------------------------------


async def test_star_marks_peers_sharing_end_time() -> None:
    """Two transitions with the same ``end_time`` both get a ★ when one is
    highlighted; the third (alone) does not."""
    state = ISimuState(
        fireable=[
            _trans("A", "fail", 1.0),
            _trans("B", "fail", 1.0),
            _trans("C", "open", 5.0),
        ]
    )

    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-fireable", FireablePanel)
        panel.refresh_from_state(state)
        await pilot.pause()

        table = app.query_one("#fireable-table", DataTable)
        # Cursor lands on row 0 by default; A and B should both be marked.
        assert _star_at(table, 0) == "★"
        assert _star_at(table, 1) == "★"
        assert _star_at(table, 2) == ""


async def test_star_follows_cursor_to_solo_row() -> None:
    state = ISimuState(
        fireable=[
            _trans("A", "fail", 1.0),
            _trans("B", "fail", 1.0),
            _trans("C", "open", 5.0),
        ]
    )

    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-fireable", FireablePanel)
        panel.refresh_from_state(state)
        await pilot.pause()

        table = app.query_one("#fireable-table", DataTable)
        table.focus()
        # Move cursor to row 2 (the solo C transition).
        await pilot.press("down")
        await pilot.press("down")
        await pilot.pause()

        assert _star_at(table, 2) == "★"
        assert _star_at(table, 0) == ""
        assert _star_at(table, 1) == ""


async def test_star_handles_none_slots_in_fireable() -> None:
    """``state.fireable`` may contain ``None`` slots (active but not fireable).
    The display rows should ignore ``None``s and the star calculation must
    still match the original indices."""
    state = ISimuState(
        fireable=[
            _trans("A", "fail", 1.0),
            None,  # active-but-not-fireable
            _trans("B", "fail", 1.0),
        ]
    )

    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-fireable", FireablePanel)
        panel.refresh_from_state(state)
        await pilot.pause()

        table = app.query_one("#fireable-table", DataTable)
        # Two visible rows (None is hidden); both share end_time → both ★.
        assert table.row_count == 2
        assert _star_at(table, 0) == "★"
        assert _star_at(table, 1) == "★"


# ---------------------------------------------------------------------------
# Live filter
# ---------------------------------------------------------------------------


async def test_filter_input_filters_tree_live() -> None:
    """Typing in the filter input must immediately re-render the Tree."""
    state = ISimuState(
        var_initial={
            "pump1.flow": 0.0,
            "pump1.working": True,
            "valve.open": False,
        },
        var_current={
            "pump1.flow": 0.0,
            "pump1.working": True,
            "valve.open": False,
        },
        var_previous={
            "pump1.flow": 0.0,
            "pump1.working": True,
            "valve.open": False,
        },
    )

    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-components", ComponentsPanel)
        panel.refresh_from_state(state)
        await pilot.pause()

        tree = app.query_one("#components-tree", Tree)
        # Three variables across two components, all visible initially.
        # Tree.root has two children (pump1, valve) each with leaves.
        comp_count = len(tree.root.children)
        assert comp_count == 2

        filter_input = app.query_one("#components-filter", Input)
        filter_input.focus()
        await pilot.press("p", "u", "m", "p")
        await pilot.pause()

        # After filtering on "pump", only pump1 keeps leaves; valve.open is hidden.
        all_labels: list[str] = []
        for comp_node in tree.root.children:
            for leaf in comp_node.children:
                label = leaf.label
                all_labels.append(
                    label.plain if hasattr(label, "plain") else str(label)
                )
        assert any("flow" in label for label in all_labels)
        assert any("working" in label for label in all_labels)
        assert not any(label.startswith("open:") for label in all_labels)


async def test_filter_clearing_restores_all_variables() -> None:
    state = ISimuState(
        var_initial={"a.x": 1, "b.y": 2},
        var_current={"a.x": 1, "b.y": 2},
    )
    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-components", ComponentsPanel)
        panel.refresh_from_state(state)
        await pilot.pause()

        filter_input = app.query_one("#components-filter", Input)
        filter_input.focus()
        await pilot.press("a", ".")
        await pilot.pause()

        tree = app.query_one("#components-tree", Tree)
        # Only a.x is visible.
        leaves: list[str] = []
        for comp_node in tree.root.children:
            for leaf in comp_node.children:
                label = leaf.label
                leaves.append(label.plain if hasattr(label, "plain") else str(label))
        assert any("x" in leaf for leaf in leaves)
        assert not any("y" in leaf for leaf in leaves)

        # Clear the filter — every leaf should come back.
        filter_input.value = ""
        await pilot.pause()
        leaves = []
        for comp_node in tree.root.children:
            for leaf in comp_node.children:
                label = leaf.label
                leaves.append(label.plain if hasattr(label, "plain") else str(label))
        assert any("x" in leaf for leaf in leaves)
        assert any("y" in leaf for leaf in leaves)


# ---------------------------------------------------------------------------
# 3-state coloring
# ---------------------------------------------------------------------------


def _styles_in(text: Text) -> set[str]:
    """Aggregate every style string applied to spans of ``text``."""
    styles: set[str] = set()
    for span in text.spans:
        if span.style:
            styles.add(str(span.style))
    return styles


def test_format_var_unchanged_uses_dim() -> None:
    text = ComponentsPanel._format_var(
        "flag", current=True, initial=True, previous=True
    )
    assert "dim" in _styles_in(text)
    assert "True" in text.plain


def test_format_var_differs_from_initial_uses_orange() -> None:
    text = ComponentsPanel._format_var(
        "flag", current=True, initial=False, previous=True
    )
    styles = _styles_in(text)
    assert "orange3" in styles
    assert "init: False" in text.plain


def test_format_var_changed_at_last_step_uses_bold_red() -> None:
    text = ComponentsPanel._format_var(
        "flag", current=True, initial=False, previous=False
    )
    styles = _styles_in(text)
    assert "bold red" in styles
    # The before → after arrow is rendered on this row.
    assert "False → True" in text.plain
