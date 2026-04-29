"""Scenario 3 — Asynchronous repair via ``p`` re-planning (★ THE demo).

Same system as Scenario 2 (two targets, ``cc_12`` common cause), but
the test sequence below uses the ``p`` modal to **re-plan one target's
repair to a later date**. This is the canonical demonstration of why
``external_rep_indep`` is called *rep_indep*: the two targets' repair
clocks are independent, the ObjFM does not lock them together.

Launch
------

::

    PYTHONPATH="examples/objfm_trigger_03_async_repair:$PYTHONPATH" \\
        uv run cod3s-isimu --factory objfm_trigger_03_async_repair:build_system

Or::

    uv run python examples/objfm_trigger_03_async_repair/objfm_trigger_03_async_repair.py

Test sequence in cod3s-isimu
----------------------------

1. **Press Enter** on ``cc_12.occ`` at ``t=0``. Simulator goes to
   ``t=10``. ``C1`` and ``C2`` ``working=False``. Fireable panel now
   shows ``C1.fm_cc.rep`` and ``C2.fm_cc.rep``, both at
   ``end_time=15`` (★ together).

2. **Move the cursor to ``C2.fm_cc.rep``** (arrow down) and press
   **``p``**. The Re-plan modal opens with title
   *"Replan transition C2.fm_cc.rep"* and a date input pre-filled with
   the current simulator time (``10.0``). **Type ``25.0`` and press
   Enter** (or click "Re-plan"). The modal closes.

3. **Look at the fireable panel**:

   - ``C1.fm_cc.rep`` at ``end_time=15`` (unchanged)
   - ``C2.fm_cc.rep`` at ``end_time=25`` (just re-planned)
   - The ★ no longer joins the two: ``end_time_bound = 15`` and only
     ``C1`` matches.

4. **Press Enter** on ``C1.fm_cc.rep``. Simulator advances to
   ``t=15``. **Only C1 repairs**:

   - ``C1.working: False → True``
   - ``C2.working`` remains ``False``

   This is the visible *independence*: at ``t∈[15, 25]``, ``C1`` is
   working again but ``C2`` is still down. Look at the components
   panel — ``C1.working`` is dim grey (matches initial), ``C2.working``
   is orange (differs from initial but unchanged at last step).

5. **Confirm the ObjFM cannot re-trigger** while ``C2`` is still in
   occ: scan the fireable panel — ``cc_12.occ`` is **absent**, blocked
   by the ``failure_cond`` ("all targets must be in rep"). This is
   important — the trigger model lets the ObjFM cycle freely, but the
   user-supplied condition still gates it.

6. **Press Enter** on ``C2.fm_cc.rep`` (still the only fireable row).
   Simulator advances to ``t=25``. ``C2.working: False → True``. Both
   targets back in rep.

7. **The ObjFM unlocks**: next ``cc_12.occ`` appears at
   ``end_time=35`` (= 25 + ttf=10). Cycle resumes.

What you should retain
----------------------

* The two target repair clocks are owned by the *targets*, not by the
  ObjFM. Re-planning one has no effect on the other.
* The ObjFM is in rep state from ``t=10`` onwards (the trigger reset
  happens immediately) but cannot fire a new combo until both targets
  are in rep again. The "rep_indep" name refers to the **target side**:
  each target's local repair clock runs independently.
* The components panel coloring (dim / orange / bold red) makes the
  partial-recovery state at ``t∈[15, 25]`` immediately readable.
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s


class Equipment(cod3s.PycComponent):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


def build_system() -> cod3s.PycSystem:
    system = cod3s.PycSystem(name="ObjFMTrigger03AsyncRepair")
    for n in ("C1", "C2"):
        system.add_component(name=n, cls="Equipment")
    system.add_component(
        cls="ObjFMDelay",
        fm_name="fm_cc",
        targets=["C1", "C2"],
        behaviour="external_rep_indep",
        failure_effects={"working": False},
        failure_param=[(99999.0,), (10.0,)],
        repair_param=[(5.0,), (99999.0,)],
    )
    return system


if __name__ == "__main__":
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
