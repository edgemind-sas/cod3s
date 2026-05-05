"""Complement-share branches must round-trip correctly to Pycatshoo.

Branches with `prob=None` (or no `prob` key) share the residual `1 - sum(probs)`
equally. After `update_bkd` and `isimu_start`, the values held by Pycatshoo
(`law.parameter(idx)`) must reflect the post-validation probabilities, not the
user-supplied `None`s.
"""

import pytest

from cod3s import terminate_session
from cod3s.pycatshoo.automaton import PycAutomaton, PycOccurrenceDistribution
from cod3s.pycatshoo.system import PycSystem


@pytest.fixture
def four_branch_two_complement():
    """4 branches: 2 explicit (0.4, 0.2), 2 complement-share (each 0.2)."""
    system = PycSystem(name="C4")
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
                    {"state": "t0", "prob": 0.4},
                    {"state": "t1", "prob": 0.2},
                    {"state": "t2"},
                    {"state": "t3"},
                ],
            },
        ],
    )
    automaton.update_bkd(comp)
    system.isimu_start()
    yield system, automaton
    terminate_session()


def _branch(automaton):
    for trans in automaton.transitions:
        if trans.name == "branch":
            return trans
    raise AssertionError


def test_complement_split_in_pydantic_model(four_branch_two_complement):
    """Pydantic must split (1 - 0.4 - 0.2) / 2 = 0.2 between the two complement branches."""
    _, automaton = four_branch_two_complement
    trans = _branch(automaton)
    assert trans.target[0].prob == pytest.approx(0.4)
    assert trans.target[1].prob == pytest.approx(0.2)
    assert trans.target[2].prob == pytest.approx(0.2)
    assert trans.target[3].prob == pytest.approx(0.2)


def test_complement_split_visible_in_pycatshoo(four_branch_two_complement):
    """After isimu_start, law.parameter(idx) reflects the post-split probs (N-1)."""
    _, automaton = four_branch_two_complement
    trans = _branch(automaton)
    law = trans._bkd.distLaw()
    assert law.nbParam() == 3
    assert law.parameter(0) == pytest.approx(0.4)
    assert law.parameter(1) == pytest.approx(0.2)
    assert law.parameter(2) == pytest.approx(0.2)


def test_complement_via_from_bkd(four_branch_two_complement):
    """from_bkd reconstructs the N-1 probs after split."""
    _, automaton = four_branch_two_complement
    trans = _branch(automaton)
    dist = PycOccurrenceDistribution.from_bkd(trans._bkd.distLaw())
    assert dist.probs == pytest.approx([0.4, 0.2, 0.2])
