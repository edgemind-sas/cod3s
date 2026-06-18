"""Tests for ``SequenceAnalyser.filter_objevent_cycles`` and
``_discover_objevent_specs``.

Mirror of ``test_pyc_sequence_filter_objfm.py`` for ObjEvent. The
algorithmic cases build synthetic ``Sequence`` / ``SequenceAnalyser``
objects directly (no PycSystem). A couple of system-based cases at the
end exercise the ``isinstance``-based auto-discovery.

An ObjEvent's transitions appear in the trace as ``{event}.occ`` /
``{event}.not_occ`` (the automaton names its transitions after the
target state via ``trans_name_12_fmt="{st2}"`` / ``trans_name_21_fmt=
"{st1}"``). ``filter_objevent_cycles`` cancels each paired occ→not_occ
transient (a flip that nets back to nominal) and keeps any unbalanced
``occ`` — notably the held ``occ`` of a reached target.

Parity invariant (cf. plan review B1): an ObjEvent starts ``not_occ``
and must end ``occ`` to be the reached target, so ``n_occ == n_not_occ
+ 1`` there and exactly one ``occ`` survives the greedy-left pairing of
``rm_events_ordered_pattern``.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s.pycatshoo.sequence import SeqEvent, Sequence, SequenceAnalyser
from cod3s.pycatshoo.system import PycSystem


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


# ---------------------------------------------------------------------------
# Algorithmic cases (pure Python, no PycSystem)
# ---------------------------------------------------------------------------


class TestFilterObjEventCycles:
    def test_drops_paired_occ_not_occ(self):
        seq = _seq(_ev("e1", "occ"), _ev("e1", "not_occ"), _ev("top", "occ"))
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objevent_cycles(
            objevents=[("e1", "occ", "not_occ")], inplace=False
        )
        assert _sig(result.sequences[0]) == [("top", "occ")]

    def test_held_occ_kept_even_midchain(self):
        """The reached target ``e1`` holds its ``occ`` (no later
        ``not_occ``) → survives, even though it sits in the middle of the
        chain (the last event is a different one). This is the
        non-regression guard for the target highlight."""
        seq = _seq(
            _ev("cause", "fail"),
            _ev("e1", "occ"),  # reached target, mid-chain
            _ev("e2", "occ"),
            target="e1",
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objevent_cycles(
            objevents=[("e1", "occ", "not_occ"), ("e2", "occ", "not_occ")],
            inplace=False,
        )
        assert _sig(result.sequences[0]) == [
            ("cause", "fail"),
            ("e1", "occ"),
            ("e2", "occ"),
        ]

    def test_not_occ_orphan_survives(self):
        """A lone ``not_occ`` (no preceding ``occ`` — theoretically
        impossible since events start ``not_occ``) never matches pat1 and
        is kept untouched."""
        seq = _seq(_ev("e1", "not_occ"), _ev("top", "occ"))
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objevent_cycles(
            objevents=[("e1", "occ", "not_occ")], inplace=False
        )
        assert _sig(result.sequences[0]) == [("e1", "not_occ"), ("top", "occ")]

    def test_odd_multiplicity_keeps_one_occ(self):
        """Parity: ``occ, occ, not_occ`` → one ``occ`` survives
        (n_occ - n_not_occ = 1)."""
        seq = _seq(
            _ev("e1", "occ"),
            _ev("e1", "occ"),
            _ev("e1", "not_occ"),
            target="e1",
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objevent_cycles(
            objevents=[("e1", "occ", "not_occ")], inplace=False
        )
        assert _sig(result.sequences[0]) == [("e1", "occ")]

    def test_transient_then_final_occ(self):
        """A target reached, repaired, then reached again
        (``occ, not_occ, occ``) → the final held ``occ`` survives."""
        seq = _seq(
            _ev("e1", "occ"),
            _ev("e1", "not_occ"),
            _ev("e1", "occ"),
            target="e1",
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objevent_cycles(
            objevents=[("e1", "occ", "not_occ")], inplace=False
        )
        assert _sig(result.sequences[0]) == [("e1", "occ")]

    def test_interleaved_two_events_collapse(self):
        """The RATP-shaped ``Normal`` case: two observers toggle,
        interleaved → both pairs cancel → empty chain."""
        seq = _seq(
            _ev("a", "occ"),
            _ev("b", "occ"),
            _ev("a", "not_occ"),
            _ev("b", "not_occ"),
            target="Normal",
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objevent_cycles(
            objevents=[("a", "occ", "not_occ"), ("b", "occ", "not_occ")],
            inplace=False,
        )
        assert _sig(result.sequences[0]) == []

    def test_dotted_event_name_is_escaped(self):
        """A dot-capable ObjEvent name (``ER.XY``) must be matched as a
        literal, not as a regex."""
        seq = _seq(_ev("ER.XY", "occ"), _ev("ER.XY", "not_occ"), _ev("top", "occ"))
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objevent_cycles(
            objevents=[("ER.XY", "occ", "not_occ")], inplace=False
        )
        assert _sig(result.sequences[0]) == [("top", "occ")]

    def test_custom_state_names(self):
        seq = _seq(_ev("alarm", "up"), _ev("alarm", "down"), _ev("top", "occ"))
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objevent_cycles(
            objevents=[("alarm", "up", "down")], inplace=False
        )
        assert _sig(result.sequences[0]) == [("top", "occ")]

    def test_empty_objevents_is_noop_then_regroups(self):
        s1 = _seq(_ev("e", "occ"))
        s2 = _seq(_ev("e", "occ"))
        analyser = SequenceAnalyser(sequences=[s1, s2])
        result = analyser.filter_objevent_cycles(objevents=[], inplace=False)
        assert len(result.sequences) == 1
        assert result.sequences[0].weight == 2

    def test_inplace_mutates_self(self):
        analyser = SequenceAnalyser(
            sequences=[_seq(_ev("e", "occ"), _ev("e", "not_occ"), _ev("top", "occ"))]
        )
        returned = analyser.filter_objevent_cycles(
            objevents=[("e", "occ", "not_occ")], inplace=True
        )
        assert returned is analyser
        assert _sig(analyser.sequences[0]) == [("top", "occ")]

    def test_zero_event_normal_sequence_is_kept(self):
        """A ``Normal`` trajectory whose observers all toggle collapses to
        an empty chain — preserved with its weight (the nominal outcome
        probability)."""
        seq = _seq(
            _ev("e1", "occ"),
            _ev("e1", "not_occ"),
            target="Normal",
            weight=42,
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objevent_cycles(
            objevents=[("e1", "occ", "not_occ")], inplace=False
        )
        assert len(result.sequences) == 1
        assert result.sequences[0].events == []
        assert result.sequences[0].weight == 42
        assert result.sequences[0].target_name == "Normal"

    def test_preserves_metadata(self):
        seq = Sequence(
            probability=None,
            weight=7,
            end_time=123.0,
            target_name="e1",
            events=[_ev("e1", "occ")],
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objevent_cycles(
            objevents=[("e1", "occ", "not_occ")], inplace=False
        )
        assert result.sequences[0].weight == 7
        assert result.sequences[0].end_time == 123.0
        assert result.sequences[0].target_name == "e1"
        assert _sig(result.sequences[0]) == [("e1", "occ")]


# ---------------------------------------------------------------------------
# Auto-discovery (system-based)
# ---------------------------------------------------------------------------


class EvtBox(cod3s.PycComponent):
    """Minimal component carrying a boolean an ObjEvent can condition on."""

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


@pytest.fixture
def pyc_session():
    yield
    cod3s.terminate_session()


def test_autodiscover_objevent_default_states(pyc_session):
    system = PycSystem(name="AutoDiscoverObjEvent")
    system.add_component(name="box", cls="EvtBox")
    system.add_component(
        cls="ObjEvent",
        name="system_down",
        cond=[[{"obj": "box", "attr": "working", "ope": "==", "value": False}]],
    )
    analyser = SequenceAnalyser(
        sequences=[
            _seq(
                _ev("system_down", "occ"),
                _ev("system_down", "not_occ"),
                _ev("top", "occ"),
            )
        ]
    )
    analyser._system = system  # simulate from_pyc_system attaching the ref

    assert analyser._discover_objevent_specs() == [("system_down", "occ", "not_occ")]

    # No args → the ObjEvent is auto-discovered and its transient cancelled.
    result = analyser.filter_objevent_cycles(inplace=False)
    assert _sig(result.sequences[0]) == [("top", "occ")]


def test_autodiscover_objevent_custom_states(pyc_session):
    system = PycSystem(name="AutoDiscoverCustom")
    system.add_component(name="box", cls="EvtBox")
    system.add_component(
        cls="ObjEvent",
        name="alarm",
        cond=[[{"obj": "box", "attr": "working", "ope": "==", "value": False}]],
        occ_state_name="up",
        not_occ_state_name="down",
    )
    analyser = SequenceAnalyser(sequences=[])
    analyser._system = system

    assert analyser._discover_objevent_specs() == [("alarm", "up", "down")]
