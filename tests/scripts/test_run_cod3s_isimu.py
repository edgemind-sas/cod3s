"""Tests for the ``cod3s-isimu`` entry-point.

Argparse and factory-resolution logic is exercised through ``main(argv)``
without launching the Textual TUI. The ``--help`` case is also verified via
subprocess so we know the binary is wired up in ``pyproject.toml``.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from cod3s.scripts.run_cod3s_isimu import _build_parser, _resolve_factory

# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------


def test_help_runs_via_subprocess() -> None:
    """``cod3s-isimu --help`` must exit 0 and mention the two input modes."""
    result = subprocess.run(
        ["cod3s-isimu", "--help"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "--model" in result.stdout
    assert "--factory" in result.stdout
    assert "Textual TUI" in result.stdout


def test_parser_requires_model_or_factory() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        # ``--study-specs`` alone is not enough; one of --model/--factory
        # is required.
        parser.parse_args(["--study-specs", "study.yaml"])


def test_parser_rejects_both_model_and_factory() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--model", "m.yaml", "--factory", "mod:fn"])


def test_parser_accepts_model() -> None:
    parser = _build_parser()
    ns = parser.parse_args(["--model", "m.yaml"])
    assert ns.model == "m.yaml"
    assert ns.factory is None


def test_parser_accepts_factory_with_study_specs() -> None:
    parser = _build_parser()
    ns = parser.parse_args(["--factory", "mod.path:fn", "--study-specs", "s.yaml"])
    assert ns.factory == "mod.path:fn"
    assert ns.study_specs == "s.yaml"


# ---------------------------------------------------------------------------
# Factory resolution
# ---------------------------------------------------------------------------


def test_resolve_factory_invalid_format() -> None:
    with pytest.raises(ValueError):
        _resolve_factory("no_colon_here")
    with pytest.raises(ValueError):
        _resolve_factory(":missing_module")
    with pytest.raises(ValueError):
        _resolve_factory("module:")


def test_resolve_factory_missing_module() -> None:
    with pytest.raises(ImportError):
        _resolve_factory("definitely_not_a_real_module_xxxyzz:build")


def test_resolve_factory_missing_attribute() -> None:
    # ``cod3s`` exists but has no ``not_a_real_function`` attribute.
    with pytest.raises(AttributeError):
        _resolve_factory("cod3s:not_a_real_function")


def test_resolve_factory_resolves_callable(tmp_path: Path) -> None:
    """A user-built module on PYTHONPATH must resolve cleanly."""
    mod_path = tmp_path / "isimu_factory_fixture.py"
    mod_path.write_text(textwrap.dedent("""
            def build():
                return "system-stub"
            """).lstrip())
    sys.path.insert(0, str(tmp_path))
    try:
        fn = _resolve_factory("isimu_factory_fixture:build")
        assert fn() == "system-stub"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("isimu_factory_fixture", None)
