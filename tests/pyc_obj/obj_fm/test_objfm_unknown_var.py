"""Regression test for the C2 bug.

When building an external (or external_rep_indep) ObjFM, a typo in
``failure_effects`` or ``repair_effects`` keys used to be silently
swallowed by ``_create_target_automaton`` (the unresolved variable was
skipped via ``continue``). The simulation then ran producing wrong
reliability numbers with no warning at all.

The fix raises a ``ValueError`` at build time so the misspelled variable
is surfaced immediately. ``ValueError`` reads better than ``KeyError`` in
the traceback (Python's ``KeyError`` repr escapes the message string),
and the semantics match: the dict-lookup succeeded, the *value* is
wrong.
"""

import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow  # noqa: F401  (registers the subclass)


# Each test builds its own PycSystem at function scope, so the
# module-scoped autouse teardown in ``conftest.py`` is too coarse.
# Override it with a function-scoped finaliser instead.
@pytest.fixture(autouse=True)
def cleanup():
    yield
    cod3s.terminate_session()


def test_unknown_failure_effect_var_raises_valueerror():
    """A typo in ``failure_effects`` must raise, not be silently dropped."""
    system = PycSystem(name="SysUnknownFailEffect")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")

    with pytest.raises(ValueError, match="flow_availabel_out"):
        system.add_component(
            cls="ObjFMExp",
            fm_name="frun",
            targets=["C1"],
            behaviour="external",
            failure_param=0.1,
            repair_param=0.1,
            failure_effects={"flow_availabel_out": False},  # typo on purpose
        )


def test_unknown_repair_effect_var_raises_valueerror():
    """A typo in ``repair_effects`` must raise too."""
    system = PycSystem(name="SysUnknownRepEffect")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")

    with pytest.raises(ValueError, match="flwo_available_out"):
        system.add_component(
            cls="ObjFMExp",
            fm_name="frun",
            targets=["C1"],
            behaviour="external_rep_indep",
            failure_param=0.1,
            repair_param=0.1,
            failure_effects={"flow_available_out": False},
            repair_effects={"flwo_available_out": True},  # typo on purpose
        )


def test_error_message_carries_kind_and_target_and_fm_name():
    """The error message must include the ``kind`` (failure/repair), the
    target name, and the ObjFM name — they are what the user needs to
    locate the typo in a multi-target, multi-FM system.
    """
    system = PycSystem(name="SysMsgFmt")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")
    system.add_component(name="C_A", cls="ObjFlow")

    with pytest.raises(ValueError) as exc_info:
        system.add_component(
            cls="ObjFMExp",
            fm_name="my_fm",
            targets=["C_A"],
            behaviour="external",
            failure_param=0.1,
            repair_param=0.1,
            failure_effects={"nonexistent": True},
        )
    msg = str(exc_info.value)
    assert "failure_effects" in msg
    assert "nonexistent" in msg
    assert "C_A" in msg
    assert "my_fm" in msg
