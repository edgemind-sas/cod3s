"""Tests for ``cod3s.scripts.study_runner``.

Avoids loading PyCATSHOO by using mock systems / builders.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from cod3s.scripts.study_runner import (
    _resolve_fm_class,
    add_failure_modes,
    apply_attribute_overrides,
    register_fm_class,
    run_study,
    write_results,
)
from cod3s.specs.study_yaml import (
    AttributeOverride,
    AttributeOverrides,
    FailureModeParamOverride,
    ObjFMExpSpec,
    ObjFMGenericSpec,
    ResultsConfig,
    StudyYaml,
)

# ---------------------------------------------------------------------------
# FM class registry
# ---------------------------------------------------------------------------


class TestFMRegistry:
    def test_register_custom_class(self):
        """register_fm_class adds a name → class mapping accessible via _resolve_fm_class."""

        class FakeWeibull:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        register_fm_class("FakeWeibull", FakeWeibull)
        try:
            cls = _resolve_fm_class("FakeWeibull")
            assert cls is FakeWeibull
        finally:
            from cod3s.scripts.study_runner import _FM_REGISTRY

            _FM_REGISTRY.pop("FakeWeibull", None)

    def test_unknown_class_raises(self):
        with pytest.raises(ValueError, match="Unknown failure mode"):
            _resolve_fm_class("NonExistentClass_XYZ_42")


# ---------------------------------------------------------------------------
# Failure mode application
# ---------------------------------------------------------------------------


class TestAddFailureModes:
    def test_dispatch_via_registry(self):
        """add_failure_modes instantiates spec.cls(**spec.model_dump())."""
        instances = []

        class FakeFM:
            def __init__(self, **kwargs):
                instances.append(kwargs)

        register_fm_class("ObjFMExp", FakeFM)
        try:
            spec = ObjFMExpSpec(
                fm_name="m1",
                targets=["A", "B"],
                failure_param=[1e-5, 8e-6],
                repair_param=[0.1, 0.1],
                failure_effects={"V_x": False},
            )
            count = add_failure_modes(MagicMock(), [spec])
            assert count == 1
            assert len(instances) == 1
            assert instances[0]["fm_name"] == "m1"
            assert instances[0]["targets"] == ["A", "B"]
            assert instances[0]["failure_param"] == [1e-5, 8e-6]
            # cls + enabled fields are excluded from the constructor call
            assert "cls" not in instances[0]
            assert "enabled" not in instances[0]
        finally:
            # Restore default registration
            from cod3s.scripts.study_runner import _FM_REGISTRY

            _FM_REGISTRY.pop("ObjFMExp", None)

    def test_disabled_skipped(self):
        instances = []

        class FakeFM:
            def __init__(self, **kwargs):
                instances.append(kwargs)

        register_fm_class("ObjFMExp", FakeFM)
        try:
            spec = ObjFMExpSpec(fm_name="m1", targets=["A"], enabled=False)
            count = add_failure_modes(MagicMock(), [spec])
            assert count == 0
            assert instances == []
        finally:
            from cod3s.scripts.study_runner import _FM_REGISTRY

            _FM_REGISTRY.pop("ObjFMExp", None)

    def test_construction_failure_logged_not_raised(self):
        """A bad FM logs but does not crash the whole run."""

        class BadFM:
            def __init__(self, **kwargs):
                raise ValueError("nope")

        register_fm_class("ObjFMExp", BadFM)
        try:
            spec = ObjFMExpSpec(fm_name="m1", targets=["A"])
            count = add_failure_modes(MagicMock(), [spec])
            assert count == 0  # nothing added, but no exception
        finally:
            from cod3s.scripts.study_runner import _FM_REGISTRY

            _FM_REGISTRY.pop("ObjFMExp", None)

    def test_generic_spec_passthrough(self):
        """ObjFMGenericSpec extra kwargs flow into the constructor."""
        instances = []

        class CustomFM:
            def __init__(self, **kwargs):
                instances.append(kwargs)

        register_fm_class("FakeWeibull", CustomFM)
        try:
            spec = ObjFMGenericSpec(
                fm_name="m1",
                targets=["A"],
                cls="FakeWeibull",
                failure_param_name=["k", "lambda"],
                failure_param=[(2.0, 1e-5)],
                custom_arg="custom_value",
            )
            count = add_failure_modes(MagicMock(), [spec])
            assert count == 1
            assert instances[0]["custom_arg"] == "custom_value"
            assert instances[0]["failure_param_name"] == ["k", "lambda"]
        finally:
            from cod3s.scripts.study_runner import _FM_REGISTRY

            _FM_REGISTRY.pop("FakeWeibull", None)


# ---------------------------------------------------------------------------
# Attribute overrides
# ---------------------------------------------------------------------------


class TestApplyAttributeOverrides:
    def test_component_attr_via_set_attribute(self):
        comp = MagicMock()
        comp.set_attribute = MagicMock()
        system = MagicMock()
        system.comp = {"PLC_1": comp}

        overrides = AttributeOverrides(
            component_attr=[
                AttributeOverride(component="PLC_1", attribute="V_state", value=False)
            ]
        )
        apply_attribute_overrides(system, overrides)
        comp.set_attribute.assert_called_once_with("V_state", False)

    def test_component_attr_fallback_to_setattr(self):
        """When set_attribute is absent, fall back to setattr."""

        class BareComp:
            pass

        comp = BareComp()
        system = MagicMock()
        system.comp = {"PLC_1": comp}

        overrides = AttributeOverrides(
            component_attr=[
                AttributeOverride(component="PLC_1", attribute="my_attr", value=42)
            ]
        )
        apply_attribute_overrides(system, overrides)
        assert comp.my_attr == 42

    def test_missing_component_skipped_with_warning(self):
        system = MagicMock()
        system.comp = {}
        logger = MagicMock()

        overrides = AttributeOverrides(
            component_attr=[AttributeOverride(component="X", attribute="a", value=1)]
        )
        apply_attribute_overrides(system, overrides, logger=logger)
        logger.warning.assert_called_once()

    def test_failure_mode_param_override(self):
        """The override updates the Python-side list AND pushes every
        per-order value into the backend parameter variables the laws
        are bound to (a bare setattr alone never reaches the
        simulation)."""
        fm = MagicMock()
        fm.targets = ["c1", "c2"]
        fm.occ_param_name = ["lambda"]
        fm.param_name_order_prefix = "__{order}_o_{order_max}"
        variables = {}

        def _variable(name):
            return variables.setdefault(name, MagicMock())

        fm.variable.side_effect = _variable

        system = MagicMock()
        system.comp = {"M_001": fm}

        overrides = AttributeOverrides(
            failure_mode_param=[
                FailureModeParamOverride(
                    fm_name="M_001",
                    field="failure_param",
                    value=[2e-5, 1e-5],
                )
            ]
        )
        apply_attribute_overrides(system, overrides)
        assert fm.failure_param == [2e-5, 1e-5]
        variables["lambda__1_o_2"].setValue.assert_called_once_with(2e-5)
        variables["lambda__2_o_2"].setValue.assert_called_once_with(1e-5)

    def test_failure_mode_param_override_without_param_surface_is_refused(self):
        """A mode whose laws are not bound to parameter variables cannot
        honour the override: it must be warned about, not silently
        applied to the Python attribute and reported as a success."""
        fm = MagicMock()
        fm.targets = []
        fm.occ_param_name = []
        system = MagicMock()
        system.comp = {"M_001": fm}
        logger = MagicMock()

        overrides = AttributeOverrides(
            failure_mode_param=[
                FailureModeParamOverride(
                    fm_name="M_001", field="failure_param", value=[2e-5]
                )
            ]
        )
        apply_attribute_overrides(system, overrides, logger=logger)
        logger.error.assert_called_once()
        logger.info3.assert_not_called()

    def test_none_overrides_no_op(self):
        """apply_attribute_overrides(None) is a no-op."""
        apply_attribute_overrides(MagicMock(), None)  # no exception


# ---------------------------------------------------------------------------
# Results writing
# ---------------------------------------------------------------------------


class TestWriteResults:
    def test_no_results_no_op(self, tmp_path):
        write_results(MagicMock(), None, tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_indicators_csv_written(self, tmp_path):
        # Mock a dataframe-like
        df = MagicMock()
        system = MagicMock()
        system.indic_to_frame = MagicMock(return_value=df)

        from cod3s.specs.study_yaml import ResultsIndicatorSpec

        cfg = ResultsConfig(
            indicators=[
                ResultsIndicatorSpec(id="my_inds", output=["csv"], comp_pattern="X.*")
            ]
        )
        write_results(system, cfg, tmp_path)
        df.to_csv.assert_called_once()
        called_path = df.to_csv.call_args[0][0]
        assert str(called_path).endswith("my_inds.csv")


# ---------------------------------------------------------------------------
# End-to-end run_study (with mock builder + mock system)
# ---------------------------------------------------------------------------


class TestRunStudyEndToEnd:
    def test_full_pipeline_minimal_study(self, tmp_path):
        """run_study composes builder.build → simulate → write_results."""

        # Mock system supporting all required methods
        system = MagicMock()
        system.comp = {}

        class StubBuilder:
            def build(self, *, logger=None):
                return system

        study = StudyYaml(
            name="minimal",
            simulation={"nb_runs": 10},
        )
        ret = run_study(
            system_builder=StubBuilder(),
            study=study,
            results_dir=tmp_path,
        )
        assert ret is system
        system.simulate.assert_called_once()
        # No failure modes / events / indicators / targets to add — but
        # the system.add_* methods should still be called with [] payloads
        system.add_events.assert_called_once_with([], logger=None)
        system.add_indicators.assert_called_once_with([], logger=None)
        system.add_targets.assert_called_once_with([], logger=None)

    def test_load_study_from_path(self, tmp_path):
        """run_study accepts a Path to a study.yaml file."""
        study_path = tmp_path / "study.yaml"
        study_path.write_text(
            yaml.safe_dump({"name": "loaded", "simulation": {"nb_runs": 1}})
        )

        system = MagicMock()
        system.comp = {}

        class StubBuilder:
            def build(self, *, logger=None):
                return system

        run_study(
            system_builder=StubBuilder(),
            study=study_path,
            results_dir=tmp_path,
        )
        system.simulate.assert_called_once()

    def test_invalid_study_raises_pydantic_error(self, tmp_path):
        """A malformed study dict surfaces a Pydantic ValidationError early."""
        with pytest.raises(Exception):  # ValidationError or ValueError
            run_study(
                system_builder=MagicMock(),
                study={"bogus": True},  # missing required ``name``
                results_dir=tmp_path,
            )
