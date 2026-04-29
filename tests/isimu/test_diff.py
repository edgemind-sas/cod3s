"""Tests for ``snapshot_vars`` / ``snapshot_initials`` / ``diff_snapshots``."""

from __future__ import annotations

from cod3s.pycatshoo.isimu.diff import (
    diff_snapshots,
    snapshot_initials,
    snapshot_vars,
)


def test_diff_snapshots_returns_only_changed() -> None:
    before = {"a": 1, "b": "x", "c": True}
    after = {"a": 1, "b": "y", "c": False}
    diff = diff_snapshots(before, after)
    assert diff == {"b": ("x", "y"), "c": (True, False)}


def test_diff_snapshots_handles_new_keys_in_after() -> None:
    diff = diff_snapshots({"a": 1}, {"a": 1, "b": 2})
    assert diff == {"b": (None, 2)}


def test_diff_snapshots_ignores_keys_only_in_before() -> None:
    diff = diff_snapshots({"a": 1, "b": 2}, {"a": 1})
    assert diff == {}


def test_snapshot_vars_initial_state(small_system) -> None:
    """Before any step, ``snapshot_vars`` reports the declared init values."""
    snap = snapshot_vars(small_system)
    # Both components contribute their two variables, namespaced ``comp.var``.
    assert snap["A.flag"] is False
    assert snap["B.flag"] is False
    assert snap["A.counter"] == 0
    assert snap["B.counter"] == 0


def test_snapshot_initials_matches_declared(small_system) -> None:
    snap = snapshot_initials(small_system)
    assert snap["A.flag"] is False
    assert snap["A.counter"] == 0
    assert snap["B.flag"] is False
    assert snap["B.counter"] == 0


def test_snapshot_keys_use_component_dot_var_namespace(small_system) -> None:
    keys = set(snapshot_vars(small_system).keys())
    assert {"A.flag", "A.counter", "B.flag", "B.counter"}.issubset(keys)
    # No bare variable names without component prefix.
    assert "flag" not in keys
    assert "counter" not in keys
