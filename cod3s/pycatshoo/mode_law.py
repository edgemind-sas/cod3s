"""Occurrence-law specifications for the generic two-state mode engine.

``ObjMode2S`` (the generic ``occ`` / ``not_occ`` engine behind the
``ObjFM*`` / ``ObjEvent`` façades) declares the law of each direction
through one of the typed specs below, discriminated on ``cls``:

* :class:`ModeLawExp` — exponential (``rate``);
* :class:`ModeLawDelay` — deterministic delay (``time``);
* :class:`ModeLawInst` — instantaneous Bernoulli draw per rising edge of
  the composite guard (``prob``), with the anti-Zeno parked micro-state
  machinery built by the engine.

Each parameter accepts a scalar or a per-CC-order vector. The specs stay
deliberately dumb about common-cause combinatorics: vector-length
validation against ``order_max`` lives in the engine (the spec does not
know the number of targets). Native engine rule (strict, no silent
padding): a scalar is only meaningful for a single-target mode; a
multi-target mode must provide the full per-order vector, using explicit
zeros for inactive orders.

This module is pure pydantic (no cod3s imports) so any layer — including
``deg_mode`` in a future convergence — can import it without cycles. The
``DegLaw*`` specs of :mod:`cod3s.pycatshoo.deg_mode` are kept
field-compatible (same ``cls`` tags, same parameter names); the schema
subset is pinned by ``tests/pyc_obj/test_mode_law.py``.
"""

import typing

import pydantic


def ensure_non_negative(value, what):
    """Shared scalar-or-vector non-negativity validator.

    Raises ``ValueError`` with a law-specific message when any entry is
    negative. Returns the value unchanged (pydantic validator contract).
    """
    values = value if isinstance(value, list) else [value]
    for v in values:
        if v < 0:
            raise ValueError(
                f"{what} must be >= 0, got {v} (sign mistake in the " f"configuration?)"
            )
    return value


class _ModeLawBase(pydantic.BaseModel):
    """Common surface of the three law specs.

    ``param_field`` drives the engine-native parameter variable naming
    (``occ_<param_field>`` / ``not_occ_<param_field>``, plus the usual
    ``__{order}_o_{order_max}`` CC suffix).
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    #: Name of the law parameter field ("rate" / "time" / "prob").
    param_field: typing.ClassVar[str]

    def values(self):
        """Return the parameter as a list (scalar -> 1-list)."""
        raw = getattr(self, self.param_field)
        return list(raw) if isinstance(raw, list) else [raw]

    def is_active_value(self, value):
        """Whether a per-order parameter value makes the law active.

        Active = worth building the combination automaton when
        ``drop_inactive_automata`` is on. Default: always active
        (``delay`` — time 0 is a valid delay; ``inst`` — prob 0 is a
        valid never-drawing mode). ``exp`` overrides: rate 0 = inactive.
        """
        return True

    def to_bkd_law(self, param):
        """Return the backend law dict, parametrized by ``param``
        (a float or a PyCATSHOO parameter variable)."""
        return {"cls": self.cls, self.param_field: param}


class ModeLawExp(_ModeLawBase):
    """Exponential occurrence law (rate per unit of time)."""

    param_field: typing.ClassVar[str] = "rate"

    cls: typing.Literal["exp"] = "exp"
    rate: float | list[float] = pydantic.Field(
        ...,
        description=(
            "Rate. A list is the per-CC-order vector (strict length == "
            "number of targets; explicit 0 for inactive orders)."
        ),
    )

    @pydantic.field_validator("rate")
    @classmethod
    def _rate_non_negative(cls, v):
        return ensure_non_negative(v, "exp law rate")

    def is_active_value(self, value):
        return value > 0


class ModeLawDelay(_ModeLawBase):
    """Deterministic delay occurrence law (time 0 is a valid delay)."""

    param_field: typing.ClassVar[str] = "time"

    cls: typing.Literal["delay"] = "delay"
    time: float | list[float] = pydantic.Field(
        ...,
        description=(
            "Deterministic delay. A list is the per-CC-order vector "
            "(strict length == number of targets)."
        ),
    )

    @pydantic.field_validator("time")
    @classmethod
    def _time_non_negative(cls, v):
        return ensure_non_negative(v, "delay law time")


class ModeLawInst(_ModeLawBase):
    """Instantaneous Bernoulli draw, one per rising edge of the guard.

    The engine builds the anti-Zeno machinery (armed / parked
    micro-state split, ``inst p=1`` re-arm) — see the ObjMode2S
    docstring. ``prob`` 0 is a valid never-drawing mode; ``prob`` 1 on
    BOTH directions with trivially-true conditions is rejected by the
    engine (certain livelock).
    """

    param_field: typing.ClassVar[str] = "prob"

    cls: typing.Literal["inst"] = "inst"
    prob: float | list[float] = pydantic.Field(
        ...,
        description=(
            "Draw probability in [0, 1]. A list is the per-CC-order "
            "vector (strict length == number of targets)."
        ),
    )

    @pydantic.field_validator("prob")
    @classmethod
    def _prob_in_unit_interval(cls, v):
        probs = v if isinstance(v, list) else [v]
        for p in probs:
            if not (0 <= p <= 1):
                raise ValueError(f"inst law prob must be within [0, 1], got {p}")
        return v

    def to_bkd_law(self, param):
        raise NotImplementedError(
            "ModeLawInst has no direct backend law dict: the engine "
            "builds the inst draw transition (branching + parked "
            "micro-state) itself."
        )


ModeLaw = typing.Annotated[
    typing.Union[ModeLawExp, ModeLawDelay, ModeLawInst],
    pydantic.Field(discriminator="cls"),
]

#: Module-level adapter — an annotated union is not instantiable, wire
#: dicts are parsed through this single entry point.
MODE_LAW_ADAPTER = pydantic.TypeAdapter(ModeLaw)


def parse_mode_law(value, what="law"):
    """Normalise a law input (spec instance or wire dict) to a spec.

    Raises a clear ``ValueError`` on unknown ``cls`` tags or malformed
    dicts instead of letting pydantic's raw error surface unlabelled.
    """
    if isinstance(value, (ModeLawExp, ModeLawDelay, ModeLawInst)):
        return value
    if isinstance(value, dict):
        try:
            return MODE_LAW_ADAPTER.validate_python(value)
        except pydantic.ValidationError as exc:
            raise ValueError(f"Invalid {what} specification: {exc}") from exc
    raise ValueError(
        f"Invalid {what} specification {value!r}: expected a ModeLaw "
        f"spec or a dict with a 'cls' tag in ('exp', 'delay', 'inst')."
    )
