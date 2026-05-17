#!/usr/bin/env python3
"""CLI entry-point for the interactive simulator (``cod3s-isimu``).

Loads a ``PycSystem`` from either a YAML model (same format as
``run-cod3s-study``) or a Python factory, then drives it step-by-step from
a Textual TUI.

Examples
--------
  # YAML model (typical use)
  cod3s-isimu --model examples/pyc_pdmp/model.yaml

  # Python factory: ``examples.my_system:build`` returns a populated PycSystem
  cod3s-isimu --factory examples.my_system:build

  # Apply failure_modes / events from a study spec on top of the model
  cod3s-isimu --model model.yaml --study-specs study.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import cod3s

from cod3s.scripts._common import (
    build_system_from_model,
    load_study_specs,
    resolve_factory,
)


def _resolve_factory(spec: str) -> Any:
    """Backwards-compatible alias kept for callers of the script API.

    The shared implementation now lives in ``_common.resolve_factory``;
    this wrapper preserves the historical ``_resolve_factory`` symbol
    (private leading underscore) for any direct importers of this
    module.
    """
    return resolve_factory(spec, flag_label="--factory")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cod3s-isimu",
        description="Interactive PyCATSHOO simulator (Textual TUI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  cod3s-isimu --model examples/pyc_pdmp/model.yaml\n"
            "  cod3s-isimu --factory mymodule:build_system\n"
            "  cod3s-isimu --model model.yaml --study-specs study.yaml\n"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"cod3s-isimu {cod3s.__version__}",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--model",
        type=str,
        help="YAML model file (same format as run-cod3s-study).",
    )
    src.add_argument(
        "--factory",
        type=str,
        help=(
            "Python factory of the form 'module.path:function_name'. The "
            "function must return a populated PycSystem when called with no "
            "arguments."
        ),
    )
    parser.add_argument(
        "--study-specs",
        type=str,
        default=None,
        help=(
            "Optional YAML with 'failure_modes' / 'events' keys to apply on "
            "top of the loaded model (indicators and targets are skipped in "
            "interactive mode)."
        ),
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="DISABLED",
        choices=[
            "DISABLED",
            "DEBUG",
            "INFO",
            "INFO1",
            "INFO2",
            "INFO3",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ],
        help="Logging level (default: DISABLED).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.log_level.upper() == "DISABLED":
        logger = None
    else:
        logger = cod3s.utils.COD3SLogger(
            "COD3SISimu", level_name=args.log_level.upper()
        )

    if args.model:
        system = build_system_from_model(
            Path(args.model), namespace=globals(), logger=logger
        )
    else:
        factory = _resolve_factory(args.factory)
        system = factory()

    if args.study_specs:
        study = load_study_specs(Path(args.study_specs), logger=logger)
        if study.get("failure_modes"):
            system.add_failure_modes(study["failure_modes"], logger=logger)
        if study.get("events"):
            system.add_events(study["events"], logger=logger)

    # Lazy-import so ``cod3s-isimu --help`` and argument validation stay
    # responsive even on environments where Textual fails to import.
    from cod3s.pycatshoo.isimu.app import run_isimu

    run_isimu(system)
    return 0


if __name__ == "__main__":
    sys.exit(main())
