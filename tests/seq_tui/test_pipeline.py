"""Tests for ``cod3s.pycatshoo.seq_tui.pipeline``.

Two angles:

1. **YAML round-trip** — each of the 6 step types serialises and
   deserialises losslessly, including all of their parameters.
2. **Apply equivalence** — composing the canonical pipeline via the
   ``Pipeline`` machinery produces the same analyser as calling the
   API methods directly. This is the safety net that guarantees the
   TUI's interactive output matches the programmatic baseline.
"""

from __future__ import annotations

import pytest

from cod3s.pycatshoo.seq_tui.pipeline import (
    PIPELINE_SCHEMA_VERSION,
    ComputeMinimalSequencesStep,
    FilterObjFMCyclesStep,
    GroupSequencesStep,
    Pipeline,
    RenameEventsStep,
    RmEventsByObjStep,
    RmEventsOrderedPatternStep,
    STEP_CLASSES,
)
from cod3s.pycatshoo.sequence import SeqEvent, Sequence, SequenceAnalyser


def _make_analyser(*seq_specs):
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


# ---------------------------------------------------------------------------
# Construction + module-level exports
# ---------------------------------------------------------------------------


class TestStepCatalogue:
    def test_step_classes_exposes_six_ops(self):
        """The TUI's AddStepModal will list these keys verbatim."""
        assert set(STEP_CLASSES) == {
            "group_sequences",
            "filter_objfm_cycles",
            "compute_minimal_sequences",
            "rm_events_by_obj",
            "rm_events_ordered_pattern",
            "rename_events",
        }


# ---------------------------------------------------------------------------
# YAML round-trip
# ---------------------------------------------------------------------------


class TestYamlRoundTrip:
    def test_empty_pipeline(self, tmp_path):
        p = Pipeline()
        path = tmp_path / "pipe.yaml"
        p.save_yaml(path)
        loaded = Pipeline.load_yaml(path)
        assert loaded.version == PIPELINE_SCHEMA_VERSION
        assert loaded.steps == []

    def test_canonical_3_step_pipeline_round_trip(self, tmp_path):
        original = Pipeline(
            steps=[
                GroupSequencesStep(),
                FilterObjFMCyclesStep(
                    objfm_internal=["pump_X__def_pump"],
                    failure_state="occ",
                    repair_state="rep",
                ),
                ComputeMinimalSequencesStep(),
            ]
        )
        path = tmp_path / "canonical.yaml"
        original.save_yaml(path)
        loaded = Pipeline.load_yaml(path)
        # Same shape, same step types, same params.
        assert len(loaded.steps) == 3
        assert isinstance(loaded.steps[0], GroupSequencesStep)
        assert isinstance(loaded.steps[1], FilterObjFMCyclesStep)
        assert loaded.steps[1].objfm_internal == ["pump_X__def_pump"]
        assert isinstance(loaded.steps[2], ComputeMinimalSequencesStep)

    def test_all_six_ops_round_trip(self, tmp_path):
        original = Pipeline(
            steps=[
                GroupSequencesStep(),
                FilterObjFMCyclesStep(
                    objfm_internal=["fm1"],
                    objfm_external=["fm2"],
                    failure_state="ko",
                    repair_state="ok",
                ),
                ComputeMinimalSequencesStep(),
                RmEventsByObjStep(obj_name="noise_comp"),
                RmEventsOrderedPatternStep(
                    name_pat1=r"^(.+)\.start$",
                    name_pat2=r"\1\.stop$",
                ),
                RenameEventsStep(
                    attr="obj",
                    pat_source=r"^old_(.+)$",
                    pat_target=r"new_\1",
                ),
            ]
        )
        path = tmp_path / "all.yaml"
        original.save_yaml(path)
        loaded = Pipeline.load_yaml(path)
        assert [type(s) for s in loaded.steps] == [type(s) for s in original.steps]
        assert loaded.steps[1].failure_state == "ko"
        assert loaded.steps[3].obj_name == "noise_comp"
        assert loaded.steps[4].name_pat1 == r"^(.+)\.start$"
        assert loaded.steps[5].pat_target == r"new_\1"

    def test_load_unknown_op_raises(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text(
            "version: '1.0.0'\nsteps:\n  - op: unknown_op_xx\n"
        )
        with pytest.raises(Exception) as exc_info:
            Pipeline.load_yaml(path)
        # Pydantic surfaces the discriminator failure
        assert "discriminator" in str(exc_info.value).lower() or "op" in str(exc_info.value)

    def test_load_invalid_step_params_raises(self, tmp_path):
        path = tmp_path / "bad_params.yaml"
        # RmEventsByObjStep requires obj_name
        path.write_text(
            "version: '1.0.0'\nsteps:\n  - op: rm_events_by_obj\n"
        )
        with pytest.raises(Exception):
            Pipeline.load_yaml(path)

    def test_load_extra_field_rejected(self, tmp_path):
        path = tmp_path / "extra.yaml"
        path.write_text(
            "version: '1.0.0'\nsteps:\n"
            "  - op: group_sequences\n"
            "    bogus_param: 42\n"
        )
        with pytest.raises(Exception, match="(?i)extra|bogus_param"):
            Pipeline.load_yaml(path)

    def test_load_missing_steps_defaults_empty(self, tmp_path):
        path = tmp_path / "noversion.yaml"
        path.write_text("version: '1.0.0'\n")
        loaded = Pipeline.load_yaml(path)
        assert loaded.steps == []


# ---------------------------------------------------------------------------
# Apply equivalence
# ---------------------------------------------------------------------------


def _signatures(analyser):
    return {
        tuple((e.obj, e.attr) for e in s.events): s.weight
        for s in analyser.sequences
    }


class TestApplyEquivalence:
    def test_pipeline_matches_direct_calls_on_synthetic_data(self):
        """Build two analysers with the same data, apply via Pipeline
        on one and via direct calls on the other — final signatures and
        weights must match exactly."""

        def make():
            return _make_analyser(
                ("top", 1, [("fm", "occ__cc_1", 1.0), ("fm", "rep__cc_1", 2.0),
                            ("fm", "occ__cc_2", 3.0), ("top", "occ", 4.0)]),
                ("top", 1, [("fm", "occ__cc_2", 1.0), ("fm", "occ__cc_1", 2.0),
                            ("top", "occ", 3.0)]),
                ("top", 1, [("fm", "occ__cc_1", 1.0), ("fm", "occ__cc_2", 2.0),
                            ("top", "occ", 3.0)]),
            )

        # Via Pipeline
        via_pipeline = make()
        Pipeline(
            steps=[
                GroupSequencesStep(),
                FilterObjFMCyclesStep(objfm_internal=["fm"]),
                ComputeMinimalSequencesStep(),
            ]
        ).apply(via_pipeline)

        # Via direct calls
        direct = make()
        direct.group_sequences(inplace=True)
        direct.filter_objfm_cycles(objfm_internal=["fm"], inplace=True)
        direct.compute_minimal_sequences(inplace=True)

        assert _signatures(via_pipeline) == _signatures(direct)

    def test_empty_pipeline_is_noop(self):
        analyser = _make_analyser(("t", 1, [("a", "occ", 1.0)]))
        before = _signatures(analyser)
        Pipeline().apply(analyser)
        assert _signatures(analyser) == before

    def test_rm_events_by_obj_step_applies(self):
        analyser = _make_analyser(
            ("t", 1, [("noise", "tick", 1.0), ("real", "occ", 2.0)])
        )
        Pipeline(steps=[RmEventsByObjStep(obj_name="noise")]).apply(analyser)
        # Re-group is implicit in rm_events_by_obj — we just check the
        # noise event is gone.
        assert [(e.obj, e.attr) for e in analyser.sequences[0].events] == [
            ("real", "occ")
        ]

    def test_filter_objfm_cycles_step_strips_pair(self):
        analyser = _make_analyser(
            ("t", 1, [("fm", "occ__cc_1", 1.0), ("fm", "rep__cc_1", 2.0),
                      ("top", "occ", 3.0)])
        )
        Pipeline(
            steps=[FilterObjFMCyclesStep(objfm_internal=["fm"])]
        ).apply(analyser)
        assert [(e.obj, e.attr) for e in analyser.sequences[0].events] == [
            ("top", "occ")
        ]

    def test_step_summary_renders(self):
        """Each step provides a one-line summary (used by the
        PipelinePanel display)."""
        steps = [
            GroupSequencesStep(),
            FilterObjFMCyclesStep(objfm_internal=["fm"]),
            ComputeMinimalSequencesStep(),
            RmEventsByObjStep(obj_name="x"),
            RmEventsOrderedPatternStep(name_pat1="a", name_pat2="b"),
            RenameEventsStep(attr="obj", pat_source="x", pat_target="y"),
        ]
        for step in steps:
            assert isinstance(step.summary(), str)
            assert len(step.summary()) > 0
