import pydantic
import pandas as pd
import typing
import statistics
import re
import tqdm
from collections import defaultdict
from .automaton import PycTransition
from ..core import ObjCOD3S
import colored as clr


# NOTE RD:
# This class should be deprecated.
# Use Sequence object instead
# Warning: PycSequence can be still use in COD3S-API Interactive simulator
class PycSequence(ObjCOD3S):
    # Parametres
    probability: float = pydantic.Field(None, description="Sequence probability")

    nb_occurrences: int = pydantic.Field(None, description="Sequence occurrence number")

    target_event: str = pydantic.Field(None, description="Target event")

    transitions: typing.List[PycTransition] = pydantic.Field(
        [], description="Liste de transition"
    )


class SeqEvent(ObjCOD3S):
    # name: str = pydantic.Field(None, description="Event name")
    obj: str = pydantic.Field(..., description="Object hit by the event")
    attr: str = pydantic.Field(..., description="Attribute hit by the event")
    time: typing.Optional[float] = pydantic.Field(None, description="Time of occurrence")
    type: typing.Optional[str] = pydantic.Field(None, description="Event type")

    @property
    def name(self):
        """Return the full name as obj.attr."""
        if self.obj and self.attr:
            return f"{self.obj}.{self.attr}"
        elif self.obj:
            return str(self.obj)
        elif self.attr:
            return str(self.attr)
        else:
            return None

    def __repr__(self):
        """Return a concise colored string representation of an Event."""
        time_str = ""
        if self.time is not None:
            if self.time > 99999:
                time_str = clr.fg("cyan") + f" @ {self.time:8.2e}" + clr.attr("reset")
            else:
                time_str = clr.fg("cyan") + f" @ {self.time:8.2f}" + clr.attr("reset")
        obj_str = (
            clr.fg("blue") + clr.attr("bold") + str(self.obj) + clr.attr("reset")
            if self.obj
            else "?"
        )
        attr_str = (
            clr.fg("yellow") + str(self.attr) + clr.attr("reset") if self.attr else "?"
        )
        type_str = (
            clr.fg("magenta") + str(self.type) + clr.attr("reset") if self.type else "?"
        )

        return f"[{type_str}{time_str}: {obj_str}.{attr_str}]"

    def __str__(self):
        """Return a detailed colored string representation of event."""
        header = (
            clr.fg("white") + clr.attr("bold") + f"Event:" + clr.attr("reset") + "\n"
        )

        # Time information
        time_info = clr.fg("cyan") + "Time: " + clr.attr("reset")
        if self.time is not None:
            time_info += (
                clr.fg("cyan")
                + clr.attr("bold")
                + f"{self.time:.3f}"
                + clr.attr("reset")
            )
        else:
            time_info += clr.fg("red") + "Unknown" + clr.attr("reset")

        # Object information
        obj_info = clr.fg("blue") + "Object: " + clr.attr("reset")
        if self.obj:
            obj_info += (
                clr.fg("blue") + clr.attr("bold") + str(self.obj) + clr.attr("reset")
            )
        else:
            obj_info += clr.fg("red") + "Unknown" + clr.attr("reset")

        # Attribute information
        attr_info = clr.fg("yellow") + "Attribute: " + clr.attr("reset")
        if self.attr:
            attr_info += (
                clr.fg("yellow") + clr.attr("bold") + str(self.attr) + clr.attr("reset")
            )
        else:
            attr_info += clr.fg("red") + "Unknown" + clr.attr("reset")

        # Type information
        type_info = clr.fg("magenta") + "Type: " + clr.attr("reset")
        if self.type:
            type_info += (
                clr.fg("magenta")
                + clr.attr("bold")
                + str(self.type)
                + clr.attr("reset")
            )
        else:
            type_info += clr.fg("red") + "Unknown" + clr.attr("reset")

        return f"{header}{time_info}\n{obj_info}\n{attr_info}\n{type_info}"

    def __eq__(self, other):
        """Check if two events are equal based on obj, attr, and type attributes.

        Args:
            other (Event): The other event to compare with

        Returns:
            bool: True if events have the same obj, attr, and type
        """
        if not isinstance(other, SeqEvent):
            return False
        return (
            self.obj == other.obj
            and self.attr == other.attr
            and self.type == other.type
        )

    def rename(self, attr, pat_source, pat_target, inplace=False):
        """Rename event attribute using regex pattern replacement.

        Args:
            attr (str): Event attribute to rename ('name', 'obj', 'type', 'attr')
            pat_source (str): Source regex pattern to match
            pat_target (str): Target replacement pattern
            inplace (bool): If True, modify this event. If False, return a new event.

        Returns:
            Event: The modified event if inplace=True, otherwise a new event.

        Raises:
            ValueError: If attr is 'time' or not a valid event attribute
        """
        # Validate attribute name
        valid_attrs = ["obj", "type", "attr"]
        if attr == "time":
            raise ValueError("Cannot rename 'time' attribute")
        if attr not in valid_attrs:
            raise ValueError(
                f"Invalid attribute '{attr}'. Must be one of: {valid_attrs}"
            )

        # Work on a copy if not inplace
        if not inplace:
            result = SeqEvent(
                obj=self.obj,
                attr=self.attr,
                time=self.time,
                type=self.type,
            )
        else:
            result = self

        # Get current value of the attribute
        current_value = getattr(result, attr)

        # Apply regex replacement if current value is not None
        if current_value is not None:
            new_value = re.sub(pat_source, pat_target, str(current_value))
            setattr(result, attr, new_value)

        return result


class Sequence(ObjCOD3S):
    # Parametres
    probability: typing.Optional[float] = pydantic.Field(None, description="Sequence probability")
    weight: int = pydantic.Field(1, description="Sequence weight")

    end_time: typing.Optional[float] = pydantic.Field(None, description="Sequence end time")

    target_name: typing.Optional[str] = pydantic.Field(None, description="Target event")

    events: typing.List[SeqEvent] = pydantic.Field([], description="Event list")

    def __repr__(self):
        """Return a concise colored string representation of sequence based on __repr__ method of Event."""
        # Sequence header with probability and target

        weight_str = (
            clr.fg("green") + f"{self.weight}" + clr.attr("reset")
            if self.weight is not None
            else ""
        )

        prob_str = (
            clr.fg("green") + f"{self.probability:5.2%}" + clr.attr("reset")
            if self.probability is not None
            else ""
        )

        target_str = (
            clr.fg("dark_orange")
            + clr.attr("bold")
            + str(self.target_name)
            + clr.attr("reset")
            if self.target_name
            else "None"
        )

        end_time_str = (
            clr.fg("cyan") + f" @ {self.end_time:.2f}" + clr.attr("reset")
            if self.end_time is not None
            else "None"
        )

        # Events summary
        events_count = len(self.events)
        events_str = clr.fg("white") + f"[{events_count} events]" + clr.attr("reset")

        # All events for preview
        events_str = ""
        if self.events:
            events_repr = [repr(event) for event in self.events]
            events_str = " → ".join(events_repr)

        return f"{target_str}{end_time_str} ({weight_str} | {prob_str}): {events_str}"

    def __str__(self):
        """Return a detailed colored string representation of sequence with each event on its own line."""
        # Target header
        target_display = (
            clr.fg("dark_orange")
            + clr.attr("bold")
            + str(self.target_name)
            + clr.attr("reset")
            if self.target_name
            else clr.fg("grey_0") + "None" + clr.attr("reset")
        )
        target_line = clr.fg("white") + "Target: " + clr.attr("reset") + target_display

        # End time line
        end_time_display = (
            clr.fg("cyan") + f"{self.end_time:.2f}" + clr.attr("reset")
            if self.end_time is not None
            else clr.fg("grey_0") + "None" + clr.attr("reset")
        )
        end_time_line = (
            clr.fg("white") + "End time: " + clr.attr("reset") + end_time_display
        )

        # Weight line
        weight_display = (
            clr.fg("green") + f"{self.weight}" + clr.attr("reset")
            if self.weight is not None
            else clr.fg("grey_0") + "None" + clr.attr("reset")
        )
        weight_line = clr.fg("white") + "Weight: " + clr.attr("reset") + weight_display

        # Probability line
        prob_display = (
            clr.fg("green") + f"{self.probability:5.2%}" + clr.attr("reset")
            if self.probability is not None
            else clr.fg("grey_0") + "None" + clr.attr("reset")
        )
        prob_line = clr.fg("white") + "Probability: " + clr.attr("reset") + prob_display

        # Events details - each event on its own line
        if not self.events:
            events_section = "\n" + clr.fg("grey_0") + "(no events)" + clr.attr("reset")
        else:
            events_lines = []
            for i, event in enumerate(self.events):
                event_line = f"  {i+1:2d}. {repr(event)}"
                events_lines.append(event_line)
            events_section = "\n" + "\n".join(events_lines)

        return f"{target_line}\n{end_time_line}\n{weight_line}\n{prob_line}{events_section}"

    def is_included(self, other_sequence):
        """Check if this sequence is included in another sequence.

        A sequence is included in sequence other_sequence if all events of sequence appear
        in other_sequence in the same order (but not necessarily consecutively).

        Args:
            other_sequence (Sequence): The sequence to check inclusion in

        Returns:
            bool: True if this sequence is included in other_sequence
        """
        if not self.events:
            return True  # Empty sequence is included in any sequence

        if len(self.events) > len(other_sequence.events):
            return False  # Cannot be included if longer

        # Check if all events of self appear in other_sequence in order
        self_idx = 0
        other_idx = 0

        while self_idx < len(self.events) and other_idx < len(other_sequence.events):
            self_event = self.events[self_idx]
            other_event = other_sequence.events[other_idx]

            # Check if events match (same obj, attr, type)
            if self_event == other_event:
                self_idx += 1

            other_idx += 1

        # All events of self were found in other_sequence
        return self_idx == len(self.events)

    def rm_events_ordered_pattern(self, name_pat1, name_pat2, inplace=False):
        """Remove ordered events matching specific name patterns.

        For each event E, if E.name matches name_pat1, look at the following events.
        As soon as a following event E' matches name_pat2, remove both E and E' from
        the resulting sequence. Events between E and E' are kept. If no match for
        event E, keep it in the resulting sequence. Then continue with the next
        non-removed event in the sequence.

        This method is useful for removing transient state changes, such as removing
        pairs of "absent→present" and "present→absent" events for the same component.
        Note: Events don't need to be strictly consecutive - intermediate events are preserved.

        Args:
            name_pat1 (str): Regular expression pattern for the first event
            name_pat2 (str): Regular expression pattern for the consecutive event
            inplace (bool): If True, modify this sequence. If False, return a new sequence.

        Returns:
            Sequence: The modified sequence if inplace=True, otherwise a new sequence.

        Example:
            Remove transient state changes for components that go absent then present:

            >>> # Remove events where a component becomes absent then present again
            >>> sequence.remove_events_wr_consecutive_name_pattern(
            ...     name_pat1=r"(.+)_absent_present",
            ...     name_pat2=r"\1_present_absent"
            ... )

            This will remove pairs of events like:
            - "ComponentA_absent_present" followed by "ComponentA_present_absent"
            - "ComponentB_absent_present" followed by "ComponentB_present_absent"

            The regex pattern uses capturing groups to ensure the same component
            name is matched in both patterns.
        """
        # Work on a copy if not inplace
        if not inplace:
            result = Sequence(
                probability=self.probability,
                weight=self.weight,
                end_time=self.end_time,
                target_name=self.target_name,
                events=[],
            )
        else:
            result = self

        events_pool = [ev for ev in self.events]

        filtered_events = []

        while len(events_pool) > 0:
            current_event = events_pool.pop(0)
            # Check if current event matches name_pat1
            match1 = (
                re.search(name_pat1, current_event.name) if current_event.name else None
            )
            if match1:
                # Look for a following event that matches name_pat2
                found_match = False

                # Substitute captured groups from first match into second pattern
                try:
                    name_pat2_substituted = match1.expand(name_pat2)
                except re.error:
                    # If substitution fails, use pattern as-is
                    name_pat2_substituted = name_pat2

                for i, following_event in enumerate(events_pool):

                    if following_event.name and re.search(
                        name_pat2_substituted, following_event.name
                    ):
                        # Found a match, skip both events (current and following)
                        found_match = True
                        events_pool.pop(i)
                        break

                if not found_match:
                    # No matching following event found, keep the current event
                    filtered_events.append(current_event)
            else:
                # Current event doesn't match name_pat1, keep it
                filtered_events.append(current_event)

        # Update events
        result.events = filtered_events

        return result

    def rename_events(self, attr, pat_source, pat_target, inplace=False):
        """Rename events of the sequence using Event.rename method.

        Args:
            attr (str): Event attribute to rename ('name', 'obj', 'type', 'attr')
            pat_source (str): Source regex pattern to match
            pat_target (str): Target replacement pattern
            inplace (bool): If True, modify this sequence. If False, return a new sequence.

        Returns:
            Sequence: The modified sequence if inplace=True, otherwise a new sequence.
        """
        if inplace:
            for event in self.events:
                event.rename(
                    attr=attr,
                    pat_source=pat_source,
                    pat_target=pat_target,
                    inplace=True,
                )

        else:
            renamed_events = []
            for event in self.events:
                renamed_event = event.rename(
                    attr=attr,
                    pat_source=pat_source,
                    pat_target=pat_target,
                    inplace=False,
                )
                renamed_events.append(renamed_event)

            result = Sequence(
                probability=self.probability,
                weight=self.weight,
                end_time=self.end_time,
                target_name=self.target_name,
                events=renamed_events,
            )
            return result


class SequenceAnalyser(ObjCOD3S):

    # nb_sequences_ori: int = pydantic.Field(0, description="Original number of sequences")
    sequences: typing.List[Sequence] = pydantic.Field([], description="Sequence list")

    @property
    def nb_sequences(self) -> int:
        """Get the number of sequences in the analyser."""
        return len(self.sequences)

    @property
    def weight_total(self) -> int:
        """Get the number of sequences in the analyser."""
        return sum(seq.weight for seq in self.sequences)

    @property
    def target_stats(self) -> dict:
        """Get information about targets.

        Returns:
            dict: Dictionary where keys are target names and values are dictionaries with:
                - count: Number of sequences for this target
                - weight: Total weight of sequences for this target
                - probability: Total weight of target sequences / weight_total of all sequences
        """
        stats = {}
        total_weight = self.weight_total

        for seq in self.sequences:
            target_name = seq.target_name if seq.target_name else ""

            if target_name not in stats:
                stats[target_name] = {
                    "nb_sequences": 0,
                    "weight": 0,
                    "probability": 0.0,
                }

            stats[target_name]["nb_sequences"] += 1
            stats[target_name]["weight"] += seq.weight

        # Calculate probabilities
        for target_name, t_stats in stats.items():
            if total_weight > 0:
                t_stats["probability"] = t_stats["weight"] / total_weight
            else:
                t_stats["probability"] = 0.0

        return stats

    # @property
    # def probability(self) -> float:
    #     """Get occurrence probability of current sequences"""
    #     return (
    #         sum(seq.weight for seq in self.sequences) / self.count
    #         if self.count > 0
    #         else None
    #     )

    def __repr__(self):
        """Return a one liner colored string representation of SequenceAnalyser."""

        # Header with total sequences
        header = (
            clr.fg("blue")
            + clr.attr("bold")
            + "SequenceAnalyser"
            + clr.attr("reset")
            + ": "
            + clr.fg("white")
            + f"#seq: {self.nb_sequences}"
            + clr.attr("reset")
            + " | "
            + clr.fg("green")
            + f"w: {self.weight_total}"
            + clr.attr("reset")
        )
        # Build target information strings using target_stats property
        target_info_list = []
        for target_name, stats in self.target_stats.items():
            nb_sequences = stats["nb_sequences"]
            weight = stats["weight"]
            probability = stats["probability"]

            target_str = (
                clr.fg("dark_orange")
                + clr.attr("bold")
                + target_name
                + clr.attr("reset")
                + ": ("
                + clr.fg("white")
                + f"#: {nb_sequences}"
                + clr.attr("reset")
                + ", "
                + clr.fg("green")
                + f"w: {weight}"
                + clr.attr("reset")
                + ", "
                + clr.fg("yellow")
                + f"%: {probability*100:.1f}"
                + clr.attr("reset")
                + ")"
            )
            target_info_list.append(target_str)

        # Combine all information
        if target_info_list:
            targets_str = " [" + ", ".join(target_info_list) + "]"
        else:
            targets_str = " []"

        return header + targets_str

    def __str__(self):
        """Return a detailed colored string representation of SequenceAnalyser."""
        # Header
        header = (
            clr.fg("blue")
            + clr.attr("bold")
            + "SequenceAnalyser"
            + clr.attr("reset")
            + "\n"
        )

        # Summary information
        summary = (
            clr.fg("white")
            + "Total sequences: "
            + clr.attr("reset")
            + clr.fg("cyan")
            + f"{self.nb_sequences}"
            + clr.attr("reset")
            + "\n"
            + clr.fg("white")
            + "Total weight: "
            + clr.attr("reset")
            + clr.fg("green")
            + f"{self.weight_total}"
            + clr.attr("reset")
            + "\n"
        )

        # Target statistics using target_stats property
        target_lines = []
        for target_name, stats in self.target_stats.items():
            count = stats["nb_sequences"]
            weight = stats["weight"]
            probability = stats["probability"]

            target_line = (
                clr.fg("dark_orange")
                + clr.attr("bold")
                + f"  {target_name}:"
                + clr.attr("reset")
                + f" sequences={count}, weight={weight}, probability={probability:.2%}"
            )
            target_lines.append(target_line)

        targets_section = (
            "\n".join(target_lines)
            if target_lines
            else clr.fg("gray") + "  (no targets)" + clr.attr("reset")
        )

        return f"{header}{summary}\nTargets:\n{targets_section}"

    @classmethod
    def from_pyc_system(cls, system, end_cause_default="Normal"):
        """Create a SequenceAnalyser from a pyc.CAnalyser object.

        Args:
            analyser: A pyc.CAnalyser object containing sequence data

        Returns:
            SequenceAnalyser: A new instance with sequences extracted from the analyser
        """
        sequence_analyser = cls()

        for seq_raw in system.sequences():
            events = []
            for i_br in range(seq_raw.branchCount()):
                br_cur = seq_raw.branch(i_br)
                br_time = br_cur.time()
                # __import__("ipdb").set_trace()

                br_elts = br_cur.monitoredElts()
                for i_ev in range(len(br_elts)):
                    ev_raw = br_elts[i_ev]
                    ev = SeqEvent(
                        time=br_time,
                        obj=ev_raw.parent().name(),
                        attr=ev_raw.basename(),
                        type=ev_raw.type(),
                    )
                    events.append(ev)

            end_cause = seq_raw.endCause()
            sequence = Sequence(
                target_name=end_cause if end_cause else end_cause_default,
                end_time=seq_raw.endTime(),
                weight=1,
                events=events,
            )
            sequence_analyser.sequences.append(sequence)

        sequence_analyser.update_probs()

        return sequence_analyser

    def show_sequences(
        self, max_sequences=None, max_event_width=None, max_events=None, targets=None
    ):
        """Pretty display sequences with vertically aligned events.

        Args:
            max_sequences: Maximum number of sequences to display (None for all)
            max_event_width: Maximum width for event display (None for no limit)
            max_events: Maximum number of events to display per sequence (default: 3)
            targets: List of regex patterns to filter sequences by target name (None for all)
        """
        # Filter sequences by target patterns if provided
        if targets:
            filtered_sequences = []
            for seq in self.sequences:
                target_name = seq.target_name if seq.target_name else ""
                if any(re.search(pattern, target_name) for pattern in targets):
                    filtered_sequences.append(seq)
            sequences_to_filter = filtered_sequences
        else:
            sequences_to_filter = self.sequences

        sequences_to_show = (
            sequences_to_filter[:max_sequences]
            if max_sequences
            else sequences_to_filter
        )

        if not sequences_to_show:
            print(clr.fg("grey_50") + "No sequences to display" + clr.attr("reset"))
            return

        # Calculate column widths
        col_widths = {
            "idx": max(3, len(str(len(sequences_to_show)))),
            "target": max(
                10, max(len(str(seq.target_name or "")) for seq in sequences_to_show)
            ),
            "weight": max(6, max(len(str(seq.weight)) for seq in sequences_to_show)),
            "prob": 7,  # Fixed width for percentage
            "end_time": max(
                8,
                max(
                    len(f"{seq.end_time:.2f}" if seq.end_time else "N/A")
                    for seq in sequences_to_show
                ),
            ),
            "events": max_event_width if max_event_width else 999,
        }

        # Print header
        header = (
            f"{'#':<{col_widths['idx']}} │ "
            f"{'Target':<{col_widths['target']}} │ "
            f"{'Weight':>{col_widths['weight']}} │ "
            f"{'Prob':>{col_widths['prob']}} │ "
            f"{'End Time':>{col_widths['end_time']}} │ "
            f"{'Events':<{col_widths['events']}}"
        )

        separator = "─" * len(header)

        print(clr.fg("white") + clr.attr("bold") + header + clr.attr("reset"))
        print(separator)

        # Print sequences
        for idx, seq in enumerate(sequences_to_show):
            # Format sequence data
            idx_str = f"{idx:<{col_widths['idx']}}"
            target_str = f"{seq.target_name or 'None':<{col_widths['target']}}"
            weight_str = f"{seq.weight:>{col_widths['weight']}}"
            prob_str = (
                f"{seq.probability*100:>5.1f}%"
                if seq.probability is not None
                else "   N/A"
            )
            end_time_str = (
                f"{seq.end_time:>{col_widths['end_time']}.2f}"
                if seq.end_time is not None
                else f"{'N/A':>{col_widths['end_time']}}"
            )

            # Format events
            if seq.events:
                # Limit number of events displayed
                events_to_display = (
                    seq.events[:max_events] if max_events else seq.events
                )
                events_repr = [repr(event) for event in events_to_display]

                # Add ellipsis if there are more events
                if max_events and len(seq.events) > max_events:
                    events_repr.append(
                        clr.fg("grey_50")
                        + f"... (+{len(seq.events) - max_events} more)"
                        + clr.attr("reset")
                    )

                events_str = " → ".join(events_repr)

                # Truncate if too long and max_event_width is specified
                if max_event_width and len(events_str) > max_event_width:
                    events_str = events_str[: max_event_width - 3] + "..."
            else:
                events_str = clr.fg("grey_50") + "(no events)" + clr.attr("reset")

            # Print row
            print(
                f"{idx_str} │ "
                f"{clr.fg('dark_orange')}{target_str}{clr.attr('reset')} │ "
                f"{clr.fg('green')}{weight_str}{clr.attr('reset')} │ "
                f"{clr.fg('yellow')}{prob_str}{clr.attr('reset')} │ "
                f"{clr.fg('cyan')}{end_time_str}{clr.attr('reset')} │ "
                f"{events_str}"
            )

        # Print summary if not all sequences shown
        if max_sequences and len(sequences_to_filter) > max_sequences:
            remaining = len(sequences_to_filter) - max_sequences
            print(separator)
            print(
                clr.fg("grey_50")
                + f"... and {remaining} more sequences"
                + clr.attr("reset")
            )

    def update_probs(self):

        for seq in self.sequences:
            seq.probability = (
                seq.weight / self.weight_total if self.weight_total > 0 else None
            )

    def group_sequences(self, inplace=False, progress=False):
        """Group sequences by target_name and merge identical event patterns.

        For each target_name, merge sequences that have exactly the same events
        in the same order (ignoring event times). After merging, the resulting
        sequence has a weight equal to the sum of merged sequences. The resulting
        time for each event is the mean of event times from merged sequences.

        Args:
            inplace (bool): If True, modify this instance. If False, return a new instance.

        Returns:
            SequenceAnalyser: The modified instance if inplace=True, otherwise a new instance.
        """
        # Work on a copy if not inplace
        if not inplace:
            result = SequenceAnalyser(sequences=[])
        else:
            result = self

        # Group sequences by target_name
        sequences_by_target = defaultdict(list)
        for seq in tqdm.tqdm(
            self.sequences, disable=not progress, desc="Rearranging sequences"
        ):
            sequences_by_target[seq.target_name].append(seq)

        grouped_sequences = []

        for target_name, target_sequences in tqdm.tqdm(
            sequences_by_target.items(), disable=not progress, desc="Target"
        ):
            # Group sequences by their event signature (ignoring times)
            signature_groups = defaultdict(list)

            for seq in tqdm.tqdm(
                target_sequences, disable=not progress, desc="Sequences"
            ):
                # Create signature: list of (obj, attr, type) tuples
                signature = tuple(
                    (event.obj, event.attr, event.type) for event in seq.events
                )
                signature_groups[signature].append(seq)

            # Merge sequences with same signature
            for signature, sequences_to_merge in signature_groups.items():
                if len(sequences_to_merge) == 1:
                    # No merging needed
                    grouped_sequences.append(sequences_to_merge[0])
                else:
                    # Merge sequences
                    merged_weight = sum(seq.weight for seq in sequences_to_merge)

                    # Calculate mean times for each event position
                    merged_events = []
                    if sequences_to_merge[0].events:  # Check if there are events
                        num_events = len(sequences_to_merge[0].events)

                        for event_idx in range(num_events):
                            # Get all times for this event position
                            event_times = [
                                seq.events[event_idx].time
                                for seq in sequences_to_merge
                                if seq.events[event_idx].time is not None
                            ]

                            # Calculate mean time
                            mean_time = (
                                statistics.mean(event_times) if event_times else None
                            )

                            # Create merged event using first sequence as template
                            template_event = sequences_to_merge[0].events[event_idx]
                            merged_event = SeqEvent(
                                time=mean_time,
                                obj=template_event.obj,
                                type=template_event.type,
                                attr=template_event.attr,
                            )
                            merged_events.append(merged_event)

                    # Calculate mean end time
                    end_times = [
                        seq.end_time
                        for seq in sequences_to_merge
                        if seq.end_time is not None
                    ]
                    mean_end_time = statistics.mean(end_times) if end_times else None

                    # Create merged sequence
                    merged_sequence = Sequence(
                        target_name=target_name,
                        end_time=mean_end_time,
                        weight=merged_weight,
                        events=merged_events,
                    )

                    grouped_sequences.append(merged_sequence)

        # Update sequences
        result.sequences = grouped_sequences

        # Sort sequences by decreasing weights
        result.sequences.sort(key=lambda seq: seq.weight, reverse=True)

        # Update probabilities
        result.update_probs()

        return result

    def rm_events_ordered_pattern(
        self, name_pat1, name_pat2, inplace=False, progress=False
    ):
        """Remove ordered events matching specific name patterns from all sequences.

        Apply rm_events_ordered_pattern to each sequence in the analyser, then
        group the resulting sequences to merge identical patterns.

        Args:
            name_pat1 (str): Regular expression pattern for the first event
            name_pat2 (str): Regular expression pattern for the consecutive event
            inplace (bool): If True, modify this instance. If False, return a new instance.

        Returns:
            SequenceAnalyser: The modified instance if inplace=True, otherwise a new instance.
        """
        # Work on a copy if not inplace
        if not inplace:
            result = SequenceAnalyser(sequences=[])
        else:
            result = self

        # Apply rm_events_ordered_pattern to each sequence
        filtered_sequences = []
        for sequence in tqdm.tqdm(
            self.sequences, disable=not progress, desc="Filtering events"
        ):
            filtered_sequence = sequence.rm_events_ordered_pattern(
                name_pat1=name_pat1, name_pat2=name_pat2, inplace=False
            )
            filtered_sequences.append(filtered_sequence)

        # Update sequences with filtered ones
        result.sequences = filtered_sequences

        # Group sequences to merge identical patterns after filtering
        result = result.group_sequences(inplace=True)

        return result

    def compute_minimal_sequences(self, inplace=False, progress=False):
        """Compute minimal sequences by removing sequences that are included in shorter ones.

        For each target, scan all sequences by increasing length. From a given sequence S
        of length k, scan all following sequences Sfollow of length > k. If Sfollow
        contains the same events as S in the same order (Sfollow is included in S),
        drop Sfollow and add its weight into S.

        Args:
            inplace (bool): If True, modify this instance. If False, return a new instance.

        Returns:
            SequenceAnalyser: The modified instance if inplace=True, otherwise a new instance.
        """
        # Work on a copy if not inplace
        if not inplace:
            result = SequenceAnalyser(
                sequences=[],
            )
        else:
            result = self

        # Group sequences by target_name
        sequences_by_target = defaultdict(list)
        for seq in self.sequences:
            sequences_by_target[seq.target_name].append(seq if inplace else seq.model_copy())

        minimal_sequences = []

        for target_name, target_sequences in sequences_by_target.items():
            # Sort sequences by length (number of events)
            target_sequences.sort(key=lambda seq: len(seq.events))
            kept_sequences = []

            with tqdm.tqdm(
                total=len(target_sequences),
                disable=not progress,
                desc=f"Processing {target_name}",
            ) as pbar:
                while len(target_sequences) > 0:
                    seq_short = target_sequences.pop(0)
                    seq_idx = 0
                    while seq_idx < len(target_sequences):
                        seq_test = target_sequences[seq_idx]
                        if seq_short.is_included(seq_test):
                            # This sequence is included in a shorter one, merge weights
                            seq_short.weight += seq_test.weight
                            target_sequences.pop(seq_idx)
                        else:
                            seq_idx += 1

                    kept_sequences.append(seq_short)
                    pbar.update(1)

            minimal_sequences.extend(kept_sequences)

        minimal_sequences.sort(key=lambda seq: seq.weight, reverse=True)
        result.sequences = minimal_sequences
        result.update_probs()

        if not inplace:
            return result

    def rename_events(self, attr, pat_source, pat_target, inplace=False):
        """Rename events in all sequences using Sequence.rename_events method.

        Apply rename_events to each sequence in the analyser to rename event attributes
        based on regex patterns.

        Args:
            attr (str): Event attribute to rename ('name', 'obj', 'type', 'attr')
            pat_source (str): Source regex pattern to match
            pat_target (str): Target replacement pattern
            inplace (bool): If True, modify this instance. If False, return a new instance.

        Returns:
            SequenceAnalyser: The modified instance if inplace=True, otherwise a new instance.
        """
        # Work on a copy if not inplace
        if inplace:
            result = self

            for sequence in self.sequences:
                sequence.rename_events(
                    attr=attr,
                    pat_source=pat_source,
                    pat_target=pat_target,
                    inplace=True,
                )

        else:
            renamed_sequences = []
            for sequence in self.sequences:
                renamed_sequence = sequence.rename_events(
                    attr=attr,
                    pat_source=pat_source,
                    pat_target=pat_target,
                    inplace=False,
                )
                renamed_sequences.append(renamed_sequence)
            result = SequenceAnalyser(sequences=renamed_sequences)

            return result

    def to_df_long(self):
        """Return a DataFrame of sequences in long format where each row is an event.

        Returns:
            pd.DataFrame: DataFrame with columns:
                - seq_idx: Sequence index (same for all events in a sequence)
                - target_name: Target name (repeated for each event in sequence)
                - probability: Sequence probability (repeated for each event in sequence)
                - weight: Sequence weight (repeated for each event in sequence)
                - end_time: Sequence end time (repeated for each event in sequence)
                - event_idx: Event index within the sequence
                - event_name: Event name
                - event_time: Event time
                - event_obj: Event object
                - event_type: Event type
                - event_attr: Event attribute
        """

        # Define columns to ensure they exist even for empty DataFrame
        columns = [
            'seq_idx', 'target_name', 'probability', 'weight', 'end_time',
            'event_idx', 'event_name', 'event_time', 'event_obj', 'event_type', 'event_attr'
        ]

        data = []

        for seq_idx, sequence in enumerate(self.sequences):
            # Sequence-level information that will be repeated for each event
            seq_info = {
                "seq_idx": seq_idx,
                "target_name": sequence.target_name,
                "probability": sequence.probability,
                "weight": sequence.weight,
                "end_time": sequence.end_time,
            }

            # If sequence has no events, add one row with sequence info and null event info
            if not sequence.events:
                event_info = {
                    "event_idx": None,
                    "event_name": None,
                    "event_time": None,
                    "event_obj": None,
                    "event_type": None,
                    "event_attr": None,
                }
                data.append({**seq_info, **event_info})
            else:
                # Add one row for each event in the sequence
                for event_idx, event in enumerate(sequence.events):
                    event_info = {
                        "event_idx": f"evt_{event_idx:04}",
                        "event_name": event.name,
                        "event_time": event.time,
                        "event_obj": event.obj,
                        "event_type": event.type,
                        "event_attr": event.attr,
                    }
                    data.append({**seq_info, **event_info})

        return pd.DataFrame(data, columns=columns)


# Parser
# import xml.etree.ElementTree as ET
# from pyc_sequences import *


# # Read Sequences
# def parse_sequences(xml_file_path):
#     sequences_list = []

#     tree = ET.parse(xml_file_path)
#     root = tree.getroot()
#     for seq in root.findall("SEQ"):
#         probability = seq.get('P')
#         number_instance = seq.get('N')
#         endCause = None

#         transitions = []
#         for branch in seq.findall("BR"):
#             branch_time = seq.get('T')
#             for branch_tr in branch.findall("TR"):
#                 tr_name = branch_tr.get('NAME')
#                 tr_final_state = branch_tr.get('ST')
#                 tr_law = branch_tr.get('TD')
#                 transition = create_transition(tr_name, tr_final_state, branch_time, tr_law)
#                 transitions.append(transition)

#                 endCause = tr_final_state

#         sequence = create_sequence(probability, number_instance, endCause, transitions)
#         sequences_list.append(sequence)

#     return sequences_list


# def create_transition(name, state, time, law):
#     transition = TransitionModel(name=name,
#                                       state=state,
#                                       time=time,
#                                       law=law)
#     return transition


# def create_sequence(probability, nb_occurrences, target_event, transitions):
#     sequence = SequenceModel(probability=probability,
#                                       nb_occurrences=nb_occurrences,
#                                       target_event=target_event)

#     for transition in transitions:
#         sequence.transitions.append(transition)

#     return sequence
