import pytest
import re
from cod3s.pycatshoo.sequence import SequenceAnalyser, Sequence, SeqEvent


class TestSequenceAnalyser:
    """Test class for SequenceAnalyser object."""

    def test_sequence_analyser_creation(self):
        """Test basic SequenceAnalyser creation."""
        analyser = SequenceAnalyser()
        
        assert analyser.sequences == []
        assert analyser.nb_sequences == 0
        assert analyser.weight_total == 0

    def test_sequence_analyser_with_sequences(self):
        """Test SequenceAnalyser creation with sequences."""
        event1 = SeqEvent(obj="comp1", attr="state", time=10.0, type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", time=20.0, type="failure")
        
        seq1 = Sequence(
            target_name="failure_A",
            weight=5,
            end_time=30.0,
            events=[event1]
        )
        seq2 = Sequence(
            target_name="failure_B",
            weight=3,
            end_time=25.0,
            events=[event2]
        )
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        
        assert len(analyser.sequences) == 2
        assert analyser.nb_sequences == 2
        assert analyser.weight_total == 8

    def test_sequence_analyser_properties(self):
        """Test SequenceAnalyser computed properties."""
        seq1 = Sequence(target_name="target_A", weight=10)
        seq2 = Sequence(target_name="target_A", weight=5)
        seq3 = Sequence(target_name="target_B", weight=3)
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2, seq3])
        
        # Test nb_sequences
        assert analyser.nb_sequences == 3
        
        # Test weight_total
        assert analyser.weight_total == 18
        
        # Test target_stats
        stats = analyser.target_stats
        assert len(stats) == 2
        
        assert stats["target_A"]["nb_sequences"] == 2
        assert stats["target_A"]["weight"] == 15
        assert abs(stats["target_A"]["probability"] - 15/18) < 1e-10
        
        assert stats["target_B"]["nb_sequences"] == 1
        assert stats["target_B"]["weight"] == 3
        assert abs(stats["target_B"]["probability"] - 3/18) < 1e-10

    def test_sequence_analyser_target_stats_empty(self):
        """Test target_stats with empty analyser."""
        analyser = SequenceAnalyser()
        stats = analyser.target_stats
        assert stats == {}

    def test_sequence_analyser_target_stats_none_target(self):
        """Test target_stats with None target names."""
        seq1 = Sequence(target_name=None, weight=5)
        seq2 = Sequence(target_name="", weight=3)
        seq3 = Sequence(target_name="real_target", weight=2)
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2, seq3])
        stats = analyser.target_stats
        
        # None and empty string should be treated as empty string
        assert "" in stats
        assert stats[""]["nb_sequences"] == 2
        assert stats[""]["weight"] == 8
        
        assert "real_target" in stats
        assert stats["real_target"]["nb_sequences"] == 1
        assert stats["real_target"]["weight"] == 2

    def test_sequence_analyser_repr(self):
        """Test SequenceAnalyser string representation."""
        seq1 = Sequence(target_name="failure", weight=10)
        seq2 = Sequence(target_name="success", weight=5)
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        repr_str = repr(analyser)
        
        # Should contain key information
        assert "SequenceAnalyser" in repr_str
        assert "#seq: 2" in repr_str
        assert "w: 15" in repr_str
        assert "failure" in repr_str
        assert "success" in repr_str

    def test_sequence_analyser_str(self):
        """Test SequenceAnalyser detailed string representation."""
        seq1 = Sequence(target_name="critical", weight=8)
        seq2 = Sequence(target_name="minor", weight=2)
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        str_repr = str(analyser)
        
        # Should contain detailed information
        assert "SequenceAnalyser" in str_repr
        assert "Total sequences:" in str_repr
        assert "Total weight:" in str_repr
        assert "Targets:" in str_repr
        assert "critical" in str_repr
        assert "minor" in str_repr

    def test_update_probs(self):
        """Test update_probs method."""
        seq1 = Sequence(target_name="A", weight=6, probability=None)
        seq2 = Sequence(target_name="B", weight=4, probability=None)
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        
        # Initially probabilities should be None
        assert seq1.probability is None
        assert seq2.probability is None
        
        # Update probabilities
        analyser.update_probs()
        
        # Check probabilities are calculated correctly
        assert abs(seq1.probability - 0.6) < 1e-10
        assert abs(seq2.probability - 0.4) < 1e-10

    def test_update_probs_zero_weight(self):
        """Test update_probs with zero total weight."""
        seq1 = Sequence(target_name="A", weight=0)
        analyser = SequenceAnalyser(sequences=[seq1])
        
        analyser.update_probs()
        assert seq1.probability is None

    def test_group_sequences_basic(self):
        """Test group_sequences with basic merging."""
        # Create sequences with identical event patterns
        event1 = SeqEvent(obj="comp1", attr="state", type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", type="failure")
        
        seq1 = Sequence(
            target_name="failure",
            weight=3,
            end_time=10.0,
            events=[
                SeqEvent(obj="comp1", attr="state", time=5.0, type="transition"),
                SeqEvent(obj="comp2", attr="value", time=8.0, type="failure")
            ]
        )
        seq2 = Sequence(
            target_name="failure",
            weight=2,
            end_time=12.0,
            events=[
                SeqEvent(obj="comp1", attr="state", time=7.0, type="transition"),
                SeqEvent(obj="comp2", attr="value", time=10.0, type="failure")
            ]
        )
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        grouped = analyser.group_sequences(inplace=False)
        
        # Should have merged into one sequence
        assert grouped.nb_sequences == 1
        merged_seq = grouped.sequences[0]
        
        # Check merged properties
        assert merged_seq.target_name == "failure"
        assert merged_seq.weight == 5  # 3 + 2
        assert abs(merged_seq.end_time - 11.0) < 1e-10  # Mean of 10.0 and 12.0
        
        # Check merged event times (should be means)
        assert len(merged_seq.events) == 2
        assert abs(merged_seq.events[0].time - 6.0) < 1e-10  # Mean of 5.0 and 7.0
        assert abs(merged_seq.events[1].time - 9.0) < 1e-10  # Mean of 8.0 and 10.0

    def test_group_sequences_different_targets(self):
        """Test group_sequences with different target names."""
        event = SeqEvent(obj="comp1", attr="state", type="transition")
        
        seq1 = Sequence(target_name="failure_A", weight=3, events=[event])
        seq2 = Sequence(target_name="failure_B", weight=2, events=[event])
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        grouped = analyser.group_sequences(inplace=False)
        
        # Should not merge sequences with different targets
        assert grouped.nb_sequences == 2

    def test_group_sequences_different_patterns(self):
        """Test group_sequences with different event patterns."""
        event1 = SeqEvent(obj="comp1", attr="state", type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", type="failure")
        
        seq1 = Sequence(target_name="failure", weight=3, events=[event1])
        seq2 = Sequence(target_name="failure", weight=2, events=[event2])
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        grouped = analyser.group_sequences(inplace=False)
        
        # Should not merge sequences with different event patterns
        assert grouped.nb_sequences == 2

    def test_group_sequences_inplace(self):
        """Test group_sequences with inplace=True."""
        event = SeqEvent(obj="comp1", attr="state", type="transition")
        
        seq1 = Sequence(target_name="failure", weight=3, events=[event])
        seq2 = Sequence(target_name="failure", weight=2, events=[event])
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        original_id = id(analyser)
        
        result = analyser.group_sequences(inplace=True)
        
        # Should return the same object
        assert result is analyser
        assert id(result) == original_id
        
        # Should have merged sequences
        assert analyser.nb_sequences == 1
        assert analyser.sequences[0].weight == 5

    def test_group_sequences_empty_events(self):
        """Test group_sequences with sequences having no events."""
        seq1 = Sequence(target_name="failure", weight=3, events=[])
        seq2 = Sequence(target_name="failure", weight=2, events=[])
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        grouped = analyser.group_sequences(inplace=False)
        
        # Should merge empty sequences
        assert grouped.nb_sequences == 1
        assert grouped.sequences[0].weight == 5
        assert grouped.sequences[0].events == []

    def test_group_sequences_none_times(self):
        """Test group_sequences with None event times."""
        seq1 = Sequence(
            target_name="failure",
            weight=3,
            end_time=None,
            events=[SeqEvent(obj="comp1", attr="state", time=None, type="transition")]
        )
        seq2 = Sequence(
            target_name="failure",
            weight=2,
            end_time=10.0,
            events=[SeqEvent(obj="comp1", attr="state", time=5.0, type="transition")]
        )
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        grouped = analyser.group_sequences(inplace=False)
        
        # Should merge and handle None times correctly
        assert grouped.nb_sequences == 1
        merged_seq = grouped.sequences[0]
        
        # End time should be mean of non-None values
        assert merged_seq.end_time == 10.0
        
        # Event time should be mean of non-None values
        assert merged_seq.events[0].time == 5.0

    def test_rm_events_ordered_pattern(self):
        """Test rm_events_ordered_pattern method."""
        # Create sequences with events that match the pattern
        seq1 = Sequence(
            target_name="failure",
            weight=3,
            events=[
                SeqEvent(obj="comp1", attr="absent_present", type="transition"),
                SeqEvent(obj="comp2", attr="state", type="normal"),
                SeqEvent(obj="comp1", attr="present_absent", type="transition")
            ]
        )
        seq2 = Sequence(
            target_name="failure",
            weight=2,
            events=[
                SeqEvent(obj="comp3", attr="other", type="normal")
            ]
        )
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        filtered = analyser.rm_events_ordered_pattern(
            name_pat1=r"(.+)\.absent_present",
            name_pat2=r"\1\.present_absent",
            inplace=False
        )
        
        # Should have filtered and grouped sequences
        assert filtered.nb_sequences == 2
        
        # First sequence should have only the middle event
        filtered_seq1 = next(seq for seq in filtered.sequences if seq.weight == 3)
        assert len(filtered_seq1.events) == 1
        assert filtered_seq1.events[0].attr == "state"
        
        # Second sequence should be unchanged
        filtered_seq2 = next(seq for seq in filtered.sequences if seq.weight == 2)
        assert len(filtered_seq2.events) == 1
        assert filtered_seq2.events[0].attr == "other"

    def test_rm_events_ordered_pattern_inplace(self):
        """Test rm_events_ordered_pattern with inplace=True."""
        seq = Sequence(
            target_name="failure",
            weight=1,
            events=[
                SeqEvent(obj="comp1", attr="start", type="transition"),
                SeqEvent(obj="comp1", attr="end", type="transition")
            ]
        )
        
        analyser = SequenceAnalyser(sequences=[seq])
        original_id = id(analyser)
        
        result = analyser.rm_events_ordered_pattern(
            name_pat1=r"(.+)\.start",
            name_pat2=r"\1\.end",
            inplace=True
        )
        
        # Should return the same object
        assert result is analyser
        assert id(result) == original_id
        
        # Should have filtered events
        assert len(analyser.sequences[0].events) == 0

    def test_compute_minimal_sequences_basic(self):
        """Test compute_minimal_sequences with basic inclusion."""
        # Create sequences where one is included in another
        event1 = SeqEvent(obj="comp1", attr="state", type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", type="failure")
        event3 = SeqEvent(obj="comp3", attr="status", type="normal")
        
        short_seq = Sequence(
            target_name="failure",
            weight=2,
            events=[event1, event3]
        )
        long_seq = Sequence(
            target_name="failure",
            weight=3,
            events=[event1, event2, event3]
        )
        
        analyser = SequenceAnalyser(sequences=[short_seq, long_seq])
        minimal = analyser.compute_minimal_sequences(inplace=False)
        
        # Should keep only the shorter sequence with combined weight
        assert minimal.nb_sequences == 1
        assert minimal.sequences[0].weight == 5  # 2 + 3
        assert len(minimal.sequences[0].events) == 2  # Shorter sequence

    def test_compute_minimal_sequences_different_targets(self):
        """Test compute_minimal_sequences with different targets."""
        event = SeqEvent(obj="comp1", attr="state", type="transition")
        
        seq1 = Sequence(target_name="failure_A", weight=2, events=[event])
        seq2 = Sequence(target_name="failure_B", weight=3, events=[event])
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        minimal = analyser.compute_minimal_sequences(inplace=False)
        
        # Should keep both sequences (different targets)
        assert minimal.nb_sequences == 2

    def test_compute_minimal_sequences_no_inclusion(self):
        """Test compute_minimal_sequences with no inclusion relationships."""
        event1 = SeqEvent(obj="comp1", attr="state", type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", type="failure")
        
        seq1 = Sequence(target_name="failure", weight=2, events=[event1])
        seq2 = Sequence(target_name="failure", weight=3, events=[event2])
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        minimal = analyser.compute_minimal_sequences(inplace=False)
        
        # Should keep both sequences (no inclusion)
        assert minimal.nb_sequences == 2

    def test_compute_minimal_sequences_inplace(self):
        """Test compute_minimal_sequences with inplace=True."""
        event1 = SeqEvent(obj="comp1", attr="state", type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", type="failure")
        
        short_seq = Sequence(target_name="failure", weight=2, events=[event1])
        long_seq = Sequence(target_name="failure", weight=3, events=[event1, event2])
        
        analyser = SequenceAnalyser(sequences=[short_seq, long_seq])
        
        result = analyser.compute_minimal_sequences(inplace=True)
        
        # Should return None for inplace operation
        assert result is None
        
        # Should have modified the original analyser
        assert analyser.nb_sequences == 1
        assert analyser.sequences[0].weight == 5

    def test_rename_events(self):
        """Test rename_events method."""
        seq1 = Sequence(
            target_name="failure",
            weight=2,
            events=[SeqEvent(obj="old_comp1", attr="state", type="transition")]
        )
        seq2 = Sequence(
            target_name="success",
            weight=3,
            events=[SeqEvent(obj="old_comp2", attr="value", type="normal")]
        )
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        renamed = analyser.rename_events(
            attr="obj",
            pat_source=r"old_(.+)",
            pat_target=r"new_\1",
            inplace=False
        )
        
        # Should have renamed all events
        assert renamed.nb_sequences == 2
        assert renamed.sequences[0].events[0].obj == "new_comp1"
        assert renamed.sequences[1].events[0].obj == "new_comp2"
        
        # Original should be unchanged
        assert analyser.sequences[0].events[0].obj == "old_comp1"
        assert analyser.sequences[1].events[0].obj == "old_comp2"

    def test_rename_events_inplace(self):
        """Test rename_events with inplace=True."""
        seq = Sequence(
            target_name="failure",
            weight=1,
            events=[SeqEvent(obj="comp1", attr="old_state", type="transition")]
        )
        
        analyser = SequenceAnalyser(sequences=[seq])
        
        result = analyser.rename_events(
            attr="attr",
            pat_source=r"old_(.+)",
            pat_target=r"new_\1",
            inplace=True
        )
        
        # Should return None for inplace operation
        assert result is None
        
        # Should have modified the original analyser
        assert analyser.sequences[0].events[0].attr == "new_state"

    def test_to_df_long_basic(self):
        """Test to_df_long method with basic sequences."""
        event1 = SeqEvent(obj="comp1", attr="state", time=10.0, type="transition")
        event2 = SeqEvent(obj="comp2", attr="value", time=20.0, type="failure")
        
        seq1 = Sequence(
            target_name="failure",
            probability=0.6,
            weight=3,
            end_time=30.0,
            events=[event1, event2]
        )
        seq2 = Sequence(
            target_name="success",
            probability=0.4,
            weight=2,
            end_time=25.0,
            events=[event1]
        )
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        df = analyser.to_df_long()
        
        # Should have 3 rows (2 events from seq1 + 1 event from seq2)
        assert len(df) == 3
        
        # Check column names
        expected_columns = [
            'seq_idx', 'target_name', 'probability', 'weight', 'end_time',
            'event_idx', 'event_name', 'event_time', 'event_obj', 'event_type', 'event_attr'
        ]
        assert list(df.columns) == expected_columns
        
        # Check first sequence data
        seq1_rows = df[df['seq_idx'] == 0]
        assert len(seq1_rows) == 2
        assert all(seq1_rows['target_name'] == 'failure')
        assert all(seq1_rows['weight'] == 3)
        
        # Check event data
        first_event_row = seq1_rows.iloc[0]
        assert first_event_row['event_obj'] == 'comp1'
        assert first_event_row['event_attr'] == 'state'
        assert first_event_row['event_time'] == 10.0

    def test_to_df_long_empty_sequences(self):
        """Test to_df_long with sequences having no events."""
        seq = Sequence(
            target_name="empty",
            probability=1.0,
            weight=1,
            end_time=0.0,
            events=[]
        )
        
        analyser = SequenceAnalyser(sequences=[seq])
        df = analyser.to_df_long()
        
        # Should have 1 row with null event data
        assert len(df) == 1
        assert df.iloc[0]['target_name'] == 'empty'
        assert df.iloc[0]['event_idx'] is None
        assert df.iloc[0]['event_name'] is None

    def test_to_df_long_empty_analyser(self):
        """Test to_df_long with empty analyser."""
        analyser = SequenceAnalyser()
        df = analyser.to_df_long()
        
        # Should return empty DataFrame with correct columns
        assert len(df) == 0
        expected_columns = [
            'seq_idx', 'target_name', 'probability', 'weight', 'end_time',
            'event_idx', 'event_name', 'event_time', 'event_obj', 'event_type', 'event_attr'
        ]
        assert list(df.columns) == expected_columns

    def test_sequence_analyser_sorting_after_operations(self):
        """Test that sequences are sorted by weight after operations."""
        seq1 = Sequence(target_name="A", weight=2)
        seq2 = Sequence(target_name="B", weight=5)
        seq3 = Sequence(target_name="C", weight=1)
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2, seq3])
        grouped = analyser.group_sequences(inplace=False)
        
        # Should be sorted by decreasing weight
        weights = [seq.weight for seq in grouped.sequences]
        assert weights == sorted(weights, reverse=True)

    def test_sequence_analyser_probability_updates(self):
        """Test that probabilities are updated after operations."""
        seq1 = Sequence(target_name="A", weight=3)
        seq2 = Sequence(target_name="A", weight=2)
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        grouped = analyser.group_sequences(inplace=False)
        
        # Should have updated probabilities
        assert grouped.sequences[0].probability == 1.0  # Only one sequence after grouping

    def test_sequence_analyser_complex_workflow(self):
        """Test a complex workflow combining multiple operations."""
        # Create sequences with patterns that can be filtered and grouped
        seq1 = Sequence(
            target_name="failure",
            weight=3,
            events=[
                SeqEvent(obj="comp1", attr="absent_present", type="transition"),
                SeqEvent(obj="comp2", attr="state", type="normal"),
                SeqEvent(obj="comp1", attr="present_absent", type="transition")
            ]
        )
        seq2 = Sequence(
            target_name="failure",
            weight=2,
            events=[
                SeqEvent(obj="comp3", attr="absent_present", type="transition"),
                SeqEvent(obj="comp2", attr="state", type="normal"),
                SeqEvent(obj="comp3", attr="present_absent", type="transition")
            ]
        )
        
        analyser = SequenceAnalyser(sequences=[seq1, seq2])
        
        # Apply filtering and grouping
        result = (analyser
                 .rm_events_ordered_pattern(
                     name_pat1=r"(.+)\.absent_present",
                     name_pat2=r"\1\.present_absent",
                     inplace=False
                 ))
        
        # Should have grouped sequences with only middle events
        assert result.nb_sequences == 1
        assert result.sequences[0].weight == 5
        assert len(result.sequences[0].events) == 1
        assert result.sequences[0].events[0].attr == "state"
