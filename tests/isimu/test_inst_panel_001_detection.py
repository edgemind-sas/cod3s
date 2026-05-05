"""Engine-layer detection of pending inst transitions.

When a ``PycSystem`` has fireable inst transitions at ``currentTime``, the
engine must surface them via a dedicated ``pending_inst()`` accessor and let
the UI batch-resolve them via ``resolve_inst(choices)``.
"""

from __future__ import annotations

import Pycatshoo as Pyc
import pytest

from cod3s import terminate_session
from cod3s.pycatshoo.automaton import PycAutomaton
from cod3s.pycatshoo.component import PycComponent
from cod3s.pycatshoo.isimu.engine import ISimuEngine
from cod3s.pycatshoo.system import PycSystem


@pytest.fixture
def system_one_inst():
    """One component, one inst transition pending at t=0.

    Yields ``(system, automata_by_comp)`` so tests can query active states
    without going through ``automata_d`` (only populated by ``add_automaton``).
    """
    system = PycSystem(name="InstDet1")
    comp = PycComponent(name="V")
    aut = PycAutomaton(
        name="aut",
        states=["src", "panne_severe", "panne_legere", "ok"],
        init_state="src",
        transitions=[
            {
                "name": "fail_check",
                "source": "src",
                "target": [
                    {"state": "panne_severe", "prob": 0.05},
                    {"state": "panne_legere", "prob": 0.10},
                    {"state": "ok"},
                ],
            },
        ],
    )
    aut.update_bkd(comp)
    yield system, {"V": aut}
    terminate_session()


@pytest.fixture
def system_two_inst():
    """Two components with two simultaneous pending inst transitions at t=0."""
    system = PycSystem(name="InstDet2")
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


# ---------------------------------------------------------------------------
# pending_inst()
# ---------------------------------------------------------------------------


def test_pending_inst_returns_one_inst_transition(system_one_inst):
    system, _ = system_one_inst
    engine = ISimuEngine(system)
    engine.start()

    pending = engine.pending_inst()
    assert len(pending) == 1
    assert pending[0].name == "fail_check"
    # An inst transition has a list-typed target.
    assert isinstance(pending[0].target, list)


def test_pending_inst_returns_two_simultaneous(system_two_inst):
    system, _ = system_two_inst
    engine = ISimuEngine(system)
    engine.start()

    pending = engine.pending_inst()
    names = sorted((t.comp_name, t.name) for t in pending)
    assert names == [("B", "check"), ("V", "check")]


# ---------------------------------------------------------------------------
# resolve_inst()
# ---------------------------------------------------------------------------


def _trans_index_in_fireable(fireable, comp_name, trans_name):
    for i, t in enumerate(fireable):
        if t is None:
            continue
        if t.comp_name == comp_name and t.name == trans_name:
            return i
    raise AssertionError(f"transition {comp_name}.{trans_name} not in fireable")


def test_resolve_inst_picks_chosen_branch(system_one_inst):
    """Choosing branch index 0 (panne_severe) lands the automaton there."""
    system, auts = system_one_inst
    engine = ISimuEngine(system)
    engine.start()

    fireable = engine.fireable()
    trans_id = _trans_index_in_fireable(fireable, "V", "fail_check")

    engine.resolve_inst({trans_id: 0})  # 0 = panne_severe
    # After resolution, no inst is pending and the automaton is in panne_severe.
    assert engine.pending_inst() == []
    assert auts["V"].get_active_state().name == "panne_severe"


def test_resolve_inst_atomic_two_pending(system_two_inst):
    """Two pending inst transitions resolved in a single call."""
    system, auts = system_two_inst
    engine = ISimuEngine(system)
    engine.start()

    pending = engine.pending_inst()
    assert len(pending) == 2

    fireable = engine.fireable()
    choices = {
        _trans_index_in_fireable(fireable, "V", "check"): 0,
        _trans_index_in_fireable(fireable, "B", "check"): 0,
    }

    engine.resolve_inst(choices)
    assert engine.pending_inst() == []
    # Both automata landed on their failure branch.
    assert auts["V"].get_active_state().name == "panne"
    assert auts["B"].get_active_state().name == "trip"
