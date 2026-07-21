"""Pipeline of sequence-analysis steps for ``cod3s-seq``.

A :class:`Pipeline` is an ordered list of :class:`PipelineStep`
instances. Each step is a Pydantic model that knows how to apply
itself to a :class:`SequenceAnalyser` and how to summarise itself for
display. The pipeline is serialisable to / from YAML so the user can
save a configuration and replay it (interactively in the TUI or
non-interactively via ``cod3s-seq --pipeline pipe.yaml``).

The six exposed operations map 1:1 to the public
:class:`SequenceAnalyser` methods:

* ``group_sequences`` → :meth:`SequenceAnalyser.group_sequences`
* ``filter_objfm_cycles`` → :meth:`SequenceAnalyser.filter_objfm_cycles`
* ``compute_minimal_sequences`` → :meth:`SequenceAnalyser.compute_minimal_sequences`
* ``rm_events_by_obj`` → :meth:`SequenceAnalyser.rm_events_by_obj`
* ``rm_events_ordered_pattern`` → :meth:`SequenceAnalyser.rm_events_ordered_pattern`
* ``rename_events`` → :meth:`SequenceAnalyser.rename_events`

Each step type carries its own parameters as model fields (validated
by Pydantic). The ``op`` field acts as the discriminator for
deserialisation; YAML round-trip is lossless.
"""

from __future__ import annotations

import typing
from pathlib import Path

import pydantic
import yaml

PIPELINE_SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Step base + concrete subclasses
# ---------------------------------------------------------------------------


class _PipelineStepBase(pydantic.BaseModel):
    """Abstract base for all pipeline steps.

    Subclasses MUST declare an ``op`` field as a ``Literal``
    discriminator. They MUST implement :meth:`apply` and
    :meth:`summary`.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    def apply(self, analyser):  # pragma: no cover — abstract
        """Apply the step on the analyser in-place. Returns the analyser."""
        raise NotImplementedError

    def summary(self) -> str:  # pragma: no cover — abstract
        """One-line summary for display in the pipeline panel."""
        raise NotImplementedError


class GroupSequencesStep(_PipelineStepBase):
    op: typing.Literal["group_sequences"] = "group_sequences"

    def apply(self, analyser):
        analyser.group_sequences(inplace=True)
        return analyser

    def summary(self) -> str:
        return "group_sequences"


class FilterObjFMCyclesStep(_PipelineStepBase):
    op: typing.Literal["filter_objfm_cycles"] = "filter_objfm_cycles"
    objfm_internal: list[str] = pydantic.Field(default_factory=list)
    objfm_external: list[str] = pydantic.Field(default_factory=list)
    failure_state: str = "occ"
    repair_state: str = "rep"

    def apply(self, analyser):
        # Auto-discovery requires an attached PycSystem which is never
        # available on the post-mortem path. Pass the explicit lists
        # (empty list = no-op on that side) plus the state names.
        analyser.filter_objfm_cycles(
            objfm_internal=list(self.objfm_internal),
            objfm_external=list(self.objfm_external),
            failure_state=self.failure_state,
            repair_state=self.repair_state,
            inplace=True,
        )
        return analyser

    def summary(self) -> str:
        parts = []
        if self.objfm_internal:
            parts.append(f"int={self.objfm_internal}")
        if self.objfm_external:
            parts.append(f"ext={self.objfm_external}")
        if self.failure_state != "occ" or self.repair_state != "rep":
            parts.append(f"{self.failure_state}/{self.repair_state}")
        suffix = f"({', '.join(parts)})" if parts else "()"
        return f"filter_objfm_cycles{suffix}"


class ComputeMinimalSequencesStep(_PipelineStepBase):
    op: typing.Literal["compute_minimal_sequences"] = "compute_minimal_sequences"

    def apply(self, analyser):
        analyser.compute_minimal_sequences(inplace=True)
        return analyser

    def summary(self) -> str:
        return "compute_minimal_sequences"


class RmEventsByObjStep(_PipelineStepBase):
    op: typing.Literal["rm_events_by_obj"] = "rm_events_by_obj"
    obj_name: str

    def apply(self, analyser):
        analyser.rm_events_by_obj(self.obj_name, inplace=True)
        return analyser

    def summary(self) -> str:
        return f"rm_events_by_obj({self.obj_name!r})"


class RmEventsOrderedPatternStep(_PipelineStepBase):
    op: typing.Literal["rm_events_ordered_pattern"] = "rm_events_ordered_pattern"
    name_pat1: str
    name_pat2: str

    def apply(self, analyser):
        analyser.rm_events_ordered_pattern(
            name_pat1=self.name_pat1,
            name_pat2=self.name_pat2,
            inplace=True,
        )
        return analyser

    def summary(self) -> str:
        return f"rm_events_ordered_pattern({self.name_pat1!r}, {self.name_pat2!r})"


class RenameEventsStep(_PipelineStepBase):
    op: typing.Literal["rename_events"] = "rename_events"
    attr: typing.Literal["obj", "attr", "type"]
    pat_source: str
    pat_target: str

    def apply(self, analyser):
        analyser.rename_events(
            attr=self.attr,
            pat_source=self.pat_source,
            pat_target=self.pat_target,
            inplace=True,
        )
        return analyser

    def summary(self) -> str:
        return (
            f"rename_events(attr={self.attr!r}, "
            f"{self.pat_source!r} → {self.pat_target!r})"
        )


# Discriminated union — Pydantic picks the right subclass at validation
# time based on the ``op`` field.
PipelineStep = typing.Annotated[
    typing.Union[
        GroupSequencesStep,
        FilterObjFMCyclesStep,
        ComputeMinimalSequencesStep,
        RmEventsByObjStep,
        RmEventsOrderedPatternStep,
        RenameEventsStep,
    ],
    pydantic.Field(discriminator="op"),
]


# Public mapping ``op string → step class``, useful for the AddStepModal.
STEP_CLASSES: dict[str, type[_PipelineStepBase]] = {
    "group_sequences": GroupSequencesStep,
    "filter_objfm_cycles": FilterObjFMCyclesStep,
    "compute_minimal_sequences": ComputeMinimalSequencesStep,
    "rm_events_by_obj": RmEventsByObjStep,
    "rm_events_ordered_pattern": RmEventsOrderedPatternStep,
    "rename_events": RenameEventsStep,
}


# ---------------------------------------------------------------------------
# Pipeline (the ordered list)
# ---------------------------------------------------------------------------


class Pipeline(pydantic.BaseModel):
    """An ordered list of :class:`PipelineStep`.

    ``apply`` runs the steps in order on the given analyser (in-place,
    chaining). ``save_yaml`` / ``load_yaml`` round-trip the pipeline
    to disk via PyYAML safe_dump / safe_load.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    version: str = PIPELINE_SCHEMA_VERSION
    steps: list[PipelineStep] = pydantic.Field(default_factory=list)

    def append(self, step) -> "Pipeline":
        """Return a new :class:`Pipeline` with ``step`` appended.

        The current instance is untouched — convenient for the
        immutable ``SeqTuiState`` flow where each step application
        produces a new state.
        """
        return Pipeline(version=self.version, steps=[*self.steps, step])

    def apply(self, analyser, *, progress=False):
        """Apply all steps in order, in-place.

        Args:
            analyser: A :class:`SequenceAnalyser` instance. Modified in
                place (each step calls its corresponding method with
                ``inplace=True``).
            progress: Forwarded to the underlying methods that accept
                a ``progress`` parameter — currently a no-op for steps
                that don't take one.

        Returns:
            The same analyser, mutated.
        """
        for step in self.steps:
            step.apply(analyser)
        return analyser

    def save_yaml(self, path) -> None:
        """Serialise the pipeline to a YAML file.

        Format::

            version: "1.0.0"
            steps:
              - op: group_sequences
              - op: filter_objfm_cycles
                objfm_internal: [pump_X__def_pump]
                ...

        The ``op`` discriminator is preserved so :meth:`load_yaml` can
        reconstruct the concrete step subclasses.
        """
        payload = self.model_dump(mode="python")
        Path(path).write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    @classmethod
    def load_yaml(cls, path) -> "Pipeline":
        """Load a pipeline from a YAML file.

        Pydantic validates the discriminated union, so a step with an
        unknown ``op`` or missing/extra parameters raises a clear
        :class:`pydantic.ValidationError`.
        """
        text = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(text) or {}
        return cls.model_validate(data)
