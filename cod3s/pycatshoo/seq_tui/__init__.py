"""Interactive TUI for analysing PyCATSHOO sequence dumps (``cod3s-seq``).

The TUI loads a sequence dump produced after a Monte-Carlo simulation
(XML written by ``PycSystem.setResultFileName`` or one of the JSON
artefacts produced by ``run-cod3s-study``: ``sequences_all.json`` /
``sequences_minimal.json``) and lets the user interactively stack
operations from the cod3s sequence-analysis pipeline:

* :func:`SequenceAnalyser.group_sequences`
* :func:`SequenceAnalyser.filter_objfm_cycles`
* :func:`SequenceAnalyser.compute_minimal_sequences`
* :func:`SequenceAnalyser.rm_events_by_obj`
* :func:`SequenceAnalyser.rm_events_ordered_pattern`
* :func:`SequenceAnalyser.rename_events`

Each step is configurable through a modal, applied to the current
``SequenceAnalyser`` snapshot, and pushed onto an undo stack so the
user can compare states.

The Textual layer (``app``, ``panels``, ``modals``) is loaded lazily
so ``cod3s-seq --help`` works even when Textual is misconfigured. The
pure-Python helpers (``loader``, ``exporter``, ``pipeline``) have no
Textual dependency and are reusable as a library:

    from cod3s.pycatshoo.seq_tui.loader import load_sequences_from_xml
    from cod3s.pycatshoo.seq_tui.pipeline import Pipeline

The TUI carries its own minor version (parent ``cod3s`` package
controls the major/minor; see ``CLAUDE.md`` versioning policy).
"""

from cod3s.pycatshoo.seq_tui.loader import (
    detect_format,
    load_sequences_from_json_cod3s,
    load_sequences_from_xml,
)

__all__ = [
    "detect_format",
    "load_sequences_from_json_cod3s",
    "load_sequences_from_xml",
]
