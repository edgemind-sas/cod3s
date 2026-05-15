"""Regression tests for the C3 bug.

``PycSystem.isimu_set_transition(trans_id, date=, state_index=)`` used
to gate the "user-provided value vs. fall back" decision on a truthy
check (``if not date:`` / ``if not state_index:``). That meant:

* ``date=0.0`` was treated as "not provided" → the explicit immediate
  scheduling was silently replaced by ``_bkd.endTime()`` (a sampled
  future for exponential laws). This was a real behaviour bug.
* ``state_index=0`` was treated as "not provided" → re-assigned to 0.
  Accidentally benign because the fallback happened to match the user's
  value, but semantically fragile.

Fix flipped both guards to ``is None``.
"""

import pytest

import cod3s
from cod3s.pycatshoo.automaton import PycAutomaton
from cod3s.pycatshoo.system import PycSystem


@pytest.fixture
def system_with_exp():
    """A minimal system with one exponential transition (`ok` → `nok`).

    After ``isimu_start``, ``currentTime() == 0.0`` and the transition's
    sampled ``endTime() > 0`` (always strictly positive for an
    exponential rate). This is the exact context where the old truthy
    check would silently override ``date=0.0``.
    """
    system = PycSystem(name="SysSetTransEdges")
    comp = system.add_component(name="C", cls="PycComponent")
    aut = PycAutomaton(
        name="aut",
        states=["ok", "nok"],
        init_state="ok",
        transitions=[
            {
                "name": "ok_nok",
                "source": "ok",
                "target": "nok",
                "occ_law": {"cls": "exp", "rate": 1.0},
            },
        ],
    )
    aut.update_bkd(comp)
    system.isimu_start()
    yield system
    system.isimu_stop()
    cod3s.terminate_session()


def test_explicit_date_zero_overrides_a_scheduled_future(system_with_exp):
    """``date=0.0`` must reach the backend untouched, even when a prior
    schedule placed the transition in the future.

    Pre-fix: ``not 0.0`` evaluated to ``True``; the fallback then read
    the previously-scheduled ``endTime() = 10.0`` (finite, in range) and
    silently replaced the user's ``0.0`` with ``10.0``. The user lost
    control over the re-planning.
    """
    system = system_with_exp
    trans = system.isimu_fireable_transitions()[0]

    # First, schedule the transition in the future.
    system.isimu_set_transition(0, date=10.0)
    assert trans._bkd.endTime() == 10.0

    # Then the user changes their mind and wants it immediate (date=0.0).
    system.isimu_set_transition(0, date=0.0)
    assert trans._bkd.endTime() == 0.0


def test_explicit_state_index_zero_is_preserved(system_with_exp):
    """``state_index=0`` must reach the backend untouched.

    Behaviour is unchanged in practice because the fallback also picks
    ``0``, but the path through the code now takes the user-provided
    branch — protects against future fallback changes.
    """
    system = system_with_exp
    # Sanity: the only fireable transition has a single target state,
    # so ``state_index=0`` is the only valid value.
    system.isimu_set_transition(0, date=5.0, state_index=0)
    assert system.isimu_fireable_transitions()[0]._bkd.endTime() == 5.0


def test_none_date_falls_back_to_end_time(system_with_exp):
    """``date=None`` (and omitted) falls back to ``endTime()`` when
    finite, else ``currentTime()``."""
    system = system_with_exp
    trans = system.isimu_fireable_transitions()[0]

    # Schedule a finite endTime, then call with date=None.
    system.isimu_set_transition(0, date=7.0)
    assert trans._bkd.endTime() == 7.0

    # date=None must pick up the existing finite endTime.
    system.isimu_set_transition(0)
    assert trans._bkd.endTime() == 7.0
