import pytest
import re
from cod3s.pycatshoo.sequence import Sequence, SeqEvent


class TestSequence:
    """Test class for Sequence object."""

    def test_sequence_creation(self):
        """Test basic Sequence creation."""
        sequence = Sequence(
            probability=0.25,
            weight=10,
            end_time=100.5,
            target_name="failure",
            events=[]
        )
        
        assert sequence.probability == 0.25
        assert sequence.weight == 10
        assert sequence.end_time == 100.5
        assert sequence.target_name == "failure"
        assert sequence.events == []

    def test_sequence_creation_with_events(self):
        """Test Sequence creation with events."""
        event1 = SeqEvent(obj="comp1", attr="state", time=10.0, type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", time=20.0, type="failure")
        
        sequence = Sequence(
            target_name="system_failure",
            events=[event1, event2]
        )
        
        assert len(sequence.events) == 2
        assert sequence.events[0] == event1
        assert sequence.events[1] == event2
        assert sequence.target_name == "system_failure"

    def test_sequence_default_values(self):
        """Test Sequence with default values."""
        sequence = Sequence()
        
        assert sequence.probability is None
        assert sequence.weight == 1  # Default value
        assert sequence.end_time is None
        assert sequence.target_name is None
        assert sequence.events == []

    def test_sequence_repr(self):
        """Test Sequence string representation."""
        event1 = SeqEvent(obj="comp1", attr="state", time=10.0, type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", time=20.0, type="failure")
        
        sequence = Sequence(
            probability=0.15,
            weight=5,
            end_time=50.0,
            target_name="test_failure",
            events=[event1, event2]
        )
        
        repr_str = repr(sequence)
        # Should contain key information
        assert "test_failure" in repr_str
        assert "50.00" in repr_str
        assert "5" in repr_str
        assert "15.00%" in repr_str

    def test_sequence_str(self):
        """Test Sequence detailed string representation."""
        event1 = SeqEvent(obj="comp1", attr="state", time=10.0, type="transition")
        
        sequence = Sequence(
            probability=0.25,
            weight=8,
            end_time=75.5,
            target_name="critical_failure",
            events=[event1]
        )
        
        str_repr = str(sequence)
        # Should contain detailed information
        assert "Target:" in str_repr
        assert "End time:" in str_repr
        assert "Weight:" in str_repr
        assert "Probability:" in str_repr
        assert "critical_failure" in str_repr

    def test_sequence_is_included_empty_sequence(self):
        """Test is_included with empty sequence."""
        empty_sequence = Sequence()
        other_sequence = Sequence(events=[
            SeqEvent(obj="comp1", attr="state", type="transition")
        ])
        
        # Empty sequence is included in any sequence
        assert empty_sequence.is_included(other_sequence) is True
        assert empty_sequence.is_included(empty_sequence) is True

    def test_sequence_is_included_same_events(self):
        """Test is_included with identical sequences."""
        event1 = SeqEvent(obj="comp1", attr="state", type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", type="failure")
        
        sequence1 = Sequence(events=[event1, event2])
        sequence2 = Sequence(events=[event1, event2])
        
        assert sequence1.is_included(sequence2) is True
        assert sequence2.is_included(sequence1) is True

    def test_sequence_is_included_subset(self):
        """Test is_included with subset of events."""
        event1 = SeqEvent(obj="comp1", attr="state", type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", type="failure")
        event3 = SeqEvent(obj="comp3", attr="status", type="repair")
        
        short_sequence = Sequence(events=[event1, event3])
        long_sequence = Sequence(events=[event1, event2, event3])
        
        # Short sequence should be included in long sequence
        assert short_sequence.is_included(long_sequence) is True
        # Long sequence should not be included in short sequence
        assert long_sequence.is_included(short_sequence) is False

    def test_sequence_is_included_different_order(self):
        """Test is_included with different event order."""
        event1 = SeqEvent(obj="comp1", attr="state", type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", type="failure")
        
        sequence1 = Sequence(events=[event1, event2])
        sequence2 = Sequence(events=[event2, event1])
        
        # Different order means not included
        assert sequence1.is_included(sequence2) is False
        assert sequence2.is_included(sequence1) is False

    def test_sequence_is_included_no_match(self):
        """Test is_included with completely different events."""
        event1 = SeqEvent(obj="comp1", attr="state", type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", type="failure")
        
        sequence1 = Sequence(events=[event1])
        sequence2 = Sequence(events=[event2])
        
        assert sequence1.is_included(sequence2) is False
        assert sequence2.is_included(sequence1) is False

    def test_sequence_rm_events_ordered_pattern_basic(self):
        """Test rm_events_ordered_pattern with basic pattern matching."""
        event1 = SeqEvent(obj="comp1", attr="absent_present", type="transition")
        event2 = SeqEvent(obj="comp2", attr="state", type="normal")
        event3 = SeqEvent(obj="comp1", attr="present_absent", type="transition")
        
        sequence = Sequence(events=[event1, event2, event3])
        
        # Remove absent_present followed by present_absent for same component
        filtered_sequence = sequence.rm_events_ordered_pattern(
            name_pat1=r"(.+)\.absent_present",
            name_pat2=r"\1\.present_absent",
            inplace=False
        )
        
        # Should only have the middle event left
        assert len(filtered_sequence.events) == 1
        assert filtered_sequence.events[0] == event2
        # Original sequence should be unchanged
        assert len(sequence.events) == 3

    def test_sequence_rm_events_ordered_pattern_inplace(self):
        """Test rm_events_ordered_pattern with inplace=True."""
        event1 = SeqEvent(obj="comp1", attr="start", type="transition")
        event2 = SeqEvent(obj="comp1", attr="end", type="transition")
        
        sequence = Sequence(events=[event1, event2])
        
        # Remove start followed by end for same component
        result = sequence.rm_events_ordered_pattern(
            name_pat1=r"(.+)\.start",
            name_pat2=r"\1\.end",
            inplace=True
        )
        
        # Should return the same object
        assert result is sequence
        # Should have no events left
        assert len(sequence.events) == 0

    def test_sequence_rm_events_ordered_pattern_no_match(self):
        """Test rm_events_ordered_pattern when no pattern matches."""
        event1 = SeqEvent(obj="comp1", attr="state1", type="transition")
        event2 = SeqEvent(obj="comp2", attr="state2", type="transition")
        
        sequence = Sequence(events=[event1, event2])
        
        filtered_sequence = sequence.rm_events_ordered_pattern(
            name_pat1=r"nonexistent",
            name_pat2=r"pattern",
            inplace=False
        )
        
        # All events should remain
        assert len(filtered_sequence.events) == 2
        assert filtered_sequence.events == sequence.events

    def test_sequence_rm_events_ordered_pattern_partial_match(self):
        """Test rm_events_ordered_pattern when first pattern matches but second doesn't."""
        event1 = SeqEvent(obj="comp1", attr="start", type="transition")
        event2 = SeqEvent(obj="comp2", attr="middle", type="normal")
        event3 = SeqEvent(obj="comp3", attr="other", type="transition")
        
        sequence = Sequence(events=[event1, event2, event3])
        
        filtered_sequence = sequence.rm_events_ordered_pattern(
            name_pat1=r"(.+)\.start",
            name_pat2=r"\1\.end",  # No matching end event
            inplace=False
        )
        
        # All events should remain since no complete pattern match
        assert len(filtered_sequence.events) == 3

    def test_sequence_rm_events_ordered_pattern_multiple_pairs(self):
        """Test rm_events_ordered_pattern with multiple matching pairs."""
        event1 = SeqEvent(obj="comp1", attr="on", type="transition")
        event2 = SeqEvent(obj="comp1", attr="off", type="transition")
        event3 = SeqEvent(obj="comp2", attr="on", type="transition")
        event4 = SeqEvent(obj="comp3", attr="state", type="normal")
        event5 = SeqEvent(obj="comp2", attr="off", type="transition")
        
        sequence = Sequence(events=[event1, event2, event3, event4, event5])
        
        filtered_sequence = sequence.rm_events_ordered_pattern(
            name_pat1=r"(.+)\.on",
            name_pat2=r"\1\.off",
            inplace=False
        )
        
        # Should only have the normal state event left
        assert len(filtered_sequence.events) == 1
        assert filtered_sequence.events[0] == event4

    def test_sequence_rename_events_obj(self):
        """Test rename_events for obj attribute."""
        event1 = SeqEvent(obj="old_comp1", attr="state", type="transition")
        event2 = SeqEvent(obj="old_comp2", attr="value", type="failure")
        
        sequence = Sequence(events=[event1, event2])
        
        renamed_sequence = sequence.rename_events(
            attr="obj",
            pat_source=r"old_(.+)",
            pat_target=r"new_\1",
            inplace=False
        )
        
        # Check renamed events
        assert renamed_sequence.events[0].obj == "new_comp1"
        assert renamed_sequence.events[1].obj == "new_comp2"
        # Original should be unchanged
        assert sequence.events[0].obj == "old_comp1"
        assert sequence.events[1].obj == "old_comp2"

    def test_sequence_rename_events_inplace(self):
        """Test rename_events with inplace=True."""
        event1 = SeqEvent(obj="comp1", attr="old_state", type="transition")
        
        sequence = Sequence(events=[event1])
        
        result = sequence.rename_events(
            attr="attr",
            pat_source=r"old_(.+)",
            pat_target=r"new_\1",
            inplace=True
        )
        
        # Should return None for inplace operation
        assert result is None
        # Original sequence should be modified
        assert sequence.events[0].attr == "new_state"

    def test_sequence_rename_events_type(self):
        """Test rename_events for type attribute."""
        event1 = SeqEvent(obj="comp1", attr="state", type="old_transition")
        event2 = SeqEvent(obj="comp2", attr="value", type="old_failure")
        
        sequence = Sequence(events=[event1, event2])
        
        renamed_sequence = sequence.rename_events(
            attr="type",
            pat_source=r"old_(.+)",
            pat_target=r"new_\1",
            inplace=False
        )
        
        assert renamed_sequence.events[0].type == "new_transition"
        assert renamed_sequence.events[1].type == "new_failure"

    def test_sequence_rename_events_no_match(self):
        """Test rename_events when pattern doesn't match."""
        event1 = SeqEvent(obj="comp1", attr="state", type="transition")
        
        sequence = Sequence(events=[event1])
        
        renamed_sequence = sequence.rename_events(
            attr="obj",
            pat_source=r"nonexistent",
            pat_target=r"replacement",
            inplace=False
        )
        
        # Events should remain unchanged
        assert renamed_sequence.events[0].obj == "comp1"

    def test_sequence_rename_events_empty_sequence(self):
        """Test rename_events with empty sequence."""
        sequence = Sequence(events=[])
        
        renamed_sequence = sequence.rename_events(
            attr="obj",
            pat_source=r"old",
            pat_target=r"new",
            inplace=False
        )
        
        # Should still be empty
        assert len(renamed_sequence.events) == 0

    def test_sequence_copy_behavior_in_operations(self):
        """Test that operations create proper copies when inplace=False."""
        event1 = SeqEvent(obj="comp1", attr="state", time=10.0, type="transition")
        
        original_sequence = Sequence(
            probability=0.5,
            weight=3,
            end_time=25.0,
            target_name="test",
            events=[event1]
        )
        
        # Test rm_events_ordered_pattern copy behavior
        filtered_sequence = original_sequence.rm_events_ordered_pattern(
            name_pat1=r"nonexistent",
            name_pat2=r"pattern",
            inplace=False
        )
        
        # Should be different objects
        assert filtered_sequence is not original_sequence
        # But should have same content
        assert filtered_sequence.probability == original_sequence.probability
        assert filtered_sequence.weight == original_sequence.weight
        assert filtered_sequence.end_time == original_sequence.end_time
        assert filtered_sequence.target_name == original_sequence.target_name
        
        # Test rename_events copy behavior
        renamed_sequence = original_sequence.rename_events(
            attr="obj",
            pat_source=r"comp1",
            pat_target=r"comp2",
            inplace=False
        )
        
        # Should be different objects
        assert renamed_sequence is not original_sequence
        # Events should be different
        assert renamed_sequence.events[0] is not original_sequence.events[0]
        assert renamed_sequence.events[0].obj == "comp2"
        assert original_sequence.events[0].obj == "comp1"

    def test_sequence_with_none_event_names(self):
        """Test sequence operations with events that have None names."""
        # Create events with None names (empty obj and attr)
        event1 = SeqEvent(obj="", attr="", type="transition")
        event2 = SeqEvent(obj="comp1", attr="state", type="normal")
        
        sequence = Sequence(events=[event1, event2])
        
        # Should not crash when processing events with None names
        filtered_sequence = sequence.rm_events_ordered_pattern(
            name_pat1=r"(.+)\.start",
            name_pat2=r"\1\.end",
            inplace=False
        )
        
        # All events should remain since None names don't match patterns
        assert len(filtered_sequence.events) == 2

    def test_sequence_preserve_metadata_in_operations(self):
        """Test that sequence metadata is preserved in operations."""
        event1 = SeqEvent(obj="comp1", attr="state", type="transition")
        
        original_sequence = Sequence(
            probability=0.75,
            weight=12,
            end_time=150.5,
            target_name="critical_failure",
            events=[event1]
        )
        
        # Test that rm_events_ordered_pattern preserves metadata
        filtered_sequence = original_sequence.rm_events_ordered_pattern(
            name_pat1=r"nonexistent",
            name_pat2=r"pattern",
            inplace=False
        )
        
        assert filtered_sequence.probability == 0.75
        assert filtered_sequence.weight == 12
        assert filtered_sequence.end_time == 150.5
        assert filtered_sequence.target_name == "critical_failure"
        
        # Test that rename_events preserves metadata
        renamed_sequence = original_sequence.rename_events(
            attr="obj",
            pat_source=r"comp1",
            pat_target=r"comp2",
            inplace=False
        )
        
        assert renamed_sequence.probability == 0.75
        assert renamed_sequence.weight == 12
        assert renamed_sequence.end_time == 150.5
        assert renamed_sequence.target_name == "critical_failure"
