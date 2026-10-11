"""What an ``ObjMode2S`` will build, computed without building it.

A caller that must bound or announce the size of a model before
constructing it (a combinatorics cap, a table showing the analyst what a
run will cost) needs the number of automata and transitions a targeted
mode creates. Re-deriving it outside cod3s means mirroring rules that
live here: the per-law activity rule, the explicit ``None`` inactive-order
marker, ``drop_inactive_automata``, the inst re-arm transitions and the
mirror automata of the external behaviours. :func:`mode_footprint` is
that count, owned by the engine that builds the automata, and
``tests/pyc_obj/obj_mode2s/test_mode2s_footprint.py`` compares it with
systems actually built.

What one targeted mode builds, for ``n`` targets:

* for every CC order ``k`` that is kept, one automaton per combination
  of ``k`` targets among ``n``, i.e. ``C(n, k)`` automata, each with
  - 2 transitions (occ, not_occ),
  - plus 1 re-arm transition per ``inst`` direction whose draw is not
    certain (probability other than exactly 1);
* an order is dropped (no automaton) when ``drop_inactive_automata`` is
  on and BOTH directions are inactive for it: ``None`` marker, or a value
  the law judges inactive (``exp`` rate 0; ``delay`` and ``inst`` are
  active at 0);
* for ``external`` and ``external_rep_indep``, one mirror automaton on
  each target, with 2 transitions, whatever the orders kept.

Scope: the native path, where both directions carry a ``ModeLaw`` spec.
The self-hosted mode (``targets=None``) and the façades whose laws come
from hooks are outside it. The count describes a mode the constructor
accepts; the constructor's refusals (an order marked ``None`` on one
direction only, inst on the return direction with several targets, a
certain inst/inst livelock, an inst return law under
``external_rep_indep``) stay the constructor's.
"""

from __future__ import annotations

import dataclasses
import math
import typing

from .mode_law import ModeLawInst, parse_mode_law

#: Behaviours that put a mirror automaton on every target.
_MIRRORED_BEHAVIOURS = ("external", "external_rep_indep")
_BEHAVIOURS = ("internal",) + _MIRRORED_BEHAVIOURS

#: Transitions of the two-state automata (mode combination, mirror).
_TWO_STATE_TRANSITIONS = 2


@dataclasses.dataclass(frozen=True)
class OrderFootprint:
    """What one CC order builds: ``combinations`` automata (0 if dropped)."""

    order: int
    combinations: int
    transitions_per_combination: int

    @property
    def automata(self) -> int:
        return self.combinations

    @property
    def transitions(self) -> int:
        return self.combinations * self.transitions_per_combination


@dataclasses.dataclass(frozen=True)
class ModeFootprint:
    """Automata and transitions a targeted ``ObjMode2S`` builds.

    ``by_order`` holds every order from 1 to the number of targets, a
    dropped order with ``combinations == 0``. The mirror automata of the
    external behaviours belong to the mode, not to an order.
    """

    behaviour: str
    n_targets: int
    by_order: typing.Tuple[OrderFootprint, ...]
    mirror_automata: int
    mirror_transitions: int

    @property
    def mode_automata(self) -> int:
        return sum(o.automata for o in self.by_order)

    @property
    def mode_transitions(self) -> int:
        return sum(o.transitions for o in self.by_order)

    @property
    def automata(self) -> int:
        return self.mode_automata + self.mirror_automata

    @property
    def transitions(self) -> int:
        return self.mode_transitions + self.mirror_transitions

    def order(self, k: int) -> OrderFootprint:
        """The footprint of CC order ``k`` (1-based)."""
        return self.by_order[k - 1]


def _direction_values(
    law: typing.Any, params: typing.Any, n_targets: int, direction: str
) -> list:
    """Per-order values of one direction, by the constructor's rules.

    Explicit ``*_param`` values win; otherwise the law vector, of strict
    length ``n_targets`` (a scalar only for a single target). A tuple
    entry is reduced to its first element, the one the activity rule and
    the certain-draw rule read.
    """
    if params is not None and not isinstance(params, list):
        params = [params]
    if params:
        values = list(params)
    else:
        values = law.values()
    if len(values) != n_targets:
        raise ValueError(
            f"{direction}: {len(values)} per-order value(s) for {n_targets} "
            f"target(s) (strict length, as the ObjMode2S constructor demands)."
        )
    return [v[0] if isinstance(v, tuple) else v for v in values]


def _rearm(law: typing.Any, value: typing.Any) -> int:
    """1 when an inst direction carries a re-arm transition at ``value``."""
    if not isinstance(law, ModeLawInst):
        return 0
    # ``None`` builds its variable at 0.0, a two-branch draw.
    return 0 if value is not None and float(value) == 1.0 else 1


def mode_footprint(
    n_targets: int,
    *,
    occ_law: typing.Any,
    not_occ_law: typing.Any,
    behaviour: str = "internal",
    occ_param: typing.Any = None,
    not_occ_param: typing.Any = None,
    drop_inactive_automata: bool = True,
) -> ModeFootprint:
    """Automata and transitions ``ObjMode2S`` builds for these arguments.

    The arguments are the constructor's own (laws as ``ModeLaw`` specs or
    their dict form, optional explicit per-order ``*_param`` vectors),
    with ``n_targets`` in place of the target names. Pure: no system, no
    PyCATSHOO object is created.
    """
    if behaviour not in _BEHAVIOURS:
        raise ValueError(f"behaviour must be one of {_BEHAVIOURS}, got {behaviour!r}")
    if not isinstance(n_targets, int) or n_targets < 0:
        raise ValueError(f"n_targets must be a non-negative integer, got {n_targets!r}")
    if occ_law is None or not_occ_law is None:
        raise ValueError(
            "mode_footprint covers the native path only: both occ_law and "
            "not_occ_law must be given as ModeLaw specs."
        )
    occ = parse_mode_law(occ_law, what="occ_law")
    not_occ = parse_mode_law(not_occ_law, what="not_occ_law")
    if n_targets == 0:
        return ModeFootprint(behaviour, 0, (), 0, 0)

    occ_values = _direction_values(occ, occ_param, n_targets, "occ")
    not_occ_values = _direction_values(not_occ, not_occ_param, n_targets, "not_occ")

    orders = []
    for k in range(1, n_targets + 1):
        occ_value, not_occ_value = occ_values[k - 1], not_occ_values[k - 1]
        dropped = (
            drop_inactive_automata
            and not occ.is_active_value(occ_value)
            and not not_occ.is_active_value(not_occ_value)
        )
        orders.append(
            OrderFootprint(
                order=k,
                combinations=0 if dropped else math.comb(n_targets, k),
                transitions_per_combination=_TWO_STATE_TRANSITIONS
                + _rearm(occ, occ_value)
                + _rearm(not_occ, not_occ_value),
            )
        )

    mirrored = behaviour in _MIRRORED_BEHAVIOURS
    return ModeFootprint(
        behaviour=behaviour,
        n_targets=n_targets,
        by_order=tuple(orders),
        mirror_automata=n_targets if mirrored else 0,
        mirror_transitions=_TWO_STATE_TRANSITIONS * n_targets if mirrored else 0,
    )
