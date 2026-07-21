"""ObjMode2S wire integration: ObjFMGenericSpec -> runner -> simulation.

The wire path uses ObjFMGenericSpec (extra="allow"): ``occ_law`` /
``not_occ_law`` travel as extra fields, ``fm_name`` / ``failure_cond``
are functional constructor aliases, and every FailureModeBaseSpec
default reaches the constructor via model_dump and must be tolerated
(explicit non-defaults rejected — covered by the core validation
suite).

Also locks: the built-in registry entry, the add_failure_modes counter
(swallow semantics), the hardened FailureModeParamOverride (values
propagated to the backend parameter variables — the historical bare
setattr was a silent no-op on the simulation), and the event-grammar
contract on a seeded run.
"""

import textwrap
import xml.etree.ElementTree as ET

import pydantic
import pytest
import yaml

import Pycatshoo as Pyc

import cod3s
from cod3s.pycatshoo.system import PycMCSimulationParam, PycSystem
from cod3s.scripts.study_runner import (
    _apply_failure_mode_param_override,
    add_failure_modes,
)
from cod3s.specs.study_yaml import (
    FailureModeParamOverride,
    FailureModeSpec,
    ObjFMGenericSpec,
)


class Equipment(cod3s.PycComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.working = self.addVariable("working", Pyc.TVarType.t_bool, True)
        self.working.setReinitialized(True)


def fresh_system(name):
    cod3s.terminate_session()
    return PycSystem(name=name)


SPEC_YAML = textwrap.dedent("""
    cls: ObjMode2S
    fm_name: wear
    targets: [E1]
    occ_law: {cls: exp, rate: 0.4}
    not_occ_law: {cls: delay, time: 1.5}
    occ_effects: {working: false}
    """)

_SPEC_ADAPTER = pydantic.TypeAdapter(FailureModeSpec)


class TestSpecDispatch:
    def test_yaml_routes_to_generic_spec_with_extras(self):
        spec = _SPEC_ADAPTER.validate_python(yaml.safe_load(SPEC_YAML))
        assert isinstance(spec, ObjFMGenericSpec)
        assert spec.cls == "ObjMode2S"
        dumped = spec.model_dump()
        assert dumped["occ_law"] == {"cls": "exp", "rate": 0.4}
        assert dumped["not_occ_law"] == {"cls": "delay", "time": 1.5}

    def test_model_dump_revalidates_identically(self):
        spec = _SPEC_ADAPTER.validate_python(yaml.safe_load(SPEC_YAML))
        spec2 = _SPEC_ADAPTER.validate_python(spec.model_dump())
        assert spec2.model_dump() == spec.model_dump()


class TestRunnerPath:
    def test_yaml_spec_builds_and_simulates(self):
        system = fresh_system("Mode2SWire1")
        Equipment("E1")
        spec = _SPEC_ADAPTER.validate_python(yaml.safe_load(SPEC_YAML))
        assert add_failure_modes(system, [spec]) == 1

        mode = system.comp["E1__wear"]
        assert mode.mode_name == "wear"
        assert mode.occ_cond is True  # BaseSpec failure_cond default = unset

        system.add_indicator_var(
            component="E1", var="working", stats=["mean"], name="up"
        )
        system.simulate(
            PycMCSimulationParam(nb_runs=500, schedule=[0.0, 20.0], seed=11)
        )
        vals = system.indicators["up_working"].values["values"]
        assert vals.iloc[0] == 1.0
        # Alternating renewal at lambda=0.4 / ttr=1.5: availability
        # settles around 0.625 — anything near 1.0 would mean the mode
        # silently did nothing.
        assert 0.4 < float(vals.iloc[-1]) < 0.85

    def test_runner_counter_zero_on_invalid_mode(self):
        """Swallow semantics: a failed construction = count 0, not an
        exception (callers must check the count — or use
        simulation.strict_failure_modes)."""
        system = fresh_system("Mode2SWire2")
        Equipment("E1")
        bad = yaml.safe_load(SPEC_YAML)
        bad["occ_law"] = {"cls": "exp", "rate": [0.4, 0.2]}  # len 2 != 1 target
        spec = _SPEC_ADAPTER.validate_python(bad)
        assert add_failure_modes(system, [spec]) == 0

    def test_enabled_false_skips(self):
        system = fresh_system("Mode2SWire3")
        Equipment("E1")
        raw = yaml.safe_load(SPEC_YAML)
        raw["enabled"] = False
        spec = _SPEC_ADAPTER.validate_python(raw)
        assert add_failure_modes(system, [spec]) == 0


class TestParamOverrideHardened:
    def test_override_propagates_to_backend_variables(self):
        """The historical bare setattr changed nothing in the
        simulation (the laws are bound to the parameter VARIABLES).
        The hardened override pushes the values into the variables —
        on façades and native modes alike."""
        system = fresh_system("Mode2SWireOv")
        Equipment("E1")
        fm = cod3s.ObjFMExp(
            fm_name="frun",
            targets=["E1"],
            failure_param=0.1,
            repair_param=0.2,
        )
        ov = FailureModeParamOverride(
            fm_name="E1__frun", field="failure_param", value=[0.7]
        )
        _apply_failure_mode_param_override(system, ov, logger=None)
        assert fm.failure_param == [0.7]
        assert fm.occ_param == [0.7]
        assert fm.variable("lambda").value() == pytest.approx(0.7)

    def test_override_honours_custom_param_name_order_prefix(self):
        """The variables carry the mode's OWN suffix format; resolving
        them with the default format silently targets names that do not
        exist and leaves the simulation on the baseline (finding 5)."""
        system = fresh_system("Mode2SWireOvPrefix")
        Equipment("E1")
        Equipment("E2")
        fm = cod3s.ObjFMExp(
            fm_name="frun",
            targets=["E1", "E2"],
            failure_param=[0.1, 0.2],
            repair_param=[0.3, 0.4],
            param_name_order_prefix="_ord{order}",
        )
        ov = FailureModeParamOverride(
            fm_name="EX__frun", field="failure_param", value=[0.9, 0.8]
        )
        _apply_failure_mode_param_override(system, ov, logger=None)
        assert fm.variable("lambda_ord1").value() == pytest.approx(0.9)
        assert fm.variable("lambda_ord2").value() == pytest.approx(0.8)
        assert fm.failure_param == [0.9, 0.8]

    def test_override_writes_every_parameter_of_a_multi_param_law(self):
        """A per-order tuple carries one value per declared parameter;
        pushing only the first leaves a half-overridden law while the
        run is reported as fully overridden (finding 6)."""

        class ObjFMTwoParam(cod3s.ObjFMExp):
            def set_default_failure_param_name(self):
                if not self.failure_param_name:
                    self.failure_param_name = ["wk", "wlam"]

            def set_occ_law_failure(self, params):
                return {"cls": "exp", "rate": params["wk"]}

        system = fresh_system("Mode2SWireOvMulti")
        Equipment("E1")
        fm = ObjFMTwoParam(
            fm_name="wb",
            targets=["E1"],
            failure_param=[(2.0, 1500.0)],
            repair_param=0.5,
        )
        ov = FailureModeParamOverride(
            fm_name="E1__wb", field="failure_param", value=[(3.0, 9999.0)]
        )
        _apply_failure_mode_param_override(system, ov, logger=None)
        assert fm.variable("wk").value() == pytest.approx(3.0)
        assert fm.variable("wlam").value() == pytest.approx(9999.0)

    def test_override_partial_value_tuple_is_refused_atomically(self):
        """An incomplete per-order tuple must abort the whole override,
        not write the parameters it happens to cover."""

        class ObjFMTwoParam(cod3s.ObjFMExp):
            def set_default_failure_param_name(self):
                if not self.failure_param_name:
                    self.failure_param_name = ["wk", "wlam"]

            def set_occ_law_failure(self, params):
                return {"cls": "exp", "rate": params["wk"]}

        system = fresh_system("Mode2SWireOvPartial")
        Equipment("E1")
        fm = ObjFMTwoParam(
            fm_name="wb",
            targets=["E1"],
            failure_param=[(2.0, 1500.0)],
            repair_param=0.5,
        )
        ov = FailureModeParamOverride(
            fm_name="E1__wb", field="failure_param", value=[(3.0,)]
        )
        _apply_failure_mode_param_override(system, ov, logger=None)
        assert fm.variable("wk").value() == pytest.approx(2.0)
        assert fm.variable("wlam").value() == pytest.approx(1500.0)
        assert fm.failure_param == [(2.0, 1500.0)]

    def test_override_on_mode_without_param_variables_is_refused(self):
        """A self-hosted mode bakes its laws as literals: there is no
        variable to override, so the runner must warn instead of
        reporting a success for a guaranteed no-op (finding 7)."""
        system = fresh_system("Mode2SWireOvSelf")
        Equipment("E1")
        cod3s.ObjMode2S(
            mode_name="watch",
            targets=None,
            occ_law={"cls": "delay", "time": 3},
            not_occ_law={"cls": "delay", "time": 1},
            occ_cond=False,
        )

        class Log:
            def __init__(self):
                self.info3_calls = []
                self.error_calls = []
                self.warning_calls = []

            def info3(self, msg):
                self.info3_calls.append(msg)

            def error(self, msg):
                self.error_calls.append(msg)

            def warning(self, msg):
                self.warning_calls.append(msg)

        logger = Log()
        ov = FailureModeParamOverride(
            fm_name="watch", field="failure_param", value=[42.0]
        )
        _apply_failure_mode_param_override(system, ov, logger=logger)
        assert logger.info3_calls == [], "a no-op must never be logged as applied"
        assert len(logger.error_calls) + len(logger.warning_calls) == 1

    def test_override_wrong_length_is_not_logged_as_success(self):
        system = fresh_system("Mode2SWireOvBad")
        Equipment("E1")
        cod3s.ObjFMExp(
            fm_name="frun",
            targets=["E1"],
            failure_param=0.1,
            repair_param=0.2,
        )
        ov = FailureModeParamOverride(
            fm_name="E1__frun", field="failure_param", value=[0.7, 0.8]
        )
        # Wrong per-order length: error path (no exception leaks).
        _apply_failure_mode_param_override(system, ov, logger=None)
        fm = system.comp["E1__frun"]
        assert fm.variable("lambda").value() == pytest.approx(0.1)


class TestEventGrammarContract:
    def test_event_name_set_on_seeded_run(self, tmp_path):
        """Exact NAME set of a native mixed-law mode under wildcard
        monitoring: occ / not_occ per target-mode, nothing else (no
        parked branches, no re-arm plumbing)."""
        system = fresh_system("Mode2SWire5")
        Equipment("E1")
        cod3s.ObjMode2S(
            mode_name="wear",
            targets=["E1"],
            occ_law={"cls": "exp", "rate": 0.4},
            not_occ_law={"cls": "inst", "prob": 0.6},
            occ_effects={"working": False},
        )
        seq_path = tmp_path / "mode2s-grammar.xml"
        system.monitorTransition("#.*")
        system.component("E1__wear").reapply_monitor_masks()
        system.setResultFileName(str(seq_path), False)
        system.simulate(PycMCSimulationParam(nb_runs=200, schedule=[15.0], seed=42))

        root = ET.fromstring(seq_path.read_text())
        names = set()
        for seq in root.iter("SEQ"):
            for tr in seq.iter("TR"):
                names.add(tr.get("NAME", ""))

        # occ: exp occurrences; not_occ: only landed return draws (the
        # occ_star branch and the re-arm are masked out).
        assert names == {"E1__wear.occ", "E1__wear.not_occ"}
