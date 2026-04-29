"""Pure unit tests for ``group_fires_together`` (no PyCATSHOO required)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cod3s.pycatshoo.isimu.grouping import group_fires_together


def _trans(end_time):
    """Lightweight stand-in for ``PycTransition`` (only ``end_time`` is read)."""
    return SimpleNamespace(end_time=end_time)


def test_empty_list_returns_empty_set() -> None:
    assert group_fires_together([], 0) == set()


def test_negative_or_out_of_range_index_returns_empty() -> None:
    fireable = [_trans(1.0), _trans(2.0)]
    assert group_fires_together(fireable, -1) == set()
    assert group_fires_together(fireable, 5) == set()


def test_none_slot_returns_empty() -> None:
    fireable = [None, _trans(1.0)]
    assert group_fires_together(fireable, 0) == set()


def test_single_match_returns_self() -> None:
    fireable = [_trans(1.0), _trans(2.0), _trans(3.0)]
    assert group_fires_together(fireable, 0) == {0}


def test_groups_equal_end_times() -> None:
    fireable = [_trans(1.0), _trans(1.0), _trans(2.0), _trans(1.0)]
    assert group_fires_together(fireable, 0) == {0, 1, 3}
    assert group_fires_together(fireable, 2) == {2}


def test_skips_none_slots_in_group() -> None:
    fireable = [_trans(1.0), None, _trans(1.0), None, _trans(2.0)]
    assert group_fires_together(fireable, 0) == {0, 2}


def test_strict_equality_by_default() -> None:
    fireable = [_trans(1.0), _trans(1.0 + 1e-9)]
    # Default epsilon = 0.0: floats are not bit-equal, no grouping.
    assert group_fires_together(fireable, 0) == {0}


def test_epsilon_tolerance_groups_close_values() -> None:
    fireable = [_trans(1.0), _trans(1.0 + 1e-9)]
    assert group_fires_together(fireable, 0, epsilon=1e-6) == {0, 1}


@pytest.mark.parametrize("idx", [0, 1, 2])
def test_self_always_in_group_when_fireable(idx: int) -> None:
    fireable = [_trans(t) for t in (1.0, 2.0, 3.0)]
    assert idx in group_fires_together(fireable, idx)


def test_transition_without_end_time_yields_only_self() -> None:
    """A transition whose ``end_time`` is ``None`` (e.g. a non-deterministic
    law placeholder) does not group — only the cursor index is returned."""
    fireable = [SimpleNamespace(end_time=None), _trans(2.0)]
    assert group_fires_together(fireable, 0) == {0}
