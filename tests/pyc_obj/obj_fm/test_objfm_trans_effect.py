"""Trans-based (``mode="trans_based"``) ObjFM effects.

Ports the reference spikes (``trans_method_semantics.py`` /
``trans_pulse_mc.py``) into non-regression tests of the real feature:
``ObjFM(failure_effects_trans=..., repair_effects_trans=...)`` wiring a
one-shot edge callback (``_wire_transition_effects``) on the occ / rep
transitions, as opposed to the state-clamped ``failure_effects``.

A trans-based effect only "sticks" on a *persistent* gate variable
(``setReinitialized(False)``): the value is written once at the firing
instant and held intra-sequence; the universal MC reset clears it between
sequences. Both-pulse = SET on occ + CLEAR on rep keeps such a gate in
phase with the failure state without a maintained level clamp (which would
write-war and hang).
"""

import time

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem


class GateComp(cod3s.PycComponent):
    """Target with a state-clamped ``working`` and two persistent gates.

    - ``working``: reinitialised (resting True) — target of a *state-based*
      effect (level clamp to False while failed, auto-restored on repair).
    - ``gate`` / ``gate2``: persistent (``setReinitialized(False)``) —
      targets of *trans-based* one-shot effects (intra-sequence memory).
    """

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)
        self.gate = self.addVariable("gate", Pyc.TVarType.t_bool, False)
        self.gate.setReinitialized(False)
        self.gate2 = self.addVariable("gate2", Pyc.TVarType.t_bool, False)
        self.gate2.setReinitialized(False)


@pytest.fixture(autouse=True)
def _release_pycatshoo_singleton_per_test():
    """Release the PyCATSHOO singleton after each test.

    These tests build several ``PycSystem`` instances (some more than one
    per test, terminating explicitly in between); PyCATSHOO is a
    process-level singleton, so each must be released. ``terminate_session``
    is idempotent, so this is safe even after an in-test terminate.
    """
    yield
    cod3s.terminate_session()


def _series(indicator):
    """('instant' list, 'values' list) from a returned indicator object."""
    return (
        indicator.values["instant"].to_list(),
        indicator.values["values"].to_list(),
    )


def test_trans_effect_edge_semantics():
    """The occ transition edge fires exactly once per crossing.

    Deterministic delays (ttf=10, ttr=5) → occ crossings at 10 / 25 / 40,
    rep crossings at 15 / 30. A spy sensitive method on the same occ
    transition that carries the trans-based gate effect records the firing
    instants; the persistent gate, sampled strictly between crossings,
    follows the both-pulse SET (occ) / CLEAR (rep) sequence exactly.
    """
    system = PycSystem(name="SysTransEdge")
    system.add_component(name="C1", cls="GateComp")
    objfm = system.add_component(
        cls="ObjFMDelay",
        fm_name="frun",
        targets=["C1"],
        failure_param=10,  # ttf
        repair_param=5,  # ttr
        failure_effects_trans={"gate": True},
        repair_effects_trans={"gate": False},
    )

    occ_bkd = objfm.automata_d["frun"].get_transition_by_name("occ")._bkd
    calls = []
    occ_bkd.addSensitiveMethod(
        "spy_occ", lambda: calls.append(round(system.currentTime(), 3))
    )

    gate_ind = system.add_indicator_var(
        component="C1", var="gate", stats=["mean"], name="gate"
    )[0]

    system.simulate(
        PycMCSimulationParam(nb_runs=1, schedule=[0, 12, 17, 27, 42], seed=42)
    )

    # Edge semantics: one call per occ crossing, at the deterministic instants.
    assert calls == [10.0, 25.0, 40.0]

    instants, gate = _series(gate_ind)
    assert instants == [0.0, 12.0, 17.0, 27.0, 42.0]
    # SET at occ (12, 27, 42 failed), CLEAR at rep (17 repaired), 0 at start.
    assert gate == [0.0, 1.0, 0.0, 1.0, 1.0]


def test_trans_effect_both_pulse_mc():
    """MC both-pulse: mean(gate) tracks P(occ); no hang, no MC leak.

    exp λ=0.1 μ=0.2 → P(occ) steady = λ/(λ+μ) = 0.333. The persistent gate
    is SET on occ and CLEARED on rep (both pulses). Over 5000 sequences,
    mean(gate) must track the failure-state probability at every instant,
    while working (state-clamped) tracks it too — proving trans and state
    effects coexist on one automaton.
    """
    system = PycSystem(name="SysTransBothPulse")
    system.add_component(name="C1", cls="GateComp")
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        failure_param=0.1,
        repair_param=0.2,
        failure_effects={"working": False},  # state-based level clamp
        failure_effects_trans={"gate": True},  # trans-based SET
        repair_effects_trans={"gate": False},  # trans-based CLEAR
    )

    occ_ind = system.add_indicator_state(
        component="C1__frun", state="occ", stats=["mean"], name="occ"
    )[0]
    gate_ind = system.add_indicator_var(
        component="C1", var="gate", stats=["mean"], name="gate"
    )[0]
    work_ind = system.add_indicator_var(
        component="C1", var="working", stats=["mean"], name="work"
    )[0]

    t0 = time.time()
    system.simulate(
        PycMCSimulationParam(nb_runs=5000, schedule=[0, 50, 100, 200], seed=12345)
    )
    elapsed = time.time() - t0

    instants, p_occ = _series(occ_ind)
    _, gate = _series(gate_ind)
    _, working = _series(work_ind)

    # no-hang: a maintained-opposite-level write-war would loop stepForward.
    assert elapsed < 30.0, f"simulate took {elapsed:.1f}s (possible write-war hang)"
    # no-leak MC: persistent gate reset between sequences.
    assert gate[0] == pytest.approx(0.0, abs=0.005)
    # both-pulse tracking + state/trans coexistence at every observed t>0.
    for i in range(1, len(instants)):
        assert gate[i] == pytest.approx(p_occ[i], abs=0.02)
        assert (1.0 - working[i]) == pytest.approx(p_occ[i], abs=0.02)
    # sanity: steady-state around the analytic 0.333.
    assert p_occ[-1] == pytest.approx(1 / 3, abs=0.03)


def test_trans_effect_coexists_with_state_effect():
    """State-based (working) and trans-based (gate) effects on one automaton.

    Deterministic single run (ttf=10, ttr=5) sampled while failed and after
    repair: working (level clamp) and gate (pulse) both apply in occ; on
    repair working is auto-restored (reinitialised) and gate is pulse-cleared.
    """
    system = PycSystem(name="SysTransCoexist")
    system.add_component(name="C1", cls="GateComp")
    system.add_component(
        cls="ObjFMDelay",
        fm_name="frun",
        targets=["C1"],
        failure_param=10,  # ttf
        repair_param=5,  # ttr
        failure_effects={"working": False},  # state-based
        failure_effects_trans={"gate": True},  # trans-based SET
        repair_effects_trans={"gate": False},  # trans-based CLEAR
    )

    gate_ind = system.add_indicator_var(
        component="C1", var="gate", stats=["mean"], name="gate"
    )[0]
    work_ind = system.add_indicator_var(
        component="C1", var="working", stats=["mean"], name="work"
    )[0]

    # occ at 10, rep at 15 → sample at 12 (failed) and 18 (repaired).
    system.simulate(PycMCSimulationParam(nb_runs=1, schedule=[0, 12, 18], seed=7))

    _, gate = _series(gate_ind)
    _, working = _series(work_ind)

    # t=0 resting, t=12 in occ (both effects), t=18 back in rep.
    assert gate == [0.0, 1.0, 0.0]
    assert working == [1.0, 0.0, 1.0]


def test_spec_without_trans_effects_byte_identical():
    """An ObjFM with empty/absent trans dicts is inert (non-regression).

    Two identical ObjFMExp built with a shared seed produce byte-identical
    MC results whether the (empty) trans dicts are passed or omitted, and
    the built automaton keeps the same occ/rep two-state structure —
    passing ``failure_effects_trans = {}`` / ``repair_effects_trans = {}``
    wires nothing. (Full ``describe()`` equality is not asserted: the occ
    law binds a backend variable object whose repr carries a per-build
    memory address, so it differs across separate ``PycSystem`` builds
    regardless of this feature.)
    """
    sim = dict(nb_runs=200, schedule=[0, 25, 75, 150], seed=98765)

    def build_and_run(with_empty_trans):
        system = PycSystem(name="SysByteId")
        system.add_component(name="C1", cls="GateComp")
        extra = (
            {"failure_effects_trans": {}, "repair_effects_trans": {}}
            if with_empty_trans
            else {}
        )
        objfm = system.add_component(
            cls="ObjFMExp",
            fm_name="frun",
            targets=["C1"],
            failure_param=0.1,
            repair_param=0.2,
            failure_effects={"working": False},
            **extra,
        )
        desc = objfm.describe()
        work_ind = system.add_indicator_var(
            component="C1", var="working", stats=["mean"], name="work"
        )[0]
        system.simulate(PycMCSimulationParam(**sim))
        _, working = _series(work_ind)
        return desc, working

    desc_absent, work_absent = build_and_run(with_empty_trans=False)
    cod3s.terminate_session()
    desc_empty, work_empty = build_and_run(with_empty_trans=True)

    # occ/rep two-state structure preserved (stable, address-free).
    for desc in (desc_absent, desc_empty):
        frun = desc["automatons"]["frun"]
        assert {s["name"] for s in frun["states"]} == {"rep", "occ"}
        assert {t["name"] for t in frun["transitions"]} == {"occ", "rep"}
    # Behavioural byte-identity: same seed → identical results.
    assert work_empty == work_absent


def test_trans_effect_multi_target_guard():
    """``target_state`` guards a trans effect to a specific landing state.

    Wired directly via ``_wire_transition_effects`` on the same occ
    transition: one effect guarded by the state occ *actually reaches*
    (applied), one guarded by rep (skipped, since rep is inactive at the
    instant occ fires).
    """
    system = PycSystem(name="SysTransGuard")
    system.add_component(name="C1", cls="GateComp")
    objfm = system.add_component(
        cls="ObjFMDelay",
        fm_name="frun",
        targets=["C1"],
        failure_param=10,  # ttf → occ at 10
        repair_param=5,
    )
    c1 = system.comp["C1"]
    aut = objfm.automata_d["frun"]

    # Guard matches the landing state → applies on occ crossing.
    objfm._wire_transition_effects(
        aut, "occ", [{"var": c1.gate, "value": True}], target_state="occ"
    )
    # Guard on a state NOT active when occ fires → never applies.
    objfm._wire_transition_effects(
        aut, "occ", [{"var": c1.gate2, "value": True}], target_state="rep"
    )

    gate_ind = system.add_indicator_var(
        component="C1", var="gate", stats=["mean"], name="gate"
    )[0]
    gate2_ind = system.add_indicator_var(
        component="C1", var="gate2", stats=["mean"], name="gate2"
    )[0]

    system.simulate(PycMCSimulationParam(nb_runs=1, schedule=[0, 12], seed=3))

    _, gate = _series(gate_ind)
    _, gate2 = _series(gate2_ind)
    assert gate == [0.0, 1.0]  # guard passed
    assert gate2 == [0.0, 0.0]  # guard skipped the pulse


def test_trans_effect_rejected_in_external_behaviour():
    """Behaviour matrix (A3): trans effects rejected outside internal law.

    ``external`` / ``external_rep_indep`` and ``ObjFMInst`` cannot host a
    one-shot occ/rep edge callback correctly → explicit ValueError (MVP).
    """
    system = PycSystem(name="SysTransReject")
    system.add_component(name="C1", cls="GateComp")

    with pytest.raises(ValueError, match="internal"):
        system.add_component(
            cls="ObjFMExp",
            fm_name="fext",
            targets=["C1"],
            behaviour="external",
            failure_param=0.1,
            repair_param=0.1,
            failure_effects_trans={"gate": True},
        )

    with pytest.raises(ValueError, match="internal"):
        system.add_component(
            cls="ObjFMExp",
            fm_name="frepindep",
            targets=["C1"],
            behaviour="external_rep_indep",
            failure_param=0.1,
            repair_param=0.1,
            repair_effects_trans={"gate": False},
        )

    with pytest.raises(ValueError, match="ObjFMInst"):
        system.add_component(
            cls="ObjFMInst",
            fm_name="finst",
            targets=["C1"],
            failure_param=0.3,
            repair_param=0.1,
            failure_effects_trans={"gate": True},
        )
