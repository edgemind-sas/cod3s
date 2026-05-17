"""Shared fixtures for the ``cod3s-seq`` test suite.

These fixtures build synthetic :class:`SequenceAnalyser` instances —
no PyCATSHOO involvement — so the suite stays fast and the TUI tests
don't fight the PyCATSHOO singleton.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cod3s.pycatshoo.seq_tui.state import SeqTuiState
from cod3s.pycatshoo.sequence import SeqEvent, Sequence, SequenceAnalyser


def make_analyser(*seq_specs) -> SequenceAnalyser:
    """Build a :class:`SequenceAnalyser` from compact tuples.

    Each ``seq_spec`` is ``(target_name, weight, [(obj, attr, time), ...])``.
    """
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


@pytest.fixture
def sample_analyser() -> SequenceAnalyser:
    """4 sequences with disparate weights and signatures."""
    return make_analyser(
        ("top", 7, [("a", "occ", 1.0), ("top", "occ", 5.0)]),
        ("top", 3, [("b", "occ", 1.0), ("top", "occ", 5.0)]),
        ("top", 2, [("a", "occ", 1.0), ("b", "occ", 2.0), ("top", "occ", 5.0)]),
        ("safe", 1, [("c", "occ", 1.0)]),
    )


@pytest.fixture
def sample_state(sample_analyser) -> SeqTuiState:
    return SeqTuiState.from_initial(
        sample_analyser,
        source_path=Path("/tmp/synthetic.json"),
        source_format="json-cod3s",
    )


@pytest.fixture
def ccf_like_analyser() -> SequenceAnalyser:
    """An analyser that exercises ObjFM cycle filtering.

    Three sequences targeting ``top``:

    * occ/rep pair on ``fm__cc_1`` then a top.occ — filter should strip the pair.
    * occ on ``fm__cc_2`` followed by top.occ — no rep, untouched by filter.
    * occ/rep pair on ``fm__cc_1`` then occ on ``fm__cc_2`` then top.occ.

    After ``filter_objfm_cycles(["fm"]) + group_sequences``, signatures
    1 and 3 collapse to the same shape (``fm__cc_2.occ → top.occ``).
    """
    return make_analyser(
        ("top", 1, [("fm", "occ__cc_1", 1.0), ("fm", "rep__cc_1", 2.0),
                    ("top", "occ", 3.0)]),
        ("top", 1, [("fm", "occ__cc_2", 1.0), ("top", "occ", 2.0)]),
        ("top", 1, [("fm", "occ__cc_1", 1.0), ("fm", "rep__cc_1", 2.0),
                    ("fm", "occ__cc_2", 3.0), ("top", "occ", 4.0)]),
    )
