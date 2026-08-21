"""Modal screens used by ``cod3s-isimu``.

Four modals at the moment:

* :class:`ExportModal` — collects a destination path (without extension) and
  returns a :class:`pathlib.Path`. The App is responsible for writing the
  CSV and JSON files via :func:`export_csv` / :func:`export_json`.
* :class:`ReplanModal` — collects a planned date for an already-identified
  transition. The transition is chosen by the caller (``p`` is bound to the
  ``FireablePanel`` and uses the cursor row), so the modal asks **only**
  for the date and returns it as ``Optional[float]``.
* :class:`ObservationStepModal` — collects the simulated time one playback
  tick advances.
* :class:`IntegrationModal` — collects the two PDMP knobs, the maximum
  integration step and the precision of the crossing search.

The last two are separate on purpose, and the distinction is the one thing a
reader gets wrong here. The observation step is how often the model is LOOKED
at; the integration step is how finely it is COMPUTED between two looks. They
are independent: a coarse observation of a finely integrated run is exact but
sparsely sampled, while a fine observation of a coarsely integrated one is
sampled often and wrong. Merging them into a single "time step" field would
make one of the two silently follow the other.

Both modals dismiss with ``None`` when the user cancels so the App can
short-circuit the action.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class ExportModal(ModalScreen[Optional[Path]]):
    """Ask for an export path (no extension) and dismiss with that ``Path``."""

    DEFAULT_CSS = """
    ExportModal {
        align: center middle;
    }
    ExportModal > Vertical {
        width: 60;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }
    ExportModal Horizontal {
        height: auto;
        align-horizontal: right;
        margin-top: 1;
    }
    ExportModal Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Export timeline", classes="modal-title")
            yield Static(
                "Path (without extension; .csv and .json will be written):",
                classes="modal-help",
            )
            yield Input(
                placeholder="/tmp/cod3s-isimu-history",
                id="export-path",
            )
            with Horizontal():
                yield Button("Cancel", id="export-cancel")
                yield Button("Export", variant="primary", id="export-ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-ok":
            value = self.query_one("#export-path", Input).value.strip()
            self.dismiss(Path(value) if value else None)
        elif event.button.id == "export-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "export-path":
            value = event.input.value.strip()
            self.dismiss(Path(value) if value else None)


class ReplanModal(ModalScreen[Optional[float]]):
    """Ask for the new planned date of a transition the caller already knows.

    The caller (typically :class:`FireablePanel.action_replan_cursor`) passes
    a ``title`` string (typically ``"Replan transition {comp}.{trans_name}"``)
    so the modal can display *which* transition is being replanned without
    asking the user to re-enter its index.
    """

    DEFAULT_CSS = """
    ReplanModal {
        align: center middle;
    }
    ReplanModal > Vertical {
        width: 60;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }
    ReplanModal Horizontal {
        height: auto;
        align-horizontal: right;
        margin-top: 1;
    }
    ReplanModal Button {
        margin-left: 1;
    }
    """

    def __init__(
        self,
        title: str = "Replan transition",
        default_date: float = 0.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._default_date = default_date

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._title, classes="modal-title")
            yield Static(
                "Set the planned firing date.",
                classes="modal-help",
            )
            yield Input(
                placeholder="planned date (float)",
                value=f"{self._default_date}",
                id="replan-date",
            )
            with Horizontal():
                yield Button("Cancel", id="replan-cancel")
                yield Button("Re-plan", variant="primary", id="replan-ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "replan-ok":
            self._submit()
        elif event.button.id == "replan-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "replan-date":
            self._submit()

    def _submit(self) -> None:
        try:
            date = float(self.query_one("#replan-date", Input).value)
        except (TypeError, ValueError):
            self.dismiss(None)
            return
        self.dismiss(date)


class ObservationStepModal(ModalScreen[Optional[float]]):
    """Ask for the simulated time one playback tick advances.

    Not the integration step: see :class:`IntegrationModal`. This one only
    decides how often the model is looked at, so lowering it costs one extra
    evaluation per look and nothing else. It is also what brackets a watched
    threshold, whose crossing ``isimu_step_to`` cannot land on: the crossing is
    only known to have happened between two observations, so a finer step
    narrows the bracket.
    """

    DEFAULT_CSS = """
    ObservationStepModal {
        align: center middle;
    }
    ObservationStepModal > Vertical {
        width: 60;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }
    ObservationStepModal Horizontal {
        height: auto;
        align-horizontal: right;
        margin-top: 1;
    }
    ObservationStepModal Button {
        margin-left: 1;
    }
    """

    def __init__(self, default_step: float = 1.0, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._default_step = default_step

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Observation step", classes="modal-title")
            yield Static(
                "Simulated time one playback tick advances. Events keep their "
                "own exact dates whatever this is.",
                classes="modal-help",
            )
            yield Input(
                placeholder="observation step (float > 0)",
                value=f"{self._default_step}",
                id="observation-step",
            )
            with Horizontal():
                yield Button("Cancel", id="observation-cancel")
                yield Button("Apply", variant="primary", id="observation-ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "observation-ok":
            self._submit()
        elif event.button.id == "observation-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "observation-step":
            self._submit()

    def _submit(self) -> None:
        try:
            step = float(self.query_one("#observation-step", Input).value)
        except (TypeError, ValueError):
            self.dismiss(None)
            return
        # A step of zero or less would either freeze the clock or ask the
        # engine to go backwards, which it refuses; cancel instead.
        self.dismiss(step if step > 0 else None)


class IntegrationModal(ModalScreen[Optional[dict]]):
    """Ask for the two PDMP knobs and dismiss with ``{"dt_max", "dt_cond"}``.

    Either field left empty is left untouched, so the modal can be used to
    change one without knowing the other.
    """

    DEFAULT_CSS = """
    IntegrationModal {
        align: center middle;
    }
    IntegrationModal > Vertical {
        width: 64;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }
    IntegrationModal Horizontal {
        height: auto;
        align-horizontal: right;
        margin-top: 1;
    }
    IntegrationModal Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Integration knobs", classes="modal-title")
            yield Static(
                "Maximum integration step (empty = unchanged):",
                classes="modal-help",
            )
            yield Input(placeholder="dtMax", id="integration-dt-max")
            yield Static(
                "Precision of the crossing search (empty = unchanged). This is "
                "what decides how far past a bound the solver stops.",
                classes="modal-help",
            )
            yield Input(placeholder="dtCond", id="integration-dt-cond")
            with Horizontal():
                yield Button("Cancel", id="integration-cancel")
                yield Button("Apply", variant="primary", id="integration-ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "integration-ok":
            self._submit()
        elif event.button.id == "integration-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    @staticmethod
    def _read(widget: Input) -> Optional[float]:
        raw = widget.value.strip()
        if not raw:
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _submit(self) -> None:
        knobs = {
            "dt_max": self._read(self.query_one("#integration-dt-max", Input)),
            "dt_cond": self._read(self.query_one("#integration-dt-cond", Input)),
        }
        if all(value is None for value in knobs.values()):
            self.dismiss(None)
            return
        self.dismiss(knobs)
