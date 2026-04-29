"""Tests for the exponential-law auto-sampling in :class:`ISimuEngine`.

PyCATSHOO does not sample non-deterministic occurrence laws (``exp``,
``uniform``, …) in interactive mode — their ``endTime`` stays ``inf`` and
``stepForward`` cannot advance the clock. The engine therefore pre-samples
them via ``random.Random(rng_seed).expovariate`` before each ``stepForward``.

These tests live in a **separate module** from ``test_engine.py`` so each
test can build and tear down its own ``PycSystem`` (PyCATSHOO is a
process-level singleton — sharing a module-scope fixture with the
``_IsimuTestComp`` system from ``conftest.py`` would collide).
"""

from __future__ import annotations

import Pycatshoo as Pyc

import cod3s
from cod3s.pycatshoo.isimu.engine import ISimuEngine


class _ExpComp(cod3s.PycComponent):
    """Component whose ``working`` flag is flipped by an exp ObjFM."""

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)


def _build_exp_system(name: str):
    system = cod3s.PycSystem(name=name)
    system.add_component(name="C1", cls="_ExpComp")
    system.add_component(
        cls="ObjFMExp",
        fm_name="fm",
        targets=["C1"],
        behaviour="internal",
        failure_effects={"working": False},
        repair_effects={"working": True},
        failure_param=0.1,
        repair_param=0.5,
    )
    return system


def test_engine_advances_through_exp_laws() -> None:
    """Without auto-sampling, ``stepForward`` cannot advance through an exp
    transition — its ``endTime`` stays ``inf``. The engine must therefore
    sample non-deterministic laws before stepping."""
    system = _build_exp_system("ExpAdvance")
    try:
        engine = ISimuEngine(system, rng_seed=0)
        engine.start()
        evt = engine.step_forward()
        assert evt.fired_at != float("inf"), evt.fired_at
        # The transition fired and applied its effect.
        assert system.comp["C1"].working.value() is False
    finally:
        cod3s.terminate_session()


def test_engine_rng_seed_is_reproducible() -> None:
    """Two engines built with the same ``rng_seed`` produce the same
    sequence of firing times for non-deterministic transitions."""

    def trace(seed: int) -> list:
        system = _build_exp_system(f"ExpRepro{seed}")
        try:
            engine = ISimuEngine(system, rng_seed=seed)
            engine.start()
            return [engine.step_forward().fired_at for _ in range(4)]
        finally:
            cod3s.terminate_session()

    assert trace(7) == trace(7)
    assert trace(7) != trace(99)


def test_engine_reset_reseeds_rng() -> None:
    """``reset()`` must re-seed the RNG so a reset+rerun reproduces the
    original sequence."""
    system = _build_exp_system("ExpReseed")
    try:
        engine = ISimuEngine(system, rng_seed=42)
        engine.start()
        first = [engine.step_forward().fired_at for _ in range(3)]

        engine.reset()
        second = [engine.step_forward().fired_at for _ in range(3)]
    finally:
        cod3s.terminate_session()

    assert first == second
