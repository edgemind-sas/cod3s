"""Mixed exp + delay ObjFM showcase for ``cod3s-isimu``.

Two ObjFMs cohabit a single ``PycSystem``:

* an ``ObjFMExp`` over **three** components (C1, C2, C3) producing three
  individual exponential failure transitions (``cc_1``, ``cc_2``,
  ``cc_3``);
* an ``ObjFMDelay`` over **two** components (D1, D2) producing a single
  deterministic common-cause failure transition (``cc_12`` with
  ``ttf = 10``).

The intent is to exercise the way ``cod3s-isimu`` surfaces fireable
transitions when **non-deterministic** (exp) and **deterministic** (delay)
laws coexist. ``isimu_fireable_transitions``
(``cod3s/pycatshoo/system.py:899``) handles this correctly; this demo is
the playground to verify the TUI faithfully reflects what that function
returns.

How to run
----------

::

    PYTHONPATH="examples/objfm_mix_demo:$PYTHONPATH" \\
        uv run cod3s-isimu --factory objfm_mix_demo:build_system

Or run the file directly (it has a ``__main__`` shortcut)::

    uv run python examples/objfm_mix_demo/objfm_mix_demo.py

The ``isimu_fireable_transitions`` rule
---------------------------------------

Reading ``cod3s/pycatshoo/system.py:899-934`` carefully, the rule is:

1. Compute ``end_time_bound = min(_bkd.endTime() for active transitions)``.
2. Append each active transition iff:

   - it is **deterministic** AND its ``end_time <= end_time_bound``, or
   - it is **non-deterministic** (then its displayed ``end_time`` is
     reset to ``currentTime()`` first, then to ``_bkd.endTime()`` at the
     end of the loop). Non-deterministic transitions are **always**
     appended, regardless of any planned end-time.

3. Other deterministic transitions land in a ``None`` slot (preserved
   for indexing into ``isimu_active_transitions``).

System layout
-------------

============  ==================  =====================================
Component     ObjFM               Transitions
============  ==================  =====================================
C1, C2, C3    CX__fm_exp          cc_1, cc_2, cc_3 (each individual,
                                  exp, λ = 0.05)
D1, D2        DX__fm_dly          cc_12 only (delay, ttf = 10).
                                  cc_1 and cc_2 individual orders are
                                  parked at ttf = 99999 so they stay
                                  ``end_time = 99999`` and never fall
                                  inside ``end_time_bound``.
============  ==================  =====================================

(``ttf = 99999`` is the cleanest way to "deactivate" a delay order — for
``ObjFMDelay`` ``ttf = 0`` means "fire immediately at t = 0", not
"inactive". ``ObjFMExp`` does drop a transition when its rate is 0,
which is why we can write ``failure_param=[(λ,), (0,), (0,)]`` for the
exp side and have higher-order combos drop cleanly.)

What you should see in cod3s-isimu
----------------------------------

**At t = 0 (initial state)**

::

    end_time_bound = min(∞, ∞, ∞, 99999, 99999, 10) = 10

Fireable panel shows **4** rows — three exp (``end_time = ∞`` because
they are unplanned) plus the deterministic ``cc_12`` (``end_time = 10``).
The two ``cc_1``/``cc_2`` of the delay ObjFM are filtered out (end_time
99999 ≫ 10). The ★ marker does not light up across the four rows —
``∞`` does not compare equal to ``10`` (and ``abs(∞ − ∞)`` is ``NaN``).

**Pressing Enter on an exp at t = 0 (no replanning)**

The exp fires at ``currentTime() = 0`` because
``isimu_set_transition(idx, date=None)`` falls back to ``currentTime()``
when the backend ``endTime`` is ``inf``. The component flips
``working=False`` but the simulator clock stays at 0.

**Pressing Enter on the delay(10) at t = 0**

The simulator advances to t = 10 and fires ``cc_12``. Both D1 and D2
flip ``working=False``. The delay's repair transition becomes active
(``ttr = 5``, end_time = 15).

**Replanning an exp to t = 12, then stepping**

  1. Press ``p`` on, say, ``CX__fm_exp.occ__cc_1``. Set the date to
     ``12``. The fireable panel now shows the same four rows but with
     ``cc_1`` at ``end_time = 12`` (the others unchanged).
     ``end_time_bound`` stays at ``10`` because the delay is the
     earliest *finite* end-time.
  2. Press Enter on the delay row → simulator advances to ``t = 10``,
     ``cc_12`` fires.
  3. After the step, the planned exp at ``t = 12`` is still pending.
     The fireable list at ``t = 10`` no longer contains the delay's
     ``cc_12`` (it has just transitioned to ``occ``); a new
     ``cc_12.rep`` is now active (``end_time = 15``).
     ``end_time_bound = min(12, ∞, ∞, 15) = 12``. The exp at 12 is
     now the smallest, the rep(15) is filtered out. You see three exp
     rows; one of them has ``end_time = 12`` and is the one to fire next.
  4. Press Enter on it → simulator advances to ``t = 12``.

  This is the "stop at t = 10 to force the user to fire the delay
  before continuing" behaviour the user expects: the delay at 10 wins
  the race, then the planned exp at 12 wins the next race.

**Replanning an exp to t = 8, then stepping**

  1. Press ``p`` on an exp, set date to ``8``.
  2. Now ``end_time_bound = min(8, ∞, ∞, 10, ...) = 8``. The
     ``delay(10)`` row disappears from the fireable list (10 > 8). The
     three exp rows remain.
  3. Press Enter on the planned exp → simulator advances to ``t = 8``,
     the exp fires.
  4. After the step, ``end_time_bound = min(∞, ∞, 10, ...) = 10`` and
     the ``delay(10)`` is back in the fireable list with the two
     remaining exp.

  This demonstrates the priority rule: a finite-time non-deterministic
  transition can preempt a deterministic one, and the engine
  reflects that immediately in what is fireable.

Things to try
-------------

- **Plan two transitions to the same date** (e.g. one exp at ``t = 10``
  and one exp at ``t = 10``) → both share end_time and get the ★
  ``fires together`` marker. Pressing Enter on either fires both at
  the same simulator time.
- **Step backward** (``b``) on a chain that crossed a delay event:
  ``isimu_step_backward`` resets the planning of any retired
  non-deterministic transition (``reset_planning=True``); the next
  fireable list at the recovered time will show the exp as unplanned
  (``end_time = ∞``) again.
- **Export** (``e``) at any point. The CSV ``fired_at`` column
  captures the actual simulator time of each transition, so a trace
  containing both delay-driven and replanned-exp-driven steps shows a
  mix of round and arbitrary times.
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s


class Equipment(cod3s.PycComponent):
    """Component with a single boolean ``working`` variable, init True.

    Same minimal shape as in ``examples/objfm_demo`` and
    ``examples/objfm_exp_demo``: the focus is on the failure-mode
    dynamics, not flow propagation.
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)


def build_system() -> cod3s.PycSystem:
    """Build the mixed exp + delay ObjFM showcase."""
    system = cod3s.PycSystem(name="ObjFMMixDemo")

    # ------------------------------------------------------------------
    # Three-target ObjFMExp — only individual cc_1, cc_2, cc_3 are active.
    # Higher orders (cc_12, cc_13, cc_23, cc_123) are dropped because their
    # rate is 0 and ObjFMExp.is_occ_law_failure_active(...) returns False
    # for them (see cod3s/pycatshoo/component.py:1745).
    # ------------------------------------------------------------------
    for comp_name in ("C1", "C2", "C3"):
        system.add_component(name=comp_name, cls="Equipment")
    system.add_component(
        cls="ObjFMExp",
        fm_name="fm_exp",
        targets=["C1", "C2", "C3"],
        behaviour="internal",
        failure_effects={"working": False},
        repair_effects={"working": True},
        # failure_param[i] / repair_param[i] target order i+1 (1-indexed).
        # Only the order-1 (individual) entries are non-zero, so only
        # cc_1 / cc_2 / cc_3 get an automaton.
        failure_param=[(0.05,), (0.0,), (0.0,)],
        repair_param=[(0.5,), (0.0,), (0.0,)],
    )

    # ------------------------------------------------------------------
    # Two-target ObjFMDelay — only the common-cause cc_12 is active in
    # the demo time window. ObjFMDelay does not drop transitions whose
    # ttf is 0 (in fact ttf=0 means "fire immediately"), so individual
    # cc_1/cc_2 are parked at ttf = 99999 to keep their end_time outside
    # ``end_time_bound`` until something explicitly plans them.
    # ------------------------------------------------------------------
    for comp_name in ("D1", "D2"):
        system.add_component(name=comp_name, cls="Equipment")
    system.add_component(
        cls="ObjFMDelay",
        fm_name="fm_dly",
        targets=["D1", "D2"],
        behaviour="internal",
        failure_effects={"working": False},
        repair_effects={"working": True},
        # failure_param[0] = order-1 ttf (cc_1 and cc_2 individually)
        # failure_param[1] = order-2 ttf (cc_12, common cause)
        failure_param=[(99999.0,), (10.0,)],
        repair_param=[(5.0,), (5.0,)],
    )

    return system


if __name__ == "__main__":
    # Convenience: ``uv run python examples/objfm_mix_demo/objfm_mix_demo.py``.
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
