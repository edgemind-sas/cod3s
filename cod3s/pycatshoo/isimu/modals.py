"""Modal screens used by ``cod3s-isimu``.

Two modals at the moment:

* :class:`ExportModal` — collects a destination path (without extension) and
  returns a :class:`pathlib.Path`. The App is responsible for writing the
  CSV and JSON files via :func:`export_csv` / :func:`export_json`.
* :class:`ReplanModal` — collects a planned date for an already-identified
  transition. The transition is chosen by the caller (``p`` is bound to the
  ``FireablePanel`` and uses the cursor row), so the modal asks **only**
  for the date and returns it as ``Optional[float]``.

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
