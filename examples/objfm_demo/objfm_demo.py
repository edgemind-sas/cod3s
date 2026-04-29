"""ObjFM demonstration system for ``cod3s-isimu``.

Two `ObjFM` failure modes side-by-side, with **deterministic delays** so
every transition fires at a predictable instant. Designed to be loaded in
`cod3s-isimu` (`--factory` mode) so the user can step through the cycles
and see the structural difference between the two behaviours live.

How to run
----------

With ``uv`` (recommended — no manual venv activation)::

    PYTHONPATH="examples/objfm_demo:$PYTHONPATH" \
        uv run cod3s-isimu --factory objfm_demo:build_system

The ``$PYTHONPATH`` carry-over is intentional: PyCATSHOO is exposed via the
shell's existing ``PYTHONPATH`` (``$HOME/Work/EdgeMind/Dev/pycatshoo/Core/lib``),
and we want to *prepend* the example's directory rather than replace the
whole path.

Or run the file directly via uv (it has a ``__main__`` shortcut)::

    PYTHONPATH="examples/objfm_demo:$PYTHONPATH" \
        uv run python examples/objfm_demo/objfm_demo.py

If you prefer activating the venv yourself::

    source .venv/bin/activate
    PYTHONPATH="examples/objfm_demo:$PYTHONPATH" cod3s-isimu --factory objfm_demo:build_system

You should see the four panels populate. Press ``Enter`` on the highlighted
fireable row to advance the simulator one step, repeatedly.

Layout of the system
--------------------

Two scenarios live in the same `PycSystem` and never interact:

==========  ===============  =======================================
Component   ObjFM            Behaviour
==========  ===============  =======================================
C1          C1__fm_int       internal       (failure_effects applied
                                             directly by the ObjFM)
C2          C2__fm_ext       external       (target carries its own
                                             automaton; ObjFM/target
                                             mutually locked via
                                             ``ctrl_fm_ext_C2``)
==========  ===============  =======================================

Each component has a single boolean variable ``working`` initialised to
``True``. When the failure mode hits, ``working`` is forced to ``False``;
on repair it goes back to ``True``.

A third behaviour exists in the codebase, ``external_rep_indep``. Its
target propagation is **work in progress** on this branch (see
``docs/brainstorms/2026-04-28-objfm-external-modes-brainstorm.md`` for the
planned "pulse" semantic). On the current ``master``, the ObjFM cycles
``occ↔rep`` correctly but the target's ``working`` variable does **not**
flip — so the demo would be misleading. A skeleton scenario is provided
at the bottom of this file (commented out) and will be activated once the
pulse model is implemented.

Expected timeline
-----------------

The cod3s-isimu fireable panel always shows transitions whose ``end_time``
is the **next** event. When several transitions share that ``end_time``,
they appear together with the ★ "fires together" marker.

The two scenarios run in parallel — at any moment, the smallest of the
four ``end_time`` candidates (C1.occ, C1.rep, C2.occ, C2.rep) is what the
TUI offers next. The complete cycle for each component is laid out below.

**Scenario 1 — internal (C1)**

The internal cycle is the simplest: each transition fires alone, the
effect is applied directly by the ObjFM (no target automaton).

::

    fireable:  C1__fm_int.occ   end_time = 10
    [Enter] →  step at t=10:    C1__fm_int.occ            → C1.working: True → False

    fireable:  C1__fm_int.rep   end_time = 15  (=10+ttr)
    [Enter] →  step at t=15:    C1__fm_int.rep            → C1.working: False → True

    fireable:  C1__fm_int.occ   end_time = 25  (=15+ttf)
    … cycles every 15 time units (ttf+ttr).

**Scenario 2 — external (C2)**

The external cycle puts an automaton ``fm_ext`` *inside* C2 with
delay(0) transitions guarded by ``ctrl_fm_ext_C2``. Each "event"
materialises as **two consecutive steps at the same simulator time**:
first the ObjFM transition (which flips the ctrl_var), then the
target's delay(0) transition (which applies the failure/repair effect).
Because both have the same ``end_time``, cod3s-isimu marks them with
the ★ "fires together" indicator before the first is fired.

::

    fireable:  C2__fm_ext.occ            end_time = 20
               (this is the ObjFM cc_1.occ — first half of the chain)
    [Enter] →  step at t=20:  C2__fm_ext.occ              → ctrl_fm_ext_C2: False → True
                                                          → C2.working unchanged (effects live
                                                            on the target automaton, not on
                                                            the ObjFM)
    fireable:  C2.occ                    end_time = 20
               (target's delay(0) transition, now enabled by ctrl_var=True)
    [Enter] →  step at t=20:  C2.occ                      → C2.working: True → False

    fireable:  C2__fm_ext.rep            end_time = 28  (=20+ttr)
    [Enter] →  step at t=28:  C2__fm_ext.rep              → ctrl_fm_ext_C2: True → False
                                                          → C2.working unchanged
    fireable:  C2.rep                    end_time = 28
    [Enter] →  step at t=28:  C2.rep                      → C2.working: False → True

    fireable:  C2__fm_ext.occ            end_time = 48  (=28+ttf)
    … cycles every 28 time units (ttf+ttr).

**Interleaving of the two scenarios**

Because both run in parallel, here is the actual sequence
``cod3s-isimu`` will guide you through (each ``[Enter]`` represents one
``stepForward``):

==========  ===============================  ==================================
Step #      Step time + fired transition     State after the step
==========  ===============================  ==================================
1           t=10  C1__fm_int.occ             C1=False, C2=True
2           t=15  C1__fm_int.rep             C1=True, C2=True
3           t=20  C2__fm_ext.occ             C1=True, C2=True (ctrl_C2=True)
4           t=20  C2.occ                     C1=True, C2=False
5           t=25  C1__fm_int.occ             C1=False, C2=False
6           t=28  C2__fm_ext.rep             C1=False, C2=False (ctrl_C2=False)
7           t=28  C2.rep                     C1=False, C2=True
8           t=30  C1__fm_int.rep             C1=True, C2=True
…           (cycles continue independently)
==========  ===============================  ==================================

Things to try in cod3s-isimu
----------------------------

- **Variable coloring** (Components panel) — after step 1, ``C1.working``
  is rendered in **bold red** because it just changed at the last step.
  Then at step 2 it changes again (red). At step 3 nothing changed in C1
  but it's still ``True`` like its initial value, so it goes back to
  the dim "matches initial" style. Variables that were touched but
  reverted (e.g. C2 between steps 4 and 7) end the rep half of their
  cycle in dim style.
- **★ "fires together" highlight** — in the external scenario, when the
  cursor sits on ``C2__fm_ext.occ`` at t=20, the row ``C2.occ`` (also
  end_time=20) lights up ★. Same for the rep half at t=28.
- **Step backward** — press ``b`` after the external chain to roll back
  ``C2.working`` *and* ``ctrl_fm_ext_C2`` together — the engine recovers
  the state both on the ObjFM and on the target automaton.
- **Re-plan** — press ``p`` on a fireable row, type a new date, and
  watch the ``end_time`` of that single transition jump while the rest
  of the schedule stays put. Useful to demonstrate that the external
  ObjFM/target lock is enforced by the *automaton condition*, not by
  the planning itself.
- **Export** — at any point press ``e`` to dump the timeline to CSV and
  JSON; the CSV's ``fired_at`` column is the actual firing time
  captured by the engine (NOT ``PycTransition.end_time``, which is the
  planned end-time and is mutated during ``isimu_fireable_transitions``
  — see ``cod3s/pycatshoo/system.py:931``).
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s


class SimpleEquipment(cod3s.PycComponent):
    """Component with a single boolean ``working`` variable.

    Kept intentionally minimal: no message boxes, no PDMP, no continuous
    variables. The only mutable state is ``working``.

    ``working`` is **reinitialised** (``setReinitialized(True)``): when no
    sensitive method actively forces it to ``False`` (i.e. no ObjFM
    automaton is in its failure state), PyCATSHOO restores it to its
    declared initial value (``True``). This is the convention used in
    every ObjFM demo: ObjFMs only set ``failure_effects={"working": False}``
    and leave ``repair_effects`` empty — the variable returns to ``True``
    automatically when the failure state is left, and there is no
    ``repair_effect`` sensitive method that could fight a concurrent
    failure on a multi-target ObjFM.
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


def build_system() -> cod3s.PycSystem:
    """Build the ObjFM showcase system.

    Returns a populated ``PycSystem`` ready to be passed to
    ``cod3s.pycatshoo.isimu.app.run_isimu`` (this is the entry-point used
    by ``cod3s-isimu --factory``).
    """
    system = cod3s.PycSystem(name="ObjFMDemo")

    # ------------------------------------------------------------------
    # Scenario 1 — internal behaviour
    # ------------------------------------------------------------------
    # ttf = 10, ttr = 5. The ObjFM owns the failure automaton; failure_effects
    # and repair_effects are applied directly to ``C1.working``.
    system.add_component(name="C1", cls="SimpleEquipment")
    system.add_component(
        cls="ObjFMDelay",
        fm_name="fm_int",
        targets=["C1"],
        behaviour="internal",
        failure_effects={"working": False},
        # No repair_effects: ``working`` is reinitialised, so it returns
        # to True automatically when the ObjFM leaves its occ state.
        failure_param=10,
        repair_param=5,
    )

    # ------------------------------------------------------------------
    # Scenario 2 — external behaviour
    # ------------------------------------------------------------------
    # ttf = 20, ttr = 8. The target C2 receives an automaton ``fm_ext``
    # with delay(0) transitions guarded by ``ctrl_fm_ext_C2``. The ObjFM
    # and the target are mutually locked: the ObjFM cannot leave ``occ``
    # until the target is also in ``occ``, and vice versa for ``rep``.
    system.add_component(name="C2", cls="SimpleEquipment")
    system.add_component(
        cls="ObjFMDelay",
        fm_name="fm_ext",
        targets=["C2"],
        behaviour="external",
        failure_effects={"working": False},
        # No repair_effects (reinitialised pattern, see C1 above).
        failure_param=20,
        repair_param=8,
    )

    # ------------------------------------------------------------------
    # Scenario 3 — external_rep_indep — DISABLED (work in progress)
    # ------------------------------------------------------------------
    # Uncomment when the "pulse" semantic from
    # ``docs/brainstorms/2026-04-28-objfm-external-modes-brainstorm.md`` lands
    # (delay(0) no-condition on the ObjFM's ``occ→rep`` transition; target
    # repair on the order-1 law). On master today, the ObjFM cycles
    # correctly but its rep transition uses the order-2 ``ttr`` and
    # the sensitive method on ``ctrl_var`` snaps it back to False
    # *before* the target's delay(0) ``occ`` chain has a chance to apply
    # the failure_effects — so ``C3.working`` and ``C4.working`` never
    # actually flip. Demo would be misleading; we leave it out.
    #
    # system.add_component(name="C3", cls="SimpleEquipment")
    # system.add_component(name="C4", cls="SimpleEquipment")
    # system.add_component(
    #     cls="ObjFMDelay",
    #     fm_name="fm_pulse",
    #     targets=["C3", "C4"],
    #     behaviour="external_rep_indep",
    #     failure_effects={"working": False},
    #     # No repair_effects (reinitialised pattern).
    #     # Order 1 (cc_1, cc_2 individually) parked at +inf — only the
    #     # common cause (cc_12, order 2) ever fires in the demo window.
    #     failure_param=[(1000,), (15,)],
    #     # Once the pulse model is implemented, repair_param[0] (=3) is
    #     # what each target uses for its independent repair clock.
    #     repair_param=[(3,), (6,)],
    # )

    return system


if __name__ == "__main__":
    # Convenience: ``python examples/objfm_demo/objfm_demo.py`` opens the TUI.
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
