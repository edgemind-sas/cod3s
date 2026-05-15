"""Regression test for the C1 bug.

``ObjFM.__init__`` used to overwrite ``self.cond_outer_logic`` with the
value of ``cond_inner_logic`` (typo on the right-hand side at
``cod3s/pycatshoo/component.py``), making the ``cond_outer_logic``
constructor argument silently dead. Two condition logics that differ
(e.g. ``any`` vs ``all``) would behave identically.

The first test asserts the bare attribute identity — enough to catch the
literal typo. The second test exercises the *behaviour*: ``any`` and
``all`` give different truth values on a mixed input, so swapping them
produces an observable divergence. The third test verifies that the
default values (``inner=all``, ``outer=any``) match what the docstring
of ``ObjFM.__init__`` promises.
"""

import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow  # noqa: F401  (registers the subclass)


# Each test in this module builds its own PycSystem at function scope, so
# the module-scoped autouse teardown in ``conftest.py`` is too coarse.
# Override it with a function-scoped finaliser instead.
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


def test_inner_and_outer_logic_produce_different_truth_values():
    """A behavioural assertion: ``any`` and ``all`` disagree on mixed
    inputs, so they MUST be stored independently. Pre-fix, both attrs
    held the same callable and this divergence would not be reachable.
    """
    system = PycSystem(name="SysCondLogicFn")
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

    mixed = [True, False]
    # Inner = any → True ; outer = all → False. They MUST disagree.
    assert fm.cond_inner_logic(mixed) is True
    assert fm.cond_outer_logic(mixed) is False
    # Sanity: if the bug were back (both bound to `any`), both would be True.
    assert fm.cond_inner_logic(mixed) != fm.cond_outer_logic(mixed)


def test_default_inner_logic_is_all_and_outer_is_any():
    """``ObjFM.__init__`` defaults documented at component.py:1198-1199:
    ``cond_inner_logic=all, cond_outer_logic=any``. Lock that contract.
    """
    system = PycSystem(name="SysCondLogicDefault")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")

    fm = system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1"],
        behaviour="external",
        failure_param=0.1,
        repair_param=0.1,
        # no override — must take the defaults
    )

    assert fm.cond_inner_logic is all
    assert fm.cond_outer_logic is any
