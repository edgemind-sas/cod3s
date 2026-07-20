"""ObjDegMode common-cause (orders k > 1): structure, invariants, MC.

Locks: the 2^N-1 combination automata and their naming, per-order
parameter names, drop of inactive orders, "an order-k fire moves exactly
k targets at the same instant", the all-targets-healthy guard, the
interleaving invariant (entry edges guarded by ctrl only), and the MC
symmetry per CC order (slow, seeded, 3-sigma tolerance).
"""

import sys
import time
import xml.etree.ElementTree as ET
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
        self.ok_flag = self.addVariable("ok_flag", Pyc.TVarType.t_bool, True)
        self.ok_flag.setReinitialized(True)


def fresh_system(name):
    cod3s.terminate_session()
    return PycSystem(name=name)


class TestCcfStructure:
    def test_seven_combos_and_per_order_params_for_n3(self):
        system = fresh_system("DegCcf1")
        Rail("R1"), Rail("R2"), Rail("R3")
        dm = ObjDegMode(
            fm_name="Fissure",
            targets=["R1", "R2", "R3"],
            states=[DegState("O", occ_law={"cls": "exp", "rate": [0.3, 0.2, 0.1]})],
        )
        aut_names = sorted(dm.automata_d.keys())
        assert aut_names == sorted(
            [
                "Fissure__cc_1",
                "Fissure__cc_2",
                "Fissure__cc_3",
                "Fissure__cc_1_2",
                "Fissure__cc_1_3",
                "Fissure__cc_2_3",
                "Fissure__cc_1_2_3",
            ]
        )
        var_names = {v.basename() for v in dm.variables()}
        assert {
            "lambda_O__1_o_3",
            "lambda_O__2_o_3",
            "lambda_O__3_o_3",
        } <= var_names
        # Fire transitions carry the cc suffix (order = number of indices).
        aut = dm.automata_d["Fissure__cc_1_2"]
        assert aut.get_transition_by_name("occ_O__cc_1_2") is not None

    def test_inactive_orders_dropped(self):
        system = fresh_system("DegCcf2")
        Rail("R1"), Rail("R2"), Rail("R3")
        dm = ObjDegMode(
            fm_name="Fissure",
            targets=["R1", "R2", "R3"],
            # Only order 2 active.
            states=[DegState("O", occ_law={"cls": "exp", "rate": [0.0, 0.2, 0.0]})],
        )
        aut_names = sorted(dm.automata_d.keys())
        assert aut_names == sorted(
            ["Fissure__cc_1_2", "Fissure__cc_1_3", "Fissure__cc_2_3"]
        )

    def test_scalar_rate_creates_order1_combos_only(self):
        system = fresh_system("DegCcf3")
        Rail("R1"), Rail("R2")
        dm = ObjDegMode(
            fm_name="Fissure",
            targets=["R1", "R2"],
            states=[DegState("O", occ_law={"cls": "exp", "rate": 0.3})],
        )
        assert sorted(dm.automata_d.keys()) == ["Fissure__cc_1", "Fissure__cc_2"]


class TestCcfSemantics:
    def _build_n2(self, lambdas=(0.3, 0.1), **state_kwargs):
        system = fresh_system("DegCcfSem")
        rails = [Rail("R1"), Rail("R2")]
        ObjDegMode(
            fm_name="Fissure",
            targets=["R1", "R2"],
            states=[
                DegState(
                    "O",
                    occ_law={"cls": "exp", "rate": list(lambdas)},
                    rep_law={"cls": "exp", "rate": 0.5},
                    **state_kwargs,
                )
            ],
        )
        return system, rails

    def test_order2_fire_moves_exactly_two_targets_same_instant(self):
        system, rails = self._build_n2()
        lv = [r.variable("Fissure_level") for r in rails]
        system.isimu_start()
        fire_by_name(system, "Fissure.occ_O__cc_1_2", date=3.0)
        # Both delay(0) entries fire in one batch on the next step.
        fired = fire_by_name(system, "Fissure__occ_O")
        assert sum(1 for f in fired if "Fissure__occ_O" in f) == 2
        assert system.currentTime() == 3.0
        assert lv[0].value() == 1 and lv[1].value() == 1
        system.isimu_stop()

    def test_all_targets_healthy_guard(self):
        system, rails = self._build_n2()
        system.isimu_start()
        # Degrade R1 alone (order-1 combo).
        enter_first_state(system, "Fissure.occ_O__cc_1", "R1.Fissure__occ_O", date=1.0)
        names = fireable_names(system)
        # Any combo containing R1 is blocked; {2} stays fireable.
        assert not any("occ_O__cc_1_2" in n for n in names), names
        assert any("occ_O__cc_2" in n for n in names), names
        # After R1 repairs, the pair combo is fireable again.
        fire_by_name(system, "R1.Fissure__rep_O", date=2.0)
        assert any("occ_O__cc_1_2" in n for n in fireable_names(system))
        system.isimu_stop()

    def test_interleaving_entry_guarded_by_ctrl_only(self):
        """The entry edges must NOT re-test occ_cond: when the first
        target's D1 state effects flip the global condition within the
        same instant, the second target must still enter D1 (otherwise
        its ctrl latch would be stranded)."""
        system = fresh_system("DegCcfInter")
        rails = [Rail("R1"), Rail("R2")]
        ObjDegMode(
            fm_name="Fissure",
            targets=["R1", "R2"],
            # Global gate: each target's own ok_flag must be True...
            occ_cond=[{"attr": "ok_flag", "value": True}],
            states=[
                DegState(
                    "O",
                    occ_law={"cls": "exp", "rate": [0.0, 0.1]},
                    # ...and entering O clamps ok_flag to False.
                    effects={"ok_flag": False},
                )
            ],
        )
        lv = [r.variable("Fissure_level") for r in rails]
        system.isimu_start()
        fire_by_name(system, "Fissure.occ_O__cc_1_2", date=2.0)
        fire_by_name(system, "Fissure__occ_O")
        # Both targets reached D1 despite the condition flip; no latch left.
        assert lv[0].value() == 1 and lv[1].value() == 1
        assert fireable_names(system) == []  # no repair, absorbing; no orphans
        system.isimu_stop()

    def test_occ_cond_false_blocks_all_combos(self):
        system = fresh_system("DegCcfCond")
        Rail("R1"), Rail("R2")
        r3 = Rail("R3")
        # Gate carried by a third component, targeted via explicit obj.
        ObjDegMode(
            fm_name="Fissure",
            targets=["R1", "R2"],
            occ_cond=[{"obj": "R3", "attr": "ok_flag", "value": False}],
            states=[DegState("O", occ_law={"cls": "exp", "rate": [0.3, 0.1]})],
        )
        system.isimu_start()
        # R3.ok_flag is True => cond (== False) is false => nothing fireable.
        assert fireable_names(system) == []
        system.isimu_stop()


@pytest.mark.slow
class TestCcfMonteCarloSymmetry:
    def test_order2_symmetry_and_target_occupation(self, tmp_path):
        """With only order 2 active on N=3, the three pair combos must
        fire with equal frequencies, and the three targets must show the
        same degradation occupation (any asymmetry beyond a few sigma =
        wiring bug). Also the anti-hang guard for the whole CC machinery.
        """
        system = fresh_system("DegCcfMc")
        for tn in ("R1", "R2", "R3"):
            Rail(tn)
        ObjDegMode(
            fm_name="Fissure",
            targets=["R1", "R2", "R3"],
            states=[
                DegState(
                    "O",
                    occ_law={"cls": "exp", "rate": [0.0, 0.15, 0.0]},
                    rep_law={"cls": "exp", "rate": 0.4},
                )
            ],
        )
        for i, tn in enumerate(("R1", "R2", "R3"), start=1):
            system.add_indicator_var(
                component=tn, var="Fissure_level", stats=["mean"], name=f"lv{i}"
            )

        seq_path = tmp_path / "degmode-ccf-mc.xml"
        system.monitorTransition("#.*occ_O.*")
        # Re-apply masks after monitorTransition (study-runner contract).
        for comp in [system.component("RX__Fissure")]:
            comp.reapply_monitor_masks()
        system.setResultFileName(str(seq_path), False)

        t0 = time.monotonic()
        system.simulate(
            PycMCSimulationParam(nb_runs=3000, schedule=[0.0, 10.0], seed=1234)
        )
        elapsed = time.monotonic() - t0
        assert elapsed < 30.0  # anti-hang guard

        # No leak at t=0, symmetric occupation across targets.
        means = []
        for i in (1, 2, 3):
            vals = system.indicators[f"lv{i}_Fissure_level"].values["values"]
            assert vals.iloc[0] == 0.0
            means.append(float(vals.iloc[-1]))
        avg = sum(means) / 3
        assert avg > 0.05  # activity observed
        for m in means:
            # Occupation symmetry: each target within 15% of the average
            # (3000 runs => sampling noise well below that).
            assert m == pytest.approx(avg, rel=0.15)

        # Combo firing symmetry from the sequence dump: equal counts for
        # the three pair combos (binomial 3-sigma half-width).
        root = ET.fromstring(seq_path.read_text())
        counts = {"cc_1_2": 0, "cc_1_3": 0, "cc_2_3": 0}
        for seq in root.iter("SEQ"):
            for tr in seq.iter("TR"):
                name = tr.get("NAME", "")
                for key in counts:
                    if name.endswith(f"occ_O__{key}"):
                        counts[key] += 1
        total = sum(counts.values())
        assert total > 300, counts
        expected = total / 3
        # 3-sigma on a multinomial cell (p=1/3): sigma = sqrt(total*p*(1-p)).
        sigma = (total * (1 / 3) * (2 / 3)) ** 0.5
        for key, cnt in counts.items():
            assert abs(cnt - expected) < 3 * sigma, (key, counts)
