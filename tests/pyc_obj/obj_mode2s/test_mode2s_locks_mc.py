"""ObjMode2S statistical locks (slow, seeded) for the new law combos.

Three locks, two of them NON-CIRCULAR (closed forms, not
cod3s-vs-cod3s):

* exp/delay alternating renewal — asymptotic availability
  ``(1/lambda) / (1/lambda + ttr)``;
* inst on the return direction with a held condition — absorption:
  each failure is instantly repaired with probability gamma or parks
  forever, so the process is a thinned Poisson absorption and
  ``P(up at T) = exp(-lambda * (1 - gamma) * T)``;
* inst/inst same-instant ping-pong — almost-sure termination (anti-hang
  guard) plus the closed-form split of the absorbing parked states:
  ``P(parked on the occ side) = g_occ * (1 - g_ret) / (1 - g_occ*g_ret)``.
"""

import time

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import ObjMode2S
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem


class Equipment(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


def fresh_system(name):
    cod3s.terminate_session()
    return PycSystem(name=name)


def _mean_working_at_end(system, nb_runs, t_end, seed):
    system.add_indicator_var(component="E1", var="working", stats=["mean"], name="up")
    t0 = time.monotonic()
    system.simulate(
        PycMCSimulationParam(nb_runs=nb_runs, schedule=[0.0, t_end], seed=seed)
    )
    assert time.monotonic() - t0 < 30.0  # anti-hang guard
    return float(system.indicators["up_working"].values["values"].iloc[-1])


@pytest.mark.slow
class TestExpDelayRenewalAnalytical:
    def test_asymptotic_availability_matches_closed_form(self):
        """exp(lambda) failures / delay(ttr) repairs form an alternating
        renewal process: A_inf = (1/lambda) / (1/lambda + ttr)."""
        lam, ttr = 0.5, 1.0
        expected = (1 / lam) / (1 / lam + ttr)  # 2/3

        system = fresh_system("LockExpDelay")
        Equipment("E1")
        ObjMode2S(
            mode_name="wear",
            targets=["E1"],
            occ_law={"cls": "exp", "rate": lam},
            not_occ_law={"cls": "delay", "time": ttr},
            occ_effects={"working": False},
        )
        # t=80 >> relaxation (mean cycle 3.0): deep in stationarity.
        # 3-sigma of a Bernoulli mean over 4000 runs ~ 0.024.
        mc = _mean_working_at_end(system, nb_runs=4000, t_end=80.0, seed=20260721)
        assert mc == pytest.approx(expected, abs=0.03)


@pytest.mark.slow
class TestInstReturnAbsorptionAnalytical:
    def test_thinned_poisson_absorption_matches_closed_form(self):
        """Return-direction inst with a held condition: at every failure
        the repair draw fires immediately — success (prob gamma)
        restores the mode instantly, failure parks it forever (the
        condition never falls, no re-arm). Up-time is therefore killed
        by a thinned Poisson process:
        ``P(working at T) = exp(-lambda * (1-gamma) * T)``."""
        lam, gamma, t_end = 0.4, 0.75, 5.0
        expected = pytest.approx(2.718281828 ** (-lam * (1 - gamma) * t_end), abs=0.03)

        system = fresh_system("LockInstReturn")
        Equipment("E1")
        ObjMode2S(
            mode_name="fix",
            targets=["E1"],
            occ_law={"cls": "exp", "rate": lam},
            not_occ_law={"cls": "inst", "prob": gamma},
            occ_effects={"working": False},
        )
        mc = _mean_working_at_end(system, nb_runs=4000, t_end=t_end, seed=20260722)
        assert mc == expected


@pytest.mark.slow
class TestInstInstTermination:
    def test_ping_pong_terminates_and_splits_analytically(self):
        """inst/inst with trivially-true conditions and probs < 1: the
        same-instant ping-pong chain has geometric length (continues
        with prob g_occ * g_ret per cycle) and terminates almost surely
        in one of the two absorbing parked states at t=0.

        P(absorbed on the occ side, i.e. working=False) =
        g_occ*(1-g_ret) * sum_k (g_occ*g_ret)^k =
        g_occ*(1-g_ret) / (1 - g_occ*g_ret).

        A Zeno regression (re-arm re-drawing instead of parking) would
        show up as a hang, caught by the wall-clock guard.
        """
        g_occ = g_ret = 0.5
        p_stuck_occ = g_occ * (1 - g_ret) / (1 - g_occ * g_ret)  # 1/3

        system = fresh_system("LockInstInst")
        Equipment("E1")
        ObjMode2S(
            mode_name="flip",
            targets=["E1"],
            occ_law={"cls": "inst", "prob": g_occ},
            not_occ_law={"cls": "inst", "prob": g_ret},
            occ_effects={"working": False},
        )
        mc_up = _mean_working_at_end(system, nb_runs=4000, t_end=1.0, seed=20260723)
        assert mc_up == pytest.approx(1 - p_stuck_occ, abs=0.03)
