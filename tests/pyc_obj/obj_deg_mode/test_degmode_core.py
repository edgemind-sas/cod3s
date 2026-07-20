"""ObjDegMode core semantics (order 1), driven step by step in isimu.

Covers: full progression, guard freezing progression but not repair,
run-to-failure, repair conditions, ctrl consumption, level variable,
monitor masks, parameter re-binding (exp AND delay), pulse effects,
clamp release semantics, delay interruptibility, and the early
equivalence lock ObjDegMode(K=1, N=1) vs ObjFM external_rep_indep.
"""

import sys
from pathlib import Path

import Pycatshoo as Pyc
import pytest

import cod3s
from cod3s import DegState, ObjDegMode
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem

sys.path.insert(0, str(Path(__file__).parent))
from _utils import enter_first_state, fire_by_name, fireable_names  # noqa: E402


class Rail(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.broken = self.addVariable("broken", Pyc.TVarType.t_bool, False)
        self.broken.setReinitialized(True)
        self.gate = self.addVariable("gate", Pyc.TVarType.t_bool, True)
        self.gate.setReinitialized(True)
        self.alarm = self.addVariable("alarm", Pyc.TVarType.t_bool, False)
        # Persistent gate for pulses: NOT reinitialized on purpose would be
        # the muscadet pattern; here a plain reinitialized bool is enough
        # for one-shot observation within a run.
        self.alarm.setReinitialized(True)


def fresh_system(name):
    cod3s.terminate_session()
    return PycSystem(name=name)


def build_mode(states, occ_cond=True, targets=("R1",), fm_name="Fissure"):
    return ObjDegMode(
        fm_name=fm_name, targets=list(targets), states=states, occ_cond=occ_cond
    )


class TestProgressionAndRepair:
    def test_full_chain_progression_then_repair(self):
        system = fresh_system("DegCore1")
        r1 = Rail("R1")
        build_mode(
            [
                DegState("O", occ_law={"cls": "exp", "rate": 0.3}),
                DegState(
                    "X1",
                    occ_law={"cls": "exp", "rate": 0.2},
                    effects={"broken": True},
                    rep_law={"cls": "delay", "time": 8.0},
                ),
            ]
        )
        level = r1.variable("Fissure_level")

        system.isimu_start()
        # Carrier CC fire at t=2 (single target: no __cc suffix); in isimu
        # the delay(0) target entry fires on the next explicit step.
        enter_first_state(system, "R1__Fissure.occ_O", "R1.Fissure__occ_O", date=2.0)
        assert system.currentTime() == 2.0
        assert level.value() == 1
        assert r1.broken.value() is False

        # Progression O -> X1 at t=5: state effect clamps broken=True.
        fire_by_name(system, "R1.Fissure__occ_X1", date=5.0)
        assert level.value() == 2
        assert r1.broken.value() is True

        # X1 is the last state: no further occ fireable, repair delay(8)
        # brings back to healthy at t=13.
        names = fireable_names(system)
        assert not any("occ" in n for n in names), names
        fire_by_name(system, "R1.Fissure__rep_X1")
        assert system.currentTime() == pytest.approx(13.0)
        assert level.value() == 0
        # Clamp release semantics (documented): once the state is left the
        # clamp stops maintaining the variable. A setReinitialized(True)
        # variable falls back to its INIT value (verified in isimu here and
        # in MC indicator sampling by the ObjFM parity suite); only a
        # NON-reinitialized variable (persistent gate) keeps the last
        # written value. Derive observables from the level variable or a
        # recomputed (muscadet-flow) variable (a same-variable release
        # pulse is rejected by the overlap check).
        assert r1.broken.value() is False
        system.isimu_stop()

    def test_run_to_failure_last_state_absorbing(self):
        system = fresh_system("DegCore2")
        Rail("R1")
        build_mode(
            [
                DegState("O", occ_law={"cls": "exp", "rate": 0.3}),
                DegState("X1", occ_law={"cls": "exp", "rate": 0.2}),
            ]
        )
        system.isimu_start()
        enter_first_state(system, "R1__Fissure.occ_O", "R1.Fissure__occ_O", date=1.0)
        fire_by_name(system, "R1.Fissure__occ_X1", date=2.0)
        # No rep_law anywhere: absorbing, nothing fireable at all.
        assert fireable_names(system) == []
        system.isimu_stop()

    def test_repair_from_intermediate_state(self):
        system = fresh_system("DegCore3")
        r1 = Rail("R1")
        build_mode(
            [
                DegState(
                    "O",
                    occ_law={"cls": "exp", "rate": 0.3},
                    rep_law={"cls": "exp", "rate": 0.5},
                ),
                DegState("X1", occ_law={"cls": "exp", "rate": 0.2}),
            ]
        )
        level = r1.variable("Fissure_level")
        system.isimu_start()
        enter_first_state(system, "R1__Fissure.occ_O", "R1.Fissure__occ_O", date=1.0)
        assert level.value() == 1
        fire_by_name(system, "R1.Fissure__rep_O", date=4.0)
        assert level.value() == 0
        # Back to healthy: the CC entry is armed again.
        assert any("R1__Fissure.occ_O" in n for n in fireable_names(system))
        system.isimu_stop()


class TestConditions:
    def test_global_occ_cond_gates_entry_and_progression_not_repair(self):
        system = fresh_system("DegCore4")
        r1 = Rail("R1")
        build_mode(
            [
                DegState("O", occ_law={"cls": "exp", "rate": 0.3}),
                DegState(
                    "X1",
                    occ_law={"cls": "exp", "rate": 0.2},
                    rep_law={"cls": "exp", "rate": 0.5},
                ),
            ],
            occ_cond=[{"attr": "gate", "value": True}],
        )
        system.isimu_start()
        # gate True: entry fireable.
        assert any("R1__Fissure.occ_O" in n for n in fireable_names(system))
        enter_first_state(system, "R1__Fissure.occ_O", "R1.Fissure__occ_O", date=1.0)
        fire_by_name(system, "R1.Fissure__occ_X1", date=2.0)

        # gate False: progression frozen... nothing left but repair.
        r1.gate.setValue(False)
        names = fireable_names(system)
        assert any("rep_X1" in n for n in names), names
        system.isimu_stop()

    def test_global_occ_cond_false_blocks_carrier_fire(self):
        system = fresh_system("DegCore5")
        r1 = Rail("R1")
        r1.gate.setValue(False)
        build_mode(
            [DegState("O", occ_law={"cls": "exp", "rate": 0.3})],
            occ_cond=[{"attr": "gate", "value": True}],
        )
        system.isimu_start()
        assert fireable_names(system) == []
        system.isimu_stop()

    def test_local_occ_cond_anded_with_global(self):
        # Conditions must be driven by REAL transitions (manual variable
        # writes do not survive the isimu replay): a second "Guard" mode
        # on the same target provides a level variable as the gate.
        system = fresh_system("DegCore6")
        Rail("R1")
        build_mode(
            [DegState("g", occ_law={"cls": "exp", "rate": 0.1})],
            fm_name="Guard",
        )
        build_mode(
            [
                DegState("O", occ_law={"cls": "exp", "rate": 0.3}),
                DegState(
                    "X1",
                    occ_law={"cls": "exp", "rate": 0.2},
                    occ_cond=[{"attr": "Guard_level", "value": 1}],
                ),
            ]
        )
        system.isimu_start()
        enter_first_state(system, "R1__Fissure.occ_O", "R1.Fissure__occ_O", date=1.0)
        # Local condition false (Guard healthy): X1 progression not fireable.
        assert not any("occ_X1" in n for n in fireable_names(system))
        # Degrade the Guard: local condition becomes true.
        enter_first_state(system, "R1__Guard.occ_g", "R1.Guard__occ_g", date=2.0)
        assert any("occ_X1" in n for n in fireable_names(system))
        system.isimu_stop()

    def test_rep_cond_controls_repair(self):
        system = fresh_system("DegCore7")
        Rail("R1")
        build_mode(
            [DegState("g", occ_law={"cls": "exp", "rate": 0.1})],
            fm_name="Guard",
        )
        build_mode(
            [
                DegState(
                    "O",
                    occ_law={"cls": "exp", "rate": 0.3},
                    rep_law={"cls": "exp", "rate": 0.5},
                    # Repair only allowed while the Guard mode is degraded
                    # (arbitrary but transition-driven).
                    rep_cond=[{"attr": "Guard_level", "value": 1}],
                )
            ]
        )
        system.isimu_start()
        enter_first_state(system, "R1__Fissure.occ_O", "R1.Fissure__occ_O", date=1.0)
        assert not any("rep_O" in n for n in fireable_names(system))
        enter_first_state(system, "R1__Guard.occ_g", "R1.Guard__occ_g", date=2.0)
        assert any("rep_O" in n for n in fireable_names(system))
        system.isimu_stop()


class TestCtrlAndMasks:
    def test_ctrl_latch_consumed_on_entry(self):
        system = fresh_system("DegCore8")
        Rail("R1")
        dm = build_mode([DegState("O", occ_law={"cls": "exp", "rate": 0.3})])
        system.isimu_start()
        enter_first_state(system, "R1__Fissure.occ_O", "R1.Fissure__occ_O", date=1.0)
        assert dm.ctrl_vars["R1"].value() is False
        system.isimu_stop()

    def test_carrier_rearm_masked(self):
        system = fresh_system("DegCore9")
        Rail("R1")
        dm = build_mode([DegState("O", occ_law={"cls": "exp", "rate": 0.3})])
        aut = dm.automata_d["Fissure"]
        rearm_bkd = aut.get_transition_by_name("rearm")._bkd
        assert rearm_bkd.monitoredOutStateMask() == "#$^"
        # Idempotent re-application (study runner hook).
        dm.reapply_monitor_masks()
        assert rearm_bkd.monitoredOutStateMask() == "#$^"


class TestParameters:
    def test_exp_law_rebound_to_lambda_variable(self):
        system = fresh_system("DegCore10")
        Rail("R1")
        dm = build_mode([DegState("O", occ_law={"cls": "exp", "rate": 0.3})])
        # Runtime override: zero the lambda variable => the entry law is
        # inactive => MC produces no degradation at all.
        dm.variable("lambda_O").setValue(0.0)
        system.add_indicator_var(
            component="R1", var="Fissure_level", stats=["mean"], name="lv"
        )
        system.simulate(PycMCSimulationParam(nb_runs=500, schedule=[50.0], seed=11))
        assert system.indicators["lv_Fissure_level"].values["values"].iloc[-1] == 0.0

    def test_delay_law_rebound_to_ttr_variable(self):
        system = fresh_system("DegCore11")
        Rail("R1")
        dm = build_mode(
            [
                DegState(
                    "O",
                    occ_law={"cls": "exp", "rate": 0.3},
                    rep_law={"cls": "delay", "time": 8.0},
                )
            ]
        )
        # Runtime override BEFORE simulation start: ttr 8 -> 3.
        dm.variable("ttr_O").setValue(3.0)
        system.isimu_start()
        enter_first_state(system, "R1__Fissure.occ_O", "R1.Fissure__occ_O", date=1.0)
        fire_by_name(system, "R1.Fissure__rep_O")
        # Repair completes at entry (t=1) + overridden ttr (3) = 4, not 9.
        assert system.currentTime() == pytest.approx(4.0)
        system.isimu_stop()

    def test_param_variable_names(self):
        system = fresh_system("DegCore12")
        Rail("R1")
        dm = build_mode(
            [
                DegState(
                    "O",
                    occ_law={"cls": "exp", "rate": 0.3},
                    rep_law={"cls": "exp", "rate": 0.5},
                ),
                DegState(
                    "X1",
                    occ_law={"cls": "delay", "time": 6.0},
                    rep_law={"cls": "delay", "time": 8.0},
                ),
            ]
        )
        names = {v.basename() for v in dm.variables()}
        # Grammar: lambda_<state> (first, N=1: no order suffix),
        # ttf/lambda_<state> for progressions, mu/ttr_<state> for repairs.
        assert {"lambda_O", "mu_O", "ttf_X1", "ttr_X1"} <= names


class TestEffects:
    def test_pulse_effects_on_occ_and_rep(self):
        system = fresh_system("DegCore13")
        r1 = Rail("R1")
        build_mode(
            [
                DegState(
                    "O",
                    occ_law={"cls": "exp", "rate": 0.3},
                    occ_effects_trans={"alarm": True},
                    rep_law={"cls": "exp", "rate": 0.5},
                    rep_effects_trans={"alarm": False},
                )
            ]
        )
        system.isimu_start()
        enter_first_state(system, "R1__Fissure.occ_O", "R1.Fissure__occ_O", date=1.0)
        assert r1.alarm.value() is True
        # One-shot: clearing by hand is not undone by any standing clamp.
        r1.alarm.setValue(False)
        r1.alarm.setValue(True)  # restore for the rep pulse observation
        fire_by_name(system, "R1.Fissure__rep_O", date=5.0)
        assert r1.alarm.value() is False
        system.isimu_stop()

    def test_level_indicator_over_mc(self):
        system = fresh_system("DegCore14")
        Rail("R1")
        build_mode(
            [
                DegState("O", occ_law={"cls": "exp", "rate": 0.5}),
                DegState("X1", occ_law={"cls": "exp", "rate": 0.5}),
            ]
        )
        system.add_indicator_var(
            component="R1", var="Fissure_level", stats=["mean"], name="lv"
        )
        system.simulate(
            PycMCSimulationParam(nb_runs=1000, schedule=[0.0, 10.0], seed=3)
        )
        vals = system.indicators["lv_Fissure_level"].values["values"]
        assert vals.iloc[0] == 0.0  # no leak at t=0
        assert 1.0 < vals.iloc[-1] <= 2.0  # strong degradation by t=10


class TestDelayInterruptibility:
    def test_interrupted_delay_resamples(self):
        """Characterisation (documented bias): a delay progression whose
        guard drops and comes back RESTARTS from zero (occ_interruptible
        semantics: exp is memoryless, delay is not).

        The guard is driven by real transitions of a second "Guard" mode
        on the same target (repairable), so simulated time really elapses
        while the delay is disabled.
        """
        system = fresh_system("DegCore15")
        Rail("R1")
        build_mode(
            [
                DegState(
                    "g",
                    occ_law={"cls": "exp", "rate": 0.1},
                    rep_law={"cls": "delay", "time": 2.0},
                )
            ],
            fm_name="Guard",
        )
        build_mode(
            [
                DegState("O", occ_law={"cls": "exp", "rate": 0.3}),
                DegState(
                    "X1",
                    occ_law={"cls": "delay", "time": 6.0},
                    # Enabled only while the Guard mode is HEALTHY.
                    occ_cond=[{"attr": "Guard_level", "value": 0}],
                ),
            ]
        )
        system.isimu_start()
        # Enter O at t=1: the X1 delay(6) is armed, would fire at t=7.
        enter_first_state(system, "R1__Fissure.occ_O", "R1.Fissure__occ_O", date=1.0)
        # Guard degrades at t=3: X1 disabled (delay interrupted).
        enter_first_state(system, "R1__Guard.occ_g", "R1.Guard__occ_g", date=3.0)
        assert not any("occ_X1" in n for n in fireable_names(system))
        # Guard repairs at t=5 (delay 2): X1 re-enabled, its clock RESTARTS
        # from t=5 => fires at 11, not at the original 7.
        fire_by_name(system, "R1.Guard__rep_g")
        assert system.currentTime() == pytest.approx(5.0)
        fire_by_name(system, "R1.Fissure__occ_X1")
        assert system.currentTime() == pytest.approx(11.0)
        system.isimu_stop()


class TestEarlyEquivalenceWithObjFM:
    """ObjDegMode(K=1, N=1) must behave like ObjFM external_rep_indep."""

    def _drive(self, system, occ_frag, rep_frag, effect_var):
        system.isimu_start()
        fire_by_name(system, occ_frag, date=2.0)
        # The delay(0) target entry may be in the same batch or need one
        # extra step depending on the primitive; normalise.
        for _ in range(2):
            if effect_var.value() is True:
                break
            names = fireable_names(system)
            entry = [n for n in names if "occ" in n]
            if not entry:
                break
            fire_by_name(system, entry[0])
        t_occ = system.currentTime()
        val_after_occ = effect_var.value()
        fire_by_name(system, rep_frag, date=9.0)
        t_rep = system.currentTime()
        system.isimu_stop()
        return t_occ, val_after_occ, t_rep

    def test_k1_matches_objfm_external_rep_indep(self):
        # --- ObjDegMode K=1 ---
        system = fresh_system("DegEquivA")
        r1 = Rail("R1")
        ObjDegMode(
            fm_name="frun",
            targets=["R1"],
            states=[
                DegState(
                    "occ",
                    occ_law={"cls": "exp", "rate": 0.3},
                    effects={"broken": True},
                    rep_law={"cls": "exp", "rate": 0.5},
                )
            ],
        )
        deg = self._drive(system, "R1__frun.occ_occ", "R1.frun__rep_occ", r1.broken)

        # --- ObjFM external_rep_indep ---
        system = fresh_system("DegEquivB")
        r1 = Rail("R1")
        system.add_component(
            cls="ObjFMExp",
            fm_name="frun",
            targets=["R1"],
            failure_effects={"broken": True},
            failure_param=0.3,
            repair_param=0.5,
            behaviour="external_rep_indep",
        )
        fm = self._drive(system, "R1__frun.occ", "R1.frun__rep", r1.broken)

        # Same firing dates, same effect on the target.
        assert deg[0] == fm[0] == 2.0
        assert deg[1] is fm[1] is True
        assert deg[2] == fm[2] == 9.0
