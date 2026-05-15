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
    PycTransition,
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


# --- C5 regression: PycTransition.from_bkd reconstructs the full N-vector
# of probabilities. Before the fix, ``probs`` only held the N-1 values that
# PyCATSHOO stores natively, so the COD3S round-trip dropped the trailing
# branch probability and ``InstOccDistribution.__str__`` reported a list
# shorter than the number of target states.


def test_two_branch_full_probs_via_transition_from_bkd(two_branch_system):
    """``PycTransition.from_bkd`` must yield ``len(probs) == len(target)``
    and reproduce the user-supplied probabilities exactly."""
    _, automaton = two_branch_system
    trans = _get_branch_transition(automaton)
    rebuilt = PycTransition.from_bkd(trans._bkd)
    assert isinstance(rebuilt.occ_law, InstOccDistribution)
    assert rebuilt.occ_law.probs == pytest.approx([0.7, 0.3], rel=1e-9)
    assert [b.prob for b in rebuilt.target] == pytest.approx([0.7, 0.3], rel=1e-9)
    assert sum(rebuilt.occ_law.probs) == pytest.approx(1.0, rel=1e-9)


def test_four_branch_full_probs_via_transition_from_bkd(four_branch_system):
    """Same on a 4-branch transition — verifies the complement assignment
    handles N > 2 correctly."""
    _, automaton = four_branch_system
    trans = _get_branch_transition(automaton)
    rebuilt = PycTransition.from_bkd(trans._bkd)
    assert rebuilt.occ_law.probs == pytest.approx([0.5, 0.2, 0.2, 0.1], rel=1e-9)
    assert [b.prob for b in rebuilt.target] == pytest.approx(
        [0.5, 0.2, 0.2, 0.1], rel=1e-9
    )


def test_inst_str_reports_full_probs_after_from_bkd(two_branch_system):
    """``__str__`` must reflect all N probabilities, not just the N-1
    PyCATSHOO holds. Pre-fix, the second probability was missing entirely
    (``inst([0.7])``)."""
    _, automaton = two_branch_system
    trans = _get_branch_transition(automaton)
    rebuilt = PycTransition.from_bkd(trans._bkd)
    rendered = str(rebuilt.occ_law)
    assert rendered.startswith("inst([0.7")
    # The second probability must appear (was lost before the fix).
    assert ", 0.3" in rendered


# --- T3: the N-vector invariant is now owned by the InstOccDistribution
# helper. These tests exercise the helper directly, independently of
# ``PycTransition.from_bkd``.


def test_helper_appends_complement_when_law_has_n_minus_1_params(two_branch_system):
    _, automaton = two_branch_system
    trans = _get_branch_transition(automaton)
    law = trans._bkd.distLaw()
    assert law.nbParam() == 1  # PyCATSHOO stores N-1
    rebuilt = InstOccDistribution.from_bkd_with_target_count(law, n_targets=2)
    assert len(rebuilt.probs) == 2
    assert sum(rebuilt.probs) == pytest.approx(1.0, rel=1e-9)
    assert rebuilt._bkd is law


def test_helper_rejects_non_inst_law(two_branch_system):
    """Passing a delay/exp law into the helper must raise a clear error."""
    _, automaton = two_branch_system
    # Find a non-inst transition by building a throwaway delay.
    # Use the law of the source state's no-arg constructor path via a fake:
    # easier — just monkey-patch a stub bkd.
    class _FakeLaw:
        @staticmethod
        def name():
            return "exp"

        @staticmethod
        def nbParam():
            return 1

        @staticmethod
        def parameter(i):
            return 0.5

    with pytest.raises(ValueError, match="inst law"):
        InstOccDistribution.from_bkd_with_target_count(_FakeLaw(), n_targets=2)


def test_helper_rejects_invalid_target_count():
    class _FakeLaw:
        @staticmethod
        def name():
            return "inst"

        @staticmethod
        def nbParam():
            return 0

        @staticmethod
        def parameter(i):
            return 0.0

    with pytest.raises(ValueError, match="n_targets must be"):
        InstOccDistribution.from_bkd_with_target_count(_FakeLaw(), n_targets=0)


def test_helper_rejects_param_count_mismatch():
    """Defensive: a law with neither N-1 nor N parameters is rejected."""
    class _FakeLaw:
        @staticmethod
        def name():
            return "inst"

        @staticmethod
        def nbParam():
            return 5  # claims 5 params for a 2-target transition

        @staticmethod
        def parameter(i):
            return 0.1

    with pytest.raises(ValueError, match="parameters"):
        InstOccDistribution.from_bkd_with_target_count(_FakeLaw(), n_targets=2)


def test_helper_accepts_law_already_carrying_full_n_vector():
    """If a hypothetical PyCATSHOO build returns N parameters instead of
    N-1, the helper must accept them as-is rather than re-appending a
    bogus complement."""
    class _FakeLaw:
        @staticmethod
        def name():
            return "inst"

        @staticmethod
        def nbParam():
            return 2

        @staticmethod
        def parameter(i):
            return [0.3, 0.7][i]

    rebuilt = InstOccDistribution.from_bkd_with_target_count(_FakeLaw(), n_targets=2)
    assert rebuilt.probs == pytest.approx([0.3, 0.7], rel=1e-9)
