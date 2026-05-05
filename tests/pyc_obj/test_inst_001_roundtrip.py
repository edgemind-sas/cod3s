"""Round-trip audit for InstOccDistribution probability assignment.

Verifies that the probabilities passed to ``InstOccDistribution(probs=...)``
are correctly transmitted to Pycatshoo via ``to_bkd``/``setParameter`` and
recoverable via ``law.parameter(idx)`` and ``PycOccurrenceDistribution.from_bkd``.

This addresses the long-standing ``# NOT WORKING: PARAMETERS DOES NOT SEEMED
TO BE ASSIGNED...`` comment in ``cod3s/pycatshoo/automaton.py:441`` without
relying on Pycatshoo's RNG or any actual simulation. Pycatshoo stores the
``N-1`` first probabilities; the last is computed as the complement.
"""

import pytest

from cod3s import terminate_session
from cod3s.pycatshoo.automaton import (
    InstOccDistribution,
    PycAutomaton,
    PycOccurrenceDistribution,
)
from cod3s.pycatshoo.system import PycSystem


@pytest.fixture
def two_branch_system():
    """Two-branch inst transition with asymmetric probs to detect index bugs."""
    system = PycSystem(name="RT2")
    comp = system.add_component(name="C", cls="PycComponent")
    automaton = PycAutomaton(
        name="aut",
        states=["src", "tgt_a", "tgt_b"],
        init_state="src",
        transitions=[
            {
                "name": "branch",
                "source": "src",
                "target": [
                    {"state": "tgt_a", "prob": 0.7},
                    {"state": "tgt_b", "prob": 0.3},
                ],
            },
        ],
    )
    automaton.update_bkd(comp)
    system.isimu_start()
    yield system, automaton
    terminate_session()


@pytest.fixture
def four_branch_system():
    """Four-branch inst transition with mixed probs."""
    system = PycSystem(name="RT4")
    comp = system.add_component(name="C", cls="PycComponent")
    automaton = PycAutomaton(
        name="aut",
        states=["src", "t0", "t1", "t2", "t3"],
        init_state="src",
        transitions=[
            {
                "name": "branch",
                "source": "src",
                "target": [
                    {"state": "t0", "prob": 0.5},
                    {"state": "t1", "prob": 0.2},
                    {"state": "t2", "prob": 0.2},
                    {"state": "t3", "prob": 0.1},
                ],
            },
        ],
    )
    automaton.update_bkd(comp)
    system.isimu_start()
    yield system, automaton
    terminate_session()


def _get_branch_transition(automaton):
    for trans in automaton.transitions:
        if trans.name == "branch":
            return trans
    raise AssertionError("branch transition not found")


def test_two_branch_target_count(two_branch_system):
    _, automaton = two_branch_system
    trans = _get_branch_transition(automaton)
    assert trans._bkd.targetCount() == 2


def test_two_branch_target_order_preserved(two_branch_system):
    _, automaton = two_branch_system
    trans = _get_branch_transition(automaton)
    assert trans._bkd.target(0).basename() == "tgt_a"
    assert trans._bkd.target(1).basename() == "tgt_b"


def test_two_branch_law_nbparam(two_branch_system):
    """Pycatshoo stores N-1 probs (last is complement)."""
    _, automaton = two_branch_system
    trans = _get_branch_transition(automaton)
    law = trans._bkd.distLaw()
    assert law.nbParam() == 1


def test_two_branch_law_parameter_value(two_branch_system):
    """The first probability written via setParameter is held by Pycatshoo."""
    _, automaton = two_branch_system
    trans = _get_branch_transition(automaton)
    law = trans._bkd.distLaw()
    assert law.parameter(0) == pytest.approx(0.7, rel=1e-9)


def test_two_branch_from_bkd_roundtrip(two_branch_system):
    """from_bkd reconstructs the probs list as Pycatshoo holds it (N-1 entries)."""
    _, automaton = two_branch_system
    trans = _get_branch_transition(automaton)
    dist = PycOccurrenceDistribution.from_bkd(trans._bkd.distLaw())
    assert isinstance(dist, InstOccDistribution)
    assert dist.probs == pytest.approx([0.7], rel=1e-9)


def test_four_branch_target_count(four_branch_system):
    _, automaton = four_branch_system
    trans = _get_branch_transition(automaton)
    assert trans._bkd.targetCount() == 4


def test_four_branch_target_order(four_branch_system):
    _, automaton = four_branch_system
    trans = _get_branch_transition(automaton)
    assert [trans._bkd.target(i).basename() for i in range(4)] == [
        "t0",
        "t1",
        "t2",
        "t3",
    ]


def test_four_branch_law_nbparam(four_branch_system):
    _, automaton = four_branch_system
    trans = _get_branch_transition(automaton)
    law = trans._bkd.distLaw()
    assert law.nbParam() == 3


def test_four_branch_law_parameter_values(four_branch_system):
    """Each of the N-1 first probs is correctly indexed."""
    _, automaton = four_branch_system
    trans = _get_branch_transition(automaton)
    law = trans._bkd.distLaw()
    assert law.parameter(0) == pytest.approx(0.5, rel=1e-9)
    assert law.parameter(1) == pytest.approx(0.2, rel=1e-9)
    assert law.parameter(2) == pytest.approx(0.2, rel=1e-9)


def test_four_branch_from_bkd_roundtrip(four_branch_system):
    _, automaton = four_branch_system
    trans = _get_branch_transition(automaton)
    dist = PycOccurrenceDistribution.from_bkd(trans._bkd.distLaw())
    assert isinstance(dist, InstOccDistribution)
    assert dist.probs == pytest.approx([0.5, 0.2, 0.2], rel=1e-9)
