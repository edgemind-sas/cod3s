"""Atomic submission of branch choices via the ``s`` key binding.

Drives a real ``PycSystem`` through ``ISimuApp`` to verify that pressing ``s``
in inst pending mode resolves all pending inst transitions in a single step
forward.
"""

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
def two_inst_system():
    system = PycSystem(name="ISImSubm")
    auts = {}
    for comp_name, st in (("V", "panne"), ("B", "trip")):
        comp = PycComponent(name=comp_name)
        aut = PycAutomaton(
            name="aut",
            states=["src", st, "ok"],
            init_state="src",
            transitions=[
                {
                    "name": "check",
                    "source": "src",
                    "target": [
                        {"state": st, "prob": 0.2},
                        {"state": "ok"},
                    ],
                },
            ],
        )
        aut.update_bkd(comp)
        auts[comp_name] = aut
    yield system, auts
    terminate_session()


async def test_submit_default_choices_resolves_all(two_inst_system) -> None:
    """Pressing ``s`` with no override fires every pending inst with its default."""
    system, auts = two_inst_system
    engine = ISimuEngine(system)
    app = ISimuApp(engine=engine)

    async with app.run_test() as pilot:
        await pilot.pause()
        # Initial render: 2 inst pending, panel in tree mode.
        panel = app.query_one("#panel-fireable", FireablePanel)
        from textual.widgets import Tree

        tree = app.query_one("#inst-pending-tree", Tree)
        assert tree.display is True
        assert len(tree.root.children) == 2
        # Default = max-prob = ok branch (state_idx 1) for both transitions.
        assert all(idx == 1 for idx in panel._inst_choices.values())

        # Submit. ``s`` is bound at the panel level — focus the tree first.
        tree.focus()
        await pilot.pause()
        await pilot.press("s")
        # Allow the worker thread to drain.
        await pilot.pause()
        await pilot.pause()

        # No more inst pending; both automata went to ``ok`` (default branch).
        assert engine.pending_inst() == []
        assert auts["V"].get_active_state().name == "ok"
        assert auts["B"].get_active_state().name == "ok"


async def test_submit_with_override_resolves_chosen_branch(two_inst_system) -> None:
    """User-overridden choice for V is honored; B keeps the default."""
    system, auts = two_inst_system
    engine = ISimuEngine(system)
    app = ISimuApp(engine=engine)

    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#panel-fireable", FireablePanel)

        # Find the fireable index for V and override its choice to "panne" (state_idx 0).
        v_fireable_idx = None
        for idx, trans in panel._pending_inst_cache:
            if trans.comp_name == "V":
                v_fireable_idx = idx
                break
        assert v_fireable_idx is not None
        panel._inst_choices[v_fireable_idx] = 0

        # Submit.
        from textual.widgets import Tree

        tree = app.query_one("#inst-pending-tree", Tree)
        tree.focus()
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        await pilot.pause()

        assert engine.pending_inst() == []
        # V went to "panne" (overridden) and B to "ok" (default).
        assert auts["V"].get_active_state().name == "panne"
        assert auts["B"].get_active_state().name == "ok"
