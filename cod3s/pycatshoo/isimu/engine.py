"""Synchronous wrapper around ``PycSystem.isimu_*`` for the interactive TUI.

The engine is the single source of truth the TUI watches:

* it owns the timeline (``history``: a list of :class:`FiredEvent`),
* it exposes pre/post-step variable snapshots so the TUI can colorize what
  changed at the last step vs what differs from the declared initial values,
* it captures ``system.currentTime()`` after each step because PyCATSHOO's
  ``PycTransition.end_time`` is the planned end-time, not the actual firing
  time (it is even mutated during ``isimu_fireable_transitions``).

Two notable workarounds compared to calling ``PycSystem.isimu_*`` directly:

#. ``isimu_start`` (``cod3s/pycatshoo/system.py:846``) calls ``startInteractive`` /
   ``stepForward`` *before* re-creating ``isimu_sequence``, so any transition
   fired at t=0 is dropped from the recorded sequence.
   :meth:`ISimuEngine.start` re-creates ``isimu_sequence`` first.
#. The native step-forward is the *raw* ``stepForward``; the COD3S
   ``isimu_step_forward`` (``cod3s/pycatshoo/system.py:1017``) records into
   ``isimu_sequence`` and returns the actually fired transitions. The engine
   uses ``isimu_step_forward`` everywhere — including the bootstrap step at
   start — so the timeline is always complete.

Note on non-deterministic occurrence laws (``exp``, ``uniform``, ...) — by
design, the interactive simulator does **not** auto-sample them. They are
returned by ``isimu_fireable_transitions`` with ``end_time = inf`` until the
operator explicitly re-plans them (via the ``p`` modal or programmatically
via :meth:`replan`). ``isimu_step_forward`` filters fireable transitions on
``end_time <= currentTime()``, so an un-replanned non-deterministic
transition is skipped — the operator must give it a date to make the
simulator advance through it. This is intentional: it gives the operator
full control over the trace instead of hiding random draws behind the
engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from cod3s.pycatshoo.isimu.diff import snapshot_initials, snapshot_vars
from cod3s.pycatshoo.sequence import PycSequence


@dataclass
class FiredEvent:
    """A single step of the interactive timeline.

    Attributes:
        fired_at: ``system.currentTime()`` *after* the step (the actual firing
            time of the transitions, not the planned ``end_time``).
        transitions: List of :class:`PycTransition` returned by
            ``isimu_step_forward``. May be empty when no transition was due.
        vars_before: Variable snapshot at the entry of this step.
        vars_after: Variable snapshot at the exit of this step.
    """

    fired_at: float
    transitions: List[Any]
    vars_before: Dict[str, Any] = field(default_factory=dict)
    vars_after: Dict[str, Any] = field(default_factory=dict)


class ISimuEngine:
    """Drive a ``PycSystem`` step-by-step and record a clean timeline.

    The engine is intentionally synchronous: PyCATSHOO is a C++ singleton and
    every public method here calls into that backend directly. The TUI must
    invoke these methods from a worker thread (``@work(thread=True)``) to keep
    the event loop responsive.
    """

    def __init__(self, system: Any) -> None:
        self.system = system
        self.history: List[FiredEvent] = []
        self.var_initial: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> FiredEvent:
        """Enter interactive mode and capture the bootstrap step.

        Idempotent: calling ``start()`` on a running engine first calls
        ``stop()`` so PyCATSHOO ends up in a fresh interactive session.

        Returns the :class:`FiredEvent` produced by the bootstrap
        ``isimu_step_forward`` (which may have no transitions if nothing is due
        at t=0).
        """
        try:
            self.system.stopInteractive()
        except Exception:
            # PyCATSHOO complains when stopping a session that was never
            # started; for an idempotent ``start()`` we swallow this.
            pass
        self.system.startInteractive()
        # Reset the underlying sequence BEFORE the first step so that any
        # delay(0) transitions fired at t=0 land in the recorded timeline.
        # mypy is unaware Pydantic provides defaults for every PycSequence
        # field; the call is valid at runtime (cf. tests/isimu/test_engine.py).
        self.system.isimu_sequence = PycSequence()  # type: ignore[call-arg]
        self.var_initial = snapshot_initials(self.system)
        self.history = []
        return self._step_and_capture()

    def stop(self) -> None:
        """Leave interactive mode. Safe to call when not started."""
        try:
            self.system.stopInteractive()
        except Exception:
            pass

    def reset(self) -> FiredEvent:
        """Restart the simulation from t=0."""
        self.stop()
        return self.start()

    # ------------------------------------------------------------------
    # Stepping
    # ------------------------------------------------------------------
    def step_forward(self) -> FiredEvent:
        """Advance the simulator and record the resulting :class:`FiredEvent`."""
        return self._step_and_capture()

    def step_backward(self) -> List[Any]:
        """Undo the last step and pop the matching :class:`FiredEvent`.

        Returns the list of transitions that were retired from the underlying
        ``isimu_sequence`` (an empty list when there is nothing to undo).
        """
        retired = self.system.isimu_step_backward(reset_planning=True) or []
        if retired and self.history:
            self.history.pop()
        return list(retired)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------
    @property
    def current_time(self) -> float:
        return float(self.system.currentTime())

    @property
    def vars_current(self) -> Dict[str, Any]:
        if self.history:
            return self.history[-1].vars_after
        return dict(self.var_initial)

    @property
    def vars_previous(self) -> Dict[str, Any]:
        if self.history:
            return self.history[-1].vars_before
        return dict(self.var_initial)

    def fireable(self) -> List[Any]:
        """Return ``isimu_fireable_transitions`` (preserves ``None`` slots)."""
        return list(self.system.isimu_fireable_transitions())

    def active(self) -> List[Any]:
        """Return ``isimu_active_transitions``."""
        return list(self.system.isimu_active_transitions())

    def replan(self, trans_id, date=None, state_index=None):
        """Plan a transition at an arbitrary date (advanced action).

        Delegates to ``PycSystem.isimu_set_transition`` without stepping
        forward — the caller is expected to call :meth:`step_forward`
        afterwards.
        """
        return self.system.isimu_set_transition(
            trans_id=trans_id, date=date, state_index=state_index
        )

    # ------------------------------------------------------------------
    # Inst transitions (probabilistic branching)
    # ------------------------------------------------------------------
    def pending_inst(self) -> List[Any]:
        """Return the inst transitions currently fireable at ``currentTime``.

        An inst transition is identified by a list-typed ``target`` (each entry
        is a :class:`StateProbModel`). When at least one inst transition is
        pending, PyCATSHOO hides timed transitions from ``fireable``, so
        callers can safely treat a non-empty ``pending_inst`` as the *only*
        thing the user needs to resolve before time can advance.
        """
        return [
            trans
            for trans in self.fireable()
            if trans is not None and isinstance(trans.target, list)
        ]

    def resolve_inst(self, choices: Dict[int, int]) -> FiredEvent:
        """Resolve all pending inst transitions in a single atomic step.

        Parameters
        ----------
        choices
            Mapping ``{trans_id_in_fireable: state_index}``. Each entry pins
            the target branch for a pending inst transition. ``trans_id`` is
            the index in the engine's ``fireable()`` list.

        Returns
        -------
        FiredEvent
            The event recorded by the bootstrap-compatible step that drains
            the inst transitions.

        Notes
        -----
        PyCATSHOO drains *all* inst transitions in a single ``stepForward``;
        the caller MUST submit one ``state_index`` per pending inst
        transition. Submitting fewer choices will leave the un-resolved
        transitions to be sampled by PyCATSHOO's RNG.
        """
        for trans_id, state_index in choices.items():
            self.system.isimu_set_transition(
                trans_id=trans_id, state_index=state_index
            )
        return self._step_and_capture()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _step_and_capture(self) -> FiredEvent:
        if self.history:
            vars_before = self.history[-1].vars_after
        else:
            # First step: the snapshot taken right before stepForward is the
            # post-startInteractive state, not the declared initials.
            vars_before = snapshot_vars(self.system)
        fired = list(self.system.isimu_step_forward() or [])
        vars_after = snapshot_vars(self.system)
        evt = FiredEvent(
            fired_at=float(self.system.currentTime()),
            transitions=fired,
            vars_before=vars_before,
            vars_after=vars_after,
        )
        self.history.append(evt)
        return evt
