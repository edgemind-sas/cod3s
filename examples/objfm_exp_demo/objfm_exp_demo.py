"""Multi-target ObjFM showcase with **exponential** failure / repair laws.

Three independent equipments — pump1, pump2, valve — each carry their own
``ObjFMExp`` failure mode (``behaviour="internal"``) with different rates.
Failures and repairs are **exp-distributed**, but ``cod3s-isimu`` does not
auto-sample those laws — that is by design (see the engine docstring).
This file is the canonical demo for the **manual-planning workflow** that
exp-based models require in interactive mode.

How interactive mode handles non-deterministic transitions
----------------------------------------------------------

``PycSystem.isimu_fireable_transitions`` (``cod3s/pycatshoo/system.py:899``)
treats ``exp`` / ``uniform`` / … laws specially:

  - they are **always** in the fireable list,
  - their displayed ``end_time`` is the underlying PyCATSHOO planned
    end-time, which is ``inf`` until the user explicitly plans them.

Translated to the cod3s-isimu UX, every unplanned exp transition shows
up in the fireable panel with ``end_time = ∞``. Pressing ``Enter`` on
it fires it **right now** at the current simulator time — the
``isimu_set_transition`` default (when no date is given) falls back to
``system.currentTime()`` for an unplanned transition. The simulator
clock does not advance.

To make time pass through an exponentially-distributed delay, **re-plan
the transition** with the ``p`` modal (or call
``ISimuEngine.replan(trans_id, date=...)`` programmatically) to a
chosen future date. This keeps the operator in full control of the
trace; it is the same workflow PyCATSHOO's interactive mode supports
natively.

The ★ "fires together" marker does **not** light up across multiple
unplanned exp transitions — the comparison ``abs(∞ - ∞) ≤ ε`` is NaN,
so each unplanned exp row appears alone in its group. Once you re-plan
two of them to the same finite date, they share the marker as expected.

How to run
----------

::

    PYTHONPATH="examples/objfm_exp_demo:$PYTHONPATH" \\
        uv run cod3s-isimu --factory objfm_exp_demo:build_system

Layout of the system
--------------------

============  ================  ====================================
Equipment     ObjFM             Rates (per unit time)
============  ================  ====================================
pump1         pump1__fm_p1      λ = 0.10  (mean ttf = 10)
                                μ = 0.50  (mean ttr =  2)
pump2         pump2__fm_p2      λ = 0.05  (mean ttf = 20)
                                μ = 0.30  (mean ttr ≈ 3.3)
valve         valve__fm_v       λ = 0.02  (mean ttf = 50)
                                μ = 0.10  (mean ttr = 10)
============  ================  ====================================

Each equipment exposes a single boolean ``working`` variable initialised
to ``True``. On failure → ``False``, on repair → ``True``.

There is **no** common-cause failure here — that would require
``external_rep_indep`` whose target propagation is still WIP on master.
What this demo shows clearly is **per-component independence**: each
ObjFM lives on its own automaton, drives its own target, and has its
own λ / μ.

What you should observe in cod3s-isimu
--------------------------------------

**At t=0** — three transitions fireable (the three ``occ`` of the three
ObjFMs), each displayed with ``end_time = ∞`` (unplanned). Each row
appears in its own group (no ★) because all three have the same ``∞``
marker — the engine treats those as not-comparable.

**Pressing Enter on one row at t=0** — fires it instantaneously. The
component flips ``working`` to ``False`` and the simulator clock stays
at t=0. The fireable panel now shows that ObjFM's ``rep`` (also exp,
``end_time = ∞``) plus the other two ``occ`` transitions still
pending, all unplanned.

**Pressing ``p`` on a row** — opens the re-plan modal. Type a future
date (e.g. ``5.0``) and press Enter. The transition is now planned at
t=5; PyCATSHOO will keep the others at currentTime so the ★ no longer
groups everything. Press Enter on the re-planned row → simulator
advances to t=5 and the transition fires.

**Variable coloring** in the components panel (right):

  - dim grey — value matches its declared initial (``True``).
  - **bold red** — value just changed (``True → False`` at the failure
    step, then ``False → True`` at the repair step).
  - orange — value differs from initial (typically: currently failed)
    but the last step did not change it.

A typical exploration session
-----------------------------

A way to drive a meaningful trace from the TUI::

    1. Press p on ``pump1__fm_pump1.occ``. Set date to 8.0 (sample
       below the mean ttf of 10, easy "first failure"). Press Enter.
       Press Enter again on the row → simulator jumps to t=8, pump1
       working=False, pump1.rep + pump2.occ + valve.occ fireable at
       end_time=8.

    2. Press p on ``pump1__fm_pump1.rep``. Date 9.5 (just over a unit
       past, μ=0.5 means mean ttr=2 — tight repair). Fire it →
       simulator at t=9.5, pump1 back to working=True.

    3. Press p on ``pump2__fm_pump2.occ`` to date 25, fire. Etc.

This gives you an **operator-driven scenario** where every clock
advance is your decision. To run a "natural" exp simulation with
sampled clocks, use ``run-cod3s-study`` in Monte-Carlo mode — that's
what it's there for.

Things to try
-------------

- **Independence**: re-plan two ObjFMs to the same future date (e.g.
  pump1.occ at t=10, valve.occ at t=10). They will fire together at
  step t=10 and the ★ will mark them — that's the only way to get a
  ★ across exp transitions, since the engine does not pick the date
  for you.
- **Step backward** (``b``): rolls back the last step *and* resets the
  planning of any non-deterministic transition that was fired (see
  ``PycSystem.isimu_step_backward``). Useful to retry a re-plan.
- **Reset** (``r``): everything back to t=0 with all ``working`` =
  ``True`` and all ObjFM ``occ`` transitions fireable at
  ``end_time = ∞`` (unplanned).
- **Export** (``e``): the CSV ``fired_at`` column captures the actual
  firing time you chose by re-planning.

Limitations
-----------

* Common-cause failures with truly independent repairs require the
  ``external_rep_indep`` "pulse" semantic; it is sketched as commented
  code in ``examples/objfm_demo/objfm_demo.py`` and will be enabled
  when the ObjFM brainstorm's pulse model is implemented.
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s


class Equipment(cod3s.PycComponent):
    """Component with a single reinitialised boolean ``working`` variable.

    Same shape as ``examples/objfm_demo/SimpleEquipment`` — intentionally
    minimal. ``working`` is ``setReinitialized(True)`` so PyCATSHOO restores
    it to its initial ``True`` value when no ObjFM automaton actively
    forces it to ``False``. The ObjFMs below only set ``failure_effects``
    and leave ``repair_effects`` empty (project-wide convention).
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


def build_system() -> cod3s.PycSystem:
    """Build the multi-target exponential-law showcase.

    Returns a populated ``PycSystem`` with three equipments and three
    independent ObjFMExp internal failure modes.
    """
    system = cod3s.PycSystem(name="ObjFMExpDemo")

    equipments = [
        # (name,  λ_fail, μ_repair)
        ("pump1", 0.10, 0.50),
        ("pump2", 0.05, 0.30),
        ("valve", 0.02, 0.10),
    ]

    for comp_name, lam, mu in equipments:
        system.add_component(name=comp_name, cls="Equipment")
        system.add_component(
            cls="ObjFMExp",
            fm_name=f"fm_{comp_name}",
            targets=[comp_name],
            behaviour="internal",
            failure_effects={"working": False},
            # No repair_effects (reinitialised ``working`` returns to True).
            failure_param=lam,
            repair_param=mu,
        )

    return system


if __name__ == "__main__":
    # Convenience: ``python examples/objfm_exp_demo/objfm_exp_demo.py`` opens
    # the TUI ready for the manual-planning workflow described in the docstring.
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
