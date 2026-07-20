"""ObjDegMode demo — graded degradation of two rails with common cause.

Two rails share a crack degradation mode ``Fissure`` with three graded
states ``O -> X1 -> X2`` (X2 absorbing except repair):

* leaving the healthy state is driven by the CC entry (``lambda_k``
  vector: independent order-1 occurrences AND an order-2 common cause
  moving both rails to ``O`` at the same instant);
* deeper progressions and repairs are strictly individual;
* every repair jumps straight back to the healthy state (full renewal);
* each rail exposes ``Fissure_level`` (0..3) for indicators.

Conventions: the observed variable is declared ``setReinitialized(True)``
and the healthy state carries no effects (state effects only on degraded
states).

Launch
------

::

    uv run python examples/objdegmode_demo/objdegmode_demo.py

Or drive it interactively::

    PYTHONPATH="examples/objdegmode_demo:$PYTHONPATH" \\
        uv run cod3s-isimu --factory objdegmode_demo:build_system

Expected sequence events (grammar)
----------------------------------

* ``RX__Fissure.occ_O__cc_1`` / ``__cc_2`` / ``__cc_1_2`` — carrier CC
  fires (order = number of ``_``-separated indices);
* ``R1.Fissure__occ_O`` ... ``R1.Fissure__occ_X2`` — per-rail trajectory;
* ``R1.Fissure__rep_X1`` — repair (departure state in the name).
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s
from cod3s import DegState, ObjDegMode
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem


class Rail(cod3s.PycComponent):
    """A rail with a boolean service flag clamped by the degradation."""

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.in_service = self.addVariable("in_service", Pyc.TVarType.t_bool, True)
        self.in_service.setReinitialized(True)


def build_system() -> PycSystem:
    system = PycSystem(name="ObjDegModeDemo")
    Rail("R1")
    Rail("R2")

    ObjDegMode(
        fm_name="Fissure",
        targets=["R1", "R2"],
        states=[
            DegState(
                "O",
                # lambda_k vector: order 1 (each rail alone) and order 2
                # (both rails together, same instant).
                occ_law={"cls": "exp", "rate": [0.15, 0.05]},
                rep_law={"cls": "exp", "rate": 0.4},
            ),
            DegState(
                "X1",
                occ_law={"cls": "exp", "rate": 0.08},
                effects={"in_service": False},
                rep_law={"cls": "exp", "rate": 0.2},
            ),
            DegState(
                "X2",
                # Deterministic ageing to the broken state.
                occ_law={"cls": "delay", "time": 20.0},
                effects={"in_service": False},
                rep_law={"cls": "delay", "time": 10.0},
            ),
        ],
    )
    return system


def main() -> None:
    system = build_system()
    for rail in ("R1", "R2"):
        system.add_indicator_var(
            component=rail,
            var="Fissure_level",
            stats=["mean"],
            name=f"lv_{rail}",
        )
    system.simulate(PycMCSimulationParam(nb_runs=5000, schedule=[10.0, 50.0], seed=1))
    for rail in ("R1", "R2"):
        vals = system.indicators[f"lv_{rail}_Fissure_level"].values["values"]
        print(f"{rail}: mean level @10={vals.iloc[0]:.3f} @50={vals.iloc[-1]:.3f}")
    cod3s.terminate_session()


if __name__ == "__main__":
    main()
