"""Tests for ``cod3s-seq`` live mode (``--factory module:fn``).

Live mode attaches a populated :class:`PycSystem` to the analyser so
``filter_objfm_cycles`` can auto-discover ObjFM and the configuration
modal can render them as a checklist instead of a free-form text
input.

The PyCATSHOO singleton is process-level — tests use a tiny synthetic
system built once per module and torn down on exit, mirroring the
isimu test pattern.
"""

from __future__ import annotations

import Pycatshoo as Pyc
import pytest

from cod3s import terminate_session
from cod3s.pycatshoo.component import ObjFMExp, PycComponent
from cod3s.pycatshoo.seq_tui.app import SeqTuiApp
from cod3s.pycatshoo.seq_tui.modals import (
    AddStepModal,
    ConfigFilterObjFMCyclesModal,
)
from cod3s.pycatshoo.seq_tui.state import SeqTuiState
from cod3s.pycatshoo.sequence import SeqEvent, Sequence, SequenceAnalyser
from cod3s.pycatshoo.system import PycSystem


# ---------------------------------------------------------------------------
# Fixture — a small system with one internal ObjFM
# ---------------------------------------------------------------------------


class _LiveComp(PycComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.variable("working").setReinitialized(True)


@pytest.fixture(scope="module")
def live_system():
    """A PycSystem with two components and one internal ObjFM."""
    system = PycSystem(name="LiveModeTest")
    for comp_name in ("pump_1", "pump_2"):
        _LiveComp(name=comp_name)

    # One ObjFM internal covering both pumps.
    ObjFMExp(
        fm_name="def_pump",
        targets=["pump_1", "pump_2"],
        failure_param=[(1e-3,), (1e-4,)],
        repair_param=[(1e-1,), (1e-2,)],
        failure_effects={"working": False},
        behaviour="internal",
    )

    yield system
    terminate_session()


def _make_analyser(*seq_specs) -> SequenceAnalyser:
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
# discover_objfms — public wrapper API
# ---------------------------------------------------------------------------


class TestDiscoverObjFMs:
    def test_returns_empty_when_no_system_attached(self):
        analyser = _make_analyser(("top", 1, [("a", "occ", 1.0)]))
        internal, external = analyser.discover_objfms()
        assert internal == []
        assert external == []

    def test_finds_internal_objfm_when_attached(self, live_system):
        analyser = _make_analyser(("top", 1, [("a", "occ", 1.0)]))
        analyser._system = live_system
        internal, external = analyser.discover_objfms()
        assert "pump_X__def_pump" in internal
        assert external == []


# ---------------------------------------------------------------------------
# SeqTuiState.from_initial(system=...) — auto-attach + auto-populate
# ---------------------------------------------------------------------------


class TestFromInitialWithSystem:
    def test_post_mortem_keeps_lists_empty(self):
        analyser = _make_analyser(("top", 1, [("a", "occ", 1.0)]))
        state = SeqTuiState.from_initial(analyser)
        assert state.available_objfms_internal == ()
        assert state.available_objfms_external == ()
        assert analyser._system is None

    def test_live_mode_attaches_and_discovers(self, live_system):
        analyser = _make_analyser(("top", 1, [("a", "occ", 1.0)]))
        state = SeqTuiState.from_initial(analyser, system=live_system)
        assert "pump_X__def_pump" in state.available_objfms_internal
        # State carries the lists; analyser is attached so the pipeline
        # step can call analyser.filter_objfm_cycles() with empty lists
        # and still auto-discover.
        assert analyser._system is live_system


# ---------------------------------------------------------------------------
# ConfigFilterObjFMCyclesModal — UX switches with available_internal
# ---------------------------------------------------------------------------


class TestModalLiveMode:
    def test_live_mode_property_reflects_input(self):
        modal_pm = ConfigFilterObjFMCyclesModal()
        assert modal_pm.live_mode is False

        modal_live = ConfigFilterObjFMCyclesModal(
            available_internal=("fm1",),
            available_external=(),
        )
        assert modal_live.live_mode is True

    async def test_post_mortem_modal_renders_text_inputs(self, sample_state):
        app = SeqTuiApp(initial_state=sample_state)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("plus")
            await pilot.pause()
            add = app.screen
            assert isinstance(add, AddStepModal)
            add.dismiss("filter_objfm_cycles")
            await pilot.pause()
            cfg = app.screen
            assert isinstance(cfg, ConfigFilterObjFMCyclesModal)
            assert cfg.live_mode is False
            # The text-input id `int` is the post-mortem marker.
            from textual.widgets import Input

            assert cfg.query_one("#int", Input) is not None

    async def test_live_modal_renders_selection_list_and_pre_checks(self):
        # Build a state that *claims* to be in live mode without the
        # PyCATSHOO singleton being involved (we just inject the
        # discovered names).
        from cod3s.pycatshoo.sequence import Sequence

        analyser = SequenceAnalyser(
            sequences=[
                Sequence(target_name="top", weight=1, events=[])
            ]
        )
        analyser.update_probs()
        state = SeqTuiState.from_initial(analyser).__class__(
            analyser=analyser,
            pipeline=SeqTuiState.from_initial(analyser).pipeline,
            available_objfms_internal=("fm_a", "fm_b"),
            available_objfms_external=("fm_c",),
        )
        app = SeqTuiApp(initial_state=state)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("plus")
            await pilot.pause()
            add = app.screen
            assert isinstance(add, AddStepModal)
            add.dismiss("filter_objfm_cycles")
            await pilot.pause()
            cfg = app.screen
            assert isinstance(cfg, ConfigFilterObjFMCyclesModal)
            assert cfg.live_mode is True
            from textual.widgets import SelectionList

            int_sel = cfg.query_one("#int-sel", SelectionList)
            ext_sel = cfg.query_one("#ext-sel", SelectionList)
            # Pre-checked: every option starts as selected.
            assert set(int_sel.selected) == {"fm_a", "fm_b"}
            assert set(ext_sel.selected) == {"fm_c"}
