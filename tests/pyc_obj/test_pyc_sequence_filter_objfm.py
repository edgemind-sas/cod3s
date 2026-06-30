"""Tests for ``rm_events_by_obj`` and ``filter_objfm_cycles``.

These methods strip ObjFM occ/rep cycles from sequence traces so the
downstream :meth:`SequenceAnalyser.compute_minimal_sequences` (which is
greedy and order-dependent) is not biased by transient pairs.

The tests build synthetic ``Sequence`` / ``SequenceAnalyser`` objects
directly — no PycSystem is needed. Reflects the real event-naming
conventions of ObjFM:

* internal mode, multi-target: ``fm.occ__cc_X`` / ``fm.rep__cc_X``
* internal mode, single-target: ``fm.occ`` / ``fm.rep`` (no suffix)
* external mode: ObjFM emits ``fm.occ__cc_X`` / ``fm.rep__cc_X`` AND
  each target emits ``target.occ`` / ``target.rep``
"""

import pytest

from cod3s.pycatshoo.sequence import SeqEvent, Sequence, SequenceAnalyser


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


# ---------------------------------------------------------------------------
# Sequence.rm_events_by_obj
# ---------------------------------------------------------------------------


class TestSequenceRmEventsByObj:
    def test_drops_matching_events_inplace(self):
        seq = _seq(_ev("fm", "occ__cc_1"), _ev("comp", "state"), _ev("fm", "rep__cc_1"))
        seq.rm_events_by_obj("fm", inplace=True)
        assert [(e.obj, e.attr) for e in seq.events] == [("comp", "state")]

    def test_returns_new_when_not_inplace(self):
        seq = _seq(_ev("fm", "occ"), _ev("c1", "state"))
        result = seq.rm_events_by_obj("fm", inplace=False)
        # Original is unchanged.
        assert [(e.obj, e.attr) for e in seq.events] == [("fm", "occ"), ("c1", "state")]
        assert [(e.obj, e.attr) for e in result.events] == [("c1", "state")]

    def test_no_match_keeps_everything(self):
        seq = _seq(_ev("c1", "occ"), _ev("c2", "rep"))
        result = seq.rm_events_by_obj("nonexistent", inplace=False)
        assert len(result.events) == 2

    def test_empty_sequence_stays_empty(self):
        seq = _seq(target="top")
        result = seq.rm_events_by_obj("fm", inplace=False)
        assert result.events == []
        assert result.target_name == "top"


# ---------------------------------------------------------------------------
# SequenceAnalyser.rm_events_by_obj
# ---------------------------------------------------------------------------


class TestAnalyserRmEventsByObj:
    def test_strips_obj_across_all_sequences_and_regroups(self):
        # Two sequences become identical after dropping ``fm`` events.
        s1 = _seq(_ev("fm", "occ"), _ev("c1", "fail"), _ev("fm", "rep"))
        s2 = _seq(_ev("c1", "fail"))
        analyser = SequenceAnalyser(sequences=[s1, s2])
        result = analyser.rm_events_by_obj("fm", inplace=False)
        # After regrouping, only one signature with weight=2 remains.
        assert len(result.sequences) == 1
        assert result.sequences[0].weight == 2
        assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
            ("c1", "fail")
        ]


# ---------------------------------------------------------------------------
# SequenceAnalyser.filter_objfm_cycles — internal mode
# ---------------------------------------------------------------------------


class TestFilterObjFMCyclesInternal:
    def test_drops_paired_occ_rep_with_suffix(self):
        seq = _seq(
            _ev("fm", "occ__cc_1"),
            _ev("fm", "rep__cc_1"),
            _ev("top", "occ"),
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objfm_cycles(objfm_internal=["fm"], inplace=False)
        assert len(result.sequences) == 1
        assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
            ("top", "occ")
        ]

    def test_drops_paired_occ_rep_without_suffix_single_target(self):
        """Single-target ObjFM emits ``fm.occ`` / ``fm.rep`` (no suffix).
        The default ``\\S*`` capture must still match."""
        seq = _seq(
            _ev("fm", "occ"),
            _ev("fm", "rep"),
            _ev("top", "occ"),
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objfm_cycles(objfm_internal=["fm"], inplace=False)
        assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
            ("top", "occ")
        ]

    def test_suffix_must_match_between_occ_and_rep(self):
        """``occ__cc_1`` must NOT be paired with ``rep__cc_2``."""
        seq = _seq(
            _ev("fm", "occ__cc_1"),
            _ev("fm", "rep__cc_2"),  # different suffix — should NOT pair
            _ev("top", "occ"),
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objfm_cycles(objfm_internal=["fm"], inplace=False)
        # Neither pair has been removed.
        assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
            ("fm", "occ__cc_1"),
            ("fm", "rep__cc_2"),
            ("top", "occ"),
        ]

    def test_unrepaired_occ_is_kept(self):
        """A failure that is not followed by its mirror repair stays in
        the trace (it contributed to reaching the top event)."""
        seq = _seq(
            _ev("fm", "occ__cc_1"),
            _ev("fm", "rep__cc_1"),
            _ev("fm", "occ__cc_2"),  # unrepaired
            _ev("top", "occ"),
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objfm_cycles(objfm_internal=["fm"], inplace=False)
        assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
            ("fm", "occ__cc_2"),
            ("top", "occ"),
        ]

    def test_restores_symmetry_on_mirror_pairs(self):
        """The canonical bug repro: two mirror traces have weight 1 each,
        but the longer trace ``cc_1 → rep_cc_1 → cc_2 → rep_cc_2 → top``
        is sub-sequence-compatible with both. After filtering, only the
        relevant cc remains and the post-grouping count is unbiased."""
        s_ab = _seq(
            _ev("fm", "occ__cc_1"),
            _ev("fm", "occ__cc_2"),
            _ev("top", "occ"),
        )
        s_ba = _seq(
            _ev("fm", "occ__cc_2"),
            _ev("fm", "occ__cc_1"),
            _ev("top", "occ"),
        )
        # Mirror trace: each component fails, repairs, then both fail
        # again. After filtering the occ_cc_1/rep_cc_1 pair and the
        # occ_cc_2/rep_cc_2 pair collapse, leaving cc_1 → cc_2 → top.
        s_long_ab = _seq(
            _ev("fm", "occ__cc_1"),
            _ev("fm", "rep__cc_1"),
            _ev("fm", "occ__cc_2"),
            _ev("fm", "rep__cc_2"),
            _ev("fm", "occ__cc_1"),
            _ev("fm", "occ__cc_2"),
            _ev("top", "occ"),
        )
        analyser = SequenceAnalyser(sequences=[s_ab, s_ba, s_long_ab])
        result = analyser.filter_objfm_cycles(objfm_internal=["fm"], inplace=False)

        # After filter+group, s_ab and s_long_ab collapse onto the same
        # signature (cc_1 → cc_2 → top), and s_ba stays distinct.
        sig_ab = (("fm", "occ__cc_1"), ("fm", "occ__cc_2"), ("top", "occ"))
        sig_ba = (("fm", "occ__cc_2"), ("fm", "occ__cc_1"), ("top", "occ"))
        sigs = {tuple((e.obj, e.attr) for e in s.events): s.weight
                for s in result.sequences}
        assert sigs[sig_ab] == 2  # s_ab + s_long_ab
        assert sigs[sig_ba] == 1  # s_ba alone


# ---------------------------------------------------------------------------
# SequenceAnalyser.filter_objfm_cycles — external mode
# ---------------------------------------------------------------------------


class TestFilterObjFMCyclesExternal:
    """In external mode the target automaton's states/transitions are
    name-prefixed with the ObjFM name (post-fix of the multi-ObjFM
    collision). So target events appear as ``c1.fm__occ`` / ``c1.fm__rep``,
    not as bare ``c1.occ`` / ``c1.rep``. The filter therefore does not
    need the list of targets — the prefix is enough to identify the
    target events belonging to a given ObjFM."""

    def test_drops_objfm_events_and_filters_prefixed_target_pairs(self):
        seq = _seq(
            _ev("fm", "occ__cc_1"),
            _ev("c1", "fm__occ"),     # target picks up the failure (prefixed)
            _ev("c1", "fm__rep"),     # target repaired (prefixed)
            _ev("fm", "rep__cc_1"),
            _ev("fm", "occ__cc_1_2"),
            _ev("c1", "fm__occ"),     # both targets fail (unrepaired)
            _ev("c2", "fm__occ"),
            _ev("top", "occ"),
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objfm_cycles(
            objfm_external=["fm"], inplace=False
        )
        assert len(result.sequences) == 1
        # After: all ``fm.*`` events dropped, c1.fm__occ/c1.fm__rep pair
        # dropped, c1.fm__occ + c2.fm__occ (unrepaired) + top.occ remain.
        assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
            ("c1", "fm__occ"),
            ("c2", "fm__occ"),
            ("top", "occ"),
        ]

    def test_objfm_external_with_no_target_pairs(self):
        """External-mode ObjFM where targets only fail without repair."""
        seq = _seq(
            _ev("fm", "occ__cc_1_2"),
            _ev("c1", "fm__occ"),
            _ev("c2", "fm__occ"),
            _ev("top", "occ"),
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objfm_cycles(
            objfm_external=["fm"], inplace=False
        )
        assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
            ("c1", "fm__occ"),
            ("c2", "fm__occ"),
            ("top", "occ"),
        ]

    def test_objfm_external_two_objfm_disambiguated(self):
        """The post-fix naming allows two ObjFM external on the same
        target. The filter discriminates by ObjFM name even when the
        same target carries both."""
        seq = _seq(
            _ev("fm_a", "occ"),
            _ev("c1", "fm_a__occ"),
            _ev("c1", "fm_a__rep"),   # fm_a cycle on c1 → drop
            _ev("fm_a", "rep"),
            _ev("fm_b", "occ"),
            _ev("c1", "fm_b__occ"),   # fm_b active, kept
            _ev("top", "occ"),
        )
        analyser = SequenceAnalyser(sequences=[seq])
        # Apply filter_objfm_cycles for both ObjFM.
        result = analyser.filter_objfm_cycles(
            objfm_external=["fm_a", "fm_b"], inplace=False
        )
        # fm_a events removed; fm_a's c1 cycle removed; fm_b events
        # removed; fm_b's c1.fm_b__occ unrepaired → kept; top.occ kept.
        assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
            ("c1", "fm_b__occ"),
            ("top", "occ"),
        ]


# ---------------------------------------------------------------------------
# SequenceAnalyser.filter_objfm_cycles — customisation
# ---------------------------------------------------------------------------


class TestFilterObjFMCyclesCustomisation:
    def test_custom_failure_state_name(self):
        """User overrides ``failure_state="ko"`` on their ObjFM."""
        seq = _seq(
            _ev("fm", "ko__cc_1"),
            _ev("fm", "rep__cc_1"),
            _ev("top", "occ"),
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objfm_cycles(
            objfm_internal=["fm"], failure_state="ko", inplace=False
        )
        assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
            ("top", "occ")
        ]

    def test_custom_repair_state_name(self):
        seq = _seq(
            _ev("fm", "occ__cc_1"),
            _ev("fm", "ok__cc_1"),
            _ev("top", "occ"),
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objfm_cycles(
            objfm_internal=["fm"], repair_state="ok", inplace=False
        )
        assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
            ("top", "occ")
        ]

    def test_objfm_name_with_regex_special_chars(self):
        """An ObjFM whose name contains regex metacharacters (``.``, ``$``,
        ``+``) must be matched as a literal, not as a pattern."""
        seq = _seq(
            _ev("fm.v2$x+", "occ__cc_1"),
            _ev("fm.v2$x+", "rep__cc_1"),
            _ev("top", "occ"),
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objfm_cycles(
            objfm_internal=["fm.v2$x+"], inplace=False
        )
        assert [(e.obj, e.attr) for e in result.sequences[0].events] == [
            ("top", "occ")
        ]

    def test_empty_objfm_lists_is_noop_then_regroups(self):
        s1 = _seq(_ev("c1", "occ"))
        s2 = _seq(_ev("c1", "occ"))
        analyser = SequenceAnalyser(sequences=[s1, s2])
        result = analyser.filter_objfm_cycles(inplace=False)
        # No filter applied — but group_sequences still runs.
        assert len(result.sequences) == 1
        assert result.sequences[0].weight == 2

    def test_inplace_mutates_self(self):
        s1 = _seq(_ev("fm", "occ__cc_1"), _ev("fm", "rep__cc_1"), _ev("top", "occ"))
        analyser = SequenceAnalyser(sequences=[s1])
        returned = analyser.filter_objfm_cycles(objfm_internal=["fm"], inplace=True)
        assert returned is analyser
        assert [(e.obj, e.attr) for e in analyser.sequences[0].events] == [
            ("top", "occ")
        ]

    def test_zero_event_sequences_are_kept(self):
        """A trajectory that only contained occ/rep cycles (no top event)
        becomes a 0-event sequence after filtering. These represent the
        ``no top event`` outcome and MUST be preserved (they carry the
        probability of safe operation)."""
        seq = _seq(
            _ev("fm", "occ__cc_1"),
            _ev("fm", "rep__cc_1"),
            target=None,  # trajectory ended without reaching top event
            weight=42,
        )
        analyser = SequenceAnalyser(sequences=[seq])
        result = analyser.filter_objfm_cycles(objfm_internal=["fm"], inplace=False)
        assert len(result.sequences) == 1
        assert result.sequences[0].events == []
        assert result.sequences[0].weight == 42
        assert result.sequences[0].target_name is None
