"""Scenario 1 — Minimal trigger cycle on a single target (delay law).

This is the smallest interesting ``external_rep_indep`` setup: one target
``C1``, one ``ObjFMDelay`` with ``ttf=10`` and ``ttr_order_1=5``. The point
is to *see* the trigger pattern in action, isolated from any common-cause
combo.

Launch
------

::

    PYTHONPATH="examples/objfm_trigger_01_minimal:$PYTHONPATH" \\
        uv run cod3s-isimu --factory objfm_trigger_01_minimal:build_system

Or::

    uv run python examples/objfm_trigger_01_minimal/objfm_trigger_01_minimal.py

Test sequence in cod3s-isimu
----------------------------

1. **At t=0**, fireable panel shows one row: ``CX__fm.occ__cc_1`` at
   ``end_time=10`` (the ★ column is empty since the row is alone in its
   group).

2. **Press Enter** on it. The simulator advances to ``t=10`` and **four
   transitions chain together in the same step** (★ "fires together"):

   - ``CX__fm.occ__cc_1``     (ObjFM enters occ)
   - ``CX__fm.rep__cc_1``     (delay(0) — the *trigger*: ObjFM goes
                              right back to rep)
   - ``C1.fm.occ``            (target's delay(0) when ``ctrl=True``)
   - ``C1.working: True → False`` (visible in the components panel,
                                   bold red)

   The ObjFM's ``ctrl_fm_C1`` flips to ``True`` along the way (you can
   filter the components panel on ``ctrl`` to see it).

3. **Look at the fireable panel after step 1**: only one row left,
   ``C1.fm.rep`` at ``end_time=15`` (= 10 + ``ttr_order_1``). The ObjFM
   itself is back in rep but its next ``cc_1.occ`` is gated by
   ``failure_cond`` (``C1`` must be in rep), so it doesn't show.

4. **Press Enter** on ``C1.fm.rep``. Simulator advances to ``t=15``.
   ``C1.working: False → True`` (via the reinitialised-variable
   mechanism — there is no ``repair_effect`` to apply); ``ctrl_fm_C1``
   resets to False (handled by the dedicated sensitive method on the
   target automaton).

5. **Now ObjFM and target are both in rep**. The fireable panel shows
   ``CX__fm.occ__cc_1`` again, this time at ``end_time=25`` (= 15 + 10).
   The cycle is complete and ready to repeat.

What you should retain
----------------------

* The ObjFM does **not** stay in occ — it pulses through it for one
  step, only long enough to set ``ctrl_var`` and chain the target.
* The target carries the persistent failure state for ``ttr_order_1``
  units of time.
* No ``repair_effect`` is ever applied — ``working`` returns to True
  via PyCATSHOO's reinit mechanism.
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s


class Equipment(cod3s.PycComponent):
    """Component with a single reinitialised boolean ``working`` variable."""

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


def build_system() -> cod3s.PycSystem:
    system = cod3s.PycSystem(name="ObjFMTrigger01Minimal")
    system.add_component(name="C1", cls="Equipment")
    system.add_component(
        cls="ObjFMDelay",
        fm_name="fm",
        targets=["C1"],
        behaviour="external_rep_indep",
        failure_effects={"working": False},
        # No repair_effects (reinitialised pattern).
        failure_param=10.0,  # ttf
        repair_param=5.0,  # ttr_order_1, used by the target's self-repair
    )
    return system


if __name__ == "__main__":
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
