"""Multi-target ObjFM showcase with **exponential** failure / repair laws.

Three independent equipments — pump1, pump2, valve — each carry their own
``ObjFMExp`` failure mode (``behaviour="internal"``) with different rates.
Failures and repairs are sampled live by the ``cod3s-isimu`` engine
(``ISimuEngine._autoplan_nondeterministic`` since version 0.2.0), so every
``stepForward`` advances the simulator clock by an exp-distributed delay
without you having to plan transitions manually.

How to run
----------

::

    PYTHONPATH="examples/objfm_exp_demo:$PYTHONPATH" \\
        uv run cod3s-isimu --factory objfm_exp_demo:build_system

Pass ``--rng-seed N`` to make the run reproducible::

    PYTHONPATH="examples/objfm_exp_demo:$PYTHONPATH" \\
        uv run cod3s-isimu --factory objfm_exp_demo:build_system --rng-seed 42

Pinning a seed is useful when a particular interleaving of events surfaces
a bug — share the seed in the report and anyone re-running with that
``--rng-seed`` will see the same trace.

Layout of the system
--------------------

Three equipments live in the same ``PycSystem`` and never interact. Each
gets its **own** ObjFMExp (``behaviour="internal"``) with independent
failure (λ) and repair (μ) rates. There is **no** common-cause failure in
this demo — that would require ``external_rep_indep``, which is still
work-in-progress on master (see the ObjFM brainstorm).

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

Independence claim
------------------

* Each ObjFM owns one failure automaton on a single target → no coupling
  between the three components.
* The engine samples each non-deterministic transition with a private
  ``random.Random(rng_seed)``, so the three components see uncorrelated
  exp draws.
* Pressing ``b`` (step backward) reverts only the **last** event,
  affecting **only** the component that just transitioned. The others
  stay where they are.
* Pressing ``r`` (reset) re-seeds the RNG and replays from t=0; with the
  same ``--rng-seed`` you get the same trace.

What you should observe in cod3s-isimu
--------------------------------------

* The **fireable panel** lists the *next* event only (smallest sampled
  ``end_time``) — typically just one row at a time. Different runs (no
  seed) give different orderings.
* The **★ "fires together"** marker rarely lights up here: with
  continuous exp distributions, two transitions sharing the *exact* same
  end-time is a probability-zero event. Run with ``--rng-seed`` and a
  carefully chosen seed if you want to deliberately reproduce a
  near-collision.
* The **components panel** colors variables in:

  - dim grey — value matches its declared initial (``True``).
  - **bold red** — value just changed (``True → False`` at the failure
    step, then ``False → True`` at the repair step).
  - orange (``differs from initial``) — value differs from initial but
    didn't change at the last step. With this exp model, the orange
    state corresponds exactly to "currently failed" (and not just
    repaired).

* The **history panel** grows as you press ``Enter``; floating-point
  ``fired_at`` values reflect the actual exp draws.

A reference run with ``--rng-seed 42`` produces (rounded)::

    step1: t=0.51   pump2.fail        | pump1=T pump2=F valve=T
    step2: t=1.35   pump2.repair      | pump1=T pump2=T valve=T
    step3: t=10.20  pump1.fail        | pump1=F pump2=T valve=T
    step4: t=12.46  pump1.repair      | pump1=T pump2=T valve=T
    step5: t=16.08  valve.fail        | pump1=T pump2=T valve=F
    step6: t=16.99  valve.repair      | pump1=T pump2=T valve=T
    step7: t=28.02  pump2.fail        | pump1=T pump2=F valve=T
    step8: t=28.12  pump2.repair      | pump1=T pump2=T valve=T

Use this trace as a sanity check after touching the engine: the same
seed must reproduce these timings to within float precision.

Things to try
-------------

- **Different seeds**: ``--rng-seed 7``, ``--rng-seed 99``, … each gives
  a different ordering of the three components' cycles.
- **Re-plan**: pin a transition to a specific date with the ``p``
  modal. The engine's auto-sampling does **not** override an
  already-planned date, so ``p`` lets you "force" an early failure.
- **Step backward**: press ``b`` repeatedly to walk back through the
  history; the engine pops the matching ``FiredEvent`` and reschedules
  the now-active transition with a fresh sample (so the next
  ``stepForward`` will likely give a different time than before).
- **Export**: press ``e`` to dump the timeline to CSV+JSON for offline
  comparison between seeds.
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s


class Equipment(cod3s.PycComponent):
    """Component with a single boolean ``working`` variable.

    Same shape as ``examples/objfm_demo/SimpleEquipment``, intentionally
    minimal: the demo is about the failure-mode dynamics, not the flow.
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)


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
            repair_effects={"working": True},
            failure_param=lam,
            repair_param=mu,
        )

    return system


if __name__ == "__main__":
    # Convenience: ``python examples/objfm_exp_demo/objfm_exp_demo.py`` opens
    # the TUI with a fresh RNG state. Pass a seed via the CLI for repro.
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
