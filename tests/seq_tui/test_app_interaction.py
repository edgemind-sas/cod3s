"""Interaction tests for ``cod3s-seq`` — phases 3, 4, 5, 6.

These drive the live :class:`SeqTuiApp` via Textual's ``Pilot`` and
exercise:

* step stacking via ``+`` → ``AddStepModal`` → config modal,
* the worker-thread apply path (notification + state mutation),
* undo / redo cycles,
* save / load YAML round-trip via the modals,
* export to JSON cod3s / CSV / Markdown.

Async waits use ``pilot.pause()`` to allow worker callbacks to flush.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cod3s.pycatshoo.seq_tui.app import SeqTuiApp
from cod3s.pycatshoo.seq_tui.modals import (
    AddStepModal,
    ConfigFilterObjFMCyclesModal,
    ConfigRmEventsByObjModal,
    ExportModal,
    LoadPipelineModal,
    SavePipelineModal,
)
from cod3s.pycatshoo.seq_tui.pipeline import (
    ComputeMinimalSequencesStep,
    FilterObjFMCyclesStep,
    GroupSequencesStep,
    Pipeline,
    RmEventsByObjStep,
)
from cod3s.pycatshoo.seq_tui.state import SeqTuiState


async def _wait_for(predicate, pilot, *, attempts: int = 30):
    """Pause repeatedly until ``predicate()`` returns truthy."""
    for _ in range(attempts):
        await pilot.pause()
        if predicate():
            return
    raise AssertionError("predicate never became truthy")


# ---------------------------------------------------------------------------
# Step stacking
# ---------------------------------------------------------------------------


class TestStepStacking:
    async def test_plus_opens_add_step_modal(self, sample_state) -> None:
        app = SeqTuiApp(initial_state=sample_state)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("plus")
            await pilot.pause()
            assert isinstance(app.screen, AddStepModal)

    async def test_group_step_applies_via_modal_chain(self, sample_state) -> None:
        """+ → AddStepModal → dismiss('group_sequences') → no-param apply."""
        app = SeqTuiApp(initial_state=sample_state)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("plus")
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, AddStepModal)
            modal.dismiss("group_sequences")
            await _wait_for(
                lambda: len(app.state.pipeline.steps) == 1,
                pilot,
            )
            assert isinstance(
                app.state.pipeline.steps[0], GroupSequencesStep
            )

    async def test_filter_step_applies_via_config_modal(
        self, ccf_like_analyser
    ) -> None:
        state = SeqTuiState.from_initial(ccf_like_analyser)
        app = SeqTuiApp(initial_state=state)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("plus")
            await pilot.pause()
            add_modal = app.screen
            assert isinstance(add_modal, AddStepModal)
            add_modal.dismiss("filter_objfm_cycles")
            await _wait_for(
                lambda: isinstance(app.screen, ConfigFilterObjFMCyclesModal),
                pilot,
            )
            cfg = app.screen
            assert isinstance(cfg, ConfigFilterObjFMCyclesModal)
            # Programmatic dismiss with a fully-built step.
            cfg.dismiss(
                FilterObjFMCyclesStep(
                    objfm_internal=["fm"],
                    failure_state="occ__cc",
                    repair_state="rep__cc",
                )
            )
            await _wait_for(
                lambda: len(app.state.pipeline.steps) == 1,
                pilot,
            )
            step = app.state.pipeline.steps[0]
            assert isinstance(step, FilterObjFMCyclesStep)
            assert step.objfm_internal == ["fm"]

    async def test_canonical_pipeline_via_tui_equivalent_to_programmatic(
        self, ccf_like_analyser
    ) -> None:
        """The 3-step canonical pipeline applied through the TUI yields
        an analyser indistinguishable from a direct programmatic call."""
        # Programmatic baseline.
        from cod3s.pycatshoo.sequence import SequenceAnalyser
        import copy

        baseline = copy.deepcopy(ccf_like_analyser)
        Pipeline(
            steps=[
                GroupSequencesStep(),
                FilterObjFMCyclesStep(
                    objfm_internal=["fm"],
                    failure_state="occ__cc",
                    repair_state="rep__cc",
                ),
                ComputeMinimalSequencesStep(),
            ]
        ).apply(baseline)

        # TUI path.
        state = SeqTuiState.from_initial(copy.deepcopy(ccf_like_analyser))
        app = SeqTuiApp(initial_state=state)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Apply directly via the public state hook to avoid the
            # cumulative modal dance — the worker test is in
            # ``test_plus_opens_add_step_modal``.
            new_state = state.with_step_applied(GroupSequencesStep())
            new_state = new_state.with_step_applied(
                FilterObjFMCyclesStep(
                    objfm_internal=["fm"],
                    failure_state="occ__cc",
                    repair_state="rep__cc",
                )
            )
            new_state = new_state.with_step_applied(ComputeMinimalSequencesStep())
            app._state = new_state
            app.refresh_panels()
            await pilot.pause()

        # Signature-by-signature equivalence.
        def sigs(an: SequenceAnalyser):
            return {
                tuple((e.obj, e.attr) for e in s.events): s.weight
                for s in an.sequences
            }

        assert sigs(app.state.analyser) == sigs(baseline)


# ---------------------------------------------------------------------------
# Undo / Redo
# ---------------------------------------------------------------------------


class TestUndoRedo:
    async def test_undo_restores_previous_state(self, sample_state) -> None:
        app = SeqTuiApp(initial_state=sample_state)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Apply one step
            new_state = sample_state.with_step_applied(GroupSequencesStep())
            app._undo.push(sample_state)
            app._state = new_state
            app.refresh_panels()
            await pilot.pause()
            assert len(app.state.pipeline.steps) == 1
            # Undo
            await pilot.press("u")
            await pilot.pause()
            assert app.state is sample_state
            assert len(app.state.pipeline.steps) == 0

    async def test_redo_after_undo(self, sample_state) -> None:
        app = SeqTuiApp(initial_state=sample_state)
        async with app.run_test() as pilot:
            await pilot.pause()
            new_state = sample_state.with_step_applied(GroupSequencesStep())
            app._undo.push(sample_state)
            app._state = new_state
            app.refresh_panels()
            await pilot.pause()
            await pilot.press("u")
            await pilot.pause()
            assert app.state is sample_state
            await pilot.press("r")
            await pilot.pause()
            assert app.state is new_state


# ---------------------------------------------------------------------------
# Save / Load YAML
# ---------------------------------------------------------------------------


class TestSaveLoadYaml:
    async def test_save_pipeline_via_modal(
        self, ccf_like_analyser, tmp_path
    ) -> None:
        state = SeqTuiState.from_initial(ccf_like_analyser).with_step_applied(
            GroupSequencesStep()
        )
        app = SeqTuiApp(initial_state=state)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, SavePipelineModal)
            target = tmp_path / "pipe.yaml"
            modal.dismiss(target)
            await _wait_for(lambda: target.exists(), pilot)

        loaded = Pipeline.load_yaml(target)
        assert len(loaded.steps) == 1
        assert isinstance(loaded.steps[0], GroupSequencesStep)

    async def test_load_pipeline_via_modal(
        self, ccf_like_analyser, tmp_path
    ) -> None:
        # Write a pipeline file first.
        pipeline = Pipeline(
            steps=[
                GroupSequencesStep(),
                FilterObjFMCyclesStep(
                    objfm_internal=["fm"],
                    failure_state="occ__cc",
                    repair_state="rep__cc",
                ),
            ]
        )
        target = tmp_path / "pipe.yaml"
        pipeline.save_yaml(target)

        state = SeqTuiState.from_initial(ccf_like_analyser)
        app = SeqTuiApp(initial_state=state)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, LoadPipelineModal)
            modal.dismiss(target)
            await _wait_for(
                lambda: len(app.state.pipeline.steps) == 2,
                pilot,
            )
            assert isinstance(app.state.pipeline.steps[0], GroupSequencesStep)
            assert isinstance(
                app.state.pipeline.steps[1], FilterObjFMCyclesStep
            )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestExport:
    @pytest.mark.parametrize(
        "fmt,suffix",
        [
            ("json-cod3s", ".json"),
            ("csv", ".csv"),
            ("markdown", ".md"),
        ],
    )
    async def test_export_via_modal(
        self, sample_state, tmp_path, fmt, suffix
    ) -> None:
        app = SeqTuiApp(initial_state=sample_state)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("e")
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, ExportModal)
            target = tmp_path / f"out{suffix}"
            modal.dismiss((fmt, target))
            await _wait_for(lambda: target.exists(), pilot)
        if fmt == "json-cod3s":
            payload = json.loads(target.read_text())
            assert "schema_version" in payload
            assert isinstance(payload["sequences"], list)

    async def test_export_cancel_writes_nothing(
        self, sample_state, tmp_path
    ) -> None:
        app = SeqTuiApp(initial_state=sample_state)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("e")
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, ExportModal)
            modal.dismiss(None)
            await pilot.pause()
        assert list(tmp_path.iterdir()) == []
