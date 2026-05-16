"""Tests for ``_persist_sequence_analysis_artifacts`` + ``_serialise_analyser``.

Uses mock systems / mock analysers to avoid loading PyCATSHOO. The
canonical pipeline (group → filter_objfm_cycles → compute_minimal_sequences)
is exercised through ``SequenceAnalyser`` itself (which IS loaded — we
mock only the ``from_pyc_system`` factory + the ``system`` input).
"""

from __future__ import annotations

import json
import sys
import types
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cod3s.scripts.study_runner import (
    SEQUENCE_ARTIFACT_SCHEMA_VERSION,
    SequenceAnalysisError,
    _persist_sequence_analysis_artifacts,
    _serialise_analyser,
)
from cod3s.specs.study_yaml import StudyYaml, TargetSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _study_with_target() -> StudyYaml:
    """Minimal StudyYaml with one target (so the helper doesn't no-op)."""
    return StudyYaml(
        name="ccf-asymmetry-mock",
        targets=[TargetSpec(name="system_down")],
        events=[],
        indicators=[],
        failure_modes=[],
    )


def _study_no_target() -> StudyYaml:
    return StudyYaml(name="no-target", targets=[])


def _make_mock_analyser(sequence_count: int = 3):
    """Build a MagicMock with the attributes the helper accesses.

    Each ``sequences`` entry has a ``model_dump(mode, exclude_none)``
    method that returns a stable dict so the serialised JSON is
    deterministic.
    """
    mock_seqs = []
    for i in range(sequence_count):
        s = MagicMock()
        s.model_dump.return_value = {
            "weight": 10 + i,
            "probability": 0.1 * (i + 1),
            "end_time": 1000.0 * (i + 1),
            "target_name": "system_down",
            "events": [{"obj": f"comp_{i}", "attr": "occ", "time": 100.0, "type": "occ"}],
        }
        mock_seqs.append(s)

    analyser = MagicMock()
    analyser.sequences = mock_seqs
    # Pipeline methods return the analyser (chainable, as cod3s does).
    analyser.group_sequences.return_value = analyser
    analyser.filter_objfm_cycles.return_value = analyser
    # compute_minimal_sequences with inplace=False returns a *new* mock
    # (the helper expects this so the all-snapshot stays untouched).
    minimal = MagicMock()
    minimal.sequences = mock_seqs[:1]  # only the top after minimal
    analyser.compute_minimal_sequences.return_value = minimal
    return analyser, minimal


@pytest.fixture
def fake_sequence_analyser(monkeypatch):
    """Inject a fake SequenceAnalyser whose from_pyc_system returns the
    pre-built mock analyser.

    The fixture exposes (factory, all_analyser, minimal_analyser) so
    individual tests can assert what was passed to the constructor and
    what was serialised.
    """
    all_analyser, minimal_analyser = _make_mock_analyser(sequence_count=3)
    factory_calls = []

    fake_module = types.ModuleType("cod3s.pycatshoo.sequence")

    class FakeSequenceAnalyser:
        @classmethod
        def from_pyc_system(cls, system, **_kw):
            factory_calls.append(system)
            return all_analyser

    fake_module.SequenceAnalyser = FakeSequenceAnalyser
    monkeypatch.setitem(sys.modules, "cod3s.pycatshoo.sequence", fake_module)

    return {
        "factory_calls": factory_calls,
        "all": all_analyser,
        "minimal": minimal_analyser,
    }


# ---------------------------------------------------------------------------
# A1 — files written when target present + sim succeeded
# ---------------------------------------------------------------------------


class TestA1FilesWritten:
    def test_writes_both_artifacts(self, tmp_path, fake_sequence_analyser):
        system = MagicMock()
        study = _study_with_target()
        _persist_sequence_analysis_artifacts(system, study, tmp_path, logger=None)

        assert (tmp_path / "sequences_all.json").exists()
        assert (tmp_path / "sequences_minimal.json").exists()
        # Factory was called once with the system instance.
        assert fake_sequence_analyser["factory_calls"] == [system]

    def test_pipeline_order(self, tmp_path, fake_sequence_analyser):
        """group → filter_objfm_cycles → write all → compute_minimal (inplace=False) → write minimal."""
        system = MagicMock()
        study = _study_with_target()
        _persist_sequence_analysis_artifacts(system, study, tmp_path, logger=None)

        all_ana = fake_sequence_analyser["all"]
        # The all-snapshot pipeline:
        all_ana.group_sequences.assert_called_once_with(inplace=True)
        all_ana.filter_objfm_cycles.assert_called_once_with(inplace=True)
        # Then minimal as a separate analyser:
        all_ana.compute_minimal_sequences.assert_called_once_with(inplace=False)


# ---------------------------------------------------------------------------
# A2 — no-op when targets=[]
# ---------------------------------------------------------------------------


class TestA2NoOp:
    def test_no_target_skips_silently(self, tmp_path, fake_sequence_analyser):
        system = MagicMock()
        study = _study_no_target()
        _persist_sequence_analysis_artifacts(system, study, tmp_path, logger=None)

        assert not (tmp_path / "sequences_all.json").exists()
        assert not (tmp_path / "sequences_minimal.json").exists()
        # Factory was NOT called.
        assert fake_sequence_analyser["factory_calls"] == []

    def test_no_target_no_warning(self, tmp_path, fake_sequence_analyser):
        """The skip should be silent — no warning loggued."""
        logger = MagicMock()
        study = _study_no_target()
        _persist_sequence_analysis_artifacts(MagicMock(), study, tmp_path, logger=logger)
        logger.warning.assert_not_called()


# ---------------------------------------------------------------------------
# A3 — fail-open + warning loggué + log truncated (security F3)
# ---------------------------------------------------------------------------


class TestA3FailOpen:
    def test_value_error_logs_warning_skips_artifacts(self, tmp_path, monkeypatch):
        """from_pyc_system raises ValueError → warn + skip, no crash."""
        fake_module = types.ModuleType("cod3s.pycatshoo.sequence")

        class BoomAnalyser:
            @classmethod
            def from_pyc_system(cls, system, **_kw):
                raise ValueError("synthetic boom — should not leak into log payload")

        fake_module.SequenceAnalyser = BoomAnalyser
        monkeypatch.setitem(sys.modules, "cod3s.pycatshoo.sequence", fake_module)

        logger = MagicMock()
        warnings: list[str] = []
        logger.warning = lambda msg: warnings.append(msg)

        _persist_sequence_analysis_artifacts(MagicMock(), _study_with_target(), tmp_path, logger=logger)

        assert not (tmp_path / "sequences_all.json").exists()
        assert not (tmp_path / "sequences_minimal.json").exists()
        # Exactly one warning logged.
        assert len(warnings) == 1
        # Log contains the exception type name (for ops triage)…
        assert "ValueError" in warnings[0]
        # …and is truncated (no >200 char payload leak).
        assert len(warnings[0]) < 500

    def test_log_truncates_long_exception_message(self, tmp_path, monkeypatch):
        """Long exception messages should be truncated to repr[:200]."""
        fake_module = types.ModuleType("cod3s.pycatshoo.sequence")
        long_payload = "X" * 5000

        class BigBoom:
            @classmethod
            def from_pyc_system(cls, system, **_kw):
                raise ValueError(long_payload)

        fake_module.SequenceAnalyser = BigBoom
        monkeypatch.setitem(sys.modules, "cod3s.pycatshoo.sequence", fake_module)

        warnings: list[str] = []
        logger = MagicMock()
        logger.warning = lambda msg: warnings.append(msg)

        _persist_sequence_analysis_artifacts(MagicMock(), _study_with_target(), tmp_path, logger=logger)

        # The full 5000-char payload must NOT be in the log.
        assert long_payload not in warnings[0]
        # And the warning itself stays under a sane bound.
        assert len(warnings[0]) < 500


# ---------------------------------------------------------------------------
# A4 — JSON schema round-trip against a golden fixture (no platform import)
# ---------------------------------------------------------------------------


class TestA4SchemaGolden:
    """We do NOT import the platform's Pydantic schema (that would
    create a forbidden cycle platform → cod3s ← platform). Instead we
    assert the JSON shape against a stable contract documented here."""

    def test_schema_envelope_matches_v1_contract(self, tmp_path, fake_sequence_analyser):
        _persist_sequence_analysis_artifacts(
            MagicMock(), _study_with_target(), tmp_path, logger=None
        )

        payload = json.loads((tmp_path / "sequences_minimal.json").read_text())

        # Top-level envelope keys, ordered for diff stability.
        assert set(payload.keys()) == {
            "schema_version",
            "target_group_id",
            "sequences",
            "meta",
        }
        assert payload["schema_version"] == SEQUENCE_ARTIFACT_SCHEMA_VERSION == "1.0.0"
        assert payload["target_group_id"] is None  # platform sets it on read
        assert payload["meta"] == {"truncated_at": None, "parse_error": None}
        assert isinstance(payload["sequences"], list)
        assert len(payload["sequences"]) >= 1
        # Each sequence carries the canonical fields.
        seq0 = payload["sequences"][0]
        assert set(seq0.keys()) >= {"weight", "probability", "events", "target_name"}

    def test_all_and_minimal_differ_in_sequence_count(self, tmp_path, fake_sequence_analyser):
        """sequences_all keeps the post-filter set ; sequences_minimal
        the after-minimal subset. The mock makes all=3, minimal=1."""
        _persist_sequence_analysis_artifacts(
            MagicMock(), _study_with_target(), tmp_path, logger=None
        )
        all_payload = json.loads((tmp_path / "sequences_all.json").read_text())
        min_payload = json.loads((tmp_path / "sequences_minimal.json").read_text())
        assert len(all_payload["sequences"]) == 3
        assert len(min_payload["sequences"]) == 1


# ---------------------------------------------------------------------------
# A6 — perf budget: structured perf log emitted
# ---------------------------------------------------------------------------


class TestA6PerfBudget:
    def test_perf_log_emitted(self, tmp_path, fake_sequence_analyser):
        """info2 must contain the structured perf marker so ops can grep."""
        logger = MagicMock()
        info_msgs: list[str] = []
        logger.info2 = lambda msg: info_msgs.append(msg)
        _persist_sequence_analysis_artifacts(
            MagicMock(), _study_with_target(), tmp_path, logger=logger
        )
        # Expect one info2 line with timings + sizes.
        perf = [m for m in info_msgs if "sequence_analysis perf" in m]
        assert len(perf) == 1
        assert "from_pyc_system=" in perf[0]
        assert "pipeline=" in perf[0]
        assert "all_size=" in perf[0]
        assert "min_size=" in perf[0]


# ---------------------------------------------------------------------------
# Bonus — _serialise_analyser unit tests (pure function, no IO)
# ---------------------------------------------------------------------------


class TestSerialiseAnalyser:
    def test_returns_compact_json_string(self):
        analyser, _ = _make_mock_analyser(sequence_count=2)
        s = _serialise_analyser(analyser)
        assert isinstance(s, str)
        # Compact (no whitespace): `,` separator without space.
        assert ", " not in s
        # Valid JSON.
        json.loads(s)

    def test_envelope_contains_constant_version(self):
        analyser, _ = _make_mock_analyser(sequence_count=0)
        payload = json.loads(_serialise_analyser(analyser))
        assert payload["schema_version"] == SEQUENCE_ARTIFACT_SCHEMA_VERSION

    def test_empty_sequence_list_serialises(self):
        analyser, _ = _make_mock_analyser(sequence_count=0)
        payload = json.loads(_serialise_analyser(analyser))
        assert payload["sequences"] == []


# ---------------------------------------------------------------------------
# Marker for SequenceAnalysisError import (currently unused in code, kept as future hook)
# ---------------------------------------------------------------------------


def test_sequence_analysis_error_is_exception_class():
    assert issubclass(SequenceAnalysisError, Exception)
