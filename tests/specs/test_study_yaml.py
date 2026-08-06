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
    ObjFMInstSpec,
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


class TestFailureModeStep:
    """``step``: the PDMP phase the mode's effect methods are placed in.

    Reachable from the wire since 1.0.2 — it was a ``ObjMode2S``
    constructor kwarg with no way to declare it in a study.yaml, and
    ``extra="forbid"`` on the base rejected the key outright.
    """

    @pytest.mark.parametrize("spec_cls", [ObjFMExpSpec, ObjFMDelaySpec, ObjFMInstSpec])
    def test_default_is_none(self, spec_cls):
        """No phase declared = the historical behaviour, untouched."""
        spec = spec_cls(fm_name="m", targets=["C"])
        assert spec.step is None
        # ``add_failure_modes`` dumps with exclude={"cls", "enabled"} and
        # passes the rest to the constructor: ``step=None`` must be there
        # (every registered FM class defaults it to None).
        assert spec.model_dump(exclude={"cls", "enabled"})["step"] is None

    @pytest.mark.parametrize("spec_cls", [ObjFMExpSpec, ObjFMDelaySpec, ObjFMInstSpec])
    def test_value_reaches_the_constructor_kwargs(self, spec_cls):
        spec = spec_cls(fm_name="m", targets=["C"], step="failure_propagation")
        assert spec.step == "failure_propagation"
        kwargs = spec.model_dump(exclude={"cls", "enabled"})
        assert kwargs["step"] == "failure_propagation"

    def test_generic_spec_declares_it_once(self):
        """ObjFMGenericSpec allows extras: check the two paths agree.

        ``step`` is a declared field on the base, so it must NOT also
        land in ``__pydantic_extra__`` (a duplicate key in the dump
        would be a silent-disagreement channel).
        """
        spec = ObjFMGenericSpec(
            fm_name="m", targets=["C"], cls="ObjFMCustom", step="phase_1"
        )
        assert spec.step == "phase_1"
        assert "step" not in (spec.__pydantic_extra__ or {})
        assert spec.model_dump()["step"] == "phase_1"

    def test_generic_spec_type_checked(self):
        """Being declared, ``step`` is now validated on the generic spec too."""
        with pytest.raises(pydantic.ValidationError):
            ObjFMGenericSpec(fm_name="m", targets=["C"], cls="ObjFMCustom", step=12)

    def test_study_yaml_end_to_end(self):
        study = StudyYaml(
            name="s",
            failure_modes=[
                {
                    "fm_name": "m",
                    "targets": ["C"],
                    "cls": "ObjFMDelay",
                    "step": "failure_propagation",
                }
            ],
        )
        assert study.failure_modes[0].step == "failure_propagation"

    def test_typo_still_rejected(self):
        """``extra="forbid"`` is intact — only ``step`` was admitted."""
        with pytest.raises(pydantic.ValidationError):
            ObjFMExpSpec(fm_name="m", targets=["C"], stepp="failure_propagation")


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
        # cls=ObjFMExp wins, the legacy STRING occ_law is dropped silently
        # (writers transition without churn).
        assert study.failure_modes[0].cls == "ObjFMExp"

    def test_structured_occ_law_is_preserved(self):
        """1.14.2 regression: the native ObjMode2S wire carries occ_law as a
        STRUCTURED ModeLaw spec (a mapping) — the legacy-string migration
        must NOT swallow it (it used to pop it unconditionally, silently
        deleting the law from the wire: silent-wrong-model channel)."""
        law = {"cls": "exp", "rate": [1e-3, 0.0]}
        study = StudyYaml(
            name="s",
            failure_modes=[
                {
                    "cls": "ObjMode2S",
                    "fm_name": "m",
                    "targets": ["C1", "C2"],
                    "occ_state": "occ",
                    "not_occ_state": "rep",
                    "occ_law": law,
                    "not_occ_law": {"cls": "exp", "rate": [0.1, 0.0]},
                }
            ],
        )
        fm = study.failure_modes[0]
        assert fm.cls == "ObjMode2S"
        extras = fm.__pydantic_extra__ or {}
        assert extras.get("occ_law") == law
        assert fm.model_dump()["occ_law"] == law


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


#: A study in the shape the anchor idiom actually takes: a ``x-`` key
#: holding the definitions, a ``<<:`` merge and a scalar alias consuming
#: them from a typed section. Modelled on the repo's own
#: ``tests/usecases/indus_4_0_Electrolyseur/test_run_cod3s_negativeH2``.
ANCHORED_STUDY_YAML = """
name: "anchored"

x-custom_config:
  plot_layout_base: &plot_layout_base
    markers: false
    layout:
      xaxis_title: "Temps (h)"
      showlegend: false
    write_options:
      width: 800
      height: 400

  color_palette:
    orange: &cs_orange ["#ff7f0e"]
    green: &cs_green ["#2ca02c"]

simulation:
  nb_runs: 2

results:
  plot_indicators:
    - id: "Electro"
      color_discrete_sequence: *cs_orange
      <<: *plot_layout_base

    - id: "Tank"
      color_discrete_sequence: *cs_green
      <<: *plot_layout_base
"""


class TestExtensionKeys:
    """Top-level ``x-`` keys: the escape hatch for YAML anchor holders.

    ``StudyYaml`` is ``extra="forbid"`` so a misspelled section is an
    error — but that also made the standard anchor idiom unexpressible:
    a study factoring repeated plot styling has nowhere to *define* the
    anchors, every section of the schema being typed. Since 1.0.3 a
    top-level ``x-`` key is dropped before validation. It must stay
    exactly that narrow.
    """

    def test_extension_key_accepted(self):
        s = StudyYaml.model_validate({"name": "s", "x-anchors": {"a": 1}})
        assert s.name == "s"

    def test_extension_key_absent_from_the_validated_model(self):
        """Stripped, not retained: nothing may read it back as an API."""
        s = StudyYaml.model_validate({"name": "s", "x-anchors": {"a": 1}})
        assert s.__pydantic_extra__ is None
        assert not hasattr(s, "x-anchors")
        assert "x-anchors" not in s.model_dump()
        assert "anchors" not in s.model_dump()

    def test_any_value_shape_accepted(self):
        """The key is dropped whatever it holds — it is never inspected."""
        s = StudyYaml.model_validate(
            {
                "name": "s",
                "x-mapping": {"a": 1},
                "x-list": [1, 2],
                "x-scalar": "text",
                "x-null": None,
            }
        )
        assert s.model_dump()["name"] == "s"

    def test_typo_still_rejected(self):
        """The whole point: the hatch is explicit, not a loosening."""
        with pytest.raises(pydantic.ValidationError, match="simulaton"):
            StudyYaml.model_validate({"name": "s", "simulaton": {"nb_runs": 1}})

    @pytest.mark.parametrize(
        "key",
        [
            "_anchors",  # the underscore convention: one convention only
            "X-anchors",  # matched case-sensitively
            "xanchors",  # the separator is part of the prefix
            "x_anchors",
            "custom_config",  # the pre-1.0.3 spelling of the idiom
        ],
    )
    def test_only_the_x_dash_prefix_is_admitted(self, key):
        with pytest.raises(pydantic.ValidationError, match="extra_forbidden"):
            StudyYaml.model_validate({"name": "s", key: {"a": 1}})

    def test_nested_forbid_models_are_unchanged(self):
        """Root-only: anchors are document-scoped, so the root suffices."""
        with pytest.raises(pydantic.ValidationError, match="extra_forbidden"):
            StudyYaml.model_validate({"name": "s", "results": {"x-anchors": {"a": 1}}})

    def test_input_mapping_is_not_mutated(self):
        """Validating must not strip the key from the caller's own dict."""
        data = {"name": "s", "x-anchors": {"a": 1}}
        StudyYaml.model_validate(data)
        assert data["x-anchors"] == {"a": 1}

    def test_round_trip(self):
        """A dump of a study parsed with extension keys re-validates."""
        s = StudyYaml.model_validate({"name": "s", "x-anchors": {"a": 1}})
        assert StudyYaml.model_validate(s.model_dump()).name == "s"

    def test_anchors_resolve_through_a_realistic_study(self):
        """The idiom end-to-end: ``<<:`` merge + scalar alias."""
        study = StudyYaml.model_validate(yaml.safe_load(ANCHORED_STUDY_YAML))

        assert study.simulation.nb_runs == 2
        assert [p.id for p in study.results.plot_indicators] == ["Electro", "Tank"]

        electro, tank = study.results.plot_indicators
        # Scalar alias — a distinct value per entry.
        assert electro.model_dump()["color_discrete_sequence"] == ["#ff7f0e"]
        assert tank.model_dump()["color_discrete_sequence"] == ["#2ca02c"]
        # ``<<:`` merge — the shared layout landed on both.
        for plot in (electro, tank):
            dump = plot.model_dump()
            assert dump["markers"] is False
            assert dump["layout"]["xaxis_title"] == "Temps (h)"
            assert plot.write_options == {"width": 800, "height": 400}

        # And the holder itself did not survive into the model.
        assert "x-custom_config" not in study.model_dump()

    def test_interaction_with_the_legacy_occ_law_validator(self):
        """Both ``mode="before"`` validators run, in either order.

        ``_drop_extension_keys`` is declared last so Pydantic runs it
        first (reverse definition order), but the two are independent:
        this locks that a study using the anchor idiom AND the legacy
        ``occ_law`` discriminator — anchored from the ``x-`` holder —
        parses exactly as each would alone.
        """
        study = StudyYaml.model_validate(yaml.safe_load("""
                name: "legacy + anchors"

                x-defaults:
                  fm_base: &fm_base
                    occ_law: "exp"
                    repair_param: 0.167

                failure_modes:
                  - fm_name: "df_a"
                    targets: ["C1"]
                    failure_param: 1.0e-5
                    <<: *fm_base

                  - fm_name: "df_b"
                    targets: ["C2"]
                    failure_param: 4.0e-6
                    <<: *fm_base
                """))
        assert [fm.cls for fm in study.failure_modes] == ["ObjFMExp", "ObjFMExp"]
        assert all(isinstance(fm, ObjFMExpSpec) for fm in study.failure_modes)
        assert [fm.repair_param for fm in study.failure_modes] == [[0.167], [0.167]]
        assert "x-defaults" not in study.model_dump()

    def test_unknown_legacy_occ_law_still_raises_through_the_hatch(self):
        """The extension key must not shadow a downstream validation error."""
        with pytest.raises(pydantic.ValidationError, match="unknown "):
            StudyYaml.model_validate(
                {
                    "name": "s",
                    "x-anchors": {"a": 1},
                    "failure_modes": [
                        {"fm_name": "m", "targets": ["C"], "occ_law": "weibull"}
                    ],
                }
            )


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
