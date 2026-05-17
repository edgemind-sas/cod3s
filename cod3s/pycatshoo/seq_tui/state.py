"""Immutable snapshot of the ``cod3s-seq`` TUI state.

The Textual panels never reach into the live ``SequenceAnalyser`` —
they consume a :class:`SeqTuiState` snapshot, rebuilt once per pipeline
mutation. This decouples rendering from analysis and makes the panels
trivially testable with synthetic states (no Pydantic / no PyCATSHOO).

The state also carries the :class:`UndoStack` history so the app can
roll back step applications.
"""

from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Deque, Literal, Optional

if TYPE_CHECKING:
    from cod3s.pycatshoo.sequence import SequenceAnalyser
    from cod3s.pycatshoo.seq_tui.pipeline import Pipeline, PipelineStep


SourceFormat = Literal["xml", "json-cod3s"]


@dataclass(frozen=True)
class SeqTuiState:
    """Snapshot of everything a panel needs to render once.

    Frozen so the app can keep references in the undo stack without
    worrying about accidental mutation. Pipeline application is done
    via :meth:`with_step_applied`, which returns a *new* state.

    The ``available_objfms_*`` fields are populated only in **live
    mode** (``cod3s-seq --factory module:fn``). They power the
    checklist UX of the :class:`ConfigFilterObjFMCyclesModal`. In
    post-mortem mode (XML / JSON loaded without a system) they stay
    empty and the modal falls back to its text-input UX.
    """

    analyser: "SequenceAnalyser"
    pipeline: "Pipeline"
    selected_seq_idx: Optional[int] = None
    source_path: Optional[Path] = None
    source_format: Optional[SourceFormat] = None
    last_delta: Optional["StateDelta"] = None
    available_objfms_internal: tuple[str, ...] = ()
    available_objfms_external: tuple[str, ...] = ()

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------
    @classmethod
    def from_initial(
        cls,
        analyser: "SequenceAnalyser",
        *,
        source_path: Optional[Path] = None,
        source_format: Optional[SourceFormat] = None,
        system: Optional[Any] = None,
    ) -> "SeqTuiState":
        """Build the starting state from a freshly loaded analyser.

        An empty :class:`Pipeline` is attached. Tests typically use this
        builder rather than constructing the dataclass directly.

        When a ``system`` (a populated :class:`PycSystem`) is provided
        — the **live mode** — the analyser is attached to that system
        (enabling ``filter_objfm_cycles`` auto-discovery) and the
        ObjFM names are extracted into the
        ``available_objfms_internal`` / ``available_objfms_external``
        fields so the configuration modal can render a checklist
        instead of a free-form text input.
        """
        # Local import to avoid a circular import at module load time.
        from cod3s.pycatshoo.seq_tui.pipeline import Pipeline

        internal: tuple[str, ...] = ()
        external: tuple[str, ...] = ()
        if system is not None:
            # Attach the system so SequenceAnalyser.filter_objfm_cycles
            # can auto-discover ObjFM when called with no explicit
            # lists. Mirrors what from_pyc_system does for the live
            # ingestion path.
            analyser._system = system
            int_names, ext_names = analyser.discover_objfms()
            internal = tuple(int_names)
            external = tuple(ext_names)

        return cls(
            analyser=analyser,
            pipeline=Pipeline(),
            source_path=source_path,
            source_format=source_format,
            available_objfms_internal=internal,
            available_objfms_external=external,
        )

    def with_step_applied(self, step: "PipelineStep") -> "SeqTuiState":
        """Return a new state with ``step`` applied to a deep copy of the
        analyser, ``step`` appended to the pipeline, and ``last_delta``
        recording the size diff.

        The original state is untouched — the caller is responsible for
        pushing it onto the undo stack before discarding the reference.
        """
        # Deep-copy the analyser so the snapshot in the undo stack stays
        # frozen even though the underlying sequences are mutated by the
        # inplace step.apply().
        new_analyser = copy.deepcopy(self.analyser)
        before_count = len(new_analyser.sequences)
        before_weight = sum(s.weight for s in new_analyser.sequences)
        step.apply(new_analyser)
        after_count = len(new_analyser.sequences)
        after_weight = sum(s.weight for s in new_analyser.sequences)

        delta = StateDelta(
            d_sequences=after_count - before_count,
            d_total_weight=after_weight - before_weight,
            step_summary=step.summary(),
            before_sequences=before_count,
            after_sequences=after_count,
        )

        new_pipeline = self.pipeline.append(step)
        return replace(
            self,
            analyser=new_analyser,
            pipeline=new_pipeline,
            # Keep selection only if still in range.
            selected_seq_idx=(
                self.selected_seq_idx
                if (
                    self.selected_seq_idx is not None
                    and self.selected_seq_idx < after_count
                )
                else None
            ),
            last_delta=delta,
        )

    def with_selection(self, idx: Optional[int]) -> "SeqTuiState":
        """Return a new state with ``selected_seq_idx`` updated."""
        if idx is not None and (idx < 0 or idx >= len(self.analyser.sequences)):
            idx = None
        return replace(self, selected_seq_idx=idx)

    # ------------------------------------------------------------------
    # Sorted views
    # ------------------------------------------------------------------
    def sorted_sequences(self):
        """Sequences sorted by descending weight (stable for ties)."""
        return sorted(
            enumerate(self.analyser.sequences),
            key=lambda iv: iv[1].weight,
            reverse=True,
        )

    @property
    def total_weight(self) -> int:
        return sum(s.weight for s in self.analyser.sequences)


@dataclass(frozen=True)
class StateDelta:
    """Size diff between two consecutive states.

    Used by :class:`PipelinePanel` to annotate the step that just ran:
    ``-3 sigs, Δw=0``.
    """

    d_sequences: int
    d_total_weight: int
    step_summary: str
    # Absolute counts on either side of the step. Carried so the
    # notification can render the explicit before → after transition
    # (`10000 → 8544 séquences distinctes`), more readable than the
    # raw delta in isolation. Default 0 keeps backward compat for
    # call sites that don't populate them.
    before_sequences: int = 0
    after_sequences: int = 0


# ---------------------------------------------------------------------------
# Undo stack — a bounded deque of past states.
# ---------------------------------------------------------------------------


@dataclass
class UndoStack:
    """Bounded undo / redo stack for :class:`SeqTuiState` snapshots.

    Default ``maxlen=20`` is a compromise between memory cost (20 deep
    copies of a 50k-sequence analyser stays well under 2 GB on typical
    desktops) and useful history depth. When the cap is reached, the
    oldest snapshot is silently dropped; callers may surface a
    notification.
    """

    maxlen: int = 20
    _undo: Deque["SeqTuiState"] = field(default_factory=lambda: deque(maxlen=20))
    _redo: Deque["SeqTuiState"] = field(default_factory=lambda: deque(maxlen=20))

    def __post_init__(self) -> None:
        # Honor a custom ``maxlen`` value at instantiation.
        self._undo = deque(self._undo, maxlen=self.maxlen)
        self._redo = deque(self._redo, maxlen=self.maxlen)

    def push(self, state: "SeqTuiState") -> None:
        """Push ``state`` onto the undo stack; clears the redo stack.

        Call this with the state *before* a step is applied. The newly
        applied state becomes the new ``current`` outside this class.
        """
        self._undo.append(state)
        self._redo.clear()

    def undo(self, current: "SeqTuiState") -> Optional["SeqTuiState"]:
        """Pop the last state off undo and push ``current`` onto redo.

        Returns the restored state, or ``None`` if the undo stack is
        empty.
        """
        if not self._undo:
            return None
        previous = self._undo.pop()
        self._redo.append(current)
        return previous

    def redo(self, current: "SeqTuiState") -> Optional["SeqTuiState"]:
        """Pop the last state off redo and push ``current`` onto undo.

        Returns the restored state, or ``None`` if the redo stack is
        empty.
        """
        if not self._redo:
            return None
        next_state = self._redo.pop()
        self._undo.append(current)
        return next_state

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_depth(self) -> int:
        return len(self._undo)

    @property
    def redo_depth(self) -> int:
        return len(self._redo)
