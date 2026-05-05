"""Post-submission state: panel reverts to timed mode, sequence captured."""

from __future__ import annotations

import pytest

from cod3s import terminate_session
from cod3s.pycatshoo.automaton import PycAutomaton
from cod3s.pycatshoo.component import PycComponent
from cod3s.pycatshoo.isimu.app import ISimuApp
from cod3s.pycatshoo.isimu.engine import ISimuEngine
from cod3s.pycatshoo.isimu.panels import FireablePanel
from cod3s.pycatshoo.system import PycSystem


@pytest.fixture
def inst_then_timed_system():
    """One component with: inst at t=0, then a timed transition with delay 5."""
    system = PycSystem(name="InstThenTimed")
    comp = PycComponent(name="C")

    aut_inst = PycAutomaton(
        name="aut_inst",
        states=["src", "a", "b"],
        init_state="src",
        transitions=[
            {
                "name": "br",
                "source": "src",
                "target": [
                    {"state": "a", "prob": 0.5},
                    {"state": "b", "prob": 0.5},
                ],
            },
        ],
    )
    aut_inst.update_bkd(comp)

    aut_timed = PycAutomaton(
        name="aut_timed",
        states=["x", "y"],
        init_state="x",
        transitions=[
            {
                "name": "go",
                "source": "x",
                "target": "y",
                "is_interruptible": False,
                "occ_law": {"cls": "delay", "time": 5},
            },
        ],
    )
    aut_timed.update_bkd(comp)

    yield system, aut_inst
    terminate_session()


async def test_panel_reverts_to_table_after_inst_resolution(
    inst_then_timed_system,
) -> None:
    """After ``s``, pending_inst is empty and the timed transition takes over."""
    system, aut_inst = inst_then_timed_system
    engine = ISimuEngine(system)
    app = ISimuApp(engine=engine)

    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import DataTable, Tree

        tree = app.query_one("#inst-pending-tree", Tree)
        table = app.query_one("#fireable-table", DataTable)
        assert tree.display is True
        assert table.display is False

        tree.focus()
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        await pilot.pause()

        # Now in timed mode: the inst is resolved, and the timed transition
        # (delay 5) is the only fireable one.
        assert engine.pending_inst() == []
        assert tree.display is False
        assert table.display is True
        assert table.row_count == 1


async def test_history_captures_inst_resolution(inst_then_timed_system) -> None:
    """The fired event after ``s`` carries the inst transition that fired."""
    system, aut_inst = inst_then_timed_system
    engine = ISimuEngine(system)
    app = ISimuApp(engine=engine)

    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import Tree

        tree = app.query_one("#inst-pending-tree", Tree)
        tree.focus()
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        await pilot.pause()

        # Engine history: bootstrap step at t=0 (inst resolution).
        # The fired transition has the inst law with the chosen target.
        last = engine.history[-1]
        assert last.fired_at == 0.0
        # The fired transition list contains the resolved inst (br).
        names = [(t.comp_name, t.name) for t in last.transitions]
        assert ("C", "br") in names
