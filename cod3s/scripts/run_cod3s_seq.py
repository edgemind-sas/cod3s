#!/usr/bin/env python3
"""CLI entry-point for the sequence-analyser TUI (``cod3s-seq``).

Two modes:

* **Post-mortem** (default) — load a sequence dump file (raw XML
  written by ``PycSystem.setResultFileName`` or one of the JSON
  artefacts produced by ``run-cod3s-study``: ``sequences_all.json`` /
  ``sequences_minimal.json``). The ObjFM names must be typed into the
  ``filter_objfm_cycles`` modal as comma-separated lists.

* **Live** (``--factory module:fn``) — also call the supplied factory
  to build a populated :class:`PycSystem`, attach it to the analyser,
  and pre-fill the configuration modals with the ObjFM names
  discovered on the system. The user picks ObjFM via a checklist
  instead of typing names. The factory **must not** simulate — it
  just builds the model, like the ``cod3s-isimu`` factory contract.

The TUI then lets the user interactively stack operations from the
cod3s sequence-analysis pipeline:

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

  # Live mode: ``mymodule:build`` returns a populated PycSystem so the
  # filter modal shows ObjFM as a checklist
  cod3s-seq results/sequences.xml --factory mymodule:build
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
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
        "--factory",
        type=str,
        default=None,
        help=(
            "Live mode: Python factory of the form "
            "'module.path:function_name'. The function must return a "
            "populated PycSystem (without simulating). The system is "
            "attached to the analyser so filter_objfm_cycles can "
            "auto-discover ObjFM, and the configuration modal renders "
            "them as a checklist."
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


def _human_bytes(n: int) -> str:
    """Format a byte count as a short human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _load_analyser(args: argparse.Namespace, logger: logging.Logger):
    """Load the input file into a :class:`SequenceAnalyser`.

    Prints concise progress lines to stderr (always visible, even at
    the default WARNING log level) so the user sees the tool is alive
    while large XML dumps stream in. The Textual TUI hasn't started
    yet at this point, so stderr is the only feedback channel.
    """
    from cod3s.pycatshoo.seq_tui.loader import (
        detect_format,
        load_sequences_from_json_cod3s,
        load_sequences_from_xml,
    )
    from cod3s.pycatshoo.sequence import SequenceAnalyser

    path = Path(args.sequences_file).expanduser()
    fmt = args.format or detect_format(path)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    size_str = _human_bytes(size) if size else "?"
    cap = f", cap {args.max_sequences} sequences" if args.max_sequences else ""

    t0 = time.perf_counter()
    print(
        f"[cod3s-seq] Loading {path.name} ({size_str}, format={fmt}{cap})…",
        file=sys.stderr,
        flush=True,
    )
    logger.info("Loading %s as %s (%s)", path, fmt, size_str)
    if fmt == "xml":
        sequences = load_sequences_from_xml(path, max_sequences=args.max_sequences)
    else:
        sequences = load_sequences_from_json_cod3s(path)
        if args.max_sequences is not None:
            sequences = sequences[: args.max_sequences]
    dt_load = time.perf_counter() - t0

    t1 = time.perf_counter()
    print(
        f"[cod3s-seq]   → {len(sequences)} raw sequences loaded in {dt_load:.1f}s. "
        f"Building analyser…",
        file=sys.stderr,
        flush=True,
    )
    analyser = SequenceAnalyser(sequences=sequences)
    analyser.update_probs()
    dt_build = time.perf_counter() - t1
    print(
        f"[cod3s-seq]   → Analyser ready ({dt_build:.1f}s).",
        file=sys.stderr,
        flush=True,
    )
    logger.info("Loaded %d sequences", len(sequences))
    return analyser, path, fmt


def _load_startup_pipeline(pipeline_path: Optional[str], logger):
    """If ``--pipeline`` was given, load it from YAML but do NOT apply.

    Returns the loaded :class:`Pipeline` object (or ``None``). The
    actual application happens inside the TUI worker thread (see
    :meth:`SeqTuiApp.on_mount`) so each step lands on the undo stack
    and the user sees per-step notifications.
    """
    if pipeline_path is None:
        return None
    from cod3s.pycatshoo.seq_tui.pipeline import Pipeline

    pipeline = Pipeline.load_yaml(Path(pipeline_path).expanduser())
    logger.info("Loaded startup pipeline (%d steps)", len(pipeline.steps))
    print(
        f"[cod3s-seq] Startup pipeline: {len(pipeline.steps)} step(s) — "
        "will be applied in the TUI after mount.",
        file=sys.stderr,
        flush=True,
    )
    return pipeline


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

    system = None
    if args.factory is not None:
        from cod3s.scripts._common import resolve_factory

        try:
            factory = resolve_factory(args.factory, flag_label="--factory")
            system = factory()
        except Exception as exc:
            parser.error(f"failed to resolve --factory {args.factory!r}: {exc}")
            return 2
        logger.info(
            "Live mode: system %r attached (%d components)",
            getattr(system, "name", lambda: "?")(),
            len(getattr(system, "comp", {}) or {}),
        )

    state = SeqTuiState.from_initial(
        analyser,
        source_path=source_path,
        source_format=source_format,
        system=system,
    )
    if system is not None:
        logger.info(
            "Discovered ObjFM: internal=%s, external=%s",
            list(state.available_objfms_internal),
            list(state.available_objfms_external),
        )

    try:
        startup_pipeline = _load_startup_pipeline(args.pipeline, logger)
    except Exception as exc:
        parser.error(f"failed to load startup pipeline: {exc}")
        return 2

    # Lazy-import the Textual app so ``--help`` and load errors stay
    # responsive even on environments where Textual can't start.
    from cod3s.pycatshoo.seq_tui.app import run_seq_tui

    print("[cod3s-seq] Starting TUI…", file=sys.stderr, flush=True)
    run_seq_tui(state, startup_pipeline=startup_pipeline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
