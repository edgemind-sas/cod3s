"""Regression test for T12: mutable default args.

``PycComponent.__init__`` and ``ObjFM.__init__`` used to declare
parameters like ``metadata={}``, ``failure_effects={}``, ``targets=[]``
as positional defaults. With Python's evaluate-once-at-def-time
semantics, two instances built without explicitly passing these
arguments would share the *same* mutable object — mutating one would
ripple to the other. ``copy.deepcopy(metadata)`` masked the issue in
some places, but the pattern remained a footgun for future refactors.

This test sets up two independent ObjFM instances, mutates the failure
effects dict on one, and verifies the other is unaffected.
"""

import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow  # noqa: F401


@pytest.fixture(autouse=True)
def cleanup():
    yield
    cod3s.terminate_session()


def test_two_objfms_with_default_failure_effects_are_independent():
    """Two ObjFM built without passing ``failure_effects`` must NOT share
    state. Pre-T12, both held a reference to the same ``{}`` dict
    declared at function-def time."""
    system = PycSystem(name="SysMutDefault")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")
    system.add_component(name="C1", cls="ObjFlow")
    system.add_component(name="C2", cls="ObjFlow")

    fm1 = system.add_component(
        cls="ObjFMExp",
        fm_name="frun1",
        targets=["C1"],
        behaviour="external",
        failure_param=0.1,
        repair_param=0.1,
    )
    fm2 = system.add_component(
        cls="ObjFMExp",
        fm_name="frun2",
        targets=["C2"],
        behaviour="external",
        failure_param=0.1,
        repair_param=0.1,
    )

    # Each instance must have its own ``failure_effects`` dict.
    assert fm1.failure_effects is not fm2.failure_effects
    # Mutating one must not affect the other.
    fm1.failure_effects["spurious"] = "leak"
    assert "spurious" not in fm2.failure_effects


def test_pyccomponent_default_metadata_is_independent():
    """Two ``PycComponent`` built without passing ``metadata`` must have
    distinct dicts."""
    system = PycSystem(name="SysMutMeta")
    c1 = system.add_component(name="C1", cls="PycComponent")
    c2 = system.add_component(name="C2", cls="PycComponent")
    assert c1.metadata is not c2.metadata
    c1.metadata["key"] = "value"
    assert "key" not in c2.metadata
