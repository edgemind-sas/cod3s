"""On-demand failure mode (``ObjFMInst``) demo for ``cod3s-isimu``.

A backup generator must start whenever the grid drops. The grid cycles
deterministically (up for 10 h, down for 2 h). The generator's
``fail_to_start`` mode is an :class:`cod3s.ObjFMInst`: at every demand
front (grid going down) it draws once — failure to start with
probability ``gamma = 0.3``, success otherwise. Repair (a successful
manual restart) follows an exponential law ``mu = 0.5``.

How to run
----------

With ``uv``::

    PYTHONPATH="examples/objfm_inst_demo:$PYTHONPATH" \\
        uv run cod3s-isimu --factory objfm_inst_demo:build_system

Or directly::

    PYTHONPATH="examples/objfm_inst_demo:$PYTHONPATH" \\
        uv run python examples/objfm_inst_demo/objfm_inst_demo.py

What you should see
-------------------

#. At t=0 the grid is up: only the timed ``down`` transition is
   planned. Press **Enter** to advance.
#. At t=10 the grid drops. The demand front arms the draw: the
   fireable panel switches to *inst pending* mode with one entry::

       generator__fail_to_start.occ   (2 branches)
         [ ] → occ       (p=0.300)
         [●] → not_occ   (p=0.700)

   Pick a branch and press **s** to submit.
#. **Success branch** (``not_occ``): the generator starts. The
   automaton parks in ``not_occ`` while the demand holds — press
   **Enter**: no re-draw happens (anti-Zeno: one front, one draw).
   At t=12 the grid comes back; the deterministic re-arm (inst p=1,
   single branch) drains on the next step **without any panel** — the
   ``ISimuEngine`` auto-resolves single-branch inst transitions. The
   next grid drop (t=22) triggers a fresh draw.
#. **Failure branch** (``occ``): ``failed`` goes ``True``. The repair
   transition is exponential (``end_time = inf``): re-plan it via
   **p** to give it a date. On repair, ``failed`` returns to rest
   (reinitialised-variable convention) — and if the grid is still
   down, the mode is re-solicited immediately: a new draw appears
   (repaired-while-demand-holds semantics; use ``mu = 0`` to model
   "one failed start per demand, no retry").

Sequence trace note: only the ``occ`` branch of the draw is recorded
in Monte-Carlo sequence monitoring; the success branch and the re-arm
transition are masked out (``setMonitoredOutStateMask``), so traces
stay comparable with ``ObjFMExp`` ones (``occ``/``rep`` events only).
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s


class Grid(cod3s.PycComponent):
    """Power grid cycling up (10 h) / down (2 h) deterministically."""

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.grid_up = self.addVariable("grid_up", Pyc.TVarType.t_bool, True)
        self.grid_up.setReinitialized(True)
        self.add_aut2st(
            name="cycle",
            st1="up",
            st2="down",
            init_st2=False,
            trans_name_12_fmt="down",
            occ_law_12={"cls": "delay", "time": 10},
            trans_name_21_fmt="up",
            occ_law_21={"cls": "delay", "time": 2},
            effects_st2={"grid_up": False},
        )


class Generator(cod3s.PycComponent):
    """Backup generator; ``failed`` records a failure to start."""

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.failed = self.addVariable("failed", Pyc.TVarType.t_bool, False)
        self.failed.setReinitialized(True)


def build_system() -> cod3s.PycSystem:
    """Build the grid + generator on-demand-failure showcase."""
    system = cod3s.PycSystem(name="ObjFMInstDemo")
    grid = system.add_component(name="grid", cls="Grid")
    system.add_component(name="generator", cls="Generator")
    system.add_component(
        cls="ObjFMInst",
        fm_name="fail_to_start",
        targets=["generator"],
        # The demand: the grid being down solicits the generator.
        failure_cond=lambda: grid.grid_up.value() is False,
        failure_effects={"failed": True},
        failure_param=0.3,  # gamma: P(fail to start) per demand
        repair_param=0.5,  # mu: exponential restart-repair rate
    )
    return system


if __name__ == "__main__":
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(build_system())
