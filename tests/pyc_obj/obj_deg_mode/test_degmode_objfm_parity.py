"""ObjDegMode(K=1) must represent ObjFMExp AND ObjFMDelay exactly.

Parity locks for the ``external_rep_indep`` situation: a two-state
ObjDegMode (healthy + one degraded state) is the degenerate case of the
degradation chain and must be a drop-in equivalent of the historical
two-state primitives —

* ``ObjFMExp``  <->  ``DegState(occ_law=exp(lambda), rep_law=exp(mu))``
* ``ObjFMDelay`` <->  ``DegState(occ_law=delay(ttf), rep_law=delay(ttr))``
  (single target: the delay entry is only legal there — with one
  combination no same-date batch tie can occur)

Each parity is locked twice: a fully deterministic isimu trajectory
(same firing dates, same effect values, cycle after repair included)
and a seeded Monte-Carlo comparison of the clamped failure marker.
A boundary test documents the ONE deliberate non-equivalence: a delay
entry with N >= 2 (multi-target ObjFMDelay CC) has no ObjDegMode
counterpart, by design.
"""

import time

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import DegState, ObjDegMode
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _utils import fire_by_name, fireable_names  # noqa: E402


class Equipment(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.failed = self.addVariable("failed", Pyc.TVarType.t_bool, False)
        self.failed.setReinitialized(True)


def fresh_system(name):
    cod3s.terminate_session()
    return PycSystem(name=name)


def build_degmode_k1(occ_law, rep_law):
    system = fresh_system("ParityDeg")
    eq = Equipment("E1")
    ObjDegMode(
        fm_name="frun",
        targets=["E1"],
        states=[
            DegState(
                "occ",
                occ_law=occ_law,
                effects={"failed": True},
                rep_law=rep_law,
            )
        ],
    )
    return system, eq, "E1__frun.occ_occ", "E1.frun__occ_occ", "E1.frun__rep_occ"


def build_objfm(cls, failure_param, repair_param):
    system = fresh_system("ParityFm")
    eq = Equipment("E1")
    system.add_component(
        cls=cls,
        fm_name="frun",
        targets=["E1"],
        failure_effects={"failed": True},
        failure_param=failure_param,
        repair_param=repair_param,
        behaviour="external_rep_indep",
    )
    return system, eq, "E1__frun.occ", "E1.frun__occ", "E1.frun__rep"


def drive_cycle(system, eq, carrier_occ, target_occ, target_rep, t_occ, t_occ2):
    """Drive occurrence -> repair -> re-occurrence; return the trace.

    ``t_occ`` / ``t_occ2`` are the requested occurrence dates for exp
    laws (isimu lets us choose); pass ``None`` to fire at the law's own
    end date (delay laws). The repair always fires at its end date.
    Returns a list of (simulated time, failed value) checkpoints.
    """
    trace = []
    system.isimu_start()

    # 1) Occurrence: carrier trigger then delay(0) target entry.
    fire_by_name(system, carrier_occ, date=t_occ)
    fire_by_name(system, target_occ)
    trace.append((system.currentTime(), eq.failed.value()))

    # 2) Repair at its end date (fires the target self-repair edge).
    fire_by_name(system, target_rep)
    trace.append((system.currentTime(), eq.failed.value()))

    # 3) The mode is re-armed: a second occurrence must be available.
    fire_by_name(system, carrier_occ, date=t_occ2)
    fire_by_name(system, target_occ)
    trace.append((system.currentTime(), eq.failed.value()))

    # 4) Nothing else than the repair edge remains fireable.
    leftover = [n for n in fireable_names(system) if "rep" not in n]
    system.isimu_stop()
    return trace, leftover


def mc_marker_means(system, dates, nb_runs=4000, seed=777):
    system.add_indicator_var(component="E1", var="failed", stats=["mean"], name="f")
    t0 = time.monotonic()
    system.simulate(PycMCSimulationParam(nb_runs=nb_runs, schedule=dates, seed=seed))
    assert time.monotonic() - t0 < 30.0
    return [float(v) for v in system.indicators["f_failed"].values["values"]]


class TestExpParity:
    """ObjDegMode(K=1, exp/exp) == ObjFMExp external_rep_indep."""

    LAMBDA, MU = 0.3, 0.5

    def test_deterministic_cycle_matches(self):
        system, eq, c, o, r = build_degmode_k1(
            {"cls": "exp", "rate": self.LAMBDA}, {"cls": "exp", "rate": self.MU}
        )
        # Repair is exp: choose its date too for a fully pinned trajectory.
        system.isimu_start()
        fire_by_name(system, c, date=2.0)
        fire_by_name(system, o)
        deg_after_occ = (system.currentTime(), eq.failed.value())
        fire_by_name(system, r, date=9.0)
        deg_after_rep = (system.currentTime(), eq.failed.value())
        fire_by_name(system, c, date=12.0)
        fire_by_name(system, o)
        deg_after_occ2 = (system.currentTime(), eq.failed.value())
        system.isimu_stop()

        system, eq, c, o, r = build_objfm("ObjFMExp", self.LAMBDA, self.MU)
        system.isimu_start()
        fire_by_name(system, c, date=2.0)
        fire_by_name(system, o)
        fm_after_occ = (system.currentTime(), eq.failed.value())
        fire_by_name(system, r, date=9.0)
        fm_after_rep = (system.currentTime(), eq.failed.value())
        fire_by_name(system, c, date=12.0)
        fire_by_name(system, o)
        fm_after_occ2 = (system.currentTime(), eq.failed.value())
        system.isimu_stop()

        assert deg_after_occ == fm_after_occ == (2.0, True)
        # Same release behaviour on both sides (reinitialized variable
        # falls back to init once the clamp's state is left).
        assert deg_after_rep == fm_after_rep
        assert deg_after_occ2 == fm_after_occ2 == (12.0, True)

    @pytest.mark.slow
    def test_mc_failure_marker_matches(self):
        system, *_ = build_degmode_k1(
            {"cls": "exp", "rate": self.LAMBDA}, {"cls": "exp", "rate": self.MU}
        )
        deg = mc_marker_means(system, [0.0, 1.0, 3.0, 8.0])

        system, *_ = build_objfm("ObjFMExp", self.LAMBDA, self.MU)
        fm = mc_marker_means(system, [0.0, 1.0, 3.0, 8.0])

        assert deg[0] == fm[0] == 0.0
        # Independent estimates, 3-sigma Bernoulli half-width per side
        # ~ 3*0.5/sqrt(4000) ~ 0.024 => 0.035 on the difference.
        for d, f in zip(deg[1:], fm[1:]):
            assert d == pytest.approx(f, abs=0.035)


class TestDelayParity:
    """ObjDegMode(K=1, delay/delay) == ObjFMDelay external_rep_indep."""

    TTF, TTR = 10.0, 4.0

    def test_deterministic_cycle_matches(self):
        # Delay laws: every firing date is imposed by the laws themselves,
        # the trajectory is fully deterministic on both sides.
        system, eq, c, o, r = build_degmode_k1(
            {"cls": "delay", "time": self.TTF}, {"cls": "delay", "time": self.TTR}
        )
        deg_trace, deg_leftover = drive_cycle(system, eq, c, o, r, None, None)

        system, eq, c, o, r = build_objfm("ObjFMDelay", self.TTF, self.TTR)
        fm_trace, fm_leftover = drive_cycle(system, eq, c, o, r, None, None)

        # occ at ttf=10, repair at 10+ttr=14, re-occ at 14+ttf=24 (the
        # delay clock restarts after re-arm) — identical on both sides.
        assert deg_trace == fm_trace
        assert [t for t, _ in deg_trace] == [10.0, 14.0, 24.0]
        assert deg_trace[0][1] is True and deg_trace[2][1] is True
        assert deg_leftover == fm_leftover == []

    @pytest.mark.slow
    def test_mc_means_match_exactly(self):
        # Deterministic laws: the MC "means" are step functions with no
        # sampling noise — parity must be exact at every date.
        dates = [0.0, 5.0, 12.0, 20.0, 30.0]
        system, *_ = build_degmode_k1(
            {"cls": "delay", "time": self.TTF}, {"cls": "delay", "time": self.TTR}
        )
        deg = mc_marker_means(system, dates, nb_runs=200)

        system, *_ = build_objfm("ObjFMDelay", self.TTF, self.TTR)
        fm = mc_marker_means(system, dates, nb_runs=200)

        assert deg == fm
        # And the step function is the expected one. The clamped variable
        # FOLLOWS the degraded state (a setReinitialized(True) variable
        # falls back to its init value once the clamp's state is left):
        # cycle occ@10 -> rep@14 -> occ@24 -> rep@28.
        assert deg[0] == deg[1] == 0.0  # t=0, t=5: not yet occurred
        assert deg[2] == 1.0  # t=12: in the degraded state (10 -> 14)
        assert deg[3] == deg[4] == 0.0  # t=20, t=30: healthy again

    def test_runtime_ttf_override_matches(self):
        # Both primitives expose the entry delay as a carrier variable:
        # ObjFMDelay 'ttf', ObjDegMode 'ttf_<state1>'. Overriding it
        # before start must shift the occurrence date identically.
        system, eq, c, o, r = build_degmode_k1(
            {"cls": "delay", "time": self.TTF}, {"cls": "delay", "time": self.TTR}
        )
        system.component("E1__frun").variable("ttf_occ").setValue(6.0)
        system.isimu_start()
        fire_by_name(system, c)
        fire_by_name(system, o)
        deg_t = system.currentTime()
        system.isimu_stop()

        system, eq, c, o, r = build_objfm("ObjFMDelay", self.TTF, self.TTR)
        system.component("E1__frun").variable("ttf").setValue(6.0)
        system.isimu_start()
        fire_by_name(system, c)
        fire_by_name(system, o)
        fm_t = system.currentTime()
        system.isimu_stop()

        assert deg_t == fm_t == 6.0


class TestParityBoundary:
    def test_multi_target_delay_entry_has_no_degmode_counterpart(self):
        """The ONE deliberate non-equivalence: ObjFMDelay with N >= 2 in
        external_rep_indep (delay-driven CC combinations) cannot be
        represented — same-date combination ties are not measure-zero
        with delay laws, so ObjDegMode rejects the shape upfront."""
        system = fresh_system("ParityBoundary")
        Equipment("E1"), Equipment("E2")
        with pytest.raises(ValueError, match="single target"):
            ObjDegMode(
                fm_name="frun",
                targets=["E1", "E2"],
                states=[
                    DegState(
                        "occ",
                        occ_law={"cls": "delay", "time": 10.0},
                        rep_law={"cls": "delay", "time": 4.0},
                    )
                ],
            )
        cod3s.terminate_session()
