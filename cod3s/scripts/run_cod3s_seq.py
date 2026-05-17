#!/usr/bin/env python3
"""CLI entry-point for the post-mortem sequence analyser TUI (``cod3s-seq``).

``cod3s-seq`` loads a PyCATSHOO sequence dump — either the raw XML
written by ``PycSystem.setResultFileName`` or one of the JSON
artefacts produced by ``run-cod3s-study`` (``sequences_all.json`` /
``sequences_minimal.json``) — and lets the user interactively stack
operations from the cod3s sequence-analysis pipeline:

* ``group_sequences``
* ``filter_objfm_cycles``
* ``compute_minimal_sequences``
* ``rm_events_by_obj``
* ``rm_events_ordered_pattern``
* ``rename_events``

A YAML pipeline can be saved / loaded, and the resulting analyser can
be exported as JSON cod3s, CSV (one row per event) or a Markdown
report.

Examples
--------
::

  # Load an XML dump and explore interactively
  cod3s-seq results/sequences.xml

  # Load a JSON cod3s dump (auto-detected by extension)
  cod3s-seq results/sequences_minimal.json

  # Force a format (useful when the extension lies)
  cod3s-seq dump.txt --format xml

  # Re-apply a saved pipeline at startup, then drop into the TUI
  cod3s-seq results/sequences.xml --pipeline saved-pipe.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

import cod3s


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cod3s-seq",
        description=(
            "Interactive analyser for PyCATSHOO sequence dumps (Textual TUI). "
            "Stacks group / filter / minimal operations, supports undo, and "
            "exports to JSON cod3s, CSV or Markdown."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  cod3s-seq results/sequences.xml\n"
            "  cod3s-seq results/sequences_minimal.json\n"
            "  cod3s-seq dump.xml --pipeline canonical.yaml\n"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"cod3s-seq {cod3s.__version__}",
    )
    parser.add_argument(
        "sequences_file",
        type=str,
        help=(
            "Sequence dump file: XML (raw PyCATSHOO) or JSON cod3s "
            "(produced by run-cod3s-study or by a previous "
            "cod3s-seq export)."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["xml", "json-cod3s"],
        default=None,
        help=(
            "Force the input format. By default the format is inferred "
            "from the file extension (.xml → xml ; .json → json-cod3s)."
        ),
    )
    parser.add_argument(
        "--pipeline",
        type=str,
        default=None,
        help=(
            "Optional pipeline YAML to apply automatically at startup. "
            "Equivalent to launching the TUI and pressing `l` immediately."
        ),
    )
    parser.add_argument(
        "--max-sequences",
        type=int,
        default=None,
        help=(
            "Cap the number of sequences loaded from the input file. "
            "Useful for quick exploration of very large XML dumps."
        ),
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Python logging level (default: WARNING).",
    )
    return parser


def _load_analyser(args: argparse.Namespace, logger: logging.Logger):
    """Load the input file into a :class:`SequenceAnalyser`."""
    from cod3s.pycatshoo.seq_tui.loader import (
        detect_format,
        load_sequences_from_json_cod3s,
        load_sequences_from_xml,
    )
    from cod3s.pycatshoo.sequence import SequenceAnalyser

    path = Path(args.sequences_file).expanduser()
    fmt = args.format or detect_format(path)
    logger.info("Loading %s as %s", path, fmt)
    if fmt == "xml":
        sequences = load_sequences_from_xml(path, max_sequences=args.max_sequences)
    else:
        sequences = load_sequences_from_json_cod3s(path)
        if args.max_sequences is not None:
            sequences = sequences[: args.max_sequences]
    analyser = SequenceAnalyser(sequences=sequences)
    analyser.update_probs()
    logger.info("Loaded %d sequences", len(sequences))
    return analyser, path, fmt


def _apply_startup_pipeline(state, pipeline_path: Optional[str], logger):
    """If ``--pipeline`` was given, apply it on top of the loaded state."""
    if pipeline_path is None:
        return state
    from cod3s.pycatshoo.seq_tui.pipeline import Pipeline

    pipeline = Pipeline.load_yaml(Path(pipeline_path).expanduser())
    logger.info("Applying startup pipeline (%d steps)", len(pipeline.steps))
    for step in pipeline.steps:
        state = state.with_step_applied(step)
    return state


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger("cod3s-seq")

    try:
        analyser, source_path, source_format = _load_analyser(args, logger)
    except FileNotFoundError as exc:
        parser.error(str(exc))
        return 2
    except Exception as exc:  # surface loader errors with a clean message
        parser.error(f"failed to load sequences: {exc}")
        return 2

    from cod3s.pycatshoo.seq_tui.state import SeqTuiState

    state = SeqTuiState.from_initial(
        analyser, source_path=source_path, source_format=source_format
    )

    try:
        state = _apply_startup_pipeline(state, args.pipeline, logger)
    except Exception as exc:
        parser.error(f"failed to apply startup pipeline: {exc}")
        return 2

    # Lazy-import the Textual app so ``--help`` and load errors stay
    # responsive even on environments where Textual can't start.
    from cod3s.pycatshoo.seq_tui.app import run_seq_tui

    run_seq_tui(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
