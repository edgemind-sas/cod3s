"""Tests for ``cod3s.specs.study_yaml``."""

from __future__ import annotations

import pydantic
import pytest
import yaml
from pathlib import Path

from cod3s.specs.study_yaml import (
    AttributeOverride,
    EventSpec,
    IndicatorSpec,
    ObjFMDelaySpec,
    ObjFMExpSpec,
    ObjFMGenericSpec,
    ResultsConfig,
    ScheduleEntry,
    SimulationConfig,
    StudyYaml,
    TargetSpec,
    STUDY_YAML_VERSION,
)

# ---------------------------------------------------------------------------
# Failure mode specs
# ---------------------------------------------------------------------------


class TestObjFMExpSpec:
    def test_minimal(self):
        spec = ObjFMExpSpec(fm_name="m1", targets=["C1"])
        assert spec.cls == "ObjFMExp"
        assert spec.failure_param == []
        assert spec.repair_param == []
        assert spec.failure_state == "occ"

    def test_full(self):
        spec = ObjFMExpSpec(
            fm_name="m1",
            targets=["C1", "C2", "C3"],
            failure_param=[1e-5, 8e-6, 4e-6],
            repair_param=[0.1, 0.1, 0.1],
            failure_effects={"V_state": False},
        )
        assert spec.failure_param == [1e-5, 8e-6, 4e-6]
        assert spec.failure_effects == {"V_state": False}

    def test_scalar_param_promoted_to_list(self):
        """Legacy YAML with scalar param must be coerced to a list."""
        spec = ObjFMExpSpec(
            fm_name="m", targets=["C"], failure_param=1.5e-5, repair_param=0.2
        )
        assert spec.failure_param == [1.5e-5]
        assert spec.repair_param == [0.2]

    def test_cls_field_is_locked(self):
        """Pydantic discriminator: cls must be ObjFMExp."""
        # Specifying it explicitly is fine
        spec = ObjFMExpSpec(fm_name="m", targets=["C"], cls="ObjFMExp")
        assert spec.cls == "ObjFMExp"
        # Wrong value is rejected
        with pytest.raises(ValueError):
            ObjFMExpSpec(fm_name="m", targets=["C"], cls="ObjFMDelay")


class TestObjFMDelaySpec:
    def test_minimal(self):
        spec = ObjFMDelaySpec(fm_name="m", targets=["C"])
        assert spec.cls == "ObjFMDelay"

    def test_with_params(self):
        spec = ObjFMDelaySpec(
            fm_name="m", targets=["C"], failure_param=[10.0], repair_param=[2.0]
        )
        assert spec.failure_param == [10.0]
        assert spec.repair_param == [2.0]


class TestObjFMGenericSpec:
    def test_with_custom_cls(self):
        spec = ObjFMGenericSpec(
            fm_name="m",
            targets=["C"],
            cls="ObjFMWeibull",
            failure_param_name=["k", "lambda"],
            failure_param=[(2.0, 1e-5)],
            repair_param_name=["mu"],
            repair_param=[0.1],
        )
        assert spec.cls == "ObjFMWeibull"
        assert spec.failure_param_name == ["k", "lambda"]

    def test_extra_kwargs_passthrough(self):
        """Subclass-specific kwargs survive parsing thanks to extra=allow."""
        spec = ObjFMGenericSpec(
            fm_name="m",
            targets=["C"],
            cls="ObjFMCustom",
            custom_kwarg="custom_value",  # type: ignore[call-arg]
        )
        dump = spec.model_dump()
        assert dump["custom_kwarg"] == "custom_value"

    def test_known_cls_rejected(self):
        """ObjFMExp / ObjFMDelay must use their typed specs."""
        with pytest.raises(ValueError, match="typed spec"):
            ObjFMGenericSpec(fm_name="m", targets=["C"], cls="ObjFMExp")


class TestFailureModeUnion:
    """The discriminated union dispatches on the cls field."""

    def test_dispatch_to_exp(self):
        study = StudyYaml(
            name="s",
            failure_modes=[{"fm_name": "m", "targets": ["C"], "cls": "ObjFMExp"}],
        )
        assert isinstance(study.failure_modes[0], ObjFMExpSpec)

    def test_dispatch_to_delay(self):
        study = StudyYaml(
            name="s",
            failure_modes=[{"fm_name": "m", "targets": ["C"], "cls": "ObjFMDelay"}],
        )
        assert isinstance(study.failure_modes[0], ObjFMDelaySpec)

    def test_dispatch_to_generic_for_unknown_cls(self):
        study = StudyYaml(
            name="s",
            failure_modes=[{"fm_name": "m", "targets": ["C"], "cls": "ObjFMWeibull"}],
        )
        assert isinstance(study.failure_modes[0], ObjFMGenericSpec)
        assert study.failure_modes[0].cls == "ObjFMWeibull"


# ---------------------------------------------------------------------------
# Backward compat: legacy ``occ_law`` field
# ---------------------------------------------------------------------------


class TestLegacyOccLaw:
    def test_exp_translated(self):
        study = StudyYaml(
            name="s",
            failure_modes=[
                {
                    "fm_name": "m",
                    "targets": ["C"],
                    "occ_law": "exp",
                    "failure_param": 1e-5,
                }
            ],
        )
        fm = study.failure_modes[0]
        assert isinstance(fm, ObjFMExpSpec)
        assert fm.cls == "ObjFMExp"
        assert fm.failure_param == [1e-5]

    def test_delay_translated(self):
        study = StudyYaml(
            name="s",
            failure_modes=[
                {
                    "fm_name": "m",
                    "targets": ["C"],
                    "occ_law": "delay",
                    "failure_param": 10.0,
                }
            ],
        )
        fm = study.failure_modes[0]
        assert isinstance(fm, ObjFMDelaySpec)

    def test_cls_takes_precedence(self):
        """If both cls and occ_law are present, cls wins."""
        study = StudyYaml(
            name="s",
            failure_modes=[
                {
                    "fm_name": "m",
                    "targets": ["C"],
                    "cls": "ObjFMExp",
                    "occ_law": "delay",
                }
            ],
        )
        # cls=ObjFMExp wins, occ_law is preserved as extra (rejected by ObjFMExpSpec)
        # Actually with extra=forbid, occ_law triggers a validation error
        # That's acceptable behaviour: don't mix the two.
        # Update: the validator only runs when cls is absent, so occ_law passes through
        # as extra=forbid → error. Verify that's the case.
        assert study.failure_modes[0].cls == "ObjFMExp"


# ---------------------------------------------------------------------------
# Other specs
# ---------------------------------------------------------------------------


class TestEventSpec:
    def test_minimal(self):
        spec = EventSpec(name="e", cond=True)
        assert spec.cls == "ObjEvent"
        assert spec.cond is True
        assert spec.tempo_occ == 0.0


class TestIndicatorSpec:
    def test_minimal(self):
        spec = IndicatorSpec(attr_type="VAR")
        assert spec.component == ".*"
        assert spec.attr_name == ".*"
        assert spec.stats == ["mean"]

    def test_extra_kwargs_passthrough(self):
        """Pass-through of PycAttrIndicator kwargs."""
        spec = IndicatorSpec(attr_type="VAR", custom_arg=42)
        assert spec.model_dump()["custom_arg"] == 42


class TestTargetSpec:
    def test_event_based(self):
        spec = TargetSpec(name="my_event")
        assert spec.var is None

    def test_var_based(self):
        spec = TargetSpec(
            name="t", var="C.attr.signal", var_type="VAR", operator="==", value=2
        )
        assert spec.var_type == "VAR"


# ---------------------------------------------------------------------------
# Schedule + simulation
# ---------------------------------------------------------------------------


class TestScheduleEntry:
    def test_range(self):
        e = ScheduleEntry(start=0, end=10, nvalues=11)
        assert e.start == 0.0

    def test_instant(self):
        e = ScheduleEntry(instant=5.0)
        assert e.instant == 5.0

    def test_mixing_rejected(self):
        with pytest.raises(ValueError, match="exclusive"):
            ScheduleEntry(start=0, end=10, nvalues=11, instant=5.0)

    def test_partial_range_rejected(self):
        with pytest.raises(ValueError, match="provide either"):
            ScheduleEntry(start=0, end=10)  # nvalues missing

    def test_end_before_start_rejected(self):
        with pytest.raises(ValueError, match="≥ start"):
            ScheduleEntry(start=10, end=0, nvalues=2)


class TestSimulationConfig:
    def test_defaults(self):
        cfg = SimulationConfig()
        assert cfg.nb_runs is None
        assert cfg.schedule == []
        assert cfg.monitor_patterns == ["#.*"]
        assert cfg.filter_objfm_in_sequences is True

    def test_extra_kwargs(self):
        """Simulator-specific knobs survive."""
        cfg = SimulationConfig(verbose=True)
        assert cfg.model_dump()["verbose"] is True

    def test_filter_objfm_in_sequences_can_be_disabled(self):
        """``False`` keeps the integral trace (audit / debugging)."""
        cfg = SimulationConfig(filter_objfm_in_sequences=False)
        assert cfg.filter_objfm_in_sequences is False

    def test_filter_objfm_in_sequences_round_trip(self):
        """Field survives ``model_dump`` ↔ ``model_validate`` cycle."""
        dumped = SimulationConfig(filter_objfm_in_sequences=False).model_dump()
        assert dumped["filter_objfm_in_sequences"] is False
        rebuilt = SimulationConfig.model_validate(dumped)
        assert rebuilt.filter_objfm_in_sequences is False


# ---------------------------------------------------------------------------
# Top-level StudyYaml
# ---------------------------------------------------------------------------


class TestStudyYaml:
    def test_minimal(self):
        s = StudyYaml(name="s")
        assert s.failure_modes == []
        assert s.version == STUDY_YAML_VERSION

    def test_unknown_fields_rejected(self):
        with pytest.raises(ValueError):
            StudyYaml(name="s", bogus_field="x")

    def test_duplicate_fm_name_rejected(self):
        with pytest.raises(ValueError, match="Duplicate"):
            StudyYaml(
                name="s",
                failure_modes=[
                    {"fm_name": "m1", "targets": ["A"], "cls": "ObjFMExp"},
                    {"fm_name": "m1", "targets": ["B"], "cls": "ObjFMExp"},
                ],
            )

    def test_failure_param_arity_check(self):
        with pytest.raises(ValueError, match="entries but only"):
            StudyYaml(
                name="s",
                failure_modes=[
                    {
                        "fm_name": "m",
                        "targets": ["A", "B"],
                        "cls": "ObjFMExp",
                        "failure_param": [1, 2, 3],  # 3 > 2 targets
                    }
                ],
            )

    def test_round_trip(self):
        """model_dump() / model_validate() preserves data."""
        s = StudyYaml(
            name="round",
            failure_modes=[
                {
                    "fm_name": "m",
                    "targets": ["A", "B"],
                    "cls": "ObjFMExp",
                    "failure_param": [1e-5, 8e-6],
                    "repair_param": [0.1, 0.1],
                    "failure_effects": {"V_x": False},
                }
            ],
        )
        dump = s.model_dump()
        s2 = StudyYaml.model_validate(dump)
        assert s2.failure_modes[0].fm_name == "m"
        assert s2.failure_modes[0].failure_param == [1e-5, 8e-6]


class TestLoadFromExistingFixture:
    """Validate that an existing legacy study.yaml from the repo loads cleanly."""

    @pytest.fixture
    def fixture_path(self) -> Path:
        return (
            Path(__file__).parent.parent
            / "usecases"
            / "indus_4_0_Electrolyseur"
            / "test_source"
            / "study.yaml"
        )

    def test_load_legacy_yaml(self, fixture_path: Path):
        if not fixture_path.exists():
            pytest.skip(f"fixture not found: {fixture_path}")
        data = yaml.safe_load(fixture_path.read_text())
        # Legacy fixture lacks ``name`` — patch it for the test
        data.setdefault("name", "test_source")
        # ``results.indicators`` uses ``id`` which is fine,
        # but ``simulation`` / ``indicators`` / ``failure_modes`` shapes
        # must validate.
        s = StudyYaml.model_validate(data)
        assert s.failure_modes[0].cls == "ObjFMDelay"
        assert s.failure_modes[0].fm_name == "df_H2O"
        assert s.failure_modes[0].failure_param == [1.0]  # scalar coerced


class TestObjFMInstSpec:
    """Wire-format contract of the on-demand failure mode spec."""

    def test_defaults_and_scalar_coercion(self):
        from cod3s.specs.study_yaml import ObjFMInstSpec

        spec = ObjFMInstSpec(
            fm_name="miss", targets=["C1"], failure_param=0.3, repair_param=0.1
        )
        assert spec.cls == "ObjFMInst"
        assert spec.failure_param == [0.3]
        assert spec.repair_param == [0.1]
        # The solicitation is the inherited failure_cond — no extra field.
        assert spec.failure_cond is True

    def test_gamma_must_be_a_probability(self):
        from cod3s.specs.study_yaml import ObjFMInstSpec

        with pytest.raises(pydantic.ValidationError, match=r"\[0, 1\]"):
            ObjFMInstSpec(fm_name="miss", targets=["C1"], failure_param=[1.5])

    def test_union_discrimination(self):
        from cod3s.specs.study_yaml import ObjFMInstSpec

        study = StudyYaml.model_validate(
            {
                "name": "s",
                "failure_modes": [
                    {
                        "cls": "ObjFMInst",
                        "fm_name": "miss",
                        "targets": ["C1"],
                        "failure_param": [0.3, 0.2],
                        "repair_param": [0.1, 0.1],
                    }
                ],
            }
        )
        assert isinstance(study.failure_modes[0], ObjFMInstSpec)

    def test_generic_spec_rejects_objfm_inst(self):
        from cod3s.specs.study_yaml import ObjFMGenericSpec

        with pytest.raises(pydantic.ValidationError, match="typed spec"):
            ObjFMGenericSpec(cls="ObjFMInst", fm_name="miss", targets=["C1"])
