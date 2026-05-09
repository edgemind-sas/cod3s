"""Pydantic schemas for the ``study.yaml`` format consumed by ``run-cod3s-study``.

The schemas in this module are the **single source of truth** for the
study YAML wire format. They mirror the constructors of the runtime
classes they target so a ``model_dump()`` of a spec can be passed to
the corresponding constructor with ``cls(**spec_dict)`` (minus the
``cls`` discriminator field).

Layout (top-level YAML):

.. code-block:: yaml

    name: "My study"
    description: "..."
    version: "1.0.0"          # optional, see STUDY_YAML_VERSION
    system_model: "model.yaml"  # path to the model used by the SystemBuilder
    failure_modes: [...]      # list[FailureModeSpec] — discriminated on cls
    events: [...]             # list[EventSpec]
    indicators: [...]         # list[IndicatorSpec]
    targets: [...]            # list[TargetSpec]
    attribute_overrides:      # optional, platform-style overrides
      component_attr: [...]
      failure_mode_param: [...]
    simulation:               # SimulationConfig
      nb_runs: 1000
      schedule: [...]
      seed: 42
    results: {...}            # ResultsConfig (optional)
    hooks: {...}              # HookSpec (optional)

Backward-compat: a study.yaml that uses the **legacy** ``occ_law``
discriminator (``"exp"`` / ``"delay"``) instead of ``cls`` is accepted
— the validator translates it. New writers should emit ``cls``.

The class hierarchy under ``FailureModeSpec`` is a Pydantic
discriminated union on the ``cls`` field. To support a future
``ObjFM`` subclass without modifying this module, downstream code
emits ``ObjFMGenericSpec`` instances (which preserve unknown kwargs
via ``extra="allow"``) and registers the subclass at runtime via
``cod3s.scripts.study_runner.register_fm_class``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

import pydantic

#: Semantic version of the wire format. Bump:
#:
#: - **patch** when adding an optional field with a default
#: - **minor** when adding a required field (or a new shape that older
#:   readers can choose to ignore)
#: - **major** when removing a field, renaming a field, or changing
#:   the meaning of an existing field
#:
#: Validators check ``major`` matches what they expect; minor/patch
#: drift is tolerated.
STUDY_YAML_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Failure mode specs — discriminated union on ``cls``.
# ---------------------------------------------------------------------------


class FailureModeBaseSpec(pydantic.BaseModel):
    """Common fields shared by all ``ObjFM*`` subclasses.

    Mirrors the base constructor of ``cod3s.ObjFM`` (cf.
    ``cod3s/pycatshoo/component.py:1161``). The ``cls`` field is the
    Pydantic discriminator; concrete subclasses fix it via ``Literal``.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    fm_name: str = pydantic.Field(..., description="Failure mode name (must be unique across the study).")
    targets: list[str] = pydantic.Field(..., description="Target component names affected by this failure mode.")
    target_name: str | None = pydantic.Field(
        None,
        description=(
            "Custom name for the target combination. If None, auto-generated "
            "by ``ObjFM._factorize_target_names`` from the target list."
        ),
    )

    failure_state: str = pydantic.Field("occ", description="Failure state name in the automaton.")
    failure_cond: bool | str | list = pydantic.Field(
        True,
        description=(
            "Failure firing condition. ``True`` = always fireable. "
            "``str`` = name of a callable resolved at runtime. "
            "``list`` = structured cond (cf. ObjFM docstring)."
        ),
    )
    failure_effects: dict[str, Any] = pydantic.Field(
        default_factory=dict,
        description="Effects applied on the failure transition (var_name → value).",
    )

    repair_state: str = pydantic.Field("rep", description="Repair state name in the automaton.")
    repair_cond: bool | str | list = pydantic.Field(True, description="Repair firing condition. Same shape as failure_cond.")
    repair_effects: dict[str, Any] = pydantic.Field(
        default_factory=dict,
        description="Effects applied on the repair transition.",
    )

    behaviour: Literal["internal", "external", "external_rep_indep"] = pydantic.Field(
        "internal",
        description="ObjFM behaviour mode (cf. cod3s.ObjFM docstring).",
    )
    drop_inactive_automata: bool = pydantic.Field(
        True, description="Whether to skip creating automata with inactive (zero-rate) occ laws."
    )

    enabled: bool = pydantic.Field(
        True,
        description=(
            "When False, the failure mode is parsed but not added to the system "
            "(non-instantiated). Useful for sensitivity studies."
        ),
    )


def _coerce_param_array(v: Any) -> list[Any]:
    """Promote a scalar param to a single-element list.

    Legacy study.yaml files (cf. ``tests/usecases/.../study.yaml``)
    write ``failure_param: 1`` as a scalar. The runtime promotes it
    via ``[failure_param] if not isinstance(failure_param, list)``,
    we mirror that here so the spec round-trips correctly.
    """
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


class ObjFMExpSpec(FailureModeBaseSpec):
    """Exponential law failure mode. Mirror of ``cod3s.ObjFMExp``.

    ``failure_param`` is a list of ``λ`` (rates) indexed by cc-order
    (1-based: index 0 = order 1 failures). ``repair_param`` is a list
    of ``μ`` (rates).

    Example: 3 components, cc_order up to 3 → ``failure_param =
    [λ_indep, λ_2_in_3, λ_3_in_3]``.
    """

    cls: Literal["ObjFMExp"] = pydantic.Field(
        "ObjFMExp",
        description="Discriminator. Locks this spec to ObjFMExp.",
    )

    failure_param: list[float] = pydantic.Field(
        default_factory=list,
        description="Failure rates (λ) per cc-order, length ≤ len(targets).",
    )
    repair_param: list[float] = pydantic.Field(
        default_factory=list,
        description="Repair rates (μ) per cc-order, length ≤ len(targets).",
    )

    @pydantic.field_validator("failure_param", "repair_param", mode="before")
    @classmethod
    def _accept_scalar(cls, v: Any) -> list[Any]:
        return _coerce_param_array(v)


class ObjFMDelaySpec(FailureModeBaseSpec):
    """Deterministic delay failure mode. Mirror of ``cod3s.ObjFMDelay``.

    ``failure_param`` = time-to-failure (ttf) per cc-order;
    ``repair_param`` = time-to-repair (ttr) per cc-order.
    """

    cls: Literal["ObjFMDelay"] = pydantic.Field("ObjFMDelay")

    failure_param: list[float] = pydantic.Field(default_factory=list)
    repair_param: list[float] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("failure_param", "repair_param", mode="before")
    @classmethod
    def _accept_scalar(cls, v: Any) -> list[Any]:
        return _coerce_param_array(v)


class ObjFMGenericSpec(FailureModeBaseSpec):
    """Forward-compatible generic ObjFM spec.

    Use when targeting a custom ``ObjFM`` subclass not yet known to
    ``cod3s/specs``. The runtime resolves ``cls`` against the
    ``register_fm_class``-populated registry; the user provides
    ``failure_param_name`` / ``repair_param_name`` explicitly to
    match the subclass's parameter shape.

    Subclass-specific kwargs pass through via ``extra="allow"``.
    """

    model_config = pydantic.ConfigDict(extra="allow")

    cls: str = pydantic.Field(
        ...,
        description="ObjFM subclass name registered via cod3s.scripts.study_runner.register_fm_class.",
    )

    failure_param_name: list[str] = pydantic.Field(
        default_factory=list,
        description="Names of failure parameters (e.g. ['lambda'] or ['weibull_k', 'weibull_lambda']).",
    )
    failure_param: list[Any] = pydantic.Field(default_factory=list)

    repair_param_name: list[str] = pydantic.Field(
        default_factory=list,
        description="Names of repair parameters.",
    )
    repair_param: list[Any] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("failure_param", "repair_param", mode="before")
    @classmethod
    def _accept_scalar(cls, v: Any) -> list[Any]:
        return _coerce_param_array(v)

    @pydantic.field_validator("cls")
    @classmethod
    def _reject_known_classes(cls, v: str) -> str:
        if v in {"ObjFMExp", "ObjFMDelay"}:
            raise ValueError(
                f"Use the typed spec ({v}Spec) instead of ObjFMGenericSpec for {v!r}."
            )
        return v


def _failure_mode_discriminator(v: Any) -> str:
    """Callable discriminator for the FailureModeSpec union.

    Pydantic 2 requires every union member to declare its discriminator
    field as a ``Literal``. Since ``ObjFMGenericSpec.cls`` is an open
    ``str`` (any registered subclass name), we route it via a callable
    that returns one of the three tags ``"ObjFMExp"``, ``"ObjFMDelay"``,
    ``"__generic__"``.
    """
    cls = v.get("cls") if isinstance(v, dict) else getattr(v, "cls", None)
    if cls == "ObjFMExp":
        return "ObjFMExp"
    if cls == "ObjFMDelay":
        return "ObjFMDelay"
    return "__generic__"


#: Discriminated union for failure modes. Dispatches via the ``cls``
#: field for ObjFMExp / ObjFMDelay, falls through to ObjFMGenericSpec
#: for any other (registered) subclass name.
FailureModeSpec = Annotated[
    Union[
        Annotated[ObjFMExpSpec, pydantic.Tag("ObjFMExp")],
        Annotated[ObjFMDelaySpec, pydantic.Tag("ObjFMDelay")],
        Annotated[ObjFMGenericSpec, pydantic.Tag("__generic__")],
    ],
    pydantic.Discriminator(_failure_mode_discriminator),
]


# ---------------------------------------------------------------------------
# Event specs — mirror of ``cod3s.ObjEvent``.
# ---------------------------------------------------------------------------


class EventSpec(pydantic.BaseModel):
    """Mirror of ``cod3s.ObjEvent`` constructor.

    Cf. ``cod3s/pycatshoo/component.py:829``.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    cls: Literal["ObjEvent"] = pydantic.Field("ObjEvent")
    name: str
    cond: list | str | bool = pydantic.Field(
        ...,
        description=(
            "Event firing condition. Either a structured nested-list "
            "spec (cf. ObjEvent docstring) or a callable name."
        ),
    )
    inner_logic: Literal["all", "any"] = "all"
    outer_logic: Literal["all", "any"] = "any"
    cond_operator: Literal["==", "!=", "<", "<=", ">", ">="] = "=="
    cond_value: Any = True
    tempo_occ: float = 0.0
    tempo_not_occ: float = 0.0
    event_aut_name: str = "ev"
    occ_state_name: str = "occ"
    not_occ_state_name: str = "not_occ"
    enabled: bool = True


# ---------------------------------------------------------------------------
# Indicator specs — mirror of ``system.add_indicator`` regex shape.
# ---------------------------------------------------------------------------


class IndicatorSpec(pydantic.BaseModel):
    """Mirror of ``cod3s.PycSystem.add_indicator`` keyword arguments.

    Cf. ``cod3s/pycatshoo/system.py:418``. Supports regex matching on
    component name + attribute name, plus pass-through of any
    PycAttrIndicator constructor kwargs via ``extra="allow"``.
    """

    model_config = pydantic.ConfigDict(extra="allow")

    component: str = pydantic.Field(
        ".*",
        description="Regex pattern for component names (anchored to ^…$ at runtime).",
    )
    attr_name: str = pydantic.Field(
        ".*",
        description="Regex pattern for attribute names.",
    )
    attr_type: str = pydantic.Field(..., description="Attribute type ('VAR', 'REF', etc.).")
    stats: list[str] = pydantic.Field(default_factory=lambda: ["mean"])
    enabled: bool = True


# ---------------------------------------------------------------------------
# Target specs — mirror of ``system.add_targets``.
# ---------------------------------------------------------------------------


class TargetSpec(pydantic.BaseModel):
    """Mirror of an entry consumed by ``cod3s.PycSystem.add_targets``.

    Two shapes: either ``name`` matches an existing ObjEvent (occ
    transition becomes the target), or the full
    ``addTarget(name, var, type, op?, value?)`` tuple is provided.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    name: str
    var: str | None = pydantic.Field(
        None,
        description="Variable expression (e.g. 'comp.attr.signal_out'). Leave None for ObjEvent-based targets.",
    )
    var_type: Literal["ST", "VAR"] | None = pydantic.Field(None, description="'ST' = state, 'VAR' = variable.")
    operator: Literal["==", "!=", "<", "<=", ">", ">="] | None = None
    value: Any = None
    enabled: bool = True


# ---------------------------------------------------------------------------
# Attribute overrides — extension for cod3s-platform integration.
# ---------------------------------------------------------------------------


class AttributeOverride(pydantic.BaseModel):
    """A single attribute override applied at simulation start.

    Used by ``cod3s-platform`` to project user-edited overrides
    (lambda/mu tweaks, init flags) onto the built system before
    ``simulate()``.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    component: str
    attribute: str
    value: Any
    attribute_role: str | None = pydantic.Field(
        None,
        description="Optional role hint ('init', 'logic', etc.) — not used by the runtime.",
    )
    source: str | None = pydantic.Field(None, description="Free-form provenance label (audit/debug).")


class FailureModeParamOverride(pydantic.BaseModel):
    """Override of a single failure mode parameter (e.g. lambda or mu)."""

    model_config = pydantic.ConfigDict(extra="forbid")

    fm_name: str = pydantic.Field(..., description="Target failure mode name (must be unique).")
    field: Literal["failure_param", "repair_param"] = pydantic.Field(
        ...,
        description="Which array to override. The full array is replaced.",
    )
    value: list[Any] = pydantic.Field(..., description="New parameter array (length must match cc-order count).")
    source: str | None = None


class AttributeOverrides(pydantic.BaseModel):
    """Container for the two override flavours.

    Optional in study.yaml. Empty container = no override.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    component_attr: list[AttributeOverride] = pydantic.Field(default_factory=list)
    failure_mode_param: list[FailureModeParamOverride] = pydantic.Field(default_factory=list)


# ---------------------------------------------------------------------------
# Simulation parameters.
# ---------------------------------------------------------------------------


class ScheduleEntry(pydantic.BaseModel):
    """A single observation schedule entry.

    Two shapes:

    - ``{start: float, end: float, nvalues: int}`` for a linear range
    - ``{instant: float}`` for a single timestamp

    The runner expands ranges into instant lists.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    start: float | None = None
    end: float | None = None
    nvalues: int | None = None
    instant: float | None = None

    @pydantic.model_validator(mode="after")
    def _check_shape(self) -> "ScheduleEntry":
        if self.instant is not None:
            if any(x is not None for x in (self.start, self.end, self.nvalues)):
                raise ValueError("ScheduleEntry: 'instant' is exclusive with start/end/nvalues.")
            return self
        if self.start is None or self.end is None or self.nvalues is None:
            raise ValueError(
                "ScheduleEntry: provide either 'instant' or all of (start, end, nvalues)."
            )
        if self.nvalues < 1:
            raise ValueError("ScheduleEntry.nvalues must be ≥ 1.")
        if self.end < self.start:
            raise ValueError("ScheduleEntry.end must be ≥ start.")
        return self


class SimulationConfig(pydantic.BaseModel):
    """Mirror of the ``simulation`` section consumed by ``run-cod3s-study``.

    Pass-through ``extra="allow"`` so simulator-specific knobs
    (verbosity, MPI hints, etc.) survive the round-trip.
    """

    model_config = pydantic.ConfigDict(extra="allow")

    nb_runs: int | None = pydantic.Field(None, description="Monte-Carlo run count. None = simulator default.")
    schedule: list[ScheduleEntry] = pydantic.Field(
        default_factory=list,
        description="Observation schedule (list of ranges or instants).",
    )
    seed: int | None = pydantic.Field(None, description="RNG seed for reproducibility.")


# ---------------------------------------------------------------------------
# Results / output configuration.
# ---------------------------------------------------------------------------


class ResultsIndicatorSpec(pydantic.BaseModel):
    """Indicator CSV export spec (cf. run_cod3s_study.py:189-247)."""

    model_config = pydantic.ConfigDict(extra="forbid")

    id: str = pydantic.Field(..., description="Output file stem (used as 'output_dir/{id}.csv').")
    output: list[Literal["csv"]] = pydantic.Field(default_factory=lambda: ["csv"])
    comp_pattern: str = pydantic.Field(".*", description="Component name regex.")
    attr_pattern: str = pydantic.Field(".*", description="Attribute name regex.")


class PlotIndicatorSpec(pydantic.BaseModel):
    """Plot output spec — passed almost as-is to ``system.indic_px_line``."""

    model_config = pydantic.ConfigDict(extra="allow")

    id: str = pydantic.Field(..., description="Output file stem.")
    output: list[Literal["html", "png"]] = pydantic.Field(default_factory=lambda: ["html"])
    write_options: dict[str, Any] = pydantic.Field(default_factory=dict)


class ResultsConfig(pydantic.BaseModel):
    """Results output specification."""

    model_config = pydantic.ConfigDict(extra="forbid")

    indicators: list[ResultsIndicatorSpec] = pydantic.Field(default_factory=list)
    plot_indicators: list[PlotIndicatorSpec] = pydantic.Field(default_factory=list)


# ---------------------------------------------------------------------------
# Hooks (custom Python files executed before/after simulation).
# ---------------------------------------------------------------------------


class HookSpec(pydantic.BaseModel):
    """Lists of hook scripts to run around the simulation."""

    model_config = pydantic.ConfigDict(extra="forbid")

    before_simu: list[str] = pydantic.Field(default_factory=list)
    after_simu: list[str] = pydantic.Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level study YAML.
# ---------------------------------------------------------------------------


class StudyYaml(pydantic.BaseModel):
    """Root of the study.yaml file.

    All sub-sections are optional except ``simulation`` (which itself
    has only optional fields). A study.yaml with no failure_modes /
    indicators / events / targets is a valid (degenerate) study that
    just runs the bare system.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    name: str = pydantic.Field(..., description="Human-readable study name.")
    description: str = pydantic.Field("", description="Free-form description.")
    version: str = pydantic.Field(STUDY_YAML_VERSION, description="Wire-format semver.")

    system_model: str | None = pydantic.Field(
        None,
        description=(
            "Path (relative to study.yaml) of the model artifact consumed by "
            "the SystemBuilder. Format depends on the builder: a YAML model "
            "for ``YamlModelBuilder``, a platform JSON export for "
            "``PlatformExportBuilder``."
        ),
    )

    failure_modes: list[FailureModeSpec] = pydantic.Field(default_factory=list)
    events: list[EventSpec] = pydantic.Field(default_factory=list)
    indicators: list[IndicatorSpec] = pydantic.Field(default_factory=list)
    targets: list[TargetSpec] = pydantic.Field(default_factory=list)
    attribute_overrides: AttributeOverrides | None = None
    simulation: SimulationConfig = pydantic.Field(default_factory=SimulationConfig)
    results: ResultsConfig | None = None
    hooks: HookSpec | None = None

    @pydantic.model_validator(mode="before")
    @classmethod
    def _legacy_occ_law_to_cls(cls, data: Any) -> Any:
        """Translate legacy ``occ_law: "exp"|"delay"`` to ``cls`` discriminator.

        Older study.yaml files (cf. tests/usecases/.../study.yaml)
        used ``occ_law`` to select between exponential and delay laws.
        Map it to the new ``cls`` discriminator at parse time so
        existing files keep loading.
        """
        if not isinstance(data, dict):
            return data
        modes = data.get("failure_modes")
        if not isinstance(modes, list):
            return data
        for fm in modes:
            if not isinstance(fm, dict):
                continue
            occ_law = fm.pop("occ_law", None)
            if "cls" in fm:
                # cls takes precedence; occ_law is dropped silently to
                # let writers transition without churn.
                continue
            if occ_law == "exp":
                fm["cls"] = "ObjFMExp"
            elif occ_law == "delay":
                fm["cls"] = "ObjFMDelay"
            elif occ_law is not None:
                raise ValueError(
                    f"failure_modes[{fm.get('fm_name', '?')!r}]: unknown "
                    f"legacy occ_law={occ_law!r}. Use cls=ObjFMExp/ObjFMDelay "
                    f"or one of the spec classes registered via register_fm_class."
                )
        return data

    @pydantic.model_validator(mode="after")
    def _check_unique_fm_names(self) -> "StudyYaml":
        """Reject duplicate fm_name (the runtime uses fm_name as id)."""
        seen: set[str] = set()
        for fm in self.failure_modes:
            if fm.fm_name in seen:
                raise ValueError(
                    f"Duplicate failure_modes.fm_name {fm.fm_name!r}. "
                    f"Each ObjFM must have a unique name across the study."
                )
            seen.add(fm.fm_name)
        return self

    @pydantic.model_validator(mode="after")
    def _check_fm_targets_match_param_arity(self) -> "StudyYaml":
        """Surface configuration errors at parse time, not runtime.

        ``cod3s.ObjFM.__init__`` raises ``ValueError`` if
        ``len(failure_param) > len(targets)`` (cf.
        component.py:1235-1241). We catch that earlier with a clearer
        message tied to the field names.
        """
        for fm in self.failure_modes:
            if not isinstance(fm, (ObjFMExpSpec, ObjFMDelaySpec, ObjFMGenericSpec)):
                continue
            n_targets = len(fm.targets)
            for field in ("failure_param", "repair_param"):
                arr = getattr(fm, field)
                if len(arr) > n_targets:
                    raise ValueError(
                        f"failure_modes[{fm.fm_name!r}].{field} has {len(arr)} entries "
                        f"but only {n_targets} target(s). Each entry of {field} "
                        f"corresponds to one cc-order; the array must be no longer "
                        f"than the number of targets."
                    )
        return self
