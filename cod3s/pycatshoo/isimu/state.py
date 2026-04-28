"""Immutable view of the simulator state shared across TUI panels.

The Textual panels do not poll :class:`ISimuEngine` directly — they consume an
:class:`ISimuState` snapshot built once per UI tick. This decouples rendering
from the live simulator and makes panels trivially testable with synthetic
states (no PyCATSHOO required for layout/rendering tests).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ISimuState:
    """Snapshot of everything a panel needs to render once."""

    current_time: float = 0.0
    fireable: List[Any] = field(default_factory=list)
    history: List[Any] = field(default_factory=list)
    var_initial: Dict[str, Any] = field(default_factory=dict)
    var_current: Dict[str, Any] = field(default_factory=dict)
    var_previous: Dict[str, Any] = field(default_factory=dict)
    last_fired_at: Optional[float] = None
    last_fired_transitions: List[Any] = field(default_factory=list)

    @classmethod
    def from_engine(cls, engine: Any) -> "ISimuState":
        """Build a snapshot from the live :class:`ISimuEngine`."""
        last = engine.history[-1] if engine.history else None
        return cls(
            current_time=engine.current_time,
            fireable=list(engine.fireable()),
            history=list(engine.history),
            var_initial=dict(engine.var_initial),
            var_current=dict(engine.vars_current),
            var_previous=dict(engine.vars_previous),
            last_fired_at=last.fired_at if last is not None else None,
            last_fired_transitions=(list(last.transitions) if last is not None else []),
        )

    # ------------------------------------------------------------------
    # Derived views used by panels
    # ------------------------------------------------------------------
    def fireable_only(self) -> List[Any]:
        """Return ``fireable`` with ``None`` slots stripped."""
        return [t for t in self.fireable if t is not None]

    def changed_at_last_step(self) -> Dict[str, Any]:
        """Variables whose value changed at the last step.

        Returns a dict ``{var_name: current_value}``; the previous value can
        be looked up in :attr:`var_previous`.
        """
        return {
            name: value
            for name, value in self.var_current.items()
            if self.var_previous.get(name) != value
        }

    def differs_from_initial(self) -> Dict[str, Any]:
        """Variables whose current value differs from the declared initial."""
        return {
            name: value
            for name, value in self.var_current.items()
            if self.var_initial.get(name) != value
        }
