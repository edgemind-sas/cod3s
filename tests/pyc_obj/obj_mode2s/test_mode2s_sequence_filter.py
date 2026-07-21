"""Sequence auto-discovery for bare (native) ObjMode2S instances.

After the façade refactor, ``ObjFM`` and ``ObjEvent`` are both
``ObjMode2S`` subclasses — the discovery branch for bare engine modes
must therefore EXCLUDE the façades, or their cycles would be
double-filtered (once by their dedicated branch, once by the generic
one). Bare internal modes collapse their occ/not_occ cycles exactly
like internal ObjFM occ/rep cycles.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import ObjMode2S
from cod3s.pycatshoo.sequence import SeqEvent, Sequence, SequenceAnalyser
from cod3s.pycatshoo.system import PycSystem


class Box(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


@pytest.fixture
def pyc_session():
    yield
    cod3s.terminate_session()


def _ev(obj, attr, t=0.0):
    return SeqEvent(obj=obj, attr=attr, time=t, type=None)


def _seq(*events, target="top", weight=1):
    return Sequence(
        probability=None,
        weight=weight,
        end_time=None,
        target_name=target,
        events=list(events),
    )


def _sig(seq):
    return [(e.obj, e.attr) for e in seq.events]


def test_bare_engine_discovered_with_facade_exclusion(pyc_session):
    system = PycSystem(name="Mode2SDiscover")
    for n in ("C1", "C2"):
        Box(n)
    # Bare native mode (internal).
    ObjMode2S(
        mode_name="wear",
        targets=["C1"],
        occ_law={"cls": "exp", "rate": 0.1},
        not_occ_law={"cls": "exp", "rate": 0.2},
    )
    # Façades: must stay in their historical buckets.
    cod3s.ObjFMExp(
        fm_name="frun",
        targets=["C2"],
        failure_param=0.1,
        repair_param=0.2,
    )
    system.add_component(
        cls="ObjEvent",
        name="system_down",
        cond=[[{"obj": "C1", "attr": "working", "ope": "==", "value": False}]],
    )

    analyser = SequenceAnalyser(sequences=[])
    analyser._system = system

    internal, external = analyser._discover_objfm_specs()
    assert ("C1__wear", "occ", "not_occ") in internal
    assert ("C2__frun", "occ", "rep") in internal
    # The bare-engine branch must NOT capture the façades: exactly one
    # entry per component, and the ObjEvent stays out of the FM buckets.
    assert len(internal) == 2
    assert external == []
    assert analyser._discover_objevent_specs() == [("system_down", "occ", "not_occ")]


def test_bare_engine_custom_states_discovered(pyc_session):
    system = PycSystem(name="Mode2SDiscoverCustom")
    Box("C1")
    ObjMode2S(
        mode_name="wear",
        targets=["C1"],
        occ_state="worn",
        not_occ_state="fresh",
        occ_law={"cls": "exp", "rate": 0.1},
        not_occ_law={"cls": "exp", "rate": 0.2},
    )
    analyser = SequenceAnalyser(sequences=[])
    analyser._system = system
    internal, _ = analyser._discover_objfm_specs()
    assert internal == [("C1__wear", "worn", "fresh")]


def test_bare_engine_cycles_collapsed(pyc_session):
    """occ/not_occ transients of a bare internal mode net out of the
    minimal sequences, exactly like internal ObjFM occ/rep cycles."""
    system = PycSystem(name="Mode2SCollapse")
    Box("C1")
    ObjMode2S(
        mode_name="wear",
        targets=["C1"],
        occ_law={"cls": "exp", "rate": 0.1},
        not_occ_law={"cls": "exp", "rate": 0.2},
    )
    analyser = SequenceAnalyser(
        sequences=[
            _seq(
                _ev("C1__wear", "occ"),
                _ev("C1__wear", "not_occ"),
                _ev("top", "occ"),
            )
        ]
    )
    analyser._system = system

    result = analyser.filter_objfm_cycles(inplace=False)
    assert _sig(result.sequences[0]) == [("top", "occ")]


class TestExplicitFilterHonoursPerModeStateNames:
    """cod3s-seq lists discovered modes and applies ONE (failure_state,
    repair_state) pair; a system mixing ObjFM (occ/rep) and a bare
    ObjMode2S (occ/not_occ) has no single valid pair, so a selected
    ObjMode2S used to be silently left untouched (review finding 9)."""

    def _system_with_both(self):
        system = PycSystem(name="Mode2SExplicitFilter")
        Box("C1")
        Box("C2")
        ObjMode2S(
            mode_name="wear",
            targets=["C1"],
            occ_law={"cls": "exp", "rate": 0.1},
            not_occ_law={"cls": "exp", "rate": 0.2},
        )
        cod3s.ObjFMExp(
            fm_name="frun", targets=["C2"], failure_param=0.1, repair_param=0.2
        )
        return system

    def _analyser(self, system):
        analyser = SequenceAnalyser(
            sequences=[
                _seq(
                    _ev("C1__wear", "occ"),
                    _ev("C1__wear", "not_occ"),
                    _ev("C2__frun", "occ"),
                    _ev("C2__frun", "rep"),
                    _ev("top", "occ"),
                )
            ]
        )
        analyser._system = system
        return analyser

    def test_default_pair_uses_each_mode_own_state_names(self, pyc_session):
        system = self._system_with_both()
        analyser = self._analyser(system)
        result = analyser.filter_objfm_cycles(
            objfm_internal=["C1__wear", "C2__frun"],
            objfm_external=[],
            inplace=False,
        )
        # Both transients collapse despite using different conventions.
        assert _sig(result.sequences[0]) == [("top", "occ")]

    def test_explicit_non_default_pair_still_wins(self, pyc_session):
        system = self._system_with_both()
        analyser = self._analyser(system)
        result = analyser.filter_objfm_cycles(
            objfm_internal=["C1__wear", "C2__frun"],
            objfm_external=[],
            failure_state="occ",
            repair_state="zzz",
            inplace=False,
        )
        # The caller asked for a specific pair: no introspection kicks
        # in, so nothing matches and nothing is stripped.
        assert _sig(result.sequences[0]) == [
            ("C1__wear", "occ"),
            ("C1__wear", "not_occ"),
            ("C2__frun", "occ"),
            ("C2__frun", "rep"),
            ("top", "occ"),
        ]

    def test_post_mortem_without_system_keeps_the_given_pair(self, pyc_session):
        """No attached system (post-mortem path): the explicit pair is
        the only available information and must be used as-is."""
        analyser = SequenceAnalyser(
            sequences=[
                _seq(
                    _ev("C2__frun", "occ"),
                    _ev("C2__frun", "rep"),
                    _ev("top", "occ"),
                )
            ]
        )
        assert analyser._system is None
        result = analyser.filter_objfm_cycles(
            objfm_internal=["C2__frun"], objfm_external=[], inplace=False
        )
        assert _sig(result.sequences[0]) == [("top", "occ")]


def test_self_hosted_bare_engine_cycles_collapsed(pyc_session):
    system = PycSystem(name="Mode2SCollapseSelf")
    Box("C1")
    box = system.comp["C1"]
    ObjMode2S(
        mode_name="watch",
        targets=None,
        occ_law={"cls": "delay", "time": 0},
        not_occ_law={"cls": "delay", "time": 0},
        occ_cond=lambda: box.working.value() is False,
    )
    analyser = SequenceAnalyser(
        sequences=[
            _seq(
                _ev("watch", "occ"),
                _ev("watch", "not_occ"),
                _ev("top", "occ"),
            )
        ]
    )
    analyser._system = system

    internal, external = analyser._discover_objfm_specs()
    assert internal == [("watch", "occ", "not_occ")]
    result = analyser.filter_objfm_cycles(inplace=False)
    assert _sig(result.sequences[0]) == [("top", "occ")]
