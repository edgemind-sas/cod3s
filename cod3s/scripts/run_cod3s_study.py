#!/usr/bin/env python3
"""CLI entry point for ``run-cod3s-study``.

Thin wrapper around :func:`cod3s.scripts.study_runner.run_study_from_yamls`.
The orchestration logic now lives in ``study_runner`` so downstream
consumers (eg. ``cod3s-platform``) can reuse it with a different
:class:`SystemBuilder`.

Usage:

.. code-block:: console

    run-cod3s-study --model system.yaml
    run-cod3s-study --model system.yaml --study-specs custom_study.yaml
    run-cod3s-study --model system.yaml --log-level DEBUG
    run-cod3s-study --model system.yaml --results-dir my_results
"""

from __future__ import annotations

import argparse
import datetime
from pathlib import Path

import cod3s
from cod3s.scripts._common import import_module_from_path
from cod3s.scripts.builders import YamlModelBuilder
from cod3s.scripts.study_runner import run_study

# Re-export for backward compatibility: existing tests / scripts may import
# this symbol from ``cod3s.scripts.run_cod3s_study``.
__all__ = ["import_module_from_path", "main"]


def _make_logger(level: str):
    """Build a COD3SLogger or return None when level == 'DISABLED'."""
    if level.upper() == "DISABLED":
        return None
    return cod3s.utils.COD3SLogger("COD3SRunStudy", level_name=level.upper())


def _resolve_results_dir(arg_value: str | None, study_path: Path) -> Path:
    """Compute the results directory, with the same fallback rules as before.

    Order:
    1. Explicit ``--results-dir`` argument
    2. ``<study-specs-stem>/`` next to study.yaml when study.yaml exists
    3. ``study_<timestamp>/`` (cwd-relative) otherwise
    """
    if arg_value:
        return Path(arg_value)
    if study_path.exists():
        return study_path.parent / study_path.stem
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"study_{timestamp}")


def main():
    parser = argparse.ArgumentParser(
        description="Run a COD3S study (YAML model + study.yaml).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default study specifications file (study.yaml)
  run-cod3s-study --model system.yaml

  # Custom study specifications file
  run-cod3s-study --model system.yaml --study-specs custom_config.yaml

  # Verbose logging
  run-cod3s-study --model system.yaml --log-level DEBUG

  # Custom results directory
  run-cod3s-study --model system.yaml --results-dir my_results
        """,
    )
    parser.add_argument(
        "--study-specs",
        type=str,
        default="study.yaml",
        help="Study specifications YAML file (default: study.yaml).",
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
    parser.add_argument(
        "--results-dir",
        type=str,
        default=None,
        help="Directory to store study results (default: derived from study-specs filename).",
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="YAML specification file of the model used by YamlModelBuilder.",
    )
    args = parser.parse_args()

    logger = _make_logger(args.log_level)

    model_path = Path(args.model)
    study_path = Path(args.study_specs)
    results_dir = _resolve_results_dir(args.results_dir, study_path)

    if logger:
        import Pycatshoo as Pyc

        logger.info1(f"PyCATSHOO Version: {Pyc.ILogManager.glLogManager().version()}")

    # ``namespace=globals()`` keeps backward compatibility with study
    # YAMLs that reference Python classes brought in by ``imports:``.
    builder = YamlModelBuilder(model_path, namespace=globals())
    system = run_study(
        system_builder=builder,
        study=study_path,
        results_dir=results_dir,
        logger=logger,
    )

    # Sequences XML is a CLI-specific artefact (cod3s-platform builds
    # its own target events from the study, not from ``CAnalyser``).
    try:
        import Pycatshoo as Pyc

        analyser = Pyc.CAnalyser(system)
        analyser.keepFilteredSeq(True)
        analyser.printFilteredSeq(100, str(results_dir / "sequences.xml"), "PySeq.xsl")
        if logger:
            logger.info3(f"Sequences XML saved to {results_dir / 'sequences.xml'}")
    except Exception as e:
        if logger:
            logger.warning(f"Failed to write sequences.xml: {e}")


if __name__ == "__main__":
    main()
