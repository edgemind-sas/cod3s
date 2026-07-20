"""ObjDegMode statistical locks (slow, seeded).

Two independent verifications of the law wiring:

* K=1 equivalence: a single-degraded-state ObjDegMode with CC (N=2)
  must be statistically indistinguishable from an ObjFMExp in
  ``external_rep_indep`` behaviour with the same lambda_k / mu — this
  locks the CC combinatorics and the trigger machinery against the
  historical reference implementation.
* Analytical Markov: K=2 on a single target is a 3-state
  continuous-time Markov chain with constant rates; the asymptotic
  expected level has a closed form — the only non-circular lock of the
  law wiring (it does not compare cod3s to cod3s).
"""

import time

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import DegState, ObjDegMode
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem


class Rail(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.failed = self.addVariable("failed", Pyc.TVarType.t_bool, False)
        self.failed.setReinitialized(True)


def fresh_system(name):
    cod3s.terminate_session()
    return PycSystem(name=name)


LAMBDA_1, LAMBDA_2, MU = 0.25, 0.12, 0.5
DATES = [0.0, 2.0, 5.0, 10.0]
NB_RUNS = 5000


def _sticky_failed_means(system):
    system.add_indicator_var(component="R1", var="failed", stats=["mean"], name="f1")
    system.add_indicator_var(component="R2", var="failed", stats=["mean"], name="f2")
    t0 = time.monotonic()
    system.simulate(
        PycMCSimulationParam(nb_runs=NB_RUNS, schedule=DATES, seed=20260720)
    )
    assert time.monotonic() - t0 < 30.0  # anti-hang guard
    out = []
    for name in ("f1_failed", "f2_failed"):
        out.append([float(v) for v in system.indicators[name].values["values"]])
    return out


@pytest.mark.slow
class TestK1EquivalenceWithObjFM:
    def test_sticky_failure_marker_matches_objfm(self):
        """Both primitives clamp ``failed`` while degraded and never
        clear it (sticky marker): the mean trajectory is P(ever entered
        degradation before t)-ish and must match run-for-run tolerance.
        """
        # --- ObjDegMode K=1, N=2, CC orders 1 and 2 ---
        system = fresh_system("DegEquivMcA")
        Rail("R1"), Rail("R2")
        ObjDegMode(
            fm_name="frun",
            targets=["R1", "R2"],
            states=[
                DegState(
                    "occ",
                    occ_law={"cls": "exp", "rate": [LAMBDA_1, LAMBDA_2]},
                    effects={"failed": True},
                    rep_law={"cls": "exp", "rate": MU},
                )
            ],
        )
        deg_means = _sticky_failed_means(system)

        # --- ObjFMExp external_rep_indep, same parameters ---
        system = fresh_system("DegEquivMcB")
        Rail("R1"), Rail("R2")
        system.add_component(
            cls="ObjFMExp",
            fm_name="frun",
            targets=["R1", "R2"],
            failure_effects={"failed": True},
            failure_param=[LAMBDA_1, LAMBDA_2],
            repair_param=[MU, MU],
            behaviour="external_rep_indep",
        )
        fm_means = _sticky_failed_means(system)

        # 3-sigma half-width for a Bernoulli mean over NB_RUNS runs is at
        # most 3*0.5/sqrt(5000) ~ 0.021 per estimate; the two estimates
        # are independent => tolerance 0.03 on the difference.
        for deg_series, fm_series in zip(deg_means, fm_means):
            assert deg_series[0] == fm_series[0] == 0.0  # no leak at t=0
            for d, f in zip(deg_series[1:], fm_series[1:]):
                assert d == pytest.approx(f, abs=0.03)


@pytest.mark.slow
class TestAnalyticalMarkov:
    def test_asymptotic_expected_level_matches_closed_form(self):
        """K=2, N=1: chain 0 -> 1 -> 2 with repairs 1->0 and 2->0.

        Stationary balance (pi Q = 0):
            pi1 = pi0 * l1 / (l2 + m1)
            pi2 = pi0 * l1 * l2 / (m2 * (l2 + m1))
        E[level]_inf = pi1 + 2 pi2.
        """
        l1, l2, m1, m2 = 0.4, 0.3, 0.6, 0.5
        pi1_over_pi0 = l1 / (l2 + m1)
        pi2_over_pi0 = l1 * l2 / (m2 * (l2 + m1))
        pi0 = 1.0 / (1.0 + pi1_over_pi0 + pi2_over_pi0)
        expected_level = pi0 * (pi1_over_pi0 + 2 * pi2_over_pi0)

        system = fresh_system("DegMarkov")
        Rail("R1")
        ObjDegMode(
            fm_name="deg",
            targets=["R1"],
            states=[
                DegState(
                    "d1",
                    occ_law={"cls": "exp", "rate": l1},
                    rep_law={"cls": "exp", "rate": m1},
                ),
                DegState(
                    "d2",
                    occ_law={"cls": "exp", "rate": l2},
                    rep_law={"cls": "exp", "rate": m2},
                ),
            ],
        )
        system.add_indicator_var(
            component="R1", var="deg_level", stats=["mean"], name="lv"
        )
        # t=60 with rates ~0.3-0.6: relaxation time ~ a few units, the
        # chain is deep in stationarity.
        t0 = time.monotonic()
        system.simulate(PycMCSimulationParam(nb_runs=6000, schedule=[60.0], seed=987))
        assert time.monotonic() - t0 < 30.0

        mc_level = float(system.indicators["lv_deg_level"].values["values"].iloc[-1])
        # Level in {0,1,2}: Var <= E[X^2] <= 4 => sigma_mean <= 2/sqrt(6000)
        # ~ 0.026; 3-sigma ~ 0.08. Use 0.05: tighter than 3-sigma of the
        # worst case, looser than the actual variance at these rates.
        assert mc_level == pytest.approx(expected_level, abs=0.05)
