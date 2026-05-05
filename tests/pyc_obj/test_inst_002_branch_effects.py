"""Per-branch effects applied via state-entry sensitive methods.

Each branch declares its own ``effects`` dict (key decision #4 of brainstorm
2026-05-05). After the inst transition fires and the engine has entered the
target state, the branch's effects are applied to the component's variables.

This test relies on a deterministic state_index pick via ``isimu_set_transition``
to avoid coupling the assertions to Pycatshoo's RNG.
"""

import Pycatshoo as pyc
import pytest

from cod3s import terminate_session
from cod3s.pycatshoo.automaton import PycAutomaton
from cod3s.pycatshoo.system import PycSystem


@pytest.fixture
def system_with_branch_effects():
    """A 3-branch inst transition. Each branch sets a different `severity`."""
    system = PycSystem(name="VS")
    comp = system.add_component(name="V", cls="PycComponent")

    # Add a severity variable to observe the effects.
    severity = comp.addVariable("severity", pyc.TVarType.t_int, 0)
    severity.setReinitialized(False)

    automaton = PycAutomaton(
        name="aut",
        states=["src", "panne_severe", "panne_legere", "ok"],
        init_state="src",
        transitions=[
            {
                "name": "branch",
                "source": "src",
                "target": [
                    {
                        "state": "panne_severe",
                        "prob": 0.05,
                        "effects": {"severity": 3},
                    },
                    {
                        "state": "panne_legere",
                        "prob": 0.10,
                        "effects": {"severity": 1},
                    },
                    {"state": "ok"},  # no effects, prob = 0.85
                ],
            },
        ],
    )
    automaton.update_bkd(comp)

    # Wire per-branch effects (Phase 1 deliverable).
    comp.register_branch_effects(automaton, "branch", automaton.transitions[0].target)

    yield system, automaton, comp
    terminate_session()


def test_branch_severe_applies_severity_3(system_with_branch_effects):
    system, automaton, comp = system_with_branch_effects
    system.isimu_start()

    # Pick branch index 0 (panne_severe).
    system.isimu_set_transition(trans_id=0, state_index=0)
    system.isimu_step_forward()

    severity = comp.variable("severity")
    assert severity.value() == 3
    assert automaton.get_active_state().name == "panne_severe"


def test_branch_legere_applies_severity_1(system_with_branch_effects):
    system, automaton, comp = system_with_branch_effects
    system.isimu_start()

    system.isimu_set_transition(trans_id=0, state_index=1)
    system.isimu_step_forward()

    severity = comp.variable("severity")
    assert severity.value() == 1
    assert automaton.get_active_state().name == "panne_legere"


def test_branch_ok_no_effect(system_with_branch_effects):
    system, automaton, comp = system_with_branch_effects
    system.isimu_start()

    system.isimu_set_transition(trans_id=0, state_index=2)
    system.isimu_step_forward()

    severity = comp.variable("severity")
    # Default value untouched (the `ok` branch has no effects).
    assert severity.value() == 0
    assert automaton.get_active_state().name == "ok"
