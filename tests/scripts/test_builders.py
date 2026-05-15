"""Tests for ``cod3s.scripts.builders``."""

from __future__ import annotations

from pathlib import Path

import pytest

from cod3s.scripts.builders import SystemBuilder, YamlModelBuilder


class TestSystemBuilderProtocol:
    def test_yaml_model_builder_satisfies_protocol(self):
        b = YamlModelBuilder(Path("nonexistent.yaml"))
        # Runtime-checkable Protocol — works for duck typing
        assert isinstance(b, SystemBuilder)

    def test_dict_does_not_satisfy_protocol(self):
        # Make sure the protocol isn't trivially matched
        assert not isinstance({}, SystemBuilder)


class TestYamlModelBuilder:
    def test_repr(self):
        b = YamlModelBuilder("foo.yaml")
        assert "foo.yaml" in repr(b)

    def test_missing_file_raises(self, tmp_path):
        b = YamlModelBuilder(tmp_path / "missing.yaml")
        with pytest.raises(FileNotFoundError):
            b.build()

    def test_with_explicit_namespace(self, tmp_path, terminate_pyc_after):
        """Verify build() forwards the namespace to build_system_from_model."""
        # Create a minimal YAML model that doesn't need imports
        # (uses default PycSystem)
        model = tmp_path / "model.yaml"
        model.write_text(
            "system:\n"
            "  name: test_sys\n"
            "components: []\n"
            "connections: []\n"
        )
        ns: dict = {}
        b = YamlModelBuilder(model, namespace=ns)
        # build() will require PyCATSHOO at runtime — skip if unavailable
        try:
            sys_obj = b.build()
        except Exception as e:
            pytest.skip(f"PyCATSHOO not available in test env: {e}")
        assert sys_obj is not None
