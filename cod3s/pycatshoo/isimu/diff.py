"""Variable snapshot and diff helpers.

The interactive simulator displays three colorings of every variable:

* neutral when its current value matches its declared initial value,
* "differs from initial" (e.g. orange) when current ≠ initial but the variable
  did not change at the last step,
* "just changed" (e.g. bold red) when the value changed at the last step.

These distinctions require two snapshots — one frozen at start (the declared
initial values from PyCATSHOO's ``initValue()``) and one captured before/after
each step (the current ``value()``). The helpers in this module produce both.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple


def snapshot_vars(system: Any) -> Dict[str, Any]:
    """Capture the current value of every backend variable in ``system.comp``.

    Keys are namespaced as ``"{component_name}.{variable_basename}"`` so a
    variable from component ``pump1`` named ``working`` becomes
    ``"pump1.working"``. Calling ``var.value()`` reads the live PyCATSHOO state.
    """
    return {
        f"{comp_name}.{var.basename()}": var.value()
        for comp_name, comp in system.comp.items()
        for var in comp.variables()
    }


def snapshot_initials(system: Any) -> Dict[str, Any]:
    """Capture the declared initial value of every backend variable.

    Uses PyCATSHOO's ``var.initValue()`` so the snapshot reflects the model
    declaration, independent of any t=0 transitions that may have already
    fired during ``startInteractive``.
    """
    return {
        f"{comp_name}.{var.basename()}": var.initValue()
        for comp_name, comp in system.comp.items()
        for var in comp.variables()
    }


def diff_snapshots(
    before: Dict[str, Any], after: Dict[str, Any]
) -> Dict[str, Tuple[Any, Any]]:
    """Return ``{var_name: (before_value, after_value)}`` for variables whose
    value changed between the two snapshots.

    Variables only present in ``after`` and absent from ``before`` are reported
    as having moved from ``None`` to their new value.
    """
    return {
        name: (before.get(name), value)
        for name, value in after.items()
        if before.get(name) != value
    }
