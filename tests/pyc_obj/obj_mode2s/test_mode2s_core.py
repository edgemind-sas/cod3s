"""Native ObjMode2S engine — construction grammar, validation, and the
façade ≡ raw-engine equivalence locks.

The equivalence tests are the anti-drift guard of the façade
architecture: an ``ObjMode2S`` hand-configured to mimic ``ObjFMExp``
must be indistinguishable from it — same automata / states /
transitions / variables, same sensitive-method registration counts
(per-step cost surface), same deterministic isimu cycle, and identical
seeded Monte-Carlo traces (same seed -> same draws -> same event
times).
"""

import contextlib

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import ModeLawDelay, ModeLawExp, ObjMode2S
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


# ---------------------------------------------------------------------------
# Native construction grammar
# ---------------------------------------------------------------------------


def test_native_single_target_grammar(pyc_session):
    system = PycSystem(name="Mode2SNative")
    Equipment("C1")
    mode = ObjMode2S(
        mode_name="wear",
        targets=["C1"],
        occ_law={"cls": "exp", "rate": 0.1},
        not_occ_law={"cls": "exp", "rate": 0.2},
        occ_effects={"working": False},
    )
    assert mode.name() == "C1__wear"
    assert mode.fm_name == "wear"  # documented legacy read alias
    assert list(mode.automata_d) == ["wear"]
    aut = mode.automata_d["wear"]
    assert [st.name for st in aut.states] == ["not_occ", "occ"]
    assert aut.init_state == "not_occ"
    assert aut.get_transition_by_name("occ").source == "not_occ"
    assert aut.get_transition_by_name("not_occ").source == "occ"
    # Engine-native parameter variables: direction prefix + law field.
    assert sorted(v.basename() for v in mode.variables()) == [
        "not_occ_rate",
        "occ_rate",
    ]
    assert isinstance(mode.occ_law, ModeLawExp)


def test_native_law_spec_instances_accepted(pyc_session):
    system = PycSystem(name="Mode2SNativeSpecs")
    Equipment("C1")
    mode = ObjMode2S(
        mode_name="wear",
        targets=["C1"],
        occ_law=ModeLawExp(rate=0.1),
        not_occ_law=ModeLawDelay(time=5.0),
    )
    # First mixed combo (exp occurrence / delay return).
    assert sorted(v.basename() for v in mode.variables()) == [
        "not_occ_time",
        "occ_rate",
    ]
    aut = mode.automata_d["wear"]
    assert aut.get_transition_by_name("occ").occ_law.rate is not None
    assert aut.get_transition_by_name("not_occ").occ_law.time is not None


def test_native_cc_vectors_and_drop(pyc_session):
    system = PycSystem(name="Mode2SNativeCC")
    for n in ("C1", "C2"):
        Equipment(n)
    mode = ObjMode2S(
        mode_name="wear",
        targets=["C1", "C2"],
        occ_law={"cls": "exp", "rate": [0.1, 0.0]},
        not_occ_law={"cls": "exp", "rate": [0.2, 0.0]},
    )
    # Order 2 fully inactive (exp rate 0) -> dropped; order-1 combos kept.
    assert sorted(mode.automata_d) == ["wear__cc_1", "wear__cc_2"]
    assert sorted(v.basename() for v in mode.variables()) == [
        "not_occ_rate__1_o_2",
        "not_occ_rate__2_o_2",
        "occ_rate__1_o_2",
        "occ_rate__2_o_2",
    ]


# ---------------------------------------------------------------------------
# Native validation (silent-failure hardening)
# ---------------------------------------------------------------------------


class TestNativeValidation:
    def test_unknown_kwarg_rejected(self, pyc_session):
        system = PycSystem(name="Mode2SValKw")
        Equipment("C1")
        with pytest.raises(TypeError, match="no_occ_law"):
            ObjMode2S(
                mode_name="wear",
                targets=["C1"],
                occ_law={"cls": "exp", "rate": 0.1},
                no_occ_law={"cls": "exp", "rate": 0.2},
            )

    def test_missing_law_rejected(self, pyc_session):
        system = PycSystem(name="Mode2SValNoLaw")
        Equipment("C1")
        with pytest.raises(ValueError, match="not_occ_law"):
            ObjMode2S(
                mode_name="wear",
                targets=["C1"],
                occ_law={"cls": "exp", "rate": 0.1},
            )

    def test_scalar_law_with_two_targets_rejected(self, pyc_session):
        system = PycSystem(name="Mode2SValScalar")
        for n in ("C1", "C2"):
            Equipment(n)
        with pytest.raises(ValueError, match="(?i)per-order|scalar"):
            ObjMode2S(
                mode_name="wear",
                targets=["C1", "C2"],
                occ_law={"cls": "exp", "rate": 0.1},
                not_occ_law={"cls": "exp", "rate": [0.2, 0.3]},
            )

    def test_partial_all_zero_param_vector_rejected_not_substituted(self, pyc_session):
        """An explicit vector of zeros is a deliberate 'inactive order'
        declaration: it must never be mistaken for an absent one and
        silently replaced by the law-spec values (review finding 8)."""
        system = PycSystem(name="Mode2SValFalsy")
        for n in ("C1", "C2"):
            Equipment(n)
        with pytest.raises(ValueError, match="strict length"):
            ObjMode2S(
                mode_name="wear",
                targets=["C1", "C2"],
                occ_law={"cls": "exp", "rate": [0.1, 0.2]},
                not_occ_law={"cls": "exp", "rate": [0.3, 0.4]},
                occ_param=[0.0],
            )

    def test_full_explicit_zero_vector_is_honoured(self, pyc_session):
        system = PycSystem(name="Mode2SValZeros")
        for n in ("C1", "C2"):
            Equipment(n)
        mode = ObjMode2S(
            mode_name="wear",
            targets=["C1", "C2"],
            occ_law={"cls": "exp", "rate": [0.1, 0.2]},
            not_occ_law={"cls": "exp", "rate": [0.3, 0.4]},
            occ_param=[0.0, 0.0],
            drop_inactive_automata=False,
        )
        assert mode.occ_param == [0.0, 0.0]
        assert mode.variable("occ_rate__1_o_2").value() == 0.0
        assert mode.variable("occ_rate__2_o_2").value() == 0.0

    def test_vector_length_mismatch_rejected(self, pyc_session):
        system = PycSystem(name="Mode2SValVec")
        for n in ("C1", "C2"):
            Equipment(n)
        with pytest.raises(ValueError, match="entries"):
            ObjMode2S(
                mode_name="wear",
                targets=["C1", "C2"],
                occ_law={"cls": "exp", "rate": [0.1, 0.2, 0.3]},
                not_occ_law={"cls": "exp", "rate": [0.2, 0.3]},
            )

    def test_invalid_state_name_rejected(self, pyc_session):
        system = PycSystem(name="Mode2SValState")
        Equipment("C1")
        with pytest.raises(ValueError, match="state name"):
            ObjMode2S(
                mode_name="wear",
                targets=["C1"],
                occ_state="occ.bad",
                occ_law={"cls": "exp", "rate": 0.1},
                not_occ_law={"cls": "exp", "rate": 0.2},
            )

    def test_identical_state_names_rejected(self, pyc_session):
        system = PycSystem(name="Mode2SValSame")
        Equipment("C1")
        with pytest.raises(ValueError, match="distinct"):
            ObjMode2S(
                mode_name="wear",
                targets=["C1"],
                occ_state="st",
                not_occ_state="st",
                occ_law={"cls": "exp", "rate": 0.1},
                not_occ_law={"cls": "exp", "rate": 0.2},
            )

    def test_unknown_law_cls_rejected(self, pyc_session):
        system = PycSystem(name="Mode2SValLawCls")
        Equipment("C1")
        with pytest.raises(ValueError, match="Invalid occ_law"):
            ObjMode2S(
                mode_name="wear",
                targets=["C1"],
                occ_law={"cls": "weibull", "shape": 2},
                not_occ_law={"cls": "exp", "rate": 0.2},
            )

    def test_missing_target_component_rejected(self, pyc_session):
        system = PycSystem(name="Mode2SValNoTarget")
        with pytest.raises(ValueError, match="ghost"):
            ObjMode2S(
                mode_name="wear",
                targets=["ghost"],
                occ_law={"cls": "exp", "rate": 0.1},
                not_occ_law={"cls": "exp", "rate": 0.2},
            )

    def test_effect_typo_fails_before_any_build(self, pyc_session):
        system = PycSystem(name="Mode2SValTypo")
        Equipment("C1")
        with pytest.raises(ValueError, match="workingg"):
            ObjMode2S(
                mode_name="wear",
                targets=["C1"],
                occ_law={"cls": "exp", "rate": 0.1},
                not_occ_law={"cls": "exp", "rate": 0.2},
                occ_effects={"workingg": False},
            )
        # Dry-run hardening: the failed mode must not have created
        # any automaton (variables are not created either — the dry
        # run happens before the param variables).
        mode = system.comp.get("C1__wear")
        assert mode is None or mode.automata_d == {}

    def test_wire_aliases_fm_name_and_failure_cond(self, pyc_session):
        system = PycSystem(name="Mode2SValAlias")
        Equipment("C1")
        mode = ObjMode2S(
            fm_name="wear",
            targets=["C1"],
            occ_law={"cls": "exp", "rate": 0.1},
            not_occ_law={"cls": "exp", "rate": 0.2},
            failure_cond=False,
        )
        assert mode.mode_name == "wear"
        assert mode.occ_cond is False

    def test_basespec_defaults_tolerated_explicit_rejected(self, pyc_session):
        system = PycSystem(name="Mode2SValBaseSpec")
        Equipment("C1")
        # BaseSpec defaults ride along silently (wire path emits them).
        mode = ObjMode2S(
            mode_name="wear",
            targets=["C1"],
            occ_law={"cls": "exp", "rate": 0.1},
            not_occ_law={"cls": "exp", "rate": 0.2},
            failure_state="occ",
            repair_state="rep",
            failure_effects={},
            repair_param=[],
        )
        assert mode.occ_state == "occ"
        # Explicit non-default legacy value -> clear rejection.
        with pytest.raises(ValueError, match="failure_effects"):
            ObjMode2S(
                mode_name="wear2",
                targets=["C1"],
                occ_law={"cls": "exp", "rate": 0.1},
                not_occ_law={"cls": "exp", "rate": 0.2},
                failure_effects={"working": False},
            )


# ---------------------------------------------------------------------------
# Façade ≡ raw-engine equivalence
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _spy_registrations(counts):
    orig_start = Pyc.CComponent.addStartMethod
    orig_aut = Pyc.IAutomaton.addSensitiveMethod
    orig_var = Pyc.IVariable.addSensitiveMethod

    def spy_start(self, name, fn):
        counts["start"] += 1
        return orig_start(self, name, fn)

    def spy_aut(self, name, fn):
        counts["aut_sensitive"] += 1
        return orig_aut(self, name, fn)

    def spy_var(self, name, fn):
        counts["var_sensitive"] += 1
        return orig_var(self, name, fn)

    Pyc.CComponent.addStartMethod = spy_start
    Pyc.IAutomaton.addSensitiveMethod = spy_aut
    Pyc.IVariable.addSensitiveMethod = spy_var
    try:
        yield
    finally:
        Pyc.CComponent.addStartMethod = orig_start
        Pyc.IAutomaton.addSensitiveMethod = orig_aut
        Pyc.IVariable.addSensitiveMethod = orig_var


def _build_facade_system():
    system = PycSystem(name="EquivFacade")
    Equipment("C1")
    counts = {"start": 0, "aut_sensitive": 0, "var_sensitive": 0}
    with _spy_registrations(counts):
        fm = cod3s.ObjFMExp(
            fm_name="frun",
            targets=["C1"],
            failure_param=0.1,
            repair_param=0.2,
            failure_effects={"working": False},
        )
    return system, fm, counts


def _build_native_system():
    system = PycSystem(name="EquivNative")
    Equipment("C1")
    counts = {"start": 0, "aut_sensitive": 0, "var_sensitive": 0}
    with _spy_registrations(counts):
        fm = ObjMode2S(
            mode_name="frun",
            targets=["C1"],
            occ_state="occ",
            not_occ_state="rep",
            occ_law={"cls": "exp", "rate": 0.1},
            not_occ_law={"cls": "exp", "rate": 0.2},
            occ_param_name="lambda",
            not_occ_param_name="mu",
            occ_effects={"working": False},
        )
    return system, fm, counts


def _law_desc(occ_law):
    """Normalise a transition law for comparison: law class + parameter,
    where a backend variable parameter is represented by its basename."""

    def norm(v):
        return v.basename() if hasattr(v, "basename") else v

    fields = {k: norm(v) for k, v in occ_law.model_dump().items() if k not in ("cls",)}
    # model_dump may not serialise backend variables — read the raw attrs.
    for attr in ("rate", "time", "probs"):
        if hasattr(occ_law, attr):
            fields[attr] = norm(getattr(occ_law, attr))
    return (type(occ_law).__name__, tuple(sorted(map(str, fields.items()))))


def _structure(fm):
    return {
        "comp": fm.name(),
        "automata": sorted(fm.automata_d),
        "shapes": {
            name: (
                [st.name for st in aut.states],
                sorted(
                    (t.name, t.source, _law_desc(t.occ_law)) for t in aut.transitions
                ),
                aut.init_state,
            )
            for name, aut in fm.automata_d.items()
        },
        "variables": sorted(v.basename() for v in fm.variables()),
    }


def _isimu_cycle(system, fm):
    """One deterministic occ -> rep cycle, returns the observable log."""
    log = []
    equipment = system.comp["C1"]
    system.isimu_start()
    trs = system.isimu_fireable_transitions()
    idx = next(
        i
        for i, t in enumerate(trs)
        if t is not None and t.name == "occ" and t.comp_name == fm.name()
    )
    system.isimu_set_transition(idx, date=3.0)
    log.append([t.name for t in system.isimu_step_forward()])
    log.append(("working", equipment.working.value()))
    trs = system.isimu_fireable_transitions()
    idx = next(i for i, t in enumerate(trs) if t is not None and t.name == "rep")
    system.isimu_set_transition(idx, date=7.5)
    log.append([t.name for t in system.isimu_step_forward()])
    log.append(("working", equipment.working.value()))
    log.append(("t", system.currentTime()))
    system.isimu_stop()
    return log


def _mc_occurrence_times(system, tmp_path, tag):
    """Seeded MC: per-run time of the first occ event (target ST)."""
    system.addTarget("occ_target", "C1__frun.occ", "ST")
    system.monitorTransition("#.*")
    seq_path = tmp_path / f"seq_{tag}.xml"
    system.setResultFileName(str(seq_path), False)
    system.setBinSeqFile(False)
    system.simulate({"nb_runs": 20, "seed": 42, "schedule": [200.0]})
    analyser = SequenceAnalyser.from_pyc_system(system)
    times = sorted(
        round(ev.time, 9)
        for seq in analyser.sequences
        for ev in seq.events
        if ev.attr == "occ"
    )
    return times


def test_facade_equals_raw_engine_structure_and_counts(pyc_session):
    system_a, fm_a, counts_a = _build_facade_system()
    struct_a = _structure(fm_a)
    cod3s.terminate_session()

    system_b, fm_b, counts_b = _build_native_system()
    struct_b = _structure(fm_b)

    assert struct_a == struct_b
    assert counts_a == counts_b


def test_facade_equals_raw_engine_isimu_cycle(pyc_session):
    system_a, fm_a, _ = _build_facade_system()
    log_a = _isimu_cycle(system_a, fm_a)
    cod3s.terminate_session()

    system_b, fm_b, _ = _build_native_system()
    log_b = _isimu_cycle(system_b, fm_b)

    assert log_a == log_b
    assert log_a[0] == ["occ"]
    assert log_a[1] == ("working", False)


def test_facade_equals_raw_engine_seeded_mc_traces(pyc_session, tmp_path):
    """Same seed, same structure -> strictly identical event times."""
    system_a, fm_a, _ = _build_facade_system()
    times_a = _mc_occurrence_times(system_a, tmp_path, "facade")
    cod3s.terminate_session()

    system_b, fm_b, _ = _build_native_system()
    times_b = _mc_occurrence_times(system_b, tmp_path, "native")

    assert len(times_a) > 0
    assert times_a == times_b
