"""Textual modal screens for the ``cod3s-seq`` TUI.

The modals are intentionally minimal: each one collects the parameters
of *one* operation, validates them with Pydantic, and dismisses with
either a fully-formed object (a :class:`PipelineStep` subclass, a
:class:`Path`, or a tuple) or ``None`` on cancel.

Layout convention (copied from ``cod3s-isimu``):

* Centered modal, fixed width, primary-bordered ``Vertical``.
* Title row on top, body (``Input`` / ``Static``) in the middle,
  Cancel + OK buttons at the bottom right.
* ``Enter`` in the main input is equivalent to clicking OK.

Modals exposed:

* :class:`AddStepModal` — pick one of the six ops; dismisses with the
  op string or ``None``.
* :class:`config_modal_for(op) -> type[ModalScreen] | None` — factory
  returning the right configuration modal for a step that has params.
  Returns ``None`` for ``group_sequences`` and
  ``compute_minimal_sequences`` (no params → no modal).
* :class:`SavePipelineModal` / :class:`LoadPipelineModal` — file path.
* :class:`ExportModal` — radio of format + path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional, Type

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    RadioButton,
    RadioSet,
    SelectionList,
    Static,
)

from cod3s.pycatshoo.seq_tui.pipeline import (
    FilterObjFMCyclesStep,
    PipelineStep,
    RenameEventsStep,
    RmEventsByObjStep,
    RmEventsOrderedPatternStep,
)

ExportFormat = Literal["json-cod3s", "csv", "markdown"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_MODAL_CSS = """
ModalScreen {
    align: center middle;
}
ModalScreen > Vertical {
    width: 70;
    height: auto;
    border: round $primary;
    padding: 1 2;
    background: $surface;
}
ModalScreen Horizontal {
    height: auto;
    align-horizontal: right;
    margin-top: 1;
}
ModalScreen Button {
    margin-left: 1;
}
ModalScreen .modal-title {
    text-style: bold;
    padding-bottom: 1;
}
ModalScreen .modal-help {
    color: $text-muted;
}
"""


def _parse_csv_list(raw: str) -> list[str]:
    """Parse a comma-separated value into a stripped list of strings.

    Empty input → empty list. ``"a, b,c"`` → ``["a", "b", "c"]``.
    """
    return [s.strip() for s in raw.split(",") if s.strip()]


# ---------------------------------------------------------------------------
# AddStepModal — pick the op
# ---------------------------------------------------------------------------


_OP_CHOICES: list[tuple[str, str]] = [
    ("group_sequences", "Group identical sequences"),
    ("filter_objfm_cycles", "Filter ObjFM cycles (occ/rep pairs)"),
    ("compute_minimal_sequences", "Compute minimal sequences"),
    ("rm_events_by_obj", "Remove events by obj name"),
    ("rm_events_ordered_pattern", "Remove ordered event patterns"),
    ("rename_events", "Rename events (regex substitution)"),
]


class AddStepModal(ModalScreen[Optional[str]]):
    """Pick a pipeline operation; dismisses with the op id or ``None``."""

    DEFAULT_CSS = _MODAL_CSS

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Add pipeline step", classes="modal-title")
            yield Static("Choose an operation:", classes="modal-help")
            with RadioSet(id="op-radio"):
                for i, (op, label) in enumerate(_OP_CHOICES):
                    yield RadioButton(
                        f"{label}  ({op})",
                        value=(i == 0),
                        id=f"op-{op}",
                    )
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button("Add", variant="primary", id="ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "ok":
            self._submit()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        # Allow double-click activation via the radio set itself.
        pass

    def _submit(self) -> None:
        radio = self.query_one("#op-radio", RadioSet)
        if radio.pressed_button is None:
            self.dismiss(None)
            return
        # The button id is "op-<opname>"
        rid = radio.pressed_button.id or ""
        op = rid.removeprefix("op-")
        self.dismiss(op or None)


# ---------------------------------------------------------------------------
# Configuration modals — one per step type that takes params
# ---------------------------------------------------------------------------


class _ConfigStepModalBase(ModalScreen[Optional[PipelineStep]]):
    """Shared scaffolding for step-config modals.

    Subclasses must implement :meth:`_build_step()` returning the
    concrete :class:`PipelineStep` or raising :class:`ValidationError`
    / :class:`ValueError` for the modal to surface the error.
    """

    DEFAULT_CSS = _MODAL_CSS
    title_text: str = "Configure step"
    help_text: str = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.title_text, classes="modal-title")
            if self.help_text:
                yield Static(self.help_text, classes="modal-help")
            yield from self._compose_fields()
            yield Static("", id="error-msg", classes="modal-help")
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button("Add", variant="primary", id="ok")

    def _compose_fields(self) -> ComposeResult:
        """Override in subclass to yield input widgets."""
        return
        yield  # pragma: no cover — make this a generator

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "ok":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        try:
            step = self._build_step()
        except (ValidationError, ValueError) as exc:
            self.query_one("#error-msg", Static).update(f"[red]error: {exc}[/red]")
            return
        self.dismiss(step)

    def _build_step(self) -> PipelineStep:  # pragma: no cover — abstract
        raise NotImplementedError


class ConfigFilterObjFMCyclesModal(_ConfigStepModalBase):
    """Configure a ``filter_objfm_cycles`` step.

    UX adapts to the loaded state:

    * **Live mode** — when ``available_internal`` and/or
      ``available_external`` are non-empty (passed in by the App from
      ``SeqTuiState`` when ``cod3s-seq --factory`` was used), the
      modal renders a :class:`SelectionList` per bucket with every
      ObjFM pre-checked. Zero typos, no need to remember the exact
      component names.
    * **Post-mortem mode** — when both lists are empty, the modal
      falls back to two free-form text inputs (the historical
      behaviour). The user types ObjFM names comma-separated.

    The ``failure_state`` and ``repair_state`` inputs are always
    rendered (override the defaults when the model uses custom
    ``trans_name_prefix`` values).
    """

    title_text = "filter_objfm_cycles"
    help_text = (
        "ObjFM names to filter. Failure/repair state names are usually "
        "'occ' / 'rep'."
    )

    def __init__(
        self,
        *,
        available_internal: tuple[str, ...] = (),
        available_external: tuple[str, ...] = (),
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._available_internal = tuple(available_internal)
        self._available_external = tuple(available_external)

    @property
    def live_mode(self) -> bool:
        """``True`` iff at least one ObjFM bucket was pre-discovered."""
        return bool(self._available_internal or self._available_external)

    def _compose_fields(self) -> ComposeResult:
        if self.live_mode:
            yield Static(
                f"[i](live mode — {len(self._available_internal)} internal, "
                f"{len(self._available_external)} external discovered)[/i]",
                classes="modal-help",
            )
            if self._available_internal:
                yield Label("ObjFM internal (check to filter):")
                yield SelectionList[str](
                    *[(name, name, True) for name in self._available_internal],
                    id="int-sel",
                )
            if self._available_external:
                yield Label("ObjFM external (check to filter):")
                yield SelectionList[str](
                    *[(name, name, True) for name in self._available_external],
                    id="ext-sel",
                )
        else:
            yield Label("ObjFM internal (comma-separated):")
            yield Input(placeholder="pump_X__def_pump, valve_Y__def_valve", id="int")
            yield Label("ObjFM external (comma-separated):")
            yield Input(placeholder="(empty)", id="ext")
        yield Label("Failure state:")
        yield Input(value="occ", id="fs")
        yield Label("Repair state:")
        yield Input(value="rep", id="rs")

    def _build_step(self) -> PipelineStep:
        if self.live_mode:
            internal: list[str] = []
            external: list[str] = []
            if self._available_internal:
                internal = list(self.query_one("#int-sel", SelectionList).selected)
            if self._available_external:
                external = list(self.query_one("#ext-sel", SelectionList).selected)
        else:
            internal = _parse_csv_list(self.query_one("#int", Input).value)
            external = _parse_csv_list(self.query_one("#ext", Input).value)
        return FilterObjFMCyclesStep(
            objfm_internal=internal,
            objfm_external=external,
            failure_state=self.query_one("#fs", Input).value.strip() or "occ",
            repair_state=self.query_one("#rs", Input).value.strip() or "rep",
        )


class ConfigRmEventsByObjModal(_ConfigStepModalBase):
    title_text = "rm_events_by_obj"
    help_text = "Drop all events whose ``obj`` field matches the given name."

    def _compose_fields(self) -> ComposeResult:
        yield Label("Object name:")
        yield Input(placeholder="noise_component", id="obj_name")

    def _build_step(self) -> PipelineStep:
        return RmEventsByObjStep(
            obj_name=self.query_one("#obj_name", Input).value.strip()
        )


class ConfigRmEventsOrderedPatternModal(_ConfigStepModalBase):
    title_text = "rm_events_ordered_pattern"
    help_text = (
        "Both patterns are Python regexes. Events matching pat1 are dropped "
        "when followed (any time later) by an event matching pat2."
    )

    def _compose_fields(self) -> ComposeResult:
        yield Label("Pattern 1 (regex, on event ``name``):")
        yield Input(placeholder=r"^(.+)\.start$", id="pat1")
        yield Label("Pattern 2 (regex, on event ``name``):")
        yield Input(placeholder=r"^\1\.stop$", id="pat2")

    def _build_step(self) -> PipelineStep:
        return RmEventsOrderedPatternStep(
            name_pat1=self.query_one("#pat1", Input).value,
            name_pat2=self.query_one("#pat2", Input).value,
        )


class ConfigRenameEventsModal(_ConfigStepModalBase):
    title_text = "rename_events"
    help_text = (
        "Apply a regex substitution on one of the SeqEvent fields. "
        "``attr`` ∈ {obj, attr, type}."
    )

    def _compose_fields(self) -> ComposeResult:
        yield Label("Attribute (obj | attr | type):")
        yield Input(value="obj", id="attr")
        yield Label("Source pattern (regex):")
        yield Input(placeholder=r"^old_(.+)$", id="src")
        yield Label("Target pattern (re.sub replacement):")
        yield Input(placeholder=r"new_\1", id="tgt")

    def _build_step(self) -> PipelineStep:
        return RenameEventsStep(
            attr=self.query_one("#attr", Input).value.strip(),  # type: ignore[arg-type]
            pat_source=self.query_one("#src", Input).value,
            pat_target=self.query_one("#tgt", Input).value,
        )


_CONFIG_MODAL_FOR_OP: dict[str, Type[_ConfigStepModalBase]] = {
    "filter_objfm_cycles": ConfigFilterObjFMCyclesModal,
    "rm_events_by_obj": ConfigRmEventsByObjModal,
    "rm_events_ordered_pattern": ConfigRmEventsOrderedPatternModal,
    "rename_events": ConfigRenameEventsModal,
}


def config_modal_for(op: str) -> Optional[Type[_ConfigStepModalBase]]:
    """Return the :class:`ModalScreen` subclass for ``op``, or ``None``.

    Steps without parameters (``group_sequences``,
    ``compute_minimal_sequences``) return ``None``; the app applies
    them directly.
    """
    return _CONFIG_MODAL_FOR_OP.get(op)


# ---------------------------------------------------------------------------
# Save / Load pipeline modals
# ---------------------------------------------------------------------------


class _PathModalBase(ModalScreen[Optional[Path]]):
    """Common scaffolding for ``Save`` / ``Load`` path modals."""

    DEFAULT_CSS = _MODAL_CSS
    title_text: str = "Path"
    help_text: str = ""
    submit_label: str = "OK"
    placeholder: str = "/tmp/pipeline.yaml"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.title_text, classes="modal-title")
            if self.help_text:
                yield Static(self.help_text, classes="modal-help")
            yield Input(placeholder=self.placeholder, id="path")
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button(self.submit_label, variant="primary", id="ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self._submit()
        elif event.button.id == "cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "path":
            self._submit()

    def _submit(self) -> None:
        value = self.query_one("#path", Input).value.strip()
        self.dismiss(Path(value).expanduser() if value else None)


class SavePipelineModal(_PathModalBase):
    title_text = "Save pipeline"
    help_text = "Destination YAML file (overwrites if exists)."
    submit_label = "Save"
    placeholder = "/tmp/cod3s-seq-pipeline.yaml"


class LoadPipelineModal(_PathModalBase):
    title_text = "Load pipeline"
    help_text = (
        "YAML file to load. The current pipeline is reset, then "
        "every loaded step is applied in order."
    )
    submit_label = "Load"
    placeholder = "/tmp/cod3s-seq-pipeline.yaml"


# ---------------------------------------------------------------------------
# Export modal
# ---------------------------------------------------------------------------


class ExportModal(ModalScreen[Optional[tuple[ExportFormat, Path]]]):
    """Pick a format and destination path."""

    DEFAULT_CSS = _MODAL_CSS

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Export current analyser", classes="modal-title")
            yield Static("Format:", classes="modal-help")
            with RadioSet(id="fmt"):
                yield RadioButton("JSON cod3s", value=True, id="fmt-json-cod3s")
                yield RadioButton("CSV (one row per event)", id="fmt-csv")
                yield RadioButton("Markdown report", id="fmt-markdown")
            yield Static("Destination path:", classes="modal-help")
            yield Input(placeholder="/tmp/cod3s-seq-export.json", id="path")
            with Horizontal():
                yield Button("Cancel", id="cancel")
                yield Button("Export", variant="primary", id="ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self._submit()
        elif event.button.id == "cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "path":
            self._submit()

    def _submit(self) -> None:
        radio = self.query_one("#fmt", RadioSet)
        if radio.pressed_button is None:
            self.dismiss(None)
            return
        rid = radio.pressed_button.id or ""
        fmt_id = rid.removeprefix("fmt-")
        path_str = self.query_one("#path", Input).value.strip()
        if not path_str or fmt_id not in ("json-cod3s", "csv", "markdown"):
            self.dismiss(None)
            return
        # mypy: cast to ExportFormat
        fmt: ExportFormat = fmt_id  # type: ignore[assignment]
        self.dismiss((fmt, Path(path_str).expanduser()))


__all__ = [
    "AddStepModal",
    "ConfigFilterObjFMCyclesModal",
    "ConfigRmEventsByObjModal",
    "ConfigRmEventsOrderedPatternModal",
    "ConfigRenameEventsModal",
    "ExportFormat",
    "ExportModal",
    "LoadPipelineModal",
    "SavePipelineModal",
    "config_modal_for",
]


# Keep imports used by the type-only typing alias above from being
# flagged as unused.
_Any = Any
