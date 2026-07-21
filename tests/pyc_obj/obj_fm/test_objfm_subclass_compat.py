"""Third-party ObjFM subclass compatibility contract (ObjMode2S safety net).

The ObjFM hook protocol is a public extension surface: domain libraries
subclass ``ObjFM``/``ObjFMExp`` and override the ``set_*`` / ``is_*`` /
``get_*_cond`` hooks and — for exotic occurrence models — the whole
``_build_fm_automaton`` (with the pre-trans-effects signature, tolerated
by the call site since commit 32c3165). This suite pins, before the
ObjMode2S engine extraction:

* the hook CALL ORDER and the partial-init state visible at each hook
  (``set_default_failure_param_name`` runs before
  ``param_name_order_prefix`` is set);
* the old-signature ``_build_fm_automaton`` override tolerance;
* the drop-inactive path (default-padded params -> automaton dropped
  after the activity hooks);
* the historical ``ObjFM(targets=[])`` silent no-op (zero automata,
  zero param variables) — the ObjMode2S self-hosted mode must NOT
  change this behaviour through the façade.
"""

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import ObjFMExp
from cod3s.pycatshoo.system import PycSystem


class Equipment(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


@pytest.fixture(scope="module")
def system():
    system = PycSystem(name="SubclassCompat")
    Equipment("C1")
    yield system
    cod3s.terminate_session()


class HookRecorderFM(ObjFMExp):
    """Records every hook invocation, then delegates to ObjFMExp."""

    def __init__(self, *args, **kwargs):
        self.hook_log = []
        self.attrs_at_param_name_hook = None
        super().__init__(*args, **kwargs)

    def set_default_failure_param_name(self):
        self.hook_log.append("set_default_failure_param_name")
        # Partial-init contract: identity attrs are set, naming prefix not yet.
        self.attrs_at_param_name_hook = {
            "has_fm_name": hasattr(self, "fm_name"),
            "has_targets": hasattr(self, "targets"),
            "has_behaviour": hasattr(self, "behaviour"),
            "has_failure_cond": hasattr(self, "failure_cond"),
            "has_param_name_order_prefix": hasattr(self, "param_name_order_prefix"),
        }
        super().set_default_failure_param_name()

    def set_default_repair_param_name(self):
        self.hook_log.append("set_default_repair_param_name")
        super().set_default_repair_param_name()

    def set_default_failure_param(self):
        self.hook_log.append("set_default_failure_param")
        super().set_default_failure_param()

    def set_default_repair_param(self):
        self.hook_log.append("set_default_repair_param")
        super().set_default_repair_param()

    def is_occ_law_failure_active(self, params):
        self.hook_log.append("is_occ_law_failure_active")
        return super().is_occ_law_failure_active(params)

    def is_occ_law_repair_active(self, params):
        self.hook_log.append("is_occ_law_repair_active")
        return super().is_occ_law_repair_active(params)

    def get_failure_cond(self, target_comps, param, **kwrds):
        self.hook_log.append("get_failure_cond")
        return super().get_failure_cond(target_comps, param, **kwrds)

    def get_repair_cond(self, target_comps, param, **kwrds):
        self.hook_log.append("get_repair_cond")
        return super().get_repair_cond(target_comps, param, **kwrds)

    def set_occ_law_failure(self, params):
        self.hook_log.append("set_occ_law_failure")
        return super().set_occ_law_failure(params)

    def set_occ_law_repair(self, params):
        self.hook_log.append("set_occ_law_repair")
        return super().set_occ_law_repair(params)


def test_hook_call_order_single_target_with_params(system):
    fm = HookRecorderFM(
        fm_name="hkfm",
        targets=["C1"],
        failure_param=0.1,
        repair_param=0.2,
    )
    # Params provided (diff == 0) -> the set_default_*_param hooks are
    # NOT called; the drop check short-circuits: failure law active ->
    # is_occ_law_repair_active is NOT evaluated.
    assert fm.hook_log == [
        "set_default_failure_param_name",
        "set_default_repair_param_name",
        "is_occ_law_failure_active",
        "get_failure_cond",
        "get_repair_cond",
        "set_occ_law_repair",
        "set_occ_law_failure",
    ]
    assert fm.attrs_at_param_name_hook == {
        "has_fm_name": True,
        "has_targets": True,
        "has_behaviour": True,
        "has_failure_cond": True,
        "has_param_name_order_prefix": False,
    }
    assert list(fm.automata_d) == ["hkfm"]


def test_hook_call_order_default_padding_drops_automaton(system):
    fm = HookRecorderFM(fm_name="hkfm2", targets=["C1"])
    # No params -> default (0,) padding hooks run; both laws inactive ->
    # the combination is dropped right after the activity hooks.
    assert fm.hook_log == [
        "set_default_failure_param_name",
        "set_default_repair_param_name",
        "set_default_failure_param",
        "set_default_repair_param",
        "is_occ_law_failure_active",
        "is_occ_law_repair_active",
    ]
    assert fm.automata_d == {}
    # Param variables are created BEFORE the drop decision (study
    # indicators reference them even for dropped automata).
    assert {v.basename() for v in fm.variables()} == {"lambda", "mu"}


class LegacyBuildFM(ObjFMExp):
    """Third-party style: overrides _build_fm_automaton with the
    pre-trans-effects signature (no *_trans kwargs)."""

    def __init__(self, *args, **kwargs):
        self.legacy_build_calls = 0
        super().__init__(*args, **kwargs)

    def _build_fm_automaton(
        self,
        aut_name,
        repair_state_name,
        failure_state_name,
        failure_cond,
        repair_cond,
        failure_var_params,
        repair_var_params,
        failure_effects,
        repair_effects,
        repair_law,
    ):
        self.legacy_build_calls += 1
        return super()._build_fm_automaton(
            aut_name,
            repair_state_name,
            failure_state_name,
            failure_cond,
            repair_cond,
            failure_var_params,
            repair_var_params,
            failure_effects,
            repair_effects,
            repair_law,
        )


def test_old_signature_build_fm_automaton_tolerated(system):
    fm = LegacyBuildFM(
        fm_name="legacy",
        targets=["C1"],
        failure_param=0.5,
        repair_param=0.5,
        failure_effects={"working": False},
    )
    assert fm.legacy_build_calls == 1
    aut = fm.automata_d["legacy"]
    assert {st.name for st in aut.states} == {"rep", "occ"}
    assert aut.get_transition_by_name("occ").source == "rep"
    assert aut.get_transition_by_name("rep").source == "occ"

    # The built automaton is functional: fire occ, effect applied.
    equipment = system.comp["C1"]
    system.isimu_start()
    trs = system.isimu_fireable_transitions()
    idx = next(
        i
        for i, t in enumerate(trs)
        if t is not None and t.name == "occ" and "legacy" in t.comp_name
    )
    system.isimu_set_transition(idx, date=1.0)
    fired = [t.name for t in system.isimu_step_forward()]
    assert "occ" in fired
    assert equipment.working.value() is False
    system.isimu_stop()


def test_empty_targets_silent_noop(system):
    """ObjFM(targets=[]) historically builds a dead component: zero
    automata, zero parameter variables. Pinned so the ObjMode2S
    self-hosted mode never activates through the façade by accident."""
    fm = ObjFMExp(fm_name="frunempty", targets=[])
    assert fm.name() == "__frunempty"
    assert fm.automata_d == {}
    assert [v.basename() for v in fm.variables()] == []
    assert "__frunempty" in system.comp
