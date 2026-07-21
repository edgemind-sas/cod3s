"""Generic two-state mode (``ObjMode2S``) demo — per-demand recovery.

The showcase of the mixed-law matrix: a machine whose failure is
deterministic (``occ_law = delay(6)``) and whose repair is a
**per-demand draw** (``not_occ_law = inst(prob=0.7)``): every visit of
the maintenance crew is ONE repair attempt that succeeds with
probability 0.7 — a failed attempt leaves the machine failed (parked in
``occ_star``) until the crew leaves and a NEW visit re-arms the next
attempt. The crew visits cycle deterministically (away 4 h / on site
1 h).

This is scenario D of the ObjMode2S brainstorm (unified inst
semantics): one draw per rising edge of the composite guard
"failed AND crew on site".

How to run
----------

With ``uv``::

    PYTHONPATH="examples/objmode2s_demo:$PYTHONPATH" \\
        uv run cod3s-isimu --factory objmode2s_demo:build_system

Or directly::

    PYTHONPATH="examples/objmode2s_demo:$PYTHONPATH" \\
        uv run python examples/objmode2s_demo/objmode2s_demo.py

What you should see
-------------------

#. At t=0 the machine works; the failure (``occ``, delay 6) and the
   first crew arrival (``on_site``, delay 4) are planned. Press
   **Enter** twice: the crew comes (t=4) and leaves (t=5) without
   anything to repair — no draw is armed (the machine is up).
#. At t=6 the machine fails: ``E1__fix.occ`` fires, ``working`` goes
   False (level clamp).
#. At t=9 the crew arrives while the machine is failed: the rising
   edge of the composite guard arms the repair draw — the fireable
   panel switches to *inst pending* with the two branches::

       not_occ  [not_occ (p=0.70), occ_star (p=0.30)]

   Pick the ``occ_star`` branch (failed attempt): the machine STAYS
   failed (``working`` False — the occ clamp covers the parked state)
   and nothing but the crew departure is fireable while the crew stays
   (anti-Zeno: no re-draw within the same visit).
#. At t=10 the crew leaves; the next step fires the deterministic
   ``inst p=1`` re-arm (``occ_star``, masked from recorded sequences)
   and the mode waits, armed, still failed.
#. At t=14 the next visit arms a NEW draw — pick the ``not_occ``
   branch this time: the machine is repaired (``working`` True). One
   visit = one attempt.
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s


class Machine(cod3s.PycComponent):
    """Machine with a ``working`` marker (clamped by the mode)."""

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


class Crew(cod3s.PycComponent):
    """Maintenance crew cycling away (4 h) / on site (1 h)."""

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.on_site = self.addVariable("on_site", Pyc.TVarType.t_bool, False)
        self.on_site.setReinitialized(True)
        self.add_aut2st(
            name="visits",
            st1="away",
            st2="present",
            init_st2=False,
            trans_name_12_fmt="on_site",
            occ_law_12={"cls": "delay", "time": 4},
            trans_name_21_fmt="departure",
            occ_law_21={"cls": "delay", "time": 1},
            effects_st2={"on_site": True},
        )


def build_system() -> cod3s.PycSystem:
    """Build the machine + crew per-demand-recovery showcase."""
    system = cod3s.PycSystem(name="ObjMode2SDemo")
    system.add_component(name="E1", cls="Machine")
    crew = system.add_component(name="crew", cls="Crew")
    cod3s.ObjMode2S(
        mode_name="fix",
        targets=["E1"],
        # Failure: deterministic wear-out after 6 h of operation.
        occ_law={"cls": "delay", "time": 6},
        # Repair: ONE Bernoulli attempt per crew visit (per-demand
        # recovery — the return-direction inst law).
        not_occ_law={"cls": "inst", "prob": 0.7},
        not_occ_cond=lambda: crew.on_site.value() is True,
        occ_effects={"working": False},
    )
    return system


if __name__ == "__main__":
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
