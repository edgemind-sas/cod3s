"""Scenario 2 — Common-cause cc_12 (2 targets, delay).

Two targets ``C1`` and ``C2``, one ``ObjFMDelay`` in
``external_rep_indep`` mode. Only the order-2 combo (``cc_12``) ever
fires in the demo window — order-1 individual combos are parked at
``ttf=99999``.

The goal is to see the trigger fire on both targets *simultaneously*,
then observe both targets repair *in the same step* (since they share
the same ``ttr_order_1=5``). Scenario 3 demonstrates how to make the
two repairs happen at different times via the ``p`` modal.

Launch
------

::

    PYTHONPATH="examples/objfm_trigger_02_common_cause:$PYTHONPATH" \\
        uv run cod3s-isimu --factory objfm_trigger_02_common_cause:build_system

Or::

    uv run python examples/objfm_trigger_02_common_cause/objfm_trigger_02_common_cause.py

Test sequence in cod3s-isimu
----------------------------

1. **At t=0**, fireable panel shows ``CX__fm_cc.occ__cc_12`` at
   ``end_time=10``. The order-1 rows ``cc_1`` and ``cc_2`` are filtered
   out because their ``end_time=99999`` exceeds the bound.

2. **Press Enter** on ``cc_12.occ``. Cascade at ``t=10`` (★ on every
   row before pressing):

   - ``CX__fm_cc.occ__cc_12``      (ObjFM occ)
   - ``CX__fm_cc.rep__cc_12``      (delay(0) — trigger reset)
   - ``C1.fm_cc.occ``              (target delay(0), ctrl_C1=True)
   - ``C2.fm_cc.occ``              (target delay(0), ctrl_C2=True)
   - ``C1.working: True → False``
   - ``C2.working: True → False``

3. **After step 1**, fireable panel: ``C1.fm_cc.rep`` and
   ``C2.fm_cc.rep`` both at ``end_time=15`` — they share the ★ marker
   ("fires together"). Pressing Enter on either fires *both* in the
   same simulator step.

4. **Press Enter** on either rep row. Cascade at ``t=15``:

   - ``C1.fm_cc.rep`` and ``C2.fm_cc.rep`` together
   - ``C1.working`` and ``C2.working`` return to True (via reinit)
   - ``ctrl_C1`` and ``ctrl_C2`` reset to False

5. **Both targets back in rep**, the ObjFM is unblocked. Next
   ``cc_12.occ`` shows up at ``end_time=25``. Cycle.

What you should retain
----------------------

* The ★ marker is the visual cue that one Enter will trigger several
  transitions chained at the same instant — both for the trigger
  cascade (step 2) and for the synchronous repair (step 4).
* With identical ``ttr_order_1`` per target *and* a deterministic
  delay law, the two repairs are inevitably synchronous. To see them
  desynchronised, see **Scenario 3** (same setup, different actions).
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
    system = cod3s.PycSystem(name="ObjFMTrigger02CommonCause")
    for n in ("C1", "C2"):
        system.add_component(name=n, cls="Equipment")
    system.add_component(
        cls="ObjFMDelay",
        fm_name="fm_cc",
        targets=["C1", "C2"],
        behaviour="external_rep_indep",
        failure_effects={"working": False},
        # failure_param[i] is the order-(i+1) ttf.
        # cc_1 / cc_2 (order 1) parked at 99999 so they never reach the
        # fireable window; only cc_12 (order 2) fires at ttf=10.
        failure_param=[(99999.0,), (10.0,)],
        # repair_param[0] (order 1) is what targets use for self-repair.
        # repair_param[1] is irrelevant — ObjFM rep is delay(0) in
        # external_rep_indep regardless of the user's value.
        repair_param=[(5.0,), (99999.0,)],
    )
    return system


if __name__ == "__main__":
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
