"""Textual widgets composing the four panels of ``cod3s-isimu``.

Each panel exposes a ``refresh_from_state(state)`` method consuming an
:class:`ISimuState` snapshot. This decouples the panels from the live
:class:`ISimuEngine` so they can be unit-tested with synthetic states.

Panel layout (left → right, top → bottom):

* :class:`FireablePanel` — top-left, full height; ``DataTable`` listing the
  fireable transitions ranked by ``end_time``.
* :class:`ComponentsPanel` — top-right; ``Input`` filter + ``Tree`` showing
  every component's variables with their current/initial values.
* :class:`LastDeltaPanel` — middle-right; ``RichLog`` summarising what fired
  and which variables changed at the last step.
* :class:`HistoryPanel` — bottom; ``RichLog`` listing every step in reverse
  chronological order, grouped by ``fired_at``.
"""

from __future__ import annotations

from typing import Any, List, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.coordinate import Coordinate
from textual.message import Message
from textual.widgets import DataTable, Input, RichLog, Tree

from cod3s.pycatshoo.isimu.grouping import group_fires_together
from cod3s.pycatshoo.isimu.state import ISimuState

# ---------------------------------------------------------------------------
# Shared formatting helpers — keep style strings in one place so the panels
# render typed values and transition arrows consistently.
# ---------------------------------------------------------------------------

ARROW_STYLE = "orange3"


def _value_style(value: Any, *, bold: bool = False, dim: bool = False) -> str:
    """Return the Rich style string for a typed variable value.

    - ``bool`` False → magenta, True → green
    - ``int`` / ``float`` → cyan
    - anything else → no color
    The ``bold`` and ``dim`` flags are appended as additional tokens.
    """
    tokens: list[str] = []
    if isinstance(value, bool):
        tokens.append("green" if value else "magenta")
    elif isinstance(value, (int, float)):
        tokens.append("cyan")
    if bold:
        tokens.append("bold")
    if dim:
        tokens.append("dim")
    return " ".join(tokens)


def _render_value(value: Any, *, bold: bool = False, dim: bool = False) -> Text:
    return Text(str(value), style=_value_style(value, bold=bold, dim=dim))


def _arrow_text() -> Text:
    return Text(" → ", style=ARROW_STYLE)


# ---------------------------------------------------------------------------
# FireablePanel
# ---------------------------------------------------------------------------


class FireablePanel(Container):
    """List of fireable transitions in a navigable :class:`DataTable`.

    The trailing ★ column lights up on the rows that share ``end_time`` with
    the currently highlighted row — those are the transitions PyCATSHOO will
    fire together at the next ``stepForward``.

    Bindings local to this panel (active only when the inner :class:`DataTable`
    has focus): ``p`` posts a :class:`ReplanRequested` message to the App for
    the cursor's transition.
    """

    BORDER_TITLE = "Fireable transitions"

    STAR_CHAR = "★"

    BINDINGS = [
        Binding("p", "replan_cursor", "Re-plan"),
    ]

    class ReplanRequested(Message):
        """Posted to the App when the user presses ``p`` on a fireable row.

        Carries the original index in ``isimu_active_transitions`` (so
        ``isimu_set_transition`` can be called by the App) and the
        ``PycTransition`` itself (so the App can compose a modal title from
        ``comp_name`` and ``name``).
        """

        def __init__(self, idx: int, trans: Any) -> None:
            super().__init__()
            self.idx = idx
            self.trans = trans

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Live cache of ``state.fireable`` (with ``None`` slots) and a parallel
        # mapping ``display_row -> original index``. Both are needed to drive
        # the ★ marker from ``on_data_table_row_highlighted``.
        self._fireable_cache: List[Optional[Any]] = []
        self._visible_idx: List[int] = []

    def action_replan_cursor(self) -> None:
        """Post a :class:`ReplanRequested` for the transition at the cursor.

        No-op when the table is empty or the cursor sits on a non-fireable
        slot. Validation that the engine actually exists is the App's job.
        """
        table = self.query_one("#fireable-table", DataTable)
        if table.row_count == 0:
            return
        cursor_row = table.cursor_row
        if cursor_row is None or cursor_row < 0:
            return
        if cursor_row >= len(self._visible_idx):
            return
        original_idx = self._visible_idx[cursor_row]
        if original_idx >= len(self._fireable_cache):
            return
        trans = self._fireable_cache[original_idx]
        if trans is None:
            return
        self.post_message(self.ReplanRequested(idx=original_idx, trans=trans))

    def compose(self) -> ComposeResult:
        table: DataTable[str] = DataTable(
            id="fireable-table",
            cursor_type="row",
            zebra_stripes=True,
        )
        table.add_columns("#", "comp", "transition", "source → target", "end_time", "★")
        yield table

    def refresh_from_state(self, state: ISimuState) -> None:
        self._fireable_cache = list(state.fireable)
        self._visible_idx = []
        table = self.query_one("#fireable-table", DataTable)
        table.clear()
        for idx, trans in enumerate(state.fireable):
            if trans is None:
                continue
            self._visible_idx.append(idx)
            target = trans.target if isinstance(trans.target, str) else "[…]"
            end_time = f"{trans.end_time:.3f}" if trans.end_time is not None else "—"
            src_target = Text()
            src_target.append(str(trans.source))
            src_target.append(_arrow_text())
            src_target.append(target)
            table.add_row(
                str(idx),
                str(trans.comp_name),
                str(trans.name),
                src_target,
                end_time,
                "",  # ★ column populated by _highlight_group on cursor move
            )
        # Seed the ★ markers for the row the cursor will land on (row 0).
        if table.row_count > 0:
            self._highlight_group(0)

    # ------------------------------------------------------------------
    # ★ "fires together" highlight
    # ------------------------------------------------------------------
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if getattr(event.control, "id", None) != "fireable-table":
            return
        self._highlight_group(event.cursor_row)

    def _highlight_group(self, cursor_row: int) -> None:
        """Update the ★ column so peers of the cursor row are marked."""
        if cursor_row < 0 or cursor_row >= len(self._visible_idx):
            return
        cursor_orig = self._visible_idx[cursor_row]
        group = group_fires_together(self._fireable_cache, cursor_orig)

        table = self.query_one("#fireable-table", DataTable)
        star_col = len(table.columns) - 1  # ★ is the last column
        for display_row, orig_idx in enumerate(self._visible_idx):
            marker = self.STAR_CHAR if orig_idx in group else ""
            try:
                table.update_cell_at(Coordinate(display_row, star_col), marker)
            except Exception:
                # The table may have been re-rendered between the highlight
                # event and here; ignore stale coordinates.
                continue


# ---------------------------------------------------------------------------
# ComponentsPanel
# ---------------------------------------------------------------------------


class ComponentsPanel(Container):
    """Tree of variables grouped by component, with a live substring filter.

    The :class:`Input` filter re-renders the tree on every keystroke via
    ``on_input_changed``. The last :class:`ISimuState` pushed by the App is
    cached so the panel can re-render itself without going back to the engine.
    """

    BORDER_TITLE = "Components / Variables"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._state: Optional[ISimuState] = None

    def compose(self) -> ComposeResult:
        yield Input(placeholder="filter (e.g. pump.flow)", id="components-filter")
        yield Tree("system", id="components-tree")

    def refresh_from_state(self, state: ISimuState) -> None:
        self._state = state
        self._render_tree()

    def on_input_changed(self, event: Input.Changed) -> None:
        if getattr(event.input, "id", None) == "components-filter":
            self._render_tree()

    def _render_tree(self) -> None:
        if self._state is None:
            return
        state = self._state

        tree: Tree[Any] = self.query_one("#components-tree", Tree)
        tree.clear()
        filter_text = self.query_one("#components-filter", Input).value.lower()

        # Bucket variables by component (everything before the first ".").
        by_comp: dict[str, dict[str, Any]] = {}
        for full_name, value in sorted(state.var_current.items()):
            comp, _, var = full_name.partition(".")
            by_comp.setdefault(comp, {})[var] = value

        for comp, vars_d in sorted(by_comp.items()):
            comp_node = tree.root.add(comp, expand=True)
            for var_name, value in sorted(vars_d.items()):
                full = f"{comp}.{var_name}"
                if filter_text and filter_text not in full.lower():
                    continue
                comp_node.add_leaf(
                    self._format_var(
                        var_name,
                        current=value,
                        initial=state.var_initial.get(full),
                        previous=state.var_previous.get(full),
                    )
                )

    @staticmethod
    def _format_var(name: str, current: Any, initial: Any, previous: Any) -> Text:
        """Color a variable line according to its delta state.

        Type-based colours always apply: bool ``False`` → magenta, bool
        ``True`` → green, numeric → cyan, other types → no color. The state
        cue is layered on top:

        - Changed at last step → values rendered **bold** with an orange
          ``previous → current`` arrow.
        - Differs from initial → current value at full intensity, plus a
          dim ``(init: …)`` hint.
        - Unchanged at initial → current value rendered dim.
        """
        text = Text()
        text.append(f"{name}: ")
        if previous != current:
            text.append(_render_value(previous, bold=True))
            text.append(_arrow_text())
            text.append(_render_value(current, bold=True))
        elif initial != current:
            text.append(_render_value(current))
            text.append(Text(f"  (init: {initial})", style="dim"))
        else:
            text.append(_render_value(current, dim=True))
        return text


# ---------------------------------------------------------------------------
# LastDeltaPanel
# ---------------------------------------------------------------------------


class LastDeltaPanel(Container):
    """Summary of the last fired step."""

    BORDER_TITLE = "Last transition Δ"

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="last-delta-log",
            wrap=True,
            highlight=False,
            markup=False,
        )

    def refresh_from_state(self, state: ISimuState) -> None:
        log = self.query_one("#last-delta-log", RichLog)
        log.clear()
        if state.last_fired_at is None:
            log.write(Text("(simulation not started)", style="dim"))
            return

        log.write(Text(f"t = {state.last_fired_at:.3f}", style="bold cyan"))

        if not state.last_fired_transitions:
            log.write(Text("  (bootstrap step — no transition fired)", style="dim"))
        else:
            for trans in state.last_fired_transitions:
                target = trans.target if isinstance(trans.target, str) else "[…]"
                line = Text()
                line.append("• ", style="green")
                line.append(f"{trans.comp_name}.{trans.name}: ", style="green")
                line.append(str(trans.source), style="green")
                line.append(_arrow_text())
                line.append(target, style="green")
                log.write(line)

        changed = state.changed_at_last_step()
        if not changed:
            log.write(Text("(no variable changed)", style="dim"))
            return

        log.write(Text("Δ vars:", style="bold"))
        for name, value in sorted(changed.items()):
            prev = state.var_previous.get(name)
            line = Text()
            line.append(f"  {name}: ")
            line.append(_render_value(prev, bold=True))
            line.append(_arrow_text())
            line.append(_render_value(value, bold=True))
            log.write(line)


# ---------------------------------------------------------------------------
# HistoryPanel
# ---------------------------------------------------------------------------


class HistoryPanel(Container):
    """Anti-chronological list of fired events grouped by ``fired_at``."""

    BORDER_TITLE = "History (grouped by t)"

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="history-log",
            wrap=False,
            highlight=False,
            markup=False,
        )

    def refresh_from_state(self, state: ISimuState) -> None:
        log = self.query_one("#history-log", RichLog)
        log.clear()
        if not state.history:
            log.write(Text("(no events yet)", style="dim"))
            return
        for evt in reversed(state.history):
            if not evt.transitions:
                log.write(Text(f"t={evt.fired_at:.3f}  ▸ <bootstrap>", style="dim"))
                continue
            names = ", ".join(
                f"{trans.comp_name}.{trans.name}" for trans in evt.transitions
            )
            log.write(Text(f"t={evt.fired_at:.3f}  ▸ {names}"))
