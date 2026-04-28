"""Tests for ``cod3s.scripts._common`` (YAML model loader helpers)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from cod3s.scripts._common import (
    build_system_from_model,
    import_module_from_path,
    load_study_specs,
)


def _write(path: Path, content: str) -> Path:
    path.write_text(textwrap.dedent(content).lstrip("\n"))
    return path


# ---------------------------------------------------------------------------
# import_module_from_path
# ---------------------------------------------------------------------------


def test_import_module_from_path_exposes_public_names(tmp_path: Path) -> None:
    mod = _write(
        tmp_path / "mymod.py",
        """
        FOO = 42

        def bar():
            return "bar"

        _private = "hidden"
        """,
    )

    namespace: dict = {}
    msg = import_module_from_path(mod, namespace)

    assert namespace["FOO"] == 42
    assert namespace["bar"]() == "bar"
    assert "_private" not in namespace
    assert str(mod) in msg


def test_import_module_from_path_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        import_module_from_path(tmp_path / "no_such.py", {})


# ---------------------------------------------------------------------------
# load_study_specs
# ---------------------------------------------------------------------------


def test_load_study_specs_missing_returns_empty(tmp_path: Path) -> None:
    assert load_study_specs(tmp_path / "absent.yaml") == {}


def test_load_study_specs_present(tmp_path: Path) -> None:
    p = _write(tmp_path / "study.yaml", "failure_modes: []\nevents: []\n")
    assert load_study_specs(p) == {"failure_modes": [], "events": []}


def test_load_study_specs_empty_file_returns_empty(tmp_path: Path) -> None:
    p = _write(tmp_path / "empty.yaml", "")
    assert load_study_specs(p) == {}


# ---------------------------------------------------------------------------
# build_system_from_model
# ---------------------------------------------------------------------------


def test_build_system_from_model_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_system_from_model(tmp_path / "nope.yaml")


def test_build_system_from_model_unknown_class_raises(tmp_path: Path) -> None:
    model = _write(
        tmp_path / "model.yaml",
        """
        system:
          python_class: NotAClass
        components: []
        connections: []
        """,
    )
    with pytest.raises(NameError):
        build_system_from_model(model)


def test_build_system_from_model_missing_import_raises(tmp_path: Path) -> None:
    model = _write(
        tmp_path / "model.yaml",
        """
        imports:
          - nonexistent_module.py
        system:
          python_class: PycSystem
        components: []
        connections: []
        """,
    )
    with pytest.raises(FileNotFoundError):
        build_system_from_model(model)


def test_build_system_from_model_default_pycsystem(
    tmp_path: Path, terminate_pyc_after
) -> None:
    """Without an ``imports:`` key, ``python_class: PycSystem`` resolves via
    the cod3s built-in fallback."""
    model = _write(
        tmp_path / "model.yaml",
        """
        system:
          python_class: PycSystem
          name: TestSys
        components: []
        connections: []
        """,
    )
    system = build_system_from_model(model)
    assert system.name() == "TestSys"


def test_build_system_from_model_with_components(
    tmp_path: Path, terminate_pyc_after
) -> None:
    """A minimal valid YAML must build a ``PycSystem`` and add components."""
    model = _write(
        tmp_path / "model.yaml",
        """
        system:
          python_class: PycSystem
          name: SmallSys
        components:
          - name: c1
            cls: PycComponent
        connections: []
        """,
    )
    system = build_system_from_model(model)
    assert system.name() == "SmallSys"
    assert "c1" in system.comp


def test_build_system_from_model_resolves_imports(
    tmp_path: Path, terminate_pyc_after
) -> None:
    """Public names from ``imports:`` files must be visible to the loader."""
    helper = _write(
        tmp_path / "helper.py",
        """
        from cod3s.pycatshoo.system import PycSystem


        class MyPycSystem(PycSystem):
            pass
        """,
    )
    model = _write(
        tmp_path / "model.yaml",
        f"""
        imports:
          - {helper.name}
        system:
          python_class: MyPycSystem
          name: ImportedSys
        components: []
        connections: []
        """,
    )
    system = build_system_from_model(model)
    assert system.__class__.__name__ == "MyPycSystem"
    assert system.name() == "ImportedSys"
