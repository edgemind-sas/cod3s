"""Shared builder for the ``objfm_trigger_02/03/05`` demo scenarios.

The three demo folders all exercise the *same* underlying system —
two ``Equipment`` targets with an ``ObjFMDelay`` in
``external_rep_indep`` mode, ``cc_12`` common-cause at ``ttf=10``,
per-target self-repair at ``ttr=5``. Only the system *name* and the
*test sequence* documented in each demo's docstring differ.

This module factors the common build code so the three demo files
become docstring-only walkthroughs that delegate to
:func:`build_system`.

Layout (identical across the three demos):

==========  ==========================  ============================
Component   Variable                    Notes
==========  ==========================  ============================
C1, C2      working (bool, init True)   Reset by the rep state of
                                        the per-target automaton.
fm_cc       (no variable of its own)    ObjFM driving cc_12 trigger.
==========  ==========================  ============================
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s


class Equipment(cod3s.PycComponent):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


def build_system(system_name: str) -> cod3s.PycSystem:
    """Build the dual-target ``cc_12`` trigger system.

    The ``system_name`` parameter is the only thing the three scenario
    folders override: it lets the cod3s-isimu header show which demo
    is loaded.
    """
    system = cod3s.PycSystem(name=system_name)
    for n in ("C1", "C2"):
        system.add_component(name=n, cls="Equipment")
    system.add_component(
        cls="ObjFMDelay",
        fm_name="fm_cc",
        targets=["C1", "C2"],
        behaviour="external_rep_indep",
        failure_effects={"working": False},
        # failure_param[i] is the order-(i+1) ttf.
        # cc_1 / cc_2 (order 1) parked at 99999 so they never reach the
        # fireable window; only cc_12 (order 2) fires at ttf=10.
        failure_param=[(99999.0,), (10.0,)],
        # repair_param[0] (order 1) is what targets use for self-repair.
        # repair_param[1] is irrelevant — ObjFM rep is delay(0) in
        # external_rep_indep regardless of the user's value.
        repair_param=[(5.0,), (99999.0,)],
    )
    return system
