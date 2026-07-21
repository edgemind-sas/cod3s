"""Structural + registration-count baselines (ObjMode2S perf guard).

Name grammar pins alone cannot catch a per-step simulation cost
regression: what costs in Monte-Carlo is the number of automata,
states, transitions, and above all the number of sensitive / start
method registrations that fire on every fixpoint pass. This suite pins
those counts for one representative model per façade behaviour, as
observed on master before the ObjMode2S engine extraction:

* internal CCF order 3 with a fully inactive order (dropped combos and
  param-variables-created-before-drop),
* external (centralised ctrl_sync + target automata),
* external_rep_indep (ctrl latch effects + reset_ctrl),
* ObjFMInst CCF (3-state draw automata).

The registration spies wrap the pybind entry points actually used by
the wiring code (Python-side calls only, which is exactly what the
COD3S layer registers).
"""

import contextlib

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s.pycatshoo.system import PycSystem


class Equipment(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


@pytest.fixture
def pyc_session():
    yield
    cod3s.terminate_session()


@contextlib.contextmanager
def spy_registrations(counts):
    orig_start = Pyc.CComponent.addStartMethod
    orig_aut = Pyc.IAutomaton.addSensitiveMethod
    orig_var = Pyc.IVariable.addSensitiveMethod
    orig_trans = Pyc.ITransition.addSensitiveMethod

    def spy_start(self, name, fn):
        counts["start"] += 1
        return orig_start(self, name, fn)

    def spy_aut(self, name, fn):
        counts["aut_sensitive"] += 1
        return orig_aut(self, name, fn)

    def spy_var(self, name, fn):
        counts["var_sensitive"] += 1
        return orig_var(self, name, fn)

    def spy_trans(self, name, fn):
        counts["trans_sensitive"] += 1
        return orig_trans(self, name, fn)

    Pyc.CComponent.addStartMethod = spy_start
    Pyc.IAutomaton.addSensitiveMethod = spy_aut
    Pyc.IVariable.addSensitiveMethod = spy_var
    Pyc.ITransition.addSensitiveMethod = spy_trans
    try:
        yield
    finally:
        Pyc.CComponent.addStartMethod = orig_start
        Pyc.IAutomaton.addSensitiveMethod = orig_aut
        Pyc.IVariable.addSensitiveMethod = orig_var
        Pyc.ITransition.addSensitiveMethod = orig_trans


def _snapshot(fm):
    return {
        "automata": sorted(fm.automata_d),
        "aut_shapes": {
            name: (len(aut.states), len(aut.transitions))
            for name, aut in sorted(fm.automata_d.items())
        },
        "variables": sorted(v.basename() for v in fm.variables()),
    }


def test_internal_ccf3_inactive_order_counts(pyc_session):
    system = PycSystem(name="CountsCCF3")
    for n in ("C1", "C2", "C3"):
        Equipment(n)
    counts = {"start": 0, "aut_sensitive": 0, "var_sensitive": 0, "trans_sensitive": 0}
    with spy_registrations(counts):
        fm = cod3s.ObjFMExp(
            fm_name="frun",
            targets=["C1", "C2", "C3"],
            failure_param=[0.1, 0, 0.3],
            repair_param=[0.2, 0, 0.4],
            failure_effects={"working": False},
            repair_effects={"working": True},
        )
    snap = _snapshot(fm)
    # Order 2 fully inactive (lambda_2 = mu_2 = 0) -> its 3 combos dropped.
    assert snap["automata"] == [
        "frun__cc_1",
        "frun__cc_1_2_3",
        "frun__cc_2",
        "frun__cc_3",
    ]
    assert set(snap["aut_shapes"].values()) == {(2, 2)}
    # Param variables exist for ALL orders, dropped ones included.
    assert snap["variables"] == [
        "lambda__1_o_3",
        "lambda__2_o_3",
        "lambda__3_o_3",
        "mu__1_o_3",
        "mu__2_o_3",
        "mu__3_o_3",
    ]
    # 4 automata x 2 state clamps (failure + repair effects).
    # var_sensitive: order-1 clamps touch 1 var each (3 x 2), the order-3
    # clamps touch 3 vars each (2 x 3).
    assert counts == {
        "start": 8,
        "aut_sensitive": 8,
        "var_sensitive": 12,
        "trans_sensitive": 0,
    }


def test_external_counts(pyc_session):
    system = PycSystem(name="CountsExternal")
    for n in ("C1", "C2"):
        Equipment(n)
    counts = {"start": 0, "aut_sensitive": 0, "var_sensitive": 0, "trans_sensitive": 0}
    with spy_registrations(counts):
        fm = cod3s.ObjFMExp(
            fm_name="frun",
            targets=["C1", "C2"],
            behaviour="external",
            failure_param=[0.1, 0.2],
            repair_param=[0.3, 0.4],
            failure_effects={"working": False},
        )
    snap = _snapshot(fm)
    assert snap["automata"] == ["frun__cc_1", "frun__cc_1_2", "frun__cc_2"]
    assert snap["variables"] == [
        "ctrl_frun_C1",
        "ctrl_frun_C2",
        "lambda__1_o_2",
        "lambda__2_o_2",
        "mu__1_o_2",
        "mu__2_o_2",
    ]
    for t in ("C1", "C2"):
        assert sorted(a.basename() for a in system.comp[t].automata()) == ["frun"]
    # ctrl_sync: 2 methods registered on their impacting automata
    # (2 + 2) + 2 starts; target failure-effect clamps: 2 automata
    # registrations + 2 starts + 2 variable registrations.
    assert counts == {
        "start": 4,
        "aut_sensitive": 6,
        "var_sensitive": 2,
        "trans_sensitive": 0,
    }


def test_external_rep_indep_counts(pyc_session):
    system = PycSystem(name="CountsRepIndep")
    for n in ("C1", "C2"):
        Equipment(n)
    counts = {"start": 0, "aut_sensitive": 0, "var_sensitive": 0, "trans_sensitive": 0}
    with spy_registrations(counts):
        fm = cod3s.ObjFMExp(
            fm_name="frun",
            targets=["C1", "C2"],
            behaviour="external_rep_indep",
            failure_param=[0.1, 0.2],
            repair_param=[0.3, 0.4],
            failure_effects={"working": False},
        )
    snap = _snapshot(fm)
    assert snap["automata"] == ["frun__cc_1", "frun__cc_1_2", "frun__cc_2"]
    for t in ("C1", "C2"):
        assert sorted(a.basename() for a in system.comp[t].automata()) == ["frun"]
    # ctrl-latch clamps on the 3 FM automata (3 aut + 3 start; ctrl var
    # registrations: 1 + 1 + 2) + target clamps (2 aut + 2 start + 2 var)
    # + reset_ctrl on the 2 target automata (2 aut, no start).
    assert counts == {
        "start": 5,
        "aut_sensitive": 7,
        "var_sensitive": 6,
        "trans_sensitive": 0,
    }


def test_inst_ccf_counts(pyc_session):
    system = PycSystem(name="CountsInstCCF")
    for n in ("E1", "E2"):
        Equipment(n)
    counts = {"start": 0, "aut_sensitive": 0, "var_sensitive": 0, "trans_sensitive": 0}
    with spy_registrations(counts):
        fm = cod3s.ObjFMInst(
            fm_name="miss",
            targets=["E1", "E2"],
            failure_cond=True,
            failure_param=[0.3, 0.1],
            repair_param=[0.5, 0.5],
            failure_effects={"working": False},
        )
    snap = _snapshot(fm)
    assert snap["automata"] == ["miss__cc_1", "miss__cc_1_2", "miss__cc_2"]
    # 3-state draw automata: rep / occ / not_occ, 3 transitions each.
    assert set(snap["aut_shapes"].values()) == {(3, 3)}
    assert snap["variables"] == [
        "gamma__1_o_2",
        "gamma__2_o_2",
        "mu__1_o_2",
        "mu__2_o_2",
    ]
    # One failure-effect clamp per combo automaton (3 aut + 3 start;
    # var registrations 1 + 1 + 2). No repair clamp (reinitialized
    # convention), re-arm and draw carry no registrations.
    assert counts == {
        "start": 3,
        "aut_sensitive": 3,
        "var_sensitive": 4,
        "trans_sensitive": 0,
    }
