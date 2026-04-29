"""Synchronous wrapper around ``PycSystem.isimu_*`` for the interactive TUI.

The engine is the single source of truth the TUI watches:

* it owns the timeline (``history``: a list of :class:`FiredEvent`),
* it exposes pre/post-step variable snapshots so the TUI can colorize what
  changed at the last step vs what differs from the declared initial values,
* it captures ``system.currentTime()`` after each step because PyCATSHOO's
  ``PycTransition.end_time`` is the planned end-time, not the actual firing
  time (it is even mutated during ``isimu_fireable_transitions``).

Three notable workarounds compared to calling ``PycSystem.isimu_*`` directly:

#. ``isimu_start`` (``cod3s/pycatshoo/system.py:846``) calls ``startInteractive`` /
   ``stepForward`` *before* re-creating ``isimu_sequence``, so any transition
   fired at t=0 is dropped from the recorded sequence.
   :meth:`ISimuEngine.start` re-creates ``isimu_sequence`` first.
#. The native step-forward is the *raw* ``stepForward``; the COD3S
   ``isimu_step_forward`` (``cod3s/pycatshoo/system.py:1017``) records into
   ``isimu_sequence`` and returns the actually fired transitions. The engine
   uses ``isimu_step_forward`` everywhere — including the bootstrap step at
   start — so the timeline is always complete.
#. PyCATSHOO does **not** auto-sample non-deterministic occurrence laws
   (``exp``, ``uniform``, ...) in interactive mode — their ``endTime``
   stays ``inf`` and ``stepForward`` cannot advance the clock through
   them. The engine pre-samples each non-planned non-deterministic
   transition (``_autoplan_nondeterministic``) before every step, using
   its own ``random.Random`` instance so a ``rng_seed`` constructor
   argument fully reproduces a run.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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

    def __init__(self, system: Any, rng_seed: Optional[int] = None) -> None:
        self.system = system
        self.history: List[FiredEvent] = []
        self.var_initial: Dict[str, Any] = {}
        # Engine-local RNG for sampling non-deterministic occurrence laws so
        # a given ``rng_seed`` deterministically reproduces a run independent
        # from the global ``random`` state and from PyCATSHOO's own RNG.
        self._rng = random.Random(rng_seed)
        self._rng_seed = rng_seed

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
        """Restart the simulation from t=0.

        Re-seeds the engine RNG so two consecutive ``reset()`` calls (or a
        ``reset`` after some steps) reproduce the same sequence of sampled
        non-deterministic transitions when ``rng_seed`` was provided.
        """
        self.stop()
        self._rng = random.Random(self._rng_seed)
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
    # Internals
    # ------------------------------------------------------------------
    def _step_and_capture(self) -> FiredEvent:
        if self.history:
            vars_before = self.history[-1].vars_after
        else:
            # First step: the snapshot taken right before stepForward is the
            # post-startInteractive state, not the declared initials.
            vars_before = snapshot_vars(self.system)
        # Sample non-deterministic transitions before stepping; otherwise
        # PyCATSHOO leaves their ``endTime`` at ``inf`` and ``stepForward``
        # cannot advance the clock.
        self._autoplan_nondeterministic()
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

    def _autoplan_nondeterministic(self) -> None:
        """Pre-sample every active non-deterministic transition.

        PyCATSHOO's interactive ``stepForward`` does not sample exponential
        / uniform laws — their ``_bkd.endTime()`` stays ``inf`` until the
        user explicitly calls ``setTransPlanning``. For each such transition
        whose planned end-time is still ``inf``, sample a delay from its
        occurrence law and plan it at ``current_time + delay``.

        Currently supports ``ExpOccDistribution`` (``exp(rate)``). Other
        non-deterministic laws are skipped silently — the user can still
        plan them manually via the ``p`` re-plan modal.
        """
        active = self.system.isimu_active_transitions()
        if not active:
            return
        now = float(self.system.currentTime())
        any_planned = False
        for trans in active:
            if trans.occ_law.is_occ_time_deterministic:
                continue
            try:
                end_time = float(trans._bkd.endTime())
            except Exception:
                continue
            if end_time != float("inf"):
                # Already planned (or sampled in a previous step); leave it.
                continue
            sample = self._sample_delay(trans.occ_law)
            if sample is None:
                continue
            self.system.setTransPlanning(trans._bkd, now + sample, 0)
            any_planned = True
        if any_planned:
            self.system.updatePlanningInt()

    def _sample_delay(self, occ_law: Any) -> Optional[float]:
        """Sample a positive delay for ``occ_law``. Returns ``None`` for
        unsupported laws."""
        cls_name = type(occ_law).__name__
        if cls_name == "ExpOccDistribution":
            rate = float(occ_law.rate)
            if rate <= 0.0:
                return None
            return self._rng.expovariate(rate)
        # Future: UniformOccDistribution, etc.
        return None
