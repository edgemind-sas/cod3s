"""Multi-component panne-types demo for ``cod3s-isimu``.

Two pumps, ``pump1`` and ``pump2``, each operating independently. Whenever
a pump enters its ``operating`` state, an inst transition decides on the
spot whether the next operation succeeds, suffers a light failure, or a
severe failure — each outcome carries its own per-branch effects on the
component's ``severity`` integer.

The two pumps are wired identically and start in ``operating`` at t=0, so
both inst transitions are pending at the same instant. This is the
simultaneous-pending UX driver: the user must commit a branch choice for
*every* pending inst before time can advance.

How to run
----------

With ``uv``::

    PYTHONPATH="examples/inst_panne_demo:$PYTHONPATH" \\
        uv run cod3s-isimu --factory inst_panne_demo:build_system

Or directly::

    PYTHONPATH="examples/inst_panne_demo:$PYTHONPATH" \\
        uv run python examples/inst_panne_demo/inst_panne_demo.py

What you should see
-------------------

At t=0 the **fireable transitions** panel switches to *inst pending* mode
with **two** root entries — one per pump::

    pump1.check   (3 branches)
      [ ] → panne_severe   (p=0.050)
      [ ] → panne_legere   (p=0.150)
      [●] → ok             (p=0.800)
    pump2.check   (3 branches)
      [ ] → panne_severe   (p=0.050)
      [ ] → panne_legere   (p=0.150)
      [●] → ok             (p=0.800)

The defaults are the highest-probability branches (``ok``). Navigate with
the arrows, press **Enter** on a different leaf to override, then press
**s** to submit both choices in one atomic call.

Per-branch effects
~~~~~~~~~~~~~~~~~~

Each branch carries its own effects:

* ``panne_severe`` → ``severity = 3``
* ``panne_legere`` → ``severity = 1``
* ``ok``           → ``severity = 0``

After resolution, the **components** panel shows the new ``severity``
value for each pump. The history panel also records which branch fired
for each pump (sequence event = ``comp.aut.transition → target_state``).

The panel then reverts to *timed* mode: a ``delay`` transition will return
each pump to ``operating`` after a state-dependent latency:

* ``panne_severe → operating`` after ``delay(10)``
* ``panne_legere → operating`` after ``delay(5)``
* ``ok            → operating`` after ``delay(1)``

The pump that landed on ``ok`` re-arms first (at t=1), inducing a single
inst pending; ``pump2`` (or whichever was severe) joins later. Try
forcing both to ``ok`` to keep the pumps synchronised, or one to
``panne_severe`` to desynchronise them.

Try it
------

#. ``s``                              → both pumps OK; history records the
                                         ``ok`` branch fired for both.
#. ``Enter`` to advance time → at t=1 both pumps are operating again
   and the inst pending panel reappears.
#. Navigate to ``pump1.panne_severe`` → ``Enter``; then ``s`` →
   ``pump1`` is severe, ``pump2`` is OK. The two pumps are now offset
   in time (pump1 will rejoin operating at t=11, pump2 at t=2).
#. From here on, multi-pending vs. single-pending alternates as the
   pumps drift in and out of synchronisation.

Brainstorm 2026-05-05 (atomic resolution): all pending inst at instant t
must be submitted together — PyCATSHOO drains them in a single
``stepForward``. The ``s`` key gathers the per-transition choices and
calls ``ISimuEngine.resolve_inst({trans_id: state_index})`` once.
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s
from cod3s.pycatshoo.automaton import PycAutomaton


class Pump(cod3s.PycComponent):
    """Pump with a single integer ``severity`` variable.

    ``severity`` records the most recent operation outcome:
    ``0 = ok``, ``1 = panne_legere``, ``3 = panne_severe``.
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.severity = self.addVariable("severity", Pyc.TVarType.t_int, 0)


def _build_pump(system: cod3s.PycSystem, name: str) -> None:
    """Wire one pump's automaton + inst branching + per-branch effects."""
    pump = system.add_component(name=name, cls="Pump")

    aut = PycAutomaton(
        name="aut",
        states=["operating", "panne_severe", "panne_legere", "ok"],
        init_state="operating",
        transitions=[
            # Inst branching at the start of every operation cycle.
            {
                "name": "check",
                "source": "operating",
                "target": [
                    {
                        "state": "panne_severe",
                        "prob": 0.05,
                        "effects": {"severity": 3},
                    },
                    {
                        "state": "panne_legere",
                        "prob": 0.15,
                        "effects": {"severity": 1},
                    },
                    # Complement (0.80); explicit effect resets the severity
                    # so the components panel reflects the operation outcome.
                    {"state": "ok", "effects": {"severity": 0}},
                ],
            },
            # Recovery delays: severity drives how long the pump stays out.
            {
                "name": "rec_severe",
                "source": "panne_severe",
                "target": "operating",
                "occ_law": {"cls": "delay", "time": 10},
            },
            {
                "name": "rec_legere",
                "source": "panne_legere",
                "target": "operating",
                "occ_law": {"cls": "delay", "time": 5},
            },
            {
                "name": "rec_ok",
                "source": "ok",
                "target": "operating",
                "occ_law": {"cls": "delay", "time": 1},
            },
        ],
    )
    aut.update_bkd(pump)
    # Wire per-branch effects (Phase 1 deliverable).
    pump.register_branch_effects(aut, "check", aut.transitions[0].target)


def build_system() -> cod3s.PycSystem:
    """Build the dual-pump panne-types showcase."""
    system = cod3s.PycSystem(name="InstPanneDemo")
    _build_pump(system, "pump1")
    _build_pump(system, "pump2")
    return system


if __name__ == "__main__":
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
