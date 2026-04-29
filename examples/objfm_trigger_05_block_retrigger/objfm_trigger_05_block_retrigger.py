"""Scenario 5 — The ObjFM cannot re-trigger while a target is still in occ.

Same system as Scenarios 2 / 3 (two targets, ``cc_12`` common cause,
``ttf=10``, ``ttr_order_1=5``). The point of this scenario is to
**verify a non-event**: between the moment the trigger fires at
``t=10`` and the moment both targets are repaired, the ObjFM is
back in its rep state but its ``cc_12.occ`` is gated by the
``failure_cond`` ("all targets must be in rep"). It does **not** show
up in the fireable list during that window.

Launch
------

::

    PYTHONPATH="examples/objfm_trigger_05_block_retrigger:$PYTHONPATH" \\
        uv run cod3s-isimu --factory objfm_trigger_05_block_retrigger:build_system

Or::

    uv run python examples/objfm_trigger_05_block_retrigger/objfm_trigger_05_block_retrigger.py

Test sequence in cod3s-isimu
----------------------------

1. **Press Enter** on ``cc_12.occ`` at ``t=0``. Simulator goes to
   ``t=10``. ``C1`` and ``C2`` both fail.

2. **Inspect the fireable panel right after step 1**. Expected
   contents:

   - ``C1.fm_cc.rep`` at ``end_time=15``
   - ``C2.fm_cc.rep`` at ``end_time=15``
   - **No ``cc_12.occ`` row** anywhere.

   This is the non-event we want to confirm: the ObjFM is in rep state
   (it triggered through occ at ``t=10`` and bounced back), but the
   ``failure_cond`` requires *both* targets in rep, and currently
   neither is.

3. **Try the active-transitions panel** (if you keep one open in your
   layout — alternatively check via Python with
   ``engine.system.isimu_active_transitions()``): ``cc_12.occ`` is
   ACTIVE (the ObjFM's automaton can transition there from rep) but
   not ``fireable`` because of the cond.

4. **Press ``p`` on ``C2.fm_cc.rep``** and re-plan to ``t=20``. Now
   ``end_time_bound = 15`` → ``C2`` rep is filtered out, ``cc_12.occ``
   is still blocked.

5. **Press Enter** on ``C1.fm_cc.rep`` (the only fireable row). At
   ``t=15``, ``C1.working`` returns to True. ``C2`` is still in occ.

6. **Re-inspect the fireable panel**. Expected:

   - ``C2.fm_cc.rep`` at ``end_time=20``
   - **Still no ``cc_12.occ``** — ``C2`` is in occ, the cond fails.

7. **Press Enter** on ``C2.fm_cc.rep``. Simulator advances to
   ``t=20``. ``C2.working`` returns to True. Both targets in rep.

8. **NOW** the fireable panel shows ``cc_12.occ`` again, planned at
   ``end_time=30`` (= 20 + ttf=10).

What you should retain
----------------------

* The trigger model frees the ObjFM's *automaton state* immediately
  (delay(0) on rep), but does **not** bypass the user's
  ``failure_cond``. The combinatorial conditions (which combos are
  enabled given target states) are still enforced.
* The fireable panel is the right place to *not see* a transition —
  conditions filter rows out. If you suspect a transition should
  appear and it doesn't, check the cond and the target states.
* This is also why a partial repair (one target up, the other still
  down) does not cause cascading re-triggers — exactly what you want
  to model staggered restoration.
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
    system = cod3s.PycSystem(name="ObjFMTrigger05BlockRetrigger")
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
