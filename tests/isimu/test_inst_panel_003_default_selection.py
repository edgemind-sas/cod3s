"""Default branch selection in inst pending mode (max-prob; ! marker if det.)."""

from __future__ import annotations

from types import SimpleNamespace

from cod3s.pycatshoo.isimu.app import ISimuApp
from cod3s.pycatshoo.isimu.panels import FireablePanel
from cod3s.pycatshoo.isimu.state import ISimuState


def _branch(state: str, prob: float | None) -> SimpleNamespace:
    return SimpleNamespace(state=state, prob=prob, effects={})


def _inst_trans(comp: str, name: str, branches) -> SimpleNamespace:
    return SimpleNamespace(
        comp_name=comp,
        name=name,
        source="src",
        target=branches,
        end_time=0.0,
    )


async def test_default_selection_is_max_prob() -> None:
    """Default = highest-prob branch."""
    branches = [_branch("low", 0.1), _branch("high", 0.7), _branch("mid", 0.2)]
    trans = _inst_trans("V", "br", branches)
    state = ISimuState(fireable=[trans], pending_inst=[trans])

    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-fireable", FireablePanel)
        panel.refresh_from_state(state)
        await pilot.pause()

        # The cache is keyed by the fireable index (here: 0). Default index = 1 ("high").
        assert panel._inst_choices == {0: 1}


async def test_default_selection_with_ties_picks_first() -> None:
    """When two branches share the max prob, the first one wins."""
    branches = [_branch("a", 0.4), _branch("b", 0.4), _branch("c", 0.2)]
    trans = _inst_trans("V", "br", branches)
    state = ISimuState(fireable=[trans], pending_inst=[trans])

    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-fireable", FireablePanel)
        panel.refresh_from_state(state)
        await pilot.pause()

        assert panel._inst_choices == {0: 0}


async def test_deterministic_branch_marker() -> None:
    """A single-branch inst transition gets the ! marker on its root label."""
    branches = [_branch("only", 1.0)]
    trans = _inst_trans("V", "det", branches)
    state = ISimuState(fireable=[trans], pending_inst=[trans])

    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-fireable", FireablePanel)
        panel.refresh_from_state(state)
        await pilot.pause()

        from textual.widgets import Tree

        tree = app.query_one("#inst-pending-tree", Tree)
        root_label = str(tree.root.children[0].label)
        assert FireablePanel.DETERMINISTIC_MARKER in root_label


async def test_non_deterministic_no_marker() -> None:
    """A multi-branch inst has no ! marker."""
    branches = [_branch("a", 0.5), _branch("b", 0.5)]
    trans = _inst_trans("V", "br", branches)
    state = ISimuState(fireable=[trans], pending_inst=[trans])

    app = ISimuApp(engine=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-fireable", FireablePanel)
        panel.refresh_from_state(state)
        await pilot.pause()

        from textual.widgets import Tree

        tree = app.query_one("#inst-pending-tree", Tree)
        root_label = str(tree.root.children[0].label)
        assert FireablePanel.DETERMINISTIC_MARKER not in root_label
