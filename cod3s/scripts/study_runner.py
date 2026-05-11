"""High-level orchestrator for COD3S studies.

The :func:`run_study` function is the single reusable entry point that
glues together a :class:`SystemBuilder` and a validated
:class:`StudyYaml` to produce simulation results. Both the
``run-cod3s-study`` CLI and the ``cod3s-platform`` runner are thin
wrappers around it.

Pipeline:

1. ``system_builder.build()`` instantiates the populated system.
2. Failure modes from ``study.failure_modes`` are added via the
   ``cls`` registry (see :func:`register_fm_class`).
3. Events / indicators / targets are wired through the existing
   ``system.add_*`` helpers.
4. ``attribute_overrides`` (cod3s-platform extension) are applied
   *before* simulate().
5. Simulation runs.
6. Results are written to ``results_dir`` (CSV indicators + plots).

The orchestrator NEVER touches PyCATSHOO directly — it composes
existing system methods.
"""

from __future__ import annotations

import datetime
import logging
import os
from pathlib import Path
from typing import Any, Optional, Type, Union

import yaml

from cod3s.scripts._common import load_study_specs
from cod3s.scripts.builders import SystemBuilder
from cod3s.specs.study_yaml import (
    AttributeOverride,
    AttributeOverrides,
    EventSpec,
    FailureModeParamOverride,
    IndicatorSpec,
    ObjFMDelaySpec,
    ObjFMExpSpec,
    ObjFMGenericSpec,
    ResultsConfig,
    StudyYaml,
    TargetSpec,
)


# ---------------------------------------------------------------------------
# Failure-mode class registry.
# ---------------------------------------------------------------------------

#: Maps a string ``cls`` (as written in study.yaml) to the actual
#: ``ObjFM`` subclass to instantiate. Pre-populated with the known
#: classes; consumers can :func:`register_fm_class` any custom
#: subclass before calling :func:`run_study`.
_FM_REGISTRY: dict[str, Type[Any]] = {}


def _populate_default_fm_registry() -> None:
    """Register the built-in ObjFM* classes lazily.

    Lazy because importing ``cod3s.pycatshoo.component`` requires
    PyCATSHOO at import time, which we want to avoid for tests that
    only exercise the schema layer.
    """
    if _FM_REGISTRY:
        return
    from cod3s.pycatshoo.component import ObjFM, ObjFMDelay, ObjFMExp

    _FM_REGISTRY.update(
        {
            "ObjFM": ObjFM,
            "ObjFMExp": ObjFMExp,
            "ObjFMDelay": ObjFMDelay,
        }
    )


def register_fm_class(name: str, fm_cls: Type[Any]) -> None:
    """Register a custom ``ObjFM`` subclass under a string name.

    Call this before :func:`run_study` if your study.yaml uses an
    ``ObjFMGenericSpec`` with a custom ``cls`` (e.g. a Weibull law).
    The runner will then instantiate ``fm_cls(**spec_dict)`` for
    failure modes targeting that name.

    The check ``issubclass(fm_cls, ObjFM)`` is deferred until first
    use to keep ``cod3s.specs`` importable without PyCATSHOO.
    """
    _FM_REGISTRY[name] = fm_cls


def _resolve_fm_class(cls_name: str) -> Type[Any]:
    """Resolve a ``cls`` discriminator string to its registered class."""
    _populate_default_fm_registry()
    if cls_name not in _FM_REGISTRY:
        raise ValueError(
            f"Unknown failure mode class {cls_name!r}. "
            f"Known classes: {sorted(_FM_REGISTRY)}. "
            f"Use cod3s.scripts.study_runner.register_fm_class(name, cls) "
            f"to add a custom subclass."
        )
    return _FM_REGISTRY[cls_name]


# ---------------------------------------------------------------------------
# Apply layer — each helper takes a system + a list of validated specs.
# ---------------------------------------------------------------------------


def add_failure_modes(
    system: Any,
    specs: list[Any],
    *,
    logger: Any = None,
) -> int:
    """Instantiate failure modes from validated specs.

    Each spec is a Pydantic model (one of the FailureModeSpec union
    members). The runner calls ``cls(**spec.model_dump(exclude={...}))``
    so every constructor kwarg flows through unchanged.

    Returns:
        The count of successfully instantiated FMs.
    """
    added = 0
    for spec in specs:
        if not getattr(spec, "enabled", True):
            if logger:
                logger.info3(f"FM {spec.fm_name!r} skipped (enabled=False)")
            continue

        # ``cls`` is the discriminator, not a constructor kwarg.
        # ``enabled`` is a wire-format flag, not a constructor kwarg.
        kwargs = spec.model_dump(exclude={"cls", "enabled"})
        # ObjFMGenericSpec stores extra subclass kwargs directly via
        # ``extra="allow"``; they're already in model_dump output.
        fm_cls = _resolve_fm_class(spec.cls)
        try:
            fm_cls(**kwargs)
        except Exception as e:
            if logger:
                logger.error(
                    f"FM {spec.fm_name!r} (cls={spec.cls}) failed: {e}",
                    exc_info=True,
                )
            else:
                logging.getLogger(__name__).warning(
                    "FM %r (cls=%s) failed: %s", spec.fm_name, spec.cls, e
                )
            continue
        added += 1
        if logger:
            logger.info2(f"FM {spec.fm_name!r} ({spec.cls}) added")
    return added


def add_events(system: Any, specs: list[EventSpec], *, logger: Any = None) -> int:
    """Instantiate events from validated specs.

    Routes through the existing ``system.add_events`` API, which
    already handles ``enabled``, ``cls`` defaulting, and
    ``add_component`` dispatch.
    """
    payload = [spec.model_dump() for spec in specs]
    system.add_events(payload, logger=logger)
    return sum(1 for s in specs if s.enabled)


def add_indicators(system: Any, specs: list[IndicatorSpec], *, logger: Any = None) -> int:
    """Wire indicators via ``system.add_indicators``."""
    payload = [spec.model_dump() for spec in specs]
    system.add_indicators(payload, logger=logger)
    return sum(1 for s in specs if s.enabled)


def add_targets(system: Any, specs: list[TargetSpec], *, logger: Any = None) -> int:
    """Wire targets via ``system.add_targets``."""
    payload = [
        # Drop None fields so add_targets gets a positional-friendly dict
        {k: v for k, v in spec.model_dump().items() if v is not None}
        for spec in specs
    ]
    system.add_targets(payload, logger=logger)
    return sum(1 for s in specs if s.enabled)


def apply_attribute_overrides(
    system: Any,
    overrides: Optional[AttributeOverrides],
    *,
    logger: Any = None,
) -> None:
    """Apply ``component_attr`` and ``failure_mode_param`` overrides.

    ``component_attr`` overrides set runtime attributes on the system's
    components (typically flow var initial values, logic modes, …).
    ``failure_mode_param`` overrides replace lambda/mu arrays on
    already-built failure modes.

    Both branches are skipped silently when the corresponding list is
    empty, so this helper is safe to call unconditionally.
    """
    if overrides is None:
        return

    for ov in overrides.component_attr:
        _apply_component_attr_override(system, ov, logger=logger)

    for ov in overrides.failure_mode_param:
        _apply_failure_mode_param_override(system, ov, logger=logger)


def _apply_component_attr_override(
    system: Any,
    ov: AttributeOverride,
    *,
    logger: Any,
) -> None:
    comp = system.comp.get(ov.component) if hasattr(system, "comp") else None
    if comp is None:
        if logger:
            logger.warning(
                f"override: component {ov.component!r} not found, skipping"
            )
        return
    try:
        if hasattr(comp, "set_attribute"):
            comp.set_attribute(ov.attribute, ov.value)
        else:
            setattr(comp, ov.attribute, ov.value)
        if logger:
            logger.info3(
                f"override: {ov.component}.{ov.attribute} = {ov.value!r}"
                + (f" (source={ov.source})" if ov.source else "")
            )
    except Exception as e:
        if logger:
            logger.error(
                f"override: {ov.component}.{ov.attribute} failed: {e}"
            )


def _apply_failure_mode_param_override(
    system: Any,
    ov: FailureModeParamOverride,
    *,
    logger: Any,
) -> None:
    fm = system.comp.get(ov.fm_name) if hasattr(system, "comp") else None
    if fm is None:
        if logger:
            logger.warning(
                f"override: failure mode {ov.fm_name!r} not found, skipping"
            )
        return
    try:
        setattr(fm, ov.field, ov.value)
        if logger:
            logger.info3(
                f"override: {ov.fm_name}.{ov.field} = {ov.value!r}"
            )
    except Exception as e:
        if logger:
            logger.error(
                f"override: {ov.fm_name}.{ov.field} failed: {e}"
            )


# ---------------------------------------------------------------------------
# Results writer.
# ---------------------------------------------------------------------------


def write_results(
    system: Any,
    results: Optional[ResultsConfig],
    results_dir: Path,
    *,
    logger: Any = None,
) -> None:
    """Write indicators CSV + plots according to ``results`` config.

    No-op when ``results`` is None or empty.
    """
    if results is None:
        return

    for ind_spec in results.indicators:
        if "csv" not in [fmt.lower() for fmt in ind_spec.output]:
            continue
        try:
            df = system.indic_to_frame(
                comp_pattern=ind_spec.comp_pattern,
                attr_pattern=ind_spec.attr_pattern,
            )
            csv_path = results_dir / f"{ind_spec.id}.csv"
            df.to_csv(csv_path, index=False)
            if logger:
                logger.info3(f"Indicators CSV saved to: {csv_path}")
        except Exception as e:
            if logger:
                logger.error(f"Failed to write indicators CSV {ind_spec.id!r}: {e}")

    for plot_spec in results.plot_indicators:
        try:
            plot_kwargs = plot_spec.model_dump(exclude={"id", "output", "write_options"})
            fig = system.indic_px_line(**plot_kwargs)
            for fmt in plot_spec.output:
                fmt_lower = fmt.lower()
                if fmt_lower == "html":
                    out = results_dir / f"{plot_spec.id}.html"
                    fig.write_html(out)
                    if logger:
                        logger.info3(f"Plot saved to: {out}")
                elif fmt_lower == "png":
                    out = results_dir / f"{plot_spec.id}.png"
                    fig.write_image(out, **plot_spec.write_options)
                    if logger:
                        logger.info3(f"Plot saved to: {out}")
        except Exception as e:
            if logger:
                logger.error(f"Failed to render plot {plot_spec.id!r}: {e}")


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------


def _resolve_study(study: Union[StudyYaml, Path, str, dict]) -> StudyYaml:
    """Coerce the ``study`` argument into a validated :class:`StudyYaml`.

    Accepts:
    - a :class:`StudyYaml` instance (returned as-is)
    - a ``dict`` (validated)
    - a ``Path`` / ``str`` to a YAML file (loaded then validated)
    """
    if isinstance(study, StudyYaml):
        return study
    if isinstance(study, dict):
        return StudyYaml.model_validate(study)
    path = Path(study)
    raw = load_study_specs(path)
    if not raw:
        raise FileNotFoundError(f"Study YAML not found or empty: {path}")
    return StudyYaml.model_validate(raw)


def run_study(
    *,
    system_builder: SystemBuilder,
    study: Union[StudyYaml, Path, str, dict],
    results_dir: Path | str,
    logger: Any = None,
) -> Any:
    """Run a COD3S study end-to-end.

    Args:
        system_builder: Object satisfying the :class:`SystemBuilder`
            Protocol (must expose ``build(logger=None)``).
        study: A :class:`StudyYaml` instance, a dict to validate, or
            a path to a study.yaml file.
        results_dir: Where to write CSV indicators + plots. Created
            if missing.
        logger: Optional COD3SLogger or similar (must support
            ``info1``/``info2``/``info3``/``warning``/``error``).

    Returns:
        The populated ``PycSystem`` post-simulation, for callers that
        want to inspect it further (eg. analyser inspection).

    Side effects:
        Writes files under ``results_dir`` according to
        ``study.results``.
    """
    study_obj = _resolve_study(study)
    results_path = Path(results_dir)
    results_path.mkdir(parents=True, exist_ok=True)

    if logger:
        logger.info2(f"Using {results_path} to store results")

    # Step 1: build system
    if logger:
        logger.info1(f"Building system via {type(system_builder).__name__}")
    system = system_builder.build(logger=logger)

    # Step 2: failure modes
    if logger:
        logger.info1("Add failure modes")
    add_failure_modes(system, study_obj.failure_modes, logger=logger)

    # Step 3: events
    if logger:
        logger.info1("Add events")
    add_events(system, study_obj.events, logger=logger)

    # Step 4: indicators
    if logger:
        logger.info1("Add indicators")
    add_indicators(system, study_obj.indicators, logger=logger)

    # Step 5: targets
    if logger:
        logger.info1("Add targets")
    add_targets(system, study_obj.targets, logger=logger)

    # Step 6: attribute overrides (cod3s-platform extension)
    if study_obj.attribute_overrides is not None:
        if logger:
            logger.info1("Apply attribute overrides")
        apply_attribute_overrides(system, study_obj.attribute_overrides, logger=logger)

    # Step 7: monitor + simulate
    # ``monitorTransition`` is required to expose transitions in the
    # sequences XML output. We restrict monitoring to ``.occ``
    # transitions (failure occurrences, including CCF variants like
    # ``.occ__cc_3``) and drop the matching ``.rep`` /
    # ``.step_to_repli`` / state-change transitions that PyCATSHOO
    # records by default.
    #
    # Pattern : ``#.*\.occ.*`` — the ``#`` prefix asks PyCATSHOO for a
    # regex match, ``.*\.occ.*`` captures any transition whose name
    # contains the literal ``.occ`` substring. We cannot anchor on
    # ``.occ$`` because ObjFMExp emits CCF variants as ``.occ__cc_N``
    # (one per element of the common-cause group), and a strict
    # end-anchor would silently drop them — that was the bug that
    # surfaced when only PC_DAME (which has no CCF) showed up in the
    # recorded sequences.
    #
    # Rationale of the filter : a Monte-Carlo trajectory that reaches
    # a target typically cycles through ``occ → rep → occ`` many
    # times before the predicate fires. Including ``.rep`` in the
    # recorded sequence makes every trajectory unique by timing of
    # those reversible events, which destroys the equivalence-class
    # grouping downstream (87 % singletons observed on the RATP DIL
    # FMDS instance with the wildcard monitor). Filtering at the
    # source costs nothing — PyCATSHOO simply doesn't store the
    # excluded transitions — and gives the downstream tools a clean
    # signal of *failure occurrences* in causal order.
    if hasattr(system, "monitorTransition"):
        system.monitorTransition("#.*\\.occ.*")

    # When at least one target is wired, ask PyCATSHOO to dump the
    # sequences (state trajectories that reached a target) as an XML
    # file alongside the run artefacts. Without this call the sequences
    # live only in memory and are lost when ``simulate()`` returns —
    # every downstream consumer (``cod3s-platform``'s
    # ``RunSequencesTable``, the user-supplied post-processor) then
    # sees an empty list. Skipped when no targets are declared because
    # the resulting XML is meaningless for a pure-indicators sub-run.
    #
    # The PyCATSHOO API splits this in two : ``setResultFileName(path,
    # append)`` sets the output path, ``setBinSeqFile(bool)`` toggles
    # binary vs textual XML. We keep the textual form because that's
    # what ``cod3s-platform``'s sequences parser consumes.
    has_targets = bool(getattr(study_obj, "targets", None))
    if has_targets and hasattr(system, "setResultFileName"):
        seq_path = results_path / "sequences.xml"
        system.setResultFileName(str(seq_path), False)
        if hasattr(system, "setBinSeqFile"):
            system.setBinSeqFile(False)
        if logger:
            logger.info2(f"Sequences XML will be written to: {seq_path}")

    if logger:
        logger.info1(
            f"Starting simulation [nb_runs={study_obj.simulation.nb_runs}]"
        )
    start = datetime.datetime.now()
    # Normalise the schedule for ``PycMCSimulationParam``: that runtime
    # accepts plain floats (single instant) or ``InstantLinearRange`` dicts
    # ``{start, end, nvalues}`` — but NOT our ``{instant: <float>}`` form,
    # which is wire-format only. Project ``ScheduleEntry(instant=t)`` back
    # to the float ``t`` here so the bridge stays one-line.
    sim_payload = study_obj.simulation.model_dump(exclude_none=True)
    if isinstance(sim_payload.get("schedule"), list):
        sim_payload["schedule"] = [
            entry["instant"] if isinstance(entry, dict) and set(entry.keys()) == {"instant"} else entry
            for entry in sim_payload["schedule"]
        ]
    system.simulate(sim_payload)
    duration = datetime.datetime.now() - start
    if logger:
        logger.info2(f"Simulation completed in: {duration}")

    # Step 8: dump PyCATSHOO parameters file (legacy artifact —
    # consumers expect it next to results)
    if hasattr(system, "dumpParameters"):
        system.dumpParameters(str(results_path / "pyc_param.xml"), False)

    # Step 9: results
    if logger:
        logger.info2("Storing results")
    write_results(system, study_obj.results, results_path, logger=logger)

    return system


def run_study_from_yamls(
    *,
    model_path: Path | str,
    study_path: Path | str,
    results_dir: Path | str,
    namespace: Optional[dict] = None,
    logger: Any = None,
) -> Any:
    """Convenience wrapper: build with :class:`YamlModelBuilder` then
    :func:`run_study`. This is what the CLI uses by default.
    """
    from cod3s.scripts.builders import YamlModelBuilder

    builder = YamlModelBuilder(model_path, namespace=namespace)
    return run_study(
        system_builder=builder,
        study=Path(study_path),
        results_dir=results_dir,
        logger=logger,
    )


__all__ = [
    "register_fm_class",
    "add_failure_modes",
    "add_events",
    "add_indicators",
    "add_targets",
    "apply_attribute_overrides",
    "write_results",
    "run_study",
    "run_study_from_yamls",
]
