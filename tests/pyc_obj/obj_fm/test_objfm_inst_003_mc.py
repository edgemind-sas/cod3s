"""ObjFMInst Monte-Carlo — gamma convergence and termination.

Termination doubles as the MC-side anti-Zeno proof: with the demand
held true from t0 in every run, a Zeno regression (the 1 - gamma branch
re-firing at the same instant) would hang ``simulate`` instead of
letting the run reach t_max.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem


class InstEquipment003(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.failed = self.addVariable("failed", Pyc.TVarType.t_bool, False)
        self.failed.setReinitialized(True)


def test_mc_convergence_to_gamma():
    system = PycSystem(name="SysInst003")
    system.add_component(name="E1", cls="InstEquipment003")
    system.add_component(
        cls="ObjFMInst",
        fm_name="miss",
        targets=["E1"],
        failure_cond=True,  # demand from t0, every run
        failure_effects={"failed": True},
        failure_param=0.3,
        repair_param=0,  # never repaired: one draw decides the run
    )
    system.add_indicator_var(component="E1", var="failed", stats=["mean"], name="ind")

    system.simulate(PycMCSimulationParam(nb_runs=4000, schedule=[1.0], seed=1234))

    ind = system.indicators["ind_failed"]
    mean_failed = ind.values["values"].iloc[-1]
    # 4000 Bernoulli(0.3) draws: 3-sigma half-width ~ 0.022.
    assert mean_failed == pytest.approx(0.3, abs=0.03)
