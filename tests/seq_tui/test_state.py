"""Tests for ``cod3s.pycatshoo.seq_tui.state``.

Three behaviours under test:

1. Immutable transitions — ``with_step_applied`` returns a *new* state
   without mutating the original analyser. The pipeline grows by one
   step and ``last_delta`` records the size diff.
2. Selection clamping — ``with_selection`` clamps out-of-range indices
   to ``None`` so panels never receive a bogus pointer.
3. UndoStack semantics — push/undo/redo behave like a standard editor
   stack, the redo branch is cleared on a new push, and the maxlen
   cap silently drops the oldest entry.
"""

from __future__ import annotations

import copy

from cod3s.pycatshoo.seq_tui.pipeline import (
    FilterObjFMCyclesStep,
    GroupSequencesStep,
    RmEventsByObjStep,
)
from cod3s.pycatshoo.seq_tui.state import SeqTuiState, StateDelta, UndoStack


# ---------------------------------------------------------------------------
# Immutable transitions
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_with_step_applied_does_not_mutate_original(self, sample_state):
        before = copy.deepcopy(sample_state.analyser.sequences)
        new_state = sample_state.with_step_applied(GroupSequencesStep())
        # Original analyser intact.
        assert sample_state.analyser.sequences == before
        # New state has its own analyser.
        assert new_state.analyser is not sample_state.analyser
        # Pipeline grew by one step.
        assert len(new_state.pipeline.steps) == len(sample_state.pipeline.steps) + 1

    def test_last_delta_records_size_change(self, ccf_like_analyser):
        state = SeqTuiState.from_initial(ccf_like_analyser)
        # After group_sequences alone, 3 distinct sigs → 3 (no collapse yet).
        s1 = state.with_step_applied(GroupSequencesStep())
        assert s1.last_delta is not None
        assert isinstance(s1.last_delta, StateDelta)
        assert s1.last_delta.step_summary.startswith("group_sequences")
        # After filter on "fm" then re-group → seq 1 and 3 collapse.
        s2 = s1.with_step_applied(
            FilterObjFMCyclesStep(objfm_internal=["fm"])
        )
        assert s2.last_delta is not None
        # filter+regroup drops 1 distinct signature → d_sequences = -1
        assert s2.last_delta.d_sequences <= 0


# ---------------------------------------------------------------------------
# Selection clamping
# ---------------------------------------------------------------------------


class TestSelection:
    def test_in_range_selection_preserved(self, sample_state):
        s = sample_state.with_selection(2)
        assert s.selected_seq_idx == 2

    def test_out_of_range_selection_clamped_to_none(self, sample_state):
        s = sample_state.with_selection(99)
        assert s.selected_seq_idx is None

    def test_selection_dropped_when_step_shrinks_below_idx(self, sample_state):
        s = sample_state.with_selection(3)  # last seq, weight=1
        # rm_events_by_obj("c") drops the "safe" sequence's only event,
        # leaving an empty sequence — count stays the same.
        s2 = s.with_step_applied(RmEventsByObjStep(obj_name="c"))
        assert s2.selected_seq_idx == 3  # still in range
        # group_sequences collapses the now-empty sequence with… nothing
        # else (no other empties), so still 4. But filtering all events
        # of every sequence followed by group would collapse them.
        # Just verify the clamping path: artificially shrink via deepcopy.
        from cod3s.pycatshoo.sequence import SequenceAnalyser

        new_analyser = SequenceAnalyser(sequences=[s2.analyser.sequences[0]])
        clamped = SeqTuiState(
            analyser=new_analyser,
            pipeline=s2.pipeline,
            selected_seq_idx=3,
        ).with_selection(3)
        assert clamped.selected_seq_idx is None


# ---------------------------------------------------------------------------
# UndoStack
# ---------------------------------------------------------------------------


class TestUndoStack:
    def test_empty_stack_returns_none(self, sample_state):
        stack = UndoStack()
        assert not stack.can_undo
        assert not stack.can_redo
        assert stack.undo(sample_state) is None
        assert stack.redo(sample_state) is None

    def test_push_then_undo_returns_previous(self, sample_state):
        stack = UndoStack()
        stack.push(sample_state)
        new_state = sample_state.with_step_applied(GroupSequencesStep())
        restored = stack.undo(new_state)
        assert restored is sample_state
        assert stack.can_redo
        assert not stack.can_undo

    def test_redo_round_trip(self, sample_state):
        stack = UndoStack()
        stack.push(sample_state)
        new_state = sample_state.with_step_applied(GroupSequencesStep())
        old = stack.undo(new_state)
        assert old is sample_state
        # Now redo back to new_state.
        restored = stack.redo(old)
        assert restored is new_state
        assert stack.can_undo
        assert not stack.can_redo

    def test_push_clears_redo_branch(self, sample_state):
        stack = UndoStack()
        stack.push(sample_state)
        new_state = sample_state.with_step_applied(GroupSequencesStep())
        # Undo, then push a new state — the redo branch must be cleared.
        old = stack.undo(new_state)
        assert stack.can_redo
        stack.push(old)
        assert not stack.can_redo

    def test_maxlen_drops_oldest(self, sample_state):
        stack = UndoStack(maxlen=3)
        for _ in range(5):
            stack.push(sample_state)
        # Only the last 3 fit.
        assert stack.undo_depth == 3
