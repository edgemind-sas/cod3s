"""inst laws x external behaviours — parity locks (guard lifted in 1.14.1).

Three locks, closing the historical coverage gap in one move:

* The ``ObjFMInst`` façade with ``behaviour="external"`` /
  ``"external_rep_indep"`` keeps building exactly as it has since
  1.10.0 (structural pin — it had no dedicated test until now).
* A native ``ObjMode2S`` configured to mimic ``ObjFMInst`` produces the
  SAME structure, registration counts and seeded MC traces in the
  external behaviours: the 1.14.1 guard lift is an alignment on the
  semantics the façade always exercised, not a new semantic.
* inst on the RETURN direction x external (order 1) — the per-demand
  recovery cell the platform 3x3 exposes — walks through a full isimu
  cycle (draw branches, parked micro-state, re-arm, successful retry).
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import ObjMode2S
from cod3s.pycatshoo.sequence import SequenceAnalyser
from cod3s.pycatshoo.system import PycSystem

from test_mode2s_core import _spy_registrations, _structure  # noqa: E402

BEHAVIOURS = ["external", "external_rep_indep"]
GAMMAS = [0.3, 0.1]
MUS = [0.5, 0.5]


class Equipment(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)
        self.crew = self.addVariable("crew", Pyc.TVarType.t_bool, False)


@pytest.fixture
def pyc_session():
    yield
    cod3s.terminate_session()


def _build_facade(behaviour):
    system = PycSystem(name="InstExtFacade")
    for n in ("E1", "E2"):
        Equipment(n)
    counts = {"start": 0, "aut_sensitive": 0, "var_sensitive": 0}
    with _spy_registrations(counts):
        fm = cod3s.ObjFMInst(
            fm_name="miss",
            targets=["E1", "E2"],
            behaviour=behaviour,
            failure_param=GAMMAS,
            repair_param=MUS,
            failure_effects={"working": False},
        )
    return system, fm, counts


def _build_native(behaviour):
    system = PycSystem(name="InstExtNative")
    for n in ("E1", "E2"):
        Equipment(n)
    counts = {"start": 0, "aut_sensitive": 0, "var_sensitive": 0}
    with _spy_registrations(counts):
        fm = ObjMode2S(
            mode_name="miss",
            targets=["E1", "E2"],
            behaviour=behaviour,
            occ_state="occ",
            not_occ_state="rep",
            occ_parked_state="not_occ",
            occ_law={"cls": "inst", "prob": GAMMAS},
            not_occ_law={"cls": "exp", "rate": MUS},
            occ_param_name="gamma",
            not_occ_param_name="mu",
            occ_effects={"working": False},
        )
    return system, fm, counts


def _mc_event_trace(system, tmp_path, tag):
    """Seeded MC: the full (component, transition, time) event multiset."""
    system.monitorTransition("#.*")
    seq_path = tmp_path / f"seq_{tag}.xml"
    system.setResultFileName(str(seq_path), False)
    system.setBinSeqFile(False)
    system.simulate({"nb_runs": 20, "seed": 42, "schedule": [50.0]})
    analyser = SequenceAnalyser.from_pyc_system(system)
    return sorted(
        (ev.obj, ev.attr, round(ev.time, 9))
        for seq in analyser.sequences
        for ev in seq.events
    )


def test_facade_objfminst_external_structural_pin(pyc_session):
    """1.13.0-era behaviour, pinned for the first time: ObjFMInst x
    external builds its per-combination automata and CC variables."""
    system, fm, _ = _build_facade("external")
    assert sorted(fm.automata_d) == ["miss__cc_1", "miss__cc_1_2", "miss__cc_2"]
    for aut in fm.automata_d.values():
        names = {st.name for st in aut.states}
        # Armed state (rep), failure state (occ), parked draw (not_occ).
        assert {n.split("__cc_")[0] for n in names} == {"rep", "occ", "not_occ"}
    assert {v.basename() for v in fm.variables()} >= {"gamma__1_o_2", "mu__1_o_2"}
    cod3s.terminate_session()

    # external_rep_indep builds too (repair independent, order 1).
    system, fm, _ = _build_facade("external_rep_indep")
    assert sorted(fm.automata_d) == ["miss__cc_1", "miss__cc_1_2", "miss__cc_2"]


@pytest.mark.parametrize("behaviour", BEHAVIOURS)
def test_inst_external_facade_equals_native_structure(pyc_session, behaviour):
    system_a, fm_a, counts_a = _build_facade(behaviour)
    struct_a = _structure(fm_a)
    cod3s.terminate_session()

    system_b, fm_b, counts_b = _build_native(behaviour)
    struct_b = _structure(fm_b)

    # The component name embeds nothing behaviour-specific; structures
    # must match exactly (automata, states, transitions + laws, vars).
    assert struct_a == struct_b
    assert counts_a == counts_b


@pytest.mark.parametrize("behaviour", BEHAVIOURS)
def test_inst_external_facade_equals_native_seeded_mc(pyc_session, tmp_path, behaviour):
    """Same seed, same structure -> strictly identical event traces.

    With no failure_cond the demand holds from t=0 ("immediately or
    never" draw), repairs re-solicit immediately: the trace mixes
    Bernoulli draws and exp(mu) repairs, a strong seeded signal.
    """
    system_a, fm_a, _ = _build_facade(behaviour)
    trace_a = _mc_event_trace(system_a, tmp_path, f"facade_{behaviour}")
    cod3s.terminate_session()

    system_b, fm_b, _ = _build_native(behaviour)
    trace_b = _mc_event_trace(system_b, tmp_path, f"native_{behaviour}")

    assert len(trace_a) > 0
    assert trace_a == trace_b


def test_return_inst_external_per_demand_recovery(pyc_session):
    """inst on the RETURN direction x external, order 1: one repair
    attempt per crew visit, with effects applied through the external
    machinery (ctrl var on the target)."""
    system = PycSystem(name="InstReturnExt")
    Equipment("E1")
    eq = system.comp["E1"]
    mode = ObjMode2S(
        mode_name="fix",
        targets=["E1"],
        behaviour="external",
        occ_law={"cls": "delay", "time": 2.0},
        not_occ_law={"cls": "inst", "prob": 0.8},
        not_occ_cond=lambda: eq.crew.value() is True,
        occ_effects={"working": False},
    )
    carrier = mode.name()
    aut = mode.automata_d["fix"]
    assert {st.name for st in aut.states} == {"not_occ", "occ", "occ_star"}

    def fireable():
        return [t for t in system.isimu_fireable_transitions() if t is not None]

    def fire(name, state_index=None, date=None):
        trs = system.isimu_fireable_transitions()
        idx = next(
            i for i, t in enumerate(trs) if t is not None and t.name == name
        )
        kwargs = {}
        if state_index is not None:
            kwargs["state_index"] = state_index
        if date is not None:
            kwargs["date"] = date
        system.isimu_set_transition(idx, **kwargs)
        return [t.name for t in system.isimu_step_forward()]

    system.isimu_start()
    # Deterministic failure at t=2; external effects land on the target.
    fired = fire("occ")
    assert "occ" in fired
    while eq.working.value() is True and fireable():
        # external may need the target-side automaton step(s) to apply
        # the effect; drain same-date pendings.
        system.isimu_step_forward()
    assert eq.working.value() is False

    # No crew -> no recovery attempt fireable on the carrier.
    assert not any(t.comp_name == carrier for t in fireable())

    # Crew arrives: the return draw is pending with branches
    # [not_occ (0.8), occ_star (0.2)].
    eq.crew.setValue(True)
    system.isimu_step_forward()
    draws = [t for t in fireable() if t.comp_name == carrier]
    assert len(draws) == 1
    assert draws[0].name == "not_occ"
    assert [b.state for b in draws[0].target] == ["not_occ", "occ_star"]
    assert draws[0].target[0].prob == pytest.approx(0.8)

    # Attempt FAILS (parked branch): logically still failed, no re-draw
    # while the crew stays (anti-Zeno).
    fire("not_occ", state_index=1)
    assert aut.get_state_by_name("occ_star")._bkd.isActive()
    assert eq.working.value() is False
    assert not any(t.comp_name == carrier for t in fireable())

    # Crew leaves -> deterministic re-arm (masked, inst p=1).
    eq.crew.setValue(False)
    system.isimu_step_forward()
    fired = [t.name for t in system.isimu_step_forward()]
    assert fired == ["occ_star"]
    assert aut.get_state_by_name("occ")._bkd.isActive()

    # New crew visit = new attempt; this one SUCCEEDS.
    eq.crew.setValue(True)
    system.isimu_step_forward()
    fire("not_occ", state_index=0)
    assert aut.get_state_by_name("not_occ")._bkd.isActive()
    while eq.working.value() is False and fireable():
        system.isimu_step_forward()
    assert eq.working.value() is True
    system.isimu_stop()
