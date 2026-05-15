"""Regression test for the C2 bug.

When building an external (or external_rep_indep) ObjFM, a typo in
``failure_effects`` or ``repair_effects`` keys used to be silently
swallowed by ``_create_target_automaton`` (the unresolved variable was
skipped via ``continue``). The simulation then ran producing wrong
reliability numbers with no warning at all.

The fix raises a ``KeyError`` at build time so the misspelled variable
is surfaced immediately.
"""

import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow  # noqa: F401  (registers the subclass)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    cod3s.terminate_session()


def test_unknown_failure_effect_var_raises_keyerror():
    """A typo in ``failure_effects`` must raise, not be silently dropped."""
    system = PycSystem(name="SysUnknownFailEffect")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")

    with pytest.raises(KeyError, match="flow_availabel_out"):
        system.add_component(
            cls="ObjFMExp",
            fm_name="frun",
            targets=["C1"],
            behaviour="external",
            failure_param=0.1,
            repair_param=0.1,
            failure_effects={"flow_availabel_out": False},  # typo on purpose
        )


def test_unknown_repair_effect_var_raises_keyerror():
    """A typo in ``repair_effects`` must raise too."""
    system = PycSystem(name="SysUnknownRepEffect")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    system.add_component(name="C1", cls="ObjFlow")

    with pytest.raises(KeyError, match="flwo_available_out"):
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
