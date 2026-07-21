"""Backward-compatibility regressions found by the post-merge review of
the ObjMode2S chantier, each verified against the 1.13.0 behaviour.

The façade layer must be indistinguishable from the pre-engine classes
for the surfaces the extension protocol exposes:

* the historical ``failure_*`` / ``repair_*`` names are *views* on the
  engine storage, not one-way copies (a legacy write must reach the
  engine, and a mutation after construction must be seen by the guards);
* constant occ / not_occ conditions stay late-bound, so rebinding the
  attribute mid-study still inhibits or re-enables the mode;
* the legacy attributes are visible inside every public hook, at the
  point the hook has always seen them;
* ``ObjFMInst`` keeps ``_build_fm_automaton`` as a real extension hook
  even though the 3-state machinery now lives in the engine.
"""

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


class TestLegacyAliasesAreViews:
    """Writing a legacy name must reach the engine storage (and back)."""

    def test_write_legacy_reaches_engine(self, pyc_session):
        system = PycSystem(name="AliasWrite")
        Equipment("C1")
        fm = cod3s.ObjFMExp(
            fm_name="frun", targets=["C1"], failure_param=0.1, repair_param=0.2
        )
        fm.failure_cond = False
        assert fm.occ_cond is False
        fm.occ_state = "boom"
        assert fm.failure_state == "boom"
        fm.repair_param = [0.9]
        assert fm.not_occ_param == [0.9]

    def test_legacy_and_engine_share_one_storage(self, pyc_session):
        system = PycSystem(name="AliasShared")
        Equipment("C1")
        fm = cod3s.ObjFMExp(
            fm_name="frun",
            targets=["C1"],
            failure_param=0.1,
            repair_param=0.2,
            failure_effects={"working": False},
        )
        # Same object, not a copy: mutating through one name is visible
        # through the other.
        fm.failure_effects["extra"] = True
        assert fm.occ_effects["extra"] is True


class TestConstantConditionLateBinding:
    """1.13.0 re-read ``self.failure_cond`` at every guard evaluation."""

    def test_failure_cond_mutation_after_construction_is_honoured(self, pyc_session):
        system = PycSystem(name="LateBindOcc")
        Equipment("C1")
        fm = cod3s.ObjFMExp(
            fm_name="frun",
            targets=["C1"],
            failure_param=0.5,
            repair_param=0.5,
            failure_cond=True,
        )
        guard = fm.get_failure_cond(
            target_comps=[system.component("C1")],
            param={"lambda": fm.variable("lambda")},
        )
        assert guard() is True
        fm.failure_cond = False
        assert guard() is False, "constant guard must stay late-bound"

    def test_repair_cond_mutation_after_construction_is_honoured(self, pyc_session):
        system = PycSystem(name="LateBindRep")
        Equipment("C1")
        fm = cod3s.ObjFMExp(
            fm_name="frun",
            targets=["C1"],
            failure_param=0.5,
            repair_param=0.5,
            repair_cond=True,
        )
        guard = fm.get_repair_cond(
            target_comps=[system.component("C1")], param={"mu": fm.variable("mu")}
        )
        assert guard() is True
        fm.repair_cond = False
        assert guard() is False

    def test_callable_cond_stays_early_bound(self, pyc_session):
        """Callables were always captured at build time — unchanged."""
        system = PycSystem(name="LateBindCallable")
        Equipment("C1")
        fm = cod3s.ObjFMExp(
            fm_name="frun",
            targets=["C1"],
            failure_param=0.5,
            repair_param=0.5,
            failure_cond=lambda: True,
        )
        guard = fm.get_failure_cond(
            target_comps=[system.component("C1")],
            param={"lambda": fm.variable("lambda")},
        )
        fm.failure_cond = lambda: False
        assert guard() is True


class TestLegacyAttributesVisibleInHooks:
    """Every public hook must see the legacy attributes it always saw."""

    def test_failure_param_visible_in_activity_hook(self, pyc_session):
        seen = {}

        class PeekExp(cod3s.ObjFMExp):
            def is_occ_law_failure_active(self, params):
                seen["failure_param"] = list(self.failure_param)
                seen["repair_param"] = list(self.repair_param)
                return super().is_occ_law_failure_active(params)

        system = PycSystem(name="HookVisibility")
        Equipment("C1")
        PeekExp(fm_name="pk", targets=["C1"], failure_param=0.1, repair_param=0.2)
        assert seen["failure_param"] == [0.1]
        assert seen["repair_param"] == [0.2]

    def test_legacy_write_inside_hook_reaches_the_build(self, pyc_session):
        """A hook rebinding a legacy attribute must drive the build."""

        class RenamingExp(cod3s.ObjFMExp):
            def set_default_failure_param_name(self):
                super().set_default_failure_param_name()
                self.failure_param_name = ["custom_lambda"]

        system = PycSystem(name="HookWrite")
        Equipment("C1")
        fm = RenamingExp(
            fm_name="rn", targets=["C1"], failure_param=0.1, repair_param=0.2
        )
        assert "custom_lambda" in [v.basename() for v in fm.variables()]
        assert fm.occ_param_name == ["custom_lambda"]


class TestObjFMInstBuildHookStillCalled:
    """The engine owns the 3-state machinery, but ``_build_fm_automaton``
    remains the documented ObjFMInst extension point."""

    def test_subclass_override_is_invoked(self, pyc_session):
        calls = []

        class MyInst(cod3s.ObjFMInst):
            def _build_fm_automaton(self, *args, **kwargs):
                calls.append(kwargs.get("aut_name") or args[0])
                return super()._build_fm_automaton(*args, **kwargs)

        system = PycSystem(name="InstHook")
        Equipment("E1")
        fm = MyInst(
            fm_name="miss",
            targets=["E1"],
            failure_cond=True,
            failure_param=0.3,
            repair_param=0.5,
            failure_effects={"working": False},
        )
        assert calls == ["miss"], "ObjFMInst _build_fm_automaton hook must run"
        # The engine still built the historical 3-state automaton.
        aut = fm.automata_d["miss"]
        assert {st.name for st in aut.states} == {"rep", "occ", "not_occ"}
        assert aut.get_transition_by_name("occ")._bkd.monitoredOutStateMask() == "#occ$"

    def test_subclass_can_post_process_the_built_automaton(self, pyc_session):
        """The override receives the built automaton and its return
        value is what the engine records — so a subclass can inspect or
        re-wire it, the reason the hook exists."""
        captured = {}

        class TighteningInst(cod3s.ObjFMInst):
            def _build_fm_automaton(self, *args, **kwargs):
                aut = super()._build_fm_automaton(*args, **kwargs)
                captured["aut"] = aut
                # A realistic post-processing: silence the draw entirely.
                aut.get_transition_by_name("occ")._bkd.setMonitoredOutStateMask(
                    self._NEVER_MATCH_MASK
                )
                return aut

        system = PycSystem(name="InstHookTighten")
        Equipment("E1")
        fm = TighteningInst(
            fm_name="miss",
            targets=["E1"],
            failure_cond=True,
            failure_param=0.3,
            repair_param=0.5,
        )
        assert captured["aut"] is fm.automata_d["miss"]
        assert (
            fm.automata_d["miss"]
            .get_transition_by_name("occ")
            ._bkd.monitoredOutStateMask()
            == "#$^"
        )

    def test_objfmexp_subclass_still_gets_the_two_state_build(self, pyc_session):
        """The inst bridge must not leak into the timed path."""
        seen = {}

        class ExpHook(cod3s.ObjFMExp):
            def _build_fm_automaton(self, *args, **kwargs):
                aut = super()._build_fm_automaton(*args, **kwargs)
                seen["states"] = {st.name for st in aut.states}
                return aut

        system = PycSystem(name="ExpHookTwoState")
        Equipment("C1")
        ExpHook(fm_name="frun", targets=["C1"], failure_param=0.1, repair_param=0.2)
        assert seen["states"] == {"rep", "occ"}
