"""Public Pydantic specifications for COD3S study YAML serialization.

The classes exposed here mirror the COD3S runtime constructors (``ObjFM``,
``ObjEvent``, ``add_indicator``, ``addTarget``) so a study YAML file can
be validated, round-tripped, and consumed by ``run-cod3s-study`` without
parallel maintenance of two schemas.

External consumers (notably ``cod3s-platform`` and any third-party
study generator) should import from this module rather than redefine
their own Pydantic models.
"""

from cod3s.specs.study_yaml import (
    AttributeOverride,
    AttributeOverrides,
    EventSpec,
    FailureModeBaseSpec,
    FailureModeSpec,
    HookSpec,
    IndicatorSpec,
    ObjFMDelaySpec,
    ObjFMExpSpec,
    ObjFMGenericSpec,
    PlotIndicatorSpec,
    ResultsConfig,
    ResultsIndicatorSpec,
    ScheduleEntry,
    SimulationConfig,
    StudyYaml,
    TargetSpec,
    STUDY_YAML_VERSION,
)

__all__ = [
    "AttributeOverride",
    "AttributeOverrides",
    "EventSpec",
    "FailureModeBaseSpec",
    "FailureModeSpec",
    "HookSpec",
    "IndicatorSpec",
    "ObjFMDelaySpec",
    "ObjFMExpSpec",
    "ObjFMGenericSpec",
    "PlotIndicatorSpec",
    "ResultsConfig",
    "ResultsIndicatorSpec",
    "ScheduleEntry",
    "SimulationConfig",
    "StudyYaml",
    "TargetSpec",
    "STUDY_YAML_VERSION",
]
