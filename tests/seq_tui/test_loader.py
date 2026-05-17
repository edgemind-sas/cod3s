"""Tests for ``cod3s.pycatshoo.seq_tui.loader``.

Pure-Python tests (no PyCATSHOO needed). XML inputs are crafted as
strings written to ``tmp_path`` and JSON inputs are built directly
from cod3s ``SequenceAnalyser`` objects (or hand-crafted dicts where
the envelope shape needs probing).
"""

from __future__ import annotations

import json

import pytest

from cod3s.pycatshoo.seq_tui.loader import (
    SequenceLoadError,
    detect_format,
    load_sequences_from_json_cod3s,
    load_sequences_from_xml,
)
from cod3s.pycatshoo.sequence import (
    SEQUENCE_ARTIFACT_SCHEMA_VERSION,
    SeqEvent,
    Sequence,
    SequenceAnalyser,
    serialise_analyser,
)


# ---------------------------------------------------------------------------
# detect_format
# ---------------------------------------------------------------------------


class TestDetectFormat:
    def test_xml_extension(self, tmp_path):
        p = tmp_path / "x.xml"
        p.write_text("<root/>")
        assert detect_format(p) == "xml"

    def test_json_cod3s_envelope_detected(self, tmp_path):
        p = tmp_path / "x.json"
        p.write_text(
            json.dumps({"schema_version": "1.0.0", "sequences": []})
        )
        assert detect_format(p) == "json-cod3s"

    def test_json_without_envelope_rejected(self, tmp_path):
        """A non-cod3s JSON file must NOT be silently accepted."""
        p = tmp_path / "x.json"
        p.write_text('{"some": "other", "shape": true}')
        with pytest.raises(SequenceLoadError, match="missing the cod3s envelope"):
            detect_format(p)

    def test_unknown_extension_rejected(self, tmp_path):
        p = tmp_path / "x.txt"
        p.write_text("whatever")
        with pytest.raises(SequenceLoadError, match="cannot detect format"):
            detect_format(p)

    def test_missing_file(self, tmp_path):
        with pytest.raises(SequenceLoadError, match="not found"):
            detect_format(tmp_path / "nope.xml")


# ---------------------------------------------------------------------------
# XML loader
# ---------------------------------------------------------------------------


def _xml_with_sequences(*seqs_xml: str) -> str:
    """Wrap a list of <SEQ>...</SEQ> snippets in a minimal envelope."""
    return f"<PY_RES>{''.join(seqs_xml)}</PY_RES>"


class TestLoadXml:
    def test_load_empty(self, tmp_path):
        p = tmp_path / "empty.xml"
        p.write_text(_xml_with_sequences())
        assert load_sequences_from_xml(p) == []

    def test_load_single_sequence(self, tmp_path):
        xml = _xml_with_sequences(
            '<SEQ C="top_event">'
            '  <BR T="10.0"><TR NAME="comp.occ"/></BR>'
            '  <BR T="20.0"><TR NAME="top.occ"/></BR>'
            "</SEQ>"
        )
        p = tmp_path / "one.xml"
        p.write_text(xml)
        result = load_sequences_from_xml(p)
        assert len(result) == 1
        seq = result[0]
        assert seq.target_name == "top_event"
        assert seq.weight == 1
        assert [(e.obj, e.attr, e.time) for e in seq.events] == [
            ("comp", "occ", 10.0),
            ("top", "occ", 20.0),
        ]

    def test_load_seq_without_C_attribute_defaults_to_Normal(self, tmp_path):
        xml = _xml_with_sequences(
            '<SEQ><BR T="5"><TR NAME="x.y"/></BR></SEQ>'
        )
        p = tmp_path / "no_c.xml"
        p.write_text(xml)
        result = load_sequences_from_xml(p)
        assert result[0].target_name == "Normal"

    def test_load_unparseable_time_defaults_to_zero(self, tmp_path):
        xml = _xml_with_sequences(
            '<SEQ C="t"><BR T="not-a-number"><TR NAME="x.y"/></BR></SEQ>'
        )
        p = tmp_path / "bad_time.xml"
        p.write_text(xml)
        result = load_sequences_from_xml(p)
        assert result[0].events[0].time == 0.0

    def test_load_name_without_dot_splits_to_attr_only(self, tmp_path):
        """``NAME="bare"`` becomes obj="bare" attr="bare" (fallback)."""
        xml = _xml_with_sequences(
            '<SEQ C="t"><BR T="0"><TR NAME="bare"/></BR></SEQ>'
        )
        p = tmp_path / "bare.xml"
        p.write_text(xml)
        result = load_sequences_from_xml(p)
        ev = result[0].events[0]
        assert ev.obj == "bare"
        assert ev.attr == "bare"

    def test_max_sequences_caps(self, tmp_path):
        xml = _xml_with_sequences(
            *[
                f'<SEQ C="t{i}"><BR T="0"><TR NAME="a.b"/></BR></SEQ>'
                for i in range(10)
            ]
        )
        p = tmp_path / "many.xml"
        p.write_text(xml)
        result = load_sequences_from_xml(p, max_sequences=3)
        assert len(result) == 3
        assert [s.target_name for s in result] == ["t0", "t1", "t2"]

    def test_load_malformed_xml_raises(self, tmp_path):
        p = tmp_path / "bad.xml"
        p.write_text("<not-closed")
        with pytest.raises(SequenceLoadError, match="malformed XML"):
            load_sequences_from_xml(p)

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(SequenceLoadError, match="not found"):
            load_sequences_from_xml(tmp_path / "nope.xml")


# ---------------------------------------------------------------------------
# JSON cod3s loader
# ---------------------------------------------------------------------------


def _make_analyser(*seq_specs):
    """Build a SequenceAnalyser from tuples ``(target, weight, [(obj, attr, time)])``."""
    sequences = []
    for target, weight, events in seq_specs:
        sequences.append(
            Sequence(
                probability=None,
                weight=weight,
                end_time=None,
                target_name=target,
                events=[
                    SeqEvent(obj=o, attr=a, time=t, type=None)
                    for (o, a, t) in events
                ],
            )
        )
    return SequenceAnalyser(sequences=sequences)


class TestLoadJsonCod3s:
    def test_round_trip(self, tmp_path):
        """Serialise → write → reload yields equivalent sequences."""
        analyser = _make_analyser(
            ("top", 3, [("a", "occ", 1.0), ("b", "occ", 2.0)]),
            ("top", 1, [("c", "occ", 5.0)]),
        )
        p = tmp_path / "dump.json"
        p.write_text(serialise_analyser(analyser))

        result = load_sequences_from_json_cod3s(p)
        assert len(result) == 2
        # weights preserved
        assert [s.weight for s in result] == [3, 1]
        # signatures preserved
        assert [(e.obj, e.attr, e.time) for e in result[0].events] == [
            ("a", "occ", 1.0),
            ("b", "occ", 2.0),
        ]

    def test_missing_envelope_field_raises(self, tmp_path):
        p = tmp_path / "no_schema.json"
        p.write_text(json.dumps({"sequences": []}))
        with pytest.raises(SequenceLoadError, match="schema_version"):
            load_sequences_from_json_cod3s(p)

    def test_missing_sequences_array_raises(self, tmp_path):
        p = tmp_path / "no_seqs.json"
        p.write_text(json.dumps({"schema_version": "1.0.0"}))
        with pytest.raises(SequenceLoadError, match="sequences"):
            load_sequences_from_json_cod3s(p)

    def test_sequences_not_a_list_raises(self, tmp_path):
        p = tmp_path / "wrong_type.json"
        p.write_text(json.dumps({"schema_version": "1.0.0", "sequences": "oops"}))
        with pytest.raises(SequenceLoadError, match="must be an array"):
            load_sequences_from_json_cod3s(p)

    def test_top_level_not_object_raises(self, tmp_path):
        p = tmp_path / "scalar.json"
        p.write_text("[1, 2, 3]")
        with pytest.raises(SequenceLoadError, match="must be an object"):
            load_sequences_from_json_cod3s(p)

    def test_malformed_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json")
        with pytest.raises(SequenceLoadError, match="malformed JSON"):
            load_sequences_from_json_cod3s(p)

    def test_unknown_schema_version_loose_mode_accepts(self, tmp_path):
        """Default ``strict_schema=False`` should NOT raise on a future
        schema version — let the user opt in to strict mode."""
        p = tmp_path / "future.json"
        p.write_text(
            json.dumps({"schema_version": "99.0.0", "sequences": []})
        )
        assert load_sequences_from_json_cod3s(p) == []

    def test_unknown_schema_version_strict_mode_raises(self, tmp_path):
        p = tmp_path / "future.json"
        p.write_text(
            json.dumps({"schema_version": "99.0.0", "sequences": []})
        )
        with pytest.raises(SequenceLoadError, match="schema_version mismatch"):
            load_sequences_from_json_cod3s(p, strict_schema=True)

    def test_invalid_sequence_entry_raises_with_index(self, tmp_path):
        """A bogus sequence dict must surface the index in the error
        message so the user can find the offending entry."""
        p = tmp_path / "bad_seq.json"
        p.write_text(
            json.dumps(
                {
                    "schema_version": SEQUENCE_ARTIFACT_SCHEMA_VERSION,
                    "sequences": [
                        # Valid first
                        {"weight": 1, "events": [], "target_name": "t"},
                        # Then invalid (events must be a list of dicts)
                        {"weight": "not-an-int", "events": "nope", "target_name": "t"},
                    ],
                }
            )
        )
        with pytest.raises(SequenceLoadError, match=r"sequences\[1\]"):
            load_sequences_from_json_cod3s(p)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(SequenceLoadError, match="not found"):
            load_sequences_from_json_cod3s(tmp_path / "nope.json")
