"""Pydantic validation rules for instantaneous-branching transitions.

The brainstorm decided that branches must have **distinct target states** within
a single inst transition (key decision #3). The sum of explicit probabilities
must also stay ≤ 1 (with float tolerance). Branches with `prob=None` (or with
no `prob` key) share the complement equally.
"""

import pytest

from cod3s.pycatshoo.automaton import PycTransition


def _build(target):
    return PycTransition(name="branch", source="src", target=target)


# ---------------------------------------------------------------------------
# Duplicate target rejection
# ---------------------------------------------------------------------------


def test_duplicate_targets_rejected():
    with pytest.raises(ValueError, match="distinct"):
        _build(
            [
                {"state": "a", "prob": 0.4},
                {"state": "a", "prob": 0.6},
            ]
        )


def test_duplicate_targets_with_none_rejected():
    """Even when one branch has no prob (complement), duplicates are rejected."""
    with pytest.raises(ValueError, match="distinct"):
        _build(
            [
                {"state": "a", "prob": 0.4},
                {"state": "a"},
            ]
        )


# ---------------------------------------------------------------------------
# Sum-of-probs constraint
# ---------------------------------------------------------------------------


def test_sum_probs_above_one_rejected():
    with pytest.raises(ValueError, match="sum"):
        _build(
            [
                {"state": "a", "prob": 0.6},
                {"state": "b", "prob": 0.5},
            ]
        )


def test_sum_probs_just_above_one_rejected():
    with pytest.raises(ValueError, match="sum"):
        _build(
            [
                {"state": "a", "prob": 0.5},
                {"state": "b", "prob": 0.5001},
            ]
        )


def test_sum_probs_just_at_one_accepted():
    """Sum exactly 1 is fine (no complement-share branch needed)."""
    trans = _build(
        [
            {"state": "a", "prob": 0.4},
            {"state": "b", "prob": 0.6},
        ]
    )
    assert trans.target[0].prob == pytest.approx(0.4)
    assert trans.target[1].prob == pytest.approx(0.6)


def test_sum_probs_below_one_with_complement_branch():
    """Branch with no prob picks up the residual."""
    trans = _build(
        [
            {"state": "a", "prob": 0.3},
            {"state": "b", "prob": 0.4},
            {"state": "c"},
        ]
    )
    assert trans.target[2].prob == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Mixed prob=None / explicit
# ---------------------------------------------------------------------------


def test_explicit_none_treated_as_complement():
    """`prob: None` behaves like a missing prob key (complement-share)."""
    trans = _build(
        [
            {"state": "a", "prob": 0.5},
            {"state": "b", "prob": None},
        ]
    )
    assert trans.target[1].prob == pytest.approx(0.5)


def test_two_complement_branches_share_residual():
    """Two branches without prob share the residual equally."""
    trans = _build(
        [
            {"state": "a", "prob": 0.6},
            {"state": "b"},
            {"state": "c"},
        ]
    )
    assert trans.target[1].prob == pytest.approx(0.2)
    assert trans.target[2].prob == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Empty branch list
# ---------------------------------------------------------------------------


def test_empty_branch_list_rejected():
    with pytest.raises(ValueError):
        _build([])
