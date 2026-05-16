"""Multi-ObjFM external on a single target.

Without name-prefixed states/transitions on the target automaton, two
ObjFM in ``external`` mode (or ``external_rep_indep``) on the same
target collide: each ObjFM tries to create states named ``rep`` / ``occ``
and transitions named ``rep`` / ``occ`` on the same component, which
PyCATSHOO rejects at build time with::

    PycException: [E]L'état rep existe déjà dans le composant C1

The fix prefixes the target automaton's states and transitions with the
ObjFM's ``fm_name`` so each ObjFM gets its own namespace on every
target.

The tests below cover:

* Building two ObjFM ``external`` on the same target — must succeed.
* The events emitted in a sequence carry the prefixed names so each
  ObjFM is identifiable from the trace alone.
"""

import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow  # noqa: F401  (registers the subclass)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    cod3s.terminate_session()


def test_two_external_objfm_on_same_target_can_be_built():
    """Two ObjFM in external mode on the same target must coexist
    without collision."""
    system = PycSystem(name="SysMultiExternal")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")
    system.add_component(name="C1", cls="ObjFlow")
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun_1",
        targets=["C1"],
        behaviour="external",
        failure_param=0.1,
        repair_param=0.1,
    )
    # The 2nd ObjFM on the same target must NOT collide with the 1st.
    system.add_component(
        cls="ObjFMExp",
        fm_name="frun_2",
        targets=["C1"],
        behaviour="external",
        failure_param=0.05,
        repair_param=0.05,
    )

    # Two ObjFM created, each with its own automaton on C1 (PyCATSHOO's
    # ``automata()`` enumerates only the component-level ones — the
    # target has both ``frun_1`` and ``frun_2`` declared).
    c1 = system.comp["C1"]
    aut_names = {a.basename() for a in c1.automata()}
    assert "frun_1" in aut_names
    assert "frun_2" in aut_names


def test_two_external_objfm_emit_disambiguated_events():
    """Events on the target must carry the ObjFM name so the two
    automata are distinguishable in the sequence trace."""
    system = PycSystem(name="SysMultiExternalEvents")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")
    system.add_component(name="C1", cls="ObjFlow")
    system.add_component(
        cls="ObjFMExp",
        fm_name="fm_a",
        targets=["C1"],
        behaviour="external",
        failure_param=0.1,
        repair_param=0.1,
    )
    system.add_component(
        cls="ObjFMExp",
        fm_name="fm_b",
        targets=["C1"],
        behaviour="external",
        failure_param=0.05,
        repair_param=0.05,
    )

    # Inspect the target automata directly. The fix prefixes states and
    # transitions on each target automaton with the ObjFM's ``fm_name``
    # so the two automata coexist with disjoint namespaces.
    c1 = system.comp["C1"]
    aut_fm_a = c1.automata_d["fm_a"]
    aut_fm_b = c1.automata_d["fm_b"]

    fm_a_states = {st.name for st in aut_fm_a.states}
    fm_b_states = {st.name for st in aut_fm_b.states}
    assert fm_a_states == {"fm_a__rep", "fm_a__occ"}, fm_a_states
    assert fm_b_states == {"fm_b__rep", "fm_b__occ"}, fm_b_states

    fm_a_trans = {tr.name for tr in aut_fm_a.transitions}
    fm_b_trans = {tr.name for tr in aut_fm_b.transitions}
    assert fm_a_trans == {"fm_a__rep", "fm_a__occ"}, fm_a_trans
    assert fm_b_trans == {"fm_b__rep", "fm_b__occ"}, fm_b_trans

    # And the namespaces really are disjoint — no bare ``rep`` / ``occ``
    # remains as a colliding state name on the component.
    assert "rep" not in fm_a_states
    assert "occ" not in fm_a_states
