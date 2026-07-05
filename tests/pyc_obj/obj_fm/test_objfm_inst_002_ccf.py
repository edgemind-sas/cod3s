"""ObjFMInst x CCF order n — structure and independent draws.

ADR 2026-07-05: CC combinations follow the ObjFM structure unchanged
(2^N - 1 automata, ``failure_param = [gamma_1, ..., gamma_n]``); each
combination automaton draws independently on a shared demand front.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem


class InstEquipment002(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.failed = self.addVariable("failed", Pyc.TVarType.t_bool, False)
        self.failed.setReinitialized(True)


@pytest.fixture(scope="module")
def the_system():
    system = PycSystem(name="SysInst002")
    system.add_component(name="E1", cls="InstEquipment002")
    system.add_component(name="E2", cls="InstEquipment002")
    system.add_component(
        cls="ObjFMInst",
        fm_name="miss",
        targets=["E1", "E2"],
        # Demand from t0 for every combination automaton.
        failure_cond=True,
        failure_effects={"failed": True},
        failure_param=[0.3, 0.2],
        repair_param=[0.1, 0.1],
    )
    yield system


def test_ccf_structure(the_system):
    fm_comp = the_system.comp["EX__miss"]

    # 2^2 - 1 combination automata, underscore-separated cc suffixes.
    assert set(fm_comp.automata_d) == {"miss__cc_1", "miss__cc_2", "miss__cc_1_2"}

    # Per-order gamma / mu parameter variables.
    var_names = {v.basename() for v in fm_comp.variables()}
    assert {"gamma__1_o_2", "gamma__2_o_2", "mu__1_o_2", "mu__2_o_2"} <= var_names

    # Each automaton carries the 3-state shape with prefixed names and
    # its masked draw / re-arm transitions.
    for suffix, gamma in (("__cc_1", 0.3), ("__cc_2", 0.3), ("__cc_1_2", 0.2)):
        aut = fm_comp.automata_d[f"miss{suffix}"]
        assert {s.name for s in aut.states} == {
            f"rep{suffix}",
            f"occ{suffix}",
            f"not_occ{suffix}",
        }
        draw = aut.get_transition_by_name(f"occ{suffix}")
        assert [b.state for b in draw.target] == [
            f"occ{suffix}",
            f"not_occ{suffix}",
        ]
        assert draw.target[0].prob == pytest.approx(gamma)
        assert draw._bkd.monitoredOutStateMask() == f"#occ{suffix}$"
        rearm = aut.get_transition_by_name(f"not_occ{suffix}")
        assert rearm._bkd.monitoredOutStateMask() == "#$^"


def test_independent_draws_on_shared_front(the_system):
    """All combination automata draw on the same front; branches are
    resolved independently (cc_1 -> occ, cc_2 / cc_1_2 -> not_occ)."""
    system = the_system
    system.isimu_start()

    fire = system.isimu_fireable_transitions()
    pending = {t.name: i for i, t in enumerate(fire) if t is not None}
    assert set(pending) == {"occ__cc_1", "occ__cc_2", "occ__cc_1_2"}

    # occ branch is index 0, not_occ branch index 1 (addTarget order).
    system.isimu_set_transition(pending["occ__cc_1"], state_index=0)
    system.isimu_set_transition(pending["occ__cc_2"], state_index=1)
    system.isimu_set_transition(pending["occ__cc_1_2"], state_index=1)
    fired = {t.name for t in system.isimu_step_forward()}
    assert fired == {"occ__cc_1", "occ__cc_2", "occ__cc_1_2"}

    # Only the cc_1 combination landed in occ -> only E1 is failed.
    assert system.comp["E1"].failed.value() is True
    assert system.comp["E2"].failed.value() is False

    fm_comp = system.comp["EX__miss"]
    assert (
        fm_comp.automata_d["miss__cc_1"].get_state_by_name("occ__cc_1")._bkd.isActive()
    )
    assert (
        fm_comp.automata_d["miss__cc_1_2"]
        .get_state_by_name("not_occ__cc_1_2")
        ._bkd.isActive()
    )

    system.isimu_stop()
