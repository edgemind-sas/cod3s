"""Shared helpers for the ObjDegMode test suite (isimu driving by name)."""

import re

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def plain_name(tr):
    """Return the bare ``component.transition`` name of a fireable entry."""
    stripped = _ANSI_RE.sub("", str(tr))
    first = stripped.splitlines()[0]
    return first.replace("PycTransition", "").strip()


def fireable_names(system):
    return [plain_name(tr) for tr in system.isimu_fireable_transitions()]


def enter_first_state(system, carrier_frag, entry_frag, date):
    """Fire the carrier CC transition then the target delay(0) entry.

    isimu drives transitions one explicit step at a time: the carrier
    fire latches ctrl, the next step fires the target entry (batched
    with the carrier re-arm at the same date).
    """
    fire_by_name(system, carrier_frag, date=date)
    return fire_by_name(system, entry_frag)


def fire_by_name(system, fragment, date=None):
    """Fire the first fireable transition whose name ends with ``fragment``.

    Returns the list of fired transition names (a same-date batch may fire
    several). Raises ``AssertionError`` when the fragment is not fireable.
    """
    trs = system.isimu_fireable_transitions()
    idx = None
    for i, tr in enumerate(trs):
        if plain_name(tr).endswith(fragment):
            idx = i
            break
    assert (
        idx is not None
    ), f"{fragment!r} not fireable; fireable={[plain_name(t) for t in trs]}"
    if date is None:
        system.isimu_set_transition(idx)
    else:
        system.isimu_set_transition(idx, date=date)
    fired = system.isimu_step_forward()
    return [plain_name(f) for f in fired]
