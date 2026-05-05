"""Snapshot of the inst pending panel layout (synthetic state, no Pycatshoo)."""

from __future__ import annotations

from types import SimpleNamespace

from textual.widgets import DataTable, Tree

from cod3s.pycatshoo.isimu.app import ISimuApp
from cod3s.pycatshoo.isimu.panels import FireablePanel
from cod3s.pycatshoo.isimu.state import ISimuState


def _branch(state: str, prob: float) -> SimpleNamespace:
    return SimpleNamespace(state=state, prob=prob, effects={})


def _inst_trans(comp: str, name: str, branches) -> SimpleNamespace:
    return SimpleNamespace(
        comp_name=comp,
        name=name,
        source="src",
        target=branches,
        end_time=0.0,
    )


async def test_pending_inst_switches_panel_to_tree_mode() -> None:
    """When state.pending_inst is non-empty, the tree is shown and the table is hidden."""
    branches = [_branch("a", 0.7), _branch("b", 0.3)]
    trans = _inst_trans("V", "br", branches)
    state = ISimuState(fireable=[trans], pending_inst=[trans])

    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-fireable", FireablePanel)
        panel.refresh_from_state(state)
        await pilot.pause()

        table = app.query_one("#fireable-table", DataTable)
        tree = app.query_one("#inst-pending-tree", Tree)
        assert table.display is False
        assert tree.display is True
        # One root child per pending inst, with one leaf per branch.
        assert len(tree.root.children) == 1
        assert len(tree.root.children[0].children) == 2


async def test_no_pending_inst_keeps_table_mode() -> None:
    """When state.pending_inst is empty, the table is shown and the tree is hidden."""
    timed = SimpleNamespace(
        comp_name="A", name="fail", source="ok", target="ko", end_time=1.0
    )
    state = ISimuState(fireable=[timed], pending_inst=[])

    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-fireable", FireablePanel)
        panel.refresh_from_state(state)
        await pilot.pause()

        table = app.query_one("#fireable-table", DataTable)
        tree = app.query_one("#inst-pending-tree", Tree)
        assert table.display is True
        assert tree.display is False
        assert table.row_count == 1


async def test_two_pending_inst_show_two_root_children() -> None:
    branches_v = [_branch("panne", 0.2), _branch("ok", 0.8)]
    branches_b = [_branch("trip", 0.1), _branch("ok", 0.9)]
    trans_v = _inst_trans("V", "check", branches_v)
    trans_b = _inst_trans("B", "check", branches_b)
    state = ISimuState(
        fireable=[trans_v, trans_b],
        pending_inst=[trans_v, trans_b],
    )

    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-fireable", FireablePanel)
        panel.refresh_from_state(state)
        await pilot.pause()

        tree = app.query_one("#inst-pending-tree", Tree)
        assert len(tree.root.children) == 2
        # Each transition shows its branches.
        for child in tree.root.children:
            assert len(child.children) == 2
