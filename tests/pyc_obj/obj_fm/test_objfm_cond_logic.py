"""Regression test for the C1 bug.

``ObjFM.__init__`` used to overwrite ``self.cond_outer_logic`` with the
value of ``cond_inner_logic`` (typo on the right-hand side at
``cod3s/pycatshoo/component.py``), making the ``cond_outer_logic``
constructor argument silently dead. Two condition logics that differ
(e.g. ``any`` vs ``all``) would behave identically.
"""

import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow  # noqa: F401  (registers the subclass)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    cod3s.terminate_session()


def test_cond_inner_and_outer_logic_are_independent():
    """``cond_inner_logic`` and ``cond_outer_logic`` must be preserved
    as distinct callables on the ObjFM instance."""
    system = PycSystem(name="SysCondLogic")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")

    fm = system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        behaviour="external",
        failure_param=0.1,
        repair_param=0.1,
        cond_inner_logic=any,
        cond_outer_logic=all,
    )

    assert fm.cond_inner_logic is any
    assert fm.cond_outer_logic is all
