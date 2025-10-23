import pytest
import re
from cod3s.pycatshoo.sequence import SeqEvent


class TestSeqEvent:
    """Test class for SeqEvent object."""

    def test_seqevent_creation(self):
        """Test basic SeqEvent creation."""
        event = SeqEvent(
            obj="component1",
            attr="state",
            time=10.5,
            type="transition"
        )
        
        assert event.obj == "component1"
        assert event.attr == "state"
        assert event.time == 10.5
        assert event.type == "transition"

    def test_seqevent_name_property(self):
        """Test the name property of SeqEvent."""
        # Test with both obj and attr
        event = SeqEvent(obj="comp1", attr="state")
        assert event.name == "comp1.state"
        
        # Test with only obj
        event = SeqEvent(obj="comp1", attr="")
        assert event.name == "comp1"
        
        # Test with only attr
        event = SeqEvent(obj="", attr="state")
        assert event.name == "state"
        
        # Test with neither
        event = SeqEvent(obj="", attr="")
        assert event.name is None

    def test_seqevent_equality(self):
        """Test SeqEvent equality comparison."""
        event1 = SeqEvent(obj="comp1", attr="state", type="transition", time=10.0)
        event2 = SeqEvent(obj="comp1", attr="state", type="transition", time=20.0)
        event3 = SeqEvent(obj="comp2", attr="state", type="transition", time=10.0)
        event4 = SeqEvent(obj="comp1", attr="value", type="transition", time=10.0)
        event5 = SeqEvent(obj="comp1", attr="state", type="failure", time=10.0)
        
        # Same obj, attr, type (time should not matter)
        assert event1 == event2
        
        # Different obj
        assert event1 != event3
        
        # Different attr
        assert event1 != event4
        
        # Different type
        assert event1 != event5
        
        # Not equal to non-SeqEvent object
        assert event1 != "not an event"
        assert event1 != 42

    def test_seqevent_rename_obj(self):
        """Test renaming obj attribute."""
        event = SeqEvent(obj="component_old", attr="state", type="transition")
        
        # Test inplace=False (default)
        renamed_event = event.rename("obj", r"component_old", "component_new")
        assert renamed_event.obj == "component_new"
        assert event.obj == "component_old"  # Original unchanged
        assert renamed_event is not event  # Different object
        
        # Test inplace=True
        event.rename("obj", r"component_old", "component_new", inplace=True)
        assert event.obj == "component_new"

    def test_seqevent_rename_attr(self):
        """Test renaming attr attribute."""
        event = SeqEvent(obj="comp1", attr="old_state", type="transition")
        
        renamed_event = event.rename("attr", r"old_state", "new_state")
        assert renamed_event.attr == "new_state"
        assert event.attr == "old_state"  # Original unchanged

    def test_seqevent_rename_type(self):
        """Test renaming type attribute."""
        event = SeqEvent(obj="comp1", attr="state", type="old_type")
        
        renamed_event = event.rename("type", r"old_type", "new_type")
        assert renamed_event.type == "new_type"
        assert event.type == "old_type"  # Original unchanged

    def test_seqevent_rename_regex_patterns(self):
        """Test renaming with regex patterns."""
        event = SeqEvent(obj="component_123", attr="state", type="transition")
        
        # Test regex substitution
        renamed_event = event.rename("obj", r"component_(\d+)", r"comp_\1")
        assert renamed_event.obj == "comp_123"

    def test_seqevent_rename_invalid_attr(self):
        """Test renaming with invalid attributes."""
        event = SeqEvent(obj="comp1", attr="state", type="transition")
        
        # Test renaming time (should raise ValueError)
        with pytest.raises(ValueError, match="Cannot rename 'time' attribute"):
            event.rename("time", "old", "new")
        
        # Test invalid attribute name
        with pytest.raises(ValueError, match="Invalid attribute 'invalid'"):
            event.rename("invalid", "old", "new")

    def test_seqevent_rename_none_value(self):
        """Test renaming when attribute value is None."""
        event = SeqEvent(obj="comp1", attr="state")  # type will be None by default
        
        # Should not raise error and should not change None value
        renamed_event = event.rename("type", "old", "new")
        assert renamed_event.type is None

    def test_seqevent_repr(self):
        """Test SeqEvent string representation."""
        event = SeqEvent(
            obj="comp1",
            attr="state",
            time=10.5,
            type="transition"
        )
        
        repr_str = repr(event)
        # Should contain key information
        assert "comp1" in repr_str
        assert "state" in repr_str
        assert "10.5" in repr_str or "10.50" in repr_str
        assert "transition" in repr_str

    def test_seqevent_str(self):
        """Test SeqEvent detailed string representation."""
        event = SeqEvent(
            obj="comp1",
            attr="state",
            time=10.5,
            type="transition"
        )
        
        str_repr = str(event)
        # Should contain detailed information
        assert "Event:" in str_repr
        assert "Time:" in str_repr
        assert "Object:" in str_repr
        assert "Attribute:" in str_repr
        assert "Type:" in str_repr

    def test_seqevent_with_missing_fields(self):
        """Test SeqEvent with some missing fields."""
        # Only required fields
        event = SeqEvent(obj="comp1", attr="state")
        assert event.obj == "comp1"
        assert event.attr == "state"
        assert event.time is None
        assert event.type is None
        
        # Test name property with missing fields
        assert event.name == "comp1.state"

    def test_seqevent_copy_behavior_in_rename(self):
        """Test that rename creates proper copies of all attributes."""
        original_event = SeqEvent(
            obj="comp1",
            attr="state",
            time=15.0,
            type="failure"
        )
        
        renamed_event = original_event.rename("obj", "comp1", "comp2", inplace=False)
        
        # Check that all attributes are properly copied
        assert renamed_event.obj == "comp2"
        assert renamed_event.attr == original_event.attr
        assert renamed_event.time == original_event.time
        assert renamed_event.type == original_event.type
        
        # Ensure original is unchanged
        assert original_event.obj == "comp1"
