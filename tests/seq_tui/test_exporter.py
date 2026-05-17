"""Tests for ``cod3s.pycatshoo.seq_tui.exporter``."""

from __future__ import annotations

import csv

from cod3s.pycatshoo.seq_tui.exporter import (
    export_csv,
    export_json_cod3s,
    export_markdown,
)
from cod3s.pycatshoo.seq_tui.loader import load_sequences_from_json_cod3s
from cod3s.pycatshoo.sequence import SeqEvent, Sequence, SequenceAnalyser


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_analyser(*seq_specs):
    """``[(target, weight, [(obj, attr, time)])]`` → SequenceAnalyser."""
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
    a = SequenceAnalyser(sequences=sequences)
    a.update_probs()
    return a


# ---------------------------------------------------------------------------
# JSON cod3s — round-trip via the loader
# ---------------------------------------------------------------------------


class TestExportJsonCod3s:
    def test_round_trip(self, tmp_path):
        analyser = _make_analyser(
            ("top", 3, [("a", "occ", 1.0), ("top", "occ", 2.0)]),
            ("top", 1, [("b", "occ", 5.0), ("top", "occ", 6.0)]),
        )
        p = tmp_path / "out.json"
        export_json_cod3s(analyser, p)

        reloaded = load_sequences_from_json_cod3s(p)
        assert [(s.weight, s.target_name) for s in reloaded] == [
            (3, "top"),
            (1, "top"),
        ]
        assert [(e.obj, e.attr) for e in reloaded[0].events] == [
            ("a", "occ"),
            ("top", "occ"),
        ]

    def test_writes_canonical_envelope(self, tmp_path):
        """File must start with ``{"schema_version":...,"target_group_id":...``"""
        analyser = _make_analyser(("top", 1, [("a", "occ", 1.0)]))
        p = tmp_path / "out.json"
        export_json_cod3s(analyser, p)
        text = p.read_text(encoding="utf-8")
        assert text.startswith('{"schema_version":')
        assert '"sequences":' in text


# ---------------------------------------------------------------------------
# CSV — one row per event
# ---------------------------------------------------------------------------


class TestExportCsv:
    def test_one_row_per_event(self, tmp_path):
        analyser = _make_analyser(
            ("top", 5, [("a", "occ", 1.0), ("b", "occ", 2.0)]),
            ("top", 3, [("c", "occ", 5.0)]),
        )
        p = tmp_path / "out.csv"
        export_csv(analyser, p)
        with p.open() as fp:
            rows = list(csv.DictReader(fp))
        # 2 events + 1 event = 3 rows
        assert len(rows) == 3

    def test_csv_columns_include_event_fields(self, tmp_path):
        analyser = _make_analyser(("top", 1, [("a", "occ", 1.0)]))
        p = tmp_path / "out.csv"
        export_csv(analyser, p)
        with p.open() as fp:
            header = next(csv.reader(fp))
        # Whatever ``to_df_long`` exposes, at minimum these must appear:
        for required in ("event_obj", "event_attr", "event_time"):
            assert required in header, f"missing {required!r} in {header}"


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


class TestExportMarkdown:
    def test_writes_header_and_top_table(self, tmp_path):
        analyser = _make_analyser(
            ("top", 5, [("a", "occ", 1.0), ("top", "occ", 2.0)]),
            ("top", 3, [("b", "occ", 5.0)]),
        )
        p = tmp_path / "out.md"
        export_markdown(analyser, p)
        text = p.read_text(encoding="utf-8")
        assert text.startswith("# Sequence analysis")
        # Top table headers
        assert "| # | weight | probability | target | events |" in text
        # Both sequences appear in the top table, sorted by weight desc
        idx_top1 = text.find("| 1 | 5 |")
        idx_top2 = text.find("| 2 | 3 |")
        assert 0 < idx_top1 < idx_top2

    def test_detail_section_per_sequence(self, tmp_path):
        analyser = _make_analyser(
            ("top", 5, [("a", "occ", 1.0)]),
            ("top", 3, [("b", "occ", 5.0)]),
        )
        p = tmp_path / "out.md"
        export_markdown(analyser, p)
        text = p.read_text(encoding="utf-8")
        assert "## Sequence #1" in text
        assert "## Sequence #2" in text

    def test_empty_sequence_marked(self, tmp_path):
        """A 0-event sequence (no top event reached) must render
        clearly in the detail section."""
        analyser = _make_analyser(("top", 7, []))
        p = tmp_path / "out.md"
        export_markdown(analyser, p)
        text = p.read_text(encoding="utf-8")
        assert "_(empty sequence — top event not reached)_" in text

    def test_signature_arrow_separated_in_top_table(self, tmp_path):
        analyser = _make_analyser(("top", 1, [("a", "occ", 1.0), ("b", "rep", 2.0)]))
        p = tmp_path / "out.md"
        export_markdown(analyser, p)
        text = p.read_text(encoding="utf-8")
        assert "a.occ → b.rep" in text
