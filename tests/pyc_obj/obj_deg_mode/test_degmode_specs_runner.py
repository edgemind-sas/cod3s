"""ObjDegMode wire integration: ObjFMGenericSpec -> runner -> simulation.

The wire path uses ObjFMGenericSpec (extra="allow"): ``states`` and
``occ_cond`` travel as extra fields, every FailureModeBaseSpec default
reaches the constructor via model_dump and must be tolerated (and any
explicit non-default value rejected — covered by the validation suite).

Also locks: the built-in registry entry, the add_failure_modes counter
(the runner swallows construction errors: a failed mode = count 0, NOT
an exception — documented limitation, the caller must check the count),
the SequenceAnalyser no-crash path, and the event-grammar contract
(structural assertions on a seeded run, replacing a brittle golden XML).
"""

import sys
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import pydantic
import pytest
import yaml

import Pycatshoo as Pyc

import cod3s
from cod3s.pycatshoo.sequence import SequenceAnalyser
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem
from cod3s.scripts.study_runner import add_failure_modes
from cod3s.specs.study_yaml import FailureModeSpec, ObjFMGenericSpec

sys.path.insert(0, str(Path(__file__).parent))


class Rail(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.ok_flag = self.addVariable("ok_flag", Pyc.TVarType.t_bool, True)
        self.ok_flag.setReinitialized(True)


def fresh_system(name):
    cod3s.terminate_session()
    return PycSystem(name=name)


SPEC_YAML = textwrap.dedent("""
    cls: ObjDegMode
    fm_name: Fissure
    targets: [R1, R2]
    occ_cond:
      - attr: ok_flag
        value: true
    states:
      - name: O
        occ_law: {cls: exp, rate: [0.3, 0.1]}
        rep_law: {cls: exp, rate: 0.5}
      - name: X1
        occ_law: {cls: delay, time: 6.0}
    """)

_SPEC_ADAPTER = pydantic.TypeAdapter(FailureModeSpec)


class TestSpecDispatch:
    def test_yaml_routes_to_generic_spec_with_extras(self):
        spec = _SPEC_ADAPTER.validate_python(yaml.safe_load(SPEC_YAML))
        assert isinstance(spec, ObjFMGenericSpec)
        assert spec.cls == "ObjDegMode"
        dumped = spec.model_dump()
        assert dumped["states"][0]["name"] == "O"
        assert dumped["occ_cond"] == [{"attr": "ok_flag", "value": True}]

    def test_model_dump_revalidates_identically(self):
        spec = _SPEC_ADAPTER.validate_python(yaml.safe_load(SPEC_YAML))
        spec2 = _SPEC_ADAPTER.validate_python(spec.model_dump())
        assert spec2.model_dump() == spec.model_dump()


class TestRunnerPath:
    def test_yaml_spec_builds_and_simulates(self):
        system = fresh_system("DegWire1")
        Rail("R1"), Rail("R2")
        spec = _SPEC_ADAPTER.validate_python(yaml.safe_load(SPEC_YAML))
        assert add_failure_modes(system, [spec]) == 1

        system.add_indicator_var(
            component="R1", var="Fissure_level", stats=["mean"], name="lv"
        )
        system.simulate(PycMCSimulationParam(nb_runs=500, schedule=[0.0, 10.0], seed=7))
        vals = system.indicators["lv_Fissure_level"].values["values"]
        assert vals.iloc[0] == 0.0
        assert vals.iloc[-1] > 0.1

    def test_runner_counter_zero_on_invalid_mode(self):
        """The runner swallows construction errors (log + continue):
        callers MUST assert the returned count — documented limitation
        of the GenericSpec path."""
        system = fresh_system("DegWire2")
        Rail("R1")
        bad = yaml.safe_load(SPEC_YAML)
        bad["targets"] = ["R1"]
        bad["states"][0]["occ_law"] = {"cls": "exp", "rate": [0.3, 0.1]}  # len 2 != 1
        spec = _SPEC_ADAPTER.validate_python(bad)
        assert add_failure_modes(system, [spec]) == 0

    def test_enabled_false_skips(self):
        system = fresh_system("DegWire3")
        Rail("R1"), Rail("R2")
        raw = yaml.safe_load(SPEC_YAML)
        raw["enabled"] = False
        spec = _SPEC_ADAPTER.validate_python(raw)
        assert add_failure_modes(system, [spec]) == 0


class TestSequenceAnalyser:
    def test_filter_objfm_cycles_ignores_degmode_without_crash(self):
        """ObjDegMode is not an ObjFM: auto-discovery must ignore it (its
        events are NOT occ/rep cycles to collapse) and the filtering path
        must run without error, preserving the degradation events."""
        system = fresh_system("DegWire4")
        Rail("R1"), Rail("R2")
        spec = _SPEC_ADAPTER.validate_python(yaml.safe_load(SPEC_YAML))
        assert add_failure_modes(system, [spec]) == 1
        system.monitorTransition("#.*")
        system.component("RX__Fissure").reapply_monitor_masks()
        system.simulate(PycMCSimulationParam(nb_runs=100, schedule=[10.0], seed=3))

        analyser = SequenceAnalyser.from_pyc_system(system)
        analyser.filter_objfm_cycles()  # auto-discovery: no ObjFM, no crash
        events = {ev.attr for seq in analyser.sequences for ev in seq.events}
        assert any(a.startswith("occ_O") for a in events)


class TestEventGrammarContract:
    """Structural contract for the downstream sequence parser (replaces
    a byte-level golden sequences.xml: seeds/timings/ordering churn must
    not break the lock, only NAME grammar changes may)."""

    def test_event_name_set_on_seeded_run(self):
        system = fresh_system("DegWire5")
        Rail("R1"), Rail("R2")
        ObjDegMode = cod3s.ObjDegMode
        ObjDegMode(
            fm_name="Fissure",
            targets=["R1", "R2"],
            states=[
                cod3s.DegState(
                    "O",
                    occ_law={"cls": "exp", "rate": [0.4, 0.2]},
                    rep_law={"cls": "exp", "rate": 0.5},
                ),
                cod3s.DegState(
                    "X1",
                    occ_law={"cls": "exp", "rate": 0.5},
                    rep_law={"cls": "exp", "rate": 0.3},
                ),
            ],
        )
        seq_path = Path("/tmp/cod3s-debug/degmode-grammar.xml")
        seq_path.parent.mkdir(parents=True, exist_ok=True)
        system.monitorTransition("#.*")
        system.component("RX__Fissure").reapply_monitor_masks()
        system.setResultFileName(str(seq_path), False)
        system.simulate(PycMCSimulationParam(nb_runs=200, schedule=[15.0], seed=42))

        root = ET.fromstring(seq_path.read_text())
        names = set()
        for seq in root.iter("SEQ"):
            for tr in seq.iter("TR"):
                names.add(tr.get("NAME", ""))

        expected = {
            # Carrier CC fires: order = number of __cc indices.
            "RX__Fissure.occ_O__cc_1",
            "RX__Fissure.occ_O__cc_2",
            "RX__Fissure.occ_O__cc_1_2",
            # Target trajectories: <target>.<fm_name>__<occ|rep>_<state>.
            "R1.Fissure__occ_O",
            "R1.Fissure__occ_X1",
            "R1.Fissure__rep_O",
            "R1.Fissure__rep_X1",
            "R2.Fissure__occ_O",
            "R2.Fissure__occ_X1",
            "R2.Fissure__rep_O",
            "R2.Fissure__rep_X1",
        }
        # Exact set: nothing else may leak into sequences (no carrier
        # re-arm, no plumbing).
        assert names == expected
