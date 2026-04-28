"""Group fireable transitions that would fire together.

PyCATSHOO chains every transition planned at the same ``endTime`` during a
single ``stepForward`` (notably all ``delay(0)`` transitions). The TUI marks
them with a "fires together" badge so the user understands the consequence
before pressing Enter.

The implementation operates on the index-aware list returned by
``PycSystem.isimu_fireable_transitions()`` (which preserves ``None`` slots for
non-fireable active transitions) and returns the indices belonging to the same
group as the current cursor position.
"""

from __future__ import annotations

from typing import Any, List, Optional, Set


def group_fires_together(
    fireable: List[Optional[Any]],
    selected_idx: int,
    epsilon: float = 0.0,
) -> Set[int]:
    """Return indices of transitions sharing the cursor's planned ``end_time``.

    Args:
        fireable: List as returned by ``PycSystem.isimu_fireable_transitions``.
            Entries may be ``None`` (slot reserved for a non-fireable active
            transition) or instances exposing an ``end_time`` attribute.
        selected_idx: Cursor position in ``fireable``. Out-of-range or
            ``None``-slot indices return an empty set.
        epsilon: Tolerance for the float comparison. Defaults to ``0.0``
            (strict equality) because PyCATSHOO produces bit-identical
            ``endTime`` for chained ``delay(0)`` transitions and shared
            deterministic delays.

    Returns:
        A set of indices. The selected index itself is always included when the
        cursor sits on a fireable transition.
    """
    if selected_idx < 0 or selected_idx >= len(fireable):
        return set()
    pivot = fireable[selected_idx]
    if pivot is None:
        return set()
    target_time = getattr(pivot, "end_time", None)
    if target_time is None:
        return {selected_idx}
    return {
        idx
        for idx, trans in enumerate(fireable)
        if trans is not None
        and getattr(trans, "end_time", None) is not None
        and abs(trans.end_time - target_time) <= epsilon
    }
