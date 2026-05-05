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
    """List of fireable transitions in a navigable widget.

    Two display modes coexist in a single panel:

    * **Timed mode** — the default :class:`DataTable` listing fireable
      transitions ranked by ``end_time``. The trailing ★ column lights up
      on rows that share ``end_time`` with the cursor. ``p`` posts a
      :class:`ReplanRequested` for the cursor's transition.
    * **Inst pending mode** — when ``state.pending_inst`` is non-empty,
      PyCATSHOO has hidden the timed transitions; the panel switches to
      a :class:`Tree` showing each pending inst transition with its
      branches (target state + probability). The default selection is
      the max-probability branch per transition; a deterministic single
      branch is marked with ``!``. ``s`` submits all selections in one
      atomic call (:class:`InstResolveRequested` posted to the App).
    """

    BORDER_TITLE = "Fireable transitions"

    STAR_CHAR = "★"
    DETERMINISTIC_MARKER = "!"

    BINDINGS = [
        Binding("p", "replan_cursor", "Re-plan"),
        Binding("s", "submit_inst", "Submit (inst)"),
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

    class InstResolveRequested(Message):
        """Posted to the App when the user presses ``s`` in inst pending mode.

        Carries ``choices: dict[trans_id_in_fireable, state_index]`` for every
        pending inst transition. The App forwards them to
        :meth:`ISimuEngine.resolve_inst`.
        """

        def __init__(self, choices: dict) -> None:
            super().__init__()
            self.choices = choices

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Live cache of ``state.fireable`` (with ``None`` slots) and a parallel
        # mapping ``display_row -> original index``. Both are needed to drive
        # the ★ marker from ``on_data_table_row_highlighted``.
        self._fireable_cache: List[Optional[Any]] = []
        self._visible_idx: List[int] = []
        # Inst pending mode bookkeeping:
        # * ``_pending_inst_cache``: list of (fireable_index, transition).
        # * ``_inst_choices``: {fireable_index: state_index} the user picked.
        self._pending_inst_cache: List[tuple] = []
        self._inst_choices: dict = {}

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

    def action_submit_inst(self) -> None:
        """Post :class:`InstResolveRequested` with the current branch choices.

        No-op when there is nothing pending (the user is in timed mode).
        """
        if not self._pending_inst_cache:
            return
        # Make sure every pending inst has a choice — fall back to the
        # cached default (max-prob branch) if the user didn't override.
        choices = dict(self._inst_choices)
        for fireable_idx, _ in self._pending_inst_cache:
            choices.setdefault(fireable_idx, self._default_branch(fireable_idx))
        self.post_message(self.InstResolveRequested(choices=choices))

    def compose(self) -> ComposeResult:
        table: DataTable[str] = DataTable(
            id="fireable-table",
            cursor_type="row",
            zebra_stripes=True,
        )
        table.add_columns("#", "comp", "transition", "source → target", "end_time", "★")
        yield table
        # Inst-mode tree, hidden by default.
        tree: Tree[Any] = Tree(
            "Pending inst (press s to submit)",
            id="inst-pending-tree",
        )
        tree.display = False
        yield tree

    def refresh_from_state(self, state: ISimuState) -> None:
        self._fireable_cache = list(state.fireable)
        self._visible_idx = []
        table = self.query_one("#fireable-table", DataTable)
        tree = self.query_one("#inst-pending-tree", Tree)
        table.clear()

        if state.pending_inst:
            # Inst pending mode: hide the table, populate the tree.
            self._render_pending_inst(state.pending_inst, tree)
            table.display = False
            tree.display = True
            return

        # Timed mode: hide the tree, populate the table.
        tree.display = False
        table.display = True
        self._pending_inst_cache = []
        self._inst_choices = {}

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
    # Inst pending rendering
    # ------------------------------------------------------------------
    def _render_pending_inst(self, pending: List[Any], tree: Tree) -> None:
        """Populate the inst pending tree and seed the default selections."""
        # Find the fireable index for each pending inst (kept stable across
        # refreshes by matching on ``(comp_name, name)`` — there cannot be
        # two pending inst transitions with the same identity).
        pending_pairs: List[tuple] = []
        for trans in pending:
            try:
                idx = next(
                    i
                    for i, t in enumerate(self._fireable_cache)
                    if t is not None
                    and t.comp_name == trans.comp_name
                    and t.name == trans.name
                )
            except StopIteration:
                continue
            pending_pairs.append((idx, trans))

        self._pending_inst_cache = pending_pairs
        self._inst_choices = {}

        tree.clear()
        for fireable_idx, trans in pending_pairs:
            branches = trans.target  # list[StateProbModel]
            deterministic = len(branches) == 1
            label = Text()
            label.append(f"{trans.comp_name}.{trans.name}", style="green")
            label.append(f"  ({len(branches)} branches)", style="dim")
            if deterministic:
                label.append(f" {self.DETERMINISTIC_MARKER}", style="bold yellow")
            node = tree.root.add(label, expand=True, data=fireable_idx)

            # Default selection = max-prob branch (or the only branch).
            default_state_idx = self._default_branch_from_branches(branches)
            self._inst_choices[fireable_idx] = default_state_idx

            for state_idx, branch in enumerate(branches):
                child_label = self._format_branch(branch, selected=(state_idx == default_state_idx))
                node.add_leaf(child_label, data=(fireable_idx, state_idx))
        tree.root.expand_all()

    @staticmethod
    def _format_branch(branch: Any, *, selected: bool) -> Text:
        """Render a branch as ``[●] → state_name (p=0.NN)`` or ``[ ]`` if not selected."""
        marker = "●" if selected else " "
        prob_str = f"p={branch.prob:.3f}" if branch.prob is not None else "p=?"
        text = Text()
        text.append(f"[{marker}] ", style="bold magenta" if selected else "dim")
        text.append("→ ", style=ARROW_STYLE)
        text.append(str(branch.state), style="green")
        text.append(f"  ({prob_str})", style="cyan")
        return text

    @staticmethod
    def _default_branch_from_branches(branches: List[Any]) -> int:
        """Index of the highest-probability branch (ties broken by order)."""
        best_idx = 0
        best_prob = -1.0
        for i, branch in enumerate(branches):
            p = branch.prob if branch.prob is not None else 0.0
            if p > best_prob:
                best_prob = p
                best_idx = i
        return best_idx

    def _default_branch(self, fireable_idx: int) -> int:
        """Look up the default branch for a given fireable index from the cache."""
        for idx, trans in self._pending_inst_cache:
            if idx == fireable_idx:
                return self._default_branch_from_branches(trans.target)
        return 0

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """User selected a branch leaf — record the choice and re-render labels."""
        if getattr(event.control, "id", None) != "inst-pending-tree":
            return
        node = event.node
        if node is None or node.data is None:
            return
        # Branch leaves carry a (fireable_idx, state_idx) tuple.
        if not isinstance(node.data, tuple):
            return
        fireable_idx, state_idx = node.data
        self._inst_choices[fireable_idx] = state_idx
        self._refresh_inst_labels()

    def _refresh_inst_labels(self) -> None:
        """Rewrite branch leaf labels to reflect the current selections."""
        tree = self.query_one("#inst-pending-tree", Tree)
        for parent in tree.root.children:
            for leaf in parent.children:
                if leaf.data is None or not isinstance(leaf.data, tuple):
                    continue
                fireable_idx, state_idx = leaf.data
                # Resolve the branch object from the cache.
                branch = self._branch_at(fireable_idx, state_idx)
                if branch is None:
                    continue
                selected = self._inst_choices.get(fireable_idx) == state_idx
                leaf.label = self._format_branch(branch, selected=selected)

    def _branch_at(self, fireable_idx: int, state_idx: int) -> Optional[Any]:
        for idx, trans in self._pending_inst_cache:
            if idx == fireable_idx and 0 <= state_idx < len(trans.target):
                return trans.target[state_idx]
        return None

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
