"""Test fixtures for the interactive simulator.

PyCATSHOO is a process-level singleton: only one ``PycSystem`` may exist at a
time, and ``terminate_session()`` must be called before instantiating a new
one. The fixtures below build a single small system per *module* (so multiple
test modules in ``tests/isimu/`` don't fight) and tear it down on module exit.

Tests that mutate the simulator state should call ``engine.start()`` (or
``engine.reset()``) at the start of each function to ensure deterministic
behavior — ``start()`` is idempotent and re-creates the underlying interactive
session.
"""

from __future__ import annotations

import Pycatshoo as Pyc
import pytest

from cod3s import terminate_session
from cod3s.pycatshoo.automaton import PycAutomaton
from cod3s.pycatshoo.component import PycComponent
from cod3s.pycatshoo.system import PycSystem


class _IsimuTestComp(PycComponent):
    """Component with two backend variables for diff/snapshot tests."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.addVariable("flag", Pyc.TVarType.t_bool, False)
        self.addVariable("counter", Pyc.TVarType.t_int, 0)


@pytest.fixture(scope="module")
def small_system():
    """A two-component PycSystem with two deterministic ``delay(1.0)``
    transitions.

    Both transitions share ``occ_law=delay(1.0)`` so PyCATSHOO plans them at
    the same ``end_time``. This is the canonical "fires together" scenario the
    TUI's ★ marker is designed for.

    Layout:
      A : _IsimuTestComp(name=A)  vars=[flag, counter]  aut_A: ok --delay(1)--> ko
      B : _IsimuTestComp(name=B)  vars=[flag, counter]  aut_B: ok --delay(1)--> ko
    """
    system = PycSystem(name="ISimuTest")

    for comp_name in ("A", "B"):
        comp = _IsimuTestComp(name=comp_name)
        aut = PycAutomaton(
            name=f"aut_{comp_name}",
            states=["ok", "ko"],
            init_state="ok",
            transitions=[
                {
                    "name": "fail",
                    "source": "ok",
                    "target": "ko",
                    "is_interruptible": False,
                    "occ_law": {"cls": "delay", "time": 1.0},
                },
            ],
        )
        aut.update_bkd(comp)

    yield system
    terminate_session()
