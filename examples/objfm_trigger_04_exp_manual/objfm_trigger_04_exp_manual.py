"""Scenario 4 — Exponential laws + manual planning (operator-driven).

Replaces the deterministic delays of Scenarios 1–3 with **exponential**
occurrence laws. Because PyCATSHOO does not auto-sample exponential
distributions in interactive mode, every transition shows up in the
fireable panel with ``end_time=∞`` until the user explicitly re-plans
it via ``p``. The operator orchestrates the trigger and the two
target repairs at the dates of their choice — useful for:

- *Reproducing a specific scenario* extracted from a run-cod3s-study
  Monte-Carlo trace,
- *Stress-testing a critical sequence* (e.g. order of repair matters
  for downstream sequencing analysis),
- *Teaching* the trigger semantics without random noise.

Launch
------

::

    PYTHONPATH="examples/objfm_trigger_04_exp_manual:$PYTHONPATH" \\
        uv run cod3s-isimu --factory objfm_trigger_04_exp_manual:build_system

Or::

    uv run python examples/objfm_trigger_04_exp_manual/objfm_trigger_04_exp_manual.py

Test sequence in cod3s-isimu
----------------------------

1. **At t=0**, the fireable panel shows **one row**:
   ``CX__fm_cc.occ__cc_12`` at ``end_time=∞``.

   .. note::

      The order-1 automata (``cc_1``, ``cc_2``) are still created in
      ``CX__fm_cc.automata_d`` because the ``external_rep_indep``
      validation requires the order-1 repair law to be active
      (``rate>0``). However their failure rate is 0, so PyCATSHOO does
      not expose their ``occ`` transition as active — they will not
      pollute the fireable panel.

2. **Move the cursor to ``cc_12.occ``** and press **``p``**. Modal
   title: *"Replan transition CX__fm_cc.occ__cc_12"*. **Type ``8.0``**
   and submit.

3. **Press Enter** on ``cc_12.occ``. Simulator advances to ``t=8``.
   The trigger cascade fires (★ on cc_12.occ, cc_12.rep, C1.fm_cc.occ,
   C2.fm_cc.occ all at end_time=8):

   - ``C1.working: True → False``
   - ``C2.working: True → False``

4. **Two new exp transitions** appear: ``C1.fm_cc.rep`` and
   ``C2.fm_cc.rep``, both at ``end_time=∞``. They do **not** share
   the ★ marker (``∞`` is not comparable to itself in this engine —
   each unplanned exp row is alone in its group).

5. **Press ``p`` on ``C1.fm_cc.rep``**, type ``12.0``, submit.
   **Press ``p`` on ``C2.fm_cc.rep``**, type ``19.5``, submit.

6. **Press Enter** on ``C1.fm_cc.rep``. Simulator advances to
   ``t=12``. ``C1.working: False → True``. C2 still down.

7. **Press Enter** on ``C2.fm_cc.rep``. Simulator advances to
   ``t=19.5``. ``C2.working: False → True``.

8. **Cycle**: at ``t=19.5``, ``cc_12.occ`` reappears in fireable
   (``end_time=∞`` again — exp is unplanned). Repeat from step 2 to
   chain another scenario.

What you should retain
----------------------

* In interactive mode with exp laws, **the user models the time line**.
  cod3s-isimu is *not* a Monte-Carlo run; for that, use
  ``run-cod3s-study`` which samples internally.
* The trigger semantic is identical to scenarios 2/3 — only the time
  values differ (and you choose them).
* Try ``b`` (step backward) after step 7 — the engine pops the last
  ``FiredEvent`` and re-opens the planning of the retired
  non-deterministic transition (``end_time`` back to ``∞``); pressing
  ``p`` again lets you experiment with a different date for ``C2``.
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
    system = cod3s.PycSystem(name="ObjFMTrigger04ExpManual")
    for n in ("C1", "C2"):
        system.add_component(name=n, cls="Equipment")
    system.add_component(
        cls="ObjFMExp",
        fm_name="fm_cc",
        targets=["C1", "C2"],
        behaviour="external_rep_indep",
        failure_effects={"working": False},
        # Order 1 failure rate = 0 (cc_1, cc_2 never fire spontaneously
        # but the automata still exist because order-1 repair is active).
        # Order 2 (cc_12) is the common-cause we want to manually plan.
        failure_param=[(0.0,), (0.1,)],
        # Order-1 repair rate must be active for external_rep_indep
        # (the constructor raises ValueError otherwise) — it is the rate
        # the targets use for their independent self-repair. Order 2 is
        # ignored (ObjFM rep is delay(0)).
        repair_param=[(0.2,), (0.0,)],
    )
    return system


if __name__ == "__main__":
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
