"""The ``min`` and ``max`` statistics of a PyCATSHOO indicator.

They are the smallest and the largest value the measure took across the
replicas at each instant. PyCATSHOO has no restitution of its own for them,
so they are read off its ``all_values`` restitution, which returns every
replica's measure at an instant. Until then asking for either raised
(``Stat min not supported for Pycatshoo indicator restitution``), and a
platform study asking for them failed on the reference engine.
"""

import Pycatshoo as Pyc

import cod3s
from cod3s import DegState, ObjDegMode
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem

DATES = [0.0, 2.0, 10.0]
NB_RUNS = 400


class Rail(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.failed = self.addVariable("failed", Pyc.TVarType.t_bool, False)
        self.failed.setReinitialized(True)


def _stats(stats):
    cod3s.terminate_session()
    system = PycSystem(name="IndicatorExtremes")
    Rail("R1")
    ObjDegMode(
        fm_name="frun",
        targets=["R1"],
        states=[
            DegState(
                "occ",
                occ_law={"cls": "exp", "rate": 0.25},
                effects={"failed": True},
                rep_law={"cls": "exp", "rate": 0.5},
            )
        ],
    )
    system.add_indicator_var(component="R1", var="failed", stats=stats, name="f")
    system.simulate(PycMCSimulationParam(nb_runs=NB_RUNS, schedule=DATES, seed=20260925))
    values = system.indicators["f_failed"].values
    return {stat: [float(v) for v in values[values["stat"] == stat]["values"]] for stat in stats}


def test_the_extremes_bound_the_mean_at_every_instant():
    stats = _stats(["mean", "min", "max"])
    for low, mean, high in zip(stats["min"], stats["mean"], stats["max"]):
        assert low <= mean <= high
    # Nothing has failed at t = 0; by t = 2 some replicas have and some not.
    assert (stats["min"][0], stats["max"][0]) == (0.0, 0.0)
    assert (stats["min"][1], stats["max"][1]) == (0.0, 1.0)


def test_asking_for_the_extremes_leaves_the_mean_unchanged():
    # The extra restitution reads the same replicas: the mean is the same
    # number whether or not the extremes are asked for.
    assert _stats(["mean", "min", "max"])["mean"] == _stats(["mean"])["mean"]
