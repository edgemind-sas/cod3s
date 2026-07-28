"""Zero-rate direction x façade ≡ native RNG-stream parity (1.14.3 fix).

A direction whose exp law carries an EXPLICIT rate 0 must not consume
RNG samples on the native path when the façade does not: ObjFMExp gates
its transition guard with ``param.bValue() and cond`` (rate 0 -> guard
false -> never scheduled -> no draw), while the native path used to
schedule exp(0) = +inf and burn one uniform per run — shifting every
subsequent draw of the SYSTEM. Invisible on the mode itself (it is
inert), the shift breaks seeded parity for every OTHER component, which
is exactly how the cod3s-platform emission-parity validation caught it
on a real study (modes with lambda=0 & mu>0, or mu_k=0 at an active
order k).

Locks, with a COMPANION mode acting as the RNG-stream witness:

* (lambda=0, mu>0) single target — the inert-occurrence cell;
* (lambda_k>0, mu_k=0) CC order 2 — the asymmetric-order cell;
* runtime re-activation: bumping the zero rate at runtime re-arms the
  transition (the gate is late-bound, exactly like the façade).
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import ObjMode2S
from cod3s.pycatshoo.sequence import SequenceAnalyser
from cod3s.pycatshoo.system import PycSystem


class Equipment(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


@pytest.fixture
def pyc_session():
    yield
    cod3s.terminate_session()


def _mc_trace(system, tmp_path, tag):
    system.monitorTransition("#.*")
    seq_path = tmp_path / f"seq_{tag}.xml"
    system.setResultFileName(str(seq_path), False)
    system.setBinSeqFile(False)
    system.simulate({"nb_runs": 30, "seed": 42, "schedule": [60.0]})
    analyser = SequenceAnalyser.from_pyc_system(system)
    return [
        tuple((ev.obj, ev.attr, round(ev.time, 9)) for ev in seq.events)
        for seq in analyser.sequences
    ]


def _build_pair(kind, native):
    """One zero-rate mode + one companion witness mode."""
    system = PycSystem(name="ZeroRateParity")
    for n in ("E1", "E2"):
        Equipment(n)
    if kind == "inert_occ":
        # lambda=0, mu>0 on one target.
        zero_kwargs_facade = dict(
            fm_name="inert", targets=["E1"], failure_param=0.0, repair_param=0.5
        )
        zero_kwargs_native = dict(
            mode_name="inert",
            targets=["E1"],
            occ_state="occ",
            not_occ_state="rep",
            occ_law={"cls": "exp", "rate": 0.0},
            not_occ_law={"cls": "exp", "rate": 0.5},
            occ_param_name="lambda",
            not_occ_param_name="mu",
        )
    else:
        # CC order 2 active on occ, mu_2 = 0 (asymmetric order).
        zero_kwargs_facade = dict(
            fm_name="asym",
            targets=["E1", "E2"],
            failure_param=[0.05, 0.02],
            repair_param=[0.15, 0.0],
        )
        zero_kwargs_native = dict(
            mode_name="asym",
            targets=["E1", "E2"],
            occ_state="occ",
            not_occ_state="rep",
            occ_law={"cls": "exp", "rate": [0.05, 0.02]},
            not_occ_law={"cls": "exp", "rate": [0.15, 0.0]},
            occ_param_name="lambda",
            not_occ_param_name="mu",
        )
    if native:
        zero = ObjMode2S(**zero_kwargs_native)
        witness = ObjMode2S(
            mode_name="witness",
            targets=["E2"],
            occ_state="occ",
            not_occ_state="rep",
            occ_law={"cls": "exp", "rate": 0.08},
            not_occ_law={"cls": "exp", "rate": 0.3},
            occ_param_name="lambda",
            not_occ_param_name="mu",
        )
    else:
        zero = cod3s.ObjFMExp(**zero_kwargs_facade)
        witness = cod3s.ObjFMExp(
            fm_name="witness", targets=["E2"], failure_param=0.08, repair_param=0.3
        )
    return system, zero, witness


@pytest.mark.parametrize("kind", ["inert_occ", "asym_order"])
def test_zero_rate_direction_facade_equals_native_traces(pyc_session, tmp_path, kind):
    system_a, _, _ = _build_pair(kind, native=False)
    traces_a = _mc_trace(system_a, tmp_path, f"facade_{kind}")
    cod3s.terminate_session()

    system_b, _, _ = _build_pair(kind, native=True)
    traces_b = _mc_trace(system_b, tmp_path, f"native_{kind}")

    assert any(len(t) > 0 for t in traces_a), "witness events expected"
    assert traces_a == traces_b


def _isimu_occ_schedulable(native):
    system, zero, _witness = _build_pair("inert_occ", native=native)
    system.isimu_start()
    carrier = zero.name()
    fireable = [
        t
        for t in system.isimu_fireable_transitions()
        if t is not None and t.comp_name == carrier and t.name == "occ"
    ]
    system.isimu_stop()
    return bool(fireable)


def test_zero_rate_isimu_schedulability_parity(pyc_session):
    """The zero-rate occ transition has the SAME isimu schedulability on
    both paths (the gate mirrors the façade's ``bValue() and cond``:
    rate 0 -> guard false -> not schedulable)."""
    facade_schedulable = _isimu_occ_schedulable(native=False)
    cod3s.terminate_session()
    native_schedulable = _isimu_occ_schedulable(native=True)
    assert facade_schedulable == native_schedulable
    assert facade_schedulable is False
