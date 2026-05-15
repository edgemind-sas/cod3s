"""Tests for the Tier 1 sequence filtering helpers.

Pure-function tests on ``_clamp_top_pct`` (no PyCATSHOO needed) plus
mock-based tests on ``_apply_sequence_filtering`` (PyCATSHOO behaviour
is not exercised — we verify that the helper reads the config correctly,
fails open on errors, and writes the metrics file when counters are
exposed by the analyser).

Refs:
- Plan : ``cod3s-platform/docs/plans/2026-05-15-feat-modelling-sequences-pycatshoo-tier1-plan.md``
- Bench : ``cod3s-platform/docs/solutions/architecture-patterns/2026-05-13-pycatshoo-vs-cod3s-sequence-perf.md``
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cod3s.scripts.study_runner import _apply_sequence_filtering, _clamp_top_pct
from cod3s.specs.study_yaml import SimulationConfig, StudyYaml


# ---------------------------------------------------------------------------
# B1 — _clamp_top_pct unit tests (pure function, no PyCATSHOO)
# ---------------------------------------------------------------------------


class TestClampTopPct:
    def test_b1_none_returns_100(self):
        """None / missing → 100 (no filtering)."""
        assert _clamp_top_pct(None) == 100

    def test_b1_below_one_clamps_to_one(self):
        """0.5 → 1 (PyCATSHOO printFilteredSeq accepts ≥ 1)."""
        assert _clamp_top_pct(0.5) == 1

    def test_b1_in_range_rounded(self):
        assert _clamp_top_pct(50) == 50
        assert _clamp_top_pct(50.7) == 51
        assert _clamp_top_pct(50.4) == 50

    def test_b1_above_100_clamps_to_100(self):
        assert _clamp_top_pct(150) == 100
        assert _clamp_top_pct(101) == 100

    def test_b1_negative_clamps_to_one(self):
        assert _clamp_top_pct(-3) == 1
        assert _clamp_top_pct(-100) == 1

    def test_b1_string_numeric_accepted(self):
        """``float()`` accepts numeric strings — useful when YAML loaders
        deserialize percent as a string."""
        assert _clamp_top_pct("25") == 25

    def test_b1_invalid_string_returns_100(self):
        """Non-numeric string → falls back to 100 (fail-open default)."""
        assert _clamp_top_pct("not-a-number") == 100

    def test_b1_zero_clamps_to_one(self):
        assert _clamp_top_pct(0) == 1


# ---------------------------------------------------------------------------
# B2-B4 — _apply_sequence_filtering with mocked PyCATSHOO
# ---------------------------------------------------------------------------


def _study_with_filtering(filtering_dict: dict | None) -> StudyYaml:
    """Build a minimal StudyYaml with optional sequence_filtering carried
    through the SimulationConfig extras (extra="allow" pattern)."""
    sim_payload: dict = {"nb_runs": 100, "schedule": []}
    if filtering_dict is not None:
        sim_payload["sequence_filtering"] = filtering_dict
    return StudyYaml(name="bench", simulation=SimulationConfig(**sim_payload))


@pytest.fixture
def fake_pyc_module(monkeypatch):
    """Inject a fake ``Pycatshoo`` module into sys.modules so the helper's
    ``import Pycatshoo as Pyc`` resolves without the native lib being
    available in the test environment."""
    fake = types.ModuleType("Pycatshoo")

    class FakeIFilterFct:
        @staticmethod
        def newConditionFilter(variable_path, time, op, val):
            # Capture args for later assertions on the analyser mock.
            return ("FilterFct", variable_path, float(time), op, float(val))

    class FakeCAnalyser:
        instances: list = []

        def __init__(self, system):
            self.system = system
            self.kept = False
            self.filter = None
            self.printed = None
            self.totals = (200, 50)
            FakeCAnalyser.instances.append(self)

        def keepFilteredSeq(self, flag):
            self.kept = bool(flag)

        def setSeqFilter(self, f):
            self.filter = f

        def printFilteredSeq(self, pct, path, xsl):
            self.printed = (pct, path, xsl)
            # Write a stub XML to mimic real PyCATSHOO behaviour.
            Path(path).write_text(
                f'<?xml version="1.0"?>\n<PYCRS NS="200" NSF="50">\n'
                f'  <SEQ N="50" P="0.25" C="bench"/>\n</PYCRS>\n'
            )

        def totalSeqCount(self):
            return self.totals[0]

        def filteredSeqCount(self):
            return self.totals[1]

    fake.IFilterFct = FakeIFilterFct
    fake.CAnalyser = FakeCAnalyser
    monkeypatch.setitem(sys.modules, "Pycatshoo", fake)
    return fake


class TestApplySequenceFiltering:
    def test_b2_no_filtering_skips_silently(self, tmp_path, fake_pyc_module):
        """When `sequence_filtering` is absent, helper does nothing."""
        study = _study_with_filtering(None)
        _apply_sequence_filtering(MagicMock(), study, tmp_path, logger=None)
        # Fake CAnalyser was never instantiated.
        assert fake_pyc_module.CAnalyser.instances == []
        assert not (tmp_path / "sequences.xml").exists()
        assert not (tmp_path / "sequence_filtering_metrics.json").exists()

    def test_b2_top_pct_only_calls_print_with_clamped_int(
        self, tmp_path, fake_pyc_module
    ):
        """top_sequences_pct=10.7 (no condition) → printFilteredSeq(11, …)."""
        # Reset the per-test counter. Note: 10.7 is used (not 10.5) to
        # avoid Python 3's banker's rounding ambiguity (round(10.5) == 10).
        fake_pyc_module.CAnalyser.instances.clear()
        study = _study_with_filtering({"top_sequences_pct": 10.7})
        _apply_sequence_filtering(MagicMock(), study, tmp_path, logger=None)

        assert len(fake_pyc_module.CAnalyser.instances) == 1
        analyser = fake_pyc_module.CAnalyser.instances[0]
        assert analyser.kept is True
        assert analyser.filter is None  # no condition
        assert analyser.printed is not None
        pct, path, xsl = analyser.printed
        assert pct == 11
        assert Path(path) == tmp_path / "sequences.xml"
        assert xsl == "PySeq.xsl"
        assert (tmp_path / "sequences.xml").exists()

    def test_b2_full_filtering_threads_condition(self, tmp_path, fake_pyc_module):
        """Full filtering (top + condition) → setSeqFilter + printFilteredSeq."""
        fake_pyc_module.CAnalyser.instances.clear()
        study = _study_with_filtering(
            {
                "top_sequences_pct": 25,
                "condition_filter": {
                    "variable_path": "T_LossPower.is_ok",
                    "time": 8760.0,
                    "op": "==",
                    "val": 0,
                },
            }
        )
        _apply_sequence_filtering(MagicMock(), study, tmp_path, logger=None)

        analyser = fake_pyc_module.CAnalyser.instances[0]
        assert analyser.filter == (
            "FilterFct",
            "T_LossPower.is_ok",
            8760.0,
            "==",
            0.0,
        )
        assert analyser.printed[0] == 25

    def test_b3_fail_open_on_setseqfilter_exception(
        self, tmp_path, fake_pyc_module, monkeypatch
    ):
        """When newConditionFilter raises (e.g. unknown variable_path),
        the run continues and the XML is still written via printFilteredSeq."""
        fake_pyc_module.CAnalyser.instances.clear()

        def boom(*args, **kwargs):
            raise RuntimeError("variable_path resolves to no monitored var")

        monkeypatch.setattr(
            fake_pyc_module.IFilterFct, "newConditionFilter", boom
        )
        study = _study_with_filtering(
            {
                "top_sequences_pct": 100,
                "condition_filter": {
                    "variable_path": "nonexistent.foo",
                    "time": 0,
                    "op": "==",
                    "val": 0,
                },
            }
        )
        # Logger captures the warning.
        logs: list[str] = []
        logger = MagicMock()
        logger.warning = lambda msg: logs.append(msg)
        logger.info2 = lambda msg: logs.append(msg)

        _apply_sequence_filtering(MagicMock(), study, tmp_path, logger=logger)

        analyser = fake_pyc_module.CAnalyser.instances[0]
        # Filter creation failed → analyser.filter stays None (no setSeqFilter call)
        assert analyser.filter is None
        # printFilteredSeq still ran (top_pct=100)
        assert analyser.printed is not None
        assert analyser.printed[0] == 100
        # A warning was logged about the filter failure.
        assert any("setSeqFilter failed" in msg for msg in logs)

    def test_b4_metrics_persisted_when_counters_available(
        self, tmp_path, fake_pyc_module
    ):
        """sequence_filtering_metrics.json is written next to the XML."""
        fake_pyc_module.CAnalyser.instances.clear()
        study = _study_with_filtering({"top_sequences_pct": 50})
        _apply_sequence_filtering(MagicMock(), study, tmp_path, logger=None)

        metrics_path = tmp_path / "sequence_filtering_metrics.json"
        assert metrics_path.exists()
        metrics = json.loads(metrics_path.read_text())
        assert metrics == {"total_sequences": 200, "filtered_sequences": 50}

    def test_b4_metrics_skipped_when_counters_missing(
        self, tmp_path, fake_pyc_module, monkeypatch
    ):
        """Older PyCATSHOO builds without the counters → metrics file omitted,
        no exception."""
        fake_pyc_module.CAnalyser.instances.clear()

        # Strip the counters from the fake class.
        analyser_cls = fake_pyc_module.CAnalyser

        def init_no_counters(self, system):
            self.system = system
            self.kept = False
            self.filter = None
            self.printed = None
            analyser_cls.instances.append(self)

        monkeypatch.setattr(analyser_cls, "__init__", init_no_counters)
        monkeypatch.setattr(analyser_cls, "totalSeqCount", lambda self: (_ for _ in ()).throw(AttributeError()))

        study = _study_with_filtering({"top_sequences_pct": 50})
        _apply_sequence_filtering(MagicMock(), study, tmp_path, logger=None)

        # XML written, metrics absent.
        assert (tmp_path / "sequences.xml").exists()
        assert not (tmp_path / "sequence_filtering_metrics.json").exists()
