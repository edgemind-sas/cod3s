"""Deterministic (single-branch) inst transitions bypass the pending panel.

``PycTransition.from_bkd`` rebuilds every inst-law transition with a
list-typed target — including single-target p=1 ones such as the
``ObjFMInst`` re-arm. Without the branch-count filter in
``ISimuEngine.pending_inst`` the operator would have to submit a
one-option pick at every re-arm. This module pins the filter.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s.pycatshoo.isimu.engine import ISimuEngine
from cod3s.pycatshoo.system import PycSystem


class InstEquipment006(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.demand = self.addVariable("demand", Pyc.TVarType.t_bool, False)
        self.failed = self.addVariable("failed", Pyc.TVarType.t_bool, False)
        self.failed.setReinitialized(True)


@pytest.fixture()
def engine():
    system = PycSystem(name="SysInstPanel006")
    system.add_component(name="E1", cls="InstEquipment006")
    system.add_component(
        cls="ObjFMInst",
        fm_name="miss",
        targets=["E1"],
        failure_cond=lambda: system.comp["E1"].demand.value() is True,
        failure_effects={"failed": True},
        failure_param=0.3,
        repair_param=0.1,
    )
    eng = ISimuEngine(system)
    eng.start()
    yield eng
    eng.stop()
    cod3s.terminate_session()


def test_single_branch_inst_not_pending(engine):
    system = engine.system
    eq = system.comp["E1"]

    # Demand front: the 2-branch draw IS pending.
    eq.demand.setValue(True)
    engine.step_forward()  # scheduler refresh after the manual toggle
    pending = engine.pending_inst()
    assert [t.name for t in pending] == ["occ"]
    assert len(pending[0].target) == 2

    # Land on not_occ, then drop the demand: the p=1 re-arm becomes
    # fireable but must NOT be surfaced as a pending inst.
    draw_id = next(i for i, t in enumerate(engine.fireable()) if t and t.name == "occ")
    engine.resolve_inst({draw_id: 1})
    eq.demand.setValue(False)
    engine.step_forward()  # scheduler refresh

    fireable = [t for t in engine.fireable() if t is not None]
    assert [t.name for t in fireable] == ["not_occ"]
    assert isinstance(fireable[0].target, list)
    assert len(fireable[0].target) == 1
    assert engine.pending_inst() == []

    # A plain step drains it without any resolution.
    evt = engine.step_forward()
    assert [t.name for t in evt.transitions] == ["not_occ"]
