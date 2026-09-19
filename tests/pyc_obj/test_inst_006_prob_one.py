"""An inst draw of probability 1 must build and run: certainty is a legitimate law.

Pycatshoo refuses ``p == 1`` on a BRANCHING inst law (2+ targets): the law check
fails with "Il y a plus d'un parametre egal a 1" and ``simulate()`` raises a bare
``PycException``. The same law on a SINGLE target is accepted -- it is what the
re-arm transition of the inst machinery already uses.

"Fails with certainty on every demand" is the most natural on-demand mode there
is (a certain detection, a certain trip), ``ModeLawInst`` validates ``p == 1``,
and the engine must therefore build it rather than hand the analyst an
unexplained crash mid-run.
"""

import pytest

from cod3s import terminate_session
from cod3s.pycatshoo.component import ObjFMInst
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem


@pytest.fixture
def system_with_certain_on_demand_mode():
    """One target component, one on-demand mode whose demand always holds."""
    system = PycSystem(name="certain_inst")
    system.add_component(name="C", cls="PycComponent")
    yield system
    terminate_session()


def _add_mode(system, gamma):
    return system.add_component(
        cls="ObjFMInst",
        fm_name="m",
        targets=["C"],
        failure_param=[(gamma,)],
        repair_param=[(0.0,)],
    )


@pytest.mark.parametrize("gamma", [0.5, 0.999999, 1.0])
def test_inst_draw_simulates_whatever_the_probability(
    system_with_certain_on_demand_mode, gamma
):
    """``gamma == 1`` must simulate exactly like any other probability."""
    system = system_with_certain_on_demand_mode
    _add_mode(system, gamma)
    system.simulate(PycMCSimulationParam(nb_runs=5, schedule=[1.0]))


def test_certain_draw_reaches_the_failed_state(system_with_certain_on_demand_mode):
    """``gamma == 1`` on a demand that holds must occur in EVERY sequence."""
    system = system_with_certain_on_demand_mode
    _add_mode(system, 1.0)
    system.add_indicator_state(component="C__m", state="occ", stats=["mean"], name="occ")
    system.simulate(PycMCSimulationParam(nb_runs=20, schedule=[1.0]))
    indic = system.indicators["occ_occ"]
    assert float(indic.values["values"].iloc[-1]) == pytest.approx(1.0)


def test_certain_direction_drops_its_parked_state():
    """A certain direction builds no parked micro-state: nothing parks in it.

    Pins the structural consequence of the single-target form. The
    uncertain direction keeps its own parked state, so the two are
    independent.
    """
    from cod3s.pycatshoo.component import ObjMode2S
    from cod3s.pycatshoo.system import PycSystem

    system = PycSystem(name="certain_structure")
    system.add_component(name="E", cls="PycComponent")
    try:
        mode = ObjMode2S(
            mode_name="m",
            targets=["E"],
            occ_law={"cls": "inst", "prob": 1},
            not_occ_law={"cls": "inst", "prob": 0.5},
            occ_cond=lambda: True,
            not_occ_cond=lambda: False,
        )
        # The parked micro-state of a direction splits its SOURCE state:
        # "not_occ_star" would be the certain occ direction's (absent),
        # "occ_star" is the uncertain return direction's (present).
        states = {st.name for st in mode.automata_d["m"].states}
        assert states == {"not_occ", "occ", "occ_star"}, states
    finally:
        terminate_session()
